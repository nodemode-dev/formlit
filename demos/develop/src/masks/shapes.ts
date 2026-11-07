import { gauss, guided, morph, smooth } from './filters';
import { toPixel, type Geo } from './geo';
import { BITMAP_KINDS, type Shape } from './types';

export interface Bitmap { w: number; h: number; data: Float32Array }
export const BITMAPS = new Map<string, Bitmap>();

export interface Base { w: number; h: number; rgba: Uint8ClampedArray; luma: Float32Array; lab: Float32Array | null }

const infos = new WeakMap<Uint8ClampedArray, Base>();
const lin = new Float32Array(256);
for (let i = 0; i < 256; i += 1) { const c = i / 255; lin[i] = c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; }

export function baseOf(rgba: Uint8ClampedArray, w: number, h: number): Base {
  const hit = infos.get(rgba);
  if (hit) return hit;
  const luma = new Float32Array(w * h);
  for (let i = 0, j = 0; i < luma.length; i += 1, j += 4) luma[i] = (0.2126 * rgba[j] + 0.7152 * rgba[j + 1] + 0.0722 * rgba[j + 2]) / 255;
  const info: Base = { w, h, rgba, luma, lab: null };
  infos.set(rgba, info);
  return info;
}

export function labOf(b: Base): Float32Array {
  if (b.lab) return b.lab;
  const n = b.w * b.h;
  const out = new Float32Array(n * 3);
  for (let i = 0, j = 0; i < n; i += 1, j += 4) {
    const r = lin[b.rgba[j]], g = lin[b.rgba[j + 1]], bl = lin[b.rgba[j + 2]];
    const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * bl);
    const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * bl);
    const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * bl);
    out[i * 3] = 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s;
    out[i * 3 + 1] = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s;
    out[i * 3 + 2] = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s;
  }
  b.lab = out;
  return out;
}

export function sampleLab(b: Base, nx: number, ny: number, radius = 2): [number, number, number] {
  const lab = labOf(b);
  const cx = Math.round(nx * (b.w - 1)), cy = Math.round(ny * (b.h - 1));
  const acc = [0, 0, 0];
  let n = 0;
  for (let y = Math.max(0, cy - radius); y <= Math.min(b.h - 1, cy + radius); y += 1) for (let x = Math.max(0, cx - radius); x <= Math.min(b.w - 1, cx + radius); x += 1) {
    const j = (y * b.w + x) * 3;
    acc[0] += lab[j]; acc[1] += lab[j + 1]; acc[2] += lab[j + 2];
    n += 1;
  }
  return [acc[0] / n, acc[1] / n, acc[2] / n];
}

const num = (v: unknown, d: number): number => (typeof v === 'number' && Number.isFinite(v) ? v : d);
const pt = (v: unknown, d: [number, number]): [number, number] => (Array.isArray(v) && v.length >= 2 ? [Number(v[0]), Number(v[1])] : d);

function linear(s: Shape, g: Geo): Float32Array {
  const out = new Float32Array(g.w * g.h);
  const a = pt(s.start, [0.5, 0.2]), b = pt(s.end, [0.5, 0.6]);
  const kx = g.ow / g.long, ky = g.oh / g.long;
  const dx = (b[0] - a[0]) * kx, dy = (b[1] - a[1]) * ky;
  const n2 = dx * dx + dy * dy;
  if (n2 < 1e-14) return out;
  for (let y = 0; y < g.h; y += 1) for (let x = 0; x < g.w; x += 1) {
    const nx = g.ax * (x + 0.5) + g.ay * (y + 0.5) + g.ac, ny = g.bx * (x + 0.5) + g.by * (y + 0.5) + g.bc;
    out[y * g.w + x] = 1 - smooth(((nx - a[0]) * kx * dx + (ny - a[1]) * ky * dy) / n2);
  }
  return out;
}

function radial(s: Shape, g: Geo): Float32Array {
  const out = new Float32Array(g.w * g.h);
  const c = pt(s.center, [0.5, 0.5]);
  const rx = Math.max(num(s.rx, 0.2), 1e-6), ry = Math.max(num(s.ry, 0.15), 1e-6);
  const t = (num(s.angle, 0) * Math.PI) / 180;
  const ct = Math.cos(t), st = Math.sin(t);
  const feather = Math.min(Math.max(num(s.feather, 50), 0), 100) / 100;
  const kx = g.ow / g.long, ky = g.oh / g.long;
  const aa = 1 / (g.ppl * Math.min(rx, ry));
  let lo = 1 - feather, hi = 1;
  if (hi - lo < aa) { lo = 1 - 0.5 * aa; hi = 1 + 0.5 * aa; }
  for (let y = 0; y < g.h; y += 1) for (let x = 0; x < g.w; x += 1) {
    const nx = g.ax * (x + 0.5) + g.ay * (y + 0.5) + g.ac, ny = g.bx * (x + 0.5) + g.by * (y + 0.5) + g.bc;
    const dx = (nx - c[0]) * kx, dy = (ny - c[1]) * ky;
    const u = (ct * dx + st * dy) / rx, v = (-st * dx + ct * dy) / ry;
    const v2 = smooth((hi - Math.sqrt(u * u + v * v)) / (hi - lo));
    out[y * g.w + x] = s.invert ? 1 - v2 : v2;
  }
  return out;
}

interface Stroke { points: Array<[number, number]>; size?: number; feather?: number; flow?: number; density?: number; erase?: boolean }

const brushMemo = new Map<string, Float32Array>();

function brush(s: Shape, g: Geo): Float32Array {
  const strokes = (Array.isArray(s.strokes) ? s.strokes : []) as Stroke[];
  const key = `${g.w}x${g.h}|${g.ax},${g.ay},${g.ac},${g.bx},${g.by},${g.bc}|${JSON.stringify(strokes)}`;
  const hit = brushMemo.get(key);
  if (hit) return hit;
  const out = new Float32Array(g.w * g.h);
  for (const st of strokes) {
    if (!Array.isArray(st.points) || !st.points.length) continue;
    const r = Math.max(num(st.size, 0.03) * g.ppl, 1.5);
    const feather = Math.min(Math.max(num(st.feather, 50), 0), 100) / 100;
    const flow = Math.min(Math.max(num(st.flow, 100), 1), 100) / 100;
    const density = Math.min(Math.max(num(st.density, 100), 0), 100) / 100;
    const core = r * (1 - feather);
    const px = st.points.map((p) => toPixel(g, p[0], p[1]));
    const buf = new Float32Array(g.w * g.h);
    let minX = g.w, minY = g.h, maxX = 0, maxY = 0;
    const dab = (cx: number, cy: number, a: number): void => {
      const x0 = Math.max(0, Math.floor(cx - r)), x1 = Math.min(g.w - 1, Math.ceil(cx + r));
      const y0 = Math.max(0, Math.floor(cy - r)), y1 = Math.min(g.h - 1, Math.ceil(cy + r));
      if (x0 < minX) minX = x0;
      if (y0 < minY) minY = y0;
      if (x1 > maxX) maxX = x1;
      if (y1 > maxY) maxY = y1;
      const hi = Math.max(r, core + 0.75);
      for (let y = y0; y <= y1; y += 1) for (let x = x0; x <= x1; x += 1) {
        const d = Math.hypot(x + 0.5 - cx, y + 0.5 - cy);
        if (d >= hi) continue;
        const p = d <= core ? 1 : smooth((hi - d) / (hi - core));
        const i = y * g.w + x;
        if (p > buf[i]) buf[i] += (p - buf[i]) * a;
      }
    };
    const step = Math.max(r * 0.14, 1);
    dab(px[0][0], px[0][1], flow);
    for (let i = 1; i < px.length; i += 1) {
      const [ax, ay] = px[i - 1], [bx, by] = px[i];
      const len = Math.hypot(bx - ax, by - ay);
      const n = Math.max(1, Math.ceil(len / step));
      const a = 1 - (1 - flow) ** (len / n / (2 * r));
      for (let k = 1; k <= n; k += 1) dab(ax + ((bx - ax) * k) / n, ay + ((by - ay) * k) / n, Math.max(a, 0.02));
    }
    for (let y = minY; y <= maxY; y += 1) for (let x = minX; x <= maxX; x += 1) {
      const i = y * g.w + x;
      const b = buf[i] * density;
      if (b <= 0) continue;
      out[i] = st.erase ? out[i] * (1 - b) : out[i] + (1 - out[i]) * b;
    }
  }
  brushMemo.set(key, out);
  if (brushMemo.size > 8) brushMemo.delete(brushMemo.keys().next().value as string);
  return out;
}

function band(v: number, lo: number, hi: number, lf: number, hf: number): number {
  const a = lf > 1e-6 ? smooth((v - lo) / lf + 1) : v >= lo ? 1 : 0;
  const b = hf > 1e-6 ? smooth((hi - v) / hf + 1) : v <= hi ? 1 : 0;
  return Math.min(a, b);
}

function luminance(s: Shape, base: Base): Float32Array {
  const lo = Math.min(num(s.lo, 0.5), num(s.hi, 1)), hi = Math.max(num(s.lo, 0.5), num(s.hi, 1));
  const lf = num(s.loFeather, 0.1), hf = num(s.hiFeather, 0.1);
  const out = new Float32Array(base.w * base.h);
  for (let i = 0; i < out.length; i += 1) out[i] = band(base.luma[i], lo, hi, lf, hf);
  return out;
}

function colour(s: Shape, base: Base): Float32Array {
  const samples = (Array.isArray(s.samples) ? s.samples : []) as number[][];
  const out = new Float32Array(base.w * base.h);
  if (!samples.length) return out;
  const refine = Math.min(Math.max(num(s.refine, 50), 0), 100);
  const tol = 0.04 * 2 ** ((2 * (refine - 50)) / 50);
  const inner = 0.35 * tol;
  const lab = labOf(base);
  for (let i = 0; i < out.length; i += 1) {
    let best = Infinity;
    for (const sm of samples) {
      const dl = (lab[i * 3] - sm[0]) * 0.5, da = lab[i * 3 + 1] - sm[1], db = lab[i * 3 + 2] - sm[2];
      const d2 = dl * dl + da * da + db * db;
      if (d2 < best) best = d2;
    }
    out[i] = 1 - smooth((Math.sqrt(best) - inner) / (tol - inner));
  }
  return out;
}

function bitmapCov(s: Shape, g: Geo): Float32Array {
  const out = new Float32Array(g.w * g.h);
  const bm = BITMAPS.get(String(s.bitmap ?? ''));
  if (!bm) return out;
  for (let y = 0; y < g.h; y += 1) for (let x = 0; x < g.w; x += 1) {
    const nx = g.ax * (x + 0.5) + g.ay * (y + 0.5) + g.ac, ny = g.bx * (x + 0.5) + g.by * (y + 0.5) + g.bc;
    if (nx < 0 || nx > 1 || ny < 0 || ny > 1) continue;
    const fx = Math.min(bm.w - 1, Math.max(0, nx * bm.w - 0.5)), fy = Math.min(bm.h - 1, Math.max(0, ny * bm.h - 0.5));
    const ix = fx | 0, iy = fy | 0, tx = fx - ix, ty = fy - iy;
    const ix1 = Math.min(bm.w - 1, ix + 1), iy1 = Math.min(bm.h - 1, iy + 1);
    const top = bm.data[iy * bm.w + ix] * (1 - tx) + bm.data[iy * bm.w + ix1] * tx;
    const bot = bm.data[iy1 * bm.w + ix] * (1 - tx) + bm.data[iy1 * bm.w + ix1] * tx;
    out[y * g.w + x] = top * (1 - ty) + bot * ty;
  }
  return s.kind === 'background' ? out.map((v) => 1 - v) : out;
}

export function edges(cov: Float32Array, s: Shape, g: Geo, base: Base): Float32Array {
  const refine = Math.min(Math.max(num(s.refine, 0), 0), 100) / 100;
  const shift = Math.min(Math.max(num(s.shift, 0), -100), 100);
  const feather = Math.min(Math.max(num(s.feather, 0), 0), 100);
  let cur = cov;
  if (refine > 0) {
    const r = Math.max(2, Math.round(0.014 * refine * g.ppl));
    const eps = 6e-2 * (5e-3) ** refine;
    let snapped = cur;
    for (let i = 0; i < 2; i += 1) snapped = guided(base.luma, snapped, g.w, g.h, r, eps);
    const k = refine;
    const mixed = new Float32Array(cur.length);
    for (let i = 0; i < mixed.length; i += 1) mixed[i] = cur[i] + (snapped[i] - cur[i]) * k;
    cur = mixed;
  }
  const grow = (Math.abs(shift) / 100) * 0.02 * g.ppl;
  if (grow >= 0.75) cur = morph(cur, g.w, g.h, Math.round(grow), shift > 0);
  const sigma = (feather / 100) * 0.03 * g.ppl;
  if (sigma >= 0.3) cur = gauss(cur, g.w, g.h, sigma);
  return cur;
}

export function coverage(s: Shape, g: Geo, base: Base): Float32Array {
  switch (s.kind) {
    case 'linear': return linear(s, g);
    case 'radial': return radial(s, g);
    case 'brush': return brush(s, g);
    case 'luminanceRange': return luminance(s, base);
    case 'colorRange': return colour(s, base);
    default:
      if (BITMAP_KINDS.has(s.kind)) return edges(bitmapCov(s, g), s, g, base);
      return new Float32Array(g.w * g.h);
  }
}
