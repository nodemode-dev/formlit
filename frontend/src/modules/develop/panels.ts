import type { Ctx } from '../../app';
import { develop, getPath, type Profile } from '../../state/develop';
import { el, q, setClass, setHidden, setText, setValue } from '../../ui/dom';
import { Histogram } from '../../ui/histogram';
import { icon } from '../../ui/icons';
import { Panel } from '../../ui/panel';
import { Slider } from '../../ui/slider';
import { CurveEditor } from './curve';
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
    profRow.appendChild(this.profileSel);
    this.wbSel = el<HTMLSelectElement>('<select class="cv-select fl-grow"></select>');
    for (const p of develop.doc?.wbPresets ?? []) this.wbSel.add(new Option(p.label, p.id));
    this.wbSel.addEventListener('change', () => this.setWbMode(this.wbSel.value));
    const picker = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" data-cmd="develop.wbPicker" aria-label="White Balance Selector (W)">${icon('eyeDropper', 15)}</button>`);
    const wbRow = el('<div class="fl-row"><span class="fl-row-label">WB</span></div>');
    wbRow.append(this.wbSel, picker);
    const auto = el(`<div class="fl-row fl-row-end"><span class="fl-sub-inline">Tone</span><button class="cv-btn fl-btn-sm" type="button" data-cmd="develop.auto">Auto</button></div>`);
    pBasic.body.append(this.treat, profRow, s('profile.amount'), el('<div class="fl-sub">White Balance</div>'), wbRow, s('wb.temp'), s('wb.tint'), auto,
      s('light.exposure'), s('light.contrast'), s('light.highlights'), s('light.shadows'), s('light.whites'), s('light.blacks'),
      el('<div class="fl-sub">Presence</div>'), s('effects.texture'), s('effects.clarity'), s('effects.dehaze'), s('color.vibrance'), s('color.saturation'));

    const pCurve = this.panel('dev.curve', 'Tone Curve', 'curve');
    this.curve = new CurveEditor();
    const curveSliders = el('<div class="fl-curve-sliders"></div>');
    curveSliders.append(s('curve.highlights'), s('curve.lights'), s('curve.darks'), s('curve.shadows'), s('curve.splitShadows'), s('curve.splitMid'), s('curve.splitHighlights'));
    pCurve.body.append(this.curve.root, curveSliders, s('curve.refineSaturation'));

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
    pMixer.body.append(this.mixerTabs, this.mixerBody, this.bwBody);

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
    pOptics.body.append(el('<div class="fl-sub">Profile</div>'), s('optics.profileDistortion'), s('optics.profileVignetting'), el('<div class="fl-sub">Manual</div>'), s('optics.distortion'), s('optics.vignetting'), s('optics.vignettingMidpoint'),
      el('<div class="fl-sub">Chromatic Aberration</div>'), s('optics.caRed'), s('optics.caBlue'), el('<div class="fl-sub">Defringe</div>'), s('optics.defringePurple'), s('optics.defringePurpleHueLo'), s('optics.defringePurpleHueHi'),
      s('optics.defringeGreen'), s('optics.defringeGreenHueLo'), s('optics.defringeGreenHueHi'));

    const pGeo = this.panel('dev.geometry', 'Transform', 'geometry');
    const upright = el(`<div class="fl-row"><span class="fl-row-label">Upright</span><div class="cv-seg fl-seg-sm fl-grow">${['off', 'auto', 'level', 'vertical', 'full'].map((m) => `<button type="button" data-up="${m}">${m === 'off' ? 'Off' : m.charAt(0).toUpperCase() + m.slice(1)}</button>`).join('')}</div></div>`);
    upright.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-up]');
      if (b) void this.upright(b.dataset.up as string);
    });
    const constrain = el(`<label class="fl-check"><input type="checkbox" data-constrain> Constrain Crop</label>`);
    q<HTMLInputElement>(constrain, 'input').addEventListener('change', (e) => develop.patch('geometry.constrainCrop', (e.target as HTMLInputElement).checked || null, 'end', 'Constrain Crop'));
    pGeo.body.append(upright, s('geometry.vertical'), s('geometry.horizontal'), s('geometry.rotate'), s('geometry.aspect'), s('geometry.scale'), s('geometry.offsetX', 'X Offset'), s('geometry.offsetY', 'Y Offset'), constrain);

    const pFx = this.panel('dev.effects', 'Effects', 'effects');
    const style = el<HTMLSelectElement>('<select class="cv-select fl-grow"><option value="highlightPriority">Highlight Priority</option><option value="colorPriority">Color Priority</option><option value="paint">Paint Overlay</option></select>');
    style.addEventListener('change', () => develop.patch('vignette.style', style.value === 'highlightPriority' ? null : style.value, 'end', 'Vignette Style'));
    style.dataset.path = 'vignette.style';
    const styleRow = el('<div class="fl-row"><span class="fl-row-label">Style</span></div>');
    styleRow.appendChild(style);
    pFx.body.append(el('<div class="fl-sub">Post-Crop Vignetting</div>'), styleRow, s('vignette.amount', 'Amount'), s('vignette.midpoint'), s('vignette.roundness'), s('vignette.feather'), s('vignette.highlights'),
      el('<div class="fl-sub">Grain</div>'), s('grain.amount', 'Amount'), s('grain.size'), s('grain.roughness'));

    const pBlur = this.panel('dev.lensBlur', 'Lens Blur', 'lensBlur', false);
    pBlur.body.append(el(`<div class="fl-row fl-row-end"><span class="fl-muted fl-grow">Uses a depth map made on this computer.</span><button class="cv-btn fl-btn-sm" type="button" data-cmd="develop.lensBlurDepth">${icon('aiSpark', 13)} Build Depth</button></div>`), s('lensBlur.amount', 'Blur Amount'), s('lensBlur.focalDistance'), s('lensBlur.focalRange'), s('lensBlur.bokeh'));

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
