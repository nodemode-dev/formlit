import type { Ctx } from '../../app';
import { library } from '../../state/library';
import { askForm } from '../../ui/askform';
import type { FieldSpec } from '../../ui/form';
import { toast } from '../../ui/toast';

interface Template { id: string; name: string; description: string; value: unknown }
interface Listing { templates: Record<string, Template[]>; identity: Record<string, string> }
interface Shoot { set: number; stages: Record<string, number>; exports: string[]; workflow: string; metadataSkipped: string[] }

const plural = (n: number, w: string): string => `${n} ${w}${n === 1 ? '' : 's'}`;
const patterns = new Map<string, Array<[string, string, string]>>();

export async function patternOptions(ctx: Ctx, kind: 'filename' | 'folder'): Promise<Array<[string, string, string]>> {
  const hit = patterns.get(kind);
  if (hit) return hit;
  try {
    const r = await ctx.api.cmd<Listing>('template.list', { kind });
    const out = (r.templates[kind] ?? []).map((t): [string, string, string] => [String(t.value), t.name, t.description]);
    patterns.set(kind, out);
    return out;
  } catch { return []; }
}

async function listing(ctx: Ctx, kind: string): Promise<Listing | null> {
  try { return await ctx.api.cmd<Listing>('template.list', { kind }); } catch (err) { ctx.fail(err, 'Templates'); return null; }
}

function choices(items: Template[]): Array<[string, string]> {
  return items.map((t) => [t.id, t.name]);
}

function about(items: Template[]): (v: Record<string, unknown>) => string {
  return (v) => items.find((t) => t.id === v.template)?.description ?? '';
}

const IDENTITY: FieldSpec[] = [
  { path: 'creator', label: 'Creator', kind: 'text', placeholder: 'your name or studio' },
  { path: 'email', label: 'Email', kind: 'text', placeholder: 'optional' },
  { path: 'url', label: 'Website', kind: 'text', placeholder: 'optional' },
];

async function newShoot(ctx: Ctx): Promise<void> {
  const l = await listing(ctx, 'shoot');
  if (!l) return;
  const items = l.templates.shoot;
  const v = await askForm('New Shoot from Template', 'Makes a collection set for the shoot with All Photos and smart collections for each stage (Picks, To Edit, Edited, Portfolio, Rejects). Import into All Photos, or set it as the target collection.',
    [{ path: 'template', label: 'Recipe', kind: 'select', options: choices(items) }, { path: 'name', label: 'Shoot name', kind: 'text', placeholder: 'client, event or listing' }, ...IDENTITY],
    { template: items[0]?.id ?? '', name: '', ...l.identity }, 'Create', about(items));
  if (!v) return;
  try {
    const r = await ctx.api.cmd<Shoot>('workflow.setupShoot', { recipe: v.template, name: String(v.name ?? ''), values: { creator: v.creator, email: v.email, url: v.url } });
    toast(`${String(v.name)}: ${plural(Object.keys(r.stages).length, 'stage collection')} ready; delivery presets ${r.exports.map((e) => e.replace('builtin.', '')).join(', ')}`);
  } catch (err) { ctx.fail(err, 'New Shoot'); }
}

async function applyMetadata(ctx: Ctx): Promise<void> {
  const ids = library.targets();
  if (!ids.length) { toast('Select photos first'); return; }
  const l = await listing(ctx, 'metadata');
  if (!l) return;
  const items = l.templates.metadata;
  const v = await askForm('Apply Metadata Template', `Writes the template's copyright and licence fields to ${plural(ids.length, 'photo')}. Creator, email and website are remembered.`,
    [{ path: 'template', label: 'Template', kind: 'select', options: choices(items) }, ...IDENTITY,
      { path: 'client', label: 'Client', kind: 'text', placeholder: 'for client licences' }, { path: 'event', label: 'Event', kind: 'text', placeholder: 'for event and wedding templates' }],
    { template: items[0]?.id ?? '', client: '', event: '', ...l.identity }, 'Apply', about(items));
  if (!v) return;
  try {
    const r = await ctx.api.cmd<{ fields: Record<string, string>; skipped: string[] }>('template.applyMetadata', { ids, template: v.template, values: { creator: v.creator, email: v.email, url: v.url, client: v.client, event: v.event } });
    toast(`${plural(Object.keys(r.fields).length, 'field')} written to ${plural(ids.length, 'photo')}${r.skipped.length ? `; skipped ${r.skipped.join(', ')}` : ''}`);
  } catch (err) { ctx.fail(err, 'Metadata Template'); }
}

async function applyKeywords(ctx: Ctx): Promise<void> {
  const ids = library.targets();
  if (!ids.length) { toast('Select photos first'); return; }
  const l = await listing(ctx, 'keywordSet');
  if (!l) return;
  const items = l.templates.keywordSet;
  const v = await askForm('Apply Keyword Set', `Adds the set's keywords to ${plural(ids.length, 'photo')}. Leave Only empty for all of them.`,
    [{ path: 'template', label: 'Keyword set', kind: 'select', options: choices(items) }, { path: 'only', label: 'Only', kind: 'text', placeholder: 'comma separated subset' }],
    { template: items[0]?.id ?? '', only: '' }, 'Add', (x) => (items.find((t) => t.id === x.template)?.value as string[] | undefined)?.join(', ') ?? '');
  if (!v) return;
  const only = String(v.only ?? '').split(',').map((s) => s.trim()).filter(Boolean);
  try {
    const r = await ctx.api.cmd<{ keywords: string[] }>('template.applyKeywords', { ids, set: v.template, keywords: only.length ? only : undefined });
    toast(`Added ${r.keywords.join(', ')}`);
  } catch (err) { ctx.fail(err, 'Keyword Set'); }
}

async function smartFromTemplate(ctx: Ctx): Promise<void> {
  const l = await listing(ctx, 'smartCollection');
  if (!l) return;
  const items = l.templates.smartCollection;
  const v = await askForm('New Smart Collection from Template', 'Creates a smart collection with the template\'s rules; edit them later like any smart collection.',
    [{ path: 'template', label: 'Template', kind: 'select', options: choices(items) }, { path: 'name', label: 'Name', kind: 'text', placeholder: 'the template name' }],
    { template: items[0]?.id ?? '', name: '' }, 'Create', about(items));
  if (!v) return;
  try {
    const r = await ctx.api.cmd<{ name: string }>('template.smartCollection', { template: v.template, name: String(v.name ?? '') });
    toast(`Smart collection ${r.name} created`);
  } catch (err) { ctx.fail(err, 'Smart Collection'); }
}

async function noiseByIso(ctx: Ctx): Promise<void> {
  const ids = library.targets();
  if (!ids.length) return;
  try {
    const r = await ctx.api.cmd<{ applied: Record<string, number>; underIso800: number; noIso: number }>('develop.noiseByIso', { ids });
    const done = Object.entries(r.applied).map(([k, n]) => `${k}: ${n}`).join(', ');
    toast(`${done || 'Nothing at ISO 800 or above'}${r.underIso800 ? `; ${r.underIso800} under ISO 800 left alone` : ''}${r.noIso ? `; ${r.noIso} without ISO` : ''}`);
  } catch (err) { ctx.fail(err, 'Noise Reduction by ISO'); }
}

export function registerTemplateActions(ctx: Ctx): void {
  const has = () => library.targets().length > 0;
  ctx.commands.add(
    { id: 'workflow.newShoot', label: 'New Shoot from Template...', keys: ['Alt+Shift+Mod+N'], run: () => void newShoot(ctx) },
    { id: 'template.smart', label: 'New Smart Collection from Template...', run: () => void smartFromTemplate(ctx) },
    { id: 'template.metadata', label: 'Apply Metadata Template...', run: () => void applyMetadata(ctx), enabled: has },
    { id: 'template.keywords', label: 'Apply Keyword Set...', run: () => void applyKeywords(ctx), enabled: has },
    { id: 'develop.noiseByIso', label: 'Noise Reduction by ISO', run: () => void noiseByIso(ctx), enabled: has },
  );
}
