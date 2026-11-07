import { Frame } from '../engine/geometry';
import { COLLECTIONS } from '../data/library';
import { store, type Item } from '../store';

export interface Photo {
  id: number; file: string; kind: string; fmt: string; w: number; h: number; a: number; t: string | null; r: number; f: number; l: string; e: number; rev: number; folder: number;
  m?: number; cn?: string; st?: number; sp?: number; sn?: number; sc?: number; miss?: number; xs?: number; dur?: number;
}
export interface Source { kind: string; id?: number; label?: string; value?: string }
export interface Filter { text?: string; rating?: number | null; flags?: string[]; labels?: string[]; edited?: boolean | null }
export interface Sort { by: string; desc: boolean }

type Fn = () => void;

export const SOURCES: Source[] = [
  { kind: 'all', label: 'All Photographs' },
  ...COLLECTIONS.map((c): Source => ({ kind: 'collection', value: c.id, label: c.name })),
  { kind: 'picks', label: 'Picks' },
  { kind: 'edited', label: 'Edited' },
  { kind: 'imported', label: 'Your Files' },
  { kind: 'samples', label: 'Procedural Samples' },
];

export const sourceKey = (s: Source): string => `${s.kind}:${s.value ?? ''}`;

export function photoOf(it: Item): Photo {
  const [nw, nh] = new Frame(it.src.w, it.src.h, it.dev).nativeSize();
  return {
    id: it.id, file: it.name, kind: 'photo', fmt: it.fmt, w: it.fullW, h: it.fullH, a: nw / Math.max(nh, 1), t: it.exif.time ?? null, r: it.rating, f: it.flag, l: it.label,
    e: store.isEdited(it) ? 1 : 0, rev: it.thumbRev, folder: 1,
  };
}

export class Library {
  source: Source = SOURCES[0];
  filter: Filter = {};
  sort: Sort = { by: 'importTime', desc: false };
  ids: number[] = [];
  readonly photos = new Map<number, Photo>();
  readonly selection = new Set<number>();
  active: number | null = null;
  anchor: number | null = null;
  loaded = false;
  revision = 0;
  private readonly onList = new Set<Fn>();
  private readonly onPhotos = new Set<(ids: number[]) => void>();
  private readonly onSelection = new Set<Fn>();
  private readonly onRender = new Set<(id: number, size: string) => void>();

  constructor() {
    store.listen('list', () => this.refresh());
    store.listen('item', (id) => {
      const it = store.items.get(id as number);
      if (!it) return;
      this.photos.set(it.id, photoOf(it));
      if (this.source.kind !== 'all' || this.hasFilter() || this.sort.by === 'rating' || this.sort.by === 'flag') this.refresh();
      for (const fn of this.onPhotos) fn([it.id]);
    });
    store.listen('render', (id, size) => {
      const it = store.items.get(id as number);
      if (it && size === 't') { this.photos.set(it.id, photoOf(it)); }
      for (const fn of this.onRender) fn(id as number, size as string);
    });
  }

  listen(kind: 'list', fn: Fn): Fn;
  listen(kind: 'photos', fn: (ids: number[]) => void): Fn;
  listen(kind: 'selection', fn: Fn): Fn;
  listen(kind: 'render', fn: (id: number, size: string) => void): Fn;
  listen(kind: string, fn: Fn | ((ids: number[]) => void) | ((id: number, size: string) => void)): Fn {
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

  inSource(it: Item, s: Source): boolean {
    const k = s.kind;
    if (k === 'collection') return it.collection === s.value;
    if (k === 'samples') return it.sample;
    if (k === 'imported') return !it.sample && !it.blob;
    if (k === 'picks') return it.flag > 0;
    if (k === 'edited') return store.isEdited(it);
    return true;
  }

  count(s: Source): number {
    let n = 0;
    for (const it of store.items.values()) if (this.inSource(it, s)) n += 1;
    return n;
  }

  private matches(it: Item): boolean {
    if (!this.inSource(it, this.source)) return false;
    const f = this.filter;
    if (f.text && !`${it.name} ${it.keywords.join(' ')} ${it.exif.model ?? ''}`.toLowerCase().includes(f.text.toLowerCase())) return false;
    if (typeof f.rating === 'number' && f.rating > 0 && it.rating < f.rating) return false;
    if (f.flags?.length) {
      const key = it.flag > 0 ? 'pick' : it.flag < 0 ? 'reject' : 'none';
      if (!f.flags.includes(key)) return false;
    }
    if (f.labels?.length && !f.labels.includes(it.label)) return false;
    if (f.edited === true && !store.isEdited(it)) return false;
    return true;
  }

  refresh(): void {
    const all = store.order.map((id) => store.items.get(id)).filter((x): x is Item => !!x);
    for (const it of all) this.photos.set(it.id, photoOf(it));
    const list = all.filter((it) => this.matches(it));
    const by = this.sort.by;
    const key = (it: Item): string | number => by === 'fileName' ? it.name.toLowerCase() : by === 'rating' ? it.rating : by === 'flag' ? it.flag : by === 'captureTime' ? (it.exif.time ?? '') : it.added;
    list.sort((a, b) => { const x = key(a), y = key(b); return x < y ? -1 : x > y ? 1 : a.id - b.id; });
    if (this.sort.desc) list.reverse();
    this.ids = list.map((it) => it.id);
    const present = new Set(this.ids);
    for (const id of Array.from(this.selection)) if (!present.has(id)) this.selection.delete(id);
    if (this.active === null || !present.has(this.active)) {
      this.active = this.ids.find((id) => this.selection.has(id)) ?? this.ids[0] ?? null;
      if (this.active !== null && this.selection.size === 0) this.selection.add(this.active);
    }
    this.loaded = true;
    for (const fn of this.onList) fn();
    for (const fn of this.onSelection) fn();
  }

  hasFilter(): boolean { return Object.keys(this.filter).length > 0; }

  setSource(source: Source): void {
    this.source = source;
    this.selection.clear();
    this.active = null;
    this.refresh();
  }

  setFilter(patch: Partial<Filter>, replace = false): void {
    this.filter = replace ? { ...patch } : { ...this.filter, ...patch };
    for (const k of Object.keys(this.filter) as Array<keyof Filter>) {
      const v = this.filter[k];
      if (v === undefined || v === null || v === '' || (Array.isArray(v) && v.length === 0)) delete this.filter[k];
    }
    this.refresh();
  }

  setSort(sort: Partial<Sort>): void {
    this.sort = { ...this.sort, ...sort };
    this.refresh();
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

  step(delta: number, extend = false): void {
    if (!this.ids.length) return;
    const i = this.active === null ? -1 : this.ids.indexOf(this.active);
    const next = this.ids[Math.max(0, Math.min(this.ids.length - 1, i < 0 ? 0 : i + delta))];
    if (next === undefined) return;
    if (extend) { this.select(next, 'range'); return; }
    this.select(next, 'only');
  }

  index(id: number | null): number { return id === null ? -1 : this.ids.indexOf(id); }

  emitSelection(): void { for (const fn of this.onSelection) fn(); }
}

export const library = new Library();
