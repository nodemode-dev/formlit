import { LUMA_2020 } from './engine/colour';
import type { Source } from './engine/geometry';
import type { Dev } from './engine/settings';

export function autoTone(src: Source): Dev {
  let lvl = 0;
  while (lvl < src.levels.length - 1 && src.sizes[lvl][0] * src.sizes[lvl][1] > 200_000) lvl += 1;
  const data = src.levels[lvl];
  const n = src.sizes[lvl][0] * src.sizes[lvl][1];
  const y = new Float32Array(n);
  for (let i = 0; i < n; i += 1) y[i] = data[i * 3] * LUMA_2020[0] + data[i * 3 + 1] * LUMA_2020[1] + data[i * 3 + 2] * LUMA_2020[2];
  y.sort();
  const at = (p: number): number => Math.max(y[Math.min(n - 1, Math.floor(p * n))], 1e-5);
  const p1 = at(0.01), p10 = at(0.1), p50 = at(0.5), p99 = at(0.99);
  const ev = Math.max(-2, Math.min(2, Math.log2(0.2 / p50) * 0.7));
  const k = 2 ** ev;
  const hi = p99 * k, lo = p10 * k, black = p1 * k;
  const clampPct = (v: number, a: number, b: number): number => Math.round(Math.max(a, Math.min(b, v)));
  const light: Dev = {
    exposure: Number(ev.toFixed(2)),
    highlights: hi > 0.95 ? -clampPct(Math.log2(hi / 0.95) * 45, 0, 70) : 0,
    whites: hi < 0.9 ? clampPct(Math.log2(0.95 / hi) * 38, 0, 60) : -clampPct(Math.log2(hi / 0.95) * 20, 0, 30),
    shadows: lo < 0.03 ? clampPct(Math.log2(0.05 / lo) * 22, 0, 70) : 0,
    blacks: black > 0.006 ? -clampPct(Math.log2(black / 0.004) * 10, 0, 40) : 0,
    contrast: p99 / p1 < 60 ? 12 : 0,
  };
  return { light };
}
