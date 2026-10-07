import { el, setClass, setDisabled, setHidden, setText, setValue } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { Panel } from '../../ui/panel';
import { toast } from '../../ui/toast';
import { registerModule } from '../registry';
import { openOutput, runOutput } from '../shared/tasks';
import { OutputModule } from './base';
import { PageView, type Layout } from './page';

interface Paper { name: string; w: number; h: number }

class PrintModule extends OutputModule {
  readonly id = 'print';
  readonly label = 'Print';
  readonly icon = 'modPrint';
  readonly key = 'Alt+Mod+6';
  readonly order = 6;
  protected readonly optionsCmd = 'print.options';
  protected readonly kind = 'print';
  private lay: Layout | null = null;
  private page = 0;
  private selectedCell = 0;
  private readonly view = new PageView();
  private readonly frame = el('<div class="fl-out-frame"></div>');
  private readonly pageLabel = el('<span class="fl-tb-label fl-out-pages"></span>');
  private readonly prev = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" aria-label="Previous Page">${icon('chevronLeft', 16)}</button>`);
  private readonly next = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" aria-label="Next Page">${icon('chevronRight', 16)}</button>`);
  private readonly cellsBox = el('<div class="fl-pkg"></div>');
  private printers: Array<{ name: string; default: boolean }> = [];
  private profiles: Array<{ name: string; path: string; space: string }> = [];
  private seq = 0;

  protected buildToolbar(bar: HTMLElement): void {
    this.prev.addEventListener('click', () => this.go(this.page - 1));
    this.next.addEventListener('click', () => this.go(this.page + 1));
    bar.append(this.prev, this.pageLabel, this.next);
  }

  protected buildStage(stage: HTMLElement): void {
    const root = el('<div class="fl-out-stage"></div>');
    this.frame.appendChild(this.view.root);
    root.appendChild(this.frame);
    stage.appendChild(root);
    new ResizeObserver(() => this.paint()).observe(root);
    this.view.onCell = (i) => { if (this.get('style') === 'custom') { this.selectedCell = i; this.syncCells(); } };
  }

  private paper(): Array<[string, string]> {
    const p = ((this.options?.paper as Record<string, Paper>) ?? {});
    return Object.entries(p).map(([k, v]) => [k, v.name] as [string, string]);
  }

  protected buildPanels(right: HTMLElement): void {
    const style = () => String(this.get('style'));
    this.formPanel(right, 'style', 'Layout Style', [
      { path: 'style', label: 'Style', kind: 'seg', options: [['grid', 'Grid'], ['package', 'Package'], ['custom', 'Custom']] },
    ]);
    this.formPanel(right, 'image', 'Image Settings', [
      { path: 'fill', label: 'Zoom to fill', kind: 'check' },
      { path: 'rotate', label: 'Rotate to fit', kind: 'check' },
      { path: 'repeat', label: 'One photo per page', kind: 'check', show: () => style() === 'grid' },
      { path: 'stroke', label: 'Stroke border', kind: 'range', min: 0, max: 20, step: 0.5, unit: ' pt' },
      { path: 'strokeColor', label: 'Stroke color', kind: 'color', show: () => Number(this.get('stroke')) > 0 },
    ]);
    this.formPanel(right, 'layout', 'Layout', [
      { path: 'paper', label: 'Paper', kind: 'select', options: () => this.paper() },
      { path: 'orientation', label: 'Orientation', kind: 'seg', options: [['portrait', 'Portrait'], ['landscape', 'Landscape']] },
      { path: 'margins.0', label: 'Left margin', kind: 'range', min: 0, max: 3, step: 0.05, unit: ' in' },
      { path: 'margins.1', label: 'Right margin', kind: 'range', min: 0, max: 3, step: 0.05, unit: ' in' },
      { path: 'margins.2', label: 'Top margin', kind: 'range', min: 0, max: 3, step: 0.05, unit: ' in' },
      { path: 'margins.3', label: 'Bottom margin', kind: 'range', min: 0, max: 3, step: 0.05, unit: ' in' },
      { path: 'rows', label: 'Rows', kind: 'range', min: 1, max: 15, show: () => style() === 'grid' },
      { path: 'cols', label: 'Columns', kind: 'range', min: 1, max: 15, show: () => style() === 'grid' },
      { path: 'gapY', label: 'Vertical gap', kind: 'range', min: 0, max: 2, step: 0.05, unit: ' in', show: () => style() === 'grid' },
      { path: 'gapX', label: 'Horizontal gap', kind: 'range', min: 0, max: 2, step: 0.05, unit: ' in', show: () => style() === 'grid' },
    ]);
    const pc = new Panel('print.cells', 'Cells');
    pc.body.appendChild(this.cellsBox);
    right.appendChild(pc.root);
    this.cellsBox.addEventListener('click', (e) => this.onCellsClick(e));
    this.cellsBox.addEventListener('change', (e) => this.onCellsChange(e));
    this.formPanel(right, 'page', 'Page', [
      { path: 'background', label: 'Background', kind: 'color' },
      { path: 'identity.on', label: 'Identity plate', kind: 'check' },
      { path: 'identity.text', label: 'Text', kind: 'text', placeholder: 'Your name or studio', show: () => !!this.get('identity.on') },
      { path: 'identity.size', label: 'Size', kind: 'range', min: 6, max: 72, unit: ' pt', show: () => !!this.get('identity.on') },
      { path: 'identity.y', label: 'Position', kind: 'range', min: 0.01, max: 0.99, step: 0.005, show: () => !!this.get('identity.on') },
      { path: 'identity.color', label: 'Color', kind: 'color', show: () => !!this.get('identity.on') },
      { path: 'pageNumbers', label: 'Page numbers', kind: 'check' },
      { path: 'pageInfo', label: 'Page info', kind: 'check' },
      { path: 'cropMarks', label: 'Crop marks', kind: 'check' },
      { path: 'caption.on', label: 'Photo info', kind: 'check' },
      { path: 'caption.field', label: 'Field', kind: 'select', options: [['title', 'Title'], ['caption', 'Caption'], ['titleCaption', 'Title and Caption'], ['fileName', 'Filename'], ['date', 'Date'], ['exposure', 'Exposure'], ['custom', 'Custom Text']], show: () => !!this.get('caption.on') },
      { path: 'caption.custom', label: 'Custom', kind: 'text', placeholder: '{title} by {creator}', show: () => !!this.get('caption.on') && this.get('caption.field') === 'custom' },
      { path: 'caption.size', label: 'Font size', kind: 'range', min: 5, max: 24, unit: ' pt', show: () => !!this.get('caption.on') },
    ]);
    this.formPanel(right, 'job', 'Print Job', [
      { path: 'job.output', label: 'Print to', kind: 'seg', options: [['printer', 'Printer'], ['pdf', 'PDF'], ['jpeg', 'JPEG'], ['tiff', 'TIFF']] },
      { path: 'job.bits', label: 'Bit depth', kind: 'seg', options: [['8', '8 bit'], ['16', '16 bit']], show: () => this.get('job.output') === 'tiff' },
      { path: 'job.printer', label: 'Printer', kind: 'select', options: () => [['', 'System default'], ...this.printers.map((p) => [p.name, p.default ? `${p.name} (default)` : p.name] as [string, string])], show: () => this.get('job.output') === 'printer' },
      { path: 'job.copies', label: 'Copies', kind: 'number', min: 1, max: 99, show: () => this.get('job.output') === 'printer' },
      { path: 'job.ppi', label: 'Resolution', kind: 'number', min: 72, max: 720, step: 10, unit: 'ppi' },
      { path: 'job.sharpen.on', label: 'Print sharpening', kind: 'check' },
      { path: 'job.sharpen.amount', label: 'Amount', kind: 'select', options: [['low', 'Low'], ['standard', 'Standard'], ['high', 'High']], show: () => !!this.get('job.sharpen.on') },
      { path: 'job.sharpen.for', label: 'Media type', kind: 'select', options: [['matte', 'Matte'], ['glossy', 'Glossy']], show: () => !!this.get('job.sharpen.on') },
      { path: 'job.quality', label: 'JPEG quality', kind: 'range', min: 50, max: 100, show: () => this.get('job.output') === 'jpeg' || this.get('job.output') === 'pdf' },
    ]);
    this.formPanel(right, 'color', 'Color Management', [
      { path: 'job.profile', label: 'Profile', kind: 'select', options: () => [['', 'Managed by Printer'], ...this.profiles.map((p) => [p.path, p.name] as [string, string])] },
      { path: 'job.space', label: 'Color space', kind: 'select', options: [['srgb', 'sRGB'], ['adobergb', 'Adobe RGB (1998)'], ['p3', 'Display P3']], show: () => !this.get('job.profile') },
      { path: 'job.intent', label: 'Intent', kind: 'seg', options: [['perceptual', 'Perceptual'], ['relative', 'Relative']], show: () => !!this.get('job.profile') },
      { path: '', label: 'formlit converts to the printer profile. Turn colour management off in the printer dialog so the colours are not converted twice.', kind: 'note', show: () => !!this.get('job.profile') && this.get('job.output') === 'printer' },
      { path: 'job.adjust.on', label: 'Print Adjustment', kind: 'check' },
      { path: 'job.adjust.brightness', label: 'Brightness', kind: 'range', min: -100, max: 100, show: () => !!this.get('job.adjust.on') },
      { path: 'job.adjust.contrast', label: 'Contrast', kind: 'range', min: -100, max: 100, show: () => !!this.get('job.adjust.on') },
    ]);
  }

  protected buildFoots(_left: HTMLElement, right: HTMLElement): void {
    const row = el('<div class="fl-foot-row"><button class="cv-btn" type="button" data-act="one">Print One</button><button class="cv-btn cv-btn-primary" type="button" data-act="print">Print...</button></div>');
    row.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-act]');
      if (b) void this.print(b.dataset.act === 'one');
    });
    right.appendChild(row);
  }

  protected onOptions(): void {
    void this.ctx.api.cmd<{ printers: Array<{ name: string; default: boolean }> }>('print.printers').then((r) => { this.printers = r.printers; this.syncForms(); }, () => undefined);
    void this.ctx.api.cmd<{ profiles: Array<{ name: string; path: string; space: string }> }>('develop.proofProfiles').then((r) => { this.profiles = r.profiles.filter((p) => p.space === 'RGB'); this.syncForms(); }, () => undefined);
  }

  protected async refresh(): Promise<void> {
    const seq = ++this.seq;
    const lay = await this.ctx.api.cmd<Layout>('print.layout', { settings: this.settings, ids: this.ids() });
    if (seq !== this.seq) return;
    this.lay = lay;
    this.page = Math.min(this.page, lay.pages.length - 1);
    this.paint();
    this.syncCells();
  }

  private go(p: number): void {
    if (!this.lay) return;
    this.page = Math.max(0, Math.min(this.lay.pages.length - 1, p));
    this.paint();
  }

  private paint(): void {
    const lay = this.lay;
    if (!lay) return;
    const stage = this.frame.parentElement as HTMLElement;
    const W = stage.clientWidth - 64, H = stage.clientHeight - 64;
    if (W <= 0 || H <= 0) return;
    const scale = Math.min(W / lay.page.w, H / lay.page.h);
    const page = lay.pages[this.page] ?? lay.pages[0];
    this.view.render(lay, page, lay.page.w * scale, { background: String(this.get('background') ?? '#fff'), stroke: Number(this.get('stroke') ?? 0), strokeColor: String(this.get('strokeColor') ?? '#000') });
    setClass(this.view.root, 'is-marks', !!this.get('cropMarks'));
    const n = lay.pages.length;
    setText(this.pageLabel, `Page ${this.page + 1} of ${n}`);
    setDisabled(this.prev, this.page <= 0);
    setDisabled(this.next, this.page >= n - 1);
    const ids = this.ids();
    const paper = ((this.options?.paper as Record<string, Paper>) ?? {})[String(this.get('paper'))];
    setText(this.status, `${ids.length} ${ids.length === 1 ? 'photo' : 'photos'} · ${paper ? paper.name : ''} · ${lay.page.w.toFixed(2)} x ${lay.page.h.toFixed(2)} in`);
  }

  private syncCells(): void {
    const style = String(this.get('style'));
    setHidden(this.cellsBox.closest('.fl-panel') as HTMLElement, style === 'grid');
    if (style === 'package') {
      const pk = (this.get('package') as Array<{ size: string }>) ?? [];
      const sizes = Object.keys((this.options?.packages as Record<string, number[]>) ?? {});
      const key = `pkg|${pk.map((c) => c.size).join(',')}`;
      if (this.cellsBox.dataset.key === key) return;
      this.cellsBox.dataset.key = key;
      this.cellsBox.innerHTML = `<div class="fl-pkg-add">${sizes.map((s) => `<button class="cv-btn fl-btn-sm" type="button" data-add="${s}">${s === 'wallet' ? 'Wallet' : s.replace('x', ' x ')}</button>`).join('')}</div>
<div class="fl-list">${pk.map((c, i) => `<div class="fl-list-row"><span>${c.size === 'wallet' ? 'Wallet 2.5 x 3.5 in' : `${c.size.replace('x', ' x ')} in`}</span><button class="cv-icon-btn" type="button" data-del="${i}" aria-label="Remove">${icon('close', 12)}</button></div>`).join('')}</div>
<p class="cv-note">${this.lay?.pages[0]?.cells.length ?? 0} of ${pk.length} cells fit on the page.</p>`;
      return;
    }
    if (style === 'custom') {
      const cells = (this.get('cells') as Array<{ x: number; y: number; w: number; h: number }>) ?? [];
      this.selectedCell = Math.min(this.selectedCell, Math.max(0, cells.length - 1));
      const c = cells[this.selectedCell];
      const key = `cus|${this.selectedCell}|${cells.length}`;
      if (this.cellsBox.dataset.key === key) {
        for (const i of Array.from(this.cellsBox.querySelectorAll<HTMLInputElement>('input[data-f]'))) if (c) setValue(i, (c[i.dataset.f as 'x' | 'y' | 'w' | 'h'] ?? 0).toFixed(2));
        return;
      }
      this.cellsBox.dataset.key = key;
      const num = (f: string, v: number) => `<label class="fl-form-row"><span class="fl-form-label">${f.toUpperCase()}</span><div class="fl-form-ctl"><input class="cv-input" type="number" step="0.05" data-f="${f}" value="${v.toFixed(2)}"><span class="fl-form-unit">in</span></div></label>`;
      this.cellsBox.innerHTML = `<div class="fl-pkg-add"><button class="cv-btn fl-btn-sm" type="button" data-addcell>Add Cell</button><button class="cv-btn fl-btn-sm" type="button" data-delcell${cells.length ? '' : ' disabled'}>Delete Cell</button></div>
<p class="cv-note">Cell ${cells.length ? this.selectedCell + 1 : 0} of ${cells.length}. Click a cell on the page to select it.</p>${c ? num('x', c.x) + num('y', c.y) + num('w', c.w) + num('h', c.h) : ''}`;
    }
  }

  private onCellsClick(e: MouseEvent): void {
    const t = e.target as HTMLElement;
    const add = t.closest<HTMLElement>('[data-add]');
    const del = t.closest<HTMLElement>('[data-del]');
    const pk = [...((this.get('package') as Array<{ size: string }>) ?? [])];
    if (add) { pk.push({ size: add.dataset.add as string }); this.set('package', pk); return; }
    if (del) { pk.splice(Number(del.dataset.del), 1); this.set('package', pk); return; }
    const cells = [...((this.get('cells') as Array<{ x: number; y: number; w: number; h: number }>) ?? [])];
    if (t.closest('[data-addcell]')) { cells.push({ x: 0.75, y: 0.75, w: 3, h: 2 }); this.selectedCell = cells.length - 1; this.set('cells', cells); }
    else if (t.closest('[data-delcell]')) { cells.splice(this.selectedCell, 1); this.set('cells', cells); }
  }

  private onCellsChange(e: Event): void {
    const i = (e.target as HTMLElement).closest<HTMLInputElement>('input[data-f]');
    if (!i) return;
    const cells = [...((this.get('cells') as Array<Record<string, number>>) ?? [])];
    const c = { ...cells[this.selectedCell] };
    c[i.dataset.f as string] = Math.max(i.dataset.f === 'w' || i.dataset.f === 'h' ? 0.25 : 0, Number(i.value) || 0);
    cells[this.selectedCell] = c;
    this.set('cells', cells);
  }

  private async print(one: boolean): Promise<void> {
    const ids = this.ids();
    if (!ids.length) { toast('Add photos to the filmstrip to print'); return; }
    let out = String(this.get('job.output') || 'pdf');
    if (out === 'printer' && !this.printers.length && !one) out = 'pdf';
    const label = out === 'printer' ? 'Sent to printer' : out === 'jpeg' ? 'Saved page JPEGs' : 'Saved the PDF';
    const r = await runOutput(this.ctx, 'print.run', { settings: this.settings, ids, output: one && out === 'jpeg' ? 'jpeg' : out, name: 'Print' }, () => label);
    if (r && out === 'pdf' && !this.printers.length && String(this.get('job.output')) === 'printer' && typeof r.path === 'string') openOutput(r.path);
  }
}

registerModule(new PrintModule());
