import type { Ctx } from '../../app';
import { Dialog } from '../../ui/dialogs';
import { el, q, setClass, setHidden, setText } from '../../ui/dom';

type Kind = 'hdr' | 'pano';

const HDR_OPTS = `<label class="fl-check"><input type="checkbox" data-k="align" checked> Auto Align</label>
<label class="fl-check"><input type="checkbox" data-k="autoTone" checked> Auto Settings</label>
<div class="fl-row"><span class="fl-row-label">Deghost</span><div class="cv-seg fl-seg-sm fl-grow" data-seg="deghost"><button type="button" data-v="off" class="is-on">None</button><button type="button" data-v="low">Low</button><button type="button" data-v="medium">Medium</button><button type="button" data-v="high">High</button></div></div>
<label class="fl-check"><input type="checkbox" data-k="showGhosts"> Show Deghost Overlay</label>`;

const PANO_OPTS = `<div class="fl-row"><span class="fl-row-label">Projection</span><div class="cv-seg fl-seg-sm fl-grow" data-seg="projection"><button type="button" data-v="spherical" class="is-on">Spherical</button><button type="button" data-v="cylindrical">Cylindrical</button><button type="button" data-v="plane">Perspective</button></div></div>
<label class="fl-opt"><span>Boundary Warp</span><input class="cv-slider" type="range" min="0" max="100" value="0" data-k="boundaryWarp"><em data-out="boundaryWarp">0</em></label>
<label class="fl-check"><input type="checkbox" data-k="fillEdges"> Fill Edges</label>
<label class="fl-check"><input type="checkbox" data-k="autoCrop" checked> Auto Crop</label>`;

class MergeDialog extends Dialog {
  private readonly prev = el('<div class="fl-merge-prev"><img alt="" draggable="false"><span class="fl-merge-status">Building preview...</span></div>');
  private readonly opts = el('<div class="fl-merge-opts"></div>');
  private readonly ok: HTMLButtonElement;
  private kind: Kind = 'pano';
  private ids: number[] = [];
  private seq = 0;
  private timer = 0;
  private resolve: ((v: Record<string, unknown> | null) => void) | null = null;

  constructor(private readonly ctx: Ctx) {
    super('Merge Preview', 720);
    this.body.append(this.prev, this.opts);
    this.button('Cancel', 'ghost', () => this.finish(null));
    this.ok = this.button('Merge', 'primary', () => this.finish(this.values()));
    this.onClose = () => this.finish(null);
    this.opts.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-seg] [data-v]');
      if (!b) return;
      for (const x of Array.from(b.parentElement?.children ?? []) as HTMLElement[]) setClass(x, 'is-on', x === b);
      this.soon();
    });
    this.opts.addEventListener('input', (e) => {
      const i = e.target as HTMLInputElement;
      const out = this.opts.querySelector<HTMLElement>(`[data-out="${i.dataset.k}"]`);
      if (out) setText(out, i.value);
      this.soon(i.type === 'range' ? 450 : 150);
    });
  }

  ask(kind: Kind, ids: number[]): Promise<Record<string, unknown> | null> {
    this.kind = kind;
    this.ids = ids;
    this.setTitle(kind === 'hdr' ? `HDR Merge Preview (${ids.length} photos)` : `Panorama Merge Preview (${ids.length} photos)`);
    const html = kind === 'hdr' ? HDR_OPTS : PANO_OPTS;
    if (this.opts.dataset.kind !== kind) { this.opts.dataset.kind = kind; this.opts.innerHTML = html; }
    q<HTMLImageElement>(this.prev, 'img').removeAttribute('src');
    setText(q(this.prev, '.fl-merge-status'), 'Building preview...');
    setHidden(q(this.prev, '.fl-merge-status'), false);
    this.open(this.ok);
    this.soon(0);
    return new Promise((r) => { this.resolve = r; });
  }

  private values(): Record<string, unknown> {
    const v: Record<string, unknown> = {};
    for (const i of Array.from(this.opts.querySelectorAll<HTMLInputElement>('input[data-k]'))) v[i.dataset.k as string] = i.type === 'checkbox' ? i.checked : Number(i.value);
    for (const s of Array.from(this.opts.querySelectorAll<HTMLElement>('[data-seg]'))) v[s.dataset.seg as string] = s.querySelector<HTMLElement>('.is-on')?.dataset.v ?? '';
    return v;
  }

  private soon(ms = 300): void {
    window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => void this.preview(), ms);
  }

  private async preview(): Promise<void> {
    const seq = ++this.seq;
    const status = q(this.prev, '.fl-merge-status');
    setClass(this.prev, 'is-busy', true);
    try {
      const opts = this.values();
      delete opts.autoTone;
      const r = await this.ctx.api.cmd<{ jpeg: string; w: number; h: number; ghostPixels: number }>('ai.mergePreview', { ids: this.ids, kind: this.kind, ...opts });
      if (seq !== this.seq) return;
      const url = `data:image/jpeg;base64,${r.jpeg}`;
      const img = q<HTMLImageElement>(this.prev, 'img');
      const pre = new Image();
      pre.src = url;
      await pre.decode().catch(() => undefined);
      if (seq !== this.seq) return;
      img.src = url;
      setHidden(status, true);
      this.ok.disabled = false;
    } catch (err) {
      if (seq !== this.seq) return;
      setText(status, err instanceof Error ? err.message : String(err));
      setHidden(status, false);
      this.ok.disabled = true;
    } finally {
      if (seq === this.seq) setClass(this.prev, 'is-busy', false);
    }
  }

  private finish(v: Record<string, unknown> | null): void {
    const r = this.resolve;
    this.resolve = null;
    this.seq += 1;
    window.clearTimeout(this.timer);
    if (this.isOpen) this.close();
    r?.(v);
  }
}

let dialog: MergeDialog | null = null;

export function askMerge(ctx: Ctx, kind: Kind, ids: number[]): Promise<Record<string, unknown> | null> {
  dialog ??= new MergeDialog(ctx);
  return dialog.ask(kind, ids);
}
