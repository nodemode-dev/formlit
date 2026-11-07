import { effectiveWb } from '../../../../demo/src/engine/render';
import { clone, get, put, type Dev } from '../../../../demo/src/engine/settings';
import { dataBytes } from '../../../../demo/src/media';
import { geoOf, type Geo } from './geo';
import { BITMAPS, coverage, type Base } from './shapes';
import { hasAdjust, liveMasks, type Mask } from './types';

const MIRED_PER_UNIT = 0.75;
const LIGHT = ['contrast', 'highlights', 'shadows', 'whites', 'blacks'];
const EFFECTS = ['texture', 'clarity', 'dehaze'];

export function maskAlpha(m: Mask, g: Geo, base: Base): Float32Array {
  let alpha: Float32Array | null = null;
  for (const c of m.components) {
    const cov = coverage(c.shape, g, base);
    const n = cov.length;
    if (alpha === null) {
      alpha = new Float32Array(n);
      for (let i = 0; i < n; i += 1) alpha[i] = c.invert ? 1 - cov[i] : cov[i];
    } else if (c.op === 'subtract') {
      for (let i = 0; i < n; i += 1) alpha[i] *= c.invert ? cov[i] : 1 - cov[i];
    } else if (c.op === 'intersect') {
      for (let i = 0; i < n; i += 1) alpha[i] *= c.invert ? 1 - cov[i] : cov[i];
    } else {
      for (let i = 0; i < n; i += 1) { const v = c.invert ? 1 - cov[i] : cov[i]; if (v > alpha[i]) alpha[i] = v; }
    }
  }
  const out = alpha ?? new Float32Array(g.w * g.h);
  if (m.invert) for (let i = 0; i < out.length; i += 1) out[i] = 1 - out[i];
  return out;
}

export function adjustedDev(dev: Dev, m: Mask): Dev {
  const d = clone(dev);
  delete d.masks;
  const amt = (m.adjust.amount ?? 100) / 100;
  const a = m.adjust;
  const add = (cid: string, v: number): void => put(d, cid, get(d, cid) + v * amt);
  if (a.temp || a.tint) {
    const [temp, tint] = effectiveWb(d);
    const mired = 1e6 / temp - (a.temp ?? 0) * amt * MIRED_PER_UNIT;
    d.wb = { ...(d.wb as Dev | undefined), mode: 'custom', temp: Math.round(1e6 / Math.max(mired, 20)), tint: Math.round(tint + (a.tint ?? 0) * amt) };
  }
  if (a.exposure) add('light.exposure', a.exposure);
  for (const k of LIGHT) if (a[k]) add(`light.${k}`, a[k]);
  for (const k of EFFECTS) if (a[k]) add(`effects.${k}`, a[k]);
  if (a.saturation) add('color.saturation', a.saturation);
  if (a.sharpness && a.sharpness > 0) add('detail.sharpenAmount', a.sharpness * 0.8);
  if (a.noise && a.noise > 0) add('detail.nrLuminance', a.noise * 0.6);
  if (a.colorSat) {
    const g = (d.grading as Dev | undefined) ?? {};
    d.grading = { ...g, global: { ...(g.global as Dev | undefined), hue: a.colorHue ?? 0, sat: Math.min(100, a.colorSat * amt) } };
  }
  return d;
}

export interface Layer { mask: Mask; alpha: Float32Array; dev: Dev }

export function layersOf(dev: Dev, srcW: number, srcH: number, base: Base): Layer[] {
  const g = geoOf(srcW, srcH, dev, base.w, base.h);
  const out: Layer[] = [];
  for (const m of liveMasks(dev)) {
    if (!hasAdjust(m)) continue;
    out.push({ mask: m, alpha: maskAlpha(m, g, base), dev: adjustedDev(dev, m) });
  }
  return out;
}

export async function loadBitmaps(pack: Record<string, string>): Promise<void> {
  for (const [key, uri] of Object.entries(pack)) {
    const bm = await createImageBitmap(new Blob([dataBytes(uri)], { type: 'image/png' }));
    const c = document.createElement('canvas');
    c.width = bm.width;
    c.height = bm.height;
    const ctx = c.getContext('2d', { willReadFrequently: true });
    if (!ctx) continue;
    ctx.drawImage(bm, 0, 0);
    const px = ctx.getImageData(0, 0, bm.width, bm.height).data;
    const data = new Float32Array(bm.width * bm.height);
    for (let i = 0; i < data.length; i += 1) data[i] = px[i * 4] / 255;
    BITMAPS.set(key, { w: bm.width, h: bm.height, data });
    bm.close();
  }
}
