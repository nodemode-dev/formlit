import type { Ctx } from '../../app';
import { library } from '../../state/library';
import { askForm } from '../../ui/askform';
import { el, escapeHtml } from '../../ui/dom';
import type { FieldSpec } from '../../ui/form';
import { toast } from '../../ui/toast';

export type MetaPresets = Record<string, Record<string, string>>;

const FIELDS: Array<[string, string]> = [
  ['creator', 'Creator'], ['creatorJob', 'Job Title'], ['creatorEmail', 'Email'], ['creatorPhone', 'Phone'], ['creatorUrl', 'Website'],
  ['creatorCity', 'City'], ['creatorCountry', 'Country'], ['copyright', 'Copyright'], ['copyrightStatus', 'Copyright Status'], ['rightsUsage', 'Rights Usage Terms'],
  ['copyrightUrl', 'Copyright Info URL'], ['credit', 'Credit Line'], ['source', 'Source'], ['instructions', 'Instructions'], ['event', 'Event'],
];

export async function loadMetaPresets(ctx: Ctx): Promise<MetaPresets> {
  try { return ((await ctx.api.cmd<Record<string, unknown>>('prefs.get')).metadataPresets as MetaPresets) ?? {}; } catch { return {}; }
}

export class MetadataPresets {
  readonly root = el('<div class="fl-row fl-mp"><select class="cv-select fl-grow" aria-label="Metadata preset"></select><button class="cv-btn fl-btn-sm" type="button" data-a="apply">Apply</button><button class="cv-btn fl-btn-sm" type="button" data-a="edit">Edit...</button></div>');
  private readonly select = this.root.querySelector('select') as HTMLSelectElement;
  private presets: MetaPresets = {};

  constructor(private readonly ctx: Ctx) {
    void loadMetaPresets(ctx).then((p) => { this.presets = p; this.render(); });
    this.root.addEventListener('click', (e) => {
      const a = (e.target as HTMLElement).closest<HTMLElement>('[data-a]')?.dataset.a;
      if (a === 'apply') void this.apply();
      else if (a === 'edit') void this.edit();
    });
  }

  private render(): void {
    const html = `<option value="">Metadata preset...</option>${Object.keys(this.presets).sort().map((n) => `<option value="${escapeHtml(n)}">${escapeHtml(n)}</option>`).join('')}`;
    if (this.select.dataset.key !== html) { this.select.dataset.key = html; this.select.innerHTML = html; }
  }

  private async apply(): Promise<void> {
    const p = this.presets[this.select.value];
    const ids = library.targets();
    if (!p || !ids.length) { toast(ids.length ? 'Choose a preset first' : 'Select photos first'); return; }
    try { await this.ctx.api.cmd('photo.setMeta', { ids, fields: p }); toast(`Applied ${this.select.value} to ${ids.length} ${ids.length === 1 ? 'photo' : 'photos'}`); } catch (err) { this.ctx.fail(err); }
  }

  private async edit(): Promise<void> {
    const name = this.select.value;
    const cur = this.presets[name] ?? {};
    const specs: FieldSpec[] = [{ path: 'name', label: 'Preset name', kind: 'text' }, ...FIELDS.map(([k, l]) => ({ path: k, label: l, kind: 'text' as const }))];
    const v = await askForm(name ? 'Edit Metadata Preset' : 'New Metadata Preset', 'Fields left empty are not changed when the preset is applied. Clear the name to delete the preset.', specs, { name: name || 'My Copyright', ...cur }, 'Save');
    if (!v) return;
    const next = { ...this.presets };
    if (name) delete next[name];
    const newName = String(v.name ?? '').trim();
    if (newName) next[newName] = Object.fromEntries(FIELDS.map(([k]) => [k, String(v[k] ?? '').trim()]).filter(([, x]) => x));
    try {
      await this.ctx.api.cmd('prefs.set', { values: { metadataPresets: next } });
      this.presets = next;
      this.render();
      if (newName) this.select.value = newName;
    } catch (err) { this.ctx.fail(err); }
  }
}
