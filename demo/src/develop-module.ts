import { el, q, setClass, setHidden, setValue } from '../../frontend/src/ui/dom';
import { icon } from '../../frontend/src/ui/icons';
import { toast } from '../../frontend/src/ui/toast';
import { autoTone } from './auto';
import { DevelopView, type Tool } from './develop-view';
import { DevelopLeft, DevelopPanels } from './develop-panels';
import { clone } from './engine/settings';
import { develop } from './shims/develop';
import { copySettings, exportSettings, importSettings, openExport, pasteSettings, resetSettings } from './actions';

const ASPECTS: Array<[string, number | null]> = [['Free', null], ['Square', 1], ['4 : 3', 4 / 3], ['3 : 2', 3 / 2], ['16 : 9', 16 / 9], ['5 : 4', 5 / 4], ['3 : 4', 3 / 4], ['2 : 3', 2 / 3]];

export class DevelopModule {
  readonly view = new DevelopView();
  readonly panels: DevelopPanels;
  readonly left: DevelopLeft;
  private readonly bar: HTMLElement;
  private readonly cropBar: HTMLElement;
  private readonly angle: HTMLInputElement;
  private readonly aspect: HTMLSelectElement;
  private active = false;

  constructor(hosts: { left: HTMLElement; stage: HTMLElement; toolbar: HTMLElement; right: HTMLElement; rightFoot: HTMLElement }) {
    hosts.stage.appendChild(this.view.root);
    this.left = new DevelopLeft(hosts.left, (z) => this.view.setZoom(z));
    this.panels = new DevelopPanels(hosts.right, {
      tool: (t) => this.setTool(this.view.tool === t ? 'none' : t),
      compare: () => this.cycleMode(),
      autoTone: () => this.auto(),
      clipping: () => this.toggleClip(),
      isTool: (t) => this.view.tool === t,
      isClipping: () => this.view.clipping,
      compareOn: () => this.view.mode !== 'after',
    });

    this.bar = el(`<div class="fl-tb fl-dtb">
<div class="cv-seg fl-seg-sm" data-g="mode"><button type="button" data-m="after">After</button><button type="button" data-m="before">Before</button><button type="button" data-m="split">Split</button></div>
<span class="fl-tb-sep"></span>
<button class="cv-icon-btn" type="button" data-b="crop" title="Crop and Straighten (R)" aria-label="Crop">${icon('crop', 16)}</button>
<button class="cv-icon-btn" type="button" data-b="wb" title="White Balance Selector (W)" aria-label="White Balance Selector">${icon('eyeDropper', 16)}</button>
<button class="cv-icon-btn" type="button" data-b="clip" title="Show Clipping (J)" aria-label="Show Clipping">${icon('clipHighlights', 16)}</button>
<button class="cv-icon-btn" type="button" data-b="auto" title="Auto Tone (Shift+A)" aria-label="Auto Tone">${icon('sparkle', 16)}</button>
<span class="fl-tb-sep"></span>
<div class="fl-dtb-crop" hidden>
<select class="cv-select fl-tb-sort" aria-label="Aspect">${ASPECTS.map(([l], i) => `<option value="${i}">${l}</option>`).join('')}</select>
<span class="fl-tb-label">Angle</span><input class="cv-range fl-tb-size" type="range" min="-45" max="45" step="0.1" value="0" aria-label="Angle">
<button class="cv-icon-btn" type="button" data-c="flipH" title="Flip Horizontal" aria-label="Flip Horizontal">${icon('flipH', 16)}</button>
<button class="cv-icon-btn" type="button" data-c="flipV" title="Flip Vertical" aria-label="Flip Vertical">${icon('flipV', 16)}</button>
<button class="cv-icon-btn" type="button" data-c="rotL" title="Rotate Left" aria-label="Rotate Left">${icon('rotateLeft', 16)}</button>
<button class="cv-icon-btn" type="button" data-c="rotR" title="Rotate Right" aria-label="Rotate Right">${icon('rotateRight', 16)}</button>
<button class="cv-btn fl-btn-sm" type="button" data-c="reset">Reset Crop</button>
</div>
<span class="fl-tb-spacer"></span>
<button class="cv-btn fl-btn-sm" type="button" data-b="copy">${icon('copyLit', 13)} Copy</button>
<button class="cv-btn fl-btn-sm" type="button" data-b="paste">${icon('pasteLit', 13)} Paste</button>
<button class="cv-btn fl-btn-sm" type="button" data-b="reset">Reset</button>
<button class="cv-btn fl-btn-sm" type="button" data-b="save">${icon('save', 13)} Settings</button>
<button class="cv-btn fl-btn-sm" type="button" data-b="load">${icon('load', 13)} Load</button>
<button class="cv-btn cv-btn-primary fl-btn-sm" type="button" data-b="export">${icon('exportLit', 13)} Export</button>
</div>`);
    this.cropBar = q(this.bar, '.fl-dtb-crop');
    this.angle = q<HTMLInputElement>(this.bar, 'input');
    this.aspect = q<HTMLSelectElement>(this.bar, 'select');
    hosts.toolbar.appendChild(this.bar);
    this.wire();

    this.view.onBins = (b, cs, ch, w, h, ms) => this.panels.setBins(b, cs, ch, w, h, ms);
    this.view.onZoom = (z) => this.left.setZoom(z);
    this.view.onPick = (temp, tint) => {
      develop.patch('wb', { mode: 'custom', temp: Math.round(temp), tint: Math.round(tint) }, 'end', 'White Balance Selector');
      this.setTool('none');
    };
    this.view.onCrop = (rect, phase) => {
      const full = rect[0] <= 0.0005 && rect[1] <= 0.0005 && rect[2] >= 0.9995 && rect[3] >= 0.9995;
      develop.patch('crop.rect', full ? null : rect.map((v) => Math.round(v * 10000) / 10000), phase, 'Crop');
    };
    develop.listen((why) => {
      this.view.schedule(why === 'drag');
      if (why !== 'drag') this.syncPanels();
      else this.syncCheap();
    });
  }

  private wire(): void {
    this.bar.addEventListener('click', (e) => {
      const t = e.target as HTMLElement;
      const m = t.closest<HTMLElement>('[data-m]')?.dataset.m;
      if (m) { this.view.setMode(m as 'after' | 'before' | 'split'); this.syncBar(); this.panels.sync(); return; }
      const b = t.closest<HTMLElement>('[data-b]')?.dataset.b;
      if (b) { this.action(b); return; }
      const c = t.closest<HTMLElement>('[data-c]')?.dataset.c;
      if (c) this.cropAction(c);
    });
    this.aspect.addEventListener('change', () => this.setAspect(Number(this.aspect.value)));
    this.angle.addEventListener('input', () => develop.patch('crop.angle', Number(this.angle.value) || null, 'drag', 'Straighten'));
    this.angle.addEventListener('change', () => develop.patch('crop.angle', Number(this.angle.value) || null, 'end', 'Straighten'));
  }

  private action(b: string): void {
    if (b === 'crop' || b === 'wb') this.setTool(this.view.tool === b ? 'none' : b);
    else if (b === 'clip') this.toggleClip();
    else if (b === 'auto') this.auto();
    else if (b === 'copy') copySettings(develop.item);
    else if (b === 'paste') { if (develop.item) pasteSettings([develop.item]); }
    else if (b === 'reset') resetSettings(develop.item);
    else if (b === 'save') exportSettings(develop.item);
    else if (b === 'load') importSettings(develop.item ? [develop.item] : []);
    else if (b === 'export') openExport(develop.item ? [develop.item] : []);
  }

  private setAspect(i: number): void {
    const [, r] = ASPECTS[i] ?? ASPECTS[0];
    this.view.cropAspect = r;
    if (!r) return;
    const [x0, y0, x1, y1] = this.view.cropRect;
    const it = develop.item;
    if (!it) return;
    const ow = it.fullW, oh = it.fullH;
    const cw = (x1 - x0) * ow, ch = (y1 - y0) * oh;
    let w = cw, h = cw / r;
    if (h > ch) { h = ch; w = ch * r; }
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    const next = [cx - w / ow / 2, cy - h / oh / 2, cx + w / ow / 2, cy + h / oh / 2];
    this.view.setCropRect(next);
    this.view.onCrop?.(next, 'end');
  }

  private cropAction(c: string): void {
    const turn = (d: number): void => {
      const cur = Number(develop.read('crop.angle')) || 0;
      develop.patch('crop.angle', ((cur + d + 540) % 360) - 180 || null, 'end', 'Rotate');
    };
    if (c === 'flipH') develop.patch('crop.flipH', develop.read('crop.flipH') ? null : true, 'end', 'Flip Horizontal');
    else if (c === 'flipV') develop.patch('crop.flipV', develop.read('crop.flipV') ? null : true, 'end', 'Flip Vertical');
    else if (c === 'rotL') turn(-90);
    else if (c === 'rotR') turn(90);
    else if (c === 'reset') { develop.patch('crop', null, 'end', 'Reset Crop'); this.view.setCropRect([0, 0, 1, 1]); }
  }

  setTool(t: Tool): void {
    this.view.setTool(t);
    setHidden(this.cropBar, t !== 'crop');
    this.syncBar();
    this.panels.sync();
  }

  cycleMode(): void {
    this.view.setMode(this.view.mode === 'after' ? 'split' : this.view.mode === 'split' ? 'before' : 'after');
    this.syncBar();
    this.panels.sync();
  }

  toggleClip(): void {
    this.view.setClipping(!this.view.clipping);
    this.syncBar();
    this.panels.sync();
  }

  auto(): void {
    const it = develop.item;
    if (!it) return;
    develop.replace({ ...clone(develop.settings), ...autoTone(it.src) }, 'end', 'Auto Tone');
    toast('Auto Tone applied');
  }

  private syncBar(): void {
    for (const b of Array.from(this.bar.querySelectorAll<HTMLElement>('[data-m]'))) setClass(b, 'is-on', b.dataset.m === this.view.mode);
    setClass(q(this.bar, '[data-b="crop"]'), 'is-active', this.view.tool === 'crop');
    setClass(q(this.bar, '[data-b="wb"]'), 'is-active', this.view.tool === 'wb');
    setClass(q(this.bar, '[data-b="clip"]'), 'is-active', this.view.clipping);
  }

  private syncCheap(): void {
    this.panels.sync();
  }

  private syncPanels(): void {
    this.panels.sync();
    this.left.sync();
    const angle = Number(develop.read('crop.angle')) || 0;
    setValue(this.angle, String(angle));
  }

  activate(on: boolean): void {
    this.active = on;
    if (on) { this.view.schedule(false); this.syncPanels(); this.syncBar(); }
  }

  open(): void {
    if (!this.active) return;
    this.view.setMode(this.view.mode);
    this.syncPanels();
  }
}
