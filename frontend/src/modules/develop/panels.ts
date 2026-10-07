import type { Ctx } from '../../app';
import { develop, getPath, type Profile } from '../../state/develop';
import { el, q, setClass, setHidden, setText, setValue } from '../../ui/dom';
import { Histogram } from '../../ui/histogram';
import { icon } from '../../ui/icons';
import { Panel } from '../../ui/panel';
import { Slider } from '../../ui/slider';
import { whenDone } from '../shared/tasks';
import { CurveEditor } from './curve';
import { HdrSection } from './hdr';
import type { DevelopView } from './view';
import { ColorWheel } from './wheel';

const BANDS = ['red', 'orange', 'yellow', 'green', 'aqua', 'blue', 'purple', 'magenta'];

export class SliderSet {
  readonly sliders = new Map<string, Slider>();
  constructor(private readonly view: DevelopView) {}

  make(cid: string, label?: string): HTMLElement {
    const spec = develop.specs.get(cid);
    if (!spec) return el('<div></div>');
    const s = new Slider({ ...spec, label: label ?? spec.label }, {
      input: (id, v, phase) => {
        this.view.setDragging(phase === 'drag');
        develop.set(id, v, phase);
      },
    });
    this.sliders.set(cid, s);
    return s.root;
  }

  sync(): void { for (const [cid, s] of this.sliders) s.set(develop.value(cid)); }
}

export class DevelopPanels {
  readonly histogram: Histogram;
  private readonly sliders: SliderSet;
  private readonly panels: Panel[] = [];
  private readonly profileSel: HTMLSelectElement;
  private readonly wbSel: HTMLSelectElement;
  private readonly treat: HTMLElement;
  private readonly curve: CurveEditor;
  private readonly wheels: ColorWheel[] = [];
  private readonly mixerTabs: HTMLElement;
  private readonly mixerBody: HTMLElement;
  private readonly bwBody: HTMLElement;
  private readonly histInfo: HTMLElement;
  private mixerMode = 'hue';
  private profiles: Profile[] = [];

  constructor(private readonly ctx: Ctx, host: HTMLElement, private readonly view: DevelopView, toolstrip: HTMLElement) {
    this.sliders = new SliderSet(view);
    const s = (cid: string, label?: string) => this.sliders.make(cid, label);

    const pHist = new Panel('dev.histogram', 'Histogram');
    this.histogram = new Histogram('fl-dev-hist');
    const clipL = el(`<button class="fl-clip fl-clip-l" type="button" data-cmd="develop.clipping" title="Show Clipping (J)">${icon('clipShadows', 12)}</button>`);
    const clipR = el(`<button class="fl-clip fl-clip-r" type="button" data-cmd="develop.clipping" title="Show Clipping (J)">${icon('clipHighlights', 12)}</button>`);
    this.histogram.root.append(clipL, clipR);
    this.histDrag();
    this.histInfo = el('<div class="fl-hist-info"></div>');
    pHist.body.append(this.histogram.root, this.histInfo, toolstrip);

    const pBasic = new Panel('dev.basic', 'Basic');
    this.treat = el(`<div class="fl-row"><span class="fl-row-label">Treatment</span><div class="cv-seg fl-seg-sm"><button type="button" data-t="color">Color</button><button type="button" data-t="bw">Black &amp; White</button></div></div>`);
    this.treat.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-t]');
      if (b) develop.patch('treatment', b.dataset.t === 'bw' ? 'bw' : null, 'end', b.dataset.t === 'bw' ? 'Black & White' : 'Color');
    });
    this.profileSel = el<HTMLSelectElement>('<select class="cv-select fl-grow"></select>');
    this.profileSel.addEventListener('change', () => develop.patch('profile', { id: this.profileSel.value, amount: develop.value('profile.amount') }, 'end', `Profile: ${this.profileSel.selectedOptions[0]?.text ?? ''}`));
    const profRow = el('<div class="fl-row"><span class="fl-row-label">Profile</span></div>');
    profRow.append(this.profileSel, el(`<button class="cv-icon-btn" type="button" data-cmd="develop.profileBrowser" aria-label="Profile Browser">${icon('viewGridLit', 15)}</button>`));
    this.wbSel = el<HTMLSelectElement>('<select class="cv-select fl-grow"></select>');
    for (const p of develop.doc?.wbPresets ?? []) this.wbSel.add(new Option(p.label, p.id));
    this.wbSel.addEventListener('change', () => this.setWbMode(this.wbSel.value));
    const picker = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" data-cmd="develop.wbPicker" aria-label="White Balance Selector (W)">${icon('eyeDropper', 15)}</button>`);
    const wbRow = el('<div class="fl-row"><span class="fl-row-label">WB</span></div>');
    wbRow.append(this.wbSel, picker);
    const auto = el(`<div class="fl-row fl-row-end"><span class="fl-sub-inline">Tone</span><button class="cv-btn fl-btn-sm" type="button" data-cmd="develop.auto">Auto</button></div>`);
    pBasic.body.append(this.treat, new HdrSection(this.view).root, profRow, s('profile.amount'), el('<div class="fl-sub">White Balance</div>'), wbRow, s('wb.temp'), s('wb.tint'), auto,
      s('light.exposure'), s('light.contrast'), s('light.highlights'), s('light.shadows'), s('light.whites'), s('light.blacks'),
      el('<div class="fl-sub">Presence</div>'), s('effects.texture'), s('effects.clarity'), s('effects.dehaze'), s('color.vibrance'), s('color.saturation'));

    const pCurve = this.panel('dev.curve', 'Tone Curve', 'curve');
    this.curve = new CurveEditor();
    const curveSliders = el('<div class="fl-curve-sliders"></div>');
    curveSliders.append(s('curve.highlights'), s('curve.lights'), s('curve.darks'), s('curve.shadows'), s('curve.splitShadows'), s('curve.splitMid'), s('curve.splitHighlights'));
    pCurve.body.append(this.curve.root, curveSliders, s('curve.refineSaturation'), el(`<div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm" type="button" data-cmd="develop.tat.curve">${icon('targeted', 13)} Targeted Adjustment</button></div>`));

    const pMixer = this.panel('dev.mixer', 'Color Mixer', 'mixer');
    this.mixerTabs = el(`<div class="cv-seg fl-seg-sm fl-mixer-tabs"><button type="button" data-m="hue">Hue</button><button type="button" data-m="sat">Saturation</button><button type="button" data-m="lum">Luminance</button><button type="button" data-m="all">All</button></div>`);
    this.mixerBody = el('<div class="fl-mixer"></div>');
    for (const b of BANDS) for (const k of ['hue', 'sat', 'lum']) {
      const node = s(`mixer.${b}.${k}`, b.charAt(0).toUpperCase() + b.slice(1));
      node.dataset.kind = k;
      this.mixerBody.appendChild(node);
    }
    this.bwBody = el('<div class="fl-mixer fl-bw"><div class="fl-row fl-row-end"><span class="fl-sub-inline">B&amp;W Mix</span><button class="cv-btn fl-btn-sm" type="button" data-cmd="develop.autoBw">Auto</button></div></div>');
    for (const b of BANDS) this.bwBody.appendChild(s(`bw.${b}`, b.charAt(0).toUpperCase() + b.slice(1)));
    this.mixerTabs.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-m]');
      if (b) { this.mixerMode = b.dataset.m as string; this.syncMixer(); }
    });
    const tatMixer = el<HTMLButtonElement>(`<button class="cv-btn fl-btn-sm" type="button">${icon('targeted', 13)} Targeted</button>`);
    tatMixer.addEventListener('click', () => this.ctx.run(develop.settings.treatment === 'bw' ? 'develop.tat.bw' : `develop.tat.${this.mixerMode === 'all' ? 'hue' : this.mixerMode}`));
    const mixerFoot = el('<div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm" type="button" data-cmd="develop.pointColor">Point Color...</button></div>');
    mixerFoot.prepend(tatMixer);
    pMixer.body.append(this.mixerTabs, this.mixerBody, this.bwBody, mixerFoot);

    const pGrade = this.panel('dev.grading', 'Color Grading', 'grading');
    const wheelRow = el('<div class="fl-wheels"></div>');
    const big = new ColorWheel('midtones', 'Midtones', 112);
    for (const [k, label] of [['shadows', 'Shadows'], ['highlights', 'Highlights']] as Array<[string, string]>) {
      const w = new ColorWheel(k, label, 100);
      this.wheels.push(w);
      wheelRow.appendChild(w.root);
    }
    const global = new ColorWheel('global', 'Global', 100);
    this.wheels.push(big, global);
    const row2 = el('<div class="fl-wheels"></div>');
    row2.append(big.root, global.root);
    pGrade.body.append(wheelRow, row2, s('grading.shadows.lum', 'Shadows Luminance'), s('grading.midtones.lum', 'Midtones Luminance'), s('grading.highlights.lum', 'Highlights Luminance'), s('grading.global.lum', 'Global Luminance'), s('grading.blending'), s('grading.balance'));

    const pDetail = this.panel('dev.detail', 'Detail', 'detail');
    pDetail.body.append(el('<div class="fl-sub">Sharpening</div>'), s('detail.sharpenAmount', 'Amount'), s('detail.sharpenRadius'), s('detail.sharpenDetail'), s('detail.sharpenMasking'),
      el('<div class="fl-sub">Noise Reduction</div>'), s('detail.nrLuminance', 'Luminance'), s('detail.nrDetail'), s('detail.nrContrast'), s('detail.nrColor', 'Color'), s('detail.nrColorDetail'), s('detail.nrColorSmoothness'),
      el(`<div class="fl-row fl-row-end"><span class="fl-muted fl-grow">Zoom to 1:1 (Z) to judge sharpening and noise.</span><button class="cv-btn fl-btn-sm" type="button" data-cmd="develop.aiDenoise">${icon('aiSpark', 13)} Denoise...</button></div>`));

    const pOptics = this.panel('dev.optics', 'Lens Corrections', 'optics');
    const lensRow = el('<div class="fl-row"><label class="fl-check-sm fl-lens-check"><input type="checkbox"> Enable Profile Corrections</label><span class="fl-muted fl-grow fl-lens-note"></span></div>');
    const lensBox = q<HTMLInputElement>(lensRow, 'input');
    lensBox.addEventListener('change', () => {
      const id = develop.id;
      if (id === null) return;
      void develop.flush().then(() => this.ctx.api.cmd<{ noProfile: number[] }>('develop.lensProfile', { ids: [id], enable: lensBox.checked })).then((r) => {
        if (r.noProfile.length) { lensBox.checked = false; setText(q(lensRow, '.fl-lens-note'), 'No lens profile is embedded in this file'); }
        return develop.reload('photo');
      }, (err) => this.ctx.fail(err));
    });
    const pick = el('<div class="fl-lens-pick"><div class="fl-row"><span class="fl-row-label">Make</span><select class="cv-select fl-grow" data-lens="maker"></select></div><div class="fl-row"><span class="fl-row-label">Model</span><select class="cv-select fl-grow" data-lens="model"></select></div><div class="fl-muted fl-lens-attr"></div></div>');
    const makerSel = q<HTMLSelectElement>(pick, '[data-lens="maker"]');
    const modelSel = q<HTMLSelectElement>(pick, '[data-lens="model"]');
    const dbRow = el('<div class="fl-row fl-row-end"><span class="fl-muted fl-grow">No lens profile database yet.</span><button class="cv-btn fl-btn-sm" type="button">Download Lens Profiles</button></div>');
    setHidden(pick, true);
    setHidden(dbRow, true);
    const fillModels = async (maker: string, chosen: string | null): Promise<void> => {
      const r = await this.ctx.api.cmd<{ models: string[] }>('lens.models', { maker }).catch(() => ({ models: [] as string[] }));
      modelSel.replaceChildren(new Option('Choose a lens...', ''), ...r.models.map((m) => new Option(m, m)));
      modelSel.value = chosen && r.models.includes(chosen) ? chosen : '';
    };
    makerSel.addEventListener('change', () => void fillModels(makerSel.value, null));
    modelSel.addEventListener('change', () => {
      const id = develop.id;
      if (id === null || !modelSel.value) return;
      void develop.flush().then(() => this.ctx.api.cmd('develop.lensProfile', { ids: [id], enable: true, lens: modelSel.value })).then(() => develop.reload('photo'), (err) => this.ctx.fail(err));
    });
    dbRow.querySelector('button')?.addEventListener('click', () => {
      setText(q(dbRow, 'span'), 'Downloading...');
      void this.ctx.api.cmd<{ task: number }>('lens.database', { download: true }).then((r) => whenDone(r.task)).then(() => { lensFor = null; setHidden(dbRow, true); develop.reload('photo'); }, (err) => { setText(q(dbRow, 'span'), 'Download failed'); this.ctx.fail(err); });
    });
    let lensFor: number | null = null;
    let makersLoaded = false;
    develop.listen((why) => {
      if (why === 'drag') return;
      const prof = ((develop.settings.optics as Record<string, unknown> | undefined)?.profile as { enabled?: boolean; lensfun?: { lens?: string; maker?: string } } | undefined);
      if (lensBox.checked !== !!prof?.enabled) lensBox.checked = !!prof?.enabled;
      if (develop.id !== null && develop.id !== lensFor) {
        lensFor = develop.id;
        void this.ctx.api.cmd<{ available: boolean; source: string | null; database: boolean; lens: string | null; maker: string | null; guess: { maker: string; model: string } | null }>('develop.lensProfileInfo', { id: develop.id }).then(async (r) => {
          const using = r.lens ? `${r.lens} (Lensfun)` : r.source === 'DNG opcodes' ? 'Built in (DNG opcodes)' : r.guess ? `${r.guess.model} (Lensfun)` : 'No profile found; choose the lens';
          setText(q(lensRow, '.fl-lens-note'), using);
          lensBox.disabled = !r.available && !prof?.enabled;
          setHidden(dbRow, r.database || r.source === 'DNG opcodes');
          setHidden(pick, !r.database || r.source === 'DNG opcodes');
          setText(q(pick, '.fl-lens-attr'), r.database ? 'Lens data from the Lensfun database, CC BY-SA 3.0' : '');
          if (r.database && r.source !== 'DNG opcodes') {
            if (!makersLoaded) {
              const m = await this.ctx.api.cmd<{ makers: string[] }>('lens.makers').catch(() => ({ makers: [] as string[] }));
              makerSel.replaceChildren(new Option('Make...', ''), ...m.makers.map((x) => new Option(x, x)));
              makersLoaded = true;
            }
            const maker = r.maker ?? r.guess?.maker ?? '';
            makerSel.value = maker;
            if (maker) await fillModels(maker, r.lens ?? r.guess?.model ?? null);
            else modelSel.replaceChildren(new Option('Choose a make first', ''));
          }
        }, () => undefined);
      }
    });
    const caRow = el('<div class="fl-row"><label class="fl-check-sm"><input type="checkbox"> Remove Chromatic Aberration</label><span class="fl-muted fl-grow fl-ca-note"></span></div>');
    const caBox = q<HTMLInputElement>(caRow, 'input');
    caBox.addEventListener('change', () => {
      const id = develop.id;
      if (id === null) return;
      const on = caBox.checked;
      setText(q(caRow, '.fl-ca-note'), on ? 'Measuring...' : '');
      const done = (vals: { autoCaRed: number; autoCaBlue: number }) => {
        if (develop.id !== id) return;
        const opt = { ...((develop.settings.optics as Record<string, unknown> | undefined) ?? {}), removeCa: on, ...vals };
        develop.patch('optics', opt, 'end', on ? 'Remove Chromatic Aberration' : 'Keep Chromatic Aberration');
        setText(q(caRow, '.fl-ca-note'), on && !vals.autoCaRed && !vals.autoCaBlue ? 'None found' : '');
      };
      if (!on) { done({ autoCaRed: 0, autoCaBlue: 0 }); return; }
      void this.ctx.api.cmd<{ autoCaRed: number; autoCaBlue: number }>('develop.autoCa', { id }).then(done, (err) => { caBox.checked = false; setText(q(caRow, '.fl-ca-note'), ''); this.ctx.fail(err); });
    });
    develop.listen((why) => {
      if (why === 'drag') return;
      const on = !!(develop.settings.optics as Record<string, unknown> | undefined)?.removeCa;
      if (caBox.checked !== on) caBox.checked = on;
    });
    const fringeHead = el(`<div class="fl-row"><span class="fl-sub-inline fl-grow">Defringe</span><button class="cv-icon-btn" type="button" data-cmd="develop.fringePicker" aria-label="Fringe Color Selector">${icon('eyeDropper', 14)}</button></div>`);
    pOptics.body.append(el('<div class="fl-sub">Profile</div>'), lensRow, pick, dbRow, s('optics.profileDistortion'), s('optics.profileVignetting'), el('<div class="fl-sub">Manual</div>'), s('optics.distortion'), s('optics.vignetting'), s('optics.vignettingMidpoint'),
      el('<div class="fl-sub">Chromatic Aberration</div>'), caRow, s('optics.caRed'), s('optics.caBlue'), fringeHead, s('optics.defringePurple'), s('optics.defringePurpleHueLo'), s('optics.defringePurpleHueHi'),
      s('optics.defringeGreen'), s('optics.defringeGreenHueLo'), s('optics.defringeGreenHueHi'));

    const pGeo = this.panel('dev.geometry', 'Transform', 'geometry');
    const upright = el(`<div class="fl-row"><span class="fl-row-label">Upright</span><div class="cv-seg fl-seg-sm fl-grow">${['off', 'auto', 'guided', 'level', 'vertical', 'full'].map((m) => `<button type="button" data-up="${m}">${m === 'off' ? 'Off' : m.charAt(0).toUpperCase() + m.slice(1)}</button>`).join('')}</div></div>`);
    upright.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-up]');
      if (b?.dataset.up === 'guided') this.ctx.run('develop.tool.guided');
      else if (b) void this.upright(b.dataset.up as string);
    });
    const constrain = el(`<label class="fl-check"><input type="checkbox" data-constrain> Constrain Crop</label>`);
    q<HTMLInputElement>(constrain, 'input').addEventListener('change', (e) => develop.patch('geometry.constrainCrop', (e.target as HTMLInputElement).checked || null, 'end', 'Constrain Crop'));
    const gridRow = el('<label class="fl-check"><input type="checkbox"> Show Grid</label>');
    q<HTMLInputElement>(gridRow, 'input').addEventListener('change', (e) => this.view.setGrid((e.target as HTMLInputElement).checked ? 8 : 0));
    pGeo.body.append(upright, s('geometry.vertical'), s('geometry.horizontal'), s('geometry.rotate'), s('geometry.aspect'), s('geometry.scale'), s('geometry.offsetX', 'X Offset'), s('geometry.offsetY', 'Y Offset'), constrain, gridRow);

    const pFx = this.panel('dev.effects', 'Effects', 'effects');
    const style = el<HTMLSelectElement>('<select class="cv-select fl-grow"><option value="highlightPriority">Highlight Priority</option><option value="colorPriority">Color Priority</option><option value="paintOverlay">Paint Overlay</option></select>');
    style.addEventListener('change', () => develop.patch('vignette.style', style.value === 'highlightPriority' ? null : style.value, 'end', 'Vignette Style'));
    style.dataset.path = 'vignette.style';
    const styleRow = el('<div class="fl-row"><span class="fl-row-label">Style</span></div>');
    styleRow.appendChild(style);
    pFx.body.append(el('<div class="fl-sub">Post-Crop Vignetting</div>'), styleRow, s('vignette.amount', 'Amount'), s('vignette.midpoint'), s('vignette.roundness'), s('vignette.feather'), s('vignette.highlights'),
      el('<div class="fl-sub">Grain</div>'), s('grain.amount', 'Amount'), s('grain.size'), s('grain.roughness'));

    const pBlur = this.panel('dev.lensBlur', 'Lens Blur', 'lensBlur', false);
    const shapeRow = el(`<div class="fl-row"><span class="fl-row-label">Bokeh</span><select class="cv-select fl-grow" data-lb-shape aria-label="Bokeh shape"><option value="circle">Circle</option><option value="bubble">Bubble</option><option value="blade5">5-Blade</option><option value="ring">Ring</option><option value="cateye">Cat Eye</option></select></div>`);
    const shapeSel = q<HTMLSelectElement>(shapeRow, 'select');
    shapeSel.addEventListener('change', () => develop.patch('lensBlur', { ...((develop.settings.lensBlur as Record<string, unknown> | undefined) ?? {}), shape: shapeSel.value }, 'end', 'Bokeh Shape'));
    develop.listen(() => setValue(shapeSel, String(((develop.settings.lensBlur as Record<string, unknown> | undefined) ?? {}).shape ?? 'circle')));
    pBlur.body.append(el(`<div class="fl-row fl-row-end"><span class="fl-muted fl-grow">Uses a depth map made on this computer.</span><button class="cv-btn fl-btn-sm" type="button" data-cmd="develop.lensBlurDepth">${icon('aiSpark', 13)} Build Depth</button></div>`), s('lensBlur.amount', 'Blur Amount'), shapeRow, s('lensBlur.focalDistance'), s('lensBlur.focalRange'), s('lensBlur.bokeh'),
      el(`<div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm" type="button" data-cmd="develop.visualizeDepth">Visualize Depth</button><button class="cv-btn fl-btn-sm" type="button" data-cmd="develop.lensBlurRefine">${icon('eyeDropper', 13)} Focus and Refine</button></div>`));

    const pCal = this.panel('dev.calibration', 'Calibration', 'calibration', false);
    pCal.body.append(s('calibration.shadowsTint', 'Shadows Tint'), el('<div class="fl-sub">Red Primary</div>'), s('calibration.redHue', 'Hue'), s('calibration.redSat', 'Saturation'),
      el('<div class="fl-sub">Green Primary</div>'), s('calibration.greenHue', 'Hue'), s('calibration.greenSat', 'Saturation'), el('<div class="fl-sub">Blue Primary</div>'), s('calibration.blueHue', 'Hue'), s('calibration.blueSat', 'Saturation'));

    host.append(pHist.root, pBasic.root, ...this.panels.map((p) => p.root));
    develop.listen((why) => { if (why !== 'drag') this.sync(); else this.syncLight(); });
  }

  private panel(id: string, title: string, section: string, open = true): Panel {
    const p = new Panel(id, title, { open, toggle: { on: () => !develop.isDisabled(section), set: () => develop.toggleSection(section), title: `Turn ${title} on or off` } });
    this.panels.push(p);
    return p;
  }

  private setWbMode(mode: string): void {
    const preset = develop.doc?.wbPresets.find((p) => p.id === mode);
    if (mode === 'custom') { develop.set('wb.temp', develop.value('wb.temp'), 'end', 'White Balance: Custom'); return; }
    const wb: Record<string, unknown> = { mode };
    if (preset?.temp) { wb.temp = preset.temp; wb.tint = preset.tint; }
    develop.patch('wb', mode === 'asShot' ? null : wb, 'end', `White Balance: ${preset?.label ?? mode}`);
    void develop.refreshInfo();
  }

  private histDrag(): void {
    const regions: Array<[number, number, string, string]> = [[0, 0.07, 'light.blacks', 'Blacks'], [0.07, 0.3, 'light.shadows', 'Shadows'], [0.3, 0.7, 'light.exposure', 'Exposure'], [0.7, 0.93, 'light.highlights', 'Highlights'], [0.93, 1.0001, 'light.whites', 'Whites']];
    const root = this.histogram.root;
    const band = el('<div class="fl-hist-band" hidden></div>');
    const tag = el('<div class="fl-hist-tag" hidden></div>');
    root.append(band, tag);
    let drag: { x0: number; v0: number; cid: string; label: string } | null = null;
    const at = (e: PointerEvent): [number, number, string, string] => {
      const r = root.getBoundingClientRect();
      const f = Math.min(0.9999, Math.max(0, (e.clientX - r.left) / Math.max(1, r.width)));
      return regions.find(([a, b]) => f >= a && f < b) ?? regions[2];
    };
    const show = (reg: [number, number, string, string] | null) => {
      setHidden(band, !reg);
      setHidden(tag, !reg);
      if (!reg) return;
      band.style.left = `${reg[0] * 100}%`;
      band.style.width = `${(Math.min(1, reg[1]) - reg[0]) * 100}%`;
      const spec = develop.specs.get(reg[2]);
      const v = develop.value(reg[2]);
      setText(tag, `${reg[3]} ${spec ? (v > 0 ? '+' : '') + v.toFixed(spec.decimals) : ''}`);
    };
    root.addEventListener('pointermove', (e) => {
      if ((e.target as HTMLElement).closest('.fl-clip')) { show(null); return; }
      if (!drag) { show(at(e)); return; }
      const spec = develop.specs.get(drag.cid);
      if (!spec) return;
      const r = root.getBoundingClientRect();
      const raw = drag.v0 + ((e.clientX - drag.x0) / Math.max(1, r.width)) * (spec.max - spec.min) * 0.5;
      const v = Math.min(spec.max, Math.max(spec.min, Math.round(raw / spec.step) * spec.step));
      develop.patch(drag.cid, Number(v.toFixed(spec.decimals)), 'drag', drag.label);
      setText(tag, `${drag.label} ${v > 0 ? '+' : ''}${v.toFixed(spec.decimals)}`);
    });
    root.addEventListener('pointerdown', (e) => {
      if (e.button !== 0 || develop.id === null || (e.target as HTMLElement).closest('.fl-clip')) return;
      const reg = at(e);
      drag = { x0: e.clientX, v0: develop.value(reg[2]), cid: reg[2], label: reg[3] };
      root.setPointerCapture(e.pointerId);
      show(reg);
    });
    root.addEventListener('pointerup', () => {
      if (!drag) return;
      const d = drag;
      drag = null;
      develop.patch(d.cid, develop.value(d.cid), 'end', d.label);
    });
    root.addEventListener('pointerleave', () => { if (!drag) show(null); });
  }

  private async upright(mode: string): Promise<void> {
    const id = develop.id;
    if (id === null) return;
    await develop.flush();
    try { await this.ctx.api.cmd('develop.upright', { ids: [id], mode }); } catch (err) { this.ctx.fail(err, 'Upright'); }
  }

  setProfiles(list: Profile[]): void {
    const key = list.map((p) => p.id).join('|');
    if (key === this.profiles.map((p) => p.id).join('|')) return;
    this.profiles = list;
    this.profileSel.replaceChildren();
    const groups = new Map<string, Profile[]>();
    for (const p of list) { if (!groups.has(p.group)) groups.set(p.group, []); groups.get(p.group)?.push(p); }
    for (const [g, items] of groups) {
      const og = document.createElement('optgroup');
      og.label = g;
      for (const p of items) og.appendChild(new Option(p.name, p.id));
      this.profileSel.appendChild(og);
    }
  }

  setHistogramInfo(text: string): void { setText(this.histInfo, text); }

  private syncLight(): void { this.sliders.sync(); }

  private syncMixer(): void {
    const bw = develop.settings.treatment === 'bw';
    setHidden(this.mixerTabs, bw);
    setHidden(this.mixerBody, bw);
    setHidden(this.bwBody, !bw);
    for (const b of Array.from(this.mixerTabs.querySelectorAll<HTMLElement>('[data-m]'))) setClass(b, 'is-on', b.dataset.m === this.mixerMode);
    for (const n of Array.from(this.mixerBody.children) as HTMLElement[]) {
      const k = n.dataset.kind;
      setHidden(n, this.mixerMode !== 'all' && k !== this.mixerMode);
      setClass(n, 'is-all', this.mixerMode === 'all');
    }
  }

  sync(): void {
    if (develop.info) this.setProfiles(develop.info.profiles.filter((p) => !p.raw || develop.info?.raw));
    this.sliders.sync();
    const bw = develop.settings.treatment === 'bw';
    for (const b of Array.from(this.treat.querySelectorAll<HTMLElement>('[data-t]'))) setClass(b, 'is-on', (b.dataset.t === 'bw') === bw);
    setValue(this.profileSel, String((getPath(develop.settings, 'profile.id') as string | undefined) ?? 'fl.color'));
    setValue(this.wbSel, develop.wbMode());
    for (const p of this.panels) p.sync();
    this.curve.sync();
    for (const w of this.wheels) w.sync();
    this.syncMixer();
    const style = this.ctx.shell.app.querySelector<HTMLSelectElement>('[data-path="vignette.style"]');
    if (style) setValue(style, String(getPath(develop.settings, 'vignette.style') ?? 'highlightPriority'));
    const cc = this.ctx.shell.app.querySelector<HTMLInputElement>('[data-constrain]');
    if (cc) cc.checked = !!getPath(develop.settings, 'geometry.constrainCrop');
    const up = String(getPath(develop.settings, 'geometry.upright') ?? 'off');
    for (const b of Array.from(this.ctx.shell.app.querySelectorAll<HTMLElement>('[data-up]'))) setClass(b, 'is-on', b.dataset.up === up);
  }

  curveHistogram(bins: Uint32Array): void { this.curve.setHistogram(bins); }
}
