import { library } from '../../state/library';
import { el, escapeHtml, patchList, q, setClass, setHidden, setStyleVar, setText, setValue } from '../../ui/dom';
import { Panel } from '../../ui/panel';
import { toast } from '../../ui/toast';
import { registerModule } from '../registry';
import { runOutput } from '../shared/tasks';
import { OutputModule } from './base';
import { PageView, type Layout } from './page';

interface Crop { z: number; x: number; y: number }
interface TextStyle { style?: string; align?: string; color?: string }
interface BookPage { template: string; photos: Array<number | null>; texts: string[]; crops?: Array<Crop | null>; styles?: Array<TextStyle | null> }
const STYLE_NAMES: Array<[string, string]> = [['', 'Book Default'], ['title', 'Title'], ['heading', 'Heading'], ['body', 'Body'], ['caption', 'Caption'], ['quote', 'Quote'], ['mono', 'Typewriter']];
interface TemplateDef { name: string; cells: number[][]; texts: number[][] }
type View = 'multi' | 'spread' | 'single';

class BookModule extends OutputModule {
  readonly id = 'book';
  readonly label = 'Book';
  readonly icon = 'modBook';
  readonly key = 'Alt+Mod+4';
  readonly order = 4;
  protected readonly optionsCmd = 'book.options';
  protected readonly kind = 'book';
  private lay: Layout | null = null;
  private selected = 0;
  private view: View = 'multi';
  private zoom = 220;
  private seq = 0;
  private readonly scroller = el('<div class="fl-book-scroll"></div>');
  private readonly spreads = el('<div class="fl-book-spreads"></div>');
  private readonly empty = el('<div class="fl-empty fl-book-empty" hidden><div class="fl-empty-card"><div class="fl-empty-title">Lay out a book</div><div class="fl-empty-sub">Auto Layout places the filmstrip photos on pages. Drag photos onto cells to change them, and pick page templates on the right.</div><div class="fl-empty-actions"><button class="cv-btn cv-btn-primary" type="button" data-auto>Auto Layout</button></div></div></div>');
  private readonly views: PageView[] = [];
  private readonly templatesBox = el('<div class="fl-tpl-grid"></div>');
  private readonly textBox = el('<div class="fl-form"></div>');
  private readonly pageInfo = el('<p class="cv-note"></p>');
  private readonly cellBox = el('<div class="fl-book-cell" hidden><div class="fl-sub">Photo in Cell</div><label class="fl-opt"><span>Zoom</span><input class="cv-slider" type="range" min="100" max="400" step="5" value="100" data-cz></label><p class="cv-note">Drag the photo in its cell to reposition it.</p><div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm" type="button" data-creset>Reset</button></div></div>');
  private selectedCell = -1;
  private pan: { view: PageView; cell: number; node: HTMLElement; sx: number; sy: number; c0: Crop; moved: boolean } | null = null;
  private readonly viewSeg = el('<div class="cv-seg fl-seg-sm"><button type="button" data-v="multi">Multi-Page</button><button type="button" data-v="spread">Spread</button><button type="button" data-v="single">Single Page</button></div>');

  protected keepOnTemplate(s: Record<string, unknown>): Record<string, unknown> {
    return { ...s, cover: this.get('cover'), pages: this.get('pages') };
  }

  private pages(): BookPage[] { return (this.get('pages') as BookPage[]) ?? []; }
  private tdefs(): Record<string, TemplateDef> { return (this.options?.templates as Record<string, TemplateDef>) ?? {}; }

  protected buildToolbar(bar: HTMLElement): void {
    this.viewSeg.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-v]');
      if (b) { this.view = b.dataset.v as View; this.paint(); }
    });
    const z = el<HTMLInputElement>('<input class="cv-slider fl-tb-size" type="range" min="120" max="520" step="10" aria-label="Page size">');
    z.value = String(this.zoom);
    z.addEventListener('input', () => { this.zoom = Number(z.value); this.paint(); });
    bar.append(this.viewSeg, el('<span class="fl-tb-sep"></span>'), el('<span class="fl-tb-label">Page size</span>'), z);
  }

  protected buildStage(stage: HTMLElement): void {
    const root = el('<div class="fl-out-stage fl-book-stage"></div>');
    this.scroller.appendChild(this.spreads);
    root.append(this.scroller, this.empty);
    stage.appendChild(root);
    this.empty.addEventListener('click', (e) => { if ((e.target as HTMLElement).closest('[data-auto]')) void this.autoLayout(); });
    new ResizeObserver(() => { if (this.view !== 'multi') this.paint(); }).observe(root);
  }

  protected buildPanels(right: HTMLElement): void {
    const sizes = () => Object.entries((this.options?.sizes as Record<string, { name: string }>) ?? {}).map(([k, v]) => [k, v.name] as [string, string]);
    this.formPanel(right, 'settings', 'Book Settings', [
      { path: 'size', label: 'Size', kind: 'select', options: sizes },
      { path: 'job.output', label: 'Book', kind: 'seg', options: [['pdf', 'PDF'], ['jpeg', 'JPEG']] },
      { path: 'job.ppi', label: 'Resolution', kind: 'number', min: 72, max: 600, step: 10, unit: 'ppi' },
      { path: 'job.quality', label: 'JPEG quality', kind: 'range', min: 50, max: 100 },
      { path: 'job.sharpen.on', label: 'Sharpening', kind: 'check' },
      { path: 'job.space', label: 'Color', kind: 'select', options: [['srgb', 'sRGB'], ['adobergb', 'Adobe RGB (1998)']] },
    ]);
    this.formPanel(right, 'auto', 'Auto Layout', [
      { path: 'autoLayout', label: 'Preset', kind: 'select', options: [['mixed', 'Mixed layouts'], ['one', 'One photo per page']] },
    ]).body.appendChild(this.buttons([['auto', 'Auto Layout'], ['clear', 'Clear Layout']]));
    const pp = new Panel('book.page', 'Page');
    pp.body.append(this.pageInfo, this.templatesBox, this.buttons([['add', 'Add Page'], ['remove', 'Remove Page']]), this.cellBox);
    right.appendChild(pp.root);
    q<HTMLInputElement>(this.cellBox, '[data-cz]').addEventListener('input', (e) => this.setCrop({ z: Number((e.target as HTMLInputElement).value) / 100 }));
    q(this.cellBox, '[data-creset]').addEventListener('click', () => this.setCrop(null));
    this.templatesBox.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-tpl]');
      if (b) this.setTemplate(b.dataset.tpl as string);
    });
    const pt = new Panel('book.text', 'Text');
    pt.body.appendChild(this.textBox);
    right.appendChild(pt.root);
    this.textBox.addEventListener('input', (e) => {
      const i = (e.target as HTMLElement).closest<HTMLInputElement | HTMLTextAreaElement>('[data-t]');
      if (i) this.setText(Number(i.dataset.t), i.value);
    });
    this.textBox.addEventListener('change', (e) => {
      const s = (e.target as HTMLElement).closest<HTMLInputElement | HTMLSelectElement>('[data-ts]');
      if (s) this.setStyle(Number(s.dataset.ts), s.dataset.k as keyof TextStyle, s.value);
    });
    this.formPanel(right, 'type', 'Type and Background', [
      { path: 'background', label: 'Background', kind: 'color' },
      { path: 'textColor', label: 'Text color', kind: 'color' },
      { path: 'titleSize', label: 'Title size', kind: 'range', min: 10, max: 72, unit: ' pt' },
      { path: 'textSize', label: 'Text size', kind: 'range', min: 6, max: 24, unit: ' pt' },
      { path: 'pageNumbers', label: 'Page numbers', kind: 'check' },
      { path: 'captions', label: 'Photo captions', kind: 'check' },
      { path: 'captionField', label: 'Caption', kind: 'select', options: [['title', 'Title'], ['caption', 'Caption'], ['titleCaption', 'Title and Caption'], ['fileName', 'Filename'], ['date', 'Date'], ['exposure', 'Exposure']], show: () => !!this.get('captions') },
    ]);
  }

  private buttons(items: Array<[string, string]>): HTMLElement {
    const row = el(`<div class="fl-row fl-row-end">${items.map(([a, l]) => `<button class="cv-btn fl-btn-sm" type="button" data-act="${a}">${escapeHtml(l)}</button>`).join('')}</div>`);
    row.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-act]');
      if (!b) return;
      const a = b.dataset.act;
      if (a === 'auto') void this.autoLayout();
      else if (a === 'clear') { this.set('pages', []); this.set('cover', { template: 'cover', photos: [], texts: [String((this.get('cover.texts') as string[] | undefined)?.[0] ?? 'Untitled'), ''] }); this.selected = 0; }
      else if (a === 'add') { const p = [...this.pages()]; p.splice(Math.max(0, this.selected), 0, { template: 'single', photos: [], texts: [] }); this.set('pages', p); this.selected += 1; }
      else if (a === 'remove' && this.selected > 0) { const p = [...this.pages()]; p.splice(this.selected - 1, 1); this.set('pages', p); this.selected = Math.min(this.selected, p.length); }
    });
    return row;
  }

  protected buildFoots(_left: HTMLElement, right: HTMLElement): void {
    const row = el('<div class="fl-foot-row"><button class="cv-btn cv-btn-primary" type="button">Export Book...</button></div>');
    row.addEventListener('click', (e) => { if ((e.target as HTMLElement).closest('button')) void this.exportBook(); });
    right.appendChild(row);
  }

  private async autoLayout(): Promise<void> {
    const ids = this.ids();
    if (!ids.length) { toast('Add photos to the filmstrip first'); return; }
    try {
      const r = await this.ctx.api.cmd<{ pages: BookPage[]; cover: BookPage }>('book.autoLayout', { ids, mode: this.get('autoLayout') });
      const title = (this.get('cover.texts') as string[] | undefined)?.[0];
      r.cover.texts = [title && title !== 'Untitled' ? title : sourceTitle(), ''];
      this.set('cover', r.cover);
      this.set('pages', r.pages);
      this.selected = 0;
    } catch (err) { this.ctx.fail(err); }
  }

  private pageRef(i: number): BookPage | null {
    if (i === 0) return (this.get('cover') as BookPage) ?? null;
    return this.pages()[i - 1] ?? null;
  }

  private writePage(i: number, page: BookPage): void {
    if (i === 0) this.set('cover', page);
    else { const p = [...this.pages()]; p[i - 1] = page; this.set('pages', p); }
  }

  private setTemplate(t: string): void {
    const page = this.pageRef(this.selected);
    if (!page) return;
    this.writePage(this.selected, { ...page, template: t, texts: (page.texts ?? []).slice(0, this.tdefs()[t]?.texts.length ?? 0) });
  }

  private setText(index: number, value: string): void {
    const page = this.pageRef(this.selected);
    if (!page) return;
    const texts = [...(page.texts ?? [])];
    while (texts.length <= index) texts.push('');
    texts[index] = value;
    this.writePage(this.selected, { ...page, texts });
  }

  private setStyle(index: number, k: keyof TextStyle, value: string): void {
    const page = this.pageRef(this.selected);
    if (!page) return;
    const styles = [...(page.styles ?? [])];
    while (styles.length <= index) styles.push(null);
    const next: TextStyle = { ...(styles[index] ?? {}), [k]: value };
    if (!value) delete next[k];
    styles[index] = Object.keys(next).length ? next : null;
    this.writePage(this.selected, { ...page, styles });
  }

  private crop(pageIndex: number, cell: number): Crop {
    const c = this.pageRef(pageIndex)?.crops?.[cell];
    return { z: c?.z ?? 1, x: c?.x ?? 0, y: c?.y ?? 0 };
  }

  private setCrop(patch: Partial<Crop> | null, pageIndex = this.selected, cell = this.selectedCell): void {
    const page = this.pageRef(pageIndex);
    if (!page || cell < 0) return;
    const crops = [...(page.crops ?? [])];
    while (crops.length <= cell) crops.push(null);
    crops[cell] = patch === null ? null : { ...this.crop(pageIndex, cell), ...patch };
    this.writePage(pageIndex, { ...page, crops });
  }

  private startPan(view: PageView, e: PointerEvent): void {
    const node = (e.target as HTMLElement).closest<HTMLElement>('.fl-pcell');
    if (!node || e.button !== 0 || view.index !== this.selected || Number(node.dataset.key) !== this.selectedCell || node.classList.contains('is-empty')) return;
    e.preventDefault();
    node.setPointerCapture(e.pointerId);
    this.pan = { view, cell: this.selectedCell, node, sx: e.clientX, sy: e.clientY, c0: this.crop(view.index, this.selectedCell), moved: false };
    setClass(node, 'is-panning', true);
  }

  private movePan(e: PointerEvent): void {
    const p = this.pan;
    if (!p) return;
    const lay = this.lay;
    const c = lay?.pages[p.view.index]?.cells[p.cell];
    if (!c?.img) return;
    const r = p.node.getBoundingClientRect();
    const iw = c.img.w / c.w, ih = c.img.h / c.h;
    const sx = Math.max(1e-3, iw - 1), sy = Math.max(1e-3, ih - 1);
    const x = Math.max(-1, Math.min(1, p.c0.x - (2 * (e.clientX - p.sx)) / (r.width * sx)));
    const y = Math.max(-1, Math.min(1, p.c0.y - (2 * (e.clientY - p.sy)) / (r.height * sy)));
    p.moved = true;
    const pct = (v: number) => `${(v * 100).toFixed(4)}%`;
    setStyleVar(p.node, '--ix', pct(iw > 1 ? -(iw - 1) * (0.5 + 0.5 * x) : (1 - iw) / 2));
    setStyleVar(p.node, '--iy', pct(ih > 1 ? -(ih - 1) * (0.5 + 0.5 * y) : (1 - ih) / 2));
    p.node.dataset.panx = String(x);
    p.node.dataset.pany = String(y);
  }

  private endPan(): void {
    const p = this.pan;
    this.pan = null;
    if (!p) return;
    setClass(p.node, 'is-panning', false);
    if (p.moved) this.setCrop({ x: Number(p.node.dataset.panx ?? p.c0.x), y: Number(p.node.dataset.pany ?? p.c0.y) }, p.view.index, p.cell);
  }

  private assign(pageIndex: number, cell: number, ids: number[]): void {
    const page = this.pageRef(pageIndex);
    if (!page || !ids.length) return;
    const photos = [...(page.photos ?? [])];
    ids.forEach((id, k) => { while (photos.length <= cell + k) photos.push(null); photos[cell + k] = id; });
    const n = this.tdefs()[page.template]?.cells.length ?? photos.length;
    this.writePage(pageIndex, { ...page, photos: photos.slice(0, n) });
  }

  protected async refresh(): Promise<void> {
    const seq = ++this.seq;
    const lay = await this.ctx.api.cmd<Layout>('book.layout', { settings: this.settings });
    if (seq !== this.seq) return;
    this.lay = lay;
    this.selected = Math.min(this.selected, lay.pages.length - 1);
    this.paint();
    this.syncPagePanel();
  }

  private paint(): void {
    const lay = this.lay;
    if (!lay) return;
    setHidden(this.empty, this.pages().length > 0);
    setHidden(this.scroller, this.pages().length === 0);
    for (const b of Array.from(this.viewSeg.querySelectorAll<HTMLElement>('[data-v]'))) setClass(b, 'is-on', b.dataset.v === this.view);
    const stage = this.scroller.parentElement as HTMLElement;
    let width = this.zoom;
    let groups: number[][] = [];
    const n = lay.pages.length;
    if (this.view === 'single') {
      width = Math.max(120, Math.min((stage.clientWidth - 80), (stage.clientHeight - 80) * lay.page.w / lay.page.h));
      groups = [[this.selected]];
    } else {
      groups.push([0]);
      for (let i = 1; i < n; i += 2) groups.push(i + 1 < n ? [i, i + 1] : [i]);
      if (this.view === 'spread') {
        const g = groups.find((x) => x.includes(this.selected)) ?? groups[0];
        groups = [g];
        width = Math.max(120, Math.min((stage.clientWidth - 100) / 2, (stage.clientHeight - 80) * lay.page.w / lay.page.h));
      }
    }
    patchList(this.spreads, groups.map((g) => ({ key: g.join('-'), g })), {
      key: (x) => x.key,
      create: () => el('<div class="fl-spread"><div class="fl-spread-pages"></div><div class="fl-spread-label"></div></div>'),
      update: () => undefined,
    });
    let vi = 0;
    for (const [gi, node] of Array.from(this.spreads.children).entries()) {
      const g = groups[gi];
      const host = q(node as HTMLElement, '.fl-spread-pages');
      setText(q(node as HTMLElement, '.fl-spread-label'), g[0] === 0 ? 'Cover' : g.length === 2 ? `Pages ${g[0]} and ${g[1]}` : `Page ${g[0]}`);
      setClass(node, 'is-cover', g[0] === 0);
      while (host.children.length > g.length) host.lastElementChild?.remove();
      for (const [k, pi] of g.entries()) {
        let v = this.views[vi];
        if (!v) {
          v = new PageView();
          const view = v;
          v.onDropIds = (cell, ids) => this.assign(view.index, cell, ids);
          v.onCell = (cell, e) => { this.selected = view.index; this.selectedCell = cell; this.paintSelection(); this.syncPagePanel(); e.stopPropagation(); };
          v.root.addEventListener('click', () => { if (this.selected !== view.index) this.selectedCell = -1; this.selected = view.index; this.paintSelection(); this.syncPagePanel(); });
          v.root.addEventListener('pointerdown', (e) => this.startPan(view, e));
          v.root.addEventListener('pointermove', (e) => this.movePan(e));
          v.root.addEventListener('pointerup', () => this.endPan());
          v.root.addEventListener('pointercancel', () => this.endPan());
          v.root.addEventListener('contextmenu', (e) => {
            const c = (e.target as HTMLElement).closest<HTMLElement>('.fl-pcell');
            if (!c) return;
            e.preventDefault();
            const page = this.pageRef(view.index);
            if (!page) return;
            const photos = [...(page.photos ?? [])];
            photos[Number(c.dataset.key)] = null;
            this.writePage(view.index, { ...page, photos });
          });
          this.views[vi] = v;
        }
        v.index = pi;
        if (host.children[k] !== v.root) host.insertBefore(v.root, host.children[k] ?? null);
        v.render(lay, lay.pages[pi], width, { background: String(this.get('background') ?? '#fff'), editable: true });
        vi += 1;
      }
    }
    this.paintSelection();
    const sz = ((this.options?.sizes as Record<string, { name: string }>) ?? {})[String(this.get('size'))];
    const photos = new Set(lay.pages.flatMap((p) => p.cells.map((c) => c.photo).filter((x) => x !== null)));
    setText(this.status, `${n - 1} ${n - 1 === 1 ? 'page' : 'pages'} · ${photos.size} photos · ${sz?.name ?? ''}`);
  }

  private paintSelection(): void {
    for (const v of this.views) {
      setClass(v.root, 'is-selected', v.root.isConnected && v.index === this.selected);
      for (const c of Array.from(v.root.querySelectorAll<HTMLElement>('.fl-pcell'))) setClass(c, 'is-cell-on', v.index === this.selected && Number(c.dataset.key) === this.selectedCell && !c.classList.contains('is-empty'));
    }
  }

  private syncPagePanel(): void {
    const page = this.pageRef(this.selected);
    setText(this.pageInfo, this.selected === 0 ? 'Cover. Pick a template, then drag photos onto its cells.' : `Page ${this.selected}. Pick a template, then drag photos onto its cells.`);
    const defs = this.tdefs();
    const keys = Object.keys(defs).filter((k) => (this.selected === 0 ? ['cover', 'full', 'single'].includes(k) : k !== 'cover'));
    patchList(this.templatesBox, keys.map((k) => ({ k, d: defs[k] })), {
      key: (x) => x.k,
      create: ({ k, d }) => el(`<button class="fl-tpl" type="button" data-tpl="${k}" title="${escapeHtml(d.name)}"><span class="fl-tpl-page">${d.cells.map((c) => `<i style="left:${c[0] * 100}%;top:${c[1] * 100}%;width:${c[2] * 100}%;height:${c[3] * 100}%"></i>`).join('')}${d.texts.map((c) => `<b style="left:${c[0] * 100}%;top:${c[1] * 100}%;width:${c[2] * 100}%;height:${c[3] * 100}%"></b>`).join('')}</span></button>`),
      update: () => undefined,
    });
    for (const n of Array.from(this.templatesBox.children) as HTMLElement[]) setClass(n, 'is-on', page?.template === n.dataset.key);
    const frames = defs[page?.template ?? '']?.texts ?? [];
    const key = `${this.selected}|${page?.template}`;
    if (this.textBox.dataset.key !== key) {
      this.textBox.dataset.key = key;
      const styleOpts = STYLE_NAMES.map(([v, l]) => `<option value="${v}">${l}</option>`).join('');
      this.textBox.innerHTML = frames.length ? frames.map((_, i) => `<div class="fl-form-row is-wide"><span class="fl-form-label">${this.selected === 0 ? (i === 0 ? 'Title' : 'Subtitle') : `Text ${i + 1}`}</span><div class="fl-form-ctl"><input class="cv-input" type="text" data-t="${i}"></div></div>
<div class="fl-row fl-book-tstyle"><select class="cv-select" data-ts="${i}" data-k="style" aria-label="Text style">${styleOpts}</select><select class="cv-select" data-ts="${i}" data-k="align" aria-label="Alignment"><option value="">Align: Style</option><option value="left">Left</option><option value="center">Center</option><option value="right">Right</option></select><input class="fl-color" type="color" data-ts="${i}" data-k="color" aria-label="Text color"></div>`).join('') : '<p class="cv-note">This template has no text. Pick one with a caption or a Text Page to add words.</p>';
    }
    for (const i of Array.from(this.textBox.querySelectorAll<HTMLInputElement>('[data-t]'))) setValue(i, page?.texts?.[Number(i.dataset.t)] ?? '');
    for (const s of Array.from(this.textBox.querySelectorAll<HTMLInputElement | HTMLSelectElement>('[data-ts]'))) {
      const st = page?.styles?.[Number(s.dataset.ts)] ?? null;
      const k = s.dataset.k as keyof TextStyle;
      setValue(s, String(st?.[k] ?? (k === 'color' ? String(this.get('textColor') ?? '#222222') : '')));
    }
    const lay = this.lay?.pages[this.selected];
    const hasPhoto = this.selectedCell >= 0 && lay?.cells[this.selectedCell]?.photo != null;
    setHidden(this.cellBox, !hasPhoto);
    if (hasPhoto) setValue(q<HTMLInputElement>(this.cellBox, '[data-cz]'), String(Math.round(this.crop(this.selected, this.selectedCell).z * 100)));
  }

  private async exportBook(): Promise<void> {
    if (!this.pages().length) { toast('Lay out the book first'); return; }
    const fmt = String(this.get('job.output') || 'pdf');
    const name = String((this.get('cover.texts') as string[] | undefined)?.[0] || 'Book');
    await runOutput(this.ctx, 'book.export', { settings: this.settings, format: fmt, name }, (r) => fmt === 'pdf' ? `Exported ${String(r.pages ?? '')} pages to PDF` : `Exported ${(r.paths as string[]).length} page JPEGs`);
  }
}

function sourceTitle(): string {
  const label = library.source.label ?? '';
  return label && library.source.kind !== 'all' ? label : 'Untitled';
}

registerModule(new BookModule());
