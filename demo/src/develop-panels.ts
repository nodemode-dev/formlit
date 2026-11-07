import { CurveEditor } from '../../frontend/src/modules/develop/curve';
import { ColorWheel } from '../../frontend/src/modules/develop/wheel';
import { el, patchList, q, setClass, setHidden, setText, setValue } from '../../frontend/src/ui/dom';
import { Histogram, type Bins } from '../../frontend/src/ui/histogram';
import { icon } from '../../frontend/src/ui/icons';
import { Panel } from '../../frontend/src/ui/panel';
import { Slider, type SliderSpec } from '../../frontend/src/ui/slider';
import { BANDS, SPECS, get, sectionEnabled } from './engine/settings';
import { PRESETS, presetDev } from './presets';
import { develop } from './shims/develop';

const SHOT_TEMP = 6500;
const MIRED_STEP = 0.75;

export const toRelativeWb = (cid: string, v: number): number => cid === 'wb.tint'
  ? Math.round(Math.max(-100, Math.min(100, v)))
  : Math.round(Math.max(-100, Math.min(100, (1e6 / SHOT_TEMP - 1e6 / Math.max(1, v)) / MIRED_STEP)));

export const fromRelativeWb = (cid: string, r: number): number => cid === 'wb.tint' ? r : Math.round(1e6 / (1e6 / SHOT_TEMP - r * MIRED_STEP));

export interface PanelActions {
  tool(t: 'crop' | 'wb'): void;
  compare(): void;
  autoTone(): void;
  clipping(): void;
  isTool(t: 'crop' | 'wb'): boolean;
  isClipping(): boolean;
  compareOn(): boolean;
}

const cap = (s: string): string => s.charAt(0).toUpperCase() + s.slice(1);

export class DevelopPanels {
  readonly histogram = new Histogram('fl-dev-hist');
  private readonly sliders = new Map<string, Slider>();
  private readonly relative = new Map<string, Slider>();
  private readonly panels: Panel[] = [];
  private readonly wheels: ColorWheel[] = [];
  private readonly curve = new CurveEditor();
  private readonly treat: HTMLElement;
  private readonly histInfo: HTMLElement;
  private readonly clipL: HTMLElement;
  private readonly clipR: HTMLElement;
  private readonly mixerTabs: HTMLElement;
  private readonly mixerBody: HTMLElement;
  private readonly bwBody: HTMLElement;
  private readonly vigStyle: HTMLSelectElement;
  private readonly strip: HTMLElement;
  private mixerMode = 'hue';

  constructor(host: HTMLElement, private readonly act: PanelActions) {
    const s = (cid: string, label?: string): HTMLElement => this.make(cid, label);

    const pHist = new Panel('dev.histogram', 'Histogram');
    this.clipL = el(`<button class="fl-clip fl-clip-l" type="button" title="Show Clipping (J)">${icon('clipShadows', 12)}</button>`);
    this.clipR = el(`<button class="fl-clip fl-clip-r" type="button" title="Show Clipping (J)">${icon('clipHighlights', 12)}</button>`);
    this.clipL.addEventListener('click', () => act.clipping());
    this.clipR.addEventListener('click', () => act.clipping());
    this.histogram.root.append(this.clipL, this.clipR);
    this.histInfo = el('<div class="fl-hist-info"></div>');
    this.strip = el(`<div class="fl-toolstrip"><button class="cv-icon-btn" type="button" data-t="crop" title="Crop and Straighten (R)" aria-label="Crop and Straighten">${icon('crop', 16)}</button><button class="cv-icon-btn" type="button" data-t="wb" title="White Balance Selector (W)" aria-label="White Balance Selector">${icon('eyeDropper', 16)}</button><button class="cv-icon-btn" type="button" data-t="compare" title="Before and After (Y)" aria-label="Before and After">${icon('beforeAfter', 16)}</button><button class="cv-icon-btn" type="button" data-t="auto" title="Auto Tone (Shift+A)" aria-label="Auto Tone">${icon('sparkle', 16)}</button></div>`);
    this.strip.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-t]');
      if (!b) return;
      if (b.dataset.t === 'crop' || b.dataset.t === 'wb') act.tool(b.dataset.t);
      else if (b.dataset.t === 'compare') act.compare();
      else act.autoTone();
    });
    pHist.body.append(this.histogram.root, this.histInfo, this.strip);

    const pBasic = new Panel('dev.basic', 'Basic');
    this.treat = el(`<div class="fl-row"><span class="fl-row-label">Treatment</span><div class="cv-seg fl-seg-sm"><button type="button" data-t="color">Color</button><button type="button" data-t="bw">Black &amp; White</button></div></div>`);
    this.treat.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-t]');
      if (b) develop.patch('treatment', b.dataset.t === 'bw' ? 'bw' : null, 'end', b.dataset.t === 'bw' ? 'Black & White' : 'Color');
    });
    const wbRow = el(`<div class="fl-row"><span class="fl-row-label">WB</span><button class="cv-btn fl-btn-sm" type="button" data-w="shot">As Shot</button><button class="cv-btn fl-btn-sm" type="button" data-w="pick">${icon('eyeDropper', 13)} Pick</button></div>`);
    wbRow.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-w]');
      if (!b) return;
      if (b.dataset.w === 'shot') develop.patch('wb', null, 'end', 'White Balance: As Shot');
      else act.tool('wb');
    });
    pBasic.body.append(this.treat, el('<div class="fl-sub">White Balance</div>'), wbRow, this.makeWb('wb.temp'), this.makeWb('wb.tint'),
      el('<div class="fl-sub">Tone</div>'), s('light.exposure'), s('light.contrast'), s('light.highlights'), s('light.shadows'), s('light.whites'), s('light.blacks'),
      el('<div class="fl-sub">Presence</div>'), s('effects.texture'), s('effects.clarity'), s('effects.dehaze'), s('color.vibrance'), s('color.saturation'));

    const pCurve = this.section('dev.curve', 'Tone Curve', 'curve');
    const curveSliders = el('<div class="fl-curve-sliders"></div>');
    curveSliders.append(s('curve.highlights'), s('curve.lights'), s('curve.darks'), s('curve.shadows'), s('curve.splitShadows'), s('curve.splitMid'), s('curve.splitHighlights'));
    pCurve.body.append(this.curve.root, curveSliders, s('curve.refineSaturation'));

    const pMixer = this.section('dev.mixer', 'Color Mixer', 'mixer');
    this.mixerTabs = el(`<div class="cv-seg fl-seg-sm fl-mixer-tabs"><button type="button" data-m="hue">Hue</button><button type="button" data-m="sat">Saturation</button><button type="button" data-m="lum">Luminance</button><button type="button" data-m="all">All</button></div>`);
    this.mixerBody = el('<div class="fl-mixer"></div>');
    for (const b of BANDS) for (const k of ['hue', 'sat', 'lum']) {
      const node = s(`mixer.${b}.${k}`, cap(b));
      node.dataset.kind = k;
      this.mixerBody.appendChild(node);
    }
    this.bwBody = el('<div class="fl-mixer fl-bw"><div class="fl-row fl-row-end"><span class="fl-sub-inline">B&amp;W Mix</span></div></div>');
    for (const b of BANDS) this.bwBody.appendChild(s(`bw.${b}`, cap(b)));
    this.mixerTabs.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-m]');
      if (b) { this.mixerMode = b.dataset.m as string; this.syncMixer(); }
    });
    pMixer.body.append(this.mixerTabs, this.mixerBody, this.bwBody);

    const pGrade = this.section('dev.grading', 'Color Grading', 'grading');
    const row1 = el('<div class="fl-wheels"></div>');
    const row2 = el('<div class="fl-wheels"></div>');
    const wS = new ColorWheel('shadows', 'Shadows', 100), wH = new ColorWheel('highlights', 'Highlights', 100), wM = new ColorWheel('midtones', 'Midtones', 112), wG = new ColorWheel('global', 'Global', 100);
    this.wheels.push(wS, wH, wM, wG);
    row1.append(wS.root, wH.root);
    row2.append(wM.root, wG.root);
    pGrade.body.append(row1, row2, s('grading.shadows.lum', 'Shadow Luminance'), s('grading.midtones.lum', 'Midtone Luminance'), s('grading.highlights.lum', 'Highlight Luminance'), s('grading.global.lum', 'Global Luminance'), s('grading.blending'), s('grading.balance'));

    const pDetail = this.section('dev.detail', 'Detail', 'detail');
    pDetail.body.append(el('<div class="fl-sub">Sharpening</div>'), s('detail.sharpenAmount', 'Amount'), s('detail.sharpenRadius', 'Radius'), s('detail.sharpenDetail', 'Detail'), s('detail.sharpenMasking', 'Masking'));

    const pGeo = this.section('dev.geometry', 'Transform', 'geometry');
    pGeo.body.append(s('geometry.vertical'), s('geometry.horizontal'), s('geometry.rotate'), s('geometry.aspect'), s('geometry.scale'), s('geometry.offsetX'), s('geometry.offsetY'));

    const pFx = this.section('dev.effects', 'Effects', 'effects');
    this.vigStyle = el<HTMLSelectElement>('<select class="cv-select fl-grow"><option value="highlightPriority">Highlight Priority</option><option value="colorPriority">Color Priority</option><option value="paintOverlay">Paint Overlay</option></select>');
    this.vigStyle.addEventListener('change', () => develop.patch('vignette.style', this.vigStyle.value === 'highlightPriority' ? null : this.vigStyle.value, 'end', 'Vignette Style'));
    const styleRow = el('<div class="fl-row"><span class="fl-row-label">Style</span></div>');
    styleRow.appendChild(this.vigStyle);
    pFx.body.append(el('<div class="fl-sub">Post-Crop Vignetting</div>'), styleRow, s('vignette.amount', 'Amount'), s('vignette.midpoint', 'Midpoint'), s('vignette.roundness', 'Roundness'), s('vignette.feather', 'Feather'), s('vignette.highlights', 'Highlights'),
      el('<div class="fl-sub">Grain</div>'), s('grain.amount', 'Amount'), s('grain.size', 'Size'), s('grain.roughness', 'Roughness'));

    const pCal = this.section('dev.calibration', 'Calibration', 'calibration');
    pCal.body.append(s('calibration.shadowsTint'), s('calibration.redHue'), s('calibration.redSat'), s('calibration.greenHue'), s('calibration.greenSat'), s('calibration.blueHue'), s('calibration.blueSat'));

    host.append(pHist.root, pBasic.root, ...this.panels.map((p) => p.root));
    this.syncMixer();
  }

  private make(cid: string, label?: string): HTMLElement {
    const spec = SPECS.get(cid);
    if (!spec) return el('<div></div>');
    const s = new Slider({ ...spec, label: label ?? spec.label } as SliderSpec, { input: (id, v, phase) => develop.set(id, v, phase) });
    this.sliders.set(cid, s);
    return s.root;
  }

  private makeWb(cid: string): HTMLElement {
    const spec = SPECS.get(cid);
    if (!spec) return el('<div></div>');
    const apply = (v: number, phase: 'drag' | 'end'): void => {
      const t = cid === 'wb.temp' ? fromRelativeWb(cid, v) : get(develop.settings, 'wb.temp') || SHOT_TEMP;
      const tint = cid === 'wb.tint' ? fromRelativeWb(cid, v) : get(develop.settings, 'wb.tint');
      develop.patch('wb', { mode: 'custom', temp: t, tint }, phase, `${spec.label} ${v > 0 ? '+' : ''}${v}`);
    };
    const s = new Slider({ ...spec, min: -100, max: 100, default: 0, step: 1, decimals: 0 } as SliderSpec, {
      input: (_id, v, phase) => apply(v, phase),
      reset: () => apply(0, 'end'),
    });
    this.relative.set(cid, s);
    return s.root;
  }

  private section(id: string, title: string, key: string): Panel {
    const p = new Panel(id, title, {
      open: false,
      toggle: {
        on: () => sectionEnabled(develop.settings, key),
        set: (on) => {
          const list = new Set(((develop.read('disabled') as string[] | undefined) ?? []));
          if (on) list.delete(key); else list.add(key);
          develop.patch('disabled', list.size ? [...list] : null, 'end', `${title} ${on ? 'On' : 'Off'}`);
        },
        title: `Turn ${title} on or off`,
      },
    });
    this.panels.push(p);
    return p;
  }

  private syncMixer(): void {
    const bw = develop.settings.treatment === 'bw';
    setHidden(this.mixerBody, bw);
    setHidden(this.mixerTabs, bw);
    setHidden(this.bwBody, !bw);
    for (const b of Array.from(this.mixerTabs.querySelectorAll<HTMLElement>('[data-m]'))) setClass(b, 'is-on', b.dataset.m === this.mixerMode);
    for (const n of Array.from(this.mixerBody.children) as HTMLElement[]) {
      const show = this.mixerMode === 'all' || n.dataset.kind === this.mixerMode;
      setHidden(n, !show);
      setClass(n, 'is-all', this.mixerMode === 'all');
    }
  }

  sync(): void {
    const dev = develop.settings;
    for (const [cid, s] of this.sliders) s.set(get(dev, cid));
    for (const [cid, s] of this.relative) s.set(toRelativeWb(cid, get(dev, cid)));
    setClass(q(this.treat, '[data-t="color"]'), 'is-on', dev.treatment !== 'bw');
    setClass(q(this.treat, '[data-t="bw"]'), 'is-on', dev.treatment === 'bw');
    for (const w of this.wheels) w.sync();
    this.curve.sync();
    for (const p of this.panels) p.sync();
    this.syncMixer();
    setValue(this.vigStyle, String((dev.vignette as Record<string, unknown> | undefined)?.style ?? 'highlightPriority'));
    for (const b of Array.from(this.strip.querySelectorAll<HTMLElement>('[data-t]'))) {
      const t = b.dataset.t;
      setClass(b, 'is-active', t === 'crop' || t === 'wb' ? this.act.isTool(t) : t === 'compare' ? this.act.compareOn() : false);
    }
    setClass(this.clipL, 'is-on', this.act.isClipping());
    setClass(this.clipR, 'is-on', this.act.isClipping());
  }

  setBins(bins: Bins, clipS: number, clipH: number, w: number, h: number, ms: number): void {
    this.histogram.draw(bins);
    this.curve.setHistogram(bins.g);
    setText(this.histInfo, `${w} x ${h} · rendered in ${Math.round(ms)} ms · ${clipS ? 'shadow clip' : ''}${clipS && clipH ? ' · ' : ''}${clipH ? 'highlight clip' : ''}`.replace(/ · $/, ''));
  }
}

export class DevelopLeft {
  private readonly nav: HTMLImageElement;
  private readonly zooms: HTMLElement;
  private readonly presetList: HTMLElement;
  private readonly histList: HTMLElement;
  private readonly amount: Slider;

  constructor(host: HTMLElement, onZoom: (z: 'fit' | 'full') => void) {
    const pNav = new Panel('dev.nav', 'Navigator');
    this.nav = el<HTMLImageElement>('<img alt="" draggable="false">');
    const navBox = el('<div class="fl-nav fl-nav-fit"></div>');
    navBox.appendChild(this.nav);
    this.zooms = el('<div class="fl-nav-zooms"><button type="button" data-z="fit" class="is-on">Fit</button><button type="button" data-z="full">100%</button></div>');
    this.zooms.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-z]');
      if (b) onZoom(b.dataset.z === 'full' ? 'full' : 'fit');
    });
    const zoomRow = el('<div class="fl-row fl-row-end"><span class="fl-sub-inline fl-grow">Zoom</span></div>');
    zoomRow.appendChild(this.zooms);
    pNav.body.append(navBox, zoomRow);

    const pPre = new Panel('dev.presets', 'Presets');
    this.amount = new Slider({ id: 'preset.amount', label: 'Amount', min: 0, max: 200, default: 100, step: 1, decimals: 0 }, { input: () => undefined });
    this.presetList = el('<div class="fl-list"></div>');
    for (const p of PRESETS) {
      const row = el(`<button class="fl-list-row" type="button" data-id="${p.id}"><span></span><em></em></button>`);
      setText(q(row, 'span'), p.name);
      setText(q(row, 'em'), p.group);
      this.presetList.appendChild(row);
    }
    this.presetList.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-id]');
      const p = PRESETS.find((x) => x.id === b?.dataset.id);
      if (!p || !develop.item) return;
      develop.replace(presetDev(develop.settings, p, this.amount.get() / 100), 'end', `Preset: ${p.name}`);
    });
    pPre.body.append(this.amount.root, this.presetList);

    const pHist = new Panel('dev.history', 'History');
    this.histList = el('<div class="fl-list fl-history"></div>');
    pHist.body.append(this.histList);
    host.append(pNav.root, pPre.root, pHist.root);
  }

  setZoom(z: 'fit' | 'full'): void {
    for (const b of Array.from(this.zooms.children) as HTMLElement[]) setClass(b, 'is-on', b.dataset.z === z);
  }

  sync(): void {
    const item = develop.item;
    if (item && item.thumb && this.nav.src !== item.thumb) { this.nav.src = item.thumb; setClass(this.nav, 'is-loaded', true); }
    const entries = item ? item.hist.map((h, i) => ({ i, label: h.label, cur: i === item.hi })).reverse() : [];
    patchList(this.histList, entries, {
      key: (e) => `${item?.id}:${e.i}`,
      create: (e) => {
        const row = el(`<button class="fl-list-row" type="button"><span></span><em></em></button>`);
        row.addEventListener('click', () => develop.goto(Number(row.dataset.i)));
        row.dataset.i = String(e.i);
        setText(q(row, 'span'), e.label);
        setText(q(row, 'em'), String(e.i));
        setClass(row, 'is-on', e.cur);
        return row;
      },
      update: (node, e) => { node.dataset.i = String(e.i); setClass(node, 'is-on', e.cur); },
    });
  }
}
