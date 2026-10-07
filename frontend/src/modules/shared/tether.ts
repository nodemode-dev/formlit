import type { Ctx } from '../../app';
import { events } from '../../io/events';
import { library } from '../../state/library';
import { askForm } from '../../ui/askform';
import { el, q, setHidden, setText } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { toast } from '../../ui/toast';

interface TetherState { active: boolean; model?: string; shots?: number; last?: number | null; settings?: Record<string, string>; choices?: Record<string, string[]>; session?: string; error?: string; installed?: boolean; preset?: string }

const READOUT: Array<[string, string]> = [['shutterspeed', 'Shutter'], ['aperture', 'Aperture'], ['iso', 'ISO'], ['whitebalance', 'WB']];

class LiveView {
  readonly root = el(`<div class="fl-live" hidden role="dialog" aria-label="Live View"><div class="fl-live-head"><span>Live View</span><span class="fl-live-fps"></span><button class="cv-icon-btn" type="button" aria-label="Close Live View">${icon('close', 14)}</button></div><img alt="" draggable="false"><span class="fl-live-msg">Waiting for the camera...</span></div>`);
  private on = false;
  private url = '';

  constructor(private readonly ctx: Ctx) {
    document.getElementById('overlay-root')?.appendChild(this.root);
    q(this.root, '.cv-icon-btn').addEventListener('click', () => this.toggle(false));
  }

  toggle(on = !this.on): void {
    this.on = on;
    setHidden(this.root, !on);
    if (on) void this.loop();
  }

  private async loop(): Promise<void> {
    const img = q<HTMLImageElement>(this.root, 'img');
    let frames = 0;
    let t0 = performance.now();
    while (this.on) {
      try {
        const r = await this.ctx.api.cmd<{ jpeg: string }>('tether.liveView');
        const blob = await (await fetch(`data:image/jpeg;base64,${r.jpeg}`)).blob();
        const url = URL.createObjectURL(blob);
        const pre = new Image();
        pre.src = url;
        await pre.decode().catch(() => undefined);
        if (!this.on) { URL.revokeObjectURL(url); break; }
        img.src = url;
        if (this.url) URL.revokeObjectURL(this.url);
        this.url = url;
        setHidden(q(this.root, '.fl-live-msg'), true);
        frames += 1;
        if (performance.now() - t0 > 1000) { setText(q(this.root, '.fl-live-fps'), `${frames} fps`); frames = 0; t0 = performance.now(); }
      } catch (err) {
        setText(q(this.root, '.fl-live-msg'), err instanceof Error ? err.message : String(err));
        setHidden(q(this.root, '.fl-live-msg'), false);
        await new Promise((r) => window.setTimeout(r, 1500));
      }
    }
  }
}

class TetherBar {
  readonly root = el(`<div class="fl-tether" hidden role="toolbar" aria-label="Tethered Capture"><div class="fl-tether-cam"><strong class="fl-tether-model"></strong><span class="fl-tether-session"></span></div>${READOUT.map(([k, l]) => `<div class="fl-tether-read"><span>${l}</span><b data-r="${k}">-</b><select class="fl-tether-sel" data-native data-set="${k}" aria-label="${l}" hidden></select></div>`).join('')}<button class="fl-tether-shutter" type="button" aria-label="Capture" title="Capture (F12)"><span></span></button><span class="fl-tether-count"></span><div class="fl-tether-read fl-tether-dev"><span>Develop</span><select class="fl-tether-sel" data-native data-dev aria-label="Develop Settings"><option value="">None</option><option value="previous">Same as Previous</option></select></div><button class="cv-btn fl-btn-sm" type="button" data-a="live" title="Live View">Live View</button><button class="cv-icon-btn" type="button" data-a="stop" aria-label="Stop Tethered Capture" title="Stop Tethered Capture">${icon('close', 14)}</button></div>`);
  private readonly liveView: LiveView;
  private stateTimer = 0;

  constructor(private readonly ctx: Ctx) {
    document.body.appendChild(this.root);
    this.liveView = new LiveView(ctx);
    q(this.root, '.fl-tether-shutter').addEventListener('click', () => this.capture());
    q(this.root, '[data-a="stop"]').addEventListener('click', () => void ctx.api.cmd('tether.stop').then(() => this.show(false), (err) => ctx.fail(err)));
    q(this.root, '[data-a="live"]').addEventListener('click', () => this.liveView.toggle());
    this.root.addEventListener('change', (e) => {
      const s = e.target as HTMLSelectElement;
      if (s.dataset.set) void ctx.api.cmd('tether.set', { key: s.dataset.set, value: s.value }).catch((err) => ctx.fail(err, 'Camera Setting'));
      if (s.dataset.dev !== undefined) void ctx.api.cmd('tether.develop', { preset: s.value }).then(() => toast(s.value ? `New shots get ${s.selectedOptions[0]?.textContent ?? s.value}` : 'New shots keep their camera settings'), (err) => ctx.fail(err));
    });
    void ctx.api.cmd<{ presets: Array<{ id: string; name: string; group: string }> }>('preset.list').then((r) => {
      const sel = q<HTMLSelectElement>(this.root, '[data-dev]');
      for (const p of r.presets) sel.add(new Option(`${p.group}: ${p.name}`, p.id));
    }, () => undefined);
    events.on('tether', (e) => {
      if (e.state === 'shot') {
        const ids = (e.ids as number[]) ?? [];
        this.count(Number(e.count ?? 0));
        const id = ids[ids.length - 1];
        let tries = 0;
        const pick = () => {
          if (id === undefined) return;
          if (library.photos.has(id) && library.ids.includes(id)) { library.setActive(id, false); return; }
          if (++tries < 12) window.setTimeout(pick, 250);
        };
        void library.refresh().then(pick, pick);
      } else if (e.state === 'settings') {
        this.readout((e.settings as Record<string, string>) ?? {});
        window.clearTimeout(this.stateTimer);
        this.stateTimer = window.setTimeout(() => void ctx.api.cmd<TetherState>('tether.state').then((s) => this.choices(s), () => undefined), 400);
      } else if (e.state === 'stopped') { this.show(false); this.liveView.toggle(false); }
      else if (e.state === 'error') toast(`Tether: ${String(e.error)}`, 'error');
    });
    void ctx.api.cmd<TetherState>('tether.state').then((s) => { if (s.active) this.apply(s); }, () => undefined);
  }

  capture(): void {
    if (this.root.hidden) return;
    void this.ctx.api.cmd('tether.capture').catch((err) => this.ctx.fail(err));
  }

  apply(s: TetherState): void {
    setText(q(this.root, '.fl-tether-model'), s.model || 'Camera');
    setText(q(this.root, '.fl-tether-session'), s.session ?? '');
    this.count(s.shots ?? 0);
    this.readout(s.settings ?? {});
    this.choices(s);
    const dev = q<HTMLSelectElement>(this.root, '[data-dev]');
    if (s.preset !== undefined && dev.value !== s.preset) dev.value = s.preset;
    this.show(true);
  }

  private choices(s: TetherState): void {
    for (const [k] of READOUT) {
      const list = s.choices?.[k] ?? [];
      const sel = q<HTMLSelectElement>(this.root, `[data-set="${k}"]`);
      const key = list.join('|');
      if (sel.dataset.key !== key) { sel.dataset.key = key; sel.replaceChildren(...list.map((v) => new Option(v, v))); }
      if (list.length && this.values[k] !== undefined && sel.value !== this.values[k]) sel.value = this.values[k];
      setHidden(sel, list.length < 2);
      setHidden(q(this.root, `[data-r="${k}"]`), list.length >= 2);
    }
  }

  private count(n: number): void { setText(q(this.root, '.fl-tether-count'), `${n} ${n === 1 ? 'shot' : 'shots'}`); }

  private readonly values: Record<string, string> = {};

  private readout(settings: Record<string, string>): void {
    Object.assign(this.values, settings);
    for (const [k] of READOUT) {
      setText(q(this.root, `[data-r="${k}"]`), this.values[k] ?? '-');
      const sel = q<HTMLSelectElement>(this.root, `[data-set="${k}"]`);
      if (this.values[k] !== undefined && sel.value !== this.values[k] && document.activeElement !== sel) sel.value = this.values[k];
    }
  }

  show(on: boolean): void { setHidden(this.root, !on); }

  live(): void { if (!this.root.hidden) this.liveView.toggle(); }
}

let bar: TetherBar | null = null;

export function registerTether(ctx: Ctx): void {
  bar = new TetherBar(ctx);
  ctx.commands.add(
    {
      id: 'library.tether', label: 'Start Tethered Capture...',
      run: async () => {
        let cams: { installed: boolean; cameras: Array<{ model: string; port: string }> };
        let presets: Array<{ id: string; name: string; group: string }> = [];
        try {
          [cams, presets] = await Promise.all([ctx.api.cmd<typeof cams>('tether.cameras'), ctx.api.cmd<{ presets: typeof presets }>('preset.list').then((r) => r.presets)]);
        } catch (err) { ctx.fail(err); return; }
        if (!cams.installed) { toast(/Win/.test(navigator.platform) ? 'Tethered capture on Windows uses digiCamControl. Install it from digicamcontrol.com, then try again.' : 'Tethered capture uses gphoto2. Install it (brew install gphoto2, or apt install gphoto2), then try again.', 'error'); return; }
        if (!cams.cameras.length) { toast('No camera found. Connect it by USB, switch it on and close other apps using it.', 'error'); return; }
        const v = await askForm('Tethered Capture Settings', 'Photos taken on the camera or with the shutter button land in the catalog as they are shot.', [
          { path: 'camera', label: 'Camera', kind: 'select', options: cams.cameras.map((c) => [c.port, `${c.model} (${c.port})`] as [string, string]) },
          { path: 'session', label: 'Session Name', kind: 'text' },
          { path: 'destination', label: 'Destination', kind: 'text', placeholder: '~/Pictures/formlit Tether' },
          { path: 'renameTemplate', label: 'Naming', kind: 'text', placeholder: '{custom}-{seq:3} (leave empty to keep camera names)' },
          { path: 'keywords', label: 'Keywords', kind: 'text', placeholder: 'Studio, Client|Acme' },
          { path: 'preset', label: 'Develop Settings', kind: 'select', options: [['', 'None'], ['previous', 'Same as Previous'], ...presets.map((p) => [p.id, `${p.group}: ${p.name}`] as [string, string])] },
        ], { camera: cams.cameras[0].port, session: `Tethered ${new Date().toISOString().slice(0, 10)}`, destination: '', renameTemplate: '', keywords: '', preset: '' }, 'OK');
        if (!v) return;
        const cam = cams.cameras.find((c) => c.port === v.camera) ?? cams.cameras[0];
        try {
          const s = await ctx.api.cmd<TetherState>('tether.start', { port: cam.port, model: cam.model, session: v.session, destination: v.destination, renameTemplate: v.renameTemplate,
            keywords: String(v.keywords ?? '').split(',').map((k) => k.trim()).filter(Boolean), preset: v.preset });
          bar?.apply(s);
        } catch (err) { ctx.fail(err); }
      },
    },
    { id: 'library.tetherCapture', label: 'Trigger Capture', keys: ['F12'], run: () => bar?.capture() },
    { id: 'library.tetherLive', label: 'Live View', run: () => bar?.live() },
    { id: 'library.tetherStop', label: 'Stop Tethered Capture', run: () => void ctx.api.cmd('tether.stop').then(() => bar?.show(false), (err) => ctx.fail(err)) },
  );
}
