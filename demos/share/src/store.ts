import { events } from './shims/events';
import type { Dict, TemplateDef } from './layout';
import { canvasBlob, dropSource, registerSource, resample, bitmapOf } from './render';
import type { Row } from './data';

export interface Rec {
  id: number;
  file: string;
  mime: string;
  bytes: Uint8Array;
  w: number;
  h: number;
  time: string | null;
  make: string;
  camera: string;
  lens: string;
  focal: number | null;
  aperture: number | null;
  shutter: number | null;
  iso: number | null;
  gps: [number, number] | null;
  alt: number | null;
  rating: number;
  flag: number;
  label: string;
  title: string;
  caption: string;
  copyright: string;
  creator: string;
  keywords: string[];
  rev: number;
  thumb: string;
  preview: string;
}

export interface Loc { id: number; name: string; lat: number; lon: number; radius: number; private: boolean }
export interface Col { id: number; name: string; kind: string; ids: number[]; settings: Dict | null }

export interface RecInput {
  file: string;
  bytes: Uint8Array;
  mime: string;
  time?: string | null;
  make?: string;
  camera?: string;
  lens?: string;
  focal?: number | null;
  aperture?: number | null;
  shutter?: number | null;
  iso?: number | null;
  gps?: [number, number] | null;
  alt?: number | null;
  rating?: number;
  flag?: number;
  label?: string;
  title?: string;
  caption?: string;
  copyright?: string;
  creator?: string;
  keywords?: string[];
}

export function km(a: number, b: number, c: number, d: number): number {
  const p1 = (a * Math.PI) / 180, p2 = (c * Math.PI) / 180;
  const dp = p2 - p1, dl = ((d - b) * Math.PI) / 180;
  const h = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.min(1, Math.sqrt(h)));
}

export function rowInput(row: Row, bytes: Uint8Array): RecInput {
  return {
    file: `${row.slug}.jpg`, bytes, mime: 'image/jpeg', time: row.date ? `${row.date}T12:00:00` : null, camera: row.camera, focal: row.focal, aperture: row.aperture, iso: row.iso, shutter: row.shutter,
    gps: row.gps, rating: row.rating, flag: row.flag, label: row.label, title: row.title, caption: row.caption, copyright: `Photo: ${row.who} (Pexels)`, creator: row.who, keywords: row.keywords,
  };
}

class Store {
  readonly recs = new Map<number, Rec>();
  readonly locations: Loc[] = [];
  readonly collections: Col[] = [];
  readonly prefs: { templates: Record<string, unknown[]>; bookTemplates: Record<string, TemplateDef>; exportPresets: Array<{ id: string; name: string; settings: Dict }> } = { templates: {}, bookTemplates: {}, exportPresets: [] };
  readonly audio = new Map<string, { url: string; seconds: number }>();
  revision = 1;
  private nextId = 1;
  private nextLoc = 1;
  private nextCol = 1;

  async add(input: RecInput): Promise<Rec> {
    const id = this.nextId;
    this.nextId += 1;
    registerSource(id, input.bytes, input.mime);
    let bmp: ImageBitmap;
    try { bmp = await bitmapOf(id); } catch { dropSource(id); throw new Error(`${input.file} is not a picture this browser can open`); }
    const long = Math.max(bmp.width, bmp.height);
    const thumb = URL.createObjectURL(await canvasBlob(resample(bmp, (bmp.width * Math.min(1, 360 / long)), (bmp.height * Math.min(1, 360 / long))), 'image/jpeg', 0.82));
    const preview = URL.createObjectURL(await canvasBlob(resample(bmp, (bmp.width * Math.min(1, 1600 / long)), (bmp.height * Math.min(1, 1600 / long))), 'image/jpeg', 0.88));
    const rec: Rec = {
      id, file: input.file, mime: input.mime, bytes: input.bytes, w: bmp.width, h: bmp.height, time: input.time ?? null, make: input.make ?? '', camera: input.camera ?? '', lens: input.lens ?? '',
      focal: input.focal ?? null, aperture: input.aperture ?? null, shutter: input.shutter ?? null, iso: input.iso ?? null, gps: input.gps ?? null, alt: input.alt ?? null,
      rating: input.rating ?? 0, flag: input.flag ?? 0, label: input.label ?? '', title: input.title ?? '', caption: input.caption ?? '', copyright: input.copyright ?? '', creator: input.creator ?? '',
      keywords: input.keywords ?? [], rev: 1, thumb, preview,
    };
    this.recs.set(id, rec);
    return rec;
  }

  announce(ids: number[]): void {
    this.revision += 1;
    events.emit({ type: 'photos.added', ids, revision: this.revision });
  }

  rec(id: number): Rec {
    const r = this.recs.get(id);
    if (!r) throw new Error('That photo is no longer open');
    return r;
  }

  aspect(id: number): number {
    const r = this.recs.get(id);
    return r ? r.w / Math.max(1, r.h) : 1.5;
  }

  aspects(ids: number[]): Map<number, number> {
    return new Map(ids.map((i) => [i, this.aspect(i)]));
  }

  row(r: Rec): Dict {
    const out: Dict = { id: r.id, file: r.file, kind: 'photo', fmt: r.mime === 'image/png' ? 'png' : r.mime === 'image/webp' ? 'webp' : 'jpeg', w: r.w, h: r.h, a: r.w / r.h, t: r.time, r: r.rating, f: r.flag, l: r.label, e: 0, rev: r.rev, folder: 1 };
    if (r.camera) out.cn = r.camera;
    if (r.gps) out.gps = r.gps;
    return out;
  }

  list(source: Dict, filter: Dict, sort: Dict): number[] {
    let ids = Array.from(this.recs.keys());
    if (source.kind === 'ids') ids = (source.ids as number[]).filter((i) => this.recs.has(i));
    else if (source.kind === 'collection') ids = (this.collections.find((c) => c.id === source.id)?.ids ?? []).filter((i) => this.recs.has(i));
    const f = filter ?? {};
    ids = ids.filter((id) => {
      const r = this.rec(id);
      if (f.hasGps === true && !r.gps) return false;
      if (f.hasGps === false && r.gps) return false;
      if (Array.isArray(f.gpsBox) && f.gpsBox.length === 4) {
        const [la0, lo0, la1, lo1] = f.gpsBox as number[];
        if (!r.gps || r.gps[0] < la0 || r.gps[0] > la1 || r.gps[1] < lo0 || r.gps[1] > lo1) return false;
      }
      if (Array.isArray(f.flags) && f.flags.length) {
        const want = new Set(f.flags as string[]);
        if (!((want.has('pick') && r.flag === 1) || (want.has('reject') && r.flag === -1) || (want.has('none') && r.flag === 0))) return false;
      }
      if (typeof f.rating === 'number' && f.rating > 0) {
        const op = f.ratingOp ?? '>=';
        if (op === '=' ? r.rating !== f.rating : op === '<=' ? r.rating > f.rating : r.rating < f.rating) return false;
      }
      if (typeof f.text === 'string' && f.text.trim()) {
        const t = f.text.trim().toLowerCase();
        if (![r.file, r.title, r.caption, r.keywords.join(' ')].join(' ').toLowerCase().includes(t)) return false;
      }
      return true;
    });
    const by = String(sort?.by ?? 'captureTime');
    const key = (id: number): string | number => {
      const r = this.rec(id);
      return by === 'fileName' ? r.file.toLowerCase() : by === 'rating' ? r.rating : r.time ?? '9999';
    };
    ids.sort((a, b) => {
      const ka = key(a), kb = key(b);
      return ka < kb ? -1 : ka > kb ? 1 : a - b;
    });
    if (sort?.desc) ids.reverse();
    if (source.kind === 'collection' && by === 'userOrder') {
      const order = this.collections.find((c) => c.id === source.id)?.ids ?? [];
      ids.sort((a, b) => order.indexOf(a) - order.indexOf(b));
    }
    return ids;
  }

  addLocation(l: Omit<Loc, 'id'>): number {
    const id = this.nextLoc;
    this.nextLoc += 1;
    this.locations.push({ ...l, id });
    return id;
  }

  addCollection(c: Omit<Col, 'id'>): number {
    const id = this.nextCol;
    this.nextCol += 1;
    this.collections.push({ ...c, id });
    return id;
  }

  inPrivate(r: Rec): boolean {
    if (!r.gps) return false;
    return this.locations.some((l) => l.private && km(r.gps![0], r.gps![1], l.lat, l.lon) <= l.radius);
  }
}

export const store = new Store();
