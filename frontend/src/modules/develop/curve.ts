import { develop, getPath, clone } from '../../state/develop';
import { el, q, setClass } from '../../ui/dom';

type Pts = Array<[number, number]>;
const CHANNELS = ['master', 'red', 'green', 'blue'] as const;
type Channel = (typeof CHANNELS)[number];
const COLORS: Record<Channel, string> = { master: '#e8e8e8', red: '#e5484d', green: '#46a758', blue: '#3e7bfa' };

const REGION_GAIN = [0.10, 0.14, 0.14, 0.10];
const REGION_MIN = 0.12;

function spline(xs: number[], ys: number[]): (x: number) => number {
  const n = xs.length;
  if (n < 2) return (x) => x;
  const sec = xs.slice(1).map((x, k) => (ys[k + 1] - ys[k]) / Math.max(x - xs[k], 1e-12));
  const tan = xs.map((_, k) => (k === 0 ? sec[0] : k === n - 1 ? sec[n - 2] : sec[k - 1] * sec[k] <= 0 ? 0 : (sec[k - 1] + sec[k]) / 2));
  sec.forEach((s, k) => {
    if (s === 0) { tan[k] = 0; tan[k + 1] = 0; return; }
    const a = tan[k] / s, b = tan[k + 1] / s, r = a * a + b * b;
    if (r > 9) { const f = 3 / Math.sqrt(r); tan[k] = f * a * s; tan[k + 1] = f * b * s; }
  });
  return (x) => {
    const t = Math.min(Math.max(x, xs[0]), xs[n - 1]);
    let k = 0;
    while (k < n - 2 && t >= xs[k + 1]) k += 1;
    const h = Math.max(xs[k + 1] - xs[k], 1e-12), s = (t - xs[k]) / h, s2 = s * s, s3 = s2 * s;
    return (2 * s3 - 3 * s2 + 1) * ys[k] + (s3 - 2 * s2 + s) * h * tan[k] + (-2 * s3 + 3 * s2) * ys[k + 1] + (s3 - s2) * h * tan[k + 1];
  };
}

function monotone(points: Pts): (x: number) => number {
  const p = points.filter((q) => Number.isFinite(q[0]) && Number.isFinite(q[1])).map((q) => [Math.min(1, Math.max(0, q[0])), Math.min(1, Math.max(0, q[1]))] as [number, number]).sort((a, b) => a[0] - b[0]);
  const kept = p.filter((q, k) => k === 0 || q[0] - p[k - 1][0] > 1e-6);
  const f = spline(kept.map((q) => q[0]), kept.map((q) => q[1]));
  return (x) => Math.min(1, Math.max(0, f(x)));
}

function parametric(c: Record<string, number>): (x: number) => number {
  const val = (k: string, d: number) => (Number.isFinite(c[k]) ? c[k] : d);
  const s1 = Math.min(Math.max(val('splitShadows', 25), 10), 70) / 100;
  const s2 = Math.max(Math.min(Math.max(val('splitMid', 50), 20), 80) / 100, s1 + 0.02);
  const s3 = Math.min(Math.max(Math.min(Math.max(val('splitHighlights', 75), 30), 90) / 100, s2 + 0.02), 0.98);
  const xs = [0, s1 / 2, (s1 + s2) / 2, (s2 + s3) / 2, (s3 + 1) / 2, 1];
  const amounts = [val('shadows', 0), val('darks', 0), val('lights', 0), val('highlights', 0)].map((v) => v / 100);
  const ys = [0, ...xs.slice(1, 5).map((x, k) => x + amounts[k] * REGION_GAIN[k]), 1];
  for (let k = 1; k < 5; k += 1) ys[k] = Math.min(Math.max(ys[k], ys[k - 1] + REGION_MIN * (xs[k] - xs[k - 1])), 1 - REGION_MIN * (1 - xs[k]));
  const f = spline(xs, ys);
  return (x) => Math.min(1, Math.max(0, f(x)));
}

export interface CurveSource {
  get(): Record<string, unknown>;
  set(curve: Record<string, unknown>, phase: 'drag' | 'end', label: string): void;
}

const GLOBAL: CurveSource = {
  get: () => (develop.read('curve') as Record<string, unknown>) ?? {},
  set: (curve, phase, label) => develop.patch('curve', curve, phase, label),
};

export class CurveEditor {
  readonly root: HTMLElement;
  private readonly canvas: HTMLCanvasElement;
  channel: Channel | 'parametric' = 'parametric';
  private drag = -1;
  private hist: Uint32Array | null = null;

  constructor(private readonly source: CurveSource = GLOBAL, regions = true) {
    if (!regions) this.channel = 'master';
    this.root = el(`<div class="fl-curve${regions ? '' : ' is-local'}"><div class="cv-seg fl-curve-tabs">${regions ? '<button type="button" data-ch="parametric" title="Parametric curve">Region</button>' : ''}<button type="button" data-ch="master" title="Point curve">Point</button><button type="button" data-ch="red" title="Red channel">R</button><button type="button" data-ch="green" title="Green channel">G</button><button type="button" data-ch="blue" title="Blue channel">B</button></div><canvas class="fl-curve-canvas" width="560" height="560"></canvas><div class="fl-curve-hint">Click to add a point, drag to shape, double-click a point to remove it</div></div>`);
    this.canvas = q<HTMLCanvasElement>(this.root, 'canvas');
    q(this.root, '.fl-curve-tabs').addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-ch]');
      if (!b) return;
      this.channel = b.dataset.ch as Channel | 'parametric';
      this.sync();
    });
    this.wire();
  }

  setHistogram(bins: Uint32Array | null): void { this.hist = bins; this.draw(); }

  private points(): Pts {
    if (this.channel === 'parametric') return [];
    const v = getPath(this.source.get(), this.channel) as Pts | undefined;
    return v && v.length >= 2 ? v.map((p) => [p[0], p[1]] as [number, number]) : [[0, 0], [1, 1]];
  }

  private write(pts: Pts, phase: 'drag' | 'end'): void {
    const ch = this.channel as Channel;
    const sorted = pts.slice().sort((a, b) => a[0] - b[0]).map((p) => [Number(p[0].toFixed(4)), Number(p[1].toFixed(4))]);
    const identity = sorted.length === 2 && sorted[0][0] === 0 && sorted[0][1] === 0 && sorted[1][0] === 1 && sorted[1][1] === 1;
    const curve = clone(this.source.get());
    if (identity) delete curve[ch]; else curve[ch] = sorted;
    this.source.set(curve, phase, `Point Curve ${ch === 'master' ? '' : ch}`.trim());
  }

  sync(): void {
    for (const b of Array.from(this.root.querySelectorAll<HTMLElement>('[data-ch]'))) setClass(b, 'is-on', b.dataset.ch === this.channel);
    setClass(this.root, 'is-parametric', this.channel === 'parametric');
    this.draw();
  }

  private toXY(e: PointerEvent): [number, number] {
    const r = this.canvas.getBoundingClientRect();
    return [Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)), Math.max(0, Math.min(1, 1 - (e.clientY - r.top) / r.height))];
  }

  private wire(): void {
    this.canvas.addEventListener('pointerdown', (e) => {
      if (this.channel === 'parametric' || e.button !== 0) return;
      const [x, y] = this.toXY(e);
      const pts = this.points();
      let best = -1, bd = 0.04;
      pts.forEach((p, i) => { const d = Math.hypot(p[0] - x, p[1] - y); if (d < bd) { bd = d; best = i; } });
      if (best < 0) {
        pts.push([x, y]);
        pts.sort((a, b) => a[0] - b[0]);
        best = pts.findIndex((p) => p[0] === x && p[1] === y);
        this.write(pts, 'drag');
      }
      this.drag = best;
      this.canvas.setPointerCapture(e.pointerId);
    });
    this.canvas.addEventListener('pointermove', (e) => {
      if (this.drag < 0) return;
      const pts = this.points();
      if (this.drag >= pts.length) return;
      let [x, y] = this.toXY(e);
      const lo = this.drag > 0 ? pts[this.drag - 1][0] + 0.01 : 0;
      const hi = this.drag < pts.length - 1 ? pts[this.drag + 1][0] - 0.01 : 1;
      if (this.drag === 0) x = Math.min(x, hi);
      else if (this.drag === pts.length - 1) x = Math.max(x, lo);
      else x = Math.max(lo, Math.min(hi, x));
      pts[this.drag] = [x, y];
      this.write(pts, 'drag');
      this.draw();
    });
    const up = () => {
      if (this.drag < 0) return;
      this.drag = -1;
      this.write(this.points(), 'end');
    };
    this.canvas.addEventListener('pointerup', up);
    this.canvas.addEventListener('pointercancel', up);
    this.canvas.addEventListener('dblclick', (e) => {
      if (this.channel === 'parametric') return;
      const [x, y] = this.toXY(e as unknown as PointerEvent);
      const pts = this.points();
      const i = pts.findIndex((p) => Math.hypot(p[0] - x, p[1] - y) < 0.04);
      if (i > 0 && i < pts.length - 1) { pts.splice(i, 1); this.write(pts, 'end'); }
      else if (i === -1 && pts.length > 2) { this.write([[0, 0], [1, 1]], 'end'); }
    });
  }

  draw(): void {
    const c = this.canvas.getContext('2d');
    if (!c) return;
    const W = this.canvas.width, H = this.canvas.height;
    c.clearRect(0, 0, W, H);
    c.fillStyle = 'rgba(255,255,255,0.03)';
    c.fillRect(0, 0, W, H);
    if (this.hist) {
      let max = 1;
      for (const v of this.hist) max = Math.max(max, v);
      c.fillStyle = 'rgba(255,255,255,0.08)';
      c.beginPath();
      c.moveTo(0, H);
      this.hist.forEach((v, i) => c.lineTo((i / (this.hist!.length - 1)) * W, H - Math.sqrt(v / max) * H * 0.9));
      c.lineTo(W, H);
      c.fill();
    }
    c.strokeStyle = 'rgba(255,255,255,0.1)';
    c.lineWidth = 2;
    for (let i = 1; i < 4; i += 1) {
      c.beginPath(); c.moveTo((i / 4) * W, 0); c.lineTo((i / 4) * W, H); c.stroke();
      c.beginPath(); c.moveTo(0, (i / 4) * H); c.lineTo(W, (i / 4) * H); c.stroke();
    }
    c.beginPath(); c.moveTo(0, H); c.lineTo(W, 0); c.strokeStyle = 'rgba(255,255,255,0.15)'; c.stroke();
    const curve = this.source.get() as Record<string, number>;
    const par = parametric(curve);
    const draw = (fn: (x: number) => number, color: string, width: number) => {
      c.beginPath();
      for (let i = 0; i <= 128; i += 1) { const x = i / 128; const y = fn(x); if (i === 0) c.moveTo(x * W, H - y * H); else c.lineTo(x * W, H - y * H); }
      c.strokeStyle = color;
      c.lineWidth = width;
      c.stroke();
    };
    if (this.channel === 'parametric') {
      draw(par, COLORS.master, 4);
      c.fillStyle = 'rgba(255,255,255,0.25)';
      for (const k of ['splitShadows', 'splitMid', 'splitHighlights']) {
        const x = ((curve[k] as number | undefined) ?? { splitShadows: 25, splitMid: 50, splitHighlights: 75 }[k] ?? 50) / 100;
        c.fillRect(x * W - 1, H - 14, 2, 14);
      }
      return;
    }
    const pts = this.points();
    const fn = monotone(pts);
    draw((x) => fn(x), COLORS[this.channel], 4);
    c.fillStyle = COLORS[this.channel];
    for (const p of pts) { c.beginPath(); c.arc(p[0] * W, H - p[1] * H, 9, 0, Math.PI * 2); c.fill(); }
  }
}
