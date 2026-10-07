import { el, q, setClass, setStyleVar, setText } from './dom';

export interface SliderSpec {
  id: string;
  label: string;
  min: number;
  max: number;
  default: number;
  step: number;
  decimals: number;
  track?: { kind: string; band?: number; from?: string; to?: string };
}

let bandHues: number[] = [0, 30, 60, 120, 180, 240, 270, 300];

export function setBandHues(hues: number[]): void {
  if (hues.length) bandHues = hues.slice();
}

const ramp = (stops: string[]): string => `linear-gradient(90deg, ${stops.join(', ')})`;
const colorAt = (hue: number, sat: number, light: number): string => `hsl(${(((hue % 360) + 360) % 360).toFixed(1)} ${sat}% ${light}%)`;

export function trackBackground(t: SliderSpec['track']): string {
  if (!t) return '';
  const hue = bandHues[t.band ?? 0] ?? 0;
  if (t.kind === 'temp') return ramp(['#4a78d6', '#cfcfcf', '#e2b84a']);
  if (t.kind === 'tint') return ramp(['#4aa85a', '#cfcfcf', '#b84ab8']);
  if (t.kind === 'rainbow') return ramp(Array.from({ length: 13 }, (_, k) => colorAt(k * 30, 72, 54)));
  if (t.kind === 'hue') return ramp([colorAt(hue - 45, 68, 52), colorAt(hue, 72, 52), colorAt(hue + 45, 68, 52)]);
  if (t.kind === 'sat') return ramp(['#8c8c8c', colorAt(hue, 82, 50)]);
  if (t.kind === 'lum') return ramp([colorAt(hue, 55, 16), colorAt(hue, 66, 74)]);
  if (t.kind === 'gradient') return ramp([t.from ?? '#808080', t.to ?? '#808080']);
  if (t.kind === 'exposure') return ramp(['#181818', '#ececec']);
  return '';
}

export interface SliderEvents {
  input: (id: string, value: number, phase: 'drag' | 'end') => void;
  reset?: (id: string) => void;
}

export class Slider {
  readonly root: HTMLElement;
  private readonly track: HTMLElement;
  private readonly num: HTMLInputElement;
  private value: number;
  private dragging = false;

  constructor(readonly spec: SliderSpec, private readonly on: SliderEvents) {
    this.value = spec.default;
    const centered = spec.min < 0 && spec.max > 0;
    this.root = el(`<div class="fl-sl${centered ? ' is-centered' : ''}" data-id="${spec.id}"><span class="fl-sl-label"></span><input class="fl-sl-num" type="text" inputmode="decimal" spellcheck="false" aria-label=""><div class="fl-sl-track" role="slider" tabindex="0" aria-valuemin="${spec.min}" aria-valuemax="${spec.max}"><div class="fl-sl-rail"></div><div class="fl-sl-fill"></div><div class="fl-sl-thumb"></div></div></div>`);
    setText(q(this.root, '.fl-sl-label'), spec.label);
    this.track = q(this.root, '.fl-sl-track');
    this.num = q<HTMLInputElement>(this.root, '.fl-sl-num');
    this.num.setAttribute('aria-label', spec.label);
    this.track.setAttribute('aria-label', spec.label);
    const bg = trackBackground(spec.track);
    if (bg) { setStyleVar(this.root, '--fl-sl-bg', bg); setClass(this.root, 'is-tinted', true); }
    this.wire();
    this.paint();
  }

  get(): number { return this.value; }

  set(v: number): void {
    if (this.dragging || v === this.value) return;
    this.value = v;
    this.paint();
  }

  setLabel(text: string): void { setText(q(this.root, '.fl-sl-label'), text); }

  private frac(v: number): number { return (v - this.spec.min) / (this.spec.max - this.spec.min); }

  private fmt(v: number): string {
    const s = this.spec;
    const t = v.toFixed(s.decimals);
    return s.min < 0 && v > 0 ? `+${t}` : t;
  }

  private paint(): void {
    const f = Math.max(0, Math.min(1, this.frac(this.value)));
    setStyleVar(this.root, '--f', f.toFixed(4));
    const zero = this.spec.min < 0 && this.spec.max > 0 ? this.frac(0) : 0;
    setStyleVar(this.root, '--z', zero.toFixed(4));
    setClass(this.root, 'is-changed', Math.abs(this.value - this.spec.default) > 1e-9);
    if (document.activeElement !== this.num) this.num.value = this.fmt(this.value);
    this.track.setAttribute('aria-valuenow', String(this.value));
  }

  private snap(v: number): number {
    const s = this.spec;
    const stepped = Math.round(v / s.step) * s.step;
    return Number(Math.max(s.min, Math.min(s.max, stepped)).toFixed(s.decimals));
  }

  private emit(v: number, phase: 'drag' | 'end'): void {
    const nv = this.snap(v);
    const changed = nv !== this.value;
    this.value = nv;
    this.paint();
    if (changed || phase === 'end') this.on.input(this.spec.id, nv, phase);
  }

  private wire(): void {
    let startX = 0, startV = 0, width = 1, moved = false;
    this.track.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      e.preventDefault();
      this.track.focus({ preventScroll: true });
      const r = this.track.getBoundingClientRect();
      width = Math.max(1, r.width);
      startX = e.clientX;
      moved = false;
      const onThumb = (e.target as HTMLElement).closest('.fl-sl-thumb');
      startV = onThumb ? this.value : this.spec.min + ((e.clientX - r.left) / width) * (this.spec.max - this.spec.min);
      this.dragging = true;
      setClass(this.root, 'is-dragging', true);
      this.track.setPointerCapture(e.pointerId);
      if (!onThumb) { moved = true; this.emitDrag(startV); }
    });
    this.track.addEventListener('pointermove', (e) => {
      if (!this.dragging) return;
      const fine = e.shiftKey ? 0.2 : 1;
      const v = startV + ((e.clientX - startX) / width) * (this.spec.max - this.spec.min) * fine;
      moved = true;
      this.emitDrag(v);
    });
    const end = () => {
      if (!this.dragging) return;
      this.dragging = false;
      setClass(this.root, 'is-dragging', false);
      if (moved) this.emit(this.value, 'end');
    };
    this.track.addEventListener('pointerup', end);
    this.track.addEventListener('pointercancel', end);
    this.track.addEventListener('dblclick', () => this.reset());
    q(this.root, '.fl-sl-label').addEventListener('dblclick', () => this.reset());
    this.track.addEventListener('keydown', (e) => {
      const big = e.shiftKey ? 10 : 1;
      if (e.key === 'ArrowRight' || e.key === 'ArrowUp') { e.preventDefault(); e.stopPropagation(); this.emit(this.value + this.spec.step * big, 'end'); }
      if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') { e.preventDefault(); e.stopPropagation(); this.emit(this.value - this.spec.step * big, 'end'); }
    });
    this.num.addEventListener('keydown', (e) => {
      e.stopPropagation();
      if (e.key === 'Enter') this.num.blur();
      if (e.key === 'Escape') { this.num.value = this.fmt(this.value); this.num.blur(); }
      if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        e.preventDefault();
        this.emit(this.value + (e.key === 'ArrowUp' ? 1 : -1) * this.spec.step * (e.shiftKey ? 10 : 1), 'end');
      }
    });
    this.num.addEventListener('focus', () => this.num.select());
    this.num.addEventListener('change', () => {
      const v = Number(this.num.value.replace(',', '.'));
      if (Number.isFinite(v)) this.emit(v, 'end'); else this.num.value = this.fmt(this.value);
    });
    this.num.addEventListener('blur', () => { this.num.value = this.fmt(this.value); });
  }

  private emitDrag(v: number): void { this.emit(v, 'drag'); }

  reset(): void {
    if (this.on.reset) { this.on.reset(this.spec.id); return; }
    this.emit(this.spec.default, 'end');
  }
}
