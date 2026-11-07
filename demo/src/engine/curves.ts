import { MID, srgbDecode, srgbEncode } from './colour';

export const VMIN = -20;
export const VMAX = 12;
export const NV = 4096;
export const NE = 4096;
export const NP = 1024;
export const PIVOT = 0.4636;
export const SAT_SLOPE = [0.5, 2.5];
const REGION_GAIN = [0.1, 0.14, 0.14, 0.1];
const REGION_MIN = 0.12;

export function monotoneSlopes(x: number[], y: number[]): number[] {
  const n = x.length;
  if (n < 2) return new Array<number>(n).fill(0);
  const d: number[] = [];
  for (let k = 0; k < n - 1; k += 1) d.push((y[k + 1] - y[k]) / Math.max(x[k + 1] - x[k], 1e-12));
  const m = new Array<number>(n).fill(0);
  m[0] = d[0];
  m[n - 1] = d[n - 2];
  for (let k = 1; k < n - 1; k += 1) m[k] = d[k - 1] * d[k] <= 0 ? 0 : (d[k - 1] + d[k]) / 2;
  for (let k = 0; k < n - 1; k += 1) {
    if (d[k] === 0) { m[k] = 0; m[k + 1] = 0; continue; }
    const a = m[k] / d[k], b = m[k + 1] / d[k];
    const s = a * a + b * b;
    if (s > 9) {
      const t = 3 / Math.sqrt(s);
      m[k] = t * a * d[k];
      m[k + 1] = t * b * d[k];
    }
  }
  return m;
}

export function hermite(x: number[], y: number[], m: number[], tIn: number): number {
  const n = x.length;
  const t = Math.min(Math.max(tIn, x[0]), x[n - 1]);
  let k = 0;
  while (k < n - 2 && t >= x[k + 1]) k += 1;
  const h = Math.max(x[k + 1] - x[k], 1e-12);
  const s = (t - x[k]) / h, s2 = s * s, s3 = s2 * s;
  return (2 * s3 - 3 * s2 + 1) * y[k] + (s3 - 2 * s2 + s) * h * m[k] + (-2 * s3 + 3 * s2) * y[k + 1] + (s3 - s2) * h * m[k + 1];
}

function cleanPoints(points: unknown): Array<[number, number]> | null {
  if (!Array.isArray(points)) return null;
  const p = points
    .filter((q) => Array.isArray(q) && Number.isFinite(q[0]) && Number.isFinite(q[1]))
    .map((q) => [Math.min(1, Math.max(0, q[0] as number)), Math.min(1, Math.max(0, q[1] as number))] as [number, number])
    .sort((a, b) => a[0] - b[0]);
  const kept = p.filter((q, k) => k === 0 || q[0] - p[k - 1][0] > 1e-6);
  return kept.length >= 2 ? kept : null;
}

export function pointLut(points: unknown, n = NE): Float32Array | null {
  const p = cleanPoints(points);
  if (!p || p.every((q) => Math.abs(q[0] - q[1]) <= 1e-6)) return null;
  const xs = p.map((q) => q[0]), ys = p.map((q) => q[1]);
  const m = monotoneSlopes(xs, ys);
  const out = new Float32Array(n);
  for (let i = 0; i < n; i += 1) out[i] = Math.min(1, Math.max(0, hermite(xs, ys, m, i / (n - 1))));
  return out;
}

function num(c: Record<string, unknown>, k: string, d: number): number {
  const v = c[k];
  return typeof v === 'number' && Number.isFinite(v) ? v : d;
}

export function parametricValues(c: Record<string, unknown>): number[] {
  const s1 = Math.min(Math.max(num(c, 'splitShadows', 25), 10), 70) / 100;
  let s2 = Math.min(Math.max(num(c, 'splitMid', 50), 20), 80) / 100;
  let s3 = Math.min(Math.max(num(c, 'splitHighlights', 75), 30), 90) / 100;
  s2 = Math.max(s2, s1 + 0.02);
  s3 = Math.max(s3, s2 + 0.02);
  return [num(c, 'shadows', 0) / 100, num(c, 'darks', 0) / 100, num(c, 'lights', 0) / 100, num(c, 'highlights', 0) / 100, s1, s2, Math.min(s3, 0.98)];
}

export function parametricLut(c: Record<string, unknown>): { y: Float32Array; d: Float32Array } | null {
  const v = parametricValues(c || {});
  if (!v.slice(0, 4).some((x) => x !== 0)) return null;
  const [sh, dk, lt, hl, s1, s2, s3] = v;
  const xs = [0, s1 / 2, (s1 + s2) / 2, (s2 + s3) / 2, (s3 + 1) / 2, 1];
  const ys = [0, ...[1, 2, 3, 4].map((k) => xs[k] + [sh, dk, lt, hl][k - 1] * REGION_GAIN[k - 1]), 1];
  for (let k = 1; k < 5; k += 1) ys[k] = Math.min(Math.max(ys[k], ys[k - 1] + REGION_MIN * (xs[k] - xs[k - 1])), 1 - REGION_MIN * (1 - xs[k]));
  const m = monotoneSlopes(xs, ys);
  const y = new Float32Array(NP + 1), d = new Float32Array(NP + 1);
  for (let i = 0; i <= NP; i += 1) y[i] = Math.min(1, Math.max(0, hermite(xs, ys, m, i / NP)));
  for (let i = 0; i <= NP; i += 1) {
    const a = Math.max(0, i - 1), b = Math.min(NP, i + 1);
    d[i] = Math.max(0, ((y[b] - y[a]) / ((b - a) / NP)));
  }
  return { y, d };
}

export function lut1(t: number, lut: Float32Array): number {
  const n = lut.length - 1;
  const c = t < 0 ? 0 : t > 1 ? 1 : t;
  const f = c * n;
  let i = f | 0;
  if (i > n - 1) i = n - 1;
  const lo = lut[i];
  return lo + (lut[i + 1] - lo) * (f - i);
}

export function encLut(): Float32Array {
  const o = new Float32Array(NE);
  for (let i = 0; i < NE; i += 1) { const u = i / (NE - 1); o[i] = srgbEncode(u ** 4); }
  return o;
}

export function decLut(): Float32Array {
  const o = new Float32Array(NE);
  for (let i = 0; i < NE; i += 1) o[i] = srgbDecode(i / (NE - 1));
  return o;
}

export function toneLuts(): { e: Float32Array; g: Float32Array } {
  const e = new Float32Array(NV), g = new Float32Array(NV);
  for (let i = 0; i < NV; i += 1) {
    const v = VMIN + (i / (NV - 1)) * (VMAX - VMIN);
    const lin = MID * 2 ** v;
    e[i] = srgbEncode(lin);
    g[i] = lin < 1 ? 1 : 0;
  }
  return { e, g };
}

export function lutV(v: number, lut: Float32Array): number {
  return lut1((v - VMIN) / (VMAX - VMIN), lut);
}

export function vAt(eLut: Float32Array, e: number): number {
  let lo = 0, hi = eLut.length;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (eLut[mid] < e) lo = mid + 1; else hi = mid; }
  const i = Math.min(Math.max(lo, 1), eLut.length - 1);
  const a = eLut[i - 1], b = eLut[i];
  const f = b <= a ? 0 : (e - a) / (b - a);
  return VMIN + (i - 1 + f) * (VMAX - VMIN) / (eLut.length - 1);
}

export function composite(master: Float32Array | null, chans: Array<Float32Array | null>): Float32Array[] | null {
  if (!master && chans.every((c) => !c)) return null;
  const e = new Float32Array(NE);
  for (let i = 0; i < NE; i += 1) {
    const u = i / (NE - 1);
    let v = srgbEncode(u ** 4);
    if (master) v = lut1(v, master);
    e[i] = v;
  }
  return chans.map((c) => {
    const out = new Float32Array(NE);
    for (let i = 0; i < NE; i += 1) out[i] = srgbDecode(c ? lut1(e[i], c) : e[i]);
    return out;
  });
}
