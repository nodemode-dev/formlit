import { LUMA_2020 } from './colour';

export const EPS_L = 2 ** -11;
export const EPS_S = 0.004;
const HS_SIGMAS = [0.01, 0.032];
const HS_EPS = [0.3, 0.45];
const CLARITY_SIGMA = 0.0075;
const CLARITY_EPS = 0.06;
const TEXTURE_SIGMAS = [0.0003, 0.0022];
const HAZE_LONG = 320;
const HAZE_PATCH = 0.01;
const HAZE_GUIDE = 0.025;
const HAZE_EPS = 0.002;

export interface Planes { l0?: Float32Array; ls?: Float32Array; hs?: Float32Array; dc?: Float32Array; dt?: Float32Array; hd?: Float32Array; sharp: Map<string, { d: Float32Array; edge: Float32Array }>; ppl: number }

export const newPlanes = (): Planes => ({ sharp: new Map(), ppl: 0 });

export function luminance(lin: Float32Array, n: number): Float32Array {
  const o = new Float32Array(n);
  for (let i = 0, j = 0; i < n; i += 1, j += 3) o[i] = lin[j] * LUMA_2020[0] + lin[j + 1] * LUMA_2020[1] + lin[j + 2] * LUMA_2020[2];
  return o;
}

export function logLum(lin: Float32Array, n: number, eps: number): Float32Array {
  const y = luminance(lin, n);
  for (let i = 0; i < n; i += 1) y[i] = Math.log2(y[i] + eps);
  return y;
}

function boxPass(src: Float32Array, dst: Float32Array, w: number, h: number, r: number, horizontal: boolean): void {
  const len = horizontal ? w : h, lines = horizontal ? h : w;
  const stride = horizontal ? 1 : w, lineStep = horizontal ? w : 1;
  const inv = 1 / (2 * r + 1);
  for (let l = 0; l < lines; l += 1) {
    const base = l * lineStep;
    let sum = src[base] * (r + 1);
    for (let k = 1; k <= r; k += 1) sum += src[base + Math.min(k, len - 1) * stride];
    for (let k = 0; k < len; k += 1) {
      dst[base + k * stride] = sum * inv;
      const add = src[base + Math.min(k + r + 1, len - 1) * stride];
      const rem = src[base + Math.max(k - r, 0) * stride];
      sum += add - rem;
    }
  }
}

export function gauss(img: Float32Array, w: number, h: number, sigma: number): Float32Array {
  if (sigma <= 0.05) return img.slice();
  if (sigma < 1.2) {
    const rad = Math.max(1, Math.ceil(sigma * 3));
    const k: number[] = [];
    let s = 0;
    for (let i = -rad; i <= rad; i += 1) { const v = Math.exp(-(i * i) / (2 * sigma * sigma)); k.push(v); s += v; }
    const tmp = new Float32Array(img.length), out = new Float32Array(img.length);
    for (let y = 0; y < h; y += 1) for (let x = 0; x < w; x += 1) {
      let a = 0;
      for (let i = -rad; i <= rad; i += 1) a += img[y * w + Math.min(w - 1, Math.max(0, x + i))] * k[i + rad];
      tmp[y * w + x] = a / s;
    }
    for (let y = 0; y < h; y += 1) for (let x = 0; x < w; x += 1) {
      let a = 0;
      for (let i = -rad; i <= rad; i += 1) a += tmp[Math.min(h - 1, Math.max(0, y + i)) * w + x] * k[i + rad];
      out[y * w + x] = a / s;
    }
    return out;
  }
  const wIdeal = Math.sqrt((12 * sigma * sigma) / 3 + 1);
  let wl = Math.floor(wIdeal);
  if (wl % 2 === 0) wl -= 1;
  const r = Math.max(1, (wl - 1) / 2);
  let a = img.slice();
  let b = new Float32Array(img.length);
  for (let pass = 0; pass < 3; pass += 1) {
    boxPass(a, b, w, h, r, true);
    boxPass(b, a, w, h, r, false);
  }
  return a;
}

export function resizeArea(src: Float32Array, w: number, h: number, nw: number, nh: number, ch = 1): Float32Array {
  const out = new Float32Array(nw * nh * ch);
  const sx = w / nw, sy = h / nh;
  for (let y = 0; y < nh; y += 1) {
    const y0 = Math.floor(y * sy), y1 = Math.max(y0 + 1, Math.min(h, Math.ceil((y + 1) * sy)));
    for (let x = 0; x < nw; x += 1) {
      const x0 = Math.floor(x * sx), x1 = Math.max(x0 + 1, Math.min(w, Math.ceil((x + 1) * sx)));
      const cnt = (y1 - y0) * (x1 - x0);
      for (let c = 0; c < ch; c += 1) {
        let s = 0;
        for (let yy = y0; yy < y1; yy += 1) for (let xx = x0; xx < x1; xx += 1) s += src[(yy * w + xx) * ch + c];
        out[(y * nw + x) * ch + c] = s / cnt;
      }
    }
  }
  return out;
}

export function resizeLinear(src: Float32Array, w: number, h: number, nw: number, nh: number): Float32Array {
  const out = new Float32Array(nw * nh);
  for (let y = 0; y < nh; y += 1) {
    const fy = Math.min(h - 1, Math.max(0, ((y + 0.5) * h) / nh - 0.5));
    const y0 = Math.floor(fy), y1 = Math.min(h - 1, y0 + 1), ty = fy - y0;
    for (let x = 0; x < nw; x += 1) {
      const fx = Math.min(w - 1, Math.max(0, ((x + 0.5) * w) / nw - 0.5));
      const x0 = Math.floor(fx), x1 = Math.min(w - 1, x0 + 1), tx = fx - x0;
      const a = src[y0 * w + x0] + (src[y0 * w + x1] - src[y0 * w + x0]) * tx;
      const b = src[y1 * w + x0] + (src[y1 * w + x1] - src[y1 * w + x0]) * tx;
      out[y * nw + x] = a + (b - a) * ty;
    }
  }
  return out;
}

function gfCoeffs(I: Float32Array, p: Float32Array, w: number, h: number, sigma: number, eps: number): [Float32Array, Float32Array] {
  const n = I.length;
  const mI = gauss(I, w, h, sigma), mp = p === I ? mI : gauss(p, w, h, sigma);
  const Ip = new Float32Array(n), II = new Float32Array(n);
  for (let i = 0; i < n; i += 1) { Ip[i] = I[i] * p[i]; II[i] = I[i] * I[i]; }
  const gIp = gauss(Ip, w, h, sigma), gII = gauss(II, w, h, sigma);
  const a = new Float32Array(n), b = new Float32Array(n);
  for (let i = 0; i < n; i += 1) {
    const cov = gIp[i] - mI[i] * mp[i];
    const v = Math.max(gII[i] - mI[i] * mI[i], 0);
    a[i] = cov / (v + eps);
    b[i] = mp[i] - a[i] * mI[i];
  }
  return [gauss(a, w, h, sigma), gauss(b, w, h, sigma)];
}

export function guided(I: Float32Array, p: Float32Array, w: number, h: number, sigma: number, eps: number): Float32Array {
  const f = Math.max(1, Math.floor(sigma / 3));
  const out = new Float32Array(I.length);
  if (f <= 1) {
    const [a, b] = gfCoeffs(I, p, w, h, sigma, eps);
    for (let i = 0; i < out.length; i += 1) out[i] = a[i] * I[i] + b[i];
    return out;
  }
  const lw = Math.max(2, Math.round(w / f)), lh = Math.max(2, Math.round(h / f));
  const Il = resizeArea(I, w, h, lw, lh);
  const pl = p === I ? Il : resizeArea(p, w, h, lw, lh);
  const [al, bl] = gfCoeffs(Il, pl, lw, lh, (sigma * lw) / w, eps);
  const a = resizeLinear(al, lw, lh, w, h), b = resizeLinear(bl, lw, lh, w, h);
  for (let i = 0; i < out.length; i += 1) out[i] = a[i] * I[i] + b[i];
  return out;
}

export function ensureL0(pl: Planes, lin: Float32Array, n: number): Float32Array {
  if (!pl.l0) pl.l0 = logLum(lin, n, EPS_L);
  return pl.l0;
}

export function buildHs(pl: Planes, lin: Float32Array, w: number, h: number, ppl: number): Float32Array {
  if (pl.hs) return pl.hs;
  const l0 = ensureL0(pl, lin, w * h);
  const b1 = guided(l0, l0, w, h, Math.max(HS_SIGMAS[0] * ppl, 1), HS_EPS[0]);
  const b2 = guided(l0, l0, w, h, Math.max(HS_SIGMAS[1] * ppl, 1), HS_EPS[1]);
  for (let i = 0; i < b1.length; i += 1) b1[i] = 0.5 * (b1[i] + b2[i]);
  pl.hs = b1;
  return b1;
}

export function buildClarity(pl: Planes, lin: Float32Array, w: number, h: number, ppl: number): Float32Array {
  if (pl.dc) return pl.dc;
  const l0 = ensureL0(pl, lin, w * h);
  const base = guided(l0, l0, w, h, Math.max(CLARITY_SIGMA * ppl, 0.8), CLARITY_EPS);
  for (let i = 0; i < base.length; i += 1) base[i] = 1.6 * Math.tanh((l0[i] - base[i]) / 1.6);
  pl.dc = base;
  return base;
}

export function buildTexture(pl: Planes, lin: Float32Array, w: number, h: number, ppl: number): Float32Array {
  if (pl.dt) return pl.dt;
  const l0 = ensureL0(pl, lin, w * h);
  const fine = gauss(l0, w, h, TEXTURE_SIGMAS[0] * ppl);
  const coarse = gauss(l0, w, h, Math.max(TEXTURE_SIGMAS[1] * ppl, 0.7));
  for (let i = 0; i < fine.length; i += 1) fine[i] -= coarse[i];
  pl.dt = fine;
  return fine;
}

function minFilter(src: Float32Array, w: number, h: number, r: number): Float32Array {
  const tmp = new Float32Array(src.length), out = new Float32Array(src.length);
  for (let y = 0; y < h; y += 1) for (let x = 0; x < w; x += 1) {
    let m = Infinity;
    for (let i = Math.max(0, x - r); i <= Math.min(w - 1, x + r); i += 1) m = Math.min(m, src[y * w + i]);
    tmp[y * w + x] = m;
  }
  for (let y = 0; y < h; y += 1) for (let x = 0; x < w; x += 1) {
    let m = Infinity;
    for (let i = Math.max(0, y - r); i <= Math.min(h - 1, y + r); i += 1) m = Math.min(m, tmp[i * w + x]);
    out[y * w + x] = m;
  }
  return out;
}

export function buildHaze(pl: Planes, lin: Float32Array, w: number, h: number, ppl: number): Float32Array {
  if (pl.hd) return pl.hd;
  const f = Math.max(1, ppl / HAZE_LONG);
  const lw = Math.max(4, Math.round(w / f)), lh = Math.max(4, Math.round(h / f));
  const small = resizeArea(lin, w, h, lw, lh, 3);
  const dark = new Float32Array(lw * lh), guide = new Float32Array(lw * lh);
  for (let i = 0; i < dark.length; i += 1) {
    const r = small[i * 3], g = small[i * 3 + 1], b = small[i * 3 + 2];
    dark[i] = Math.min(r, g, b);
    guide[i] = Math.sqrt(Math.max(r * LUMA_2020[0] + g * LUMA_2020[1] + b * LUMA_2020[2], 0));
  }
  const rad = Math.max(1, Math.round((HAZE_PATCH * ppl) / f));
  const eroded = minFilter(dark, lw, lh, rad);
  for (let i = 0; i < eroded.length; i += 1) eroded[i] = Math.sqrt(Math.max(eroded[i], 0));
  const [al, bl] = gfCoeffs(guide, eroded, lw, lh, Math.max((HAZE_GUIDE * ppl) / f, 1), HAZE_EPS);
  const a = resizeLinear(al, lw, lh, w, h), b = resizeLinear(bl, lw, lh, w, h);
  const out = new Float32Array(w * h);
  for (let i = 0; i < out.length; i += 1) {
    const y = Math.sqrt(Math.max(lin[i * 3] * LUMA_2020[0] + lin[i * 3 + 1] * LUMA_2020[1] + lin[i * 3 + 2] * LUMA_2020[2], 0));
    const q = Math.max(a[i] * y + b[i], 0);
    out[i] = q * q;
  }
  pl.hd = out;
  return out;
}

export function sharpDetail(pl: Planes, lin: Float32Array, w: number, h: number, sigma: number): { d: Float32Array; edge: Float32Array } {
  const key = sigma.toFixed(4);
  const hit = pl.sharp.get(key);
  if (hit) return hit;
  if (!pl.ls) pl.ls = logLum(lin, w * h, EPS_S);
  const ls = pl.ls;
  const g = gauss(ls, w, h, sigma);
  const d = new Float32Array(ls.length);
  for (let i = 0; i < d.length; i += 1) d[i] = ls[i] - g[i];
  const sm = gauss(ls, w, h, Math.max(sigma, 0.7));
  const edge = new Float32Array(ls.length);
  const at = (x: number, y: number): number => sm[Math.min(h - 1, Math.max(0, y)) * w + Math.min(w - 1, Math.max(0, x))];
  for (let y = 0; y < h; y += 1) for (let x = 0; x < w; x += 1) {
    const gx = (at(x + 1, y - 1) + 2 * at(x + 1, y) + at(x + 1, y + 1) - at(x - 1, y - 1) - 2 * at(x - 1, y) - at(x - 1, y + 1)) * 0.125;
    const gy = (at(x - 1, y + 1) + 2 * at(x, y + 1) + at(x + 1, y + 1) - at(x - 1, y - 1) - 2 * at(x, y - 1) - at(x + 1, y - 1)) * 0.125;
    edge[y * w + x] = Math.sqrt(gx * gx + gy * gy);
  }
  const res = { d, edge };
  pl.sharp.set(key, res);
  return res;
}
