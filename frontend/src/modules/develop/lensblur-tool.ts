import { clone, develop } from '../../state/develop';
import { el, q, setClass, setHidden, setText } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { Slider } from '../../ui/slider';
import type { ToolHost } from './tools';
import type { DevelopView, Pt, Tool } from './view';

type Mode = 'focus' | 'brushFocus' | 'brushBlur';
interface Stroke { mode: 'focus' | 'blur'; points: number[][]; size: number; feather: number; flow: number; density: number }

export class LensBlurTool implements Tool {
  readonly id = 'lensblur';
  cursor = 'crosshair';
  private mode: Mode = 'focus';
  private readonly root: HTMLElement;
  private readonly brushBox: HTMLElement;
  private readonly readout: HTMLElement;
  private brush = { size: 0.04, feather: 50, flow: 70 };
  private hoverPt: Pt | null = null;
  private stroke: Stroke | null = null;
  private box: { a: Pt; b: Pt } | null = null;

  constructor(private readonly host: ToolHost) {
    this.root = el(`<div class="fl-tool-opts"><div class="fl-tool-title">${icon('lensBlur', 14)} Lens Blur Refine</div>
<div class="cv-seg fl-seg-sm fl-lb-modes"><button type="button" data-m="focus">Focus Point</button><button type="button" data-m="brushFocus">Focus Brush</button><button type="button" data-m="brushBlur">Blur Brush</button></div>
<div class="fl-muted fl-lb-read"></div>
<div class="fl-lb-brush"></div>
<label class="fl-check fl-check-sm"><input type="checkbox" data-depth> Visualize Depth</label>
<div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm" type="button" data-a="clear">Clear Brushes</button><button class="cv-btn fl-btn-sm fl-btn-cta" type="button" data-a="done">Done</button></div></div>`);
    this.brushBox = q(this.root, '.fl-lb-brush');
    this.readout = q(this.root, '.fl-lb-read');
    const mk = (id: string, label: string, min: number, max: number, val: number, fn: (v: number) => void) => {
      const s = new Slider({ id, label, min, max, default: val, step: 1, decimals: 0 }, { input: (_id, v) => fn(v) });
      s.set(val);
      return s.root;
    };
    this.brushBox.append(mk('lb.size', 'Size', 4, 300, 40, (v) => { this.brush.size = v / 1000; this.host.view.draw(); }), mk('lb.feather', 'Feather', 0, 100, 50, (v) => { this.brush.feather = v; }), mk('lb.flow', 'Flow', 1, 100, 70, (v) => { this.brush.flow = v; }));
    this.root.addEventListener('click', (e) => {
      const t = e.target as HTMLElement;
      const m = t.closest<HTMLElement>('[data-m]')?.dataset.m as Mode | undefined;
      if (m) { this.setMode(m); return; }
      const a = t.closest<HTMLElement>('[data-a]')?.dataset.a;
      if (a === 'done') this.host.done();
      else if (a === 'clear') this.write([], 'Clear Lens Blur Brushes');
    });
    q<HTMLInputElement>(this.root, '[data-depth]').addEventListener('change', (e) => { this.host.view.depth = (e.target as HTMLInputElement).checked; this.host.view.schedule(); });
  }

  activate(): void {
    this.host.drawer.replaceChildren(this.root);
    q<HTMLInputElement>(this.root, '[data-depth]').checked = this.host.view.depth;
    this.setMode(this.mode);
  }

  setMode(m: Mode): void {
    this.mode = m;
    for (const b of Array.from(this.root.querySelectorAll<HTMLElement>('[data-m]'))) setClass(b, 'is-on', b.dataset.m === m);
    setHidden(this.brushBox, m === 'focus');
    const lb = (develop.settings.lensBlur as Record<string, unknown> | undefined) ?? {};
    setText(this.readout, !lb.depth ? 'Build the depth map first.' : m === 'focus' ? 'Click to focus on a point, or drag a box to keep an area sharp.' : m === 'brushFocus' ? 'Paint where the photo should stay sharp.' : 'Paint where the photo should be blurred.');
    this.host.view.draw();
  }

  private strokes(): Stroke[] { return clone((((develop.settings.lensBlur as Record<string, unknown> | undefined) ?? {}).refine as Stroke[] | undefined) ?? []); }

  private write(strokes: Stroke[], label: string, phase: 'drag' | 'end' = 'end'): void {
    const lb = { ...((develop.settings.lensBlur as Record<string, unknown> | undefined) ?? {}) };
    if (strokes.length) lb.refine = strokes; else delete lb.refine;
    develop.patch('lensBlur', lb, phase, label);
  }

  hover(p: Pt | null): void { this.hoverPt = p; if (this.mode !== 'focus') this.host.view.draw(); }

  down(p: Pt): boolean {
    const lb = (develop.settings.lensBlur as Record<string, unknown> | undefined) ?? {};
    if (!lb.depth) { this.host.ctx.fail(new Error('Build the depth map first')); return true; }
    if (this.mode === 'focus') { this.box = { a: p, b: p }; return true; }
    this.stroke = { mode: this.mode === 'brushFocus' ? 'focus' : 'blur', points: [[p.nx, p.ny]], size: this.brush.size, feather: this.brush.feather, flow: this.brush.flow, density: 100 };
    this.host.view.setDragging(true);
    this.write([...this.strokes(), this.stroke], 'Lens Blur Brush', 'drag');
    return true;
  }

  move(p: Pt): void {
    if (this.box) { this.box.b = p; this.host.view.draw(); return; }
    const s = this.stroke;
    if (!s) return;
    const last = s.points[s.points.length - 1];
    const [lx, ly] = this.host.view.normToStage(last[0], last[1]);
    if (Math.hypot(lx - p.sx, ly - p.sy) < 3) return;
    s.points.push([Number(p.nx.toFixed(5)), Number(p.ny.toFixed(5))]);
    const all = this.strokes();
    all[all.length - 1] = s;
    this.write(all, 'Lens Blur Brush', 'drag');
  }

  up(): void {
    if (this.box) {
      const { a, b } = this.box;
      this.box = null;
      this.host.view.draw();
      const id = develop.id;
      if (id === null) return;
      const area = Math.abs(a.sx - b.sx) > 6 && Math.abs(a.sy - b.sy) > 6;
      const params = area ? { id, box: [Math.min(a.nx, b.nx), Math.min(a.ny, b.ny), Math.max(a.nx, b.nx), Math.max(a.ny, b.ny)], apply: false } : { id, x: a.nx, y: a.ny, apply: false };
      void develop.flush().then(() => this.host.ctx.api.cmd<{ focalDistance: number; focalRange: number | null }>('develop.lensBlurFocus', params)).then((r) => {
        const lb: Record<string, unknown> = { ...((develop.settings.lensBlur as Record<string, unknown> | undefined) ?? {}), focalDistance: r.focalDistance };
        if (r.focalRange !== null) lb.focalRange = r.focalRange;
        develop.patch('lensBlur', lb, 'end', 'Lens Blur Focus');
        setText(this.readout, `Focus ${r.focalDistance}${r.focalRange !== null ? `, range ${r.focalRange}` : ''}`);
      }, (err) => this.host.ctx.fail(err));
      return;
    }
    if (!this.stroke) return;
    this.stroke = null;
    this.host.view.setDragging(false);
    this.write(this.strokes(), 'Lens Blur Brush', 'end');
  }

  key(_e: KeyboardEvent, combo: string): boolean {
    if (combo === 'Escape') { this.host.done(); return true; }
    if (combo === '[' || combo === ']') { this.brush.size = Math.max(0.004, Math.min(0.3, this.brush.size * (combo === ']' ? 1.15 : 1 / 1.15))); this.host.view.draw(); return true; }
    return false;
  }

  draw(c: CanvasRenderingContext2D, view: DevelopView): void {
    c.save();
    c.shadowColor = 'rgba(0,0,0,0.6)';
    c.shadowBlur = 3;
    c.strokeStyle = 'rgba(255,255,255,0.92)';
    if (this.box) {
      c.setLineDash([5, 4]);
      c.strokeRect(Math.min(this.box.a.sx, this.box.b.sx), Math.min(this.box.a.sy, this.box.b.sy), Math.abs(this.box.b.sx - this.box.a.sx), Math.abs(this.box.b.sy - this.box.a.sy));
      c.setLineDash([]);
    }
    if (this.mode !== 'focus' && this.hoverPt) {
      const r = this.brush.size * view.pxPerLong();
      c.beginPath(); c.arc(this.hoverPt.sx, this.hoverPt.sy, r, 0, Math.PI * 2); c.stroke();
      c.setLineDash([3, 3]);
      c.beginPath(); c.arc(this.hoverPt.sx, this.hoverPt.sy, Math.max(1, r * (1 - this.brush.feather / 100)), 0, Math.PI * 2); c.stroke();
      c.setLineDash([]);
    }
    c.restore();
  }
}
