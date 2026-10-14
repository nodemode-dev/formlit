import type { Ctx } from '../../app';
import { clone, develop, type Layer } from '../../state/develop';
import { promptName } from '../../ui/dialogs';
import { el, escapeHtml, patchList, q, setClass, setHidden, setText, setValue } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { Panel } from '../../ui/panel';
import { toast } from '../../ui/toast';

const AI: Array<[string, string]> = [['subject', 'Subject'], ['sky', 'Sky'], ['background', 'Background'], ['people', 'People']];
const MAX = 8;

export class LayersPanel {
  readonly panel = new Panel('dev.layers', 'Layers');
  private readonly banner: HTMLElement;
  private readonly bannerText: HTMLElement;
  private readonly list: HTMLElement;
  private readonly opts: HTMLElement;
  private readonly opacity: HTMLInputElement;
  private readonly opacityVal: HTMLElement;
  private readonly maskSel: HTMLSelectElement;
  private readonly invert: HTMLInputElement;
  private readonly add: HTMLButtonElement;

  constructor(private readonly ctx: Ctx) {
    this.panel.root.classList.add('fl-layers');
    const body = el(`<div class="fl-layers-body">
<div class="fl-layer-banner" hidden><span class="fl-layer-banner-text"></span><button class="cv-btn fl-btn-sm" type="button" data-l="photo">Back to Photo</button></div>
<div class="fl-layer-list" role="listbox" aria-label="Layers"><button class="fl-layer-row fl-layer-photo" type="button" data-row="photo">${icon('layers', 13)}<span class="fl-grow">Photo</span><span class="fl-muted">base settings</span></button></div>
<div class="fl-layer-opts" hidden>
<label class="fl-opt"><span>Opacity</span><input class="cv-slider" type="range" min="0" max="100" step="1" data-l="opacity"><b class="fl-layer-opval"></b></label>
<div class="fl-row"><span class="fl-row-label">Mask</span><select class="cv-select fl-grow" data-l="mask" aria-label="Layer mask"></select></div>
<label class="fl-check fl-check-sm"><input type="checkbox" data-l="invert"> Invert mask</label>
<div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm" type="button" data-l="rename">Rename</button><button class="cv-btn fl-btn-sm" type="button" data-l="dup">Duplicate</button><button class="cv-btn fl-btn-sm" type="button" data-l="delete">Delete</button></div>
</div>
<div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm" type="button" data-l="add">${icon('add', 12)} New Layer</button></div>
<div class="fl-muted fl-layer-note">A layer is its own copy of the colour and tone settings, blended in through a mask. Select it and the sliders change the layer only; white balance, crop, lens and noise reduction stay with the photo.</div>
</div>`);
    this.panel.body.appendChild(body);
    this.banner = q(body, '.fl-layer-banner');
    this.bannerText = q(body, '.fl-layer-banner-text');
    this.list = q(body, '.fl-layer-list');
    this.opts = q(body, '.fl-layer-opts');
    this.opacity = q<HTMLInputElement>(body, '[data-l="opacity"]');
    this.opacityVal = q(body, '.fl-layer-opval');
    this.maskSel = q<HTMLSelectElement>(body, '[data-l="mask"]');
    this.invert = q<HTMLInputElement>(body, '[data-l="invert"]');
    this.add = q<HTMLButtonElement>(body, '[data-l="add"]');
    body.addEventListener('click', (e) => this.click(e));
    this.opacity.addEventListener('input', () => this.setOpacity('drag'));
    this.opacity.addEventListener('change', () => this.setOpacity('end'));
    this.maskSel.addEventListener('change', () => void this.setMask(this.maskSel.value));
    this.invert.addEventListener('change', () => this.edit((l) => { l.mask = { ...(l.mask ?? {}), invert: this.invert.checked }; }, this.invert.checked ? 'Invert Layer Mask' : 'Layer Mask'));
    develop.listen(() => this.sync());
    this.sync();
  }

  private current(): Layer | undefined { return develop.layer === null ? undefined : develop.layers()[develop.layer]; }

  private edit(fn: (l: Layer) => void, label: string, phase: 'drag' | 'end' = 'end'): void {
    const i = develop.layer;
    if (i === null) return;
    const layers = clone(develop.layers());
    if (!layers[i]) return;
    fn(layers[i]);
    develop.patch('layers', layers, phase, `${layers[i].name}: ${label}`);
  }

  private setOpacity(phase: 'drag' | 'end'): void {
    const v = Number(this.opacity.value);
    setText(this.opacityVal, `${v}%`);
    this.edit((l) => { l.opacity = v; }, `Opacity ${v}%`, phase);
  }

  private async setMask(value: string): Promise<void> {
    const i = develop.layer;
    if (i === null || develop.id === null) return;
    if (value.startsWith('mask:')) {
      const m = ((develop.settings.masks as Array<{ id: number; name: string; components: unknown[]; invert?: boolean }> | undefined) ?? []).find((x) => String(x.id) === value.slice(5));
      if (!m) return;
      this.edit((l) => { l.mask = { components: clone(m.components), invert: !!m.invert, source: value }; }, `Mask from ${m.name}`);
      return;
    }
    if (value === 'photo') { this.edit((l) => { l.mask = { components: [], invert: false, source: 'photo' }; }, 'Whole Photo'); return; }
    const done = this.ctx.shell.busy(`Finding ${value} for the layer`);
    try {
      await develop.flush();
      const layer = this.current();
      await this.ctx.api.cmd('develop.setLayer', { id: develop.id, layer: layer?.id ?? i, mask: value, invert: this.invert.checked });
      await develop.reload('layer');
    } catch (err) { this.ctx.fail(err, 'Layer Mask'); } finally { done(); }
  }

  private async newLayer(copyOf?: Layer): Promise<void> {
    if (develop.id === null) return;
    if (develop.layers().length >= MAX) { toast(`A photo holds up to ${MAX} layers`); return; }
    try {
      await develop.flush();
      if (copyOf) {
        const layers = clone(develop.layers());
        const id = layers.reduce((a, l) => Math.max(a, l.id), 0) + 1;
        layers.push({ ...clone(copyOf), id, name: `${copyOf.name} Copy` });
        develop.patch('layers', layers, 'end', `Duplicate Layer ${copyOf.name}`);
        await develop.flush();
        develop.selectLayer(layers.length - 1);
        return;
      }
      await this.ctx.api.cmd('develop.addLayer', { id: develop.id, mask: 'photo' });
      await develop.reload('layer');
      develop.selectLayer(develop.layers().length - 1);
    } catch (err) { this.ctx.fail(err, 'New Layer'); }
  }

  private click(e: MouseEvent): void {
    const t = e.target as HTMLElement;
    const row = t.closest<HTMLElement>('[data-row]');
    if (row) {
      if (row.dataset.row === 'photo') { develop.selectLayer(null); return; }
      const i = Number(row.dataset.row);
      if (t.closest('[data-eye]')) {
        const layers = clone(develop.layers());
        if (layers[i]) { layers[i].visible = layers[i].visible === false; develop.patch('layers', layers, 'end', `${layers[i].visible ? 'Show' : 'Hide'} ${layers[i].name}`); }
        return;
      }
      develop.selectLayer(i);
      return;
    }
    const a = t.closest<HTMLElement>('[data-l]')?.dataset.l;
    if (a === 'photo') develop.selectLayer(null);
    if (a === 'add') void this.newLayer();
    const l = this.current();
    if (!l) return;
    if (a === 'dup') void this.newLayer(l);
    if (a === 'delete') {
      const i = develop.layer as number;
      const layers = clone(develop.layers());
      layers.splice(i, 1);
      develop.selectLayer(null);
      develop.patch('layers', layers, 'end', `Delete Layer ${l.name}`);
    }
    if (a === 'rename') {
      void promptName('Rename Layer', l.name, 'Rename').then((name) => { if (name) this.edit((x) => { x.name = name; }, 'Rename'); });
    }
  }

  private sync(): void {
    const layers = develop.layers();
    const sel = develop.layer;
    const items = layers.map((l, i) => ({ l, i }));
    const fill = (node: HTMLElement, x: { l: Layer; i: number }) => {
      const html = `<span class="cv-icon-btn" data-eye role="button" aria-label="Show or hide">${icon(x.l.visible === false ? 'eyeOff' : 'eye', 13)}</span><span class="fl-grow fl-layer-name">${escapeHtml(x.l.name)}</span><span class="fl-muted">${Math.round(Number(x.l.opacity ?? 100))}%</span>`;
      if (node.dataset.html !== html) { node.dataset.html = html; node.innerHTML = html; }
      node.dataset.row = String(x.i);
      setClass(node, 'is-on', x.i === sel);
      setClass(node, 'is-hidden', x.l.visible === false);
    };
    const photo = q(this.list, '.fl-layer-photo');
    setClass(photo, 'is-on', sel === null);
    const rows = el('<div></div>');
    const holder = this.list.querySelector<HTMLElement>('.fl-layer-rows') ?? (() => { rows.className = 'fl-layer-rows'; this.list.appendChild(rows); return rows; })();
    patchList(holder, items, {
      key: (x) => String(x.l.id),
      create: (x) => { const n = el('<button class="fl-layer-row" type="button"></button>'); fill(n, x); return n; },
      update: fill,
    });
    const l = this.current();
    setHidden(this.opts, !l);
    setHidden(this.banner, !l);
    setClass(this.ctx.shell.app, 'is-layer-editing', !!l);
    this.add.disabled = layers.length >= MAX;
    if (!l) return;
    setText(this.bannerText, `Editing ${l.name}: the sliders change this layer only`);
    const op = Math.round(Number(l.opacity ?? 100));
    if (document.activeElement !== this.opacity) setValue(this.opacity, String(op));
    setText(this.opacityVal, `${op}%`);
    const masks = (develop.settings.masks as Array<{ id: number; name: string }> | undefined) ?? [];
    const options: Array<[string, string]> = [['photo', 'Whole photo'], ...AI, ...masks.map((m): [string, string] => [`mask:${m.id}`, `Mask: ${m.name}`])];
    const key = options.map((o) => o.join('=')).join('|');
    if (this.maskSel.dataset.key !== key) {
      this.maskSel.dataset.key = key;
      this.maskSel.innerHTML = options.map(([v, label]) => `<option value="${escapeHtml(v)}">${escapeHtml(label)}</option>`).join('');
    }
    const src = l.mask?.source ?? ((l.mask?.components?.length ?? 0) ? '' : 'photo');
    setValue(this.maskSel, src || 'photo');
    this.invert.checked = !!l.mask?.invert;
  }
}
