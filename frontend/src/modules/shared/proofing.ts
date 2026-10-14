import type { Ctx } from '../../app';
import { library } from '../../state/library';
import { askForm } from '../../ui/askform';
import { toast } from '../../ui/toast';
import { whenDone } from './tasks';

export function registerProofing(ctx: Ctx): void {
  ctx.commands.add(
    {
      id: 'library.proofExport', label: 'Export Proofing Gallery...', enabled: () => library.targets().length > 0,
      run: async () => {
        const ids = library.targets();
        const v = await askForm('Export Proofing Gallery', `Makes a folder your client opens in any browser, with no account and no server: they pick, reject, rate and comment on ${ids.length} photo${ids.length === 1 ? '' : 's'}, then send you a small selections file. Zip the folder to email it, or put it on any web host.`, [
          { path: 'title', label: 'Title', kind: 'text', placeholder: 'Smith Wedding Proofs' },
          { path: 'note', label: 'Note to the client', kind: 'textarea', placeholder: 'Pick up to 40 favourites by Friday.' },
          { path: 'size', label: 'Image size', kind: 'select', options: [['1200', '1200 px'], ['1600', '1600 px'], ['2048', '2048 px']] },
          { path: 'names', label: 'Show file names', kind: 'check' },
          { path: 'folder', label: 'Folder (optional)', kind: 'text', placeholder: 'Exports/Proofs/<title>' },
        ], { title: '', note: '', size: '1600', names: false, folder: '' }, 'Export');
        if (!v) return;
        try {
          const r = await ctx.api.cmd<{ task: number }>('proof.export', { ids, title: String(v.title || 'Proofs'), note: String(v.note || ''), size: Number(v.size || 1600), names: !!v.names, ...(v.folder ? { folder: String(v.folder) } : {}) });
          const done = await whenDone(r.task) as { folder?: string; photos?: number };
          toast(`Proofing gallery ready: ${done.folder ?? ''}`);
        } catch (err) { ctx.fail(err); }
      },
    },
    {
      id: 'library.proofImport', label: 'Import Client Selections...',
      run: async () => {
        const v = await askForm('Import Client Selections', 'The file your client saved from the proofing gallery, or the text they copied. Picks and rejects become flags, stars become ratings, comments go onto the photos, and the picks get a collection.', [
          { path: 'path', label: 'Selections file', kind: 'text', placeholder: '~/Downloads/selections-Smith_Wedding-Jordan.json' },
          { path: 'text', label: 'Or the copied text', kind: 'textarea', placeholder: '{"format":"formlit-proof-selections", ...}' },
          { path: 'flags', label: 'Apply picks and rejects', kind: 'check' },
          { path: 'ratings', label: 'Apply stars', kind: 'check' },
        ], { path: '', text: '', flags: true, ratings: true }, 'Import');
        if (!v || (!v.path && !v.text)) return;
        try {
          const r = await ctx.api.cmd<{ client: string; matched: number; missing: number; picked: number; rejected: number; commented: number }>('proof.import', { path: String(v.path || ''), text: String(v.text || ''), flags: !!v.flags, ratings: !!v.ratings });
          toast(`${r.client}: ${r.picked} picked, ${r.rejected} rejected, ${r.commented} comment${r.commented === 1 ? '' : 's'}${r.missing ? ` · ${r.missing} not in this catalog` : ''}`);
        } catch (err) { ctx.fail(err); }
      },
    },
  );
}
