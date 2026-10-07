import type { Ctx } from '../../app';
import { library } from '../../state/library';
import { Dialog } from '../../ui/dialogs';
import { el, q, setText } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { toast } from '../../ui/toast';
import { askEnhance, askMerge } from './merge-dialog';

interface CullResult { photos: number; groups: number; best: number[]; blurry: number[]; duplicates: number[]; eyesClosed?: number[]; withFaces?: number; scores?: Record<string, { sharpness: number; exposure: number; eyesOpen: number | null }> }

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
function ask(title: string, html: string, okLabel: string, read: (root: HTMLElement) => Record<string, unknown>, wire?: (root: HTMLElement) => void): Promise<Record<string, unknown> | null> {
  dialog ??= new OptionsDialog();
  const body = el(`<div class="fl-ai-dialog">${html}</div>`);
  wire?.(body);
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
      const first = library.photo(library.active ?? ids[0]);
      if (!first) return;
      const v = await askEnhance(ctx, first.id, ids.some((id) => library.photo(id)?.kind === 'raw'), ids.length);
      if (!v) return;
      if (v.denoise) await run(ctx, 'ai.denoise', { ids, amount: v.amount }, `Denoising ${ids.length} photo${ids.length === 1 ? '' : 's'}`);
      if (v.rawDetails) await run(ctx, 'ai.rawDetails', { ids }, `Raw Details for ${ids.length} photo${ids.length === 1 ? '' : 's'}`);
      if (v.sr) await run(ctx, 'ai.superResolution', { ids }, 'Super Resolution started');
    } },
    { id: 'photo.hdr', label: 'HDR Merge...', keys: ['Mod+H'], enabled: two, run: async () => {
      const ids = library.targets();
      const v = await askMerge(ctx, 'hdr', ids);
      if (v) await run(ctx, 'ai.hdrMerge', { ids, deghost: v.deghost, autoTone: v.autoTone, align: v.align, createStack: v.createStack }, 'HDR merge started');
    } },
    { id: 'photo.pano', label: 'Panorama Merge...', keys: ['Mod+M'], enabled: two, run: async () => {
      const ids = library.targets();
      const v = await askMerge(ctx, 'pano', ids);
      if (v) await run(ctx, 'ai.panoMerge', { ids, projection: v.projection, boundaryWarp: v.boundaryWarp, fillEdges: v.fillEdges, autoCrop: v.autoCrop, createStack: v.createStack }, 'Panorama merge started');
    } },
    { id: 'photo.hdrPano', label: 'HDR Panorama Merge...', keys: ['Shift+Mod+M'], enabled: () => library.targets().length > 3, run: async () => {
      const ids = library.targets();
      const v = await askMerge(ctx, 'hdrpano', ids);
      if (v) await run(ctx, 'ai.hdrPanoMerge', { ids, projection: v.projection, boundaryWarp: v.boundaryWarp, fillEdges: v.fillEdges, autoCrop: v.autoCrop, deghost: v.deghost, createStack: v.createStack }, 'HDR Panorama merge started');
    } },
    { id: 'library.cull', label: 'Assisted Culling...', keys: ['Alt+Shift+C'], enabled: has, run: async () => {
      const ids = library.targets().length > 1 ? library.targets() : library.ids;
      if (!ids.length) return;
      try {
        const done = ctx.shell.busy(`Assessing ${ids.length} photos`);
        let r: CullResult;
        try { r = await ctx.api.cmd<CullResult>('cull.analyze', { ids, wait: true }); } finally { done(); }
        const scores = Object.values(r.scores ?? {});
        const count = (fn: (s: { sharpness: number; exposure: number; eyesOpen: number | null }) => boolean) => scores.filter(fn).length;
        const slider = (k: string, label: string, val: number) => `<label class="fl-opt fl-cull-opt"><span>${label}</span><input class="cv-slider" type="range" min="0" max="100" value="${val}" data-k="${k}"><em data-out="${k}">${val}</em></label>`;
        const v = await ask('Assisted Culling', `<p class="cv-note">${r.photos} photos assessed for focus, exposure${r.withFaces ? ` and open eyes (${r.withFaces} with faces)` : ''}; ${r.groups} ${r.groups === 1 ? 'group' : 'groups'} of near duplicates.</p>
<label class="fl-check"><input type="checkbox" data-k="pick" checked> Mark the best of each group (${r.groups})</label>
<label class="fl-check"><input type="checkbox" data-k="blur" checked> Reject blurry photos</label>
${slider('threshold', 'Sharpness', 35)}
<label class="fl-check"><input type="checkbox" data-k="eyes"${r.withFaces ? ' checked' : ' disabled'}> Reject closed eyes (${r.eyesClosed?.length ?? 0})</label>
${slider('exposureMin', 'Exposure', 0)}
<label class="fl-check"><input type="checkbox" data-k="dupes"> Reject the other near duplicates (${r.duplicates.length})</label>
<div class="fl-row"><span class="fl-row-label">Apply as</span><div class="cv-seg fl-seg-sm fl-grow" data-seg="applyAs"><button type="button" data-v="flags" class="is-on">Flags</button><button type="button" data-v="ratings">Ratings</button><button type="button" data-v="labels">Labels</button><button type="button" data-v="stacks">Stacks</button></div></div>
<p class="cv-note fl-cull-count"></p>`, 'Apply', (root) => ({
          pickBest: q<HTMLInputElement>(root, '[data-k="pick"]').checked, rejectBlurry: q<HTMLInputElement>(root, '[data-k="blur"]').checked, rejectDuplicates: q<HTMLInputElement>(root, '[data-k="dupes"]').checked,
          rejectEyesClosed: q<HTMLInputElement>(root, '[data-k="eyes"]').checked, threshold: Number(q<HTMLInputElement>(root, '[data-k="threshold"]').value),
          exposureMin: Number(q<HTMLInputElement>(root, '[data-k="exposureMin"]').value), applyAs: root.querySelector<HTMLElement>('[data-seg="applyAs"] .is-on')?.dataset.v ?? 'flags',
        }), (root) => {
          const sync = () => {
            const t = Number(q<HTMLInputElement>(root, '[data-k="threshold"]').value), e = Number(q<HTMLInputElement>(root, '[data-k="exposureMin"]').value);
            for (const o of Array.from(root.querySelectorAll<HTMLElement>('[data-out]'))) setText(o, q<HTMLInputElement>(root, `[data-k="${o.dataset.out}"]`).value);
            setText(q(root, '.fl-cull-count'), `${count((s) => s.sharpness < t)} below the sharpness threshold, ${count((s) => e > 0 && s.exposure < e)} below the exposure threshold.`);
          };
          root.addEventListener('input', sync);
          root.addEventListener('click', (ev) => { const b = (ev.target as HTMLElement).closest<HTMLElement>('[data-seg] [data-v]'); if (b) for (const x of Array.from(b.parentElement?.children ?? []) as HTMLElement[]) x.classList.toggle('is-on', x === b); });
          sync();
        });
        if (!v) return;
        const res = await ctx.api.cmd<{ picks: number[]; rejects: number[]; kept: number[]; stacks: number[][] }>('cull.apply', { ids, ...v });
        toast(v.applyAs === 'stacks' ? `Stacked ${res.stacks.length} groups of near duplicates` : `${res.picks.length} best, ${res.rejects.length} rejected, ${res.kept.length} kept`);
      } catch (err) { ctx.fail(err, 'Assisted Culling'); }
    } },
    { id: 'library.findFaces', label: 'Find Faces', run: () => void run(ctx, 'ai.findFaces', { all: true }, 'Finding faces in the catalog') },
  );
}
