import { Frame } from './engine/geometry';
import { Renderer, solveWb } from './engine/render';
import { clone, type Dev } from './engine/settings';
import { binsOf, type Bins } from '../../frontend/src/ui/histogram';
import { el, q, setClass, setHidden, setStyleVar } from '../../frontend/src/ui/dom';
import { icon } from '../../frontend/src/ui/icons';
import { develop } from './shims/develop';

export type ViewMode = 'after' | 'before' | 'split';
export type Tool = 'none' | 'crop' | 'wb';
type Handle = 'move' | 'nw' | 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w';

const LOW_LONG = 520;
const FULL_CAP = 2400;

export class DevelopView {
  readonly root: HTMLElement;
  private readonly box: HTMLElement;
  private readonly beforeBox: HTMLElement;
  private readonly after: HTMLCanvasElement;
  private readonly beforeCanvas: HTMLCanvasElement;
  private readonly split: HTMLElement;
  private readonly overlay: HTMLCanvasElement;
  private readonly tagBefore: HTMLElement;
  private readonly tagAfter: HTMLElement;
  private readonly empty: HTMLElement;
  private readonly scratch = document.createElement('canvas');
  private readonly renderer = new Renderer();
  private readonly beforeRenderer = new Renderer();
  private beforeKey = '';
  private raf = 0;
  private wantLow = false;
  private lastW = 0;
  private lastH = 0;
  private boxRect = { x: 0, y: 0, w: 1, h: 1 };
  mode: ViewMode = 'after';
  splitAt = 0.5;
  zoom: 'fit' | 'full' = 'fit';
  clipping = false;
  tool: Tool = 'none';
  private cx = 0.5;
  private cy = 0.5;
  cropRect = [0, 0, 1, 1];
  cropAspect: number | null = null;
  onBins: ((b: Bins, clipS: number, clipH: number, w: number, h: number, ms: number) => void) | null = null;
  onCrop: ((rect: number[], phase: 'drag' | 'end') => void) | null = null;
  onPick: ((temp: number, tint: number) => void) | null = null;
  onZoom: ((z: 'fit' | 'full') => void) | null = null;

  constructor() {
    this.root = el(`<div class="fl-dv"><div class="fl-dv-box"><canvas class="fl-dv-img is-loaded" width="4" height="4"></canvas></div><div class="fl-dv-before" hidden><canvas class="fl-dv-img" width="4" height="4"></canvas></div><div class="fl-dv-split" hidden></div><span class="fl-dv-tag" hidden>Before</span><span class="fl-dv-tag fl-dv-aftertag" hidden>After</span><canvas class="fl-dv-canvas" width="4" height="4"></canvas><div class="fl-empty"><div class="fl-empty-card"><span class="fl-empty-title">${icon('modDevelop', 20)} No photo selected</span><span class="fl-empty-sub">Pick a photo in the Library, or drop one on this window.</span></div></div></div>`);
    this.box = q(this.root, '.fl-dv-box');
    this.after = q<HTMLCanvasElement>(this.root, '.fl-dv-box canvas');
    this.beforeBox = q(this.root, '.fl-dv-before');
    this.beforeCanvas = q<HTMLCanvasElement>(this.root, '.fl-dv-before canvas');
    this.split = q(this.root, '.fl-dv-split');
    this.overlay = q<HTMLCanvasElement>(this.root, '.fl-dv-canvas');
    const tags = Array.from(this.root.querySelectorAll<HTMLElement>('.fl-dv-tag'));
    this.tagBefore = tags[0];
    this.tagAfter = tags[1];
    this.empty = q(this.root, '.fl-empty');
    new ResizeObserver(() => { this.sizeOverlay(); this.place(); this.drawOverlay(); if (this.zoom === 'fit') this.schedule(false); }).observe(this.root);
    this.wire();
  }

  private sizeOverlay(): void {
    const w = this.root.clientWidth, h = this.root.clientHeight;
    if (this.overlay.width !== w) this.overlay.width = w;
    if (this.overlay.height !== h) this.overlay.height = h;
  }

  private currentDev(): Dev {
    const base = develop.settings;
    if (this.tool !== 'crop') return base;
    const crop = (base.crop as Dev | undefined) ?? {};
    return { ...base, crop: { angle: crop.angle ?? 0, flipH: crop.flipH, flipV: crop.flipV } };
  }

  setMode(m: ViewMode): void {
    this.mode = m;
    setClass(this.root, 'is-before-only', m === 'before');
    setHidden(this.beforeBox, m === 'after');
    setHidden(this.split, m !== 'split');
    setHidden(this.tagBefore, m === 'after');
    setHidden(this.tagAfter, m !== 'split');
    this.tagBefore.textContent = 'Before';
    this.applyClip();
    this.beforeKey = '';
    this.schedule(false);
  }

  setTool(t: Tool): void {
    this.tool = t;
    this.root.style.cursor = t === 'wb' ? 'crosshair' : '';
    if (t === 'crop') {
      const r = (develop.read('crop.rect') as number[] | undefined) ?? [0, 0, 1, 1];
      this.cropRect = r.slice();
    }
    this.beforeKey = '';
    this.schedule(false);
    this.drawOverlay();
  }

  setZoom(z: 'fit' | 'full'): void {
    this.zoom = z;
    this.cx = 0.5; this.cy = 0.5;
    this.onZoom?.(z);
    this.schedule(false);
  }

  setClipping(on: boolean): void { this.clipping = on; this.schedule(false); }

  schedule(low: boolean): void {
    this.wantLow = this.raf ? this.wantLow && low : low;
    if (this.raf) return;
    this.raf = requestAnimationFrame(() => { this.raf = 0; this.run(this.wantLow); });
  }

  private fullLong(): number {
    if (this.zoom === 'full') return FULL_CAP;
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    return Math.max(480, Math.min(1800, Math.ceil(Math.max(this.root.clientWidth, this.root.clientHeight) * dpr)));
  }

  private aspectOf(w: number, h: number): number { return w / Math.max(h, 1); }

  private place(): void {
    const item = develop.item;
    const vw = this.root.clientWidth, vh = this.root.clientHeight;
    if (!item || !this.lastW) return;
    const asp = this.aspectOf(this.lastW, this.lastH);
    let dw: number, dh: number;
    if (this.zoom === 'fit') {
      const pad = 24;
      const mw = Math.max(1, vw - pad * 2), mh = Math.max(1, vh - pad * 2);
      if (mw / mh > asp) { dh = mh; dw = mh * asp; } else { dw = mw; dh = mw / asp; }
    } else { dw = this.lastW; dh = this.lastH; }
    let x = (vw - dw) / 2, y = (vh - dh) / 2;
    if (dw > vw) x = Math.min(0, Math.max(vw - dw, vw / 2 - this.cx * dw));
    if (dh > vh) y = Math.min(0, Math.max(vh - dh, vh / 2 - this.cy * dh));
    this.boxRect = { x, y, w: dw, h: dh };
    for (const b of [this.box, this.beforeBox]) {
      setStyleVar(b, '--x', `${Math.round(x)}px`);
      setStyleVar(b, '--y', `${Math.round(y)}px`);
      setStyleVar(b, '--w', `${Math.round(dw)}px`);
      setStyleVar(b, '--h', `${Math.round(dh)}px`);
    }
    setClass(this.root, 'is-zoomed', dw > vw + 1 || dh > vh + 1);
    this.applyClip();
  }

  private applyClip(): void {
    if (this.mode === 'split') {
      setStyleVar(this.beforeBox, '--clip', `inset(0 ${((1 - this.splitAt) * 100).toFixed(2)}% 0 0)`);
      setStyleVar(this.split, 'left', `${(this.boxRect.x + this.boxRect.w * this.splitAt).toFixed(1)}px`);
    } else setStyleVar(this.beforeBox, '--clip', 'none');
  }

  private run(low: boolean): void {
    const item = develop.item;
    setHidden(this.empty, !!item);
    if (!item) { this.box.style.visibility = 'hidden'; return; }
    this.box.style.visibility = '';
    const t0 = performance.now();
    const dev = this.currentDev();
    const r = this.renderer.render(item.src, dev, low ? LOW_LONG : this.fullLong());
    const ctx = this.after.getContext('2d');
    if (!ctx) return;
    const img = new ImageData(r.rgba, r.w, r.h);
    const asp = this.aspectOf(r.w, r.h);
    const same = this.lastW > 0 && Math.abs(this.aspectOf(this.after.width, this.after.height) - asp) < 0.01;
    if (low && same) {
      if (this.scratch.width !== r.w) this.scratch.width = r.w;
      if (this.scratch.height !== r.h) this.scratch.height = r.h;
      this.scratch.getContext('2d')?.putImageData(img, 0, 0);
      ctx.imageSmoothingEnabled = true;
      ctx.drawImage(this.scratch, 0, 0, this.after.width, this.after.height);
    } else {
      if (this.after.width !== r.w) this.after.width = r.w;
      if (this.after.height !== r.h) this.after.height = r.h;
      ctx.putImageData(this.clipping ? this.withClipping(r.rgba, r.w, r.h) : img, 0, 0);
      this.lastW = r.w; this.lastH = r.h;
    }
    if (!low) { this.lastW = this.after.width; this.lastH = this.after.height; }
    this.place();
    if (this.mode !== 'after') this.drawBefore(item.id, r.w, r.h, low);
    const bins = binsOf(r.rgba, low ? 16 : 8);
    const ms = performance.now() - t0;
    this.onBins?.(bins, bins.r[0] + bins.g[0] + bins.b[0], bins.r[127] + bins.g[127] + bins.b[127], r.w, r.h, ms);
    this.drawOverlay();
  }

  private withClipping(rgba: Uint8ClampedArray, w: number, h: number): ImageData {
    const out = new Uint8ClampedArray(rgba);
    for (let i = 0; i < out.length; i += 4) {
      if (out[i] >= 254 || out[i + 1] >= 254 || out[i + 2] >= 254) { out[i] = 255; out[i + 1] = 59; out[i + 2] = 59; }
      else if (out[i] <= 1 && out[i + 1] <= 1 && out[i + 2] <= 1) { out[i] = 47; out[i + 1] = 107; out[i + 2] = 255; }
    }
    return new ImageData(out, w, h);
  }

  private drawBefore(id: number, w: number, h: number, low: boolean): void {
    const item = develop.item;
    if (!item) return;
    const d = this.currentDev();
    const keep: Dev = {};
    for (const k of ['crop', 'orientation', 'geometry']) if (d[k] !== undefined) keep[k] = d[k];
    const key = JSON.stringify([id, keep, this.tool]);
    if (key === this.beforeKey && this.beforeCanvas.width > 4) {
      return;
    }
    const long = low ? LOW_LONG : Math.max(w, h);
    const r = this.beforeRenderer.render(item.src, keep, long);
    if (this.beforeCanvas.width !== r.w) this.beforeCanvas.width = r.w;
    if (this.beforeCanvas.height !== r.h) this.beforeCanvas.height = r.h;
    this.beforeCanvas.getContext('2d')?.putImageData(new ImageData(r.rgba, r.w, r.h), 0, 0);
    if (!low) this.beforeKey = key;
  }

  private toNorm(e: PointerEvent): [number, number] {
    const r = this.root.getBoundingClientRect();
    const b = this.boxRect;
    return [(e.clientX - r.left - b.x) / b.w, (e.clientY - r.top - b.y) / b.h];
  }

  private oriented(): [number, number] {
    const item = develop.item;
    if (!item) return [1, 1];
    const f = new Frame(item.src.w, item.src.h, { orientation: develop.settings.orientation });
    return [f.ow, f.oh];
  }

  private hit(nx: number, ny: number): Handle | null {
    const [x0, y0, x1, y1] = this.cropRect;
    const b = this.boxRect;
    const tx = 12 / b.w, ty = 12 / b.h;
    const nearX0 = Math.abs(nx - x0) < tx, nearX1 = Math.abs(nx - x1) < tx, nearY0 = Math.abs(ny - y0) < ty, nearY1 = Math.abs(ny - y1) < ty;
    const inX = nx > x0 - tx && nx < x1 + tx, inY = ny > y0 - ty && ny < y1 + ty;
    if (nearX0 && nearY0) return 'nw';
    if (nearX1 && nearY0) return 'ne';
    if (nearX0 && nearY1) return 'sw';
    if (nearX1 && nearY1) return 'se';
    if (nearY0 && inX) return 'n';
    if (nearY1 && inX) return 's';
    if (nearX0 && inY) return 'w';
    if (nearX1 && inY) return 'e';
    if (nx > x0 && nx < x1 && ny > y0 && ny < y1) return 'move';
    return null;
  }

  private dragCrop(h: Handle, nx: number, ny: number, start: number[], sx: number, sy: number): number[] {
    const [ow, oh] = this.oriented();
    let [x0, y0, x1, y1] = start;
    const min = 0.03;
    const clamp = (v: number): number => Math.min(1, Math.max(0, v));
    if (h === 'move') {
      const dx = nx - sx, dy = ny - sy;
      const w = x1 - x0, hh = y1 - y0;
      x0 = Math.min(1 - w, Math.max(0, x0 + dx)); y0 = Math.min(1 - hh, Math.max(0, y0 + dy));
      return [x0, y0, x0 + w, y0 + hh];
    }
    if (h.includes('w')) x0 = Math.min(clamp(nx), x1 - min);
    if (h.includes('e')) x1 = Math.max(clamp(nx), x0 + min);
    if (h.includes('n')) y0 = Math.min(clamp(ny), y1 - min);
    if (h.includes('s')) y1 = Math.max(clamp(ny), y0 + min);
    const r = this.cropAspect;
    if (r) {
      const fixedX = h.includes('w') ? x1 : x0, fixedY = h.includes('n') ? y1 : y0;
      let wpx = (x1 - x0) * ow, hpx = (y1 - y0) * oh;
      if (h === 'n' || h === 's') wpx = hpx * r; else if (h === 'e' || h === 'w') hpx = wpx / r; else if (wpx / hpx > r) wpx = hpx * r; else hpx = wpx / r;
      let nw = wpx / ow, nh = hpx / oh;
      const maxW = h.includes('w') ? fixedX : h.includes('e') ? 1 - fixedX : Math.min(fixedX, 1 - fixedX) * 2;
      const maxH = h.includes('n') ? fixedY : h.includes('s') ? 1 - fixedY : Math.min(fixedY, 1 - fixedY) * 2;
      const k = Math.min(1, maxW / nw, maxH / nh);
      nw *= k; nh *= k;
      if (h.includes('w')) { x1 = fixedX; x0 = fixedX - nw; } else if (h.includes('e')) { x0 = fixedX; x1 = fixedX + nw; } else { const c = (x0 + x1) / 2; x0 = c - nw / 2; x1 = c + nw / 2; }
      if (h.includes('n')) { y1 = fixedY; y0 = fixedY - nh; } else if (h.includes('s')) { y0 = fixedY; y1 = fixedY + nh; } else { const c = (y0 + y1) / 2; y0 = c - nh / 2; y1 = c + nh / 2; }
    }
    return [x0, y0, x1, y1];
  }

  drawOverlay(): void {
    const c = this.overlay.getContext('2d');
    if (!c) return;
    c.clearRect(0, 0, this.overlay.width, this.overlay.height);
    if (this.tool !== 'crop' || !develop.item) return;
    const b = this.boxRect;
    const [x0, y0, x1, y1] = this.cropRect;
    const X0 = b.x + x0 * b.w, Y0 = b.y + y0 * b.h, X1 = b.x + x1 * b.w, Y1 = b.y + y1 * b.h;
    c.fillStyle = 'rgba(0,0,0,0.55)';
    c.fillRect(b.x, b.y, b.w, Y0 - b.y);
    c.fillRect(b.x, Y1, b.w, b.y + b.h - Y1);
    c.fillRect(b.x, Y0, X0 - b.x, Y1 - Y0);
    c.fillRect(X1, Y0, b.x + b.w - X1, Y1 - Y0);
    c.strokeStyle = 'rgba(255,255,255,0.95)';
    c.lineWidth = 1.5;
    c.strokeRect(X0 + 0.5, Y0 + 0.5, X1 - X0, Y1 - Y0);
    c.strokeStyle = 'rgba(255,255,255,0.35)';
    c.lineWidth = 1;
    for (let i = 1; i < 3; i += 1) {
      c.beginPath(); c.moveTo(X0 + ((X1 - X0) * i) / 3, Y0); c.lineTo(X0 + ((X1 - X0) * i) / 3, Y1); c.stroke();
      c.beginPath(); c.moveTo(X0, Y0 + ((Y1 - Y0) * i) / 3); c.lineTo(X1, Y0 + ((Y1 - Y0) * i) / 3); c.stroke();
    }
    c.fillStyle = '#fff';
    for (const [px, py] of [[X0, Y0], [X1, Y0], [X0, Y1], [X1, Y1], [(X0 + X1) / 2, Y0], [(X0 + X1) / 2, Y1], [X0, (Y0 + Y1) / 2], [X1, (Y0 + Y1) / 2]]) c.fillRect(px - 4, py - 4, 8, 8);
  }

  private wire(): void {
    let drag: { h: Handle; start: number[]; sx: number; sy: number } | null = null;
    let pan: { x: number; y: number; cx: number; cy: number } | null = null;
    let splitting = false;
    this.root.addEventListener('pointerdown', (e) => {
      if (e.button !== 0 || !develop.item) return;
      if ((e.target as HTMLElement).closest('.fl-dv-split')) { splitting = true; this.split.setPointerCapture(e.pointerId); return; }
      const [nx, ny] = this.toNorm(e);
      if (this.tool === 'crop') {
        const h = this.hit(nx, ny);
        if (h) { drag = { h, start: this.cropRect.slice(), sx: nx, sy: ny }; this.root.setPointerCapture(e.pointerId); }
        return;
      }
      if (this.tool === 'wb') {
        if (nx < 0 || ny < 0 || nx > 1 || ny > 1) return;
        const rgb = this.renderer.sampleLinear(develop.item.src, nx, ny, 3);
        if (rgb) { const [t, tint] = solveWb(rgb); this.onPick?.(t, tint); }
        return;
      }
      if (this.zoom === 'full') {
        pan = { x: e.clientX, y: e.clientY, cx: this.cx, cy: this.cy };
        setClass(this.root, 'is-panning', true);
        this.root.setPointerCapture(e.pointerId);
      }
    });
    this.root.addEventListener('pointermove', (e) => {
      if (splitting) {
        const r = this.root.getBoundingClientRect();
        this.splitAt = Math.min(0.98, Math.max(0.02, (e.clientX - r.left - this.boxRect.x) / this.boxRect.w));
        this.applyClip();
        return;
      }
      if (drag) {
        const [nx, ny] = this.toNorm(e);
        this.cropRect = this.dragCrop(drag.h, nx, ny, drag.start, drag.sx, drag.sy);
        this.drawOverlay();
        this.onCrop?.(this.cropRect, 'drag');
        return;
      }
      if (pan) {
        this.cx = Math.min(1, Math.max(0, pan.cx - (e.clientX - pan.x) / this.boxRect.w));
        this.cy = Math.min(1, Math.max(0, pan.cy - (e.clientY - pan.y) / this.boxRect.h));
        this.place();
        return;
      }
      if (this.tool === 'crop') {
        const [nx, ny] = this.toNorm(e);
        const h = this.hit(nx, ny);
        this.root.style.cursor = !h ? '' : h === 'move' ? 'move' : h === 'n' || h === 's' ? 'ns-resize' : h === 'e' || h === 'w' ? 'ew-resize' : h === 'nw' || h === 'se' ? 'nwse-resize' : 'nesw-resize';
      }
    });
    const up = (): void => {
      if (drag) { drag = null; this.onCrop?.(this.cropRect, 'end'); }
      pan = null;
      splitting = false;
      setClass(this.root, 'is-panning', false);
    };
    this.root.addEventListener('pointerup', up);
    this.root.addEventListener('pointercancel', up);
  }

  setCropRect(rect: number[]): void { this.cropRect = rect.slice(); this.drawOverlay(); }

  cropState(): { rect: number[]; aspect: number | null } { return { rect: clone(this.cropRect), aspect: this.cropAspect }; }
}
