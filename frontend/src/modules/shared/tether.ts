import type { Ctx } from '../../app';
import { events } from '../../io/events';
import { library } from '../../state/library';
import { askForm } from '../../ui/askform';
import { el, q, setHidden, setText } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { toast } from '../../ui/toast';

interface TetherState { active: boolean; model?: string; shots?: number; last?: number | null; settings?: Record<string, string>; session?: string; error?: string; installed?: boolean }

const READOUT: Array<[string, string]> = [['shutterspeed', 'Shutter'], ['aperture', 'Aperture'], ['iso', 'ISO'], ['whitebalance', 'WB']];

class TetherBar {
  readonly root = el(`<div class="fl-tether" hidden role="toolbar" aria-label="Tethered Capture"><div class="fl-tether-cam"><strong class="fl-tether-model"></strong><span class="fl-tether-session"></span></div>${READOUT.map(([k, l]) => `<div class="fl-tether-read"><span>${l}</span><b data-r="${k}">-</b></div>`).join('')}<button class="fl-tether-shutter" type="button" aria-label="Capture" title="Capture (F12)"><span></span></button><span class="fl-tether-count"></span><button class="cv-icon-btn" type="button" data-a="stop" aria-label="Stop Tethered Capture" title="Stop Tethered Capture">${icon('close', 14)}</button></div>`);

  constructor(private readonly ctx: Ctx) {
    document.body.appendChild(this.root);
    q(this.root, '.fl-tether-shutter').addEventListener('click', () => this.capture());
    q(this.root, '[data-a="stop"]').addEventListener('click', () => void ctx.api.cmd('tether.stop').then(() => this.show(false), (err) => ctx.fail(err)));
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
      } else if (e.state === 'settings') this.readout((e.settings as Record<string, string>) ?? {});
      else if (e.state === 'stopped') this.show(false);
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
    this.show(true);
  }

  private count(n: number): void { setText(q(this.root, '.fl-tether-count'), `${n} ${n === 1 ? 'shot' : 'shots'}`); }

  private readonly values: Record<string, string> = {};

  private readout(settings: Record<string, string>): void {
    Object.assign(this.values, settings);
    for (const [k] of READOUT) setText(q(this.root, `[data-r="${k}"]`), this.values[k] ?? '-');
  }

  show(on: boolean): void { setHidden(this.root, !on); }
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
        if (!cams.installed) { toast('Tethered capture uses gphoto2. Install it (brew install gphoto2, or apt install gphoto2), then try again.', 'error'); return; }
        if (!cams.cameras.length) { toast('No camera found. Connect it by USB, switch it on and close other apps using it.', 'error'); return; }
        const v = await askForm('Tethered Capture Settings', 'Photos taken on the camera or with the shutter button land in the catalog as they are shot.', [
          { path: 'camera', label: 'Camera', kind: 'select', options: cams.cameras.map((c) => [c.port, `${c.model} (${c.port})`] as [string, string]) },
          { path: 'session', label: 'Session Name', kind: 'text' },
          { path: 'destination', label: 'Destination', kind: 'text', placeholder: '~/Pictures/formlit Tether' },
          { path: 'renameTemplate', label: 'Naming', kind: 'text', placeholder: '{custom}-{seq:3} (leave empty to keep camera names)' },
          { path: 'keywords', label: 'Keywords', kind: 'text', placeholder: 'Studio, Client|Acme' },
          { path: 'preset', label: 'Develop Settings', kind: 'select', options: [['', 'None'], ...presets.map((p) => [p.id, `${p.group}: ${p.name}`] as [string, string])] },
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
    { id: 'library.tetherStop', label: 'Stop Tethered Capture', run: () => void ctx.api.cmd('tether.stop').then(() => bar?.show(false), (err) => ctx.fail(err)) },
  );
}
