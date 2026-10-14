import { develop } from '../../state/develop';
import { el, q, setText } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { toast } from '../../ui/toast';
import type { ToolHost } from './tools';
import type { Pt, Tool } from './view';

export class SkinPickerTool implements Tool {
  readonly id = 'skin';
  cursor = 'crosshair';
  private readonly root: HTMLElement;
  private readonly readout: HTMLElement;

  constructor(private readonly host: ToolHost) {
    this.root = el(`<div class="fl-tool-opts"><div class="fl-tool-title">${icon('eyeDropper', 14)} Skin Tone Selector</div><div class="fl-muted fl-wb-read">Click an evenly lit patch of skin. Shift-click to try another spot.</div><div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm fl-btn-cta" type="button" data-a="done">Done</button></div></div>`);
    this.readout = q(this.root, '.fl-wb-read');
    this.root.addEventListener('click', (e) => { if ((e.target as HTMLElement).closest('[data-a="done"]')) this.host.done(); });
  }

  activate(): void { this.host.drawer.replaceChildren(this.root); }

  down(p: Pt): boolean {
    const id = develop.id;
    if (id === null || p.u < 0 || p.u > 1 || p.v < 0 || p.v > 1) return true;
    const keep = p.e.shiftKey;
    if (!keep) this.host.done();
    void develop.flush().then(() => this.host.ctx.api.cmd<{ hue: number; saturation: number; skinLike: boolean }>('develop.skinPick', { id, x: p.nx, y: p.ny })).then((r) => {
      develop.set('skin.hue', r.hue, 'end', `Skin Hue ${r.hue}`);
      if (!develop.value('skin.hueUniformity') && !develop.value('skin.satUniformity') && !develop.value('skin.lumUniformity')) develop.set('skin.hueUniformity', 50, 'end', 'Hue Uniformity 50');
      const text = r.skinLike ? `Skin hue ${r.hue}. Raise the uniformity sliders to even it out.` : `Hue ${r.hue} does not look like skin; pick an evenly lit patch of skin, or keep it if that is the colour to even out.`;
      if (keep) setText(this.readout, text); else toast(text);
    }, (err) => this.host.ctx.fail(err, 'Skin Tone'));
    return true;
  }

  key(_e: KeyboardEvent, combo: string): boolean {
    if (combo === 'Escape') { this.host.done(); return true; }
    return false;
  }
}
