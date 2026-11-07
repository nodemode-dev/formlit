import { Frame } from '../../../../demo/src/engine/geometry';
import type { Dev } from '../../../../demo/src/engine/settings';

export interface Geo {
  w: number; h: number; ow: number; oh: number; long: number; ppl: number;
  ax: number; ay: number; ac: number; bx: number; by: number; bc: number;
  det: number;
}

export function geoOf(srcW: number, srcH: number, dev: Dev, w: number, h: number): Geo {
  const fr = new Frame(srcW, srcH, dev);
  const [x0, y0, x1, y1] = fr.rect;
  const cx = fr.ow / 2, cy = fr.oh / 2;
  const t = (-fr.angle * Math.PI) / 180;
  const ca = Math.cos(t), sa = Math.sin(t);
  const map = (px: number, py: number): [number, number] => {
    if (fr.flipH) px = w - px;
    if (fr.flipV) py = h - py;
    let ox = x0 * fr.ow + px * (((x1 - x0) * fr.ow) / w);
    let oy = y0 * fr.oh + py * (((y1 - y0) * fr.oh) / h);
    const dx = ox - cx, dy = oy - cy;
    ox = cx + ca * dx - sa * dy;
    oy = cy + sa * dx + ca * dy;
    return [ox / fr.ow, oy / fr.oh];
  };
  const p0 = map(0, 0), px = map(1, 0), py = map(0, 1);
  const ax = px[0] - p0[0], ay = py[0] - p0[0], bx = px[1] - p0[1], by = py[1] - p0[1];
  return {
    w, h, ow: fr.ow, oh: fr.oh, long: Math.max(fr.ow, fr.oh), ppl: fr.pxPerLong(w),
    ax, ay, ac: p0[0], bx, by, bc: p0[1], det: ax * by - ay * bx,
  };
}

export function toNorm(g: Geo, x: number, y: number): Vec2 {
  return [g.ax * x + g.ay * y + g.ac, g.bx * x + g.by * y + g.bc];
}

export function toPixel(g: Geo, nx: number, ny: number): Vec2 {
  const u = nx - g.ac, v = ny - g.bc;
  return [(g.by * u - g.ay * v) / g.det, (-g.bx * u + g.ax * v) / g.det];
}

export type Vec2 = [number, number];
