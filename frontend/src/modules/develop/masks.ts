import { clone, develop } from '../../state/develop';
import { promptName } from '../../ui/dialogs';
import { el, escapeHtml, patchList, q, setClass, setHidden, setText } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { Slider } from '../../ui/slider';
import { CurveEditor } from './curve';
import type { ToolHost } from './tools';
import type { DevelopView, Pt, Tool } from './view';

type Vec = [number, number];
interface Shape { kind: string; [k: string]: unknown }
type Op = 'add' | 'subtract' | 'intersect' | 'refine';
interface Component { shape: Shape; op: Op; invert?: boolean }
const BITMAP_KINDS = new Set(['subject', 'sky', 'background', 'object', 'people', 'landscape']);
interface LocalPoint { hue: number; chroma: number; lum: number; hueShift: number; satShift: number; lumShift: number; variance: number; range: number }
interface Mask { id: number; name: string; visible?: boolean; components: Component[]; adjust: Record<string, unknown>; invert?: boolean; refine?: number }
interface EffectPreset { name: string; adjust: Record<string, unknown>; builtin?: boolean }

const EFFECT_PRESETS: EffectPreset[] = [
  { name: 'Burn (Darken)', adjust: { exposure: -0.3 }, builtin: true },
  { name: 'Dodge (Lighten)', adjust: { exposure: 0.25 }, builtin: true },
  { name: 'Iris Enhance', adjust: { exposure: 0.35, clarity: 40, saturation: 40 }, builtin: true },
  { name: 'Soften Skin', adjust: { clarity: -100, texture: -60, sharpness: 25 }, builtin: true },
  { name: 'Teeth Whitening', adjust: { exposure: 0.4, saturation: -60 }, builtin: true },
  { name: 'Clarity', adjust: { clarity: 50 }, builtin: true },
  { name: 'Sharpness', adjust: { sharpness: 50 }, builtin: true },
  { name: 'Haze Removal', adjust: { dehaze: 40 }, builtin: true },
  { name: 'Darken Sky', adjust: { exposure: -0.4, highlights: -40, saturation: 15 }, builtin: true },
  { name: 'Brighten Subject', adjust: { exposure: 0.3, shadows: 20, texture: 10 }, builtin: true },
];
const POINT_KEYS: Array<[keyof LocalPoint, string, number, number]> = [['hueShift', 'Hue Shift', -100, 100], ['satShift', 'Sat Shift', -100, 100], ['lumShift', 'Lum Shift', -100, 100], ['range', 'Range', 0, 100]];

const AI_KINDS: Array<[string, string, string]> = [['subject', 'Subject', 'maskSubject'], ['sky', 'Sky', 'maskSky'], ['background', 'Background', 'maskBackground'], ['people', 'People', 'maskPeople'], ['object', 'Objects', 'maskObject']];
const MANUAL: Array<[string, string, string]> = [['brush', 'Brush', 'maskBrush'], ['linear', 'Linear Gradient', 'maskLinear'], ['radial', 'Radial Gradient', 'maskRadial']];
const RANGES: Array<[string, string, string]> = [['colorRange', 'Color Range', 'maskColor'], ['luminanceRange', 'Luminance Range', 'maskLuminance'], ['depthRange', 'Depth Range', 'maskDepth'], ['edgeRange', 'Edge Range', 'maskLuminance']];
const PART_GROUPS: Array<[string, string, string]> = [['people-parts', 'People Parts', 'maskPeople'], ['landscape', 'Landscape', 'maskSky']];
const PARTS: Record<string, Array<[string, string]>> = {
  people: [['faceSkin', 'Face Skin'], ['bodySkin', 'Body Skin'], ['eyebrows', 'Eyebrows'], ['sclera', 'Eye Sclera'], ['iris', 'Iris and Pupil'], ['lips', 'Lips'], ['teeth', 'Teeth'], ['hair', 'Hair'], ['clothes', 'Clothes']],
  landscape: [['sky', 'Sky'], ['water', 'Water'], ['vegetation', 'Vegetation'], ['mountains', 'Mountains'], ['architecture', 'Architecture'], ['naturalGround', 'Natural Ground'], ['artificialGround', 'Artificial Ground']],
};
const NAMES: Record<string, string> = { ...Object.fromEntries([...AI_KINDS, ...MANUAL, ...RANGES].map(([k, l]) => [k, l])), landscape: 'Landscape' };

export class MaskTool implements Tool {
  readonly id = 'masks';
  cursor = 'crosshair';
  private sel = -1;
  private comp = 0;
  private ghost: Mask[] | null = null;
  private showOverlay = true;
  private drag: { kind: string; start: Pt; orig: Shape; handle: string; strokeIndex?: number } | null = null;
  private brush = { size: 0.03, feather: 60, flow: 80, density: 100, auto: false, snap: false, erase: false };
  private hoverPt: Pt | null = null;
  private pendingKind = '';
  private readonly root: HTMLElement;
  private readonly list: HTMLElement;
  private readonly adjust: HTMLElement;
  private readonly sliders = new Map<string, Slider>();
  private readonly compOpts: HTMLElement;
  private readonly brushOpts: HTMLElement;
  private seq = 0;
  private readonly points: HTMLElement;
  private readonly pointSliders = new Map<string, Slider>();
  private readonly effect: HTMLSelectElement;
  private readonly curveBox: HTMLElement;
  private readonly curve: CurveEditor;
  private effects: EffectPreset[] = EFFECT_PRESETS;
  private pointIdx = 0;
  private pickPoint = false;

  private localPoints(m: Mask | undefined): LocalPoint[] { return ((m?.adjust?.pointColors as LocalPoint[] | undefined) ?? []).slice(); }

  private setPoint(k: keyof LocalPoint, v: number, phase: 'drag' | 'end'): void {
    const { masks, m } = this.current();
    const pts = this.localPoints(m);
    if (!m || !pts[this.pointIdx]) return;
    pts[this.pointIdx] = { ...pts[this.pointIdx], [k]: v };
    m.adjust = { ...m.adjust, pointColors: pts };
    this.host.view.setDragging(phase === 'drag');
    develop.patch('masks', masks, phase, 'Mask Point Color');
  }

  private paintPoints(m: Mask | undefined): void {
    setHidden(this.points, !m);
    const pts = this.localPoints(m);
    if (this.pointIdx >= pts.length) this.pointIdx = Math.max(0, pts.length - 1);
    const html = pts.map((p, i) => {
      const a = p.chroma * Math.cos((p.hue * Math.PI) / 180), b = p.chroma * Math.sin((p.hue * Math.PI) / 180);
      return `<button class="fl-point-sw${i === this.pointIdx ? ' is-on' : ''}" type="button" data-pt="${i}" style="background: oklab(${(p.lum * 100).toFixed(1)}% ${a.toFixed(4)} ${b.toFixed(4)})" aria-label="Point ${i + 1}"></button>`;
    }).join('') || `<span class="fl-muted">${this.pickPoint ? 'Click a colour in the photo' : 'Press the eyedropper, then click a colour'}</span>`;
    const sw = q(this.points, '.fl-point-swatches');
    if (sw.dataset.key !== html) { sw.dataset.key = html; sw.innerHTML = html; }
    setClass(q(this.points, '[data-a="pickpoint"]'), 'is-on', this.pickPoint);
    setHidden(q(this.points, '.fl-mask-point-sliders'), !pts.length);
    const cur = pts[this.pointIdx];
    for (const [k, s] of this.pointSliders) s.set(cur ? Number(cur[k as keyof LocalPoint] ?? (k === 'range' ? 50 : 0)) : (k === 'range' ? 50 : 0));
  }

  private async addPoint(p: Pt): Promise<void> {
    const id = develop.id;
    if (id === null) return;
    try {
      const r = await this.host.ctx.api.cmd<{ lab: [number, number, number] }>('develop.sampleColor', { id, x: p.nx, y: p.ny, settings: develop.settings });
      const { masks, m } = this.current();
      if (!m) return;
      const pts = this.localPoints(m);
      if (pts.length >= 8) { this.host.ctx.fail(new Error('A mask holds eight point colours; remove one first')); return; }
      const [l, a, b] = r.lab;
      pts.push({ lum: l, chroma: Math.hypot(a, b), hue: ((Math.atan2(b, a) * 180) / Math.PI + 360) % 360, hueShift: 0, satShift: 0, lumShift: 0, variance: 0, range: 50 });
      m.adjust = { ...m.adjust, pointColors: pts };
      this.pointIdx = pts.length - 1;
      if (!p.e.shiftKey) this.pickPoint = false;
      this.write(masks, 'end', 'Mask Point Color');
    } catch (err) { this.host.ctx.fail(err, 'Point Color'); }
  }

  private async loadEffects(): Promise<void> {
    try {
      const p = await this.host.ctx.api.cmd<Record<string, unknown>>('prefs.get');
      this.effects = [...EFFECT_PRESETS, ...((p.maskEffects as EffectPreset[] | undefined) ?? [])];
    } catch { this.effects = EFFECT_PRESETS; }
    const mine = this.effects.filter((e) => !e.builtin);
    const html = [`<option value="">Custom</option>`, ...this.effects.map((e, i) => `<option value="${i}">${escapeHtml(e.name)}</option>`), '<option value="#save">Save Current Settings as New Preset...</option>', ...mine.map((e) => `<option value="#del:${escapeHtml(e.name)}">Delete Preset "${escapeHtml(e.name)}"</option>`)].join('');
    if (this.effect.dataset.key !== html) { this.effect.dataset.key = html; this.effect.innerHTML = html; }
  }

  private async pickEffect(v: string): Promise<void> {
    const { masks, m } = this.current();
    const mine = this.effects.filter((e) => !e.builtin);
    if (v === '#save') {
      if (!m) return;
      const name = (await promptName('New Mask Effect Preset', 'My Effect', 'Create'))?.trim();
      if (!name) return;
      const adjust = Object.fromEntries(Object.entries(m.adjust ?? {}).filter(([k]) => k !== 'amount'));
      await this.host.ctx.api.cmd('prefs.set', { values: { maskEffects: [...mine.filter((e) => e.name !== name), { name, adjust }] } }).catch((err) => this.host.ctx.fail(err));
      await this.loadEffects();
      return;
    }
    if (v.startsWith('#del:')) {
      await this.host.ctx.api.cmd('prefs.set', { values: { maskEffects: mine.filter((e) => e.name !== v.slice(5)) } }).catch((err) => this.host.ctx.fail(err));
      await this.loadEffects();
      return;
    }
    const preset = this.effects[Number(v)];
    if (!m || !preset || v === '') return;
    m.adjust = { ...(m.adjust?.amount !== undefined ? { amount: m.adjust.amount } : {}), ...clone(preset.adjust) };
    this.write(masks, 'end', `Mask Effect: ${preset.name}`);
  }

  constructor(private readonly host: ToolHost) {
    const btn = ([k, l, ic]: [string, string, string]) => `<button class="fl-mask-new" type="button" data-new="${k}" title="${l}">${icon(ic, 16)}<span>${l}</span></button>`;
    this.root = el(`<div class="fl-tool-opts fl-masks">
<div class="fl-tool-title">${icon('masking', 14)} Masks<span class="fl-grow"></span><label class="fl-check fl-check-sm"><input type="checkbox" data-overlay checked> Show Overlay (O)</label></div>
<div class="fl-mask-list"></div>
<div class="fl-sub">Create New Mask</div>
<div class="fl-mask-grid">${AI_KINDS.map(btn).join('')}${PART_GROUPS.map(btn).join('')}${MANUAL.map(btn).join('')}${RANGES.map(btn).join('')}</div>
<div class="fl-mask-parts" hidden><div class="fl-sub fl-mask-parts-title"></div><div class="fl-mask-who"></div><div class="fl-mask-parts-list"></div><label class="fl-check fl-check-sm"><input type="checkbox" data-separate> Create separate masks</label><div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm" type="button" data-a="parts-cancel">Cancel</button><button class="cv-btn fl-btn-sm fl-btn-cta" type="button" data-a="parts-create">Create Mask</button></div></div>
<div class="fl-mask-comp"></div>
<div class="fl-mask-brush" hidden></div>
<div class="fl-mask-adjust" hidden><div class="fl-sub">Adjustments</div><div class="fl-row"><span class="fl-row-label">Effect</span><select class="cv-select fl-grow" data-effect aria-label="Effect preset"></select></div></div>
<div class="fl-mask-points" hidden><div class="fl-sub">Point Color<span class="fl-grow"></span><button class="cv-icon-btn" type="button" data-a="pickpoint" title="Pick a colour in the photo">${icon('eyeDropper', 14)}</button></div><div class="fl-point-swatches"></div><div class="fl-mask-point-sliders"></div></div>
<div class="fl-mask-curve" hidden><div class="fl-sub">Curve</div></div>
<div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm" type="button" data-a="invert">Invert</button><button class="cv-btn fl-btn-sm" type="button" data-a="dup">Duplicate</button><button class="cv-btn fl-btn-sm" type="button" data-a="delete">Delete</button><button class="cv-btn fl-btn-sm fl-btn-cta" type="button" data-a="done">Done</button></div>
</div>`);
    this.list = q(this.root, '.fl-mask-list');
    this.adjust = q(this.root, '.fl-mask-adjust');
    this.compOpts = q(this.root, '.fl-mask-comp');
    this.brushOpts = q(this.root, '.fl-mask-brush');
    for (const spec of develop.doc?.local ?? []) {
      const s = new Slider(spec, { input: (id, v, phase) => this.setAdjust(id, v, phase) });
      this.sliders.set(spec.id, s);
      this.adjust.appendChild(s.root);
    }
    const tint = new Slider({ id: 'colorSat', label: 'Color', min: 0, max: 100, default: 0, step: 1, decimals: 0 }, { input: (id, v, phase) => this.setAdjust(id, v, phase) });
    const tintHue = new Slider({ id: 'colorHue', label: 'Color Hue', min: 0, max: 360, default: 0, step: 1, decimals: 0, track: { kind: 'rainbow' } }, { input: (id, v, phase) => this.setAdjust(id, v, phase) });
    this.sliders.set('colorSat', tint);
    this.sliders.set('colorHue', tintHue);
    this.adjust.append(tintHue.root, tint.root);
    this.points = q(this.root, '.fl-mask-points');
    for (const [k, label, min, max] of POINT_KEYS) {
      const s = new Slider({ id: k, label, min, max, default: k === 'range' ? 50 : 0, step: 1, decimals: 0 }, { input: (id, v, phase) => this.setPoint(id as keyof LocalPoint, v, phase) });
      this.pointSliders.set(k, s);
      q(this.points, '.fl-mask-point-sliders').appendChild(s.root);
    }
    this.curveBox = q(this.root, '.fl-mask-curve');
    this.curve = new CurveEditor({
      get: () => (this.current().m?.adjust?.curve as Record<string, unknown> | undefined) ?? {},
      set: (curve, phase, label) => {
        const { masks, m } = this.current();
        if (!m) return;
        m.adjust = { ...(m.adjust ?? {}) };
        if (['master', 'red', 'green', 'blue'].some((k) => curve[k])) m.adjust.curve = curve; else delete m.adjust.curve;
        this.host.view.setDragging(phase === 'drag');
        develop.patch('masks', masks, phase, `Mask ${label}`);
      },
    }, false);
    this.curveBox.appendChild(this.curve.root);
    this.effect = q<HTMLSelectElement>(this.root, '[data-effect]');
    this.effect.addEventListener('change', () => { const v = this.effect.value; this.effect.value = ''; this.effect.blur(); void this.pickEffect(v); });
    void this.loadEffects();
    this.buildBrush();
    this.root.addEventListener('click', (e) => this.click(e));
    q<HTMLInputElement>(this.root, '[data-overlay]').addEventListener('change', (e) => { this.showOverlay = (e.target as HTMLInputElement).checked; this.host.view.schedule(); });
  }

  activate(): void {
    this.host.drawer.replaceChildren(this.root);
    const masks = this.masks();
    if (this.sel >= masks.length) this.sel = masks.length - 1;
    if (this.sel < 0 && masks.length) this.sel = 0;
    this.sync();
  }

  overlay(): Record<string, unknown> | null {
    const m = this.masks()[this.sel];
    return this.showOverlay && m ? { mask: m.id, opacity: 0.45 } : null;
  }

  private masks(): Mask[] { return clone(this.ghost ?? (develop.settings.masks as Mask[] | undefined) ?? []); }

  private ghostStart(shape: Shape, op: 'new' | Op): () => void {
    const keep = [this.sel, this.comp];
    const g = this.masks();
    this.place({ ...shape, label: `${NAMES[shape.kind] ?? shape.kind} (finding)` }, op, g);
    this.ghost = g;
    this.sync();
    return () => { this.ghost = null; [this.sel, this.comp] = keep; };
  }

  private write(masks: Mask[], phase: 'drag' | 'end', label: string): void {
    if (this.ghost) return;
    const tidy = (v: unknown): unknown => typeof v === 'number' ? Math.round(v * 1e5) / 1e5 : Array.isArray(v) ? v.map(tidy) : v && typeof v === 'object' ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, tidy(x)])) : v;
    if (phase === 'end') masks = tidy(masks) as Mask[];
    develop.patch('masks', masks.length ? masks : null, phase, label);
    this.sync();
    this.host.view.draw();
  }

  private current(): { masks: Mask[]; m: Mask | undefined; c: Component | undefined } {
    const masks = this.masks();
    const m = masks[this.sel];
    return { masks, m, c: m?.components[this.comp] };
  }

  private buildBrush(): void {
    const mk = (id: string, label: string, min: number, max: number, val: number, fn: (v: number) => void) => {
      const s = new Slider({ id, label, min, max, default: val, step: 1, decimals: 0 }, { input: (_id, v) => fn(v) });
      s.set(val);
      return s.root;
    };
    this.brushOpts.append(el('<div class="fl-sub">Brush</div>'),
      mk('b.size', 'Size', 2, 300, 30, (v) => { this.brush.size = v / 1000; }),
      mk('b.feather', 'Feather', 0, 100, 60, (v) => { this.brush.feather = v; }),
      mk('b.flow', 'Flow', 1, 100, 80, (v) => { this.brush.flow = v; }),
      mk('b.density', 'Density', 1, 100, 100, (v) => { this.brush.density = v; }),
      el('<div class="fl-row"><label class="fl-check fl-check-sm"><input type="checkbox" data-auto> Auto Mask</label><label class="fl-check fl-check-sm" title="Stop the soft edge of the brush at the nearest strong edge in the photo"><input type="checkbox" data-snap> Edge Snap</label><label class="fl-check fl-check-sm"><input type="checkbox" data-erase> Erase (Alt)</label></div>'));
    q<HTMLInputElement>(this.brushOpts, '[data-auto]').addEventListener('change', (e) => { this.brush.auto = (e.target as HTMLInputElement).checked; });
    q<HTMLInputElement>(this.brushOpts, '[data-snap]').addEventListener('change', (e) => { this.brush.snap = (e.target as HTMLInputElement).checked; });
    q<HTMLInputElement>(this.brushOpts, '[data-erase]').addEventListener('change', (e) => { this.brush.erase = (e.target as HTMLInputElement).checked; });
  }

  private click(e: Event): void {
    const t = e.target as HTMLElement;
    const nw = t.closest<HTMLElement>('[data-new]')?.dataset.new;
    if (nw === 'people-parts' || nw === 'landscape' || nw === 'people') { void this.openParts(nw === 'landscape' ? 'landscape' : nw === 'people' ? 'persons' : 'people'); return; }
    if (nw) { void this.create(nw, 'new'); return; }
    const pa = t.closest<HTMLElement>('[data-a="parts-cancel"], [data-a="parts-create"]')?.dataset.a;
    if (pa === 'parts-cancel') { setHidden(q(this.root, '.fl-mask-parts'), true); return; }
    if (pa === 'parts-create') { void this.createParts(); return; }
    const pt = t.closest<HTMLElement>('[data-pt]');
    if (pt) { this.pointIdx = Number(pt.dataset.pt); this.paintPoints(this.current().m); return; }
    if (t.closest('[data-a="pickpoint"]')) {
      this.pickPoint = !this.pickPoint;
      this.host.ctx.shell.setHint(this.pickPoint ? 'Click a colour in the photo to shift it inside this mask. Shift-click to keep picking.' : '');
      this.paintPoints(this.current().m);
      return;
    }
    const addTo = t.closest<HTMLElement>('[data-addop]');
    if (addTo) { void this.create(addTo.dataset.kind as string, addTo.dataset.addop as Op); return; }
    const row = t.closest<HTMLElement>('[data-mask]');
    if (row) {
      const i = Number(row.dataset.mask);
      if (t.closest('[data-eye]')) {
        const masks = this.masks();
        masks[i].visible = masks[i].visible === false;
        this.write(masks, 'end', 'Mask Visibility');
        return;
      }
      const ci = t.closest<HTMLElement>('[data-comp]');
      this.sel = i;
      this.comp = ci ? Number(ci.dataset.comp) : 0;
      this.sync();
      this.host.view.schedule();
      return;
    }
    const a = t.closest<HTMLElement>('[data-a]')?.dataset.a;
    const { masks, m } = this.current();
    if (a === 'done') { this.host.done(); return; }
    if (!m) return;
    if (a === 'invert') { m.invert = !m.invert; this.write(masks, 'end', 'Invert Mask'); }
    if (a === 'delete') { masks.splice(this.sel, 1); this.sel = Math.min(this.sel, masks.length - 1); this.comp = 0; this.write(masks, 'end', 'Delete Mask'); }
    if (a === 'dup') { const copy = clone(m); copy.id = this.nextId(masks); copy.name = `${m.name} Copy`; masks.push(copy); this.sel = masks.length - 1; this.write(masks, 'end', 'Duplicate Mask'); }
    if (a === 'edge') { void this.toggleEdge(); return; }
    if (a === 'edge-reset') {
      const c = m.components[this.comp];
      if (c) { delete c.shape.outline; this.edgeEd = null; this.host.ctx.shell.setHint(''); this.write(masks, 'end', 'Reset Mask Edge'); }
      return;
    }
    const op = t.closest<HTMLElement>('[data-compop]');
    if (op) {
      const c = m.components[this.comp];
      if (c) { c.op = op.dataset.compop as Component['op']; this.write(masks, 'end', 'Mask Mode'); }
    }
  }

  private nextId(masks: Mask[]): number { return masks.reduce((a, m) => Math.max(a, m.id), 0) + 1; }

  private partGroup: 'people' | 'landscape' | 'persons' = 'people';
  private people: { id: number; all: Shape; persons: Array<{ index: number; thumb: string; coverage: number; shape: Shape }> } | null = null;

  private async loadPeople(): Promise<boolean> {
    const id = develop.id;
    if (id === null) return false;
    if (this.people?.id === id) return true;
    const done = this.host.ctx.shell.busy('Finding people');
    try {
      await develop.flush();
      const r = await this.host.ctx.api.cmd<{ all: Shape; persons: Array<{ index: number; thumb: string; coverage: number; shape: Shape }> }>('develop.aiPeople', { id });
      this.people = { id, ...r };
      return true;
    } catch (err) { this.host.ctx.fail(err, 'People'); return false; } finally { done(); }
  }

  private async openParts(group: 'people' | 'landscape' | 'persons'): Promise<void> {
    if (group !== 'landscape' && !(await this.loadPeople())) return;
    this.partGroup = group;
    const box = q(this.root, '.fl-mask-parts');
    setText(q(box, '.fl-mask-parts-title'), group === 'people' ? 'People Parts' : group === 'persons' ? `People (${this.people?.persons.length ?? 0} found)` : 'Landscape');
    const persons = this.people?.persons ?? [];
    const who = q(box, '.fl-mask-who');
    const whoHtml = group === 'people' && persons.length > 1 ? `<div class="fl-row"><span class="fl-row-label">Person</span><select class="cv-select fl-grow" data-who><option value="">All People</option>${persons.map((p) => `<option value="${p.index}">Person ${p.index + 1}</option>`).join('')}</select></div>` : '';
    if (who.dataset.key !== `${group}:${this.people?.id}:${persons.length}`) { who.dataset.key = `${group}:${this.people?.id}:${persons.length}`; who.innerHTML = whoHtml; }
    const html = group === 'persons'
      ? `<label class="fl-check fl-check-sm fl-person"><input type="checkbox" data-person="all" checked> All People</label>${persons.map((p) => `<label class="fl-check fl-check-sm fl-person"><input type="checkbox" data-person="${p.index}">${p.thumb ? `<img alt="" src="data:image/jpeg;base64,${p.thumb}">` : ''} Person ${p.index + 1}</label>`).join('')}`
      : PARTS[group].map(([k, l]) => `<label class="fl-check fl-check-sm"><input type="checkbox" data-part="${k}"> ${l}</label>`).join('');
    const list = q(box, '.fl-mask-parts-list');
    const key = group === 'persons' ? `persons:${this.people?.id}:${persons.length}` : group;
    if (list.dataset.key !== key) { list.dataset.key = key; list.innerHTML = html; }
    setClass(list, 'is-persons', group === 'persons');
    setHidden(box, false);
  }

  private personsShapes(): Array<[string, Shape]> {
    const box = q(this.root, '.fl-mask-parts');
    const picked = Array.from(box.querySelectorAll<HTMLInputElement>('[data-person]')).filter((i) => i.checked).map((i) => i.dataset.person as string);
    if (!this.people || !picked.length) return [];
    if (picked.includes('all')) return [['People', this.people.all]];
    return picked.map((v) => { const p = this.people?.persons[Number(v)]; return [`Person ${Number(v) + 1}`, p?.shape] as [string, Shape | undefined]; }).filter((x): x is [string, Shape] => !!x[1]);
  }

  private async createParts(): Promise<void> {
    const box = q(this.root, '.fl-mask-parts');
    const separate = q<HTMLInputElement>(box, '[data-separate]').checked;
    if (this.partGroup === 'persons') {
      const shapes = this.personsShapes();
      if (!shapes.length) { this.host.ctx.fail(new Error('Tick one or more people')); return; }
      const masks = this.masks();
      if (separate) for (const [name, s] of shapes) masks.push({ id: this.nextId(masks), name, visible: true, components: [{ shape: s, op: 'add' }], adjust: {} });
      else masks.push({ id: this.nextId(masks), name: shapes.map(([n]) => n).join(', '), visible: true, components: shapes.map(([, s]) => ({ shape: s, op: 'add' as const })), adjust: {} });
      this.sel = masks.length - 1;
      this.comp = 0;
      setHidden(box, true);
      this.write(masks, 'end', 'Mask: People');
      return;
    }
    const parts = Array.from(box.querySelectorAll<HTMLInputElement>('[data-part]')).filter((i) => i.checked).map((i) => i.dataset.part as string);
    if (!parts.length) { this.host.ctx.fail(new Error('Tick one or more parts')); return; }
    const id = develop.id;
    if (id === null) return;
    const whoSel = box.querySelector<HTMLSelectElement>('[data-who]');
    const person = whoSel && whoSel.value !== '' ? Number(whoSel.value) : undefined;
    const done = this.host.ctx.shell.busy(this.partGroup === 'people' ? 'Finding people parts' : 'Finding landscape parts');
    try {
      await develop.flush();
      const r = await this.host.ctx.api.cmd<{ shapes: Shape[] }>('develop.aiParts', { id, group: this.partGroup, parts, ...(person !== undefined ? { person } : {}) });
      const masks = this.masks();
      if (separate) {
        for (const s of r.shapes) masks.push({ id: this.nextId(masks), name: String(s.label ?? s.part), visible: true, components: [{ shape: s, op: 'add' }], adjust: {} });
      } else {
        masks.push({ id: this.nextId(masks), name: r.shapes.map((s) => String(s.label ?? s.part)).join(', '), visible: true, components: r.shapes.map((s) => ({ shape: s, op: 'add' as const })), adjust: {} });
      }
      this.sel = masks.length - 1;
      this.comp = 0;
      setHidden(box, true);
      this.write(masks, 'end', this.partGroup === 'people' ? 'Mask: People Parts' : 'Mask: Landscape');
    } catch (err) { this.host.ctx.fail(err, 'AI Mask'); } finally { done(); }
  }

  private defaultShape(kind: string): Shape {
    switch (kind) {
      case 'linear': return { kind, start: [0.5, 0.2], end: [0.5, 0.6] };
      case 'radial': return { kind, center: [0.5, 0.5], rx: 0.2, ry: 0.15, angle: 0, feather: 50 };
      case 'brush': return { kind, strokes: [] };
      case 'luminanceRange': return { kind, lo: 0.5, hi: 1.0, loFeather: 0.1, hiFeather: 0.1 };
      case 'colorRange': return { kind, samples: [], refine: 50 };
      case 'depthRange': return { kind, lo: 0.0, hi: 0.4, feather: 0.1, bitmap: 'depth' };
      case 'edgeRange': return { kind, lo: 0.35, hi: 1.0, loFeather: 0.1, detail: 0.5 };
      default: return { kind };
    }
  }

  private pendingOp: 'new' | Op = 'new';

  private place(shape: Shape, op: 'new' | Op, masks: Mask[]): void {
    if (op === 'new' || !masks[this.sel]) {
      masks.push({ id: this.nextId(masks), name: `Mask ${masks.length + 1}`, visible: true, components: [{ shape, op: 'add' }], adjust: {} });
      this.sel = masks.length - 1;
      this.comp = 0;
    } else {
      masks[this.sel].components.push({ shape, op });
      this.comp = masks[this.sel].components.length - 1;
    }
  }

  private async create(kind: string, op: 'new' | Op): Promise<void> {
    if (kind === 'linear' || kind === 'radial' || kind === 'object') {
      this.pendingKind = kind;
      this.pendingOp = op;
      this.host.ctx.shell.setHint(kind === 'object' ? 'Click the object, or drag a box around it, to select it' : `Drag on the photo to place the ${NAMES[kind].toLowerCase()}`);
      return;
    }
    let shape = this.defaultShape(kind);
    if (AI_KINDS.some(([k]) => k === kind) || kind === 'depthRange') {
      const id = develop.id;
      if (id === null) return;
      const done = this.host.ctx.shell.busy(`Detecting ${NAMES[kind].toLowerCase()}`);
      const unghost = this.ghostStart(shape, op);
      try {
        await develop.flush();
        const r = await this.host.ctx.api.cmd<{ shape: Shape }>('develop.aiMask', { id, kind: kind === 'depthRange' ? 'depth' : kind });
        shape = kind === 'depthRange' ? { ...shape, bitmap: (r.shape.bitmap as string) ?? 'depth' } : r.shape;
      } catch (err) { unghost(); this.sync(); this.host.ctx.fail(err, NAMES[kind]); return; } finally { done(); }
      unghost();
    }
    const masks = this.masks();
    this.place(shape, op, masks);
    this.pendingKind = '';
    this.write(masks, 'end', `Mask: ${NAMES[kind] ?? kind}`);
  }

  private setAdjust(id: string, v: number, phase: 'drag' | 'end'): void {
    const { masks, m } = this.current();
    if (!m) return;
    m.adjust = { ...(m.adjust ?? {}), [id]: v };
    if (v === 0 && id !== 'amount') delete m.adjust[id];
    this.host.view.setDragging(phase === 'drag');
    develop.patch('masks', masks, phase, `Mask ${develop.doc?.local.find((s) => s.id === id)?.label ?? id}`);
  }

  sync(): void {
    const masks = this.masks();
    const items = masks.map((m, i) => ({ m, i }));
    const update = (node: HTMLElement, x: { m: (typeof masks)[number]; i: number }) => {
      const comps = x.m.components.map((c, k) => `<button class="fl-mask-comp-row${x.i === this.sel && k === this.comp ? ' is-on' : ''}" type="button" data-mask="${x.i}" data-comp="${k}">${icon(this.iconOf(c.shape.kind), 12)}<span>${c.op === 'add' ? '' : c.op === 'subtract' ? 'Subtract: ' : c.op === 'refine' ? 'Refine Edge: ' : 'Intersect: '}${escapeHtml(String(c.shape.label ?? NAMES[c.shape.kind] ?? c.shape.kind))}</span></button>`).join('');
      const html = `<div class="fl-mask-head${x.i === this.sel ? ' is-on' : ''}" data-mask="${x.i}"><button class="cv-icon-btn" type="button" data-eye aria-label="Show or hide">${icon(x.m.visible === false ? 'eyeOff' : 'eye', 13)}</button><span class="fl-grow">${escapeHtml(x.m.name)}${x.m.invert ? ' (inverted)' : ''}</span></div>${x.i === this.sel ? comps : ''}`;
      if (node.dataset.html !== html) { node.dataset.html = html; node.innerHTML = html; }
    };
    patchList(this.list, items, {
      key: (x) => String(x.m.id),
      create: (x) => { const n = el('<div class="fl-mask-row"></div>'); update(n, x); return n; },
      update,
    });
    const { m, c } = this.current();
    if (this.edgeEd && this.edgeEd.key !== this.edgeKey()) { this.edgeEd = null; this.host.ctx.shell.setHint(''); }
    setClass(this.root, 'is-finding', !!this.ghost);
    setHidden(this.adjust, !m);
    setHidden(this.curveBox, !m);
    if (m) this.curve.sync();
    if (m) {
      for (const [id, s] of this.sliders) s.set(Number(m.adjust?.[id] ?? (id === 'amount' ? 100 : 0)));
    }
    this.paintPoints(m);
    setHidden(this.brushOpts, c?.shape.kind !== 'brush');
    const opList: Op[] = c?.shape.kind === 'brush' && this.comp > 0 ? ['add', 'subtract', 'intersect', 'refine'] : ['add', 'subtract', 'intersect'];
    const ops = c ? `<div class="fl-sub">Component</div><div class="fl-row"><div class="cv-seg fl-seg-sm fl-grow">${opList.map((o) => `<button type="button" data-compop="${o}" class="${c.op === o ? 'is-on' : ''}">${o === 'refine' ? 'Refine' : o.charAt(0).toUpperCase() + o.slice(1)}</button>`).join('')}</div></div><div class="fl-row fl-mask-addrow"><span class="fl-row-label">Add</span>${[...MANUAL, ...RANGES, ...AI_KINDS].slice(0, 6).map(([k, l, ic]) => `<button class="cv-icon-btn" type="button" data-addop="add" data-kind="${k}" title="Add ${l}">${icon(ic, 14)}</button>`).join('')}<button class="cv-icon-btn" type="button" data-addop="refine" data-kind="brush" title="Refine Edge Brush: paint over hair, fur or a soft edge and the mask follows the photo's edges there">${icon('maskRefine', 14)}</button></div>${this.shapeControls(c.shape)}` : '';
    if (this.compOpts.dataset.html !== ops) {
      this.compOpts.dataset.html = ops;
      this.compOpts.innerHTML = ops;
      this.wireShapeControls();
    }
  }

  private iconOf(kind: string): string { return [...AI_KINDS, ...MANUAL, ...RANGES].find(([k]) => k === kind)?.[2] ?? 'masking'; }

  private shapeControls(s: Shape): string {
    const range = (key: string, label: string, v: number) => `<label class="fl-opt"><span>${label}</span><input class="cv-slider" type="range" min="0" max="100" step="1" value="${Math.round(v * 100)}" data-shape="${key}"></label>`;
    if (s.kind === 'luminanceRange') return range('lo', 'Low', Number(s.lo ?? 0.5)) + range('hi', 'High', Number(s.hi ?? 1)) + range('loFeather', 'Low Feather', Number(s.loFeather ?? 0.1)) + range('hiFeather', 'High Feather', Number(s.hiFeather ?? 0.1));
    if (s.kind === 'edgeRange') return '<div class="fl-muted">Selects edges and fine detail, or flat areas with Invert, so sharpening, clarity or noise reduction land only where they help. A higher threshold keeps only strong edges.</div>' + range('lo', 'Edge Threshold', Number(s.lo ?? 0.35)) + range('loFeather', 'Feather', Number(s.loFeather ?? 0.1)) + range('detail', 'Fine Detail', Number(s.detail ?? 0.5)) + '<label class="fl-check fl-check-sm"><input type="checkbox" data-shape-invert> Invert (flat areas)</label>';
    if (s.kind === 'depthRange') return range('lo', 'Near', Number(s.lo ?? 0)) + range('hi', 'Far', Number(s.hi ?? 0.4)) + range('feather', 'Feather', Number(s.feather ?? 0.1));
    if (s.kind === 'colorRange') return `<div class="fl-muted">Click the photo to pick a color, Shift-click to add more.</div>${range('refine', 'Refine', Number(s.refine ?? 50) / 100)}`;
    if (s.kind === 'radial') return range('feather', 'Feather', Number(s.feather ?? 50) / 100) + '<label class="fl-check fl-check-sm"><input type="checkbox" data-shape-invert> Invert Radial</label>';
    if (s.kind === 'linear') return '<div class="fl-muted">Drag on the photo to set the gradient.</div>';
    if (s.kind === 'brush') return this.current().c?.op === 'refine' ? '<div class="fl-muted">Paint over hair, fur or a soft edge: the mask follows the photo\'s edges where you paint. Hold Alt to erase.</div>' : '<div class="fl-muted">Paint on the photo. Hold Alt to erase.</div>';
    if (BITMAP_KINDS.has(s.kind)) {
      const edge = (key: string, label: string, min: number, title: string) => `<label class="fl-opt" title="${title}"><span>${label}</span><input class="cv-slider" type="range" min="${min}" max="100" step="1" value="${Math.round(Number(s[key] ?? 0))}" data-shape="${key}" data-int></label>`;
      return edge('refine', 'Refine Edge', 0, 'Snaps the mask edge to the edges in the photo, for hair and soft outlines') + edge('shift', 'Shift Edge', -100, 'Grows the mask outward or shrinks it inward, up to 2 percent of the long side') + edge('feather', 'Feather', 0, 'Softens the mask edge, up to 3 percent of the long side')
        + `<div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm${this.edgeEd ? ' is-on' : ''}" type="button" data-a="edge" title="Show the mask outline as dots: drag a dot to move the edge, click the outline to add a dot, Alt-click a dot to remove it">Edit Edge Points</button><button class="cv-btn fl-btn-sm" type="button" data-a="edge-reset"${s.outline ? '' : ' disabled'}>Reset Edge</button></div>`;
    }
    return '';
  }

  private wireShapeControls(): void {
    for (const inp of Array.from(this.compOpts.querySelectorAll<HTMLInputElement>('[data-shape]'))) {
      const write = (phase: 'drag' | 'end') => {
        const { masks, c } = this.current();
        if (!c) return;
        const key = inp.dataset.shape as string;
        const v = Number(inp.value) / 100;
        c.shape[key] = inp.dataset.int !== undefined ? Math.round(Number(inp.value)) : key === 'refine' || (key === 'feather' && c.shape.kind === 'radial') ? Math.round(v * 100) : v;
        this.host.view.setDragging(phase === 'drag');
        develop.patch('masks', masks, phase, inp.dataset.int !== undefined ? 'Mask Edge' : 'Mask Range');
      };
      inp.addEventListener('input', () => write('drag'));
      inp.addEventListener('change', () => write('end'));
    }
    const inv = this.compOpts.querySelector<HTMLInputElement>('[data-shape-invert]');
    if (inv) {
      inv.checked = !!this.current().c?.shape.invert;
      inv.addEventListener('change', () => { const { masks, c } = this.current(); if (c) { c.shape.invert = inv.checked; this.write(masks, 'end', c.shape.kind === 'radial' ? 'Invert Radial' : 'Invert Edge Range'); } });
    }
  }

  private stage(v: Vec): [number, number] { return this.host.view.normToStage(v[0], v[1]); }

  private edgeEd: { key: string; polys: Vec[][]; orig: Vec[][]; sig: number; drag: { p: number; i: number } | null } | null = null;

  private edgeKey(): string {
    const { c } = this.current();
    return c && BITMAP_KINDS.has(c.shape.kind) ? `${this.sel}:${this.comp}:${String(c.shape.bitmap ?? '')}` : '';
  }

  private async toggleEdge(): Promise<void> {
    if (this.edgeEd) { this.edgeEd = null; this.host.ctx.shell.setHint(''); this.sync(); this.host.view.draw(); return; }
    const { c } = this.current();
    const key = this.edgeKey();
    if (!c || !key || develop.id === null) return;
    const saved = c.shape.outline as { edit?: Vec[][]; orig?: Vec[][]; sig?: number } | undefined;
    try {
      const r = saved?.edit && saved.orig && saved.sig !== undefined ? { polys: saved.edit, orig: saved.orig, sig: saved.sig }
        : await this.host.ctx.api.cmd<{ polys: Vec[][]; sig: number }>('develop.maskOutline', { id: develop.id, bitmap: String(c.shape.bitmap) }).then((x) => ({ ...x, orig: clone(x.polys) }));
      if (this.edgeKey() !== key) return;
      this.edgeEd = { key, polys: clone(r.polys), orig: r.orig, sig: r.sig, drag: null };
      this.host.ctx.shell.setHint('Drag a dot to move the edge, click the outline to add a dot, Alt-click a dot to remove it');
      this.sync();
      this.host.view.draw();
    } catch (err) { this.host.ctx.fail(err, 'Edge Points'); }
  }

  private edgeCommit(phase: 'drag' | 'end'): void {
    const e = this.edgeEd;
    const { masks, c } = this.current();
    if (!e || !c) return;
    c.shape.outline = { orig: e.orig, edit: e.polys, sig: e.sig };
    this.host.view.setDragging(phase === 'drag');
    if (phase === 'end') this.write(masks, 'end', 'Mask Edge Points'); else develop.patch('masks', masks, 'drag', 'Mask Edge Points');
  }

  private edgeDown(p: Pt): boolean {
    const e = this.edgeEd;
    if (!e) return false;
    for (let pi = 0; pi < e.polys.length; pi++) {
      const poly = e.polys[pi];
      for (let i = 0; i < poly.length; i++) {
        const s = this.stage(poly[i]);
        if (Math.hypot(s[0] - p.sx, s[1] - p.sy) > 7) continue;
        if (p.e.altKey) { if (poly.length > 3) { poly.splice(i, 1); this.edgeCommit('end'); } return true; }
        e.drag = { p: pi, i };
        return true;
      }
    }
    for (let pi = 0; pi < e.polys.length; pi++) {
      const poly = e.polys[pi];
      for (let i = 0; i < poly.length; i++) {
        const a = this.stage(poly[i]), b = this.stage(poly[(i + 1) % poly.length]);
        const dx = b[0] - a[0], dy = b[1] - a[1];
        const t = Math.max(0, Math.min(1, ((p.sx - a[0]) * dx + (p.sy - a[1]) * dy) / Math.max(1e-6, dx * dx + dy * dy)));
        if (Math.hypot(a[0] + t * dx - p.sx, a[1] + t * dy - p.sy) > 6) continue;
        poly.splice(i + 1, 0, [p.nx, p.ny]);
        e.drag = { p: pi, i: i + 1 };
        this.host.view.draw();
        return true;
      }
    }
    return true;
  }

  private drawEdge(c: CanvasRenderingContext2D): void {
    const e = this.edgeEd;
    if (!e) return;
    c.save();
    c.lineWidth = 1.25;
    c.strokeStyle = 'rgba(255,255,255,0.9)';
    for (const poly of e.polys) {
      c.beginPath();
      poly.forEach((v, i) => { const s = this.stage(v); if (i) c.lineTo(s[0], s[1]); else c.moveTo(s[0], s[1]); });
      c.closePath();
      c.stroke();
    }
    c.shadowBlur = 0;
    for (const poly of e.polys) {
      for (const v of poly) {
        const s = this.stage(v);
        c.beginPath();
        c.arc(s[0], s[1], 3.5, 0, Math.PI * 2);
        c.fillStyle = '#fff';
        c.fill();
        c.lineWidth = 1;
        c.strokeStyle = 'rgba(0,0,0,0.75)';
        c.stroke();
      }
    }
    c.restore();
  }

  hover(p: Pt | null): void { this.hoverPt = p; if (this.current().c?.shape.kind === 'brush') this.host.view.draw(); }

  private box: { a: Pt; b: Pt } | null = null;

  private async objectFrom(a: Pt, b: Pt): Promise<void> {
    const id = develop.id;
    if (id === null) return;
    const click = Math.abs(a.sx - b.sx) <= 6 && Math.abs(a.sy - b.sy) <= 6;
    const prompt = click ? { points: [[b.nx, b.ny]] } : { box: [Math.min(a.nx, b.nx), Math.min(a.ny, b.ny), Math.max(a.nx, b.nx), Math.max(a.ny, b.ny)] };
    const done = this.host.ctx.shell.busy('Selecting the object');
    const unghost = this.ghostStart({ kind: 'object' }, this.pendingOp);
    try {
      await develop.flush();
      const r = await this.host.ctx.api.cmd<{ shape: Shape }>('develop.aiMask', { id, kind: 'object', ...prompt });
      unghost();
      const masks = this.masks();
      this.place(r.shape, this.pendingOp, masks);
      this.write(masks, 'end', 'Mask: Objects');
    } catch (err) { unghost(); this.sync(); this.host.ctx.fail(err, 'Objects'); } finally { done(); }
  }

  down(p: Pt): boolean {
    if (this.edgeEd && this.edgeEd.key === this.edgeKey()) return this.edgeDown(p);
    if (this.pickPoint && this.current().m) {
      void this.addPoint(p).then(() => { if (!this.pickPoint) this.host.ctx.shell.setHint(''); });
      return true;
    }
    if (this.pendingKind === 'object') {
      this.box = { a: p, b: p };
      return true;
    }
    if (this.pendingKind === 'linear' || this.pendingKind === 'radial') {
      const masks = this.masks();
      const shape = this.pendingKind === 'linear' ? { kind: 'linear', start: [p.nx, p.ny], end: [p.nx, p.ny] } : { kind: 'radial', center: [p.nx, p.ny], rx: 0.005, ry: 0.005, angle: 0, feather: 50 };
      this.place(shape, this.pendingOp, masks);
      this.drag = { kind: shape.kind, start: p, orig: clone(shape), handle: 'create' };
      this.pendingKind = '';
      this.host.ctx.shell.setHint('');
      develop.patch('masks', masks, 'drag', NAMES[shape.kind]);
      this.sync();
      return true;
    }
    const { masks, c } = this.current();
    if (!c) return false;
    const s = c.shape;
    const v = this.host.view;
    if (s.kind === 'linear') {
      const a = this.stage(s.start as Vec), b = this.stage(s.end as Vec);
      const handle = Math.hypot(a[0] - p.sx, a[1] - p.sy) < 10 ? 'start' : Math.hypot(b[0] - p.sx, b[1] - p.sy) < 10 ? 'end' : 'move';
      this.drag = { kind: 'linear', start: p, orig: clone(s), handle };
      return true;
    }
    if (s.kind === 'radial') {
      const ctr = this.stage(s.center as Vec);
      const k = v.pxPerLong();
      const rx = Number(s.rx) * k, ry = Number(s.ry) * k;
      const onEdgeX = Math.abs(Math.abs(p.sx - ctr[0]) - rx) < 10 && Math.abs(p.sy - ctr[1]) < 12;
      const onEdgeY = Math.abs(Math.abs(p.sy - ctr[1]) - ry) < 10 && Math.abs(p.sx - ctr[0]) < 12;
      const handle = onEdgeX ? 'rx' : onEdgeY ? 'ry' : 'move';
      this.drag = { kind: 'radial', start: p, orig: clone(s), handle };
      return true;
    }
    if (s.kind === 'brush') {
      const strokes = (s.strokes as Array<Record<string, unknown>>) ?? [];
      strokes.push({ points: [[p.nx, p.ny]], size: this.brush.size, feather: this.brush.feather, flow: this.brush.flow, density: this.brush.density, erase: this.brush.erase || p.e.altKey, auto: this.brush.auto || undefined, snap: this.brush.snap || undefined });
      s.strokes = strokes;
      this.drag = { kind: 'brush', start: p, orig: s, handle: 'paint', strokeIndex: strokes.length - 1 };
      this.host.view.setDragging(true);
      develop.patch('masks', masks, 'drag', 'Brush');
      return true;
    }
    if (s.kind === 'colorRange') {
      void this.sampleColor(p);
      return true;
    }
    return false;
  }

  private async sampleColor(p: Pt): Promise<void> {
    const id = develop.id;
    if (id === null) return;
    const seq = ++this.seq;
    try {
      const r = await this.host.ctx.api.cmd<{ lab: [number, number, number] }>('develop.sampleColor', { id, x: p.nx, y: p.ny, settings: develop.settings });
      if (seq !== this.seq) return;
      const { masks, c } = this.current();
      if (!c) return;
      const samples = p.e.shiftKey ? ((c.shape.samples as number[][]) ?? []).slice(0, 4) : [];
      samples.push(r.lab);
      c.shape.samples = samples;
      this.write(masks, 'end', 'Color Range');
    } catch (err) { this.host.ctx.fail(err, 'Color Range'); }
  }

  move(p: Pt): void {
    if (this.box) { this.box.b = p; return; }
    if (this.edgeEd?.drag) {
      const d = this.edgeEd.drag;
      this.edgeEd.polys[d.p][d.i] = [p.nx, p.ny];
      this.edgeCommit('drag');
      this.host.view.draw();
      return;
    }
    const d = this.drag;
    if (!d) return;
    const { masks, c } = this.current();
    if (!c) return;
    const s = c.shape;
    const dx = p.nx - d.start.nx, dy = p.ny - d.start.ny;
    const o = d.orig;
    if (d.kind === 'linear') {
      if (d.handle === 'create' || d.handle === 'end') s.end = [p.nx, p.ny];
      else if (d.handle === 'start') s.start = [p.nx, p.ny];
      else { s.start = [(o.start as Vec)[0] + dx, (o.start as Vec)[1] + dy]; s.end = [(o.end as Vec)[0] + dx, (o.end as Vec)[1] + dy]; }
    } else if (d.kind === 'radial') {
      const k = this.host.view.pxPerLong();
      if (d.handle === 'create') { s.rx = Math.max(0.005, Math.abs(p.sx - d.start.sx) / k); s.ry = Math.max(0.005, Math.abs(p.sy - d.start.sy) / k); if (p.e.shiftKey) s.ry = s.rx; }
      else if (d.handle === 'rx') { const ctr = this.stage(o.center as Vec); s.rx = Math.max(0.005, Math.abs(p.sx - ctr[0]) / k); }
      else if (d.handle === 'ry') { const ctr = this.stage(o.center as Vec); s.ry = Math.max(0.005, Math.abs(p.sy - ctr[1]) / k); }
      else s.center = [(o.center as Vec)[0] + dx, (o.center as Vec)[1] + dy];
    } else if (d.kind === 'brush') {
      const strokes = s.strokes as Array<{ points: number[][] }>;
      const st = strokes[d.strokeIndex ?? strokes.length - 1];
      if (!st) return;
      const last = st.points[st.points.length - 1];
      const [lx, ly] = this.stage([last[0], last[1]]);
      if (Math.hypot(lx - p.sx, ly - p.sy) < 3) return;
      st.points.push([Number(p.nx.toFixed(5)), Number(p.ny.toFixed(5))]);
    }
    this.host.view.setDragging(true);
    develop.patch('masks', masks, 'drag', NAMES[s.kind] ?? 'Mask');
  }

  up(): void {
    if (this.edgeEd?.drag) { this.edgeEd.drag = null; this.edgeCommit('end'); return; }
    if (this.box) {
      const { a, b } = this.box;
      this.box = null;
      this.pendingKind = '';
      this.host.ctx.shell.setHint('');
      void this.objectFrom(a, b);
      return;
    }
    const d = this.drag;
    this.drag = null;
    if (!d) return;
    this.pendingKind = '';
    this.host.view.setDragging(false);
    const { masks, c } = this.current();
    if (c) this.write(masks, 'end', NAMES[c.shape.kind] ?? 'Mask');
  }

  key(_e: KeyboardEvent, combo: string): boolean {
    if (combo === 'O') { this.showOverlay = !this.showOverlay; const cb = this.root.querySelector<HTMLInputElement>('[data-overlay]'); if (cb) cb.checked = this.showOverlay; this.host.view.schedule(); return true; }
    if (combo === '[' || combo === ']') { this.brush.size = Math.max(0.002, Math.min(0.3, this.brush.size * (combo === ']' ? 1.15 : 1 / 1.15))); this.host.view.draw(); return true; }
    if ((combo === 'Backspace' || combo === 'Delete') && this.current().m) {
      const { masks, m } = this.current();
      if (m && m.components.length > 1) { m.components.splice(this.comp, 1); this.comp = 0; } else masks.splice(this.sel, 1);
      this.sel = Math.min(this.sel, masks.length - 1);
      this.write(masks, 'end', 'Delete Mask');
      return true;
    }
    if (combo === 'Escape') { this.host.done(); return true; }
    return false;
  }

  draw(c: CanvasRenderingContext2D, view: DevelopView): void {
    const { m, c: comp } = this.current();
    c.save();
    c.shadowColor = 'rgba(0,0,0,0.6)';
    c.shadowBlur = 3;
    c.strokeStyle = 'rgba(255,255,255,0.92)';
    c.fillStyle = '#fff';
    if (m && comp) {
      const s = comp.shape;
      if (s.kind === 'linear') {
        const a = this.stage(s.start as Vec), b = this.stage(s.end as Vec);
        const dx = b[0] - a[0], dy = b[1] - a[1];
        const len = Math.max(1, Math.hypot(dx, dy));
        const nx = -dy / len * 2000, ny = dx / len * 2000;
        for (const [p, dash] of [[a, []], [b, [5, 4]]] as Array<[[number, number], number[]]>) {
          c.setLineDash(dash);
          c.beginPath(); c.moveTo(p[0] - nx, p[1] - ny); c.lineTo(p[0] + nx, p[1] + ny); c.stroke();
        }
        c.setLineDash([]);
        for (const p of [a, b]) { c.beginPath(); c.arc(p[0], p[1], 5, 0, Math.PI * 2); c.fill(); }
      }
      if (s.kind === 'radial') {
        const ctr = this.stage(s.center as Vec);
        const k = view.pxPerLong();
        const rx = Number(s.rx) * k, ry = Number(s.ry) * k;
        c.beginPath(); c.ellipse(ctr[0], ctr[1], rx, ry, 0, 0, Math.PI * 2); c.stroke();
        const f = 1 - Math.max(0.01, Number(s.feather ?? 50) / 100);
        c.setLineDash([4, 4]);
        c.beginPath(); c.ellipse(ctr[0], ctr[1], rx * f, ry * f, 0, 0, Math.PI * 2); c.stroke();
        c.setLineDash([]);
        for (const [x, y] of [[ctr[0], ctr[1]], [ctr[0] + rx, ctr[1]], [ctr[0] - rx, ctr[1]], [ctr[0], ctr[1] + ry], [ctr[0], ctr[1] - ry]]) { c.beginPath(); c.arc(x, y, 4, 0, Math.PI * 2); c.fill(); }
      }
    }
    if (this.box) {
      c.setLineDash([5, 4]);
      c.strokeRect(Math.min(this.box.a.sx, this.box.b.sx), Math.min(this.box.a.sy, this.box.b.sy), Math.abs(this.box.b.sx - this.box.a.sx), Math.abs(this.box.b.sy - this.box.a.sy));
      c.setLineDash([]);
    }
    if (comp?.shape.kind === 'brush' && this.hoverPt) {
      const r = this.brush.size * view.pxPerLong();
      const hard = r * (1 - this.brush.feather / 100);
      c.beginPath(); c.arc(this.hoverPt.sx, this.hoverPt.sy, r, 0, Math.PI * 2); c.stroke();
      c.setLineDash([3, 3]);
      c.beginPath(); c.arc(this.hoverPt.sx, this.hoverPt.sy, Math.max(1, hard), 0, Math.PI * 2); c.stroke();
      c.setLineDash([]);
    }
    c.restore();
    if (this.edgeEd && this.edgeEd.key === this.edgeKey()) this.drawEdge(c);
    setClass(this.root, 'has-mask', !!m);
  }
}
