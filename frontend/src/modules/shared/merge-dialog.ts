import type { Ctx } from '../../app';
import { Dialog } from '../../ui/dialogs';
import { el, q, setClass, setHidden, setText } from '../../ui/dom';

type Kind = 'hdr' | 'pano' | 'hdrpano' | 'focus' | 'astro';

const DEGHOST = `<div class="fl-row"><span class="fl-row-label">Deghost</span><div class="cv-seg fl-seg-sm fl-grow" data-seg="deghost"><button type="button" data-v="off" class="is-on">None</button><button type="button" data-v="low">Low</button><button type="button" data-v="medium">Medium</button><button type="button" data-v="high">High</button></div></div>`;
const STACK = '<label class="fl-check"><input type="checkbox" data-k="createStack"> Create Stack</label>';

const HDR_OPTS = `<label class="fl-check"><input type="checkbox" data-k="align" checked> Auto Align</label>
<label class="fl-check"><input type="checkbox" data-k="autoTone" checked> Auto Settings</label>
${DEGHOST}
<label class="fl-check"><input type="checkbox" data-k="showGhosts"> Show Deghost Overlay</label>
${STACK}`;

const PANO_CORE = `<div class="fl-row"><span class="fl-row-label">Projection</span><div class="cv-seg fl-seg-sm fl-grow" data-seg="projection"><button type="button" data-v="spherical" class="is-on">Spherical</button><button type="button" data-v="cylindrical">Cylindrical</button><button type="button" data-v="plane">Perspective</button></div></div>
<label class="fl-opt"><span>Boundary Warp</span><input class="cv-slider" type="range" min="0" max="100" value="0" data-k="boundaryWarp"><em data-out="boundaryWarp">0</em></label>
<label class="fl-check"><input type="checkbox" data-k="fillEdges"> Fill Edges</label>
<label class="fl-check"><input type="checkbox" data-k="autoCrop" checked> Auto Crop</label>`;

const PANO_OPTS = `${PANO_CORE}
${STACK}`;

const HDRPANO_OPTS = `${PANO_CORE}
${DEGHOST}
${STACK}`;

const FOCUS_OPTS = `<label class="fl-check"><input type="checkbox" data-k="align" checked> Auto Align (corrects the size change between frames as focus moves)</label>
<label class="fl-check"><input type="checkbox" data-k="autoCrop" checked> Auto Crop to the area every frame covers</label>
<label class="fl-check"><input type="checkbox" data-k="createStack" checked> Create Stack</label>
<p class="cv-note">Shoot on a tripod, same exposure, focus stepping from near to far. The merged DNG keeps the middle frame's settings.</p>`;

const ASTRO_OPTS = `<label class="fl-check"><input type="checkbox" data-k="align" checked> Align on the Stars (follows the sky as it turns between frames)</label>
<label class="fl-check"><input type="checkbox" data-k="fixedGround" checked> Keep the Landscape Sharp (stacks the ground without moving it; needs the sky model)</label>
<div class="fl-row"><span class="fl-row-label">Combine</span><div class="cv-seg fl-seg-sm fl-grow" data-seg="reject"><button type="button" data-v="sigma" class="is-on">Reject Outliers</button><button type="button" data-v="median">Median</button><button type="button" data-v="mean">Average</button></div></div>
<label class="fl-check"><input type="checkbox" data-k="autoCrop" checked> Auto Crop to the sky every frame covers (when the landscape is not kept)</label>
${STACK}
<p class="cv-note">Shoot from a tripod, the same exposure for every frame, ten or more frames. Reject Outliers removes satellites, planes and hot pixels; noise falls by about the square root of the frame count.</p>`;

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
    this.setTitle(kind === 'hdr' ? `HDR Merge Preview (${ids.length} photos)` : kind === 'hdrpano' ? `HDR Panorama Merge Preview (${ids.length} photos)` : kind === 'focus' ? `Focus Stack Preview (${ids.length} photos)` : kind === 'astro' ? `Astro Stack Preview (${ids.length} frames)` : `Panorama Merge Preview (${ids.length} photos)`);
    const html = kind === 'hdr' ? HDR_OPTS : kind === 'hdrpano' ? HDRPANO_OPTS : kind === 'focus' ? FOCUS_OPTS : kind === 'astro' ? ASTRO_OPTS : PANO_OPTS;
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

class EnhanceDialog extends Dialog {
  private readonly prev = el('<div class="fl-enh-prev"><figure><img alt="" draggable="false"><figcaption>Before</figcaption></figure><figure><img alt="" draggable="false"><figcaption>After</figcaption></figure><span class="fl-merge-status">Building preview...</span></div>');
  private readonly opts = el(`<div class="fl-merge-opts"><label class="fl-check"><input type="checkbox" data-k="denoise" checked> Denoise</label>
<label class="fl-opt"><span>Amount</span><input class="cv-slider" type="range" min="0" max="100" value="50" data-k="amount"><em data-out="amount">50</em></label>
<label class="fl-check"><input type="checkbox" data-k="rawDetails"> Raw Details (sharper demosaic, raw photos)</label>
<label class="fl-check"><input type="checkbox" data-k="sr"> Super Resolution (twice the width and height)</label>
<p class="cv-note">Each enhancement makes a new DNG next to the original and stacks the two. Your edits carry over. Denoise uses the learned SCUNet denoiser once it is installed (Preferences, AI models), otherwise a classic one.</p></div>`);
  private readonly ok: HTMLButtonElement;
  private id = 0;
  private raw = false;
  private seq = 0;
  private timer = 0;
  private resolve: ((v: Record<string, unknown> | null) => void) | null = null;

  constructor(private readonly ctx: Ctx) {
    super('Enhance', 720);
    this.body.append(this.prev, this.opts);
    this.button('Cancel', 'ghost', () => this.finish(null));
    this.ok = this.button('Enhance', 'primary', () => this.finish(this.values()));
    this.onClose = () => this.finish(null);
    this.opts.addEventListener('input', (e) => {
      const i = e.target as HTMLInputElement;
      if (i.dataset.k === 'amount') setText(q(this.opts, '[data-out="amount"]'), i.value);
      if (i.dataset.k === 'denoise' && i.checked) q<HTMLInputElement>(this.opts, '[data-k="rawDetails"]').checked = false;
      if (i.dataset.k === 'rawDetails' && i.checked) q<HTMLInputElement>(this.opts, '[data-k="denoise"]').checked = false;
      this.sync();
      if (i.dataset.k !== 'sr') this.soon(i.type === 'range' ? 500 : 100);
    });
  }

  ask(id: number, raw: boolean, count: number): Promise<Record<string, unknown> | null> {
    this.id = id;
    this.raw = raw;
    this.setTitle(count > 1 ? `Enhance ${count} Photos` : 'Enhance');
    const rd = q<HTMLInputElement>(this.opts, '[data-k="rawDetails"]');
    rd.disabled = !raw;
    if (!raw) rd.checked = false;
    this.sync();
    this.open(this.ok);
    this.soon(0);
    return new Promise((r) => { this.resolve = r; });
  }

  private values(): Record<string, unknown> {
    const v = (k: string) => q<HTMLInputElement>(this.opts, `[data-k="${k}"]`);
    return { denoise: v('denoise').checked, amount: Number(v('amount').value), rawDetails: v('rawDetails').checked, sr: v('sr').checked };
  }

  private sync(): void {
    const v = this.values();
    setHidden(q(this.opts, '.fl-opt'), !v.denoise);
    this.ok.disabled = !v.denoise && !v.rawDetails && !v.sr;
  }

  private soon(ms: number): void {
    window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => void this.preview(), ms);
  }

  private async preview(): Promise<void> {
    const v = this.values();
    const status = q(this.prev, '.fl-merge-status');
    if (!v.denoise && !v.rawDetails) { setText(status, 'Super Resolution has no preview here; it doubles the pixel count.'); setHidden(status, false); return; }
    const seq = ++this.seq;
    setText(status, v.rawDetails ? 'Demosaicing the whole raw file for Raw Details...' : 'Building preview...');
    setHidden(status, false);
    setClass(this.prev, 'is-busy', true);
    try {
      const r = await this.ctx.api.cmd<{ before: string; after: string }>('ai.enhancePreview', { id: this.id, kind: v.rawDetails ? 'rawDetails' : 'denoise', amount: v.amount });
      if (seq !== this.seq) return;
      const imgs = this.prev.querySelectorAll<HTMLImageElement>('img');
      const urls = [`data:image/jpeg;base64,${r.before}`, `data:image/jpeg;base64,${r.after}`];
      await Promise.all(urls.map((u) => { const i = new Image(); i.src = u; return i.decode().catch(() => undefined); }));
      if (seq !== this.seq) return;
      imgs[0].src = urls[0];
      imgs[1].src = urls[1];
      setHidden(status, true);
    } catch (err) {
      if (seq === this.seq) { setText(status, err instanceof Error ? err.message : String(err)); setHidden(status, false); }
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

let enhance: EnhanceDialog | null = null;

export function askEnhance(ctx: Ctx, id: number, raw: boolean, count: number): Promise<Record<string, unknown> | null> {
  enhance ??= new EnhanceDialog(ctx);
  return enhance.ask(id, raw, count);
}
