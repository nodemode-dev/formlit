import { eye, inv, mul, type Mat3 } from './colour';
import { sectionEnabled, type Dev } from './settings';
import { resizeArea } from './planes';

const FOCAL = 1.5;
const KEYSTONE_MAX = 30;
const ASPECT_MAX = 0.5;
const OFFSET_FULL = 0.5;
export const BLANK = 0.18;

export interface Source { id: number; w: number; h: number; levels: Float32Array[]; sizes: Array<[number, number]> }

export function makeSource(id: number, w: number, h: number, lin: Float32Array): Source {
  const levels = [lin], sizes: Array<[number, number]> = [[w, h]];
  let cw = w, ch = h, cur = lin;
  while (Math.min(cw, ch) >= 64 && levels.length < 6) {
    const nw = Math.max(1, cw >> 1), nh = Math.max(1, ch >> 1);
    cur = resizeArea(cur, cw, ch, nw, nh, 3);
    levels.push(cur);
    sizes.push([nw, nh]);
    cw = nw; ch = nh;
  }
  return { id, w, h, levels, sizes };
}

const rotX = (t: number): Mat3 => { const c = Math.cos(t), s = Math.sin(t); return [1, 0, 0, 0, c, -s, 0, s, c]; };
const rotY = (t: number): Mat3 => { const c = Math.cos(t), s = Math.sin(t); return [c, 0, s, 0, 1, 0, -s, 0, c]; };
const rotZ = (t: number): Mat3 => { const c = Math.cos(t), s = Math.sin(t); return [c, -s, 0, s, c, 0, 0, 0, 1]; };
const diag = (a: number, b: number): Mat3 => [a, 0, 0, 0, b, 0, 0, 0, 1];

function recentre(m: Mat3): Mat3 {
  if (Math.abs(m[8]) < 1e-12) return eye();
  const n = m.map((v) => v / m[8]);
  const t = mul([1, 0, -n[2], 0, 1, -n[5], 0, 0, 1], n);
  const det = Math.abs(t[0] * t[4] - t[1] * t[3]);
  if (det < 1e-12) return eye();
  const s = 1 / Math.sqrt(det);
  const o = mul(diag(s, s), t);
  return o.map((v) => v / o[8]);
}

function keystone(vertical: number, horizontal: number): Mat3 {
  const tx = (-vertical / 100 * KEYSTONE_MAX * Math.PI) / 180;
  const ty = (horizontal / 100 * KEYSTONE_MAX * Math.PI) / 180;
  if (tx === 0 && ty === 0) return eye();
  const k = diag(FOCAL, FOCAL);
  return recentre(mul(k, mul(mul(rotX(tx), rotY(ty)), inv(k))));
}

function manual(geo: Record<string, number>): Mat3 {
  const n = (k: string, d = 0): number => (Number.isFinite(geo[k]) ? geo[k] : d);
  const rot = rotZ((n('rotate') * Math.PI) / 180);
  const key = keystone(n('vertical'), n('horizontal'));
  const a = (n('aspect') / 100) * ASPECT_MAX;
  const asp = diag(2 ** -a, 2 ** a);
  const k = Math.max(0.01, n('scale', 100) / 100);
  const off: Mat3 = [1, 0, (n('offsetX') / 100) * OFFSET_FULL, 0, 1, (-n('offsetY') / 100) * OFFSET_FULL, 0, 0, 1];
  return mul(off, mul(diag(k, k), mul(asp, mul(key, rot))));
}

export class Frame {
  readonly turns: number;
  readonly ow: number;
  readonly oh: number;
  rect = [0, 0, 1, 1];
  angle = 0;
  flipH = false;
  flipV = false;
  readonly hinv: Mat3 | null;

  constructor(readonly srcW: number, readonly srcH: number, dev: Dev) {
    this.turns = (((Number(dev.orientation) || 0) % 4) + 4) % 4;
    [this.ow, this.oh] = this.turns % 2 === 0 ? [srcW, srcH] : [srcH, srcW];
    const crop = dev.crop as Dev | undefined;
    if (crop) {
      const r = crop.rect as number[] | undefined;
      if (Array.isArray(r) && r.length === 4 && r[2] > r[0] && r[3] > r[1]) this.rect = r.slice();
      this.angle = Number(crop.angle) || 0;
      this.flipH = crop.flipH === true;
      this.flipV = crop.flipV === true;
    }
    const geo = sectionEnabled(dev, 'geometry') && dev.geometry && typeof dev.geometry === 'object' ? (dev.geometry as Record<string, number>) : {};
    const p = manual(geo);
    const pn = Math.abs(p[8]) > 1e-12 ? p.map((v) => v / p[8]) : eye();
    this.hinv = pn.every((v, k) => Math.abs(v - eye()[k]) <= 1e-12) ? null : inv(pn);
  }

  nativeSize(): [number, number] {
    return [(this.rect[2] - this.rect[0]) * this.ow, (this.rect[3] - this.rect[1]) * this.oh];
  }

  fit(maxW: number, maxH: number): [number, number] {
    const [nw, nh] = this.nativeSize().map((v) => Math.max(v, 1e-9));
    const s = Math.min(maxW / nw, maxH / nh);
    return [Math.max(1, Math.min(Math.floor(maxW), Math.round(nw * s))), Math.max(1, Math.min(Math.floor(maxH), Math.round(nh * s)))];
  }

  fitLong(long: number | null): [number, number] {
    const [nw, nh] = this.nativeSize();
    if (long === null || Math.max(nw, nh) <= long) return [Math.max(1, Math.round(nw)), Math.max(1, Math.round(nh))];
    return this.fit(long, long);
  }

  pxPerLong(outW: number): number {
    return (outW / Math.max(this.nativeSize()[0], 1e-9)) * Math.max(this.ow, this.oh);
  }

  sample(src: Source, w: number, h: number): Float32Array {
    const [x0, y0, x1, y1] = this.rect;
    const sx = ((x1 - x0) * this.ow) / w, sy = ((y1 - y0) * this.oh) / h;
    const lvl = Math.min(src.levels.length - 1, Math.max(0, Math.floor(Math.log2(Math.max(1, Math.min(sx, sy))))));
    const data = src.levels[lvl];
    const [lw, lh] = src.sizes[lvl];
    const f = 2 ** lvl;
    const cx = this.ow / 2, cy = this.oh / 2;
    const t = (-this.angle * Math.PI) / 180;
    const ca = Math.cos(t), sa = Math.sin(t);
    const out = new Float32Array(w * h * 3);
    const hinv = this.hinv;
    const L = Math.max(this.ow, this.oh) / 2;
    for (let y = 0; y < h; y += 1) {
      for (let x = 0; x < w; x += 1) {
        let px = x + 0.5, py = y + 0.5;
        if (this.flipH) px = w - px;
        if (this.flipV) py = h - py;
        let ox = x0 * this.ow + px * ((x1 - x0) * this.ow / w);
        let oy = y0 * this.oh + py * ((y1 - y0) * this.oh / h);
        const dx = ox - cx, dy = oy - cy;
        ox = cx + ca * dx - sa * dy;
        oy = cy + sa * dx + ca * dy;
        let ok = true;
        if (hinv) {
          const u = (ox - cx) / L, v = (oy - cy) / L;
          const d = hinv[6] * u + hinv[7] * v + hinv[8];
          const s = Math.abs(d) < 1e-12 ? 1e-12 : d;
          ox = ((hinv[0] * u + hinv[1] * v + hinv[2]) / s) * L + cx;
          oy = ((hinv[3] * u + hinv[4] * v + hinv[5]) / s) * L + cy;
          ok = d > 1e-9;
        }
        let spx: number, spy: number;
        if (this.turns === 0) { spx = ox; spy = oy; }
        else if (this.turns === 1) { spx = oy; spy = this.srcH - ox; }
        else if (this.turns === 2) { spx = this.srcW - ox; spy = this.srcH - oy; }
        else { spx = this.srcW - oy; spy = ox; }
        const o = (y * w + x) * 3;
        if (!ok || spx < 0 || spy < 0 || spx > this.srcW || spy > this.srcH) { out[o] = BLANK; out[o + 1] = BLANK; out[o + 2] = BLANK; continue; }
        const fx = Math.min(lw - 1, Math.max(0, spx / f - 0.5)), fy = Math.min(lh - 1, Math.max(0, spy / f - 0.5));
        const ix = fx | 0, iy = fy | 0, tx = fx - ix, ty = fy - iy;
        const ix1 = Math.min(lw - 1, ix + 1), iy1 = Math.min(lh - 1, iy + 1);
        const a = (iy * lw + ix) * 3, b = (iy * lw + ix1) * 3, c = (iy1 * lw + ix) * 3, d2 = (iy1 * lw + ix1) * 3;
        for (let k = 0; k < 3; k += 1) {
          const top = data[a + k] + (data[b + k] - data[a + k]) * tx;
          const bot = data[c + k] + (data[d2 + k] - data[c + k]) * tx;
          out[o + k] = top + (bot - top) * ty;
        }
      }
    }
    return out;
  }
}

export function cropFitAngle(w: number, h: number, angle: number, aspect: number | null): number[] {
  const asp = aspect || w / h;
  const t = (angle * Math.PI) / 180;
  const c = Math.abs(Math.cos(t)), s = Math.abs(Math.sin(t));
  const a = Math.min(w / 2 / (c + s / asp), h / 2 / (s + c / asp));
  const b = a / asp;
  return [0.5 - a / w, 0.5 - b / h, 0.5 + a / w, 0.5 + b / h];
}
