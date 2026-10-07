import { api } from '../io/api';
import { events, type EngineEvent } from '../io/events';

export interface Photo {
  id: number;
  file: string;
  kind: string;
  fmt: string;
  w: number;
  h: number;
  a: number;
  t: string | null;
  r: number;
  f: number;
  l: string;
  e: number;
  rev: number;
  folder: number;
  m?: number;
  cn?: string;
  st?: number;
  sp?: number;
  sn?: number;
  sc?: number;
  miss?: number;
  xs?: number;
  dur?: number;
  gps?: [number, number];
}

export interface Source { kind: string; id?: number; label?: string; recursive?: boolean; ids?: number[]; value?: string }
export interface Filter {
  text?: string;
  rating?: number | null;
  ratingOp?: string;
  flags?: string[];
  labels?: string[];
  kinds?: string[];
  edited?: boolean | null;
  cameras?: string[];
  lenses?: string[];
  keywords?: number[];
  dates?: string[];
}
export interface Sort { by: string; desc: boolean }

type Fn = () => void;
type IdsFn = (ids: number[]) => void;

const VIEW_KEY = 'formlit_library_view';
const FIELDS_THAT_FILTER = new Set(['rating', 'flag', 'label', 'edited', 'kind', 'capture_time', 'file_name', 'stack_id', 'stack_pos', 'folder_id', 'missing']);

export function sameSource(a: Source, b: Source): boolean {
  return a.kind === b.kind && (a.id ?? null) === (b.id ?? null) && (a.value ?? null) === (b.value ?? null);
}

export class Library {
  source: Source = { kind: 'all', label: 'All Photographs' };
  filter: Filter = {};
  sort: Sort = { by: 'captureTime', desc: false };
  ids: number[] = [];
  readonly photos = new Map<number, Photo>();
  readonly selection = new Set<number>();
  active: number | null = null;
  anchor: number | null = null;
  loaded = false;
  revision = 0;
  private seq = 0;
  private refreshTimer = 0;
  private sessionTimer = 0;
  private readonly onList = new Set<Fn>();
  private readonly onPhotos = new Set<IdsFn>();
  private readonly onSelection = new Set<Fn>();
  private readonly onRender = new Set<(id: number, size: string) => void>();

  constructor() {
    try {
      const v = JSON.parse(localStorage.getItem(VIEW_KEY) || '{}') as { source?: Source; sort?: Sort; filter?: Filter };
      if (v.source?.kind) this.source = v.source;
      if (v.sort?.by) this.sort = v.sort;
      if (v.filter) this.filter = v.filter;
    } catch { this.source = { kind: 'all', label: 'All Photographs' }; }
    events.on('photos.added', () => this.refreshSoon(60));
    events.on('photos.removed', (e) => { this.dropIds((e.ids as number[]) ?? []); this.refreshSoon(60); });
    events.on('photos.changed', (e) => this.changed(e));
    events.on('undo', () => this.refreshSoon(30));
    events.on('redo', () => this.refreshSoon(30));
    events.on('resync', () => this.refreshSoon(0));
    events.on('list.changed', (e) => { if (e.list === 'stacks' || (e.list === 'collections' && this.source.kind !== 'all')) this.refreshSoon(60); });
    events.on('render', (e) => { for (const fn of this.onRender) fn(Number(e.id), String(e.size)); });
  }

  listen(kind: 'list', fn: Fn): Fn;
  listen(kind: 'photos', fn: IdsFn): Fn;
  listen(kind: 'selection', fn: Fn): Fn;
  listen(kind: 'render', fn: (id: number, size: string) => void): Fn;
  listen(kind: string, fn: Fn | IdsFn | ((id: number, size: string) => void)): Fn {
    const set = (kind === 'list' ? this.onList : kind === 'photos' ? this.onPhotos : kind === 'selection' ? this.onSelection : this.onRender) as Set<unknown>;
    set.add(fn);
    return () => { set.delete(fn); };
  }

  photo(id: number | null): Photo | undefined { return id === null ? undefined : this.photos.get(id); }

  selected(): number[] {
    const ids = this.ids.filter((id) => this.selection.has(id));
    if (!ids.length && this.active !== null) return [this.active];
    return ids;
  }

  targets(): number[] {
    const sel = this.selected();
    return sel.length ? sel : [];
  }

  async refresh(): Promise<void> {
    const seq = ++this.seq;
    const res = await api.cmd<{ ids: number[]; photos: Record<string, Photo> }>('library.query', { source: this.source, filter: this.filter, sort: this.sort });
    if (seq !== this.seq) return;
    this.ids = res.ids;
    for (const [k, p] of Object.entries(res.photos)) this.photos.set(Number(k), p);
    const present = new Set(this.ids);
    for (const id of Array.from(this.selection)) if (!present.has(id)) this.selection.delete(id);
    if (this.active === null || !present.has(this.active)) {
      const first = this.ids.find((id) => this.selection.has(id)) ?? this.ids[0] ?? null;
      this.active = first;
      if (first !== null && this.selection.size === 0) this.selection.add(first);
    }
    this.loaded = true;
    this.persist();
    this.emitList();
    this.emitSelection();
  }

  refreshSoon(ms = 80): void {
    window.clearTimeout(this.refreshTimer);
    this.refreshTimer = window.setTimeout(() => { void this.refresh().catch(() => undefined); }, ms);
  }

  setSource(source: Source): void {
    if (sameSource(source, this.source) && source.recursive === this.source.recursive) return;
    this.source = source;
    this.selection.clear();
    this.active = null;
    void this.refresh().catch(() => undefined);
  }

  setFilter(patch: Partial<Filter>, replace = false): void {
    this.filter = replace ? { ...patch } : { ...this.filter, ...patch };
    for (const k of Object.keys(this.filter) as Array<keyof Filter>) {
      const v = this.filter[k];
      if (v === undefined || v === null || v === '' || (Array.isArray(v) && v.length === 0)) delete this.filter[k];
    }
    this.refreshSoon(40);
  }

  hasFilter(): boolean { return Object.keys(this.filter).length > 0; }

  setSort(sort: Partial<Sort>): void {
    this.sort = { ...this.sort, ...sort };
    this.refreshSoon(0);
  }

  select(id: number, mode: 'only' | 'toggle' | 'range' | 'add' = 'only'): void {
    if (mode === 'only') {
      this.selection.clear();
      this.selection.add(id);
      this.anchor = id;
    } else if (mode === 'toggle') {
      if (this.selection.has(id) && this.selection.size > 1) {
        this.selection.delete(id);
        if (this.active === id) { this.active = this.ids.find((x) => this.selection.has(x)) ?? id; this.emitSelection(); return; }
      } else this.selection.add(id);
      this.anchor = id;
    } else if (mode === 'range') {
      const a = this.ids.indexOf(this.anchor ?? this.active ?? id);
      const b = this.ids.indexOf(id);
      if (a < 0 || b < 0) { this.select(id, 'only'); return; }
      this.selection.clear();
      for (let i = Math.min(a, b); i <= Math.max(a, b); i += 1) this.selection.add(this.ids[i]);
    } else this.selection.add(id);
    this.active = id;
    this.emitSelection();
  }

  setActive(id: number | null, keepSelection = true): void {
    if (id === null || this.active === id) return;
    if (!keepSelection || !this.selection.has(id)) { this.selection.clear(); this.selection.add(id); this.anchor = id; }
    this.active = id;
    this.emitSelection();
  }

  selectAll(): void { for (const id of this.ids) this.selection.add(id); this.emitSelection(); }

  selectNone(): void {
    this.selection.clear();
    if (this.active !== null) this.selection.add(this.active);
    this.emitSelection();
  }

  invert(): void {
    const next = this.ids.filter((id) => !this.selection.has(id));
    this.selection.clear();
    for (const id of next) this.selection.add(id);
    this.active = next[0] ?? this.active;
    this.emitSelection();
  }

  selectWhere(test: (p: Photo) => boolean): void {
    this.selection.clear();
    for (const id of this.ids) { const p = this.photos.get(id); if (p && test(p)) this.selection.add(id); }
    this.active = this.ids.find((id) => this.selection.has(id)) ?? this.active;
    this.emitSelection();
  }

  step(delta: number, extend = false): void {
    if (!this.ids.length) return;
    const i = this.active === null ? -1 : this.ids.indexOf(this.active);
    const next = this.ids[Math.max(0, Math.min(this.ids.length - 1, (i < 0 ? 0 : i + delta)))];
    if (next === undefined) return;
    if (extend) { this.select(next, 'range'); return; }
    this.select(next, 'only');
  }

  index(id: number | null): number { return id === null ? -1 : this.ids.indexOf(id); }

  async run<T = unknown>(cmd: string, params: Record<string, unknown> = {}): Promise<T> {
    return api.cmd<T>(cmd, params);
  }

  private changed(e: EngineEvent): void {
    const map = (e.photos ?? {}) as Record<string, string[]>;
    const ids = Object.keys(map).map(Number).filter((id) => this.photos.has(id));
    if (typeof e.revision === 'number') this.revision = e.revision;
    if (!ids.length) return;
    const affects = Object.values(map).some((fields) => fields.some((f) => FIELDS_THAT_FILTER.has(f)));
    if (affects && (this.hasFilter() || this.sort.by !== 'captureTime' || this.source.kind !== 'all')) { this.refreshSoon(120); }
    void this.patch(ids);
  }

  async patch(ids: number[]): Promise<void> {
    if (!ids.length) return;
    const res = await api.cmd<{ photos: Record<string, Photo> }>('library.query', { source: { kind: 'ids', ids }, stacks: false });
    for (const [k, p] of Object.entries(res.photos)) {
      const id = Number(k);
      const old = this.photos.get(id);
      if (old && old.sn !== undefined && p.sn === undefined) { p.sn = old.sn; p.sc = old.sc; }
      this.photos.set(id, p);
    }
    for (const fn of this.onPhotos) fn(ids);
  }

  private dropIds(ids: number[]): void {
    if (!ids.length) return;
    const gone = new Set(ids);
    this.ids = this.ids.filter((id) => !gone.has(id));
    for (const id of ids) { this.photos.delete(id); this.selection.delete(id); }
    if (this.active !== null && gone.has(this.active)) this.active = this.ids[0] ?? null;
    this.emitList();
    this.emitSelection();
  }

  private emitList(): void { for (const fn of this.onList) fn(); }

  emitSelection(): void {
    for (const fn of this.onSelection) fn();
    window.clearTimeout(this.sessionTimer);
    this.sessionTimer = window.setTimeout(() => {
      void api.cmd('library.select', { ids: this.selected(), active: this.active, source: this.source }).catch(() => undefined);
    }, 120);
  }

  private persist(): void {
    try { localStorage.setItem(VIEW_KEY, JSON.stringify({ source: this.source, sort: this.sort, filter: this.filter })); } catch { return; }
  }
}

export const library = new Library();
