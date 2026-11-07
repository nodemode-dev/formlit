import { readExif } from './exif';
import { events } from './shims/events';
import { changed } from './jobs';
import { PLACES } from './gazetteer';
import { outputUrl, saveOutput } from './outputs';
import { OUTPUT_COMMANDS, type Handler } from './engine-output';
import { store, km, type Rec } from './store';
import type { Dict } from './layout';

export class EngineMiss extends Error {}

function idsOf(p: Dict): number[] {
  return Array.isArray(p.ids) ? (p.ids as unknown[]).map(Number).filter((i) => store.recs.has(i)) : [];
}

function settleCollections(): void {
  events.emit({ type: 'list.changed', list: 'collections' });
}

const near = (r: Rec, loc: { lat: number; lon: number; radius: number }): boolean => !!r.gps && km(r.gps[0], r.gps[1], loc.lat, loc.lon) <= loc.radius;

function gpxPoints(text: string): Array<[number, number, number]> {
  const doc = new DOMParser().parseFromString(text, 'application/xml');
  const out: Array<[number, number, number]> = [];
  for (const pt of Array.from(doc.querySelectorAll('trkpt, rtept'))) {
    const t = pt.querySelector('time')?.textContent;
    if (!t) continue;
    const when = Date.parse(t.trim());
    if (Number.isFinite(when)) out.push([when / 1000, Number(pt.getAttribute('lat')), Number(pt.getAttribute('lon'))]);
  }
  return out.sort((a, b) => a[0] - b[0]);
}

const CORE: Record<string, Handler> = {
  'library.query': (p) => {
    const ids = store.list((p.source ?? { kind: 'all' }) as Dict, (p.filter ?? {}) as Dict, (p.sort ?? {}) as Dict);
    const photos: Record<string, Dict> = {};
    for (const id of ids) photos[String(id)] = store.row(store.rec(id));
    return { ids, photos };
  },
  'library.tree': () => ({
    catalog: { name: 'Shared Pictures', path: '', total: store.recs.size, previousImport: 0, quick: 0, missing: 0, revision: store.revision },
    folders: [{ id: 1, path: 'Pexels', name: 'Pexels', parent: null, count: store.recs.size, missing: 0, online: true }],
    volumes: [],
    collections: store.collections.map((c) => ({ id: c.id, name: c.name, kind: c.kind, parent: null, count: c.ids.length, target: false, rules: null, settings: c.settings, service: null, cover: c.ids[0] ?? null })),
    keywords: [],
    labelNames: {},
  }),
  'library.select': () => ({}),
  'library.labelNames': () => ({ names: {} }),
  'prefs.get': () => ({ templates: store.prefs.templates, bookTemplates: store.prefs.bookTemplates, exportPresets: store.prefs.exportPresets }),
  'prefs.set': (p) => {
    const v = (p.values ?? {}) as Dict;
    if (v.templates) store.prefs.templates = v.templates;
    if (v.bookTemplates) store.prefs.bookTemplates = v.bookTemplates;
    return {};
  },
  'photo.setRating': (p) => { for (const id of idsOf(p)) store.rec(id).rating = Number(p.rating); changed(idsOf(p), ['rating']); return {}; },
  'photo.setFlag': (p) => { for (const id of idsOf(p)) store.rec(id).flag = Number(p.flag); changed(idsOf(p), ['flag']); return {}; },
  'photo.setGps': (p) => {
    const ids = idsOf(p);
    const has = typeof p.lat === 'number' && typeof p.lon === 'number';
    if (has && !(Math.abs(Number(p.lat)) <= 90 && Math.abs(Number(p.lon)) <= 180)) throw new Error('Latitude is -90 to 90 and longitude is -180 to 180');
    for (const id of ids) store.rec(id).gps = has ? [Number(p.lat), Number(p.lon)] : null;
    changed(ids, ['gps_lat', 'gps_lon']);
    return { ids, lat: p.lat ?? null, lon: p.lon ?? null };
  },
  'gps.search': (p) => {
    const q = String(p.query ?? '').trim();
    if (!q) return { results: [] };
    const m = /^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$/.exec(q);
    if (m && Math.abs(Number(m[1])) <= 90 && Math.abs(Number(m[2])) <= 180) return { results: [{ name: `${Number(m[1]).toFixed(6)}, ${Number(m[2]).toFixed(6)}`, lat: Number(m[1]), lon: Number(m[2]), bbox: null }] };
    const key = q.toLowerCase();
    const hits = PLACES.filter((x) => x.name.toLowerCase().includes(key)).slice(0, 6);
    return { results: hits.map((x) => ({ name: x.name, lat: x.lat, lon: x.lon, kind: x.kind, bbox: null })), attribution: 'Place names from the small list built into this demo' };
  },
  'gps.lookupAddress': (p) => {
    const ids = idsOf(p).filter((i) => store.rec(i).gps);
    const seen = new Set<string>();
    let filled = 0;
    for (const id of ids) {
      const r = store.rec(id);
      let best: { name: string; d: number } | null = null;
      for (const x of PLACES) {
        if (x.kind === 'sea') continue;
        const d = km(r.gps![0], r.gps![1], x.lat, x.lon);
        if (!best || d < best.d) best = { name: x.name, d };
      }
      if (best && best.d < 800) { seen.add(best.name); filled += 1; }
    }
    return { photos: filled, places: seen.size };
  },
  'gps.tracklog': (p) => {
    const text = String(p.gpx ?? '');
    if (!text) throw new Error('Pass a GPX file path or its contents');
    const pts = gpxPoints(text);
    if (!pts.length) throw new Error('The track log has no timed points');
    const offset = typeof p.offsetMinutes === 'number' ? Number(p.offsetMinutes) : -new Date().getTimezoneOffset();
    const maxGap = 30 * 60;
    const matched: Record<string, [number, number]> = {};
    for (const id of idsOf(p)) {
      const r = store.rec(id);
      if (!r.time) continue;
      const when = Date.parse(`${r.time}Z`);
      if (!Number.isFinite(when)) continue;
      const ts = when / 1000 - offset * 60;
      let i = pts.findIndex((x) => x[0] >= ts);
      if (i < 0) i = pts.length;
      if (i > 0 && i < pts.length && pts[i][0] - pts[i - 1][0] <= maxGap) {
        const a = pts[i - 1], b = pts[i];
        const k = (ts - a[0]) / Math.max(1e-6, b[0] - a[0]);
        matched[String(id)] = [a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
      } else {
        const j = [i - 1, i].filter((x) => x >= 0 && x < pts.length).sort((x, y) => Math.abs(pts[x][0] - ts) - Math.abs(pts[y][0] - ts))[0];
        if (j !== undefined && Math.abs(pts[j][0] - ts) <= maxGap) matched[String(id)] = [pts[j][1], pts[j][2]];
      }
    }
    const hit = Object.keys(matched).map(Number);
    if (p.apply !== false && hit.length) { for (const id of hit) store.rec(id).gps = matched[String(id)]; changed(hit, ['gps_lat', 'gps_lon']); }
    const step = Math.max(1, Math.floor(pts.length / 2000));
    return { matched, count: hit.length, points: pts.length, track: pts.filter((_x, i) => i % step === 0).map((x) => [x[1], x[2]]), start: new Date(pts[0][0] * 1000).toISOString(), end: new Date(pts[pts.length - 1][0] * 1000).toISOString(), offsetMinutes: offset };
  },
  'location.list': () => ({ locations: store.locations.map((l) => ({ ...l, count: Array.from(store.recs.values()).filter((r) => near(r, l)).length })).sort((a, b) => a.name.localeCompare(b.name)) }),
  'location.save': (p) => {
    const data = { name: String(p.name ?? '').trim() || 'Location', lat: Number(p.lat), lon: Number(p.lon), radius: Math.max(0.01, Number(p.radius ?? 0.2)), private: !!p.private };
    if (p.id === undefined || p.id === null) {
      const id = store.addLocation(data);
      events.emit({ type: 'list.changed', list: 'locations' });
      return { id };
    }
    const hit = store.locations.find((l) => l.id === Number(p.id));
    if (hit) Object.assign(hit, data);
    events.emit({ type: 'list.changed', list: 'locations' });
    return { id: Number(p.id) };
  },
  'location.delete': (p) => {
    const at = store.locations.findIndex((l) => l.id === Number(p.id));
    if (at >= 0) store.locations.splice(at, 1);
    events.emit({ type: 'list.changed', list: 'locations' });
    return { deleted: Number(p.id) };
  },
  'collection.create': (p) => {
    const ids = Array.isArray(p.ids) ? (p.ids as number[]) : [];
    const id = store.addCollection({ name: String(p.name ?? 'Untitled'), kind: String(p.kind ?? 'collection'), ids, settings: (p.settings ?? null) as Dict | null });
    settleCollections();
    return { id };
  },
  'collection.update': (p) => {
    const c = store.collections.find((x) => x.id === Number(p.id));
    if (c && p.settings) c.settings = p.settings as Dict;
    settleCollections();
    return {};
  },
  'collection.removePhotos': (p) => {
    const c = store.collections.find((x) => x.id === Number(p.id));
    if (c) c.ids = c.ids.filter((i) => !(p.ids as number[]).includes(i));
    events.emit({ type: 'list.changed', list: 'collections' });
    return {};
  },
  'collection.reorder': (p) => {
    const c = store.collections.find((x) => x.id === Number(p.id));
    if (c && Array.isArray(p.ids)) c.ids = (p.ids as number[]).slice();
    events.emit({ type: 'list.changed', list: 'collections' });
    return {};
  },
  'output.reveal': async (p) => { await saveOutput(String(p.path ?? '')); return {}; },
  'develop.proofProfiles': () => ({ profiles: [] }),
  'metadata.checkRequired': () => ({ missing: [], total: 0 }),
};

const TABLE: Record<string, Handler> = { ...CORE, ...OUTPUT_COMMANDS };

export function viewOf(path: string): string {
  const photo = /^\/api\/photos\/(\d+)\/(thumb|preview|full|original)/.exec(path);
  if (photo) {
    const r = store.recs.get(Number(photo[1]));
    if (!r) return '';
    return photo[2] === 'thumb' ? r.thumb : photo[2] === 'preview' ? r.preview : originalUrl(r);
  }
  const audio = /^\/api\/output\/audio\?path=(.*)$/.exec(path);
  if (audio) return store.audio.get(decodeURIComponent(audio[1]))?.url ?? '';
  const out = /^\/api\/output\/fs\/(.*)$/.exec(path);
  if (out) return outputUrl(out[1].split('/').map(decodeURIComponent).join('/'));
  return path;
}

const originals = new Map<number, string>();

function originalUrl(r: Rec): string {
  let u = originals.get(r.id);
  if (!u) {
    u = URL.createObjectURL(new Blob([r.bytes as BlobPart], { type: r.mime }));
    originals.set(r.id, u);
  }
  return u;
}

export const engine = {
  url: viewOf,
  async run(id: string, params: Dict): Promise<unknown> {
    const h = TABLE[id];
    if (!h) throw new EngineMiss(`${id} is part of the desktop app and is not in this demo`);
    return h(params);
  },
};

export async function openFiles(files: File[]): Promise<number[]> {
  const made: number[] = [];
  for (const f of files) {
    const bytes = new Uint8Array(await f.arrayBuffer());
    const mime = f.type || (/\.png$/i.test(f.name) ? 'image/png' : /\.webp$/i.test(f.name) ? 'image/webp' : 'image/jpeg');
    let x: ReturnType<typeof readExif> = {};
    try { x = readExif(bytes.buffer as ArrayBuffer); } catch { x = {}; }
    const rec = await store.add({
      file: f.name, bytes, mime, time: x.time ?? null, make: x.make, camera: x.model, lens: x.lens, focal: x.focal ?? null, aperture: x.fnumber ?? null, shutter: x.shutter ?? null,
      iso: x.iso ?? null, gps: x.gps ?? null, alt: x.alt ?? null, title: x.title ?? f.name.replace(/\.[^.]+$/, ''), copyright: x.copyright ?? '', creator: x.creator ?? '',
    });
    made.push(rec.id);
  }
  if (made.length) store.announce(made);
  return made;
}
