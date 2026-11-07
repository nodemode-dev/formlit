import { crc32 } from '../../../demo/src/zip';

export interface ExifRead {
  make?: string;
  model?: string;
  lens?: string;
  iso?: number;
  shutter?: number;
  fnumber?: number;
  focal?: number;
  time?: string;
  gps?: [number, number];
  alt?: number;
  title?: string;
  copyright?: string;
  creator?: string;
}

export interface ExifWrite {
  make?: string;
  model?: string;
  lens?: string;
  iso?: number | null;
  shutter?: number | null;
  fnumber?: number | null;
  focal?: number | null;
  time?: string | null;
  gps?: [number, number] | null;
  alt?: number | null;
  caption?: string;
  copyright?: string;
  creator?: string;
  width: number;
  height: number;
}

type Raw = number[] | string;
const SIZE: Record<number, number> = { 1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8 };

function readIfd(view: DataView, base: number, off: number, le: boolean, out: Map<number, Raw>, depth: number, tag0 = 0): void {
  if (depth > 3 || off <= 0 || base + off + 2 > view.byteLength) return;
  const n = view.getUint16(base + off, le);
  for (let i = 0; i < n; i += 1) {
    const e = base + off + 2 + i * 12;
    if (e + 12 > view.byteLength) return;
    const tag = view.getUint16(e, le), type = view.getUint16(e + 2, le), count = view.getUint32(e + 4, le);
    const bytes = count * (SIZE[type] ?? 1);
    const at = bytes <= 4 ? e + 8 : base + view.getUint32(e + 8, le);
    if (at + bytes > view.byteLength) continue;
    if (tag === 0x8769 || tag === 0x8825) { readIfd(view, base, view.getUint32(e + 8, le), le, out, depth + 1, tag === 0x8825 ? 0x10000 : 0); continue; }
    const key = tag + tag0;
    if (type === 2) {
      let s = '';
      for (let k = 0; k < count; k += 1) { const c = view.getUint8(at + k); if (!c) break; s += String.fromCharCode(c); }
      out.set(key, s.trim());
    } else if (type === 3) out.set(key, Array.from({ length: count }, (_v, k) => view.getUint16(at + k * 2, le)));
    else if (type === 4) out.set(key, Array.from({ length: count }, (_v, k) => view.getUint32(at + k * 4, le)));
    else if (type === 5) out.set(key, Array.from({ length: count }, (_v, k) => view.getUint32(at + k * 8, le) / (view.getUint32(at + k * 8 + 4, le) || 1)));
    else if (type === 1 || type === 7) out.set(key, Array.from({ length: count }, (_v, k) => view.getUint8(at + k)));
  }
}

export function readExif(buf: ArrayBuffer): ExifRead {
  const out: ExifRead = {};
  try {
    const view = new DataView(buf);
    if (view.getUint16(0) !== 0xffd8) return out;
    let o = 2;
    while (o + 4 < view.byteLength && view.getUint8(o) === 0xff) {
      const marker = view.getUint8(o + 1), len = view.getUint16(o + 2);
      if (marker === 0xe1 && view.getUint32(o + 4) === 0x45786966) {
        const base = o + 10;
        const le = view.getUint16(base) === 0x4949;
        const map = new Map<number, Raw>();
        readIfd(view, base, view.getUint32(base + 4, le), le, map, 0);
        const num = (t: number): number | undefined => { const v = map.get(t); return Array.isArray(v) ? v[0] : undefined; };
        const str = (t: number): string | undefined => { const v = map.get(t); return typeof v === 'string' && v ? v : undefined; };
        out.make = str(0x010f);
        out.model = str(0x0110);
        out.lens = str(0xa434);
        out.iso = num(0x8827);
        out.shutter = num(0x829a);
        out.fnumber = num(0x829d);
        out.focal = num(0x920a);
        out.time = str(0x9003)?.replace(/^(\d{4}):(\d\d):(\d\d) /, '$1-$2-$3T');
        out.title = str(0x010e);
        out.copyright = str(0x8298);
        out.creator = str(0x013b);
        const la = map.get(0x10002), lo = map.get(0x10004);
        if (Array.isArray(la) && Array.isArray(lo) && la.length >= 3 && lo.length >= 3) {
          const sa = map.get(0x10001) === 'S' ? -1 : 1, so = map.get(0x10003) === 'W' ? -1 : 1;
          out.gps = [sa * (la[0] + la[1] / 60 + la[2] / 3600), so * (lo[0] + lo[1] / 60 + lo[2] / 3600)];
          const alt = num(0x10006);
          if (alt !== undefined) out.alt = (map.get(0x10005) as number[] | undefined)?.[0] === 1 ? -alt : alt;
        }
        break;
      }
      if (marker === 0xda) break;
      o += 2 + len;
    }
  } catch { return out; }
  return out;
}

interface Entry { tag: number; type: 1 | 2 | 3 | 4 | 5 | 7; v: number[] | string }

const rational = (x: number): [number, number] => {
  if (x > 0 && x < 1) return [1, Math.round(1 / x)];
  const den = x < 100 ? 1000 : 10;
  return [Math.round(x * den), den];
};

function payload(e: Entry): Uint8Array {
  if (typeof e.v === 'string') {
    const b = new Uint8Array(e.v.length + 1);
    for (let i = 0; i < e.v.length; i += 1) b[i] = e.v.charCodeAt(i) & 0xff;
    return b;
  }
  const v = e.v;
  const dv = new DataView(new ArrayBuffer(v.length * (SIZE[e.type] ?? 1)));
  v.forEach((x, i) => {
    if (e.type === 3) dv.setUint16(i * 2, x, true);
    else if (e.type === 4) dv.setUint32(i * 4, x, true);
    else dv.setUint8(i, x);
  });
  return new Uint8Array(dv.buffer);
}

function ratPayload(parts: Array<[number, number]>): Uint8Array {
  const dv = new DataView(new ArrayBuffer(parts.length * 8));
  parts.forEach(([n, d], i) => { dv.setUint32(i * 8, n, true); dv.setUint32(i * 8 + 4, d, true); });
  return new Uint8Array(dv.buffer);
}

interface Item { tag: number; type: number; count: number; data: Uint8Array }

function item(e: Entry): Item {
  const data = payload(e);
  return { tag: e.tag, type: e.type, count: e.type === 2 ? data.length : data.length / (SIZE[e.type] ?? 1), data };
}

function rat(tag: number, parts: Array<[number, number]>): Item {
  return { tag, type: 5, count: parts.length, data: ratPayload(parts) };
}

function build(items: Item[], at: number): Uint8Array {
  const sorted = items.slice().sort((a, b) => a.tag - b.tag);
  const head = 2 + sorted.length * 12 + 4;
  let tail = 0;
  const offs = sorted.map((it) => { if (it.data.length <= 4) return -1; const o = at + head + tail; tail += it.data.length + (it.data.length % 2); return o; });
  const out = new Uint8Array(head + tail);
  const dv = new DataView(out.buffer);
  dv.setUint16(0, sorted.length, true);
  sorted.forEach((it, i) => {
    const p = 2 + i * 12;
    dv.setUint16(p, it.tag, true);
    dv.setUint16(p + 2, it.type, true);
    dv.setUint32(p + 4, it.count, true);
    if (offs[i] < 0) out.set(it.data, p + 8);
    else { dv.setUint32(p + 8, offs[i], true); out.set(it.data, offs[i] - at); }
  });
  return out;
}

function dms(v: number): Array<[number, number]> {
  const a = Math.abs(v);
  const total = Math.round(a * 3600 * 10000);
  const d = Math.floor(total / 36000000), m = Math.floor((total - d * 36000000) / 600000);
  return [[d, 1], [m, 1], [total - d * 36000000 - m * 600000, 10000]];
}

export function exifPayload(r: ExifWrite): Uint8Array {
  const ifd0: Item[] = [item({ tag: 0x0131, type: 2, v: 'formlit' }), item({ tag: 0x0112, type: 3, v: [1] })];
  if (r.make) ifd0.push(item({ tag: 0x010f, type: 2, v: r.make }));
  if (r.model) ifd0.push(item({ tag: 0x0110, type: 2, v: r.model }));
  if (r.caption) ifd0.push(item({ tag: 0x010e, type: 2, v: r.caption }));
  if (r.creator) ifd0.push(item({ tag: 0x013b, type: 2, v: r.creator }));
  if (r.copyright) ifd0.push(item({ tag: 0x8298, type: 2, v: r.copyright }));
  const sub: Item[] = [item({ tag: 0xa002, type: 4, v: [r.width] }), item({ tag: 0xa003, type: 4, v: [r.height] })];
  if (r.time) sub.push(item({ tag: 0x9003, type: 2, v: r.time.slice(0, 19).replace(/^(\d{4})-(\d\d)-(\d\d)T?/, '$1:$2:$3 ').padEnd(19, '0') }));
  if (r.shutter) sub.push(rat(0x829a, [rational(r.shutter)]));
  if (r.fnumber) sub.push(rat(0x829d, [rational(r.fnumber)]));
  if (r.focal) sub.push(rat(0x920a, [rational(r.focal)]));
  if (r.iso) sub.push(item({ tag: 0x8827, type: 3, v: [r.iso] }));
  if (r.lens) sub.push(item({ tag: 0xa434, type: 2, v: r.lens }));
  const gps: Item[] = [];
  if (r.gps) {
    gps.push({ tag: 0, type: 1, count: 4, data: new Uint8Array([2, 3, 0, 0]) });
    gps.push(item({ tag: 1, type: 2, v: r.gps[0] >= 0 ? 'N' : 'S' }), rat(2, dms(r.gps[0])), item({ tag: 3, type: 2, v: r.gps[1] >= 0 ? 'E' : 'W' }), rat(4, dms(r.gps[1])));
    if (r.alt !== null && r.alt !== undefined) gps.push({ tag: 5, type: 1, count: 1, data: new Uint8Array([r.alt >= 0 ? 0 : 1]) }, rat(6, [rational(Math.abs(r.alt))]));
  }
  const ptr = (tag: number): Item => ({ tag, type: 4, count: 1, data: new Uint8Array(4) });
  const withPtrs = (): Item[] => [...ifd0, ptr(0x8769), ...(gps.length ? [ptr(0x8825)] : [])];
  const size0 = build(withPtrs(), 8).length;
  const sizeSub = build(sub, 8 + size0).length;
  const subAt = 8 + size0, gpsAt = subAt + sizeSub;
  const pointed = withPtrs().map((it) => {
    if (it.tag === 0x8769) return { ...it, data: new Uint8Array(new Uint32Array([subAt]).buffer) };
    if (it.tag === 0x8825) return { ...it, data: new Uint8Array(new Uint32Array([gpsAt]).buffer) };
    return it;
  });
  const parts = [build(pointed, 8), build(sub, subAt), ...(gps.length ? [build(gps, gpsAt)] : [])];
  const total = 8 + parts.reduce((t, p) => t + p.length, 0);
  const out = new Uint8Array(6 + total);
  out.set([0x45, 0x78, 0x69, 0x66, 0, 0, 0x49, 0x49, 42, 0, 8, 0, 0, 0]);
  let p = 14;
  for (const part of parts) { out.set(part, p); p += part.length; }
  return out;
}

export function withExifJpeg(jpeg: Uint8Array, exif: Uint8Array): Uint8Array {
  let at = 2;
  while (at + 4 < jpeg.length && jpeg[at] === 0xff && jpeg[at + 1] === 0xe1) at += 2 + ((jpeg[at + 2] << 8) | jpeg[at + 3]);
  const seg = new Uint8Array(4 + exif.length);
  seg.set([0xff, 0xe1, (exif.length + 2) >> 8, (exif.length + 2) & 0xff]);
  seg.set(exif, 4);
  const out = new Uint8Array(jpeg.length - (at - 2) + seg.length);
  out.set(jpeg.subarray(0, 2));
  out.set(seg, 2);
  out.set(jpeg.subarray(at), 2 + seg.length);
  return out;
}

export function stripExifJpeg(jpeg: Uint8Array): Uint8Array {
  const keep: Uint8Array[] = [jpeg.subarray(0, 2)];
  let at = 2;
  while (at + 4 < jpeg.length && jpeg[at] === 0xff && jpeg[at + 1] !== 0xda) {
    const len = 2 + ((jpeg[at + 2] << 8) | jpeg[at + 3]);
    if (jpeg[at + 1] !== 0xe1) keep.push(jpeg.subarray(at, at + len));
    at += len;
  }
  keep.push(jpeg.subarray(at));
  const out = new Uint8Array(keep.reduce((t, k) => t + k.length, 0));
  let p = 0;
  for (const k of keep) { out.set(k, p); p += k.length; }
  return out;
}

export function withExifPng(png: Uint8Array, exif: Uint8Array): Uint8Array {
  const body = exif.subarray(6);
  const chunk = new Uint8Array(12 + body.length);
  const dv = new DataView(chunk.buffer);
  dv.setUint32(0, body.length);
  chunk.set([0x65, 0x58, 0x49, 0x66], 4);
  chunk.set(body, 8);
  dv.setUint32(8 + body.length, crc32(chunk.subarray(4, 8 + body.length)));
  const at = 8 + 25;
  const out = new Uint8Array(png.length + chunk.length);
  out.set(png.subarray(0, at));
  out.set(chunk, at);
  out.set(png.subarray(at), at + chunk.length);
  return out;
}

export function withExifWebp(webp: Uint8Array, exif: Uint8Array, w: number, h: number): Uint8Array {
  const body = exif.subarray(6);
  const first = String.fromCharCode(...webp.subarray(12, 16));
  if (first === 'VP8X') return webp;
  const image = webp.subarray(12);
  const vp8x = new Uint8Array(18);
  const vdv = new DataView(vp8x.buffer);
  vp8x.set([0x56, 0x50, 0x38, 0x58]);
  vdv.setUint32(4, 10, true);
  vp8x[8] = 0x08;
  vp8x[12] = (w - 1) & 0xff; vp8x[13] = ((w - 1) >> 8) & 0xff; vp8x[14] = ((w - 1) >> 16) & 0xff;
  vp8x[15] = (h - 1) & 0xff; vp8x[16] = ((h - 1) >> 8) & 0xff; vp8x[17] = ((h - 1) >> 16) & 0xff;
  const pad = body.length % 2;
  const tail = new Uint8Array(8 + body.length + pad);
  tail.set([0x45, 0x58, 0x49, 0x46]);
  new DataView(tail.buffer).setUint32(4, body.length, true);
  tail.set(body, 8);
  const total = 4 + vp8x.length + image.length + tail.length;
  const out = new Uint8Array(8 + total);
  out.set([0x52, 0x49, 0x46, 0x46]);
  new DataView(out.buffer).setUint32(4, total, true);
  out.set([0x57, 0x45, 0x42, 0x50], 8);
  out.set(vp8x, 12);
  out.set(image, 12 + vp8x.length);
  out.set(tail, 12 + vp8x.length + image.length);
  return out;
}
