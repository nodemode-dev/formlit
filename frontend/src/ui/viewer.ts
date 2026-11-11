import { api } from '../io/api';
import type { Photo } from '../state/library';
import { el, pendingClass, q, setClass, setStyleVar, setText, type Disposer } from './dom';
import { icon } from './icons';
import { previewUrl } from './thumbs';

export type Zoom = 'fit' | 'fill' | number;

const PREVIEW_LONG = 2560;

export function infoLine(p: Photo): string {
  const t = p.t ? p.t.slice(0, 16).replace('T', ' ') : '';
  return [p.cn ? `${p.file} (${p.cn})` : p.file, t, `${p.w} x ${p.h}`].filter(Boolean).join(' · ');
}

export class Viewer {
  readonly root: HTMLElement;
  readonly box: HTMLElement;
  private readonly img: HTMLImageElement;
  private readonly hi: HTMLImageElement;
  private readonly info: HTMLElement;
  private readonly spinner: HTMLElement;
  photo: Photo | null = null;
  zoom: Zoom = 'fit';
  private cx = 0.5;
  private cy = 0.5;
  private pending: Disposer | null = null;
  private loadSeq = 0;
  private hiFor = '';
  onZoom: ((z: Zoom) => void) | null = null;
  onView: ((z: Zoom, cx: number, cy: number) => void) | null = null;
  onClick: ((e: MouseEvent) => void) | null = null;
  infoMode = 1;

  constructor(cls = '') {
    this.root = el(`<div class="fl-viewer ${cls}"><div class="fl-viewer-box"><img class="fl-viewer-img" alt="" draggable="false"><img class="fl-viewer-hi" alt="" draggable="false" hidden></div><div class="fl-viewer-info"></div><div class="fl-viewer-spin">${icon('loading', 18)}</div></div>`);
    this.box = q(this.root, '.fl-viewer-box');
    this.img = q<HTMLImageElement>(this.root, '.fl-viewer-img');
    this.hi = q<HTMLImageElement>(this.root, '.fl-viewer-hi');
    this.info = q(this.root, '.fl-viewer-info');
    this.spinner = q(this.root, '.fl-viewer-spin');
    new ResizeObserver(() => this.place()).observe(this.root);
    this.drag();
  }

  async show(p: Photo | null): Promise<void> {
    const same = this.photo?.id === p?.id;
    this.photo = p;
    if (!p) {
      this.loadSeq += 1;
      this.pending?.();
      this.pending = null;
      delete this.img.dataset.src;
      this.img.removeAttribute('src');
      setClass(this.img, 'is-loaded', false);
      this.hi.hidden = true;
      setText(this.info, '');
      return;
    }
    if (!same) { this.cx = 0.5; this.cy = 0.5; this.hiFor = ''; this.hi.hidden = true; }
    setText(this.info, this.infoMode ? infoLine(p) : '');
    this.place();
    const url = previewUrl(p);
    if (this.img.dataset.src === url) { this.maybeHi(); return; }
    const seq = ++this.loadSeq;
    this.pending?.();
    this.pending = pendingClass(this.spinner);
    const next = new Image();
    next.decoding = 'async';
    next.src = url;
    try { await next.decode(); } catch { if (seq === this.loadSeq) { this.pending?.(); this.pending = null; } return; }
    if (seq !== this.loadSeq) return;
    this.img.dataset.src = url;
    this.img.src = url;
    setClass(this.img, 'is-loaded', true);
    this.pending?.();
    this.pending = null;
    this.maybeHi();
  }

  refresh(): void { if (this.photo) void this.show(this.photo); }

  setInfo(mode: number): void {
    this.infoMode = mode;
    setText(this.info, mode && this.photo ? infoLine(this.photo) : '');
  }

  setZoom(z: Zoom, at?: { x: number; y: number }): void {
    if (at) { this.cx = at.x; this.cy = at.y; }
    this.zoom = z;
    this.place();
    this.maybeHi();
    this.onZoom?.(z);
    this.onView?.(this.zoom, this.cx, this.cy);
  }

  center(): [number, number] { return [this.cx, this.cy]; }

  visible(): [number, number, number, number] | null {
    const p = this.photo;
    if (!p || this.root.hidden || !this.root.isConnected || !this.root.clientWidth) return null;
    const [w, h] = this.dims(p);
    const s = this.scale();
    const vw = this.root.clientWidth, vh = this.root.clientHeight;
    const dw = w * s, dh = h * s;
    if (dw <= vw + 1 && dh <= vh + 1) return null;
    const x = dw > vw ? Math.min(0, Math.max(vw - dw, vw / 2 - this.cx * dw)) : (vw - dw) / 2;
    const y = dh > vh ? Math.min(0, Math.max(vh - dh, vh / 2 - this.cy * dh)) : (vh - dh) / 2;
    return [Math.max(0, -x / dw), Math.max(0, -y / dh), Math.min(1, (vw - x) / dw), Math.min(1, (vh - y) / dh)];
  }

  follow(z: Zoom, cx: number, cy: number): void {
    if (this.zoom === z && this.cx === cx && this.cy === cy) return;
    this.zoom = z;
    this.cx = cx;
    this.cy = cy;
    this.place();
    this.maybeHi();
  }

  scale(): number {
    const p = this.photo;
    if (!p) return 1;
    const [w, h] = this.dims(p);
    const vw = this.root.clientWidth || 1;
    const vh = this.root.clientHeight || 1;
    if (this.zoom === 'fit') return Math.min(vw / w, vh / h);
    if (this.zoom === 'fill') return Math.max(vw / w, vh / h);
    return this.zoom;
  }

  private dims(p: Photo): [number, number] {
    const a = p.a || p.w / Math.max(1, p.h);
    const long = Math.max(p.w, p.h);
    return a >= 1 ? [long, long / a] : [long * a, long];
  }

  private place(): void {
    const p = this.photo;
    if (!p) return;
    const [w, h] = this.dims(p);
    const s = this.scale();
    const vw = this.root.clientWidth;
    const vh = this.root.clientHeight;
    const dw = w * s;
    const dh = h * s;
    let x = (vw - dw) / 2;
    let y = (vh - dh) / 2;
    if (dw > vw) x = Math.min(0, Math.max(vw - dw, vw / 2 - this.cx * dw));
    if (dh > vh) y = Math.min(0, Math.max(vh - dh, vh / 2 - this.cy * dh));
    setStyleVar(this.box, '--x', `${Math.round(x)}px`);
    setStyleVar(this.box, '--y', `${Math.round(y)}px`);
    setStyleVar(this.box, '--w', `${Math.round(dw)}px`);
    setStyleVar(this.box, '--h', `${Math.round(dh)}px`);
    setClass(this.root, 'is-zoomed', dw > vw + 1 || dh > vh + 1);
  }

  private maybeHi(): void {
    const p = this.photo;
    if (!p || p.kind === 'video') return;
    const [w, h] = this.dims(p);
    const shown = Math.max(w, h) * this.scale();
    if (shown <= Math.min(PREVIEW_LONG, Math.max(w, h)) * 1.02) { this.hi.hidden = true; return; }
    const key = `${p.id}:${p.rev}`;
    if (this.hiFor === key) { this.hi.hidden = false; return; }
    this.hiFor = key;
    const url = api.url(`/api/photos/${p.id}/full?rev=${p.rev}`);
    const done = pendingClass(this.spinner, 150);
    const next = new Image();
    next.decoding = 'async';
    next.src = url;
    next.decode().then(() => {
      done();
      if (this.hiFor !== key) return;
      this.hi.src = url;
      this.hi.hidden = false;
    }, () => { done(); if (this.hiFor === key) this.hiFor = ''; });
  }

  private drag(): void {
    let sx = 0, sy = 0, ox = 0, oy = 0, moved = false, down = false;
    this.root.addEventListener('pointerdown', (e) => {
      if (e.button !== 0 || !this.photo) return;
      down = true; moved = false; sx = e.clientX; sy = e.clientY; ox = this.cx; oy = this.cy;
      this.root.setPointerCapture(e.pointerId);
    });
    this.root.addEventListener('pointermove', (e) => {
      if (!down || !this.photo) return;
      const dx = e.clientX - sx, dy = e.clientY - sy;
      if (!moved && Math.hypot(dx, dy) < 4) return;
      moved = true;
      if (!this.root.classList.contains('is-zoomed')) return;
      const [w, h] = this.dims(this.photo);
      const s = this.scale();
      this.cx = Math.min(1, Math.max(0, ox - dx / (w * s)));
      this.cy = Math.min(1, Math.max(0, oy - dy / (h * s)));
      setClass(this.root, 'is-panning', true);
      this.place();
      this.onView?.(this.zoom, this.cx, this.cy);
    });
    this.root.addEventListener('pointerup', (e) => {
      if (!down) return;
      down = false;
      setClass(this.root, 'is-panning', false);
      if (moved) return;
      this.onClick?.(e);
    });
    this.root.addEventListener('wheel', (e) => {
      if (!this.photo || !(e.ctrlKey || e.metaKey)) return;
      e.preventDefault();
      const s = this.scale() * Math.exp(-e.deltaY * 0.0025);
      this.setZoom(Math.max(0.05, Math.min(8, s)), this.pointAt(e));
    }, { passive: false });
  }

  pointAt(e: MouseEvent): { x: number; y: number } {
    const r = this.box.getBoundingClientRect();
    return { x: Math.min(1, Math.max(0, (e.clientX - r.left) / Math.max(1, r.width))), y: Math.min(1, Math.max(0, (e.clientY - r.top) / Math.max(1, r.height))) };
  }

  toggleZoom(e?: MouseEvent): void {
    if (this.zoom === 'fit' || this.zoom === 'fill') this.setZoom(1, e ? this.pointAt(e) : undefined);
    else this.setZoom('fit');
  }
}
