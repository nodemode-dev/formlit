import { develop } from '../../state/develop';
import { el, q, setStyleVar, setText } from '../../ui/dom';

export class ColorWheel {
  readonly root: HTMLElement;
  private readonly puck: HTMLElement;
  private dragging = false;

  constructor(private readonly key: string, label: string, size = 128) {
    this.root = el(`<div class="fl-wheel" style="--size:${size}px"><div class="fl-wheel-name"></div><div class="fl-wheel-disc"><div class="fl-wheel-puck"></div></div><div class="fl-wheel-read"></div></div>`);
    setText(q(this.root, '.fl-wheel-name'), label);
    this.puck = q(this.root, '.fl-wheel-puck');
    const disc = q(this.root, '.fl-wheel-disc');
    const at = (e: PointerEvent, phase: 'drag' | 'end') => {
      const r = disc.getBoundingClientRect();
      const dx = (e.clientX - r.left) / r.width * 2 - 1, dy = (e.clientY - r.top) / r.height * 2 - 1;
      const fine = e.shiftKey ? 0.35 : 1;
      const sat = Math.min(1, Math.hypot(dx, dy) * fine) * 100;
      const hue = ((Math.atan2(-dy, dx) * 180) / Math.PI + 360) % 360;
      develop.set(`grading.${this.key}.hue`, Math.round(hue), 'drag');
      develop.set(`grading.${this.key}.sat`, Math.round(sat), phase, `Color Grading ${label}`);
      this.sync();
    };
    disc.addEventListener('pointerdown', (e) => { if (e.button !== 0) return; this.dragging = true; disc.setPointerCapture(e.pointerId); at(e, 'drag'); });
    disc.addEventListener('pointermove', (e) => { if (this.dragging) at(e, 'drag'); });
    disc.addEventListener('pointerup', (e) => { if (!this.dragging) return; this.dragging = false; at(e, 'end'); });
    disc.addEventListener('dblclick', () => {
      develop.set(`grading.${this.key}.hue`, 0, 'drag');
      develop.set(`grading.${this.key}.sat`, 0, 'end', `Reset ${label}`);
      this.sync();
    });
  }

  sync(): void {
    const hue = develop.value(`grading.${this.key}.hue`);
    const sat = develop.value(`grading.${this.key}.sat`);
    const a = (hue * Math.PI) / 180;
    const r = sat / 100;
    setStyleVar(this.puck, '--px', `${(50 + Math.cos(a) * r * 50).toFixed(2)}%`);
    setStyleVar(this.puck, '--py', `${(50 - Math.sin(a) * r * 50).toFixed(2)}%`);
    setText(q(this.root, '.fl-wheel-read'), sat ? `H ${Math.round(hue)}  S ${Math.round(sat)}` : 'H 0  S 0');
  }
}
