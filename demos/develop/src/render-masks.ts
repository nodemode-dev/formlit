import type { Source } from '../../../demo/src/engine/geometry';
import { Renderer as Base, SHOT_TEMP, SHOT_TINT, effectiveWb, solveWb, type Rendered } from '../../../demo/src/engine/render';
import type { Dev } from '../../../demo/src/engine/settings';
import { layersOf } from './masks/eval';
import { baseOf } from './masks/shapes';
import { hasAdjust, liveMasks } from './masks/types';

export { SHOT_TEMP, SHOT_TINT, effectiveWb, solveWb };
export type { Rendered };

const KEEP = 8;

export class Renderer extends Base {
  private readonly layer = new Base();
  private readonly cache = new Map<string, Rendered>();

  render(src: Source, dev: Dev, long: number | null): Rendered {
    const live = liveMasks(dev).filter(hasAdjust);
    const base = super.render(src, dev, long);
    if (!live.length) return base;
    const layers = layersOf(dev, src.w, src.h, baseOf(base.rgba, base.w, base.h));
    const out = new Uint8ClampedArray(base.rgba);
    const n = base.w * base.h;
    for (const l of layers) {
      const adj = this.adjusted(src, l.dev, long, base);
      for (let p = 0, j = 0; p < n; p += 1, j += 4) {
        const k = l.alpha[p];
        if (k <= 0.002) continue;
        out[j] += k * (adj.rgba[j] - base.rgba[j]);
        out[j + 1] += k * (adj.rgba[j + 1] - base.rgba[j + 1]);
        out[j + 2] += k * (adj.rgba[j + 2] - base.rgba[j + 2]);
      }
    }
    return { w: base.w, h: base.h, rgba: out };
  }

  globalOnly(src: Source, dev: Dev, long: number | null): Rendered {
    return super.render(src, dev, long);
  }

  private adjusted(src: Source, dev: Dev, long: number | null, base: Rendered): Rendered {
    const key = `${src.id}|${base.w}|${base.h}|${JSON.stringify(dev)}`;
    const hit = this.cache.get(key);
    if (hit) return hit;
    const made = this.layer.render(src, dev, long);
    this.cache.set(key, made);
    if (this.cache.size > KEEP) this.cache.delete(this.cache.keys().next().value as string);
    return made;
  }

  drop(id: number): void {
    super.drop(id);
    this.layer.drop(id);
    for (const k of Array.from(this.cache.keys())) if (k.startsWith(`${id}|`)) this.cache.delete(k);
  }
}
