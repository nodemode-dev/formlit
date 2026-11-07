import { srgbEncode } from '../engine/colour';

export interface SceneInfo { id: string; name: string; make: string; model: string; lens: string; iso: number; shutter: string; fnum: number; focal: number; time: string; keywords: string[] }

export const SCENES: SceneInfo[] = [
  { id: 'coast', name: 'Coast at dusk', make: 'Procedural', model: 'Scene 01', lens: '24 mm f/4', iso: 100, shutter: '1/60', fnum: 8, focal: 24, time: '2026-06-14T20:41:00', keywords: ['sea', 'dusk', 'rocks'] },
  { id: 'ridges', name: 'Ridge lines', make: 'Procedural', model: 'Scene 02', lens: '70 mm f/4', iso: 200, shutter: '1/250', fnum: 8, focal: 70, time: '2026-07-02T08:12:00', keywords: ['mountains', 'haze'] },
  { id: 'forest', name: 'Forest light', make: 'Procedural', model: 'Scene 03', lens: '35 mm f/2', iso: 800, shutter: '1/125', fnum: 4, focal: 35, time: '2026-05-21T17:03:00', keywords: ['forest', 'light'] },
  { id: 'city', name: 'City after dark', make: 'Procedural', model: 'Scene 04', lens: '50 mm f/1.4', iso: 3200, shutter: '1/60', fnum: 1.8, focal: 50, time: '2026-01-09T22:15:00', keywords: ['city', 'night'] },
  { id: 'dunes', name: 'Dune ridges', make: 'Procedural', model: 'Scene 05', lens: '85 mm f/4', iso: 100, shutter: '1/500', fnum: 11, focal: 85, time: '2026-03-30T16:48:00', keywords: ['desert', 'sand'] },
  { id: 'meadow', name: 'Summer meadow', make: 'Procedural', model: 'Scene 06', lens: '28 mm f/4', iso: 100, shutter: '1/400', fnum: 8, focal: 28, time: '2026-08-11T13:26:00', keywords: ['meadow', 'flowers'] },
];

function hash(ix: number, iy: number, seed: number): number {
  let x = (Math.imul(ix, 374761393) + Math.imul(iy, 668265263) + Math.imul(seed, 2147483647)) | 0;
  x = Math.imul(x ^ (x >>> 13), 1274126177);
  x ^= x >>> 16;
  return (x & 0xffff) / 65535;
}

function vnoise(x: number, y: number, seed: number): number {
  const ix = Math.floor(x), iy = Math.floor(y);
  let tx = x - ix, ty = y - iy;
  tx = tx * tx * (3 - 2 * tx);
  ty = ty * ty * (3 - 2 * ty);
  const a = hash(ix, iy, seed), b = hash(ix + 1, iy, seed), c = hash(ix, iy + 1, seed), d = hash(ix + 1, iy + 1, seed);
  const t = a + (b - a) * tx;
  return t + (c + (d - c) * tx - t) * ty;
}

function fbm(x: number, y: number, oct: number, seed: number): number {
  let a = 0.5, s = 0, f = 1;
  for (let i = 0; i < oct; i += 1) { s += a * vnoise(x * f, y * f, seed + i * 17); f *= 2.03; a *= 0.5; }
  return s;
}

const mix = (a: number, b: number, t: number): number => a + (b - a) * t;
const sm = (a: number, b: number, x: number): number => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
type V3 = [number, number, number];
const mix3 = (a: V3, b: V3, t: number): V3 => [mix(a[0], b[0], t), mix(a[1], b[1], t), mix(a[2], b[2], t)];
const mul3 = (a: V3, k: number): V3 => [a[0] * k, a[1] * k, a[2] * k];
const add3 = (a: V3, b: V3): V3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];

type Fn = (u: number, v: number, aspect: number) => V3;

const coast: Fn = (u, v, asp) => {
  const hor = 0.52, sx = 0.68;
  const x = u * asp;
  if (v < hor) {
    const t = v / hor;
    let col = mix3([0.05, 0.07, 0.22], [1.15, 0.42, 0.14], t ** 1.6);
    const c = fbm(x * 2.4, v * 5.5, 5, 3);
    const cloud = sm(0.42, 0.72, c) * sm(0.0, 0.25, v) * (1 - sm(0.42, 0.52, v));
    const lit = [1.6, 0.62, 0.3] as V3;
    col = mix3(col, add3(mul3(lit, 0.9 + c), [0.1, 0.05, 0.1]), cloud * 0.8);
    const d = Math.hypot((u - sx) * asp, (v - hor + 0.02) * 1.4);
    col = add3(col, mul3([2.2, 1.2, 0.55], Math.exp(-d * 9) * 0.9 + Math.exp(-d * 45) * 1.6));
    return col;
  }
  const t = (v - hor) / (1 - hor);
  const depth = t ** 0.8;
  const ripple = fbm(x * (20 + 60 * depth), v * 140, 3, 9);
  let col = mix3([0.45, 0.22, 0.2], [0.02, 0.07, 0.11], Math.min(1, t * 2.2));
  const streak = Math.exp(-((u - sx) ** 2) / (0.01 + 0.05 * depth)) * (0.5 + ripple) * (1 - sm(0.35, 0.9, t));
  col = add3(col, mul3([1.8, 0.8, 0.35], streak * 1.4));
  col = mul3(col, 0.75 + ripple * 0.5);
  const edge = 0.74 - 0.14 * fbm(x * 2.2, 1.7, 5, 21) - 0.04 * u;
  if (v > edge) {
    const tex = fbm(x * 18, v * 18, 5, 33);
    const rim = Math.exp(-(v - edge) * 70);
    const rock = mix3([0.015, 0.012, 0.012], [0.07, 0.05, 0.045], tex);
    return add3(rock, mul3([0.5, 0.2, 0.08], rim * 0.35 * tex));
  }
  return col;
};

const ridges: Fn = (u, v, asp) => {
  const x = u * asp;
  let col = mix3([0.18, 0.34, 0.62], [0.95, 0.78, 0.6], Math.min(1, v * 1.5) ** 1.3);
  const sun = Math.exp(-Math.hypot((u - 0.3) * asp, v - 0.28) * 5);
  col = add3(col, mul3([1.1, 0.7, 0.35], sun * 0.6));
  const layers = 6;
  for (let i = 0; i < layers; i += 1) {
    const f = i / (layers - 1);
    const base = 0.38 + f * 0.42;
    const h = base - 0.2 * fbm(x * (1.6 + f * 1.4) + i * 5, i * 3.3, 6, 40 + i);
    if (v > h) {
      const haze = 1 - f;
      const body = mix3([0.05, 0.1, 0.08], [0.02, 0.05, 0.05], f);
      const snow = sm(0.7, 0.85, fbm(x * 4 + i, v * 6, 4, 60 + i)) * (1 - f) * sm(h, h + 0.05, v) * 0.0;
      const shade = 0.6 + 0.8 * fbm(x * 12 + i, v * 10, 5, 80 + i);
      const lit = mul3(body, shade);
      col = mix3(add3(lit, [snow, snow, snow]), mix3([0.55, 0.62, 0.78], [0.9, 0.78, 0.66], 0.4), Math.min(0.92, haze ** 1.2 * 0.85 + 0.08));
    }
  }
  return col;
};

const forest: Fn = (u, v, asp) => {
  const x = u * asp;
  let col = mix3([0.015, 0.05, 0.03], [0.12, 0.25, 0.1], fbm(x * 3, v * 3, 5, 11));
  const dep = fbm(x * 9, v * 9, 5, 12);
  col = mul3(col, 0.5 + dep);
  for (let i = 0; i < 9; i += 1) {
    const cx = (hash(i, 1, 5) * 1.25 - 0.05) * asp;
    const wd = 0.012 + hash(i, 2, 5) * 0.03;
    const k = Math.exp(-((x - cx - (v - 0.5) * 0.04 * (hash(i, 3, 5) - 0.5)) ** 2) / (wd * wd));
    const bark = 0.01 + 0.05 * fbm(x * 70, v * 8, 4, 50 + i);
    col = mix3(col, [bark * 1.2, bark, bark * 0.7], Math.min(1, k * 1.5));
  }
  const ang = (u - 1.0) * 0.9 + (v - 0.0) * 0.6;
  const shaft = Math.exp(-((ang - 0.1) ** 2) / 0.012) * sm(0.0, 0.5, 1 - v) * (0.6 + 0.8 * fbm(x * 5, v * 2, 3, 71));
  col = add3(col, mul3([1.2, 1.0, 0.55], shaft * 0.75));
  const ground = sm(0.74, 0.8, v + 0.03 * fbm(x * 8, 3, 4, 90));
  const path = Math.exp(-((u - 0.45 - (v - 0.78) * 0.9) ** 2) / 0.02);
  const gcol = mix3([0.03, 0.08, 0.025], [0.38, 0.28, 0.14], path * 0.9);
  col = mix3(col, mul3(gcol, 0.7 + fbm(x * 30, v * 30, 4, 100)), ground);
  const top = 1 - sm(0, 0.15, v);
  return add3(col, mul3([0.9, 0.95, 0.8], top * 0.35));
};

const cityBuildings = Array.from({ length: 22 }, (_, i) => ({ x: i / 22 + hash(i, 1, 7) * 0.02, w: 0.032 + hash(i, 2, 7) * 0.04, h: 0.22 + hash(i, 3, 7) * 0.4, tone: hash(i, 4, 7) }));

const city: Fn = (u, v, asp) => {
  let col = mix3([0.01, 0.015, 0.05], [0.22, 0.1, 0.12], sm(0.1, 0.78, v) ** 1.5);
  const pal = [[1.4, 0.9, 0.45], [0.5, 0.8, 1.3], [1.3, 0.4, 0.5]] as V3[];
  for (const b of cityBuildings) {
    const top = 0.78 - b.h;
    if (u >= b.x && u <= b.x + b.w && v >= top) {
      const gx = Math.floor(((u - b.x) / b.w) * 5), gy = Math.floor((v - top) * 55);
      const on = hash(gx, gy, 31 + Math.floor(b.tone * 50)) > 0.62;
      const wx = ((u - b.x) / b.w) * 5 - gx, wy = (v - top) * 55 - gy;
      const win = on && wx > 0.2 && wx < 0.75 && wy > 0.25 && wy < 0.8;
      col = win ? mul3(pal[Math.floor(hash(gx, gy, 3) * 3) % 3], 0.5 + hash(gx, gy, 9)) : mix3([0.01, 0.012, 0.025], [0.03, 0.03, 0.05], b.tone);
    }
  }
  if (v > 0.78) {
    const t = (v - 0.78) / 0.22;
    col = mix3([0.05, 0.04, 0.05], [0.015, 0.015, 0.02], t);
    const glow = Math.exp(-((u - 0.5) ** 2) / 0.08) * (1 - t) * 0.7;
    col = add3(col, mul3([1.2, 0.55, 0.2], glow * (0.5 + fbm(u * asp * 40, v * 6, 3, 15))));
  }
  for (let i = 0; i < 26; i += 1) {
    const cx = hash(i, 5, 13) * asp, cy = 0.3 + hash(i, 6, 13) * 0.6;
    const r = 0.018 + hash(i, 7, 13) * 0.045;
    const d = Math.hypot(u * asp - cx, v - cy);
    const disc = (1 - sm(r * 0.9, r, d)) * (0.35 + 0.65 * sm(r * 0.4, r * 0.95, d));
    col = add3(col, mul3(pal[i % 3], disc * 0.45));
  }
  return col;
};

const dunes: Fn = (u, v, asp) => {
  const x = u * asp;
  let col = mix3([0.35, 0.55, 0.85], [1.05, 0.88, 0.7], sm(0, 0.5, v) ** 0.8);
  const ridge = (k: number, sc: number, base: number, amp: number): number => base + amp * Math.sin(x * sc + k) * Math.sin(x * sc * 0.37 + k * 2) + 0.05 * fbm(x * 2, k, 4, 120 + k);
  const layers = [ridge(1, 3.2, 0.5, 0.06), ridge(2, 4.6, 0.62, 0.08), ridge(3, 5.6, 0.78, 0.1)];
  for (let i = 0; i < 3; i += 1) {
    if (v > layers[i]) {
      const slope = Math.cos(x * (3.2 + i * 1.2) + i) ;
      const shade = sm(-0.6, 0.8, slope + (v - layers[i]) * 2.5);
      const grain = 0.9 + 0.2 * fbm(x * 90, v * 90, 3, 140 + i);
      const sand = mix3([0.12, 0.06, 0.035], [1.15, 0.72, 0.42], shade);
      col = mul3(sand, grain * (0.75 + 0.25 * i * 0.5));
    }
  }
  return col;
};

const meadowDots = Array.from({ length: 900 }, (_, i) => {
  const t = hash(i, 1, 55);
  return { x: hash(i, 2, 55), y: 0.6 + 0.4 * t ** 0.6, hue: Math.floor(hash(i, 3, 55) * 4), r: 0.0025 + 0.012 * t ** 1.6 };
});
const flowerCols: V3[] = [[1.5, 0.08, 0.06], [1.7, 1.4, 0.2], [1.5, 1.45, 1.4], [0.7, 0.2, 1.1]];

const meadow: Fn = (u, v, asp) => {
  const x = u * asp;
  let col = mix3([0.12, 0.38, 0.95], [0.6, 0.78, 1.1], sm(0, 0.5, v));
  const c = fbm(x * 2.8, v * 6, 6, 77);
  const cloud = sm(0.5, 0.74, c) * (1 - sm(0.3, 0.52, v));
  col = mix3(col, [1.5 + c * 0.4, 1.48 + c * 0.4, 1.45 + c * 0.4], cloud);
  const hill = 0.5 + 0.06 * Math.sin(x * 2.1) + 0.05 * fbm(x * 2, 4, 4, 88);
  if (v > hill) {
    const t = (v - hill) / (1 - hill);
    const blades = fbm(x * 120, v * (60 + 200 * t), 3, 99);
    col = mul3(mix3([0.08, 0.26, 0.06], [0.2, 0.5, 0.1], t), 0.6 + blades * 0.9);
    col = mix3(col, [0.4, 0.55, 0.3], (1 - t) * 0.5);
    for (const d of meadowDots) {
      const dd = Math.hypot((u - d.x) * asp, (v - d.y) * 1.0);
      if (dd < d.r * 1.3 && v > hill + 0.02) col = mix3(col, flowerCols[d.hue], 1 - sm(d.r * 0.7, d.r * 1.2, dd));
    }
  }
  return col;
};

const FNS: Record<string, Fn> = { coast, ridges, forest, city, dunes, meadow };

function filmic(x: number): number {
  const w = 3.5;
  return (x * (1 + x / (w * w))) / (1 + x);
}

export function renderScene(id: string, w: number, h: number): Uint8ClampedArray {
  const fn = FNS[id] ?? coast;
  const out = new Uint8ClampedArray(w * h * 4);
  const asp = w / h;
  const grainSeed = id.length * 7;
  for (let y = 0; y < h; y += 1) {
    for (let x = 0; x < w; x += 1) {
      const c = fn((x + 0.5) / w, (y + 0.5) / h, asp);
      const n = (hash(x, y, grainSeed) - 0.5) * 0.02;
      const o = (y * w + x) * 4;
      out[o] = srgbEncode(filmic(Math.max(c[0], 0)) + n) * 255;
      out[o + 1] = srgbEncode(filmic(Math.max(c[1], 0)) + n) * 255;
      out[o + 2] = srgbEncode(filmic(Math.max(c[2], 0)) + n) * 255;
      out[o + 3] = 255;
    }
  }
  return out;
}
