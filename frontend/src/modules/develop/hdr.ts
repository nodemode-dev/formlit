import { clone, develop } from '../../state/develop';
import { el, q, setClass, setHidden } from '../../ui/dom';
import { Slider } from '../../ui/slider';
import type { DevelopView } from './view';

interface Hdr { enabled?: boolean; headroom?: number; sdr?: Record<string, number> }

const SDR: Array<[string, string]> = [['brightness', 'Brightness'], ['contrast', 'Contrast'], ['clarity', 'Clarity'], ['saturation', 'Saturation']];

export class HdrSection {
  readonly root = el(`<div class="fl-hdr"><div class="fl-row"><span class="fl-row-label">HDR</span><button class="cv-btn fl-btn-sm fl-hdr-toggle" type="button" aria-pressed="false" title="Edit in high dynamic range">HDR</button><span class="fl-grow"></span></div>
<div class="fl-hdr-body" hidden><div class="fl-hdr-head"></div>
<label class="fl-check fl-check-sm"><input type="checkbox" data-k="visualize"> Visualize HDR</label>
<label class="fl-check fl-check-sm"><input type="checkbox" data-k="sdr"> Preview for SDR Display</label>
<div class="fl-hdr-sdr" hidden><div class="fl-sub">SDR Settings</div></div></div></div>`);
  private readonly head: Slider;
  private readonly sliders = new Map<string, Slider>();

  constructor(private readonly view: DevelopView) {
    this.head = new Slider({ id: 'hdr.headroom', label: 'Headroom', min: 0.5, max: 4, default: 2, step: 0.1, decimals: 1 }, { input: (_id, v, phase) => {
      const h = this.cfg();
      h.headroom = v;
      this.write(h, phase, 'HDR Headroom');
    } });
    q(this.root, '.fl-hdr-head').appendChild(this.head.root);
    for (const [k, label] of SDR) {
      const s = new Slider({ id: `hdr.sdr.${k}`, label, min: -100, max: 100, default: 0, step: 1, decimals: 0 }, { input: (_id, v, phase) => {
        const h = this.cfg();
        h.sdr = { ...(h.sdr ?? {}), [k]: v };
        if (!v) delete h.sdr[k];
        this.write(h, phase, `SDR ${label}`);
      } });
      this.sliders.set(k, s);
      q(this.root, '.fl-hdr-sdr').appendChild(s.root);
    }
    q(this.root, '.fl-hdr-toggle').addEventListener('click', () => {
      const h = this.cfg();
      h.enabled = !h.enabled;
      this.write(h, 'end', h.enabled ? 'HDR On' : 'HDR Off');
    });
    this.root.addEventListener('change', () => this.mode());
    develop.listen(() => this.sync());
    this.sync();
  }

  private cfg(): Hdr { return clone((develop.settings.hdr as Hdr | undefined) ?? {}); }

  private write(h: Hdr, phase: 'drag' | 'end', label: string): void {
    if (h.sdr && !Object.keys(h.sdr).length) delete h.sdr;
    develop.patch('hdr', h.enabled || h.sdr || (h.headroom !== undefined && h.headroom !== 2) ? h : null, phase, label);
    this.view.setDragging(phase === 'drag');
    this.sync();
  }

  private mode(): void {
    const h = this.cfg();
    const sdr = q<HTMLInputElement>(this.root, '[data-k="sdr"]').checked;
    const vis = q<HTMLInputElement>(this.root, '[data-k="visualize"]').checked;
    setHidden(q(this.root, '.fl-hdr-sdr'), !sdr);
    const next = !h.enabled ? '' : sdr ? 'sdr' : vis ? 'visualize' : 'display';
    if (next !== this.view.hdr) { this.view.hdr = next; this.view.schedule(); }
  }

  sync(): void {
    const h = this.cfg();
    const t = q(this.root, '.fl-hdr-toggle');
    setClass(t, 'is-on', !!h.enabled);
    t.setAttribute('aria-pressed', String(!!h.enabled));
    setHidden(q(this.root, '.fl-hdr-body'), !h.enabled);
    this.head.set(h.headroom ?? 2);
    for (const [k, s] of this.sliders) s.set(h.sdr?.[k] ?? 0);
    this.mode();
  }
}
