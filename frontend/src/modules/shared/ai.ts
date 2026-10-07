import type { Ctx } from '../../app';
import { library } from '../../state/library';
import { Dialog } from '../../ui/dialogs';
import { el, q, setText } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { toast } from '../../ui/toast';
import { askMerge } from './merge-dialog';

interface CullResult { photos: number; groups: number; best: number[]; blurry: number[]; duplicates: number[] }

class OptionsDialog extends Dialog {
  private resolve: ((v: Record<string, unknown> | null) => void) | null = null;
  private readonly ok: HTMLButtonElement;
  private read: () => Record<string, unknown> = () => ({});
  constructor() {
    super('Options', 460);
    this.button('Cancel', 'ghost', () => this.finish(null));
    this.ok = this.button('OK', 'primary', () => this.finish(this.read()));
    this.onClose = () => this.finish(null);
  }
  ask(title: string, body: HTMLElement, okLabel: string, read: () => Record<string, unknown>): Promise<Record<string, unknown> | null> {
    this.setTitle(title);
    this.body.replaceChildren(body);
    setText(this.ok, okLabel);
    this.read = read;
    this.open(this.ok);
    return new Promise((r) => { this.resolve = r; });
  }
  private finish(v: Record<string, unknown> | null): void {
    const r = this.resolve;
    this.resolve = null;
    if (this.isOpen) this.close();
    r?.(v);
  }
}

let dialog: OptionsDialog | null = null;
function ask(title: string, html: string, okLabel: string, read: (root: HTMLElement) => Record<string, unknown>): Promise<Record<string, unknown> | null> {
  dialog ??= new OptionsDialog();
  const body = el(`<div class="fl-ai-dialog">${html}</div>`);
  return dialog.ask(title, body, okLabel, () => read(body));
}

async function run(ctx: Ctx, cmd: string, params: Record<string, unknown>, started: string): Promise<void> {
  try {
    await ctx.api.cmd(cmd, params);
    toast(started);
  } catch (err) { ctx.fail(err); }
}

export function registerAiCommands(ctx: Ctx): void {
  const has = () => library.targets().length > 0;
  const two = () => library.targets().length > 1;
  ctx.commands.add(
    { id: 'photo.enhance', label: 'Enhance...', keys: ['Alt+Shift+Mod+I'], enabled: has, run: async () => {
      const ids = library.targets();
      const v = await ask('Enhance', `<p class="cv-note">Makes a new DNG next to the original and stacks the two. Your edits carry over.</p>
<label class="fl-check"><input type="checkbox" data-k="denoise" checked> ${icon('denoise', 14)} Denoise</label>
<label class="fl-opt"><span>Amount</span><input class="cv-slider" type="range" min="0" max="100" value="50" data-k="amount"></label>
<label class="fl-check"><input type="checkbox" data-k="sr"> ${icon('superRes', 14)} Super Resolution (twice the width and height)</label>`, 'Enhance', (r) => ({
        denoise: q<HTMLInputElement>(r, '[data-k="denoise"]').checked, amount: Number(q<HTMLInputElement>(r, '[data-k="amount"]').value), sr: q<HTMLInputElement>(r, '[data-k="sr"]').checked,
      }));
      if (!v) return;
      if (v.denoise) await run(ctx, 'ai.denoise', { ids, amount: v.amount }, `Denoising ${ids.length} photo${ids.length === 1 ? '' : 's'}`);
      if (v.sr) await run(ctx, 'ai.superResolution', { ids }, 'Super Resolution started');
    } },
    { id: 'photo.hdr', label: 'HDR Merge...', keys: ['Mod+H'], enabled: two, run: async () => {
      const ids = library.targets();
      const v = await askMerge(ctx, 'hdr', ids);
      if (v) await run(ctx, 'ai.hdrMerge', { ids, deghost: v.deghost, autoTone: v.autoTone, align: v.align }, 'HDR merge started');
    } },
    { id: 'photo.pano', label: 'Panorama Merge...', keys: ['Mod+M'], enabled: two, run: async () => {
      const ids = library.targets();
      const v = await askMerge(ctx, 'pano', ids);
      if (v) await run(ctx, 'ai.panoMerge', { ids, projection: v.projection, boundaryWarp: v.boundaryWarp, fillEdges: v.fillEdges, autoCrop: v.autoCrop }, 'Panorama merge started');
    } },
    { id: 'library.cull', label: 'Assisted Culling...', keys: ['Alt+Shift+C'], enabled: has, run: async () => {
      const ids = library.targets().length > 1 ? library.targets() : library.ids;
      if (!ids.length) return;
      try {
        const r = await ctx.api.cmd<CullResult>('cull.analyze', { ids, wait: true });
        const v = await ask('Assisted Culling', `<p class="cv-note">${r.photos} photos assessed for focus and exposure, ${r.groups} groups of near duplicates found.</p>
<label class="fl-check"><input type="checkbox" data-k="pick" checked> Flag the best of each group as a pick (${r.groups})</label>
<label class="fl-check"><input type="checkbox" data-k="blur" checked> Reject blurry photos (${r.blurry.length})</label>
<label class="fl-check"><input type="checkbox" data-k="dupes"> Reject the other near duplicates (${r.duplicates.length})</label>`, 'Apply', (root) => ({
          pickBest: q<HTMLInputElement>(root, '[data-k="pick"]').checked, rejectBlurry: q<HTMLInputElement>(root, '[data-k="blur"]').checked, rejectDuplicates: q<HTMLInputElement>(root, '[data-k="dupes"]').checked,
        }));
        if (!v) return;
        const res = await ctx.api.cmd<{ picks: number[]; rejects: number[] }>('cull.apply', { ids, ...v });
        toast(`${res.picks.length} picked, ${res.rejects.length} rejected`);
      } catch (err) { ctx.fail(err, 'Assisted Culling'); }
    } },
    { id: 'library.findFaces', label: 'Find Faces', run: () => void run(ctx, 'ai.findFaces', { all: true }, 'Finding faces in the catalog') },
  );
}
