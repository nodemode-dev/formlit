import type { Ctx } from '../../app';
import { develop } from '../../state/develop';
import { library } from '../../state/library';
import { Dialog } from '../../ui/dialogs';
import { el, q, setClass, setText } from '../../ui/dom';
import { binsOf } from '../../ui/histogram';
import { icon } from '../../ui/icons';
import { toast } from '../../ui/toast';
import { filmstrip } from '../library';
import { registerModule, type ModuleHosts } from '../registry';
import { LeftPanels } from './left';
import { MaskTool } from './masks';
import { DevelopPanels } from './panels';
import { CropTool, RedEyeTool, SpotTool, toolStrip, WbPickerTool, type ToolHost } from './tools';
import { DevelopView, type Compare, type Tool } from './view';

const GROUPS: Array<[string, string]> = [
  ['whiteBalance', 'White Balance'], ['basicTone', 'Basic Tone'], ['presence', 'Presence'], ['toneCurve', 'Tone Curve'], ['colorMixer', 'Color Mixer'],
  ['pointColor', 'Point Color'], ['bwMix', 'B&W Mix'], ['treatment', 'Treatment'], ['colorGrading', 'Color Grading'], ['detail', 'Detail'],
  ['lensCorrections', 'Lens Corrections'], ['transform', 'Transform'], ['effects', 'Effects'], ['calibration', 'Calibration'], ['profile', 'Profile'],
  ['lensBlur', 'Lens Blur'], ['masks', 'Masking'], ['spots', 'Healing'], ['redEye', 'Red Eye'], ['crop', 'Crop'],
];
const DEFAULT_OFF = new Set(['masks', 'spots', 'redEye', 'crop']);

class GroupsDialog extends Dialog {
  private resolve: ((v: string[] | null) => void) | null = null;
  private readonly boxes = new Map<string, HTMLInputElement>();
  private readonly ok: HTMLButtonElement;
  constructor() {
    super('Copy Settings', 520);
    const grid = el('<div class="fl-groups"></div>');
    for (const [k, l] of GROUPS) {
      const row = el(`<label class="fl-check"><input type="checkbox"> <span></span></label>`);
      setText(q(row, 'span'), l);
      const cb = q<HTMLInputElement>(row, 'input');
      cb.checked = !DEFAULT_OFF.has(k);
      this.boxes.set(k, cb);
      grid.appendChild(row);
    }
    const all = el('<div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm" type="button" data-all="1">Check All</button><button class="cv-btn fl-btn-sm" type="button" data-all="0">Check None</button></div>');
    all.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-all]');
      if (b) for (const cb of this.boxes.values()) cb.checked = b.dataset.all === '1';
    });
    this.body.append(grid, all);
    this.button('Cancel', 'ghost', () => this.finish(null));
    this.ok = this.button('Copy', 'primary', () => this.finish([...this.boxes].filter(([, cb]) => cb.checked).map(([k]) => k)));
    this.onClose = () => this.finish(null);
  }
  ask(title: string, okLabel: string): Promise<string[] | null> {
    this.setTitle(title);
    setText(this.ok, okLabel);
    this.open(this.ok);
    return new Promise((r) => { this.resolve = r; });
  }
  private finish(v: string[] | null): void {
    const r = this.resolve;
    this.resolve = null;
    if (this.isOpen) this.close();
    r?.(v);
  }
}

class DevelopModule {
  private ctx!: Ctx;
  private hosts!: ModuleHosts;
  view!: DevelopView;
  private panels!: DevelopPanels;
  private drawer!: HTMLElement;
  private tools = new Map<string, Tool & { activate(): void }>();
  private toolId = '';
  private active = false;
  private groupsDialog: GroupsDialog | null = null;
  private histTimer = 0;

  mount(ctx: Ctx, hosts: ModuleHosts): void {
    this.ctx = ctx;
    this.hosts = hosts;
    this.view = new DevelopView();
    hosts.stage.appendChild(this.view.root);
    this.drawer = el('<div class="fl-drawer" hidden></div>');
    const strip = toolStrip();
    void develop.init().then(() => {
      this.panels = new DevelopPanels(ctx, hosts.right, this.view, strip);
      q(hosts.right, '.fl-panel').appendChild(this.drawer);
      new LeftPanels(ctx, hosts.left, this.view);
      const host: ToolHost = { ctx, view: this.view, drawer: this.drawer, done: () => this.setTool('') };
      this.tools.set('crop', new CropTool(host));
      this.tools.set('spot', new SpotTool(host));
      this.tools.set('redeye', new RedEyeTool(host));
      this.tools.set('masks', new MaskTool(host));
      this.tools.set('wb', new WbPickerTool(host));
      if (this.active) void this.open();
    }, (err) => ctx.fail(err, 'Develop'));
    this.toolbar();
    this.foots();
    this.commands();
    this.view.onRendered = (img) => {
      window.clearTimeout(this.histTimer);
      this.histTimer = window.setTimeout(() => {
        if (!this.panels) return;
        this.panels.histogram.fromImage(img);
        const c = document.createElement('canvas');
        const s = Math.min(1, 200 / Math.max(img.naturalWidth, img.naturalHeight));
        c.width = Math.max(1, Math.round(img.naturalWidth * s));
        c.height = Math.max(1, Math.round(img.naturalHeight * s));
        const g = c.getContext('2d', { willReadFrequently: true });
        if (!g) return;
        g.drawImage(img, 0, 0, c.width, c.height);
        const bins = binsOf(g.getImageData(0, 0, c.width, c.height).data);
        const lum = new Uint32Array(bins.r.length);
        for (let i = 0; i < lum.length; i += 1) lum[i] = bins.r[i] + bins.g[i] + bins.b[i];
        this.panels.curveHistogram(lum);
      }, 60);
    };
    this.view.onError = (err) => ctx.shell.setHint(`Render failed: ${err instanceof Error ? err.message : String(err)}`);
    develop.listen((why) => {
      if (why === 'drag' || why === 'edit' || why === 'reload' || why === 'photo') this.view.schedule();
      if (why === 'edit' || why === 'reload') this.view.setDragging(false);
      if (why === 'photo' || why === 'reload' || why === 'info') this.syncInfo();
    });
    library.listen('selection', () => { if (this.active) void this.open(); });
    library.listen('photos', (ids) => { if (this.active && develop.id !== null && ids.includes(develop.id)) this.view.setPhoto(library.photo(develop.id) ?? null); });
  }

  activate(): void {
    this.active = true;
    if (filmstrip) filmstrip.onOpen = (id) => library.setActive(id);
    void this.open();
  }

  deactivate(): void {
    this.active = false;
    void develop.flush().catch(() => undefined);
    this.setTool('');
  }

  private async open(): Promise<void> {
    if (!this.panels) return;
    const id = library.active;
    const p = library.photo(id) ?? null;
    if (develop.id !== id) {
      try { await develop.open(id); } catch (err) { this.ctx.fail(err); }
    }
    this.view.setPhoto(p);
    this.ctx.shell.setSelection(p ? p.file : '');
    this.ctx.shell.setCount(`${library.ids.length} photo${library.ids.length === 1 ? '' : 's'}`);
  }

  private syncInfo(): void {
    const i = develop.info;
    if (!this.panels || !i) return;
    const p = library.photo(develop.id);
    this.panels.setHistogramInfo(p ? `${i.width ?? p.w} x ${i.height ?? p.h}${i.raw ? ' · raw' : ''} · As shot ${i.asShotTemp} K` : '');
  }

  setTool(id: string): void {
    if (this.toolId === id) id = '';
    this.toolId = id;
    const t = this.tools.get(id) ?? null;
    this.drawer.hidden = !t;
    if (t) t.activate();
    this.view.setTool(t);
    this.view.invalidateRegion();
    for (const b of Array.from(this.ctx.shell.app.querySelectorAll<HTMLElement>('[data-cmd^="develop.tool."]'))) setClass(b, 'is-active', b.dataset.cmd === `develop.tool.${id}`);
    if (id === 'crop') this.view.setZoom('fit');
    this.view.schedule();
  }

  private toolbar(): void {
    const t = this.hosts.toolbar;
    const bar = el(`<div class="fl-tb">
<button class="cv-icon-btn" type="button" data-cmd="develop.loupe" aria-label="Loupe">${icon('viewLoupe', 16)}</button>
<div class="cv-seg fl-seg-sm fl-tb-compare"><button type="button" data-c="off" title="After only">After</button><button type="button" data-c="lr" title="Before and After, Left and Right (Y)">Left/Right</button><button type="button" data-c="tb" title="Before and After, Top and Bottom">Top/Bottom</button><button type="button" data-c="split" title="Split view">Split</button><button type="button" data-c="before" title="Before only (\\)">Before</button></div>
<span class="fl-tb-sep"></span>
<button class="cv-icon-btn" type="button" data-cmd="develop.clipping" aria-label="Show Clipping (J)">${icon('clipHighlights', 16)}</button>
<button class="cv-icon-btn" type="button" data-cmd="develop.wbPicker" aria-label="White Balance Selector (W)">${icon('eyeDropper', 16)}</button>
<span class="fl-tb-spacer"></span>
<span class="fl-tb-label fl-tb-zoom"></span>
<div class="cv-seg fl-seg-sm fl-tb-zooms"><button type="button" data-z="fit">Fit</button><button type="button" data-z="fill">Fill</button><button type="button" data-z="1">1:1</button><button type="button" data-z="2">2:1</button></div>
</div>`);
    t.appendChild(bar);
    q(bar, '.fl-tb-compare').addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-c]');
      if (b) this.setCompare(b.dataset.c as Compare);
    });
    q(bar, '.fl-tb-zooms').addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-z]');
      if (!b) return;
      const z = b.dataset.z as string;
      this.view.setZoom(z === 'fit' || z === 'fill' ? z : Number(z));
    });
    const prev = this.view.onZoom;
    this.view.onZoom = (z) => {
      prev?.(z);
      setText(q(bar, '.fl-tb-zoom'), z === 'fit' ? 'Fit' : z === 'fill' ? 'Fill' : `${Math.round(z * 100)}%`);
      for (const b of Array.from(bar.querySelectorAll<HTMLElement>('[data-z]'))) setClass(b, 'is-on', b.dataset.z === String(z));
    };
    this.setCompare('off');
  }

  private setCompare(c: Compare): void {
    this.view.setCompare(c);
    for (const b of Array.from(this.hosts.toolbar.querySelectorAll<HTMLElement>('[data-c]'))) setClass(b, 'is-on', b.dataset.c === c);
  }

  private foots(): void {
    const l = el(`<div class="fl-foot-row"><button class="cv-btn" type="button" data-cmd="develop.copy">Copy...</button><button class="cv-btn" type="button" data-cmd="develop.paste">Paste</button></div>`);
    const r = el(`<div class="fl-foot-row"><button class="cv-btn" type="button" data-cmd="develop.syncSettings">Sync...</button><button class="cv-btn" type="button" data-cmd="develop.reset">Reset</button></div>`);
    this.hosts.leftFoot.appendChild(l);
    this.hosts.rightFoot.appendChild(r);
  }

  private async targets(): Promise<number[]> {
    await develop.flush();
    const ids = library.targets();
    return ids.length ? ids : develop.id !== null ? [develop.id] : [];
  }

  private run(cmd: string, params: Record<string, unknown> = {}, done?: (r: unknown) => void): void {
    void this.targets().then((ids) => this.ctx.api.cmd(cmd, { ids, ...params })).then((r) => done?.(r), (err) => this.ctx.fail(err));
  }

  private commands(): void {
    const ctx = this.ctx;
    const has = () => develop.id !== null;
    const multi = () => library.targets().length > 1;
    const tool = (id: string) => () => { if (ctx.module() !== 'develop') ctx.toModule('develop'); this.setTool(id); };
    ctx.commands.add(
      { id: 'develop.auto', label: 'Auto Settings', keys: ['Shift+Mod+U'], run: () => this.run('develop.auto'), enabled: has },
      { id: 'develop.autoBw', label: 'Auto B&W Mix', run: () => this.run('develop.autoBw'), enabled: has },
      { id: 'develop.reset', label: 'Reset All Settings', keys: ['Shift+Mod+R'], run: () => this.run('develop.reset'), enabled: has },
      { id: 'develop.copy', label: 'Copy Settings...', keys: ['Shift+Mod+C'], run: async () => {
        if (develop.id === null) return;
        await develop.flush();
        this.groupsDialog ??= new GroupsDialog();
        const groups = await this.groupsDialog.ask('Copy Settings', 'Copy');
        if (groups) await ctx.api.cmd('develop.copy', { id: develop.id, groups }).then(() => toast('Settings copied'), (e) => ctx.fail(e));
      }, enabled: has },
      { id: 'develop.paste', label: 'Paste Settings', keys: ['Shift+Mod+V'], run: () => this.run('develop.paste', {}, () => toast('Settings pasted')), enabled: has },
      { id: 'develop.pastePrevious', label: 'Paste Settings from Previous', keys: ['Alt+Mod+V'], run: () => this.run('develop.pastePrevious'), enabled: has },
      { id: 'develop.syncSettings', label: 'Sync Settings...', keys: ['Shift+Mod+S'], run: async () => {
        const ids = await this.targets();
        const from = library.active;
        if (ids.length < 2 || from === null) { toast('Select two or more photos to sync'); return; }
        this.groupsDialog ??= new GroupsDialog();
        const groups = await this.groupsDialog.ask('Synchronize Settings', 'Synchronize');
        if (groups) await ctx.api.cmd('develop.sync', { ids: ids.filter((i) => i !== from), from, groups }).then(() => toast(`Synced ${ids.length - 1} photos`), (e) => ctx.fail(e));
      }, enabled: multi },
      { id: 'develop.matchExposure', label: 'Match Total Exposures', keys: ['Alt+Shift+Mod+M'], run: () => this.run('develop.matchExposure'), enabled: multi },
      { id: 'develop.clipping', label: 'Show Clipping', keys: ['J'], run: () => { this.view.clipping = !this.view.clipping; this.view.schedule(); }, checked: () => this.view.clipping },
      { id: 'develop.beforeAfter', label: 'Before/After Left/Right', keys: ['Y'], run: () => { if (ctx.module() !== 'develop') ctx.toModule('develop'); this.setCompare(this.view.compare === 'lr' ? 'off' : 'lr'); }, checked: () => this.view.compare === 'lr' },
      { id: 'develop.before', label: 'Show Before', keys: ['\\'], run: () => this.setCompare(this.view.compare === 'before' ? 'off' : 'before'), checked: () => this.view.compare === 'before' },
      { id: 'develop.loupe', label: 'Loupe', run: () => this.setCompare('off') },
      { id: 'develop.tool.crop', label: 'Crop and Straighten', keys: ['R'], run: tool('crop'), checked: () => this.toolId === 'crop' },
      { id: 'develop.tool.spot', label: 'Healing', keys: ['Q'], run: tool('spot'), checked: () => this.toolId === 'spot' },
      { id: 'develop.tool.redeye', label: 'Red Eye Correction', keys: ['Shift+E'], run: tool('redeye'), checked: () => this.toolId === 'redeye' },
      { id: 'develop.tool.masks', label: 'Masking', keys: ['Shift+W'], run: tool('masks'), checked: () => this.toolId === 'masks' },
      { id: 'develop.wbPicker', label: 'White Balance Selector', keys: ['W'], run: tool('wb'), checked: () => this.toolId === 'wb' },
      { id: 'develop.preset', label: 'New Develop Preset...', run: () => ctx.run('develop.newPreset') },
      { id: 'develop.zoom', label: 'Toggle Zoom', keys: ['Z'], run: () => { if (ctx.module() === 'develop') this.view.toggleZoom(); else ctx.run('view.zoomToggle'); } },
      { id: 'develop.aiDenoise', label: 'Denoise...', keys: ['Alt+Mod+D'], run: () => this.run('ai.denoise', { amount: 50 }, () => toast('Denoise started; a new DNG will appear next to the original')), enabled: has },
      { id: 'develop.lensBlurDepth', label: 'Build Depth Map', run: () => this.run('ai.depth', {}, () => toast('Depth map ready')), enabled: has },
    );
  }

  onKey(e: KeyboardEvent, combo: string): boolean {
    const t = this.view.tool;
    if (t?.key?.(e, combo)) { this.view.draw(); return true; }
    if (combo === 'Escape' && this.toolId) { this.setTool(''); return true; }
    if (combo === 'Space') { this.view.toggleZoom(); return true; }
    return false;
  }
}

const mod = new DevelopModule();

registerModule({
  id: 'develop', label: 'Develop', icon: 'modDevelop', key: 'D', order: 2,
  mount: (ctx, hosts) => mod.mount(ctx, hosts),
  activate: () => mod.activate(),
  deactivate: () => mod.deactivate(),
  onKey: (e, combo) => mod.onKey(e, combo),
});
