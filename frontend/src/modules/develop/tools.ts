import type { Ctx } from '../../app';
import { clone, develop } from '../../state/develop';
import { el, q, setClass, setHidden, setText } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { Slider } from '../../ui/slider';
import type { DevelopView, Pt, Tool } from './view';

export interface ToolHost {
  ctx: Ctx;
  view: DevelopView;
  drawer: HTMLElement;
  done(): void;
}

type Rect = [number, number, number, number];

function rotPoint(x: number, y: number, ow: number, oh: number, angleDeg: number): [number, number] {
  const a = (-angleDeg * Math.PI) / 180;
  const cx = ow / 2, cy = oh / 2;
  const s = Math.sin(a), c = Math.cos(a);
  return [c * x - s * y + (cx - c * cx + s * cy), s * x + c * y + (cy - s * cx - c * cy)];
}

function unrotPoint(x: number, y: number, ow: number, oh: number, angleDeg: number): [number, number] { return rotPoint(x, y, ow, oh, -angleDeg); }

function fits(r: Rect, ow: number, oh: number, angle: number): boolean {
  for (const [u, v] of [[r[0], r[1]], [r[2], r[1]], [r[2], r[3]], [r[0], r[3]]]) {
    const [x, y] = rotPoint(u * ow, v * oh, ow, oh, angle);
    if (x < -0.5 || y < -0.5 || x > ow + 0.5 || y > oh + 0.5) return false;
  }
  return true;
}

function shrinkToFit(r: Rect, ow: number, oh: number, angle: number): Rect {
  if (fits(r, ow, oh, angle)) return r;
  const cx = (r[0] + r[2]) / 2, cy = (r[1] + r[3]) / 2, hw = (r[2] - r[0]) / 2, hh = (r[3] - r[1]) / 2;
  let lo = 0, hi = 1;
  for (let i = 0; i < 28; i += 1) {
    const m = (lo + hi) / 2;
    if (fits([cx - hw * m, cy - hh * m, cx + hw * m, cy + hh * m], ow, oh, angle)) lo = m; else hi = m;
  }
  return [cx - hw * lo, cy - hh * lo, cx + hw * lo, cy + hh * lo];
}

function slider(id: string, label: string, min: number, max: number, def: number, value: number, onInput: (v: number, phase: 'drag' | 'end') => void, decimals = 0, step = 1): Slider {
  const s = new Slider({ id, label, min, max, default: def, step, decimals }, { input: (_id, v, phase) => onInput(v, phase) });
  s.set(value);
  return s;
}

export class CropTool implements Tool {
  readonly id = 'crop';
  readonly uncropped = true;
  cursor = 'crosshair';
  private rect: Rect = [0, 0, 1, 1];
  private angle = 0;
  private aspect: number | null = null;
  private aspectId = 'asShot';
  private drag: { kind: string; start: Pt; rect: Rect; angle: number } | null = null;
  private readonly angleSlider: Slider;
  private readonly aspectSel: HTMLSelectElement;
  private readonly root: HTMLElement;

  constructor(private readonly host: ToolHost) {
    this.root = el(`<div class="fl-tool-opts"><div class="fl-tool-title">${icon('crop', 14)} Crop and Straighten</div><div class="fl-row"><span class="fl-row-label">Aspect</span></div><div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm" type="button" data-a="auto">Auto Straighten</button><button class="cv-btn fl-btn-sm" type="button" data-a="swap">Swap (X)</button><button class="cv-btn fl-btn-sm" type="button" data-a="reset">Reset</button><button class="cv-btn fl-btn-sm fl-btn-cta" type="button" data-a="done">Done</button></div></div>`);
    this.aspectSel = el<HTMLSelectElement>('<select class="cv-select fl-grow"></select>');
    for (const a of develop.doc?.aspects ?? []) this.aspectSel.add(new Option(a.label, a.id));
    q(this.root, '.fl-row').appendChild(this.aspectSel);
    this.aspectSel.addEventListener('change', () => this.setAspect(this.aspectSel.value));
    this.angleSlider = slider('crop.angle', 'Angle', -45, 45, 0, 0, (v, phase) => {
      this.angle = v;
      this.rect = shrinkToFit(this.rect, this.ow(), this.oh(), this.angle);
      this.host.view.draw();
      if (phase === 'end') this.commit('Straighten');
    }, 2, 0.05);
    this.root.insertBefore(this.angleSlider.root, this.root.lastElementChild);
    this.root.addEventListener('click', (e) => {
      const a = (e.target as HTMLElement).closest<HTMLElement>('[data-a]')?.dataset.a;
      if (a === 'reset') { this.rect = [0, 0, 1, 1]; this.angle = 0; this.angleSlider.set(0); this.setAspect('asShot'); this.commit('Reset Crop'); }
      if (a === 'swap') this.swap();
      if (a === 'auto') void this.autoStraighten();
      if (a === 'done') this.host.done();
    });
  }

  private ow(): number { return this.host.view.geo?.ow ?? 1; }
  private oh(): number { return this.host.view.geo?.oh ?? 1; }

  activate(): void {
    const crop = (develop.settings.crop as Record<string, unknown> | undefined) ?? {};
    const r = crop.rect as Rect | undefined;
    this.rect = r && r.length === 4 ? [r[0], r[1], r[2], r[3]] : [0, 0, 1, 1];
    this.angle = Number(crop.angle ?? 0);
    this.aspectId = String(crop.aspect ?? 'asShot');
    this.aspectSel.value = this.aspectId;
    this.aspect = this.ratioOf(this.aspectId);
    this.angleSlider.set(this.angle);
    this.host.drawer.replaceChildren(this.root);
  }

  private ratioOf(id: string): number | null {
    const a = develop.doc?.aspects.find((x) => x.id === id);
    if (id === 'asShot' || id === 'original') return this.ow() / this.oh();
    if (!a?.ratio) return null;
    const [w, h] = a.ratio;
    const landscape = (this.rect[2] - this.rect[0]) * this.ow() >= (this.rect[3] - this.rect[1]) * this.oh();
    return landscape ? Math.max(w, h) / Math.min(w, h) : Math.min(w, h) / Math.max(w, h);
  }

  private setAspect(id: string): void {
    this.aspectId = id;
    this.aspect = this.ratioOf(id);
    if (this.aspect) this.fitAspect();
    this.host.view.draw();
    this.commit('Crop Aspect');
  }

  private fitAspect(): void {
    const a = this.aspect;
    if (!a) return;
    const ow = this.ow(), oh = this.oh();
    const cx = (this.rect[0] + this.rect[2]) / 2, cy = (this.rect[1] + this.rect[3]) / 2;
    let w = (this.rect[2] - this.rect[0]) * ow, h = (this.rect[3] - this.rect[1]) * oh;
    if (w / h > a) w = h * a; else h = w / a;
    this.rect = shrinkToFit([cx - w / ow / 2, cy - h / oh / 2, cx + w / ow / 2, cy + h / oh / 2], ow, oh, this.angle);
    this.rect = this.clampRect(this.rect);
  }

  private clampRect(r: Rect): Rect {
    const w = r[2] - r[0], h = r[3] - r[1];
    const x0 = Math.max(0, Math.min(1 - w, r[0])), y0 = Math.max(0, Math.min(1 - h, r[1]));
    return [x0, y0, x0 + w, y0 + h];
  }

  private swap(): void {
    if (this.aspect) this.aspect = 1 / this.aspect;
    const ow = this.ow(), oh = this.oh();
    const cx = (this.rect[0] + this.rect[2]) / 2, cy = (this.rect[1] + this.rect[3]) / 2;
    const w = (this.rect[3] - this.rect[1]) * oh, h = (this.rect[2] - this.rect[0]) * ow;
    this.rect = shrinkToFit(this.clampRect([cx - w / ow / 2, cy - h / oh / 2, cx + w / ow / 2, cy + h / oh / 2]), ow, oh, this.angle);
    this.host.view.draw();
    this.commit('Swap Crop');
  }

  private async autoStraighten(): Promise<void> {
    const id = develop.id;
    if (id === null) return;
    try {
      const r = await this.host.ctx.api.cmd<{ angle: number }>('develop.autoStraighten', { id });
      this.angle = r.angle;
      this.angleSlider.set(this.angle);
      this.rect = shrinkToFit(this.rect, this.ow(), this.oh(), this.angle);
      this.host.view.draw();
      this.commit('Auto Straighten');
    } catch (err) { this.host.ctx.fail(err, 'Auto Straighten'); }
  }

  private commit(label: string): void {
    const crop = clone((develop.settings.crop as Record<string, unknown>) ?? {});
    crop.rect = this.rect.map((v) => Number(v.toFixed(5)));
    crop.angle = Number(this.angle.toFixed(2));
    crop.aspect = this.aspectId === 'asShot' ? null : this.aspectId;
    develop.patch('crop', crop, 'end', label);
  }

  private corners(): Array<[number, number]> {
    const ow = this.ow(), oh = this.oh();
    const v = this.host.view;
    return [[this.rect[0], this.rect[1]], [this.rect[2], this.rect[1]], [this.rect[2], this.rect[3]], [this.rect[0], this.rect[3]]].map(([u, w]) => {
      const [x, y] = rotPoint(u * ow, w * oh, ow, oh, this.angle);
      return v.normToStage(x / ow, y / oh);
    });
  }

  private toRot(p: Pt): [number, number] {
    const ow = this.ow(), oh = this.oh();
    const [x, y] = unrotPoint(p.nx * ow, p.ny * oh, ow, oh, this.angle);
    return [x / ow, y / oh];
  }

  private hit(p: Pt): string {
    const cs = this.corners();
    const names = ['nw', 'ne', 'se', 'sw'];
    for (let i = 0; i < 4; i += 1) if (Math.hypot(cs[i][0] - p.sx, cs[i][1] - p.sy) < 12) return names[i];
    const [u, v] = this.toRot(p);
    const tolU = 10 / Math.max(1, this.host.view.displayRect().w), tolV = 10 / Math.max(1, this.host.view.displayRect().h);
    const inside = u > this.rect[0] && u < this.rect[2] && v > this.rect[1] && v < this.rect[3];
    if (Math.abs(u - this.rect[0]) < tolU && v > this.rect[1] && v < this.rect[3]) return 'w';
    if (Math.abs(u - this.rect[2]) < tolU && v > this.rect[1] && v < this.rect[3]) return 'e';
    if (Math.abs(v - this.rect[1]) < tolV && u > this.rect[0] && u < this.rect[2]) return 'n';
    if (Math.abs(v - this.rect[3]) < tolV && u > this.rect[0] && u < this.rect[2]) return 's';
    return inside ? 'move' : 'rotate';
  }

  hover(p: Pt | null): void {
    if (!p) return;
    const k = this.hit(p);
    this.host.view.root.style.cursor = k === 'move' ? 'move' : k === 'rotate' ? 'alias' : k === 'n' || k === 's' ? 'ns-resize' : k === 'e' || k === 'w' ? 'ew-resize' : k === 'nw' || k === 'se' ? 'nwse-resize' : 'nesw-resize';
  }

  down(p: Pt): boolean {
    this.drag = { kind: this.hit(p), start: p, rect: [...this.rect] as Rect, angle: this.angle };
    return true;
  }

  move(p: Pt): void {
    const d = this.drag;
    if (!d) return;
    const ow = this.ow(), oh = this.oh();
    if (d.kind === 'rotate') {
      const c = this.host.view.normToStage(0.5, 0.5);
      const a0 = Math.atan2(d.start.sy - c[1], d.start.sx - c[0]);
      const a1 = Math.atan2(p.sy - c[1], p.sx - c[0]);
      this.angle = Math.max(-45, Math.min(45, d.angle + ((a1 - a0) * 180) / Math.PI));
      this.rect = shrinkToFit(d.rect, ow, oh, this.angle);
      this.angleSlider.set(Number(this.angle.toFixed(2)));
      return;
    }
    const [u0, v0] = this.toRot(d.start);
    const [u1, v1] = this.toRot(p);
    const du = u1 - u0, dv = v1 - v0;
    let r: Rect = [...d.rect] as Rect;
    if (d.kind === 'move') {
      r = [r[0] + du, r[1] + dv, r[2] + du, r[3] + dv];
      r = this.clampRect(r);
      if (!fits(r, ow, oh, this.angle)) return;
      this.rect = r;
      return;
    }
    if (d.kind.includes('w')) r[0] = Math.min(r[2] - 0.02, r[0] + du);
    if (d.kind.includes('e')) r[2] = Math.max(r[0] + 0.02, r[2] + du);
    if (d.kind.includes('n')) r[1] = Math.min(r[3] - 0.02, r[1] + dv);
    if (d.kind.includes('s')) r[3] = Math.max(r[1] + 0.02, r[3] + dv);
    const a = this.aspect ?? (p.e.shiftKey ? ((d.rect[2] - d.rect[0]) * ow) / ((d.rect[3] - d.rect[1]) * oh) : null);
    if (a) {
      const w = (r[2] - r[0]) * ow, h = (r[3] - r[1]) * oh;
      if (d.kind === 'n' || d.kind === 's') { const nw = h * a / ow; const cx = (r[0] + r[2]) / 2; r[0] = cx - nw / 2; r[2] = cx + nw / 2; }
      else if (d.kind === 'e' || d.kind === 'w') { const nh = w / a / oh; const cy = (r[1] + r[3]) / 2; r[1] = cy - nh / 2; r[3] = cy + nh / 2; }
      else {
        const nh = w / a / oh;
        if (d.kind.includes('n')) r[1] = r[3] - nh; else r[3] = r[1] + nh;
      }
    }
    r = [Math.max(0, r[0]), Math.max(0, r[1]), Math.min(1, r[2]), Math.min(1, r[3])];
    if (fits(r, ow, oh, this.angle)) this.rect = r;
  }

  up(): void {
    if (!this.drag) return;
    const kind = this.drag.kind;
    this.drag = null;
    this.commit(kind === 'rotate' ? 'Straighten' : 'Crop');
  }

  key(_e: KeyboardEvent, combo: string): boolean {
    if (combo === 'X') { this.swap(); return true; }
    if (combo === 'Enter' || combo === 'Escape') { this.host.done(); return true; }
    return false;
  }

  draw(c: CanvasRenderingContext2D, view: DevelopView): void {
    const cs = this.corners();
    const r = view.displayRect();
    c.save();
    c.fillStyle = 'rgba(0,0,0,0.55)';
    c.beginPath();
    c.rect(r.x - 2, r.y - 2, r.w + 4, r.h + 4);
    c.moveTo(cs[0][0], cs[0][1]);
    for (let i = 3; i >= 0; i -= 1) c.lineTo(cs[i][0], cs[i][1]);
    c.closePath();
    c.fill('evenodd');
    c.strokeStyle = 'rgba(255,255,255,0.9)';
    c.lineWidth = 1;
    c.beginPath();
    c.moveTo(cs[0][0], cs[0][1]);
    for (let i = 1; i < 4; i += 1) c.lineTo(cs[i][0], cs[i][1]);
    c.closePath();
    c.stroke();
    c.strokeStyle = 'rgba(255,255,255,0.35)';
    for (const t of [1 / 3, 2 / 3]) {
      const a = [cs[0][0] + (cs[1][0] - cs[0][0]) * t, cs[0][1] + (cs[1][1] - cs[0][1]) * t];
      const b = [cs[3][0] + (cs[2][0] - cs[3][0]) * t, cs[3][1] + (cs[2][1] - cs[3][1]) * t];
      c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke();
      const e = [cs[0][0] + (cs[3][0] - cs[0][0]) * t, cs[0][1] + (cs[3][1] - cs[0][1]) * t];
      const f = [cs[1][0] + (cs[2][0] - cs[1][0]) * t, cs[1][1] + (cs[2][1] - cs[1][1]) * t];
      c.beginPath(); c.moveTo(e[0], e[1]); c.lineTo(f[0], f[1]); c.stroke();
    }
    c.fillStyle = '#fff';
    for (const [x, y] of cs) c.fillRect(x - 4, y - 4, 8, 8);
    c.restore();
  }
}

interface Spot { points: Array<[number, number]>; size: number; source: [number, number] | null; feather: number; opacity: number; mode: string; hidden?: boolean; patch?: string; variants?: string[] }

export class SpotTool implements Tool {
  readonly id = 'spot';
  cursor = 'crosshair';
  private sel = -1;
  private drag: { kind: 'src' | 'dst' | 'new'; i: number; start: Pt; orig: Spot } | null = null;
  private size = 0.02;
  private feather = 50;
  private opacity = 100;
  private mode = 'heal';
  private hoverPt: Pt | null = null;
  private readonly root: HTMLElement;
  private readonly sSize: Slider;
  private readonly sFeather: Slider;
  private readonly sOpacity: Slider;

  constructor(private readonly host: ToolHost) {
    this.root = el(`<div class="fl-tool-opts"><div class="fl-tool-title">${icon('spotHeal', 14)} Healing</div><div class="fl-row"><span class="fl-row-label">Mode</span><div class="cv-seg fl-seg-sm fl-grow"><button type="button" data-m="remove" title="Generative remove, fills from the surroundings">Remove</button><button type="button" data-m="heal">Heal</button><button type="button" data-m="clone">Clone</button></div></div><div class="fl-row fl-row-end"><span class="fl-muted fl-grow">Click to heal, drag to paint a stroke. [ and ] change size.</span><button class="cv-btn fl-btn-sm" type="button" data-a="clear">Reset</button><button class="cv-btn fl-btn-sm fl-btn-cta" type="button" data-a="done">Done</button></div></div>`);
    const upd = (k: 'size' | 'feather' | 'opacity') => (v: number, phase: 'drag' | 'end') => {
      if (k === 'size') this.size = v / 1000; else if (k === 'feather') this.feather = v; else this.opacity = v;
      if (this.sel >= 0) { const spots = this.spots(); const s = spots[this.sel]; if (s) { if (k === 'size') s.size = this.size; else (s as unknown as Record<string, number>)[k] = v; this.write(spots, phase, 'Edit Spot'); } }
      this.host.view.draw();
    };
    this.sSize = slider('spot.size', 'Size', 2, 200, 20, 20, upd('size'));
    this.sFeather = slider('spot.feather', 'Feather', 0, 100, 50, 50, upd('feather'));
    this.sOpacity = slider('spot.opacity', 'Opacity', 0, 100, 100, 100, upd('opacity'));
    this.root.insertBefore(this.sOpacity.root, this.root.lastElementChild);
    this.root.insertBefore(this.sFeather.root, this.sOpacity.root);
    this.root.insertBefore(this.sSize.root, this.sFeather.root);
    this.root.insertBefore(this.variantsRow, this.root.lastElementChild);
    this.variantsRow.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-var]');
      if (!b || this.sel < 0) return;
      e.stopPropagation();
      const spots = this.spots();
      const s = spots[this.sel];
      if (!s) return;
      if (b.dataset.var === 'more') { this.fill(this.sel, s, 'Remove: New Variations'); return; }
      const v = s.variants?.[Number(b.dataset.var)];
      if (v) { s.patch = v; this.write(spots, 'end', 'Remove: Choose Variation'); this.syncVariants(); }
    });
    this.root.addEventListener('click', (e) => {
      const m = (e.target as HTMLElement).closest<HTMLElement>('[data-m]')?.dataset.m;
      if (m) { this.mode = m; if (this.sel >= 0) { const sp = this.spots(); if (sp[this.sel]) { sp[this.sel].mode = m; this.write(sp, 'end', 'Spot Mode'); } } this.syncOpts(); }
      const a = (e.target as HTMLElement).closest<HTMLElement>('[data-a]')?.dataset.a;
      if (a === 'clear') { this.sel = -1; this.write([], 'end', 'Reset Spots'); }
      if (a === 'done') this.host.done();
    });
  }

  activate(): void { this.host.drawer.replaceChildren(this.root); this.syncOpts(); }

  private readonly variantsRow = el('<div class="fl-row fl-spot-vars" hidden><span class="fl-row-label">Variations</span><div class="cv-seg fl-seg-sm fl-grow"></div><button class="cv-btn fl-btn-sm" type="button" data-var="more" title="Make three new fills">Refresh</button></div>');

  private syncVariants(): void {
    const s = this.spots()[this.sel];
    const vars = s?.mode === 'remove' ? s.variants ?? [] : [];
    setHidden(this.variantsRow, vars.length < 2);
    const html = vars.map((v, i) => `<button type="button" data-var="${i}" class="${v === s?.patch ? 'is-on' : ''}">${i + 1}</button>`).join('');
    const seg = q(this.variantsRow, '.cv-seg');
    if (seg.dataset.key !== html) { seg.dataset.key = html; seg.innerHTML = html; }
  }

  private fill(i: number, s: Spot, label: string): void {
    const done = this.host.ctx.shell.busy('Removing');
    void develop.flush().then(() => this.host.ctx.api.cmd<{ patch: string; variants: string[] }>('develop.removeFill', { id: develop.id, spot: s })).then((r) => {
      const now = this.spots();
      if (now[i]) { now[i].patch = r.patch; now[i].variants = r.variants; now[i].source = null; this.write(now, 'end', label); this.syncVariants(); }
    }, (err) => { this.host.ctx.fail(err, 'Remove'); this.write(this.spots(), 'end', label); }).finally(done);
  }

  private syncOpts(): void {
    for (const b of Array.from(this.root.querySelectorAll<HTMLElement>('[data-m]'))) setClass(b, 'is-on', b.dataset.m === this.mode);
    this.sSize.set(Math.round(this.size * 1000));
    this.sFeather.set(this.feather);
    this.sOpacity.set(this.opacity);
    this.syncVariants();
  }

  private spots(): Spot[] { return clone((develop.settings.spots as Spot[] | undefined) ?? []); }

  private write(spots: Spot[], phase: 'drag' | 'end', label: string): void {
    develop.patch('spots', spots.length ? spots : null, phase, label);
    this.host.view.draw();
  }

  private stageOf(nx: number, ny: number): [number, number] { return this.host.view.normToStage(nx, ny); }

  private radiusPx(size: number): number { return size * this.host.view.pxPerLong(); }

  private hitSpot(p: Pt): { i: number; kind: 'src' | 'dst' } | null {
    const spots = this.spots();
    for (let i = spots.length - 1; i >= 0; i -= 1) {
      const s = spots[i];
      const [x, y] = this.stageOf(s.points[0][0], s.points[0][1]);
      const r = Math.max(6, this.radiusPx(s.size));
      if (s.source) {
        const [sx, sy] = this.stageOf(s.points[0][0] + s.source[0], s.points[0][1] + s.source[1]);
        if (Math.hypot(sx - p.sx, sy - p.sy) < r) return { i, kind: 'src' };
      }
      if (Math.hypot(x - p.sx, y - p.sy) < r) return { i, kind: 'dst' };
    }
    return null;
  }

  hover(p: Pt | null): void { this.hoverPt = p; this.host.view.draw(); }

  down(p: Pt): boolean {
    const hit = this.hitSpot(p);
    const spots = this.spots();
    if (hit) {
      this.sel = hit.i;
      const s = spots[hit.i];
      this.size = s.size; this.feather = s.feather; this.opacity = s.opacity; this.mode = s.mode;
      this.syncOpts();
      this.drag = { kind: hit.kind, i: hit.i, start: p, orig: s };
      return true;
    }
    const spot: Spot = { points: [[p.nx, p.ny]], size: this.size, source: null, feather: this.feather, opacity: this.opacity, mode: this.mode };
    spots.push(spot);
    this.sel = spots.length - 1;
    this.drag = { kind: 'new', i: this.sel, start: p, orig: spot };
    this.write(spots, 'drag', 'Spot Removal');
    return true;
  }

  move(p: Pt): void {
    const d = this.drag;
    if (!d) return;
    const spots = this.spots();
    const s = spots[d.i];
    if (!s) return;
    if (d.kind === 'new') {
      const last = s.points[s.points.length - 1];
      const [lx, ly] = this.stageOf(last[0], last[1]);
      if (Math.hypot(lx - p.sx, ly - p.sy) > 4) s.points.push([p.nx, p.ny]);
    } else if (d.kind === 'dst') {
      const dx = p.nx - d.start.nx, dy = p.ny - d.start.ny;
      s.points = d.orig.points.map(([x, y]) => [x + dx, y + dy]);
    } else if (d.orig.source) {
      s.source = [d.orig.source[0] + (p.nx - d.start.nx), d.orig.source[1] + (p.ny - d.start.ny)];
    }
    this.write(spots, 'drag', 'Spot Removal');
  }

  up(): void {
    const d = this.drag;
    this.drag = null;
    if (!d) return;
    const spots = this.spots();
    const s = spots[d.i];
    if (!s) return;
    if (s.mode === 'remove' && (d.kind === 'new' || d.kind === 'dst')) {
      this.fill(d.i, s, 'Remove');
      return;
    }
    if (d.kind === 'new' || !s.source) {
      void this.host.ctx.api.cmd<{ source: [number, number] }>('develop.spotSource', { id: develop.id, spot: s, settings: develop.settings }).then((r) => {
        const now = this.spots();
        if (now[d.i]) { now[d.i].source = r.source; this.write(now, 'end', 'Spot Removal'); }
      }, () => this.write(spots, 'end', 'Spot Removal'));
      return;
    }
    this.write(spots, 'end', 'Move Spot');
  }

  key(_e: KeyboardEvent, combo: string): boolean {
    if ((combo === 'Backspace' || combo === 'Delete') && this.sel >= 0) {
      const spots = this.spots();
      spots.splice(this.sel, 1);
      this.sel = -1;
      this.write(spots, 'end', 'Delete Spot');
      return true;
    }
    if (combo === '[' || combo === ']') {
      this.size = Math.max(0.002, Math.min(0.2, this.size * (combo === ']' ? 1.15 : 1 / 1.15)));
      this.syncOpts();
      this.host.view.draw();
      return true;
    }
    if (combo === 'Escape') { this.host.done(); return true; }
    return false;
  }

  draw(c: CanvasRenderingContext2D): void {
    const spots = this.spots();
    c.save();
    spots.forEach((s, i) => {
      const r = Math.max(4, this.radiusPx(s.size));
      const on = i === this.sel;
      c.lineWidth = on ? 2 : 1;
      c.strokeStyle = on ? '#fff' : 'rgba(255,255,255,0.7)';
      c.shadowColor = 'rgba(0,0,0,0.6)';
      c.shadowBlur = 3;
      const pts = s.points.map(([x, y]) => this.stageOf(x, y));
      if (pts.length > 1) { c.lineWidth = r * 2; c.globalAlpha = 0.18; c.beginPath(); pts.forEach(([x, y], k) => (k ? c.lineTo(x, y) : c.moveTo(x, y))); c.stroke(); c.globalAlpha = 1; c.lineWidth = on ? 2 : 1; }
      c.beginPath(); c.arc(pts[0][0], pts[0][1], r, 0, Math.PI * 2); c.stroke();
      if (s.source) {
        const [sx, sy] = this.stageOf(s.points[0][0] + s.source[0], s.points[0][1] + s.source[1]);
        c.setLineDash([4, 3]);
        c.beginPath(); c.arc(sx, sy, r, 0, Math.PI * 2); c.stroke();
        c.beginPath(); c.moveTo(sx, sy); c.lineTo(pts[0][0], pts[0][1]); c.stroke();
        c.setLineDash([]);
      }
    });
    if (this.hoverPt && !this.drag) {
      c.strokeStyle = 'rgba(255,255,255,0.8)';
      c.lineWidth = 1;
      c.beginPath(); c.arc(this.hoverPt.sx, this.hoverPt.sy, Math.max(4, this.radiusPx(this.size)), 0, Math.PI * 2); c.stroke();
    }
    c.restore();
  }
}

interface Eye { center: [number, number]; rx: number; ry: number; pupilSize: number; darken: number; pet?: boolean; catchlight?: [number, number] }

export class RedEyeTool implements Tool {
  readonly id = 'redeye';
  cursor = 'crosshair';
  private drag: { start: Pt; i: number; light?: boolean } | null = null;
  private pet = false;
  private readonly root: HTMLElement;
  private sel = -1;
  private readonly sPupil: Slider;
  private readonly sDark: Slider;

  constructor(private readonly host: ToolHost) {
    this.root = el(`<div class="fl-tool-opts"><div class="fl-tool-title">${icon('redEye', 14)} Red Eye Correction</div><div class="fl-row"><span class="fl-row-label">Type</span><div class="cv-seg fl-seg-sm fl-grow"><button type="button" data-t="red">Red Eye</button><button type="button" data-t="pet">Pet Eye</button></div></div><label class="fl-check-sm fl-eye-cl" hidden><input type="checkbox"> Add Catchlight (drag the dot to place it)</label><div class="fl-row fl-row-end"><span class="fl-muted fl-grow">Drag across an eye.</span><button class="cv-btn fl-btn-sm" type="button" data-a="clear">Reset</button><button class="cv-btn fl-btn-sm fl-btn-cta" type="button" data-a="done">Done</button></div></div>`);
    const upd = (k: 'pupilSize' | 'darken') => (v: number, phase: 'drag' | 'end') => {
      const eyes = this.eyes();
      if (this.sel >= 0 && eyes[this.sel]) { eyes[this.sel][k] = v; develop.patch('redEye', eyes, phase, 'Red Eye'); }
    };
    this.sPupil = slider('eye.pupil', 'Pupil Size', 0, 100, 50, 50, upd('pupilSize'));
    this.sDark = slider('eye.darken', 'Darken', 0, 100, 50, 50, upd('darken'));
    this.root.insertBefore(this.sDark.root, this.root.lastElementChild);
    this.root.insertBefore(this.sPupil.root, this.sDark.root);
    this.root.addEventListener('click', (e) => {
      const t = (e.target as HTMLElement).closest<HTMLElement>('[data-t]')?.dataset.t;
      if (t) { this.pet = t === 'pet'; this.sync(); }
      const a = (e.target as HTMLElement).closest<HTMLElement>('[data-a]')?.dataset.a;
      if (a === 'clear') develop.patch('redEye', null, 'end', 'Reset Red Eye');
      if (a === 'done') this.host.done();
    });
    q<HTMLInputElement>(this.root, '.fl-eye-cl input').addEventListener('change', (e) => {
      const eyes = this.eyes();
      const eye = eyes[this.sel];
      if (!eye) return;
      if ((e.target as HTMLInputElement).checked) {
        const info = develop.info;
        const long = info ? Math.max(info.width, info.height) : 1;
        eye.catchlight = [eye.center[0] - (0.3 * eye.rx * long) / (info?.width || long), eye.center[1] - (0.3 * eye.ry * long) / (info?.height || long)];
      } else delete eye.catchlight;
      develop.patch('redEye', eyes, 'end', 'Catchlight');
    });
  }

  activate(): void { this.host.drawer.replaceChildren(this.root); this.sync(); }

  private sync(): void {
    for (const b of Array.from(this.root.querySelectorAll<HTMLElement>('[data-t]'))) setClass(b, 'is-on', (b.dataset.t === 'pet') === this.pet);
    const eye = this.eyes()[this.sel];
    setHidden(q(this.root, '.fl-eye-cl'), !(this.pet || eye?.pet));
    q<HTMLInputElement>(this.root, '.fl-eye-cl input').checked = !!eye?.catchlight;
  }

  private eyes(): Eye[] { return clone((develop.settings.redEye as Eye[] | undefined) ?? []); }

  down(p: Pt): boolean {
    const eyes = this.eyes();
    const hit = eyes.findIndex((e) => { if (!e.catchlight) return false; const [x, y] = this.host.view.normToStage(e.catchlight[0], e.catchlight[1]); return Math.hypot(x - p.sx, y - p.sy) < 8; });
    if (hit >= 0) { this.sel = hit; this.drag = { start: p, i: hit, light: true }; this.sync(); return true; }
    eyes.push({ center: [p.nx, p.ny], rx: 0.01, ry: 0.008, pupilSize: 50, darken: 50, pet: this.pet || undefined });
    this.sel = eyes.length - 1;
    this.drag = { start: p, i: this.sel };
    develop.patch('redEye', eyes, 'drag', 'Red Eye');
    return true;
  }

  move(p: Pt): void {
    const d = this.drag;
    if (!d) return;
    const eyes = this.eyes();
    const e = eyes[d.i];
    if (!e) return;
    if (d.light) { e.catchlight = [p.nx, p.ny]; develop.patch('redEye', eyes, 'drag', 'Catchlight'); return; }
    const k = this.host.view.pxPerLong();
    const rx = Math.max(0.003, Math.abs(p.sx - d.start.sx) / k);
    const ry = Math.max(0.003, Math.abs(p.sy - d.start.sy) / k);
    e.rx = rx;
    e.ry = ry;
    develop.patch('redEye', eyes, 'drag', 'Red Eye');
  }

  up(): void { this.drag = null; develop.patch('redEye', this.eyes(), 'end', 'Red Eye'); }

  key(_e: KeyboardEvent, combo: string): boolean {
    if ((combo === 'Backspace' || combo === 'Delete') && this.sel >= 0) { const e = this.eyes(); e.splice(this.sel, 1); this.sel = -1; develop.patch('redEye', e.length ? e : null, 'end', 'Delete Red Eye'); return true; }
    if (combo === 'Escape') { this.host.done(); return true; }
    return false;
  }

  draw(c: CanvasRenderingContext2D, view: DevelopView): void {
    const k = view.pxPerLong();
    c.save();
    c.strokeStyle = 'rgba(255,255,255,0.85)';
    this.eyes().forEach((e, i) => {
      const [x, y] = view.normToStage(e.center[0], e.center[1]);
      c.lineWidth = i === this.sel ? 2 : 1;
      c.beginPath(); c.ellipse(x, y, Math.max(3, e.rx * k), Math.max(3, e.ry * k), 0, 0, Math.PI * 2); c.stroke();
      if (e.catchlight) { const [lx, ly] = view.normToStage(e.catchlight[0], e.catchlight[1]); c.beginPath(); c.arc(lx, ly, 4, 0, Math.PI * 2); c.stroke(); }
    });
    c.restore();
  }
}

export class WbPickerTool implements Tool {
  readonly id = 'wb';
  cursor = 'crosshair';
  private readonly root: HTMLElement;
  private readonly readout: HTMLElement;

  constructor(private readonly host: ToolHost) {
    this.root = el(`<div class="fl-tool-opts"><div class="fl-tool-title">${icon('eyeDropper', 14)} White Balance Selector</div><div class="fl-muted fl-wb-read">Click a neutral grey or white area of the photo.</div><div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm fl-btn-cta" type="button" data-a="done">Done</button></div></div>`);
    this.readout = q(this.root, '.fl-wb-read');
    this.root.addEventListener('click', (e) => { if ((e.target as HTMLElement).closest('[data-a="done"]')) this.host.done(); });
  }

  activate(): void { this.host.drawer.replaceChildren(this.root); }

  down(p: Pt): boolean {
    const id = develop.id;
    if (id === null || p.u < 0 || p.u > 1 || p.v < 0 || p.v > 1) return true;
    void develop.flush().then(() => this.host.ctx.api.cmd<{ temp: number; tint: number }>('develop.whiteBalancePick', { id, x: p.nx, y: p.ny })).then((r) => {
      setText(this.readout, `Temp ${r.temp} K · Tint ${r.tint > 0 ? '+' : ''}${r.tint}`);
      if (!p.e.shiftKey) this.host.done();
    }, (err) => this.host.ctx.fail(err));
    return true;
  }

  key(_e: KeyboardEvent, combo: string): boolean {
    if (combo === 'Escape') { this.host.done(); return true; }
    return false;
  }
}

export class GuidedTool implements Tool {
  readonly id = 'guided';
  cursor = 'crosshair';
  private readonly root: HTMLElement;
  private readonly note: HTMLElement;
  private guides: number[][] = [];
  private drag: { a: Pt; b: Pt } | null = null;
  private sel = -1;

  constructor(private readonly host: ToolHost) {
    this.root = el(`<div class="fl-tool-opts"><div class="fl-tool-title">${icon('upright', 14)} Guided Upright</div><div class="fl-muted fl-wb-read">Draw two to four guides along lines that should be vertical or horizontal. Click a guide and press Delete to remove it.</div><label class="fl-check-sm"><input type="checkbox" data-grid> Show Grid</label><div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm" type="button" data-a="clear">Clear Guides</button><button class="cv-btn fl-btn-sm fl-btn-cta" type="button" data-a="done">Done</button></div></div>`);
    this.note = q(this.root, '.fl-wb-read');
    this.root.addEventListener('click', (e) => {
      const a = (e.target as HTMLElement).closest<HTMLElement>('[data-a]')?.dataset.a;
      if (a === 'done') this.host.done();
      if (a === 'clear') void this.send({ clear: true });
    });
    q<HTMLInputElement>(this.root, '[data-grid]').addEventListener('change', (e) => this.host.view.setGrid((e.target as HTMLInputElement).checked ? 8 : 0));
  }

  activate(): void {
    this.host.drawer.replaceChildren(this.root);
    q<HTMLInputElement>(this.root, '[data-grid]').checked = this.host.view.grid > 0;
    this.sel = -1;
    void this.send({ read: true });
  }

  private async send(params: Record<string, unknown>): Promise<void> {
    const id = develop.id;
    if (id === null) return;
    try {
      if (!params.read) await develop.flush();
      const r = await this.host.ctx.api.cmd<{ guides: number[][]; count: number }>('develop.uprightGuides', { id, ...params });
      this.guides = r.guides;
      if (this.sel >= this.guides.length) this.sel = -1;
      setText(this.note, r.count ? `${r.count} guide${r.count === 1 ? '' : 's'}${r.count < 2 ? ': add another to correct perspective' : ''}. Click a guide and press Delete to remove it.` : 'Draw two to four guides along lines that should be vertical or horizontal.');
      this.host.view.draw();
    } catch (err) { this.host.ctx.fail(err); }
  }

  private hit(p: Pt): number {
    const v = this.host.view;
    let best = -1, bestD = 8;
    this.guides.forEach((g, i) => {
      const [x1, y1] = v.normToStage(g[0], g[1]);
      const [x2, y2] = v.normToStage(g[2], g[3]);
      const dx = x2 - x1, dy = y2 - y1;
      const t = Math.max(0, Math.min(1, ((p.sx - x1) * dx + (p.sy - y1) * dy) / Math.max(1e-6, dx * dx + dy * dy)));
      const d = Math.hypot(p.sx - (x1 + t * dx), p.sy - (y1 + t * dy));
      if (d < bestD) { bestD = d; best = i; }
    });
    return best;
  }

  down(p: Pt): boolean {
    const i = this.hit(p);
    if (i >= 0) { this.sel = i; this.host.view.draw(); return true; }
    this.sel = -1;
    this.drag = { a: p, b: p };
    return true;
  }

  move(p: Pt): void { if (this.drag) this.drag.b = p; }

  up(p: Pt): void {
    const d = this.drag;
    this.drag = null;
    if (!d) return;
    if (Math.hypot(p.sx - d.a.sx, p.sy - d.a.sy) < 16) { this.host.view.draw(); return; }
    void this.send({ add: [d.a.nx, d.a.ny, p.nx, p.ny] });
  }

  key(_e: KeyboardEvent, combo: string): boolean {
    if ((combo === 'Backspace' || combo === 'Delete') && this.sel >= 0) { const i = this.sel; this.sel = -1; void this.send({ remove: i }); return true; }
    if (combo === 'Escape') { this.host.done(); return true; }
    return false;
  }

  draw(c: CanvasRenderingContext2D, view: DevelopView): void {
    c.save();
    c.lineWidth = 2;
    this.guides.forEach((g, i) => {
      const [x1, y1] = view.normToStage(g[0], g[1]);
      const [x2, y2] = view.normToStage(g[2], g[3]);
      c.strokeStyle = i === this.sel ? 'rgba(255,170,60,0.95)' : 'rgba(255,255,255,0.9)';
      c.beginPath(); c.moveTo(x1, y1); c.lineTo(x2, y2); c.stroke();
      for (const [x, y] of [[x1, y1], [x2, y2]]) { c.beginPath(); c.arc(x, y, 3.5, 0, Math.PI * 2); c.stroke(); }
    });
    if (this.drag) {
      c.setLineDash([5, 4]);
      c.strokeStyle = 'rgba(255,255,255,0.9)';
      c.beginPath(); c.moveTo(this.drag.a.sx, this.drag.a.sy); c.lineTo(this.drag.b.sx, this.drag.b.sy); c.stroke();
    }
    c.restore();
  }
}

export class FringePickerTool implements Tool {
  readonly id = 'fringe';
  cursor = 'crosshair';
  private readonly root: HTMLElement;
  private readonly readout: HTMLElement;

  constructor(private readonly host: ToolHost) {
    this.root = el(`<div class="fl-tool-opts"><div class="fl-tool-title">${icon('eyeDropper', 14)} Fringe Color Selector</div><div class="fl-muted fl-wb-read">Zoom in and click a purple or green fringe along an edge.</div><div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm fl-btn-cta" type="button" data-a="done">Done</button></div></div>`);
    this.readout = q(this.root, '.fl-wb-read');
    this.root.addEventListener('click', (e) => { if ((e.target as HTMLElement).closest('[data-a="done"]')) this.host.done(); });
  }

  activate(): void { this.host.drawer.replaceChildren(this.root); }

  down(p: Pt): boolean {
    const id = develop.id;
    if (id === null || p.u < 0 || p.u > 1 || p.v < 0 || p.v > 1) return true;
    void develop.flush().then(() => this.host.ctx.api.cmd<{ kind: string; lo?: number; hi?: number }>('develop.fringeHue', { id, x: p.nx, y: p.ny })).then((r) => {
      if (!r.kind) { setText(this.readout, 'That color is not a purple or green fringe. Try a pixel right on the colored edge.'); return; }
      const name = r.kind === 'purple' ? 'Purple' : 'Green';
      const opt = { ...((develop.settings.optics as Record<string, unknown> | undefined) ?? {}) };
      const amt = Number(opt[`defringe${name}`] ?? 0);
      opt[`defringe${name}`] = amt > 0 ? amt : 5;
      opt[`defringe${name}HueLo`] = r.lo;
      opt[`defringe${name}HueHi`] = r.hi;
      develop.patch('optics', opt, 'end', `Defringe ${name}`);
      setText(this.readout, `${name} fringe: hue ${r.lo} to ${r.hi}`);
      if (!p.e.shiftKey) this.host.done();
    }, (err) => this.host.ctx.fail(err));
    return true;
  }

  key(_e: KeyboardEvent, combo: string): boolean {
    if (combo === 'Escape') { this.host.done(); return true; }
    return false;
  }
}

interface PointColor { hue: number; chroma: number; lum: number; hueShift: number; satShift: number; lumShift: number; variance: number; range: number }

const POINT_SLIDERS: Array<[keyof PointColor, string, number, number]> = [['hueShift', 'Hue Shift', -100, 100], ['satShift', 'Sat Shift', -100, 100], ['lumShift', 'Lum Shift', -100, 100], ['variance', 'Variance', -100, 100], ['range', 'Range', 0, 100]];

export class PointColorTool implements Tool {
  readonly id = 'point';
  cursor = 'crosshair';
  private readonly root: HTMLElement;
  private readonly swatches: HTMLElement;
  private readonly sliders = new Map<string, Slider>();
  private current = 0;

  constructor(private readonly host: ToolHost) {
    this.root = el(`<div class="fl-tool-opts"><div class="fl-tool-title">${icon('eyeDropper', 14)} Point Color</div><div class="fl-muted">Click a colour in the photo to add it (up to eight), then shift it.</div><div class="fl-point-swatches"></div><div class="fl-point-sliders"></div><div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm" type="button" data-a="remove">Remove</button><button class="cv-btn fl-btn-sm fl-btn-cta" type="button" data-a="done">Done</button></div></div>`);
    this.swatches = q(this.root, '.fl-point-swatches');
    const box = q(this.root, '.fl-point-sliders');
    for (const [k, label, min, max] of POINT_SLIDERS) {
      const s = new Slider({ id: k, label, min, max, default: k === 'range' ? 50 : 0, step: 1, decimals: 0 }, { input: (id, v, phase) => this.setValue(id as keyof PointColor, v, phase) });
      this.sliders.set(k, s);
      box.appendChild(s.root);
    }
    this.root.addEventListener('click', (e) => {
      const t = e.target as HTMLElement;
      const sw = t.closest<HTMLElement>('[data-i]');
      if (sw) { this.current = Number(sw.dataset.i); this.paint(); return; }
      if (t.closest('[data-a="done"]')) this.host.done();
      else if (t.closest('[data-a="remove"]')) {
        const pts = this.points();
        if (!pts.length) return;
        pts.splice(this.current, 1);
        this.current = Math.max(0, this.current - 1);
        develop.patch('pointColors', pts, 'end', 'Remove Point Color');
        this.paint();
      }
    });
  }

  private points(): PointColor[] { return clone((develop.settings.pointColors as PointColor[] | undefined) ?? []); }

  activate(): void { this.host.drawer.replaceChildren(this.root); this.paint(); }

  private paint(): void {
    const pts = this.points();
    const html = pts.map((p, i) => {
      const a = p.chroma * Math.cos((p.hue * Math.PI) / 180), b = p.chroma * Math.sin((p.hue * Math.PI) / 180);
      return `<button class="fl-point-sw${i === this.current ? ' is-on' : ''}" type="button" data-i="${i}" style="background: oklab(${(p.lum * 100).toFixed(1)}% ${a.toFixed(4)} ${b.toFixed(4)})" aria-label="Point ${i + 1}"></button>`;
    }).join('');
    if (this.swatches.dataset.key !== html) { this.swatches.dataset.key = html; this.swatches.innerHTML = html || '<span class="fl-muted">No colours yet</span>'; }
    const cur = pts[this.current];
    for (const [k, s] of this.sliders) s.set(cur ? Number(cur[k as keyof PointColor] ?? (k === 'range' ? 50 : 0)) : (k === 'range' ? 50 : 0));
  }

  private setValue(k: keyof PointColor, v: number, phase: 'drag' | 'end'): void {
    const pts = this.points();
    if (!pts[this.current]) return;
    pts[this.current] = { ...pts[this.current], [k]: v };
    develop.patch('pointColors', pts, phase, `Point Color ${k.replace('Shift', '')}`);
  }

  down(p: Pt): boolean {
    const id = develop.id;
    if (id === null || p.u < 0 || p.u > 1 || p.v < 0 || p.v > 1) return true;
    void this.host.ctx.api.cmd<{ lab: [number, number, number] }>('develop.sampleColor', { id, x: p.nx, y: p.ny, settings: develop.settings }).then((r) => {
      const [l, a, b] = r.lab;
      const pts = this.points();
      if (pts.length >= 8) { this.host.ctx.fail(new Error('Point Color holds eight colours; remove one first')); return; }
      pts.push({ lum: l, chroma: Math.hypot(a, b), hue: ((Math.atan2(b, a) * 180) / Math.PI + 360) % 360, hueShift: 0, satShift: 0, lumShift: 0, variance: 0, range: 50 });
      this.current = pts.length - 1;
      develop.patch('pointColors', pts, 'end', 'Add Point Color');
      this.paint();
    }, (err) => this.host.ctx.fail(err));
    return true;
  }

  key(_e: KeyboardEvent, combo: string): boolean {
    if (combo === 'Escape') { this.host.done(); return true; }
    return false;
  }
}

export type TatMode = 'curve' | 'hue' | 'sat' | 'lum' | 'bw';
const TAT_TITLES: Record<TatMode, string> = { curve: 'Tone Curve', hue: 'Hue', sat: 'Saturation', lum: 'Luminance', bw: 'B&W Mix' };

export class TatTool implements Tool {
  readonly id = 'tat';
  cursor = 'ns-resize';
  mode: TatMode = 'curve';
  private readonly root: HTMLElement;
  private readonly read: HTMLElement;
  private drag: { cid: string; y: number; start: number; seq: number } | null = null;
  private seq = 0;

  constructor(private readonly host: ToolHost) {
    this.root = el(`<div class="fl-tool-opts"><div class="fl-tool-title">${icon('targeted', 14)} <span class="fl-tat-title"></span></div><div class="fl-muted fl-tat-read">Press on the photo and drag up or down to adjust what is under the pointer.</div><div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm fl-btn-cta" type="button" data-a="done">Done</button></div></div>`);
    this.read = q(this.root, '.fl-tat-read');
    this.root.addEventListener('click', (e) => { if ((e.target as HTMLElement).closest('[data-a="done"]')) this.host.done(); });
  }

  activate(): void {
    setText(q(this.root, '.fl-tat-title'), `Targeted Adjustment: ${TAT_TITLES[this.mode]}`);
    this.host.drawer.replaceChildren(this.root);
  }

  down(p: Pt): boolean {
    const id = develop.id;
    if (id === null || p.u < 0 || p.u > 1 || p.v < 0 || p.v > 1) return true;
    const seq = ++this.seq;
    const y = p.e.clientY;
    this.drag = { cid: '', y, start: 0, seq };
    void this.host.ctx.api.cmd<{ band: string; region: string }>('develop.sampleColor', { id, x: p.nx, y: p.ny, settings: develop.settings }).then((r) => {
      if (!this.drag || this.drag.seq !== seq) return;
      const cid = this.mode === 'curve' ? `curve.${r.region}` : this.mode === 'bw' ? `bw.${r.band}` : `mixer.${r.band}.${this.mode}`;
      this.drag.cid = cid;
      this.drag.start = develop.value(cid);
      setText(this.read, `${develop.labelFor(cid, this.drag.start)} (${this.mode === 'curve' ? r.region : r.band})`);
    }, (err) => this.host.ctx.fail(err));
    return true;
  }

  move(p: Pt): void {
    const d = this.drag;
    if (!d || !d.cid) return;
    const v = d.start + (d.y - p.e.clientY) * 0.5;
    develop.set(d.cid, v, 'drag');
    setText(this.read, develop.labelFor(d.cid, develop.value(d.cid)));
  }

  up(): void {
    const d = this.drag;
    this.drag = null;
    if (d?.cid) develop.set(d.cid, develop.value(d.cid), 'end');
  }

  key(_e: KeyboardEvent, combo: string): boolean {
    if (combo === 'Escape') { this.host.done(); return true; }
    return false;
  }
}

export function toolStrip(): HTMLElement {
  const b = (cmd: string, ic: string, label: string) => `<button class="cv-icon-btn" type="button" data-cmd="${cmd}" aria-label="${label}">${icon(ic, 17)}</button>`;
  return el(`<div class="fl-toolstrip">${b('develop.tool.crop', 'crop', 'Crop and Straighten')}${b('develop.tool.spot', 'spotHeal', 'Healing')}${b('develop.tool.redeye', 'redEye', 'Red Eye Correction')}${b('develop.tool.masks', 'masking', 'Masking')}</div>`);
}
