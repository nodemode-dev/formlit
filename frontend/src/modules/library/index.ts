import type { Ctx } from '../../app';
import { catalog } from '../../state/catalog';
import { library } from '../../state/library';
import { el, q, setClass, setHidden, setText } from '../../ui/dom';
import { brandMark } from '../../ui/brand';
import { Filmstrip } from '../../ui/filmstrip';
import { ThumbGrid } from '../../ui/grid';
import { icon } from '../../ui/icons';
import { PopupMenu } from '../../ui/menu';
import { bump, previewUrl } from '../../ui/thumbs';
import { Viewer } from '../../ui/viewer';
import { registerModule, type ModuleHosts } from '../registry';
import { FilterBar } from './filterbar';
import { importDropped, openImport } from './importer';
import { InspectPanels } from './inspect';
import { PeoplePanel } from './people';
import { SourcePanels } from './sources';

type View = 'grid' | 'loupe' | 'compare' | 'survey';

const SIZE_KEY = 'formlit_grid_size';
const SORTS: Array<[string, string]> = [['captureTime', 'Capture Time'], ['importTime', 'Added Order'], ['editTime', 'Edit Time'], ['fileName', 'File Name'], ['rating', 'Rating'], ['flag', 'Pick'], ['label', 'Color Label'], ['kind', 'File Type'], ['aspect', 'Aspect Ratio'], ['camera', 'Camera'], ['userOrder', 'Custom Order']];

export let filmstrip: Filmstrip | null = null;

class LibraryModule {
  private ctx!: Ctx;
  private hosts!: ModuleHosts;
  private view: View = 'grid';
  private grid!: ThumbGrid;
  private loupe!: Viewer;
  private compareA!: Viewer;
  private compareB!: Viewer;
  private filter!: FilterBar;
  private survey!: HTMLElement;
  private empty!: HTMLElement;
  private candidate: number | null = null;
  private menu!: PopupMenu;
  private active = false;

  mount(ctx: Ctx, hosts: ModuleHosts): void {
    this.ctx = ctx;
    this.hosts = hosts;
    this.menu = new PopupMenu(ctx.commands, null, true);
    new SourcePanels(ctx, hosts.left);
    hosts.left.appendChild(new PeoplePanel(ctx).panel.root);
    new InspectPanels(ctx, hosts.right);
    this.stage();
    this.toolbar();
    this.foots();
    this.commands();
    if (!filmstrip) {
      filmstrip = new Filmstrip(ctx.shell.filmstrip);
      filmstrip.onContext = (_id, e) => this.context(e);
    }
    filmstrip.onOpen = (id) => { library.setActive(id); if (ctx.module() === 'library') this.setView('loupe'); };
    library.listen('list', () => this.syncEmpty());
    library.listen('selection', () => this.selectionChanged());
    library.listen('photos', (ids) => { if (library.active !== null && ids.includes(library.active)) this.selectionChanged(); });
    library.listen('render', (id, size) => {
      if (size !== 'p') return;
      bump(id, 'p');
      for (const v of [this.loupe, this.compareA, this.compareB]) if (v.photo?.id === id) v.refresh();
      if (this.view === 'survey' && library.selection.has(id)) this.renderSurvey();
    });
    catalog.listen(() => { this.syncEmpty(); const name = catalog.tree.catalog.name; ctx.shell.setCatalogName(name === 'formlit' ? '' : name); });
    void library.refresh().catch((e) => ctx.fail(e));
    void catalog.refresh().catch(() => undefined);
    this.setView('grid');
  }

  activate(): void {
    this.active = true;
    this.grid.show(this.view === 'grid');
    this.selectionChanged();
  }

  deactivate(): void { this.active = false; }

  private stage(): void {
    const s = this.hosts.stage;
    this.filter = new FilterBar(this.ctx);
    let size = 168;
    try { size = Number(localStorage.getItem(SIZE_KEY)) || 168; } catch { size = 168; }
    this.grid = new ThumbGrid({ axis: 'y', cls: 'fl-lg', names: true, onOpen: (id) => { library.setActive(id); this.setView('loupe'); }, onContext: (_id, e) => this.context(e) });
    this.grid.setSize(size);
    this.loupe = new Viewer('fl-loupe');
    this.loupe.onClick = (e) => this.loupe.toggleZoom(e);
    this.compareA = new Viewer('fl-compare-a');
    this.compareB = new Viewer('fl-compare-b');
    this.compareA.onClick = () => { if (this.compareA.photo) library.setActive(this.compareA.photo.id); };
    this.compareB.onClick = () => { if (this.compareB.photo) this.candidate = this.compareB.photo.id; };
    const gridWrap = el('<div class="fl-lib-view fl-lib-grid"></div>');
    gridWrap.append(this.filter.root, this.grid.root);
    const loupeWrap = el('<div class="fl-lib-view fl-lib-loupe" hidden></div>');
    loupeWrap.appendChild(this.loupe.root);
    const compareWrap = el(`<div class="fl-lib-view fl-lib-compare" hidden><div class="fl-compare-pane"><div class="fl-compare-tag">Select</div></div><div class="fl-compare-pane"><div class="fl-compare-tag">Candidate</div></div></div>`);
    compareWrap.children[0].appendChild(this.compareA.root);
    compareWrap.children[1].appendChild(this.compareB.root);
    this.survey = el('<div class="fl-lib-view fl-lib-survey" hidden></div>');
    this.survey.addEventListener('click', (e) => {
      const tile = (e.target as HTMLElement).closest<HTMLElement>('.fl-survey-tile');
      if (!tile) return;
      const id = Number(tile.dataset.id);
      if ((e.target as HTMLElement).closest('.fl-survey-x')) { library.selection.delete(id); library.emitSelection(); return; }
      library.setActive(id);
    });
    this.empty = el(`<div class="fl-empty" hidden><div class="fl-empty-card"><div class="fl-empty-title">${brandMark(28)}<span>Your library is empty</span></div><div class="fl-empty-sub">Import a folder of photos to start. formlit reads raw files from every major camera, plus JPEG, HEIC, TIFF, PNG and video, and never changes your originals.</div><div class="fl-empty-actions"><button class="cv-btn fl-btn-cta" type="button" data-cmd="library.import">${icon('importLit', 16)} Import Photos...</button></div><div class="fl-empty-sub fl-muted">or drop photos anywhere on this window</div></div></div>`);
    s.append(gridWrap, loupeWrap, compareWrap, this.survey, this.empty);
    const drop = el('<div class="fl-dropzone" hidden><div>Drop photos to import</div></div>');
    s.appendChild(drop);
    s.addEventListener('dragover', (e) => { if (e.dataTransfer?.types.includes('Files')) { e.preventDefault(); setHidden(drop, false); } });
    s.addEventListener('dragleave', (e) => { if (!s.contains(e.relatedTarget as Node)) setHidden(drop, true); });
    s.addEventListener('drop', (e) => {
      setHidden(drop, true);
      if (!e.dataTransfer?.files.length) return;
      e.preventDefault();
      void importDropped(this.ctx, e.dataTransfer.files);
    });
  }

  private toolbar(): void {
    const t = this.hosts.toolbar;
    const viewBtn = (v: View, ic: string, label: string, key: string) => `<button class="cv-icon-btn" type="button" data-cmd="view.${v}" aria-label="${label}" title="${label} (${key})">${icon(ic, 16)}</button>`;
    const bar = el(`<div class="fl-tb">
<div class="fl-tb-group">${viewBtn('grid', 'viewGridLit', 'Grid', 'G')}${viewBtn('loupe', 'viewLoupe', 'Loupe', 'E')}${viewBtn('compare', 'viewCompare', 'Compare', 'C')}${viewBtn('survey', 'viewSurvey', 'Survey', 'N')}</div>
<span class="fl-tb-sep"></span>
<span class="fl-tb-label">Sort</span><select class="cv-select fl-tb-sort">${SORTS.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select>
<button class="cv-icon-btn fl-tb-dir" type="button" aria-label="Sort Direction">${icon('sortLit', 16)}</button>
<span class="fl-tb-sep"></span>
<button class="cv-icon-btn" type="button" data-cmd="photo.pick" aria-label="Flag as Pick">${icon('flagPick', 16)}</button>
<button class="cv-icon-btn" type="button" data-cmd="photo.reject" aria-label="Reject">${icon('flagReject', 16)}</button>
<span class="fl-tb-stars">${[1, 2, 3, 4, 5].map((n) => `<button type="button" data-cmd="photo.rate${n}" aria-label="${n} stars">${icon('starFill', 13)}</button>`).join('')}</span>
<span class="fl-tb-labels">${['red', 'yellow', 'green', 'blue', 'purple'].map((l) => `<button class="fl-swatch-btn" type="button" data-cmd="photo.label.${l}" data-label="${l}"></button>`).join('')}</span>
<span class="fl-tb-sep"></span>
<button class="cv-icon-btn" type="button" data-cmd="photo.rotateLeft" aria-label="Rotate Left">${icon('rotateLeft', 16)}</button>
<button class="cv-icon-btn" type="button" data-cmd="photo.rotateRight" aria-label="Rotate Right">${icon('rotateRight', 16)}</button>
<span class="fl-tb-spacer"></span>
<span class="fl-tb-label fl-tb-zoom"></span>
<span class="fl-tb-label fl-tb-gridonly">Thumbnails</span><input class="cv-slider fl-tb-size fl-tb-gridonly" type="range" min="80" max="400" step="4" aria-label="Thumbnail size">
</div>`);
    t.appendChild(bar);
    const sort = q<HTMLSelectElement>(bar, '.fl-tb-sort');
    sort.value = library.sort.by;
    sort.addEventListener('change', () => library.setSort({ by: sort.value }));
    const dir = q(bar, '.fl-tb-dir');
    setClass(dir, 'is-flipped', library.sort.desc);
    dir.addEventListener('click', () => { library.setSort({ desc: !library.sort.desc }); setClass(dir, 'is-flipped', library.sort.desc); });
    const size = q<HTMLInputElement>(bar, '.fl-tb-size');
    size.value = String(this.grid.cellSize);
    size.addEventListener('input', () => {
      this.grid.setSize(Number(size.value));
      try { localStorage.setItem(SIZE_KEY, size.value); } catch { return; }
    });
    this.loupe.onZoom = () => this.syncZoom();
  }

  private syncZoom(): void {
    const z = this.loupe.zoom;
    setText(q(this.hosts.toolbar, '.fl-tb-zoom'), this.view === 'loupe' ? (z === 'fit' ? 'Fit' : z === 'fill' ? 'Fill' : `${Math.round(z * 100)}%`) : '');
  }

  private foots(): void {
    const l = el(`<div class="fl-foot-row"><button class="cv-btn" type="button" data-cmd="library.import">Import...</button><button class="cv-btn" type="button" data-cmd="library.export">Export...</button></div>`);
    const r = el(`<div class="fl-foot-row"><button class="cv-btn" type="button" data-cmd="develop.syncSettings">Sync Settings</button><button class="cv-btn" type="button" data-cmd="library.syncMetadata">Sync Metadata</button></div>`);
    this.hosts.leftFoot.appendChild(l);
    this.hosts.rightFoot.appendChild(r);
  }

  private commands(): void {
    const ctx = this.ctx;
    const toLib = (v: View) => () => { if (ctx.module() !== 'library') ctx.toModule('library'); this.setView(v); };
    ctx.commands.add(
      { id: 'view.grid', label: 'Grid', keys: ['G'], run: toLib('grid'), checked: () => ctx.module() === 'library' && this.view === 'grid' },
      { id: 'view.loupe', label: 'Loupe', keys: ['E'], run: toLib('loupe'), checked: () => ctx.module() === 'library' && this.view === 'loupe' },
      { id: 'view.compare', label: 'Compare', keys: ['C'], run: toLib('compare'), checked: () => ctx.module() === 'library' && this.view === 'compare' },
      { id: 'view.survey', label: 'Survey', keys: ['N'], run: toLib('survey'), checked: () => ctx.module() === 'library' && this.view === 'survey' },
      { id: 'view.filterBar', label: 'Show Filter Bar', keys: ['\\'], run: () => { if (ctx.module() !== 'library') ctx.toModule('library'); this.setView('grid'); this.filter.toggle(); }, checked: () => this.filter.visible },
      { id: 'view.find', label: 'Find...', keys: ['Mod+F'], run: () => { if (ctx.module() !== 'library') ctx.toModule('library'); this.setView('grid'); this.filter.focusText(); } },
      { id: 'view.zoomIn', label: 'Zoom In', keys: ['Mod+='], run: () => { this.setView('loupe'); this.loupe.setZoom(Math.min(8, this.loupe.scale() * 1.5)); } },
      { id: 'view.zoomOut', label: 'Zoom Out', keys: ['Mod+-'], run: () => { this.setView('loupe'); this.loupe.setZoom(Math.max(0.05, this.loupe.scale() / 1.5)); } },
      { id: 'view.zoomToggle', label: 'Toggle Zoom View', keys: ['Z'], run: () => { if (this.view !== 'loupe') this.setView('loupe'); this.loupe.toggleZoom(); } },
      { id: 'view.info', label: 'Cycle Info Overlay', keys: ['I'], run: () => this.loupe.setInfo((this.loupe.infoMode + 1) % 2) },
      { id: 'library.import', label: 'Import Photos and Videos...', keys: ['Shift+Mod+I'], run: () => openImport(ctx) },
      { id: 'library.filterPicks', label: 'Show Picks Only', run: () => library.setFilter({ flags: library.filter.flags?.length ? [] : ['pick'] }), checked: () => !!library.filter.flags?.includes('pick') },
      { id: 'library.filterOff', label: 'Filters Off', keys: ['Mod+L'], run: () => library.setFilter({}, true), enabled: () => library.hasFilter() },
      { id: 'library.swapCompare', label: 'Swap Select and Candidate', run: () => { const a = library.active; library.setActive(this.candidate); this.candidate = a; this.renderCompare(); } },
      { id: 'library.syncMetadata', label: 'Sync Metadata', run: () => void this.syncMetadata(), enabled: () => library.targets().length > 1 },
    );
  }

  private async syncMetadata(): Promise<void> {
    const ids = library.targets();
    const src = library.active;
    if (src === null || ids.length < 2) return;
    try {
      const d = await this.ctx.api.cmd<{ meta: Record<string, string>; keywords: string[] }>('photo.get', { id: src });
      await this.ctx.api.cmd('photo.setMeta', { ids, fields: d.meta });
      await this.ctx.api.cmd('photo.addKeywords', { ids, keywords: d.keywords });
    } catch (err) { this.ctx.fail(err); }
  }

  private context(e: MouseEvent): void {
    this.menu.setItems(['photo.pick', 'photo.reject', 'photo.unflag', '-', { label: 'Set Rating', items: ['photo.rate0', 'photo.rate1', 'photo.rate2', 'photo.rate3', 'photo.rate4', 'photo.rate5'] }, { label: 'Set Color Label', items: ['photo.label.red', 'photo.label.yellow', 'photo.label.green', 'photo.label.blue', 'photo.label.purple', 'photo.label.none'] }, '-', 'module.develop', 'library.export', '-', 'photo.virtualCopy', 'photo.quick', 'photo.target', { label: 'Stacking', items: ['photo.stack', 'photo.unstack', 'photo.toggleStack', 'photo.stackTop', 'photo.autoStack'] }, 'photo.rotateLeft', 'photo.rotateRight', '-', 'photo.saveMetadata', 'photo.reveal', '-', 'photo.remove']);
    this.menu.openAt(e.clientX, e.clientY);
  }

  setView(v: View): void {
    this.view = v;
    const s = this.hosts.stage;
    for (const [cls, on] of [['.fl-lib-grid', v === 'grid'], ['.fl-lib-loupe', v === 'loupe'], ['.fl-lib-compare', v === 'compare'], ['.fl-lib-survey', v === 'survey']] as Array<[string, boolean]>) setHidden(q(s, cls), !on);
    this.grid.show(v === 'grid');
    setClass(q(this.hosts.toolbar, '.fl-tb'), 'is-grid', v === 'grid');
    if (v === 'compare' && this.candidate === null) {
      const i = library.index(library.active);
      this.candidate = library.ids[i + 1] ?? library.ids[i - 1] ?? null;
    }
    this.selectionChanged();
    this.syncZoom();
    this.syncEmpty();
  }

  private selectionChanged(): void {
    if (!this.active && this.ctx.module() !== 'library') return;
    const p = library.photo(library.active) ?? null;
    if (this.view === 'loupe') void this.loupe.show(p);
    if (this.view === 'compare') this.renderCompare();
    if (this.view === 'survey') this.renderSurvey();
    const n = library.selected().length;
    this.ctx.shell.setSelection(n > 1 ? `${n} selected` : p ? p.file : '');
    this.ctx.shell.setCount(`${library.ids.length} photo${library.ids.length === 1 ? '' : 's'}`);
  }

  private renderCompare(): void {
    const a = library.photo(library.active) ?? null;
    if (this.candidate === library.active) this.candidate = library.ids.find((id) => id !== library.active && library.selection.has(id)) ?? null;
    const b = library.photo(this.candidate) ?? null;
    void this.compareA.show(a);
    void this.compareB.show(b);
  }

  private renderSurvey(): void {
    const ids = library.selected().slice(0, 24);
    const n = ids.length;
    const cols = Math.ceil(Math.sqrt(n * 1.5)) || 1;
    this.survey.style.setProperty('--cols', String(cols));
    const keep = new Map<string, HTMLElement>();
    for (const c of Array.from(this.survey.children) as HTMLElement[]) keep.set(c.dataset.id ?? '', c);
    const next: HTMLElement[] = [];
    for (const id of ids) {
      const p = library.photo(id);
      if (!p) continue;
      let tile = keep.get(String(id));
      if (!tile) {
        tile = el(`<div class="fl-survey-tile" data-id="${id}"><img alt="" draggable="false"><button class="fl-survey-x cv-icon-btn" type="button" aria-label="Remove from Survey">${icon('close', 12)}</button></div>`);
      }
      const img = q<HTMLImageElement>(tile, 'img');
      const url = previewUrl(p);
      if (img.dataset.src !== url) {
        img.dataset.src = url;
        const pre = new Image();
        pre.src = url;
        void pre.decode().then(() => { if (img.dataset.src === url) img.src = url; }, () => undefined);
      }
      setClass(tile, 'is-active', id === library.active);
      next.push(tile);
    }
    this.survey.replaceChildren(...next);
  }

  private syncEmpty(): void {
    const none = library.loaded && catalog.tree.catalog.total === 0 && library.source.kind === 'all';
    setHidden(this.empty, !none);
  }

  onKey(_e: KeyboardEvent, combo: string): boolean {
    if (this.view === 'grid' && (combo === 'Up' || combo === 'Down' || combo === 'Shift+Up' || combo === 'Shift+Down')) {
      const d = (combo.endsWith('Up') ? -1 : 1) * this.grid.columns;
      library.step(d, combo.startsWith('Shift'));
      return true;
    }
    if (combo === 'Enter' && this.view === 'grid') { this.setView('loupe'); return true; }
    if (combo === 'Escape' && this.view !== 'grid') { this.setView('grid'); return true; }
    return false;
  }
}

const mod = new LibraryModule();

registerModule({
  id: 'library', label: 'Library', icon: 'modLibrary', key: 'Alt+Mod+1', order: 1,
  mount: (ctx, hosts) => mod.mount(ctx, hosts),
  activate: () => mod.activate(),
  deactivate: () => mod.deactivate(),
  onKey: (e, combo) => mod.onKey(e, combo),
});
