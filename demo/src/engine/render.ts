import { apply, wbMatrix } from './colour';
import { Frame, type Source } from './geometry';
import { newPlanes, type Planes } from './planes';
import { prepare, renderRows } from './finish';
import type { Dev } from './settings';

export interface Rendered { w: number; h: number; rgba: Uint8ClampedArray<ArrayBuffer> }

interface Stage { geo: string; sampled: Float32Array | null; lin: Float32Array | null; linKey: string; planes: Planes; w: number; h: number; ppl: number }

export const SHOT_TEMP = 6500;
export const SHOT_TINT = 0;

export function effectiveWb(dev: Dev): [number, number] {
  const wb = (dev.wb && typeof dev.wb === 'object' ? dev.wb : {}) as Dev;
  if ((wb.mode ?? 'asShot') === 'asShot') return [SHOT_TEMP, SHOT_TINT];
  return [Number.isFinite(wb.temp) ? (wb.temp as number) : SHOT_TEMP, Number.isFinite(wb.tint) ? (wb.tint as number) : SHOT_TINT];
}

export class Renderer {
  private readonly stages = new Map<number, Stage>();

  private stage(id: number): Stage {
    let s = this.stages.get(id);
    if (!s) {
      s = { geo: '', sampled: null, lin: null, linKey: '', planes: newPlanes(), w: 0, h: 0, ppl: 0 };
      this.stages.set(id, s);
      if (this.stages.size > 4) this.stages.delete(this.stages.keys().next().value as number);
    }
    return s;
  }

  drop(id: number): void { this.stages.delete(id); }

  size(src: Source, dev: Dev, long: number | null): [number, number] {
    return new Frame(src.w, src.h, dev).fitLong(long);
  }

  render(src: Source, dev: Dev, long: number | null): Rendered {
    const frame = new Frame(src.w, src.h, dev);
    const [w, h] = frame.fitLong(long);
    const ppl = frame.pxPerLong(w);
    const st = this.stage(src.id);
    const geoOn = !(Array.isArray(dev.disabled) && (dev.disabled as string[]).includes('geometry'));
    const geo = JSON.stringify([w, h, dev.orientation, dev.crop, geoOn ? dev.geometry : null]);
    if (st.geo !== geo || !st.sampled) {
      st.sampled = frame.sample(src, w, h);
      st.geo = geo;
      st.linKey = '';
      st.planes = newPlanes();
      st.w = w; st.h = h; st.ppl = ppl;
    }
    const wb = effectiveWb(dev);
    const linKey = `${geo}|${wb[0]}|${wb[1]}`;
    if (st.linKey !== linKey || !st.lin) {
      const m = wbMatrix(wb[0], wb[1], SHOT_TEMP, SHOT_TINT);
      const s = st.sampled;
      const lin = new Float32Array(s.length);
      if (!m) for (let i = 0; i < s.length; i += 1) lin[i] = Math.max(s[i], 0);
      else for (let i = 0; i < s.length; i += 3) {
        lin[i] = Math.max(m[0] * s[i] + m[1] * s[i + 1] + m[2] * s[i + 2], 0);
        lin[i + 1] = Math.max(m[3] * s[i] + m[4] * s[i + 1] + m[5] * s[i + 2], 0);
        lin[i + 2] = Math.max(m[6] * s[i] + m[7] * s[i + 1] + m[8] * s[i + 2], 0);
      }
      st.lin = lin;
      st.linKey = linKey;
      st.planes = newPlanes();
    }
    const plan = prepare(dev, st.lin, st.planes, w, h, ppl, Math.max(src.w, src.h));
    const rgba = new Uint8ClampedArray(w * h * 4);
    renderRows(plan, st.lin, rgba, 0, h);
    return { w, h, rgba };
  }

  sampleLinear(src: Source, u: number, v: number, radius = 3): number[] | null {
    const st = this.stages.get(src.id);
    if (!st || !st.sampled) return null;
    const cx = Math.round(u * (st.w - 1)), cy = Math.round(v * (st.h - 1));
    const acc = [0, 0, 0];
    let n = 0;
    for (let y = Math.max(0, cy - radius); y <= Math.min(st.h - 1, cy + radius); y += 1) for (let x = Math.max(0, cx - radius); x <= Math.min(st.w - 1, cx + radius); x += 1) {
      const j = (y * st.w + x) * 3;
      acc[0] += st.sampled[j]; acc[1] += st.sampled[j + 1]; acc[2] += st.sampled[j + 2];
      n += 1;
    }
    return n ? acc.map((a) => a / n) : null;
  }
}

export function solveWb(rgb: number[]): [number, number] {
  const cost = (t: number, tint: number): number => {
    const m = wbMatrix(t, tint, SHOT_TEMP, SHOT_TINT);
    const o = m ? apply(m, rgb) : rgb;
    const y = (o[0] + o[1] + o[2]) / 3 || 1e-6;
    return Math.abs(o[0] - o[1]) / y + Math.abs(o[2] - o[1]) / y;
  };
  let best: [number, number, number] = [SHOT_TEMP, 0, Infinity];
  for (let mired = 40; mired <= 500; mired += 10) for (let tint = -150; tint <= 150; tint += 10) {
    const t = 1e6 / mired;
    const c = cost(t, tint);
    if (c < best[2]) best = [t, tint, c];
  }
  let [bt, bn] = best;
  for (const [dm, dn] of [[5, 5], [1, 1]]) {
    const m0 = 1e6 / bt;
    for (let mired = m0 - 10 * dm; mired <= m0 + 10 * dm; mired += dm) for (let tint = bn - 10 * dn; tint <= bn + 10 * dn; tint += dn) {
      const t = 1e6 / Math.max(mired, 20);
      const c = cost(t, tint);
      if (c < best[2]) { best = [t, tint, c]; }
    }
    [bt, bn] = best;
  }
  return [Math.round(Math.min(50000, Math.max(2000, bt))), Math.round(Math.min(150, Math.max(-150, bn)))];
}
