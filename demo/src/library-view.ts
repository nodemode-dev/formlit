import { el, q, setClass, setHidden, setText, setValue } from '../../frontend/src/ui/dom';
import { Filmstrip } from '../../frontend/src/ui/filmstrip';
import { ThumbGrid } from '../../frontend/src/ui/grid';
import { icon } from '../../frontend/src/ui/icons';
import { Panel } from '../../frontend/src/ui/panel';
import { Viewer } from '../../frontend/src/ui/viewer';
import { autoTone } from './auto';
import { SCENES } from './data/scenes';
import { clone } from './engine/settings';
import { PRESETS, presetDev } from './presets';
import { SOURCES, library, sourceKey } from './shims/library';
import { store, type Item } from './store';
import { copySettings, exportSettings, importSettings, openExport, openInfo, openSync, pasteSettings, resetSettings } from './actions';

const SORTS: Array<[string, string]> = [['importTime', 'Added Order'], ['captureTime', 'Capture Time'], ['fileName', 'File Name'], ['rating', 'Rating'], ['flag', 'Pick']];
const LABELS = ['red', 'yellow', 'green', 'blue', 'purple'];

export interface LibraryHooks { openDevelop(id: number): void; pickFiles(): void }

export class LibraryView {
  readonly grid: ThumbGrid;
  readonly loupe: Viewer;
  readonly filmstrip: Filmstrip;
  view: 'grid' | 'loupe' = 'grid';
  private readonly gridWrap: HTMLElement;
  private readonly loupeWrap: HTMLElement;
  private readonly bar: HTMLElement;
  private readonly empty: HTMLElement;
  private readonly metaBody: HTMLElement;
  private readonly sources: HTMLElement;
  private readonly count: HTMLElement;
  private readonly keywords: HTMLInputElement;
  private readonly presetSel: HTMLSelectElement;

  constructor(hosts: { left: HTMLElement; stage: HTMLElement; toolbar: HTMLElement; right: HTMLElement; strip: HTMLElement }, hook: LibraryHooks) {
    this.grid = new ThumbGrid({ axis: 'y', cls: 'fl-lg', names: true, onOpen: (id) => { library.setActive(id); this.setView('loupe'); } });
    this.grid.setSize(190);
    this.loupe = new Viewer('fl-loupe');
    this.loupe.onClick = (e) => this.loupe.toggleZoom(e);
    this.gridWrap = el('<div class="fl-lib-view fl-lib-grid"></div>');
    this.empty = el(`<div class="fl-empty"><div class="fl-empty-card"><span class="fl-empty-title">${icon('modLibrary', 20)} No photos here</span><span class="fl-empty-sub">Add a procedural sample from the left, or drop your own photos on this window.</span></div></div>`);
    this.gridWrap.append(this.grid.root, this.empty);
    this.loupeWrap = el('<div class="fl-lib-view fl-lib-loupe" hidden></div>');
    this.loupeWrap.appendChild(this.loupe.root);
    hosts.stage.append(this.gridWrap, this.loupeWrap);

    this.bar = el(`<div class="fl-tb is-grid">
<div class="fl-tb-group"><button class="cv-icon-btn" type="button" data-v="grid" title="Grid (G)" aria-label="Grid">${icon('viewGridLit', 16)}</button><button class="cv-icon-btn" type="button" data-v="loupe" title="Loupe (E)" aria-label="Loupe">${icon('viewLoupe', 16)}</button></div>
<span class="fl-tb-sep"></span>
<span class="fl-tb-label">Sort</span><select class="cv-select fl-tb-sort">${SORTS.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select>
<button class="cv-icon-btn fl-tb-dir" type="button" data-dir aria-label="Sort Direction">${icon('sortLit', 16)}</button>
<span class="fl-tb-sep"></span>
<input class="cv-input fl-tb-search" type="search" placeholder="Search name, keyword, camera" aria-label="Search">
<span class="fl-tb-stars">${[1, 2, 3, 4, 5].map((n) => `<button type="button" data-rate="${n}" aria-label="${n} stars">${icon('starFill', 13)}</button>`).join('')}</span>
<span class="fl-tb-labels">${LABELS.map((l) => `<button class="fl-swatch-btn" type="button" data-label="${l}" aria-label="${l}"></button>`).join('')}</span>
<span class="fl-tb-spacer"></span>
<span class="fl-tb-label fl-tb-gridonly">Size</span><input class="cv-range fl-tb-size fl-tb-gridonly" type="range" min="90" max="360" value="190" aria-label="Thumbnail size">
</div>`);
    hosts.toolbar.appendChild(this.bar);
    this.wireBar();

    this.filmstrip = new Filmstrip(hosts.strip);
    this.filmstrip.onOpen = (id) => { library.setActive(id); this.setView('loupe'); };

    const pSrc = new Panel('lib.sources', 'Catalog');
    this.sources = el('<div class="fl-list"></div>');
    for (const s of SOURCES) {
      const row = el(`<button class="fl-list-row" type="button"><span></span><em></em></button>`);
      row.dataset.key = sourceKey(s);
      setText(q(row, 'span'), s.label ?? s.kind);
      this.sources.appendChild(row);
    }
    this.sources.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-key]');
      const s = SOURCES.find((x) => sourceKey(x) === b?.dataset.key);
      if (s) library.setSource(s);
    });
    pSrc.body.appendChild(this.sources);

    const pAdd = new Panel('lib.samples', 'Add Photos');
    const addRow = el('<div class="fl-row"></div>');
    const pick = el<HTMLButtonElement>(`<button class="cv-btn cv-btn-primary fl-btn-sm" type="button">${icon('importLit', 13)} Open Your Photos</button>`);
    pick.addEventListener('click', () => hook.pickFiles());
    addRow.appendChild(pick);
    const sample = el('<div class="fl-list"></div>');
    SCENES.forEach((s, i) => {
      const row = el('<button class="fl-list-row" type="button"><span></span><em>sample</em></button>');
      setText(q(row, 'span'), s.name);
      row.addEventListener('click', () => { void store.addSample(i).then((it) => { library.setActive(it.id, false); }); });
      sample.appendChild(row);
    });
    const all = el<HTMLButtonElement>('<button class="cv-btn fl-btn-sm" type="button">Add All Samples</button>');
    all.addEventListener('click', () => { SCENES.forEach((_s, i) => { void store.addSample(i); }); });
    pAdd.body.append(addRow, el('<div class="fl-sub">Procedural samples</div>'), sample, el('<div class="fl-row"></div>'));
    pAdd.body.lastElementChild?.appendChild(all);
    this.count = el('<div class="fl-muted fl-privacy">Everything runs in this page. Photos never leave your computer.</div>');
    pAdd.body.appendChild(this.count);
    hosts.left.append(pSrc.root, pAdd.root);

    const pMeta = new Panel('lib.meta', 'Metadata');
    this.metaBody = el('<div class="fl-kv"></div>');
    this.keywords = el<HTMLInputElement>('<input class="cv-input" type="text" placeholder="Keywords, comma separated" aria-label="Keywords">');
    this.keywords.addEventListener('change', () => {
      const it = this.current();
      if (!it) return;
      it.keywords = this.keywords.value.split(',').map((s) => s.trim()).filter(Boolean);
      store.emit('item', it.id);
    });
    pMeta.body.append(this.metaBody, el('<div class="fl-sub">Keywords</div>'), this.keywords);

    const pQuick = new Panel('lib.quick', 'Quick Develop');
    this.presetSel = el<HTMLSelectElement>(`<select class="cv-select fl-grow"><option value="">Choose a preset</option>${PRESETS.map((p) => `<option value="${p.id}">${p.group}: ${p.name}</option>`).join('')}</select>`);
    this.presetSel.addEventListener('change', () => {
      const p = PRESETS.find((x) => x.id === this.presetSel.value);
      if (!p) return;
      for (const it of this.targets()) store.commit(it, presetDev(it.dev, p), `Preset: ${p.name}`);
      this.presetSel.value = '';
    });
    const presetRow = el('<div class="fl-row"><span class="fl-row-label">Preset</span></div>');
    presetRow.appendChild(this.presetSel);
    const quick = el(`<div class="fl-row fl-row-wrap">
<button class="cv-btn fl-btn-sm" type="button" data-q="auto">${icon('sparkle', 13)} Auto Tone</button>
<button class="cv-btn fl-btn-sm" type="button" data-q="reset">Reset</button>
<button class="cv-btn fl-btn-sm" type="button" data-q="copy">${icon('copyLit', 13)} Copy</button>
<button class="cv-btn fl-btn-sm" type="button" data-q="paste">${icon('pasteLit', 13)} Paste</button>
<button class="cv-btn fl-btn-sm" type="button" data-q="sync">${icon('syncLit', 13)} Sync</button>
<button class="cv-btn fl-btn-sm" type="button" data-q="save">${icon('save', 13)} Settings</button>
<button class="cv-btn fl-btn-sm" type="button" data-q="load">${icon('load', 13)} Load</button>
</div>`);
    quick.addEventListener('click', (e) => {
      const k = (e.target as HTMLElement).closest<HTMLElement>('[data-q]')?.dataset.q;
      if (k) this.quick(k);
    });
    pQuick.body.append(presetRow, quick);

    const pOut = new Panel('lib.output', 'Export');
    const outRow = el(`<div class="fl-row fl-row-wrap"><button class="cv-btn cv-btn-primary fl-btn-sm" type="button" data-o="export">${icon('exportLit', 13)} Export Selected</button><button class="cv-btn fl-btn-sm" type="button" data-o="info">${icon('info', 13)} Photo Info</button></div>`);
    outRow.addEventListener('click', (e) => {
      const k = (e.target as HTMLElement).closest<HTMLElement>('[data-o]')?.dataset.o;
      if (k === 'export') openExport(this.targets());
      else if (k === 'info') openInfo(this.current());
    });
    pOut.body.append(outRow, el('<p class="cv-note">JPEG, PNG or WebP at a size and quality you choose. Several photos can be bundled as one ZIP.</p>'));
    hosts.right.append(pMeta.root, pQuick.root, pOut.root);

    library.listen('list', () => this.sync());
    library.listen('selection', () => this.sync());
    library.listen('photos', () => this.sync());
    library.listen('render', (id, size) => { if (size === 'p' && this.view === 'loupe' && library.active === id) this.loupe.refresh(); });
    this.sync();
  }

  current(): Item | null {
    const id = library.active;
    return id === null ? null : store.items.get(id) ?? null;
  }

  targets(): Item[] {
    return library.selected().map((id) => store.items.get(id)).filter((x): x is Item => !!x);
  }

  quick(k: string): void {
    const t = this.targets();
    const it = this.current();
    if (k === 'auto') {
      for (const x of t) store.commit(x, { ...clone(x.dev), ...autoTone(x.src) }, 'Auto Tone');
    } else if (k === 'reset') for (const x of t) resetSettings(x);
    else if (k === 'copy') copySettings(it);
    else if (k === 'paste') pasteSettings(t);
    else if (k === 'sync') openSync(it, t);
    else if (k === 'save') exportSettings(it);
    else if (k === 'load') importSettings(t);
  }

  rate(n: number): void { for (const it of this.targets()) store.setMeta(it, { rating: it.rating === n ? 0 : n }); }
  flag(v: number): void { for (const it of this.targets()) store.setMeta(it, { flag: it.flag === v ? 0 : v }); }
  label(l: string): void { for (const it of this.targets()) store.setMeta(it, { label: it.label === l ? '' : l }); }

  private wireBar(): void {
    const sort = q<HTMLSelectElement>(this.bar, '.fl-tb-sort');
    sort.addEventListener('change', () => library.setSort({ by: sort.value }));
    q(this.bar, '[data-dir]').addEventListener('click', () => {
      library.setSort({ desc: !library.sort.desc });
      setClass(q(this.bar, '[data-dir]'), 'is-flipped', library.sort.desc);
    });
    const search = q<HTMLInputElement>(this.bar, '.fl-tb-search');
    search.addEventListener('input', () => library.setFilter({ text: search.value }));
    const size = q<HTMLInputElement>(this.bar, '.fl-tb-size');
    size.addEventListener('input', () => this.grid.setSize(Number(size.value)));
    this.bar.addEventListener('click', (e) => {
      const t = e.target as HTMLElement;
      const v = t.closest<HTMLElement>('[data-v]')?.dataset.v;
      if (v) { this.setView(v === 'loupe' ? 'loupe' : 'grid'); return; }
      const r = t.closest<HTMLElement>('[data-rate]')?.dataset.rate;
      if (r) { this.rate(Number(r)); return; }
      const l = t.closest<HTMLElement>('[data-label]')?.dataset.label;
      if (l) this.label(l);
    });
  }

  setView(v: 'grid' | 'loupe'): void {
    this.view = v;
    setHidden(this.gridWrap, v !== 'grid');
    setHidden(this.loupeWrap, v !== 'loupe');
    this.grid.show(v === 'grid');
    setClass(this.bar, 'is-grid', v === 'grid');
    for (const b of Array.from(this.bar.querySelectorAll<HTMLElement>('[data-v]'))) setClass(b, 'is-active', b.dataset.v === v);
    this.sync();
  }

  show(on: boolean): void {
    if (on) this.grid.show(this.view === 'grid');
    else this.grid.show(false);
    if (on) this.sync();
  }

  sync(): void {
    setHidden(this.empty, library.ids.length > 0);
    const it = this.current();
    for (const b of Array.from(this.sources.children) as HTMLElement[]) {
      setClass(b, 'is-on', b.dataset.key === sourceKey(library.source));
      const s = SOURCES.find((x) => sourceKey(x) === b.dataset.key);
      if (s) setText(q(b, 'em'), String(library.count(s)));
    }
    const p = library.photo(library.active);
    if (this.view === 'loupe') void this.loupe.show(p ?? null);
    const stars = Array.from(this.bar.querySelectorAll<HTMLElement>('[data-rate]'));
    for (const s of stars) setClass(s, 'is-on', !!it && Number(s.dataset.rate) <= it.rating);
    for (const s of Array.from(this.bar.querySelectorAll<HTMLElement>('[data-label]'))) setClass(s, 'is-on', !!it && it.label === s.dataset.label);
    setValue(this.keywords, it ? it.keywords.join(', ') : '');
    const rows: Array<[string, string]> = it ? [
      ['File', it.name], ['Size', `${it.fullW} x ${it.fullH}`], ['Captured', it.exif.time ? it.exif.time.slice(0, 10) : 'unknown'], ['Camera', [it.exif.make, it.exif.model].filter(Boolean).join(' ') || 'unknown'],
      ['Focal length', it.exif.focal ? `${it.exif.focal} mm` : 'unknown'], ['Exposure', [it.exif.exposure, it.exif.fnumber ? `f/${it.exif.fnumber}` : '', it.exif.iso ? `ISO ${it.exif.iso}` : ''].filter(Boolean).join('  ') || 'unknown'],
      ['Rating', it.rating ? `${it.rating} of 5` : 'none'], ['Flag', it.flag > 0 ? 'Pick' : it.flag < 0 ? 'Rejected' : 'none'],
    ] : [];
    const key = JSON.stringify(rows);
    if (this.metaBody.dataset.key !== key) {
      this.metaBody.dataset.key = key;
      while (this.metaBody.children.length > rows.length) this.metaBody.lastElementChild?.remove();
      rows.forEach(([k, v], i) => {
        let row = this.metaBody.children[i] as HTMLElement | undefined;
        if (!row) { row = el('<div class="fl-kv-row"><span></span><strong></strong></div>'); this.metaBody.appendChild(row); }
        setText(q(row, 'span'), k);
        setText(q(row, 'strong'), v);
      });
    }
  }
}
