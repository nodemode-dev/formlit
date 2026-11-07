import doc from '../../../shared/controls.json';
import { clone } from '../../../demo/src/engine/settings';
import { develop } from '../../../demo/src/shims/develop';
import { promptName } from '../../../frontend/src/ui/dialogs';
import { el, escapeHtml, patchList, q, setClass, setHidden } from '../../../frontend/src/ui/dom';
import { icon } from '../../../frontend/src/ui/icons';
import { Panel } from '../../../frontend/src/ui/panel';
import { Slider, type SliderSpec } from '../../../frontend/src/ui/slider';
import { ICONS, NAMES, maskState as st } from './mask-state';
import type { Mask, Op } from './masks/types';

const SUPPORTED = new Set(['temp', 'tint', 'exposure', 'contrast', 'highlights', 'shadows', 'whites', 'blacks', 'texture', 'clarity', 'dehaze', 'saturation', 'sharpness', 'noise', 'amount']);
const LOCAL = (doc.local as SliderSpec[]).filter((s) => SUPPORTED.has(s.id));

interface Effect { name: string; adjust: Record<string, number>; builtin?: boolean }

const EFFECTS: Effect[] = [
  { name: 'Burn (Darken)', adjust: { exposure: -0.3 }, builtin: true },
  { name: 'Dodge (Lighten)', adjust: { exposure: 0.25 }, builtin: true },
  { name: 'Soften Skin', adjust: { clarity: -100, texture: -60, sharpness: 25 }, builtin: true },
  { name: 'Clarity', adjust: { clarity: 50 }, builtin: true },
  { name: 'Sharpness', adjust: { sharpness: 50 }, builtin: true },
  { name: 'Haze Removal', adjust: { dehaze: 40 }, builtin: true },
  { name: 'Darken Sky', adjust: { exposure: -0.4, highlights: -40, saturation: 15 }, builtin: true },
  { name: 'Brighten Subject', adjust: { exposure: 0.3, shadows: 20, texture: 10 }, builtin: true },
];

const KEY = 'formlit-demo-develop-effects';

function readMine(): Effect[] {
  try { return JSON.parse(localStorage.getItem(KEY) ?? '[]') as Effect[]; } catch { return []; }
}

function writeMine(list: Effect[]): void {
  try { localStorage.setItem(KEY, JSON.stringify(list)); } catch { /* storage blocked */ }
}

interface Ctl { key: string; label: string; min: number; max: number; scale: number }

const CONTROLS: Record<string, Ctl[]> = {
  luminanceRange: [{ key: 'lo', label: 'Low', min: 0, max: 100, scale: 100 }, { key: 'hi', label: 'High', min: 0, max: 100, scale: 100 }, { key: 'loFeather', label: 'Low Feather', min: 0, max: 100, scale: 100 }, { key: 'hiFeather', label: 'High Feather', min: 0, max: 100, scale: 100 }],
  colorRange: [{ key: 'refine', label: 'Refine', min: 0, max: 100, scale: 1 }],
  radial: [{ key: 'feather', label: 'Feather', min: 0, max: 100, scale: 1 }],
  edge: [{ key: 'refine', label: 'Refine Edge', min: 0, max: 100, scale: 1 }, { key: 'shift', label: 'Shift Edge', min: -100, max: 100, scale: 1 }, { key: 'feather', label: 'Feather', min: 0, max: 100, scale: 1 }],
};

const HINTS: Record<string, string> = {
  linear: 'Drag the pins on the photo to move the gradient.',
  radial: 'Drag the centre, or a side pin to resize the ellipse.',
  brush: 'Paint on the photo. Hold Alt to erase.',
  colorRange: 'Click the photo to pick a colour. Shift-click adds more.',
  luminanceRange: 'Select by brightness; the red overlay shows the result.',
  sky: 'Edge controls snap the mask to the photo.',
  subject: 'Edge controls snap the mask to the photo.',
  background: 'Edge controls snap the mask to the photo.',
};

const edgeKind = (k: string): string => (k === 'sky' || k === 'subject' || k === 'background' ? 'edge' : k);

export class MaskPanel {
  readonly panel: Panel;
  private readonly root: HTMLElement;
  private readonly list: HTMLElement;
  private readonly grid: HTMLElement;
  private readonly hint: HTMLElement;
  private readonly comp: HTMLElement;
  private readonly brush: HTMLElement;
  private readonly adjust: HTMLElement;
  private readonly effect: HTMLSelectElement;
  private readonly sliders = new Map<string, Slider>();
  private shapeKey = '';
  private shapeInputs = new Map<string, HTMLInputElement>();
  private effects: Effect[] = [...EFFECTS, ...readMine()];

  constructor(host: HTMLElement, before: Element | null) {
    this.panel = new Panel('dev.masking', 'Masking', { open: true });
    const btn = (k: string): string => `<button class="fl-mask-new" type="button" data-new="${k}" title="${NAMES[k]}">${icon(ICONS[k], 16)}<span>${NAMES[k]}</span></button>`;
    this.root = el(`<div class="fl-tool-opts fl-masks">
<div class="fl-tool-title">${icon('masking', 14)} Masks<span class="fl-grow"></span><label class="fl-check fl-check-sm"><input type="checkbox" data-overlay> Show Overlay</label></div>
<div class="fl-mask-list"></div>
<div class="fl-sub">Create New Mask</div>
<div class="fl-mask-grid">${['subject', 'sky', 'background', 'linear', 'radial', 'brush', 'colorRange', 'luminanceRange'].map(btn).join('')}</div>
<div class="fl-mask-hint fl-muted"></div>
<div class="fl-mask-comp"></div>
<div class="fl-mask-brush" hidden></div>
<div class="fl-mask-adjust" hidden><div class="fl-sub">Adjustments</div><div class="fl-row"><span class="fl-row-label">Effect</span><select class="cv-select fl-grow" data-effect aria-label="Effect preset"></select></div></div>
<div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm" type="button" data-a="invert">Invert</button><button class="cv-btn fl-btn-sm" type="button" data-a="dup">Duplicate</button><button class="cv-btn fl-btn-sm" type="button" data-a="delete">Delete</button></div>
</div>`);
    this.list = q(this.root, '.fl-mask-list');
    this.grid = q(this.root, '.fl-mask-grid');
    this.hint = q(this.root, '.fl-mask-hint');
    this.comp = q(this.root, '.fl-mask-comp');
    this.brush = q(this.root, '.fl-mask-brush');
    this.adjust = q(this.root, '.fl-mask-adjust');
    this.effect = q<HTMLSelectElement>(this.root, '[data-effect]');
    for (const spec of LOCAL) {
      const s = new Slider(spec, { input: (id, v, phase) => this.setAdjust(id, v, phase), reset: (id) => this.setAdjust(id, id === 'amount' ? 100 : 0, 'end') });
      this.sliders.set(spec.id, s);
      this.adjust.appendChild(s.root);
    }
    this.buildBrush();
    this.fillEffects();
    this.panel.body.appendChild(this.root);
    if (before) host.insertBefore(this.panel.root, before); else host.appendChild(this.panel.root);
    this.root.addEventListener('click', (e) => this.click(e));
    this.effect.addEventListener('change', () => { const v = this.effect.value; this.effect.value = ''; void this.pickEffect(v); });
    q<HTMLInputElement>(this.root, '[data-overlay]').addEventListener('change', (e) => { st.showOverlay = (e.target as HTMLInputElement).checked; st.changed(); });
    this.panel.onOpen = (open) => { st.active = open; if (!open) { st.pending = ''; st.pick = false; } st.changed(); this.sync(); };
    st.active = this.panel.root.querySelector('.fl-panel-head')?.getAttribute('aria-expanded') !== 'false';
    develop.listen((why) => { if (why !== 'drag') this.sync(); });
    st.listen(() => this.sync());
    this.sync();
  }

  private buildBrush(): void {
    const mk = (label: string, min: number, max: number, val: number, fn: (v: number) => void): HTMLElement => {
      const s = new Slider({ id: label, label, min, max, default: val, step: 1, decimals: 0 }, { input: (_id, v) => { fn(v); st.changed(); } });
      s.set(val);
      return s.root;
    };
    this.brush.append(el('<div class="fl-sub">Brush</div>'),
      mk('Size', 2, 300, st.brush.size, (v) => { st.brush.size = v; }),
      mk('Feather', 0, 100, st.brush.feather, (v) => { st.brush.feather = v; }),
      mk('Flow', 1, 100, st.brush.flow, (v) => { st.brush.flow = v; }),
      mk('Density', 1, 100, st.brush.density, (v) => { st.brush.density = v; }),
      el('<div class="fl-row"><label class="fl-check fl-check-sm"><input type="checkbox" data-erase> Erase (Alt)</label></div>'));
    q<HTMLInputElement>(this.brush, '[data-erase]').addEventListener('change', (e) => { st.brush.erase = (e.target as HTMLInputElement).checked; });
  }

  private fillEffects(): void {
    const mine = this.effects.filter((e) => !e.builtin);
    const html = ['<option value="">Custom</option>', ...this.effects.map((e, i) => `<option value="${i}">${escapeHtml(e.name)}</option>`), '<option value="#save">Save Current Settings as New Preset...</option>', ...mine.map((e) => `<option value="#del:${escapeHtml(e.name)}">Delete Preset "${escapeHtml(e.name)}"</option>`)].join('');
    if (this.effect.dataset.key !== html) { this.effect.dataset.key = html; this.effect.innerHTML = html; }
  }

  private async pickEffect(v: string): Promise<void> {
    const { masks, m } = st.current();
    const mine = this.effects.filter((e) => !e.builtin);
    if (v === '#save') {
      if (!m) return;
      const name = (await promptName('New Mask Effect Preset', 'My Effect', 'Create'))?.trim();
      if (!name) return;
      const adjust = Object.fromEntries(Object.entries(m.adjust ?? {}).filter(([k]) => k !== 'amount'));
      this.effects = [...EFFECTS, ...mine.filter((e) => e.name !== name), { name, adjust }];
      writeMine(this.effects.filter((e) => !e.builtin));
      this.fillEffects();
      return;
    }
    if (v.startsWith('#del:')) {
      this.effects = [...EFFECTS, ...mine.filter((e) => e.name !== v.slice(5))];
      writeMine(this.effects.filter((e) => !e.builtin));
      this.fillEffects();
      return;
    }
    const preset = this.effects[Number(v)];
    if (!m || !preset || v === '') return;
    m.adjust = { ...(m.adjust.amount !== undefined ? { amount: m.adjust.amount } : {}), ...clone(preset.adjust) };
    st.write(masks, 'end', `Mask Effect: ${preset.name}`);
  }

  private setAdjust(id: string, v: number, phase: 'drag' | 'end'): void {
    const { masks, m } = st.current();
    if (!m) return;
    m.adjust = { ...(m.adjust ?? {}), [id]: v };
    if (v === 0 && id !== 'amount') delete m.adjust[id];
    st.write(masks, phase, `Mask ${LOCAL.find((s) => s.id === id)?.label ?? id}`);
  }

  private click(e: Event): void {
    const t = e.target as HTMLElement;
    const nw = t.closest<HTMLElement>('[data-new]')?.dataset.new;
    if (nw) { this.create(nw, 'new'); return; }
    const add = t.closest<HTMLElement>('[data-addop]');
    if (add) { this.create(add.dataset.kind as string, 'add'); return; }
    const row = t.closest<HTMLElement>('[data-mask]');
    if (row) {
      const i = Number(row.dataset.mask);
      if (t.closest('[data-eye]')) {
        const masks = st.masks();
        masks[i].visible = masks[i].visible === false;
        st.write(masks, 'end', 'Mask Visibility');
        return;
      }
      st.sel = i;
      st.comp = Number(t.closest<HTMLElement>('[data-comp]')?.dataset.comp ?? 0);
      st.pending = '';
      st.pick = false;
      st.changed();
      return;
    }
    const op = t.closest<HTMLElement>('[data-compop]');
    const { masks, m } = st.current();
    if (op && m) {
      const c = m.components[st.comp];
      if (c) { c.op = op.dataset.compop as Op; st.write(masks, 'end', 'Mask Mode'); }
      return;
    }
    if (t.closest('[data-pickcolor]')) { st.pick = !st.pick; st.changed(); return; }
    const a = t.closest<HTMLElement>('[data-a]')?.dataset.a;
    if (!a || !m) return;
    if (a === 'invert') { m.invert = !m.invert; st.write(masks, 'end', 'Invert Mask'); }
    if (a === 'delete') { masks.splice(st.sel, 1); st.sel = Math.min(st.sel, masks.length - 1); st.comp = 0; st.write(masks, 'end', 'Delete Mask'); }
    if (a === 'dup') { const copy = clone(m); copy.id = st.nextId(masks); copy.name = `${m.name} Copy`; masks.push(copy); st.sel = masks.length - 1; st.write(masks, 'end', 'Duplicate Mask'); }
  }

  private create(kind: string, op: 'new' | Op): void {
    if (kind === 'linear' || kind === 'radial') {
      if (op === 'new') { st.pending = kind; st.pick = false; st.changed(); return; }
      st.create(kind, op);
      return;
    }
    st.create(kind, op);
  }

  private shapeControls(kind: string): void {
    const k = edgeKind(kind);
    const key = `${kind}`;
    if (this.shapeKey === key) return;
    this.shapeKey = key;
    this.shapeInputs = new Map();
    const box = el('<div></div>');
    for (const c of CONTROLS[k] ?? []) {
      const row = el(`<label class="fl-opt"><span>${c.label}</span><input class="cv-slider" type="range" min="${c.min}" max="${c.max}" step="1" value="0" data-shape="${c.key}"></label>`);
      const inp = q<HTMLInputElement>(row, 'input');
      const write = (phase: 'drag' | 'end'): void => {
        const { masks, c: comp } = st.current();
        if (!comp) return;
        comp.shape[c.key] = Number(inp.value) / c.scale;
        st.write(masks, phase, 'Mask Range');
      };
      inp.addEventListener('input', () => write('drag'));
      inp.addEventListener('change', () => write('end'));
      this.shapeInputs.set(c.key, inp);
      box.appendChild(row);
    }
    if (kind === 'colorRange') {
      const b = el<HTMLButtonElement>(`<button class="cv-btn fl-btn-sm" type="button" data-pickcolor>${icon('eyeDropper', 13)} Pick Color</button>`);
      box.appendChild(b);
    }
    this.comp.querySelector('[data-controls]')?.replaceChildren(...Array.from(box.children));
  }

  sync(): void {
    const masks = st.masks();
    if (st.sel >= masks.length) st.sel = masks.length - 1;
    if (st.sel < 0 && masks.length) st.sel = 0;
    const items = masks.map((m, i) => ({ m, i }));
    const comps = (x: { m: Mask; i: number }): string => x.m.components.map((c, k) => `<button class="fl-mask-comp-row${x.i === st.sel && k === st.comp ? ' is-on' : ''}" type="button" data-mask="${x.i}" data-comp="${k}">${icon(ICONS[c.shape.kind] ?? 'masking', 12)}<span>${c.op === 'add' ? '' : c.op === 'subtract' ? 'Subtract: ' : 'Intersect: '}${escapeHtml(NAMES[c.shape.kind] ?? c.shape.kind)}</span></button>`).join('');
    const update = (node: HTMLElement, x: { m: Mask; i: number }): void => {
      const html = `<div class="fl-mask-head${x.i === st.sel ? ' is-on' : ''}" data-mask="${x.i}"><button class="cv-icon-btn" type="button" data-eye aria-label="Show or hide">${icon(x.m.visible === false ? 'eyeOff' : 'eye', 13)}</button><span class="fl-grow">${escapeHtml(x.m.name)}${x.m.invert ? ' (inverted)' : ''}</span></div>${x.i === st.sel ? comps(x) : ''}`;
      if (node.dataset.html !== html) { node.dataset.html = html; node.innerHTML = html; }
    };
    patchList(this.list, items, { key: (x) => String(x.m.id), create: (x) => { const n = el('<div class="fl-mask-row"></div>'); update(n, x); return n; }, update });
    const m = masks[st.sel];
    const c = m?.components[st.comp];
    setClass(this.root, 'has-mask', !!m);
    const have = !!develop.item;
    for (const k of ['subject', 'sky', 'background']) {
      const b = q<HTMLButtonElement>(this.grid, `[data-new="${k}"]`);
      const ok = have && !!st.bitmapKey(k);
      b.disabled = !ok;
      b.title = ok ? NAMES[k] : `${NAMES[k]}: available on the demo photos that carry a prepared selection`;
    }
    for (const k of ['linear', 'radial']) setClass(q(this.grid, `[data-new="${k}"]`), 'is-on', st.pending === k);
    const hintText = st.pending ? `Drag on the photo to place the ${st.pending === 'linear' ? 'linear gradient' : 'radial gradient'}.` : st.pick ? HINTS.colorRange : c ? HINTS[c.shape.kind] ?? '' : 'Choose a mask type, or select a mask below.';
    if (this.hint.textContent !== hintText) this.hint.textContent = hintText;
    setHidden(this.adjust, !m);
    setHidden(this.brush, c?.shape.kind !== 'brush');
    if (m) for (const [id, s] of this.sliders) s.set(Number(m.adjust?.[id] ?? (id === 'amount' ? 100 : 0)));
    this.syncComp(m, c);
  }

  private syncComp(m: Mask | undefined, c: Mask['components'][number] | undefined): void {
    if (!m || !c) {
      if (this.comp.dataset.html) { this.comp.dataset.html = ''; this.comp.textContent = ''; this.shapeKey = ''; }
      return;
    }
    const ops: Op[] = ['add', 'subtract', 'intersect'];
    const shell = `${m.id}`;
    if (this.comp.dataset.html !== shell) {
      this.comp.dataset.html = shell;
      this.shapeKey = '';
      this.comp.innerHTML = `<div class="fl-sub">Component</div><div class="fl-row"><div class="cv-seg fl-seg-sm fl-grow">${ops.map((o) => `<button type="button" data-compop="${o}">${o.charAt(0).toUpperCase() + o.slice(1)}</button>`).join('')}</div></div><div class="fl-row fl-mask-addrow"><span class="fl-row-label">Add</span>${['brush', 'linear', 'radial', 'colorRange', 'luminanceRange', 'sky', 'subject'].map((k) => `<button class="cv-icon-btn" type="button" data-addop="add" data-kind="${k}" title="Add ${NAMES[k]}">${icon(ICONS[k], 14)}</button>`).join('')}</div><div data-controls></div>`;
    }
    for (const b of Array.from(this.comp.querySelectorAll<HTMLElement>('[data-compop]'))) setClass(b, 'is-on', b.dataset.compop === c.op);
    for (const k of ['sky', 'subject']) {
      const b = this.comp.querySelector<HTMLButtonElement>(`[data-addop][data-kind="${k}"]`);
      if (b) b.disabled = !st.bitmapKey(k);
    }
    this.shapeControls(c.shape.kind);
    for (const [key, inp] of this.shapeInputs) {
      const ctl = (CONTROLS[edgeKind(c.shape.kind)] ?? []).find((x) => x.key === key);
      if (!ctl) continue;
      const raw = Number(c.shape[key] ?? (key === 'refine' ? (c.shape.kind === 'colorRange' ? 50 : 0) : key === 'feather' && c.shape.kind === 'radial' ? 50 : key === 'hi' ? 1 : key === 'lo' ? 0.5 : 0.1));
      const val = String(Math.round(raw * ctl.scale));
      if (inp.value !== val && document.activeElement !== inp) inp.value = val;
    }
    const pick = this.comp.querySelector<HTMLElement>('[data-pickcolor]');
    if (pick) setClass(pick, 'is-on', st.pick);
  }
}
