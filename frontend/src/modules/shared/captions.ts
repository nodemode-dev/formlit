import type { Ctx } from '../../app';
import { askForm } from '../../ui/askform';
import { confirmAction } from '../../ui/dialogs';
import { toast } from '../../ui/toast';
import { library } from '../../state/library';

interface CodeState { sets: Array<{ name: string; count: number }>; active: string; delimiter: string; delimiters: string[]; on: boolean; required: string[]; enforce: boolean; tokens: string[]; fields: string[] }
interface Check { required: string[]; incomplete: number; complete: number; byField: Record<string, number> }

const LABELS: Record<string, string> = {
  title: 'Title', caption: 'Caption', headline: 'Headline', creator: 'Creator', copyright: 'Copyright', credit: 'Credit Line', source: 'Source',
  city: 'City', state: 'State / Province', country: 'Country', isoCountryCode: 'ISO Country Code', location: 'Location', sublocation: 'Sublocation',
  event: 'Event', jobId: 'Job Identifier', instructions: 'Instructions', personShown: 'Person Shown', altText: 'Alt Text', rightsUsage: 'Rights Usage Terms',
};
const COMMON = ['title', 'caption', 'headline', 'creator', 'copyright', 'credit', 'source', 'city', 'state', 'country', 'sublocation', 'event', 'jobId', 'personShown', 'altText', 'rightsUsage'];

export const fieldLabel = (f: string): string => LABELS[f] ?? f;

export function registerCaptions(ctx: Ctx): void {
  const state = () => ctx.api.cmd<CodeState>('codes.state');

  const edit = async (): Promise<void> => {
    try {
      const s = await state();
      const cur = s.active ? await ctx.api.cmd<{ name: string; text: string }>('codes.get', { name: s.active }) : { name: '', text: '' };
      const v = await askForm('Code Replacements',
        `Type a code between ${s.delimiter} marks in any metadata field (${s.delimiter}23${s.delimiter}) and it becomes its text when saved. One code per line: the code, a tab or comma, then the text. Captions can also use ${s.tokens.slice(0, 7).join(' ')} and more, filled from each photo.`,
        [
          { path: 'name', label: 'Set name', kind: 'text', placeholder: 'Lakers roster' },
          { path: 'text', label: 'Codes', kind: 'textarea', wide: true, placeholder: '23\tLeBron James (23) of the Los Angeles Lakers' },
          { path: 'delimiter', label: 'Code marks', kind: 'select', options: s.delimiters.map((d): [string, string] => [d, `${d}code${d}`]) },
          { path: 'on', label: 'Replace codes when metadata is saved', kind: 'check' },
        ],
        { name: cur.name || 'Codes', text: cur.text, delimiter: s.delimiter, on: s.on }, 'Save');
      if (!v) return;
      if (String(v.text ?? '').trim()) {
        const r = await ctx.api.cmd<{ count: number; name: string }>('codes.save', { name: String(v.name ?? '').trim() || 'Codes', text: String(v.text) });
        toast(`${r.name}: ${r.count} ${r.count === 1 ? 'code' : 'codes'}, now the active set`);
      }
      await ctx.api.cmd('codes.settings', { delimiter: v.delimiter, on: !!v.on });
    } catch (err) { ctx.fail(err, 'Code Replacements'); }
  };

  const choose = async (): Promise<void> => {
    try {
      const s = await state();
      if (!s.sets.length) { toast('No code sets yet: Metadata, Code Replacements makes one'); return; }
      const v = await askForm('Choose Code Set', 'The active set is the one codes are replaced from.', [
        { path: 'active', label: 'Set', kind: 'select', options: s.sets.map((x): [string, string] => [x.name, `${x.name} (${x.count})`]) },
        { path: 'remove', label: 'Delete this set instead', kind: 'check' },
      ], { active: s.active || s.sets[0].name, remove: false }, 'OK');
      if (!v) return;
      if (v.remove) {
        if (!(await confirmAction('Delete Code Set', `Delete ${String(v.active)}? Captions already written keep their text.`, 'Delete', true))) return;
        await ctx.api.cmd('codes.delete', { name: v.active });
        toast(`Deleted ${String(v.active)}`);
        return;
      }
      await ctx.api.cmd('codes.settings', { active: v.active });
      toast(`Codes now come from ${String(v.active)}`);
    } catch (err) { ctx.fail(err, 'Choose Code Set'); }
  };

  const importFile = async (): Promise<void> => {
    const v = await askForm('Import Code Replacements', 'A tab or comma separated text file, as Photo Mechanic and team roster services export them. The set is named after the file.', [
      { path: 'path', label: 'File', kind: 'text', placeholder: '/Users/me/Codes/lakers.txt', wide: true },
    ], { path: '' }, 'Import');
    if (!v || !String(v.path ?? '').trim()) return;
    try {
      const r = await ctx.api.cmd<{ count: number; name: string }>('codes.importFile', { path: String(v.path).trim() });
      toast(`Imported ${r.count} codes into ${r.name}, now the active set`);
    } catch (err) { ctx.fail(err, 'Import Code Replacements'); }
  };

  const required = async (): Promise<void> => {
    try {
      const s = await state();
      const fields = COMMON.filter((f) => s.fields.includes(f));
      const values: Record<string, unknown> = { enforce: s.enforce };
      for (const f of fields) values[f] = s.required.includes(f);
      const v = await askForm('Required Fields', 'Fields every photo must have before it is delivered, as agencies and editors require. Export warns about photos missing them.', [
        ...fields.map((f) => ({ path: f, label: fieldLabel(f), kind: 'check' as const })),
        { path: 'enforce', label: 'Refuse to export photos missing them', kind: 'check' as const },
      ], values, 'Save');
      if (!v) return;
      const req = fields.filter((f) => !!v[f]);
      await ctx.api.cmd('codes.settings', { required: req, enforce: !!v.enforce });
      toast(req.length ? `Required: ${req.map(fieldLabel).join(', ')}` : 'No fields are required');
    } catch (err) { ctx.fail(err, 'Required Fields'); }
  };

  ctx.commands.add(
    { id: 'metadata.codes', label: 'Code Replacements...', run: () => void edit() },
    { id: 'metadata.codesChoose', label: 'Choose Code Set...', run: () => void choose() },
    { id: 'metadata.codesImport', label: 'Import Code Replacements...', run: () => void importFile() },
    { id: 'metadata.required', label: 'Required Fields...', run: () => void required() },
    { id: 'metadata.checkRequired', label: 'Check Required Fields', enabled: () => library.ids.length > 0, run: async () => {
      const ids = library.targets().length ? library.targets() : library.ids;
      try {
        const r = await ctx.api.cmd<Check>('metadata.checkRequired', { ids });
        if (!r.required.length) { toast('No fields are required: Metadata, Required Fields sets them'); return; }
        toast(r.incomplete ? `${r.incomplete} of ${ids.length} missing ${summary(r)}` : `All ${ids.length} have ${r.required.map(fieldLabel).join(', ')}`, r.incomplete ? 'error' : undefined);
      } catch (err) { ctx.fail(err); }
    } },
  );
}

function summary(r: Check): string {
  return Object.entries(r.byField).sort((a, b) => b[1] - a[1]).slice(0, 4).map(([f, n]) => `${fieldLabel(f)} (${n})`).join(', ');
}

export async function warnMissing(ctx: Ctx, ids: number[]): Promise<boolean> {
  try {
    const [s, r] = await Promise.all([ctx.api.cmd<CodeState>('codes.state'), ctx.api.cmd<Check>('metadata.checkRequired', { ids })]);
    if (!r.incomplete || s.enforce) return true;
    return await confirmAction('Missing Required Metadata', `${r.incomplete} of ${ids.length} photos are missing ${summary(r)}. Export them anyway?`, 'Export Anyway');
  } catch { return true; }
}
