import { clone } from '../../../demo/src/engine/settings';
import { develop } from '../../../demo/src/shims/develop';
import { BITMAPS } from './masks/shapes';
import { masksOf, type Component, type Mask, type Op, type Shape } from './masks/types';
import { stemOf } from './virtual-copy';

export type Pending = '' | 'linear' | 'radial';

export const NAMES: Record<string, string> = {
  subject: 'Subject', sky: 'Sky', background: 'Background', brush: 'Brush', linear: 'Linear Gradient', radial: 'Radial Gradient', colorRange: 'Color Range', luminanceRange: 'Luminance Range',
};

export const ICONS: Record<string, string> = {
  subject: 'maskSubject', sky: 'maskSky', background: 'maskBackground', brush: 'maskBrush', linear: 'maskLinear', radial: 'maskRadial', colorRange: 'maskColor', luminanceRange: 'maskLuminance',
};

export class MaskState {
  sel = -1;
  comp = 0;
  pending: Pending = '';
  pick = false;
  showOverlay = false;
  active = false;
  brush = { size: 30, feather: 60, flow: 80, density: 100, erase: false };
  private readonly fns = new Set<() => void>();

  listen(fn: () => void): void { this.fns.add(fn); }

  changed(): void { for (const fn of this.fns) fn(); }

  masks(): Mask[] { return clone(masksOf(develop.settings)); }

  current(): { masks: Mask[]; m: Mask | undefined; c: Component | undefined } {
    const masks = this.masks();
    const m = masks[this.sel];
    return { masks, m, c: m?.components[this.comp] };
  }

  write(masks: Mask[], phase: 'drag' | 'end', label: string): void {
    const tidy = (v: unknown): unknown => (typeof v === 'number' ? Math.round(v * 1e5) / 1e5 : Array.isArray(v) ? v.map(tidy) : v && typeof v === 'object' ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, tidy(x)])) : v);
    develop.patch('masks', masks.length ? (phase === 'end' ? (tidy(masks) as Mask[]) : masks) : null, phase, label);
  }

  nextId(masks: Mask[]): number { return masks.reduce((a, m) => Math.max(a, m.id), 0) + 1; }

  shapeFor(kind: string): Shape {
    switch (kind) {
      case 'linear': return { kind, start: [0.5, 0.2], end: [0.5, 0.6] };
      case 'radial': return { kind, center: [0.5, 0.5], rx: 0.2, ry: 0.15, angle: 0, feather: 50 };
      case 'brush': return { kind, strokes: [] };
      case 'luminanceRange': return { kind, lo: 0.5, hi: 1, loFeather: 0.1, hiFeather: 0.1 };
      case 'colorRange': return { kind, samples: [], refine: 50 };
      default: return { kind };
    }
  }

  bitmapKey(kind: string): string | null {
    const item = develop.item;
    if (!item) return null;
    const key = `${stemOf(item)}_${kind === 'background' ? 'subject' : kind}`;
    return BITMAPS.has(key) ? key : null;
  }

  place(shape: Shape, op: 'new' | Op, masks: Mask[]): void {
    if (op === 'new' || !masks[this.sel]) {
      masks.push({ id: this.nextId(masks), name: `Mask ${masks.length + 1}`, visible: true, components: [{ shape, op: 'add' }], adjust: {} });
      this.sel = masks.length - 1;
      this.comp = 0;
    } else {
      masks[this.sel].components.push({ shape, op });
      this.comp = masks[this.sel].components.length - 1;
    }
  }

  create(kind: string, op: 'new' | Op, patch: Partial<Shape> = {}): boolean {
    let shape = this.shapeFor(kind);
    if (kind === 'subject' || kind === 'sky' || kind === 'background') {
      const key = this.bitmapKey(kind);
      if (!key) return false;
      shape = { kind, bitmap: key, refine: 0, shift: 0, feather: 0 };
    }
    shape = { ...shape, ...patch };
    const masks = this.masks();
    this.place(shape, op, masks);
    if (op === 'new') masks[this.sel].name = NAMES[kind] ?? kind;
    this.pending = '';
    this.pick = kind === 'colorRange';
    this.write(masks, 'end', `Mask: ${NAMES[kind] ?? kind}`);
    return true;
  }
}

export const maskState = new MaskState();
