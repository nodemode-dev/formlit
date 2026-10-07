import type { Ctx } from '../../app';
import { el, q, setClass, setHidden } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { toast } from '../../ui/toast';

type Kind = 'keywords' | 'label' | 'flag' | 'rating' | 'rotate' | 'preset' | 'collection';

const VALUES: Record<Exclude<Kind, 'keywords' | 'preset'>, Array<[string, string]>> = {
  label: [['red', 'Red'], ['yellow', 'Yellow'], ['green', 'Green'], ['blue', 'Blue'], ['purple', 'Purple'], ['none', 'None']],
  flag: [['pick', 'Picked'], ['reject', 'Rejected'], ['none', 'Unflagged']],
  rating: [['5', '5 stars'], ['4', '4 stars'], ['3', '3 stars'], ['2', '2 stars'], ['1', '1 star'], ['0', 'No rating']],
  rotate: [['1', 'Rotate Right'], ['-1', 'Rotate Left']],
  collection: [['target', 'Target Collection']],
};

export class Painter {
  readonly root = el(`<span class="fl-painter"><button class="cv-icon-btn" type="button" data-cmd="library.painter" aria-label="Painter">${icon('paintbrush', 16)}</button><span class="fl-painter-opts" hidden><select class="cv-select" data-p="kind" aria-label="Paint"><option value="keywords">Keywords</option><option value="label">Label</option><option value="flag">Flag</option><option value="rating">Rating</option><option value="rotate">Rotation</option><option value="preset">Develop Preset</option><option value="collection">Target Collection</option></select><input class="cv-input" data-p="text" type="text" spellcheck="false" placeholder="keyword, another"><select class="cv-select" data-p="value" aria-label="Value" hidden></select></span></span>`);
  active = false;
  private readonly kind = q<HTMLSelectElement>(this.root, '[data-p="kind"]');
  private readonly text = q<HTMLInputElement>(this.root, '[data-p="text"]');
  private readonly value = q<HTMLSelectElement>(this.root, '[data-p="value"]');
  private presets: Array<[string, string]> = [];

  constructor(private readonly ctx: Ctx) {
    this.kind.addEventListener('change', () => this.sync());
    ctx.commands.add({ id: 'library.painter', label: 'Painter', keys: ['Alt+Mod+K'], run: () => this.toggle(), checked: () => this.active });
  }

  toggle(): void {
    this.active = !this.active;
    setHidden(q(this.root, '.fl-painter-opts'), !this.active);
    setClass(this.root, 'is-on', this.active);
    if (this.active && !this.presets.length) {
      void this.ctx.api.cmd<{ presets: Array<{ id: string; name: string; group: string }> }>('preset.list').then((r) => { this.presets = r.presets.map((p) => [p.id, `${p.group}: ${p.name}`]); this.sync(); }, () => undefined);
    }
    document.body.classList.toggle('is-painting', this.active);
    if (this.active) toast('Painter: click photos to apply. Press the brush again to stop.');
    this.sync();
  }

  private sync(): void {
    const k = this.kind.value as Kind;
    setHidden(this.text, k !== 'keywords');
    setHidden(this.value, k === 'keywords');
    const opts = k === 'preset' ? this.presets : k === 'keywords' ? [] : VALUES[k];
    const key = `${k}|${opts.length}`;
    if (this.value.dataset.key !== key) {
      this.value.dataset.key = key;
      this.value.innerHTML = opts.map(([v, l]) => `<option value="${v}">${l}</option>`).join('');
    }
  }

  paint(id: number): boolean {
    if (!this.active) return false;
    const k = this.kind.value as Kind;
    const v = this.value.value;
    const ids = [id];
    const run = (cmd: string, params: Record<string, unknown>) => void this.ctx.api.cmd(cmd, { ids, ...params }).catch((e) => this.ctx.fail(e));
    if (k === 'keywords') {
      const kws = this.text.value.split(',').map((s) => s.trim()).filter(Boolean);
      if (!kws.length) { toast('Type the keywords to paint first'); return true; }
      run('photo.addKeywords', { keywords: kws });
    } else if (k === 'label') run('photo.label', { label: v });
    else if (k === 'flag') run('photo.flag', { flag: v });
    else if (k === 'rating') run('photo.rate', { rating: Number(v) });
    else if (k === 'rotate') run('photo.rotate', { turns: Number(v) });
    else if (k === 'preset' && v) run('preset.apply', { preset: v });
    else if (k === 'collection') void this.ctx.api.cmd('collection.addPhotos', { ids }).catch((e) => this.ctx.fail(e));
    return true;
  }
}
