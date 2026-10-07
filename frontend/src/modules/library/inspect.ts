import type { Ctx } from '../../app';
import { catalog, type KeywordRow } from '../../state/catalog';
import { library } from '../../state/library';
import { el, escapeHtml, q, setClass, setHtml, setText, setValue } from '../../ui/dom';
import { Histogram } from '../../ui/histogram';
import { icon } from '../../ui/icons';
import { Panel } from '../../ui/panel';
import { thumbUrl } from '../../ui/thumbs';
import { toast } from '../../ui/toast';
import { Tree, type TreeNode } from '../../ui/tree';

export interface PhotoDetail {
  id: number;
  path: string;
  folderPath: string;
  fileName: string;
  captureTime: string | null;
  fileSize: number | null;
  camera: string | null;
  lens: string | null;
  focal: number | null;
  aperture: number | null;
  shutter: number | null;
  iso: number | null;
  bias: number | null;
  flash: number | null;
  gpsLat: number | null;
  gpsLon: number | null;
  meta: Record<string, string>;
  keywords: string[];
  w: number;
  h: number;
  r: number;
  l: string;
  copyName: string | null;
  kind: string;
  fmt: string;
  develop: Record<string, unknown>;
}

export function shutterText(s: number | null): string {
  if (!s) return '';
  if (s >= 1) return `${s.toFixed(s >= 10 ? 0 : 1)} sec`;
  return `1/${Math.round(1 / s)} sec`;
}

export function exposureLine(d: PhotoDetail | null): string {
  if (!d) return '';
  return [d.iso ? `ISO ${d.iso}` : '', d.focal ? `${Math.round(d.focal)} mm` : '', d.aperture ? `f/${d.aperture.toFixed(1)}` : '', shutterText(d.shutter)].filter(Boolean).join('   ');
}

export class DetailCache {
  private readonly map = new Map<number, { rev: number; d: PhotoDetail }>();
  async get(ctx: Ctx, id: number): Promise<PhotoDetail> {
    const hit = this.map.get(id);
    if (hit && hit.rev === library.revision) return hit.d;
    const d = await ctx.api.cmd<PhotoDetail>('photo.get', { id });
    this.map.set(id, { rev: library.revision, d });
    if (this.map.size > 200) this.map.delete(this.map.keys().next().value as number);
    return d;
  }
}

export const details = new DetailCache();

const META_FIELDS: Array<[string, string]> = [
  ['title', 'Title'], ['caption', 'Caption'], ['headline', 'Headline'], ['creator', 'Creator'], ['creatorJob', 'Job Title'], ['copyright', 'Copyright'],
  ['copyrightStatus', 'Copyright Status'], ['rightsUrl', 'Rights URL'], ['location', 'Sublocation'], ['city', 'City'], ['state', 'State / Province'],
  ['country', 'Country'], ['countryCode', 'ISO Country Code'], ['event', 'Event'], ['instructions', 'Instructions'], ['credit', 'Credit Line'], ['source', 'Source'],
];

export class InspectPanels {
  private readonly hist: Histogram;
  private readonly histInfo: HTMLElement;
  private readonly meta: HTMLElement;
  private readonly kwText: HTMLTextAreaElement;
  private readonly kwSuggest: HTMLElement;
  private readonly kwTree: Tree;
  private readonly kwSearch: HTMLInputElement;
  private detail: PhotoDetail | null = null;
  private seq = 0;
  private timer = 0;

  constructor(private readonly ctx: Ctx, host: HTMLElement) {
    const pHist = new Panel('lib.histogram', 'Histogram');
    this.hist = new Histogram();
    this.histInfo = el('<div class="fl-hist-info"></div>');
    pHist.body.append(this.hist.root, this.histInfo);

    const pQuick = new Panel('lib.quick', 'Quick Develop', { open: false });
    pQuick.body.appendChild(this.quickDevelop());

    const pKw = new Panel('lib.keywording', 'Keywording');
    this.kwText = el<HTMLTextAreaElement>('<textarea class="cv-input fl-kw-text" rows="3" spellcheck="false" placeholder="Click here to add keywords"></textarea>');
    const kwAdd = el<HTMLInputElement>('<input class="cv-input fl-kw-add" type="text" spellcheck="false" placeholder="Enter keywords, comma separated">');
    this.kwSuggest = el('<div class="fl-kw-chips"></div>');
    pKw.body.append(this.kwText, kwAdd, el('<div class="fl-sub">Keyword Suggestions</div>'), this.kwSuggest);
    this.kwText.addEventListener('change', () => void this.setKeywords());
    kwAdd.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      const kws = kwAdd.value.split(',').map((s) => s.trim()).filter(Boolean);
      kwAdd.value = '';
      if (kws.length) void this.run('photo.addKeywords', { keywords: kws });
    });
    this.kwSuggest.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-kw]');
      if (b) void this.run('photo.addKeywords', { keywords: [b.dataset.kw] });
    });

    const pList = new Panel('lib.keywordList', 'Keyword List');
    this.kwSearch = el<HTMLInputElement>('<input class="cv-input fl-kw-search" type="search" placeholder="Filter Keywords" spellcheck="false">');
    this.kwTree = new Tree({
      id: 'keywords', empty: 'Keywords you add appear here',
      onPick: (n, e) => {
        const k = n.data as KeywordRow;
        if ((e.target as HTMLElement).closest('.fl-tree-icon')) { void this.toggleKeyword(k); return; }
        library.setSource({ kind: 'keyword', id: k.id, label: k.name });
      },
      canDrop: () => true,
      onDrop: (n, ids) => void ctx.api.cmd('photo.addKeywords', { ids, keywords: [catalog.keywordPath((n.data as KeywordRow).id)] }).catch((e) => ctx.fail(e)),
    });
    this.kwSearch.addEventListener('input', () => this.renderKeywords());
    pList.body.append(this.kwSearch, this.kwTree.root);

    const pMeta = new Panel('lib.metadata', 'Metadata');
    this.meta = el('<div class="fl-meta"></div>');
    pMeta.body.appendChild(this.meta);
    this.buildMeta();

    host.append(pHist.root, pQuick.root, pKw.root, pList.root, pMeta.root);
    library.listen('selection', () => this.load());
    library.listen('photos', (ids) => { if (library.active !== null && ids.includes(library.active)) this.load(); });
    catalog.listen(() => this.renderKeywords());
  }

  private async run(cmd: string, params: Record<string, unknown>): Promise<void> {
    const ids = library.targets();
    if (!ids.length) return;
    try { await this.ctx.api.cmd(cmd, { ids, ...params }); } catch (err) { this.ctx.fail(err); }
  }

  private load(): void {
    window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => void this.fetch(), 60);
  }

  private async fetch(): Promise<void> {
    const id = library.active;
    const seq = ++this.seq;
    if (id === null) { this.detail = null; this.paint(); return; }
    const p = library.photo(id);
    if (p) void this.hist.fromUrl(thumbUrl(p));
    try {
      const d = await details.get(this.ctx, id);
      if (seq !== this.seq) return;
      this.detail = d;
      this.paint();
      const s = await this.ctx.api.cmd<{ keywords: string[] }>('keyword.suggest', { ids: [id] });
      if (seq === this.seq) setHtml(this.kwSuggest, s.keywords.map((k) => `<button class="fl-chip" type="button" data-kw="${escapeHtml(k)}">${escapeHtml(k.split('|').pop() ?? k)}</button>`).join('') || '<span class="fl-muted">No suggestions yet</span>', s.keywords.join(','));
    } catch { return; }
  }

  private paint(): void {
    const d = this.detail;
    setText(this.histInfo, exposureLine(d));
    const kwValue = d ? d.keywords.map((k) => k.split('|').pop() ?? k).join(', ') : '';
    if (this.kwText.value !== kwValue && document.activeElement !== this.kwText) this.kwText.value = kwValue;
    this.renderKeywords();
    for (const row of Array.from(this.meta.querySelectorAll<HTMLElement>('[data-field]'))) {
      const f = row.dataset.field as string;
      const input = row.querySelector<HTMLInputElement>('input');
      const value = this.metaValue(d, f);
      if (input) setValue(input, value);
      else setText(q(row, '.fl-meta-val'), value);
    }
    const n = library.selected().length;
    setText(q(this.meta, '.fl-meta-note'), n > 1 ? `${n} photos selected · edits apply to all` : '');
  }

  private metaValue(d: PhotoDetail | null, f: string): string {
    if (!d) return '';
    switch (f) {
      case 'fileName': return d.fileName;
      case 'copyName': return d.copyName ?? '';
      case 'folder': return d.folderPath;
      case 'dims': return `${d.w} x ${d.h}`;
      case 'captureTime': return d.captureTime ? d.captureTime.replace('T', ' ').slice(0, 19) : '';
      case 'camera': return d.camera ?? '';
      case 'lens': return d.lens ?? '';
      case 'exposure': return [shutterText(d.shutter), d.aperture ? `at f/${d.aperture.toFixed(1)}` : ''].filter(Boolean).join(' ');
      case 'focal': return d.focal ? `${Math.round(d.focal)} mm` : '';
      case 'iso': return d.iso ? `ISO ${d.iso}` : '';
      case 'bias': return d.bias !== null && d.bias !== undefined ? `${d.bias > 0 ? '+' : ''}${d.bias.toFixed(1)} EV` : '';
      case 'flash': return d.flash === null || d.flash === undefined ? '' : d.flash & 1 ? 'Fired' : 'Did not fire';
      case 'gps': return d.gpsLat !== null && d.gpsLon !== null ? `${d.gpsLat.toFixed(5)}, ${d.gpsLon.toFixed(5)}` : '';
      case 'size': return d.fileSize ? `${(d.fileSize / 1048576).toFixed(1)} MB` : '';
      default: return d.meta?.[f] ?? '';
    }
  }

  private buildMeta(): void {
    const ro = (f: string, label: string) => `<div class="fl-meta-row" data-field="${f}"><span class="fl-meta-key">${label}</span><span class="fl-meta-val"></span></div>`;
    const rw = (f: string, label: string) => `<label class="fl-meta-row" data-field="${f}"><span class="fl-meta-key">${label}</span><input class="fl-meta-input" type="text" spellcheck="false"></label>`;
    const html = [
      '<div class="fl-meta-note"></div>',
      ro('fileName', 'File Name'), ro('copyName', 'Copy Name'), ro('folder', 'Folder'), ro('size', 'File Size'), ro('dims', 'Dimensions'),
      ...META_FIELDS.slice(0, 7).map(([f, l]) => rw(f, l)),
      '<div class="fl-sub">Camera</div>',
      ro('captureTime', 'Capture Time'), ro('camera', 'Camera'), ro('lens', 'Lens'), ro('exposure', 'Exposure'), ro('focal', 'Focal Length'), ro('iso', 'ISO Speed'),
      ro('bias', 'Exposure Bias'), ro('flash', 'Flash'), ro('gps', 'GPS'),
      '<div class="fl-sub">Location and IPTC</div>',
      ...META_FIELDS.slice(7).map(([f, l]) => rw(f, l)),
    ].join('');
    this.meta.innerHTML = html;
    this.meta.addEventListener('change', (e) => {
      const input = e.target as HTMLInputElement;
      const row = input.closest<HTMLElement>('[data-field]');
      if (!row) return;
      void this.run('photo.setMeta', { fields: { [row.dataset.field as string]: input.value } });
    });
    this.meta.addEventListener('keydown', (e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); });
  }

  private async setKeywords(): Promise<void> {
    const kws = this.kwText.value.split(',').map((s) => s.trim()).filter(Boolean);
    const keep = (this.detail?.keywords ?? []).filter((k) => kws.includes(k.split('|').pop() ?? k));
    const fresh = kws.filter((k) => !keep.some((x) => (x.split('|').pop() ?? x) === k));
    await this.run('photo.setKeywords', { keywords: [...keep, ...fresh] });
  }

  private async toggleKeyword(k: KeywordRow): Promise<void> {
    const path = catalog.keywordPath(k.id);
    const has = (this.detail?.keywords ?? []).includes(path);
    await this.run(has ? 'photo.removeKeywords' : 'photo.addKeywords', { keywords: [path] });
    toast(`${has ? 'Removed' : 'Added'} ${k.name}`);
  }

  private renderKeywords(): void {
    const rows = catalog.tree.keywords;
    const has = new Set(this.detail?.keywords ?? []);
    const filter = this.kwSearch.value.trim().toLowerCase();
    const kids = new Map<number | null, KeywordRow[]>();
    for (const r of rows) { const p = r.parent; if (!kids.has(p)) kids.set(p, []); kids.get(p)?.push(r); }
    const out: TreeNode[] = [];
    const walk = (parent: number | null, depth: number, path: string) => {
      for (const k of kids.get(parent) ?? []) {
        const full = path ? `${path}|${k.name}` : k.name;
        const match = !filter || full.toLowerCase().includes(filter);
        if (match) out.push({ key: `keyword:${k.id}`, label: k.name, icon: has.has(full) ? 'check' : k.person ? 'people' : 'tag', count: k.count, depth: filter ? 0 : depth, hasKids: !filter && (kids.get(k.id) ?? []).length > 0, data: k });
        walk(k.id, depth + 1, full);
      }
    };
    walk(null, 0, '');
    this.kwTree.set(out);
    this.kwTree.setActive(library.source.kind === 'keyword' ? `keyword:${library.source.id}` : '');
  }

  private quickDevelop(): HTMLElement {
    const root = el('<div class="fl-qd"></div>');
    const steps: Array<[string, string, number, number]> = [
      ['Exposure', 'light.exposure', 1 / 3, 1], ['Contrast', 'light.contrast', 5, 20], ['Highlights', 'light.highlights', 5, 20], ['Shadows', 'light.shadows', 5, 20],
      ['Whites', 'light.whites', 5, 20], ['Blacks', 'light.blacks', 5, 20], ['Clarity', 'effects.clarity', 5, 20], ['Vibrance', 'color.vibrance', 5, 20],
      ['Temperature', 'wb.temp', 100, 500], ['Tint', 'wb.tint', 2, 10],
    ];
    const presets = el<HTMLSelectElement>('<select class="cv-select fl-qd-preset"><option value="">Saved Preset...</option></select>');
    const wb = el<HTMLSelectElement>(`<select class="cv-select"><option value="">White Balance...</option>${['asShot', 'auto', 'daylight', 'cloudy', 'shade', 'tungsten', 'fluorescent', 'flash'].map((m) => `<option value="${m}">${m === 'asShot' ? 'As Shot' : m.charAt(0).toUpperCase() + m.slice(1)}</option>`).join('')}</select>`);
    presets.addEventListener('focus', () => void this.ctx.api.cmd<{ presets: Array<{ id: string; name: string; group: string }> }>('preset.list').then((r) => {
      if (presets.options.length > 1) return;
      for (const p of r.presets) presets.add(new Option(`${p.group} / ${p.name}`, p.id));
    }), { once: true });
    presets.addEventListener('change', () => { const v = presets.value; presets.value = ''; if (v) void this.run('preset.apply', { preset: v }); });
    wb.addEventListener('change', () => { const v = wb.value; wb.value = ''; if (v) void this.run('develop.whiteBalancePreset', { mode: v }); });
    root.append(presets, wb);
    for (const [label, cid, small, big] of steps) {
      const row = el(`<div class="fl-qd-row"><span class="fl-qd-label">${label}</span><span class="fl-qd-btns"><button type="button" data-d="${-big}">${icon('chevronLeft', 10)}${icon('chevronLeft', 10)}</button><button type="button" data-d="${-small}">${icon('chevronLeft', 10)}</button><button type="button" data-d="${small}">${icon('chevronRight', 10)}</button><button type="button" data-d="${big}">${icon('chevronRight', 10)}${icon('chevronRight', 10)}</button></span></div>`);
      row.addEventListener('click', (e) => {
        const b = (e.target as HTMLElement).closest<HTMLElement>('[data-d]');
        if (b) void this.run('develop.set', { values: { [cid]: Number(b.dataset.d) }, delta: true, label: `Quick Develop ${label}` });
      });
      root.appendChild(row);
    }
    const actions = el(`<div class="fl-qd-actions"><button class="cv-btn" type="button" data-a="auto">Auto Settings</button><button class="cv-btn" type="button" data-a="reset">Reset All</button></div>`);
    actions.addEventListener('click', (e) => {
      const a = (e.target as HTMLElement).closest<HTMLElement>('[data-a]')?.dataset.a;
      if (a === 'auto') void this.run('develop.auto', {});
      if (a === 'reset') void this.run('develop.reset', {});
    });
    root.appendChild(actions);
    setClass(root, 'is-ready', true);
    return root;
  }
}
