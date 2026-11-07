import { develop } from '../../../demo/src/shims/develop';
import type { DevelopView } from '../../../demo/src/develop-view';
import { el } from '../../../frontend/src/ui/dom';
import { geoOf, toNorm, toPixel, type Geo } from './masks/geo';
import { maskAlpha } from './masks/eval';
import { baseOf, sampleLab, type Base } from './masks/shapes';
import type { Vec } from './masks/types';
import { maskState as st } from './mask-state';
import { Renderer } from './render-masks';

const OVERLAY_LONG = 640;
const HANDLE = 6;
const HIT = 11;

type Drag =
  | { kind: 'create'; shape: 'linear' | 'radial'; at: Vec; index: number }
  | { kind: 'linear'; handle: 'a' | 'b' | 'move'; from: Vec; start: Vec; end: Vec }
  | { kind: 'radial'; handle: 'c' | 'x' | 'y'; from: Vec; center: Vec; rx: number; ry: number }
  | { kind: 'stroke'; points: Vec[]; done: unknown[] };

const round = (v: number): number => Math.round(v * 1e4) / 1e4;

export class MaskOverlay {
  private readonly canvas = el<HTMLCanvasElement>('<canvas class="fl-mask-overlay" width="4" height="4" aria-hidden="true"></canvas>');
  private readonly tint = document.createElement('canvas');
  private readonly renderer = new Renderer();
  private raf = 0;
  private drag: Drag | null = null;
  private hover: Vec | null = null;
  private box = { x: 0, y: 0, w: 1, h: 1 };
  private tintKey = '';
  private base: { key: string; info: Base } | null = null;

  constructor(private readonly view: DevelopView) {
    view.root.appendChild(this.canvas);
    new ResizeObserver(() => this.refresh()).observe(view.root);
    develop.listen(() => this.refresh());
    st.listen(() => this.refresh());
    const root = view.root;
    root.addEventListener('pointerdown', (e) => this.down(e), true);
    root.addEventListener('pointermove', (e) => this.move(e), true);
    root.addEventListener('pointerup', (e) => this.up(e), true);
    root.addEventListener('pointercancel', (e) => this.up(e), true);
    root.addEventListener('pointerleave', () => { this.hover = null; this.refresh(); });
  }

  refresh(): void {
    if (this.raf) return;
    this.raf = requestAnimationFrame(() => { this.raf = 0; this.draw(); });
  }

  private live(): boolean {
    return st.active && !!develop.item && this.view.tool === 'none' && this.view.mode !== 'before';
  }

  private place(): boolean {
    const b = this.view.root.querySelector<HTMLElement>('.fl-dv-box');
    if (!b) return false;
    const r = b.getBoundingClientRect(), p = this.view.root.getBoundingClientRect();
    this.box = { x: r.left - p.left, y: r.top - p.top, w: Math.max(1, r.width), h: Math.max(1, r.height) };
    return true;
  }

  private geo(): Geo | null {
    const item = develop.item;
    if (!item) return null;
    return geoOf(item.src.w, item.src.h, develop.settings, Math.max(2, Math.round(this.box.w)), Math.max(2, Math.round(this.box.h)));
  }

  private baseInfo(): Base | null {
    const item = develop.item;
    if (!item) return null;
    const key = `${item.src.id}|${JSON.stringify({ ...develop.settings, masks: undefined })}`;
    if (this.base?.key === key) return this.base.info;
    const r = this.renderer.globalOnly(item.src, develop.settings, OVERLAY_LONG);
    const info = baseOf(r.rgba, r.w, r.h);
    this.base = { key, info };
    return info;
  }

  private screen(g: Geo, n: Vec): Vec {
    const p = toPixel(g, n[0], n[1]);
    return [this.box.x + p[0], this.box.y + p[1]];
  }

  private fromEvent(e: PointerEvent): { norm: Vec; sx: number; sy: number } | null {
    const g = this.geo();
    if (!g || !this.place()) return null;
    const r = this.view.root.getBoundingClientRect();
    const sx = e.clientX - r.left, sy = e.clientY - r.top;
    return { norm: toNorm(g, sx - this.box.x, sy - this.box.y), sx, sy };
  }

  private draw(): void {
    const c = this.canvas;
    const w = this.view.root.clientWidth, h = this.view.root.clientHeight;
    if (c.width !== w) c.width = w;
    if (c.height !== h) c.height = h;
    const ctx = c.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, w, h);
    if (!this.live() || !this.place()) return;
    const g = this.geo();
    const { m, c: comp } = st.current();
    if (!g || !m) { this.cursor(ctx, g); return; }
    if (st.showOverlay) this.drawTint(ctx, m);
    if (comp && comp.shape.kind === 'linear') this.drawLinear(ctx, g, comp.shape);
    if (comp && comp.shape.kind === 'radial') this.drawRadial(ctx, g, comp.shape);
    this.cursor(ctx, g);
  }

  private drawTint(ctx: CanvasRenderingContext2D, m: ReturnType<typeof st.current>['m']): void {
    const base = this.baseInfo();
    const item = develop.item;
    if (!base || !item || !m) return;
    const key = `${this.base?.key}|${JSON.stringify(m)}`;
    if (key !== this.tintKey) {
      const g = geoOf(item.src.w, item.src.h, develop.settings, base.w, base.h);
      const a = maskAlpha(m, g, base);
      if (this.tint.width !== base.w) this.tint.width = base.w;
      if (this.tint.height !== base.h) this.tint.height = base.h;
      const img = new ImageData(base.w, base.h);
      for (let i = 0; i < a.length; i += 1) { img.data[i * 4] = 235; img.data[i * 4 + 1] = 40; img.data[i * 4 + 2] = 60; img.data[i * 4 + 3] = Math.round(a[i] * 0.5 * 255); }
      this.tint.getContext('2d')?.putImageData(img, 0, 0);
      this.tintKey = key;
    }
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(this.tint, this.box.x, this.box.y, this.box.w, this.box.h);
  }

  private pins(ctx: CanvasRenderingContext2D, pts: Vec[]): void {
    ctx.fillStyle = '#fff';
    ctx.strokeStyle = 'rgba(0,0,0,0.6)';
    ctx.lineWidth = 1;
    for (const [x, y] of pts) { ctx.fillRect(x - HANDLE / 2, y - HANDLE / 2, HANDLE, HANDLE); ctx.strokeRect(x - HANDLE / 2 + 0.5, y - HANDLE / 2 + 0.5, HANDLE, HANDLE); }
  }

  private line(ctx: CanvasRenderingContext2D, a: Vec, b: Vec, dash: number[], alpha = 0.95): void {
    ctx.setLineDash(dash);
    ctx.strokeStyle = `rgba(255,255,255,${alpha})`;
    ctx.lineWidth = 1.25;
    ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke();
    ctx.setLineDash([]);
  }

  private drawLinear(ctx: CanvasRenderingContext2D, g: Geo, s: Record<string, unknown>): void {
    const a = this.screen(g, s.start as Vec), b = this.screen(g, s.end as Vec);
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const len = Math.hypot(dx, dy) || 1;
    const nx = (-dy / len) * 400, ny = (dx / len) * 400;
    this.line(ctx, a, b, []);
    this.line(ctx, [a[0] - nx, a[1] - ny], [a[0] + nx, a[1] + ny], [6, 4], 0.7);
    this.line(ctx, [b[0] - nx, b[1] - ny], [b[0] + nx, b[1] + ny], [6, 4], 0.5);
    this.pins(ctx, [a, b]);
  }

  private radialGeometry(g: Geo, s: Record<string, unknown>): { c: Vec; ex: Vec; ey: Vec; rx: number; ry: number } {
    const cn = s.center as Vec;
    const rx = Number(s.rx), ry = Number(s.ry);
    const kx = g.long / g.ow, ky = g.long / g.oh;
    return { c: this.screen(g, cn), ex: this.screen(g, [cn[0] + rx * kx, cn[1]]), ey: this.screen(g, [cn[0], cn[1] + ry * ky]), rx, ry };
  }

  private drawRadial(ctx: CanvasRenderingContext2D, g: Geo, s: Record<string, unknown>): void {
    const r = this.radialGeometry(g, s);
    const rxp = Math.abs(r.ex[0] - r.c[0]), ryp = Math.abs(r.ey[1] - r.c[1]);
    ctx.strokeStyle = 'rgba(255,255,255,0.95)';
    ctx.lineWidth = 1.25;
    ctx.beginPath(); ctx.ellipse(r.c[0], r.c[1], Math.max(rxp, 1), Math.max(ryp, 1), 0, 0, Math.PI * 2); ctx.stroke();
    const feather = Math.min(100, Math.max(0, Number(s.feather ?? 50))) / 100;
    ctx.setLineDash([5, 4]);
    ctx.strokeStyle = 'rgba(255,255,255,0.55)';
    ctx.beginPath(); ctx.ellipse(r.c[0], r.c[1], Math.max(rxp * (1 - feather), 1), Math.max(ryp * (1 - feather), 1), 0, 0, Math.PI * 2); ctx.stroke();
    ctx.setLineDash([]);
    this.pins(ctx, [r.c, [r.c[0] + rxp, r.c[1]], [r.c[0] - rxp, r.c[1]], [r.c[0], r.c[1] + ryp], [r.c[0], r.c[1] - ryp]]);
  }

  private cursor(ctx: CanvasRenderingContext2D, g: Geo | null): void {
    if (!this.hover || !g) return;
    const { c } = st.current();
    const painting = c?.shape.kind === 'brush' && !st.pick;
    const [x, y] = this.hover;
    if (st.pick) {
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.arc(x, y, 8, 0, Math.PI * 2); ctx.stroke();
      return;
    }
    if (!painting) return;
    const r = (st.brush.size / 1000) * g.ppl;
    ctx.strokeStyle = 'rgba(255,255,255,0.9)'; ctx.lineWidth = 1.25;
    ctx.beginPath(); ctx.arc(x, y, Math.max(r, 2), 0, Math.PI * 2); ctx.stroke();
    ctx.setLineDash([3, 3]);
    ctx.strokeStyle = 'rgba(0,0,0,0.5)';
    ctx.beginPath(); ctx.arc(x, y, Math.max(r * (1 - st.brush.feather / 100), 1), 0, Math.PI * 2); ctx.stroke();
    ctx.setLineDash([]);
  }

  private hitLinear(g: Geo, s: Record<string, unknown>, sx: number, sy: number): 'a' | 'b' | 'move' | null {
    const a = this.screen(g, s.start as Vec), b = this.screen(g, s.end as Vec);
    if (Math.hypot(sx - a[0], sy - a[1]) < HIT) return 'a';
    if (Math.hypot(sx - b[0], sy - b[1]) < HIT) return 'b';
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const t = Math.min(1, Math.max(0, ((sx - a[0]) * dx + (sy - a[1]) * dy) / (dx * dx + dy * dy || 1)));
    return Math.hypot(sx - (a[0] + dx * t), sy - (a[1] + dy * t)) < HIT ? 'move' : null;
  }

  private hitRadial(g: Geo, s: Record<string, unknown>, sx: number, sy: number): 'c' | 'x' | 'y' | null {
    const r = this.radialGeometry(g, s);
    const rxp = Math.abs(r.ex[0] - r.c[0]), ryp = Math.abs(r.ey[1] - r.c[1]);
    if (Math.hypot(sx - (r.c[0] + rxp), sy - r.c[1]) < HIT || Math.hypot(sx - (r.c[0] - rxp), sy - r.c[1]) < HIT) return 'x';
    if (Math.hypot(sx - r.c[0], sy - (r.c[1] + ryp)) < HIT || Math.hypot(sx - r.c[0], sy - (r.c[1] - ryp)) < HIT) return 'y';
    const u = (sx - r.c[0]) / Math.max(rxp, 1), v = (sy - r.c[1]) / Math.max(ryp, 1);
    return u * u + v * v <= 1 ? 'c' : null;
  }

  private down(e: PointerEvent): void {
    if (e.button !== 0 || !this.live()) return;
    if ((e.target as HTMLElement).closest('.fl-dv-split')) return;
    const at = this.fromEvent(e);
    const g = this.geo();
    if (!at || !g) return;
    const inside = at.sx >= this.box.x && at.sx <= this.box.x + this.box.w && at.sy >= this.box.y && at.sy <= this.box.y + this.box.h;
    const { masks, m, c } = st.current();
    if (st.pending && inside) {
      this.drag = { kind: 'create', shape: st.pending, at: at.norm, index: -1 };
      this.capture(e);
      return;
    }
    if (st.pick && m && c?.shape.kind === 'colorRange' && inside) {
      const base = this.baseInfo();
      if (!base) return;
      const lab = sampleLab(base, Math.min(1, Math.max(0, (at.sx - this.box.x) / this.box.w)), Math.min(1, Math.max(0, (at.sy - this.box.y) / this.box.h)), 2);
      const prev = Array.isArray(c.shape.samples) && e.shiftKey ? (c.shape.samples as number[][]) : [];
      c.shape.samples = [...prev, lab.map((v) => round(v))];
      if (!e.shiftKey) st.pick = false;
      st.write(masks, 'end', 'Mask Color Range');
      st.changed();
      e.stopPropagation();
      e.preventDefault();
      return;
    }
    if (m && c?.shape.kind === 'brush' && inside) {
      this.drag = { kind: 'stroke', points: [at.norm], done: Array.isArray(c.shape.strokes) ? [...(c.shape.strokes as unknown[])] : [] };
      this.capture(e);
      this.stroke(false, e.altKey);
      return;
    }
    if (m && c?.shape.kind === 'linear') {
      const hit = this.hitLinear(g, c.shape, at.sx, at.sy);
      if (hit) { this.drag = { kind: 'linear', handle: hit, from: at.norm, start: [...(c.shape.start as Vec)], end: [...(c.shape.end as Vec)] }; this.capture(e); }
      return;
    }
    if (m && c?.shape.kind === 'radial') {
      const hit = this.hitRadial(g, c.shape, at.sx, at.sy);
      if (hit) { this.drag = { kind: 'radial', handle: hit, from: at.norm, center: [...(c.shape.center as Vec)], rx: Number(c.shape.rx), ry: Number(c.shape.ry) }; this.capture(e); }
    }
  }

  private capture(e: PointerEvent): void {
    this.view.root.setPointerCapture(e.pointerId);
    e.stopPropagation();
    e.preventDefault();
  }

  private stroke(end: boolean, erase: boolean): void {
    if (!this.drag || this.drag.kind !== 'stroke') return;
    const { masks, c } = st.current();
    if (!c) return;
    const b = st.brush;
    const stroke = { points: this.drag.points.map((p) => [round(p[0]), round(p[1])]), size: b.size / 1000, feather: b.feather, flow: b.flow, density: b.density, erase: b.erase || erase };
    c.shape.strokes = [...this.drag.done, stroke];
    st.write(masks, end ? 'end' : 'drag', 'Mask Brush Stroke');
  }

  private move(e: PointerEvent): void {
    const at = this.fromEvent(e);
    if (!this.live() || !at) { this.hover = null; return; }
    this.hover = [at.sx, at.sy];
    const d = this.drag;
    if (!d) {
      const { c } = st.current();
      const g = this.geo();
      let cursor = '';
      if (st.pending || st.pick) cursor = 'crosshair';
      else if (c?.shape.kind === 'brush') cursor = 'none';
      else if (g && c?.shape.kind === 'linear' && this.hitLinear(g, c.shape, at.sx, at.sy)) cursor = 'grab';
      else if (g && c?.shape.kind === 'radial' && this.hitRadial(g, c.shape, at.sx, at.sy)) cursor = 'grab';
      this.view.root.style.cursor = cursor;
      this.refresh();
      return;
    }
    e.stopPropagation();
    const g = this.geo();
    if (!g) return;
    const { masks, m, c } = st.current();
    if (d.kind === 'stroke') {
      const last = d.points[d.points.length - 1];
      const a = this.screen(g, last);
      if (Math.hypot(a[0] - at.sx, a[1] - at.sy) < 2) return;
      d.points.push(at.norm);
      this.stroke(false, e.altKey);
      return;
    }
    if (d.kind === 'create') {
      this.createDrag(d, at.norm);
      return;
    }
    if (!m || !c) return;
    const dx = at.norm[0] - d.from[0], dy = at.norm[1] - d.from[1];
    if (d.kind === 'linear') {
      c.shape.start = d.handle === 'b' ? d.start : [d.start[0] + dx, d.start[1] + dy];
      c.shape.end = d.handle === 'a' ? d.end : [d.end[0] + dx, d.end[1] + dy];
      st.write(masks, 'drag', 'Mask Gradient');
    } else {
      if (d.handle === 'c') c.shape.center = [d.center[0] + dx, d.center[1] + dy];
      if (d.handle === 'x') c.shape.rx = Math.max(0.005, Math.abs(at.norm[0] - d.center[0]) * (g.ow / g.long));
      if (d.handle === 'y') c.shape.ry = Math.max(0.005, Math.abs(at.norm[1] - d.center[1]) * (g.oh / g.long));
      st.write(masks, 'drag', 'Mask Radial');
    }
  }

  private createDrag(d: Extract<Drag, { kind: 'create' }>, to: Vec): void {
    const g = this.geo();
    if (!g) return;
    const masks = st.masks();
    const shape = st.shapeFor(d.shape);
    if (d.shape === 'linear') { shape.start = d.at; shape.end = to; }
    else {
      shape.center = d.at;
      shape.rx = Math.max(0.01, Math.abs(to[0] - d.at[0]) * (g.ow / g.long));
      shape.ry = Math.max(0.01, Math.abs(to[1] - d.at[1]) * (g.oh / g.long));
    }
    if (d.index >= 0 && masks[d.index]) masks[d.index].components[0].shape = shape;
    else {
      st.place(shape, 'new', masks);
      masks[st.sel].name = d.shape === 'linear' ? 'Linear Gradient' : 'Radial Gradient';
      d.index = st.sel;
    }
    st.write(masks, 'drag', 'Mask Gradient');
  }

  private up(e: PointerEvent): void {
    const d = this.drag;
    if (!d) return;
    this.drag = null;
    try { this.view.root.releasePointerCapture(e.pointerId); } catch { /* released already */ }
    if (d.kind === 'stroke') { this.stroke(true, e.altKey); st.changed(); return; }
    const masks = st.masks();
    if (d.kind === 'create') {
      const m = masks[d.index];
      if (m) {
        st.pending = '';
        st.write(masks, 'end', `Mask: ${m.name}`);
        st.changed();
      }
      return;
    }
    const { masks: cur } = st.current();
    st.write(cur, 'end', d.kind === 'linear' ? 'Mask Gradient' : 'Mask Radial');
    st.changed();
  }
}
