import { api } from '../../io/api';
import { develop } from '../../state/develop';
import type { Photo } from '../../state/library';
import { el, pendingClass, q, setClass, setHidden, setStyleVar, type Disposer } from '../../ui/dom';
import { icon } from '../../ui/icons';

export interface Geo { norm: number[]; w: number; h: number; ow: number; oh: number; rect: number[]; angle: number; flipH: boolean; flipV: boolean }
export type Zoom = 'fit' | 'fill' | number;
export type Compare = 'off' | 'before' | 'lr' | 'tb' | 'split';

export interface Pt { sx: number; sy: number; u: number; v: number; nx: number; ny: number; e: PointerEvent }

export interface Tool {
  id: string;
  cursor?: string;
  uncropped?: boolean;
  down?(p: Pt): boolean | void;
  move?(p: Pt): void;
  up?(p: Pt): void;
  hover?(p: Pt | null): void;
  draw?(ctx: CanvasRenderingContext2D, view: DevelopView): void;
  overlay?(): Record<string, unknown> | null;
  key?(e: KeyboardEvent, combo: string): boolean;
}

const MAX_LONG = 2560;

class Img {
  readonly el: HTMLImageElement;
  url = '';
  constructor(cls: string) { this.el = el<HTMLImageElement>(`<img class="${cls}" alt="" draggable="false">`); }
  async swap(blob: Blob): Promise<boolean> {
    const url = URL.createObjectURL(blob);
    const probe = new Image();
    probe.decoding = 'async';
    probe.src = url;
    try { await probe.decode(); } catch { URL.revokeObjectURL(url); return false; }
    const old = this.url;
    this.url = url;
    this.el.src = url;
    if (old) URL.revokeObjectURL(old);
    return true;
  }
}

export class DevelopView {
  readonly root: HTMLElement;
  private readonly box: HTMLElement;
  private readonly beforeBox: HTMLElement;
  private readonly base = new Img('fl-dv-img');
  private readonly region = new Img('fl-dv-region');
  private readonly before = new Img('fl-dv-img');
  private readonly canvas: HTMLCanvasElement;
  private readonly spin: HTMLElement;
  private readonly tag: HTMLElement;
  photo: Photo | null = null;
  geo: Geo | null = null;
  zoom: Zoom = 'fit';
  cx = 0.5;
  cy = 0.5;
  compare: Compare = 'off';
  split = 0.5;
  clipping = false;
  tool: Tool | null = null;
  private inflight = false;
  private queued = false;
  private dragging = false;
  private seq = 0;
  private regionSeq = 0;
  private regionTimer = 0;
  private beforeFor = '';
  private pending: Disposer | null = null;
  private aspect = 1.5;
  onRendered: ((img: HTMLImageElement) => void) | null = null;
  onZoom: ((z: Zoom) => void) | null = null;
  onError: ((err: unknown) => void) | null = null;

  constructor() {
    this.root = el(`<div class="fl-dv"><div class="fl-dv-before" hidden><div class="fl-dv-tag">Before</div></div><div class="fl-dv-box"><div class="fl-dv-zoomclip"></div></div><canvas class="fl-dv-canvas"></canvas><div class="fl-dv-split" hidden></div><div class="fl-dv-tag fl-dv-aftertag" hidden>After</div><div class="fl-viewer-spin">${icon('loading', 18)}</div></div>`);
    this.box = q(this.root, '.fl-dv-box');
    this.beforeBox = q(this.root, '.fl-dv-before');
    this.canvas = q<HTMLCanvasElement>(this.root, '.fl-dv-canvas');
    this.spin = q(this.root, '.fl-viewer-spin');
    this.tag = q(this.root, '.fl-dv-aftertag');
    this.box.prepend(this.base.el);
    q(this.root, '.fl-dv-zoomclip').appendChild(this.region.el);
    this.beforeBox.appendChild(this.before.el);
    this.region.el.hidden = true;
    new ResizeObserver(() => { this.place(); this.schedule(); }).observe(this.root);
    this.pointer();
  }

  setPhoto(p: Photo | null): void {
    const changed = p?.id !== this.photo?.id;
    this.photo = p;
    if (changed) {
      this.cx = 0.5;
      this.cy = 0.5;
      this.geo = null;
      this.beforeFor = '';
      this.region.el.hidden = true;
      this.aspect = p?.a || 1.5;
      this.place();
    }
    this.schedule();
  }

  setTool(t: Tool | null): void {
    const was = this.tool?.uncropped;
    this.tool = t;
    this.root.style.cursor = t?.cursor ?? '';
    if (!!was !== !!t?.uncropped) this.schedule();
    this.draw();
  }

  setDragging(on: boolean): void { this.dragging = on; }

  setZoom(z: Zoom, at?: { x: number; y: number }): void {
    if (at) { this.cx = at.x; this.cy = at.y; }
    this.zoom = z;
    this.place();
    this.scheduleRegion(60);
    this.onZoom?.(z);
  }

  setCompare(c: Compare): void {
    this.compare = c;
    this.beforeFor = '';
    this.place();
    this.schedule();
  }

  private stageRect(): { w: number; h: number } {
    return { w: this.root.clientWidth || 1, h: this.root.clientHeight || 1 };
  }

  private panes(): { x: number; y: number; w: number; h: number; bx: number; by: number } {
    const { w, h } = this.stageRect();
    if (this.compare === 'lr') return { x: w / 2 + 4, y: 0, w: w / 2 - 4, h, bx: 0, by: 0 };
    if (this.compare === 'tb') return { x: 0, y: h / 2 + 4, w, h: h / 2 - 4, bx: 0, by: 0 };
    return { x: 0, y: 0, w, h, bx: 0, by: 0 };
  }

  native(): { w: number; h: number } {
    const g = this.geo;
    const info = develop.info;
    if (!g) {
      const long = Math.max(this.photo?.w ?? 1500, this.photo?.h ?? 1000);
      const a = this.aspect || 1.5;
      return a >= 1 ? { w: long, h: long / a } : { w: long * a, h: long };
    }
    const k = info ? Math.max(info.width ?? g.ow, info.height ?? g.oh) / Math.max(g.ow, g.oh) : 1;
    const rw = (g.rect[2] - g.rect[0]) * g.ow * k;
    const rh = (g.rect[3] - g.rect[1]) * g.oh * k;
    return this.tool?.uncropped ? { w: g.ow * k, h: g.oh * k } : { w: rw, h: rh };
  }

  scale(): number {
    const n = this.native();
    const p = this.panes();
    const pad = this.zoom === 'fit' ? 24 : 0;
    if (this.zoom === 'fit') return Math.min((p.w - pad) / n.w, (p.h - pad) / n.h);
    if (this.zoom === 'fill') return Math.max(p.w / n.w, p.h / n.h);
    return this.zoom;
  }

  displayRect(): { x: number; y: number; w: number; h: number } {
    const n = this.native();
    const s = this.scale();
    const p = this.panes();
    const dw = n.w * s, dh = n.h * s;
    let x = p.x + (p.w - dw) / 2;
    let y = p.y + (p.h - dh) / 2;
    if (dw > p.w) x = Math.min(p.x, Math.max(p.x + p.w - dw, p.x + p.w / 2 - this.cx * dw));
    if (dh > p.h) y = Math.min(p.y, Math.max(p.y + p.h - dh, p.y + p.h / 2 - this.cy * dh));
    return { x, y, w: dw, h: dh };
  }

  private place(): void {
    const r = this.displayRect();
    for (const [k, v] of [['--x', r.x], ['--y', r.y], ['--w', r.w], ['--h', r.h]] as Array<[string, number]>) setStyleVar(this.box, k, `${Math.round(v)}px`);
    const p = this.panes();
    const before = this.compare === 'lr' || this.compare === 'tb' || this.compare === 'before' || this.compare === 'split';
    setHidden(this.beforeBox, !before);
    if (before) {
      const { w, h } = this.stageRect();
      const bp = this.compare === 'lr' ? { x: 0, y: 0, w: w / 2 - 4, h } : this.compare === 'tb' ? { x: 0, y: 0, w, h: h / 2 - 4 } : { x: p.x, y: p.y, w: p.w, h: p.h };
      const bx = bp.x + (r.x - p.x) * (bp.w / p.w) + 0;
      const by = bp.y + (r.y - p.y) * (bp.h / p.h) + 0;
      const sameSize = this.compare === 'before' || this.compare === 'split';
      setStyleVar(this.beforeBox, '--x', `${Math.round(sameSize ? r.x : bx)}px`);
      setStyleVar(this.beforeBox, '--y', `${Math.round(sameSize ? r.y : by)}px`);
      setStyleVar(this.beforeBox, '--w', `${Math.round(r.w)}px`);
      setStyleVar(this.beforeBox, '--h', `${Math.round(r.h)}px`);
      setStyleVar(this.beforeBox, '--clip', this.compare === 'split' ? `inset(0 ${Math.round(r.w * (1 - this.split))}px 0 0)` : 'none');
    }
    setClass(this.root, 'is-before-only', this.compare === 'before');
    setHidden(q(this.root, '.fl-dv-split'), this.compare !== 'split');
    if (this.compare === 'split') setStyleVar(q(this.root, '.fl-dv-split'), 'left', `${Math.round(r.x + r.w * this.split)}px`);
    setHidden(this.tag, !(this.compare === 'lr' || this.compare === 'tb' || this.compare === 'split'));
    const { w, h } = this.stageRect();
    setClass(this.root, 'is-zoomed', r.w > p.w + 1 || r.h > p.h + 1);
    if (this.canvas.width !== Math.round(w * devicePixelRatio) || this.canvas.height !== Math.round(h * devicePixelRatio)) {
      this.canvas.width = Math.round(w * devicePixelRatio);
      this.canvas.height = Math.round(h * devicePixelRatio);
    }
    this.placeRegion();
    this.draw();
  }

  schedule(): void {
    if (!this.photo) return;
    if (this.inflight) { this.queued = true; return; }
    void this.run();
  }

  private renderLong(): number {
    const r = this.displayRect();
    const p = this.panes();
    const dpr = Math.min(2, devicePixelRatio || 1);
    const n = this.native();
    const shown = this.zoom === 'fit' ? Math.max(r.w, r.h) : Math.max(p.w, p.h);
    const long = Math.min(shown * dpr, Math.max(n.w, n.h), MAX_LONG) * (this.dragging ? 0.6 : 1);
    return Math.round(Math.max(320, long));
  }

  private body(extra: Record<string, unknown> = {}): Record<string, unknown> {
    const overlay: Record<string, unknown> = {};
    if (this.clipping) overlay.clipping = true;
    const t = this.tool?.overlay?.();
    if (t) Object.assign(overlay, t);
    return { settings: develop.settings, view: 'develop', crop: !this.tool?.uncropped, quality: this.dragging ? 80 : 90, overlay: Object.keys(overlay).length ? overlay : undefined, ...extra };
  }

  private async run(): Promise<void> {
    const p = this.photo;
    if (!p) return;
    this.inflight = true;
    this.queued = false;
    const seq = ++this.seq;
    this.pending?.();
    this.pending = pendingClass(this.spin, 400);
    try {
      const r = await fetch(api.url(`/api/photos/${p.id}/render`), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.body({ long: this.renderLong() })) });
      if (!r.ok) throw new Error(`render ${r.status}`);
      const geo = JSON.parse(r.headers.get('X-Geometry') || 'null') as Geo | null;
      const blob = await r.blob();
      if (seq === this.seq && p.id === this.photo?.id) {
        if (await this.base.swap(blob)) {
          if (geo) this.geo = geo;
          this.aspect = geo ? geo.w / Math.max(1, geo.h) : this.aspect;
          setClass(this.base.el, 'is-loaded', true);
          this.place();
          this.onRendered?.(this.base.el);
          if (!this.dragging) this.scheduleRegion(80);
        }
      }
      if (this.compare !== 'off' && this.beforeFor !== `${p.id}:${p.rev}`) void this.renderBefore(p);
    } catch (err) {
      this.onError?.(err);
    } finally {
      this.pending?.();
      this.pending = null;
      this.inflight = false;
      if (this.queued) void this.run();
    }
  }

  private async renderBefore(p: Photo): Promise<void> {
    this.beforeFor = `${p.id}:${p.rev}`;
    try {
      const r = await fetch(api.url(`/api/photos/${p.id}/render`), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ defaults: true, long: this.renderLong(), view: 'before', crop: true }) });
      if (r.ok) await this.before.swap(await r.blob());
    } catch { this.beforeFor = ''; }
  }

  private scheduleRegion(ms: number): void {
    window.clearTimeout(this.regionTimer);
    this.regionTimer = window.setTimeout(() => void this.renderRegion(), ms);
  }

  private visibleUV(): [number, number, number, number] | null {
    const r = this.displayRect();
    const p = this.panes();
    const u0 = Math.max(0, (p.x - r.x) / r.w), v0 = Math.max(0, (p.y - r.y) / r.h);
    const u1 = Math.min(1, (p.x + p.w - r.x) / r.w), v1 = Math.min(1, (p.y + p.h - r.y) / r.h);
    if (u1 <= u0 || v1 <= v0) return null;
    return [u0, v0, u1, v1];
  }

  private regionRect: [number, number, number, number] | null = null;
  private regionFull: [number, number] | null = null;

  private async renderRegion(): Promise<void> {
    const p = this.photo;
    if (!p || this.tool?.uncropped) { this.region.el.hidden = true; return; }
    const r = this.displayRect();
    const baseW = this.base.el.naturalWidth || 1;
    const shown = r.w * (devicePixelRatio || 1);
    if (shown <= baseW * 1.05) { this.region.el.hidden = true; return; }
    const uv = this.visibleUV();
    if (!uv) return;
    const n = this.native();
    const outLong = Math.round(Math.max(n.w, n.h) * Math.min(this.scale() * (devicePixelRatio || 1), 1));
    const seq = ++this.regionSeq;
    try {
      const res = await fetch(api.url(`/api/photos/${p.id}/render`), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.body({ long: outLong, region: uv, quality: 92 })) });
      if (!res.ok || seq !== this.regionSeq) return;
      const rect = (res.headers.get('X-Region') || '').split(',').map(Number);
      const full = (res.headers.get('X-Full') || '').split(',').map(Number);
      const blob = await res.blob();
      if (seq !== this.regionSeq || p.id !== this.photo?.id) return;
      if (await this.region.swap(blob)) {
        this.regionRect = [rect[0], rect[1], rect[2], rect[3]];
        this.regionFull = [full[0], full[1]];
        this.region.el.hidden = false;
        this.placeRegion();
      }
    } catch { return; }
  }

  private placeRegion(): void {
    const rr = this.regionRect, f = this.regionFull;
    if (!rr || !f || this.region.el.hidden) return;
    const r = this.displayRect();
    const sx = r.w / f[0], sy = r.h / f[1];
    const s = this.region.el.style;
    s.left = `${(rr[0] * sx).toFixed(2)}px`;
    s.top = `${(rr[1] * sy).toFixed(2)}px`;
    s.width = `${((rr[2] - rr[0]) * sx).toFixed(2)}px`;
    s.height = `${((rr[3] - rr[1]) * sy).toFixed(2)}px`;
  }

  invalidateRegion(): void { this.regionSeq += 1; this.region.el.hidden = true; }

  toPt(e: PointerEvent | MouseEvent): Pt {
    const rect = this.root.getBoundingClientRect();
    const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
    const r = this.displayRect();
    const u = (sx - r.x) / Math.max(1, r.w), v = (sy - r.y) / Math.max(1, r.h);
    const [nx, ny] = this.uvToNorm(u, v);
    return { sx, sy, u, v, nx, ny, e: e as PointerEvent };
  }

  uvToNorm(u: number, v: number): [number, number] {
    const g = this.geo;
    if (!g) return [u, v];
    const x = u * g.w, y = v * g.h, m = g.norm;
    return [m[0] * x + m[1] * y + m[2], m[3] * x + m[4] * y + m[5]];
  }

  normToStage(nx: number, ny: number): [number, number] {
    const g = this.geo;
    const r = this.displayRect();
    if (!g) return [r.x + nx * r.w, r.y + ny * r.h];
    const m = g.norm;
    const det = m[0] * m[4] - m[1] * m[3];
    const dx = nx - m[2], dy = ny - m[5];
    const x = (m[4] * dx - m[1] * dy) / det, y = (-m[3] * dx + m[0] * dy) / det;
    return [r.x + (x / g.w) * r.w, r.y + (y / g.h) * r.h];
  }

  pxPerLong(): number {
    const g = this.geo;
    const r = this.displayRect();
    if (!g) return r.w;
    return (r.w * Math.max(g.ow, g.oh)) / Math.max(1e-9, (g.rect[2] - g.rect[0]) * g.ow);
  }

  normToLong(nx: number, ny: number): [number, number] {
    const g = this.geo;
    if (!g) return [nx, ny];
    const l = Math.max(g.ow, g.oh);
    return [(nx * g.ow) / l, (ny * g.oh) / l];
  }

  longToNorm(lx: number, ly: number): [number, number] {
    const g = this.geo;
    if (!g) return [lx, ly];
    const l = Math.max(g.ow, g.oh);
    return [(lx * l) / g.ow, (ly * l) / g.oh];
  }

  draw(): void {
    const c = this.canvas.getContext('2d');
    if (!c) return;
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.clearRect(0, 0, this.canvas.width, this.canvas.height);
    c.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
    this.tool?.draw?.(c, this);
  }

  private pointer(): void {
    let pan: { x: number; y: number; cx: number; cy: number } | null = null;
    let moved = false;
    let toolDown = false;
    let splitDrag = false;
    this.root.addEventListener('pointerdown', (e) => {
      if (e.button !== 0 || !this.photo) return;
      this.root.setPointerCapture(e.pointerId);
      moved = false;
      if ((e.target as HTMLElement).closest('.fl-dv-split')) { splitDrag = true; return; }
      const pt = this.toPt(e);
      if (this.tool?.down && !e.getModifierState('Space') && this.tool.down(pt) !== false) { toolDown = true; return; }
      pan = { x: e.clientX, y: e.clientY, cx: this.cx, cy: this.cy };
    });
    this.root.addEventListener('pointermove', (e) => {
      if (splitDrag) {
        const r = this.displayRect();
        const rect = this.root.getBoundingClientRect();
        this.split = Math.max(0, Math.min(1, (e.clientX - rect.left - r.x) / r.w));
        this.place();
        return;
      }
      if (toolDown) { this.tool?.move?.(this.toPt(e)); this.draw(); return; }
      if (!pan) { this.tool?.hover?.(this.toPt(e)); return; }
      const dx = e.clientX - pan.x, dy = e.clientY - pan.y;
      if (!moved && Math.hypot(dx, dy) < 4) return;
      moved = true;
      if (!this.root.classList.contains('is-zoomed')) return;
      const r = this.displayRect();
      this.cx = Math.min(1, Math.max(0, pan.cx - dx / r.w));
      this.cy = Math.min(1, Math.max(0, pan.cy - dy / r.h));
      setClass(this.root, 'is-panning', true);
      this.place();
      this.scheduleRegion(120);
    });
    const up = (e: PointerEvent) => {
      if (splitDrag) { splitDrag = false; return; }
      if (toolDown) { toolDown = false; this.tool?.up?.(this.toPt(e)); this.draw(); return; }
      if (!pan) return;
      pan = null;
      setClass(this.root, 'is-panning', false);
      if (!moved && !this.tool) this.toggleZoom(e);
    };
    this.root.addEventListener('pointerup', up);
    this.root.addEventListener('pointercancel', up);
    this.root.addEventListener('pointerleave', () => this.tool?.hover?.(null));
    this.root.addEventListener('wheel', (e) => {
      if (!this.photo || !(e.ctrlKey || e.metaKey)) return;
      e.preventDefault();
      const r = this.displayRect();
      const rect = this.root.getBoundingClientRect();
      const at = { x: (e.clientX - rect.left - r.x) / r.w, y: (e.clientY - rect.top - r.y) / r.h };
      this.setZoom(Math.max(0.03, Math.min(8, this.scale() * Math.exp(-e.deltaY * 0.0025))), at);
    }, { passive: false });
  }

  toggleZoom(e?: MouseEvent): void {
    if (this.zoom === 'fit' || this.zoom === 'fill') {
      const r = this.displayRect();
      const rect = this.root.getBoundingClientRect();
      const at = e ? { x: (e.clientX - rect.left - r.x) / r.w, y: (e.clientY - rect.top - r.y) / r.h } : undefined;
      this.setZoom(1, at);
    } else this.setZoom('fit');
  }
}
