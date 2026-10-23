import type { Ctx } from '../../app';
import { catalog } from '../../state/catalog';
import { confirmAction, Dialog, promptName } from '../../ui/dialogs';
import { el, escapeHtml, patchList, q, setClass, setHidden, setText, setValue } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { toast } from '../../ui/toast';
import { patternOptions } from '../shared/templates';
import { loadMetaPresets, type MetaPresets } from './metadata-presets';

interface Root { name: string; path: string; kind: string }
interface ScanFile { path: string; name: string; size: number; mtime: number; kind: string; duplicate: boolean; inCatalog: boolean }

const PREFS_KEY = 'formlit_import';
const RENAMES: Array<[string, string]> = [['', 'Filename (unchanged)'], ['{date:%Y%m%d}-{name}', 'Date - Camera Name'], ['{custom}-{seq:3}', 'Name - Sequence'], ['{date:%Y-%m-%d}-{seq:4}', 'Date - Sequence'], ['{shoot}-{name}', 'Shoot Name - Filename']];
const ORGANIZE: Array<[string, string]> = [['{date:%Y}/{date:%Y-%m-%d}', 'By date: 2026/2026-10-07'], ['{date:%Y}/{date:%m}', 'By date: 2026/10'], ['{date:%Y-%m-%d}', 'By date: 2026-10-07'], ['', 'Into one folder']];

interface Prefs { mode: string; recursive: boolean; skipDup: boolean; previews: string; smart: boolean; eject: boolean; rename: string; organize: string; destination: string; backup: string; preset: string; copyright: string; creator: string; last: string }
type ImportPreset = Omit<Prefs, 'last'>;
const PRESET_KEYS: Array<keyof ImportPreset> = ['mode', 'recursive', 'skipDup', 'previews', 'smart', 'eject', 'rename', 'organize', 'destination', 'backup', 'preset', 'copyright', 'creator'];

function readPrefs(): Prefs {
  const d: Prefs = { mode: 'add', recursive: true, skipDup: true, previews: 'embedded', smart: false, eject: false, rename: '', organize: ORGANIZE[0][0], destination: '', backup: '', preset: '', copyright: '', creator: '', last: '' };
  try { return { ...d, ...(JSON.parse(localStorage.getItem(PREFS_KEY) || '{}') as Partial<Prefs>) }; } catch { return d; }
}

class ImportDialog extends Dialog {
  private prefs = readPrefs();
  private metaPresets: MetaPresets = {};
  private path = '';
  private files: ScanFile[] = [];
  private readonly checked = new Set<string>();
  private readonly crumbs: HTMLElement;
  private readonly roots: HTMLElement;
  private readonly dirs: HTMLElement;
  private readonly grid: HTMLElement;
  private readonly summary: HTMLElement;
  private readonly status: HTMLElement;
  private readonly go: HTMLButtonElement;
  private readonly dest: HTMLElement;
  private readonly presetSel = el<HTMLSelectElement>('<select class="cv-select fl-imp-preset" aria-label="Import preset"></select>');
  private importPresets: Record<string, ImportPreset> = {};
  private volumes: string[] = [];
  private presetName = '';
  private seq = 0;
  private templatesFilled = false;

  constructor(private readonly ctx: Ctx) {
    super('Import Photos and Videos', 1180);
    q<HTMLElement>(this.scrim, '.cv-dialog').classList.add('fl-import');
    const layout = el(`<div class="fl-imp">
<div class="fl-imp-top"><div class="cv-seg fl-imp-mode"><button type="button" data-mode="add">Add</button><button type="button" data-mode="dng">Copy as DNG</button><button type="button" data-mode="copy">Copy</button><button type="button" data-mode="move">Move</button></div><span class="fl-imp-modehint"></span><span class="fl-tb-spacer"></span><div class="fl-imp-crumbs"></div></div>
<div class="fl-imp-body">
<aside class="fl-imp-side"><div class="fl-sub">Source</div><div class="fl-imp-roots"></div><div class="fl-sub">Folders</div><div class="fl-imp-dirs"></div><label class="fl-check"><input type="checkbox" data-pref="recursive"> Include Subfolders</label></aside>
<section class="fl-imp-main"><div class="fl-imp-bar"><span class="fl-imp-status"></span><span class="fl-tb-spacer"></span><button class="cv-btn cv-btn-ghost" type="button" data-all="1">Check All</button><button class="cv-btn cv-btn-ghost" type="button" data-all="0">Uncheck All</button></div><div class="fl-imp-grid"></div></section>
<aside class="fl-imp-opts">
<div class="fl-sub">File Handling</div>
<label class="fl-opt"><span>Build Previews</span><select class="cv-select" data-pref="previews"><option value="embedded">Embedded and Sidecar</option><option value="standard">Standard</option><option value="1:1">1:1</option></select></label>
<label class="fl-check"><input type="checkbox" data-pref="smart"> Build Intelligent Previews</label>
<label class="fl-check fl-imp-eject" hidden><input type="checkbox" data-pref="eject"> Eject after import</label>
<label class="fl-check"><input type="checkbox" data-pref="skipDup"> Don't Import Suspected Duplicates</label>
<label class="fl-opt"><span>Add to Collection</span><select class="cv-select" data-collection><option value="">None</option></select></label>
<div class="fl-sub">File Renaming</div>
<label class="fl-opt"><span>Template</span><select class="cv-select" data-preset-for="rename">${RENAMES.map(([v, l]) => `<option value="${escapeHtml(v)}">${l}</option>`).join('')}<option value="__custom">Custom</option></select></label>
<label class="fl-opt"><span>Pattern</span><input class="cv-input" type="text" data-pref="rename" spellcheck="false" placeholder="unchanged"></label>
<div class="fl-imp-tokens">{name} {seq:3} {num} {date:%Y%m%d} {camera} {lens} {iso} {custom} {shoot} {folder}</div>
<label class="fl-opt"><span>Custom Text</span><input class="cv-input" type="text" data-custom placeholder="Shoot name"></label>
<div class="fl-sub">Apply During Import</div>
<label class="fl-opt"><span>Develop Settings</span><select class="cv-select" data-pref="preset"><option value="">None</option></select></label>
<label class="fl-opt"><span>Metadata</span><select class="cv-select" data-metapreset><option value="">None</option></select></label>
<label class="fl-opt"><span>Creator</span><input class="cv-input" type="text" data-pref="creator" spellcheck="false"></label>
<label class="fl-opt"><span>Copyright</span><input class="cv-input" type="text" data-pref="copyright" spellcheck="false"></label>
<label class="fl-opt"><span>Keywords</span><input class="cv-input" type="text" data-keywords placeholder="comma separated" spellcheck="false"></label>
<div class="fl-imp-dest"><div class="fl-sub">Destination</div>
<label class="fl-opt"><span>To</span><input class="cv-input" type="text" data-pref="destination" spellcheck="false"></label>
<label class="fl-opt"><span>Organize</span><select class="cv-select" data-preset-for="organize">${ORGANIZE.map(([v, l]) => `<option value="${escapeHtml(v)}">${l}</option>`).join('')}<option value="__custom">Custom</option></select></label>
<label class="fl-opt"><span>Folders</span><input class="cv-input" type="text" data-pref="organize" spellcheck="false" placeholder="into one folder"></label>
<label class="fl-opt"><span>Second Copy To</span><input class="cv-input" type="text" data-pref="backup" placeholder="No second copy" spellcheck="false"></label></div>
</aside></div></div>`);
    this.body.appendChild(layout);
    this.crumbs = q(layout, '.fl-imp-crumbs');
    this.roots = q(layout, '.fl-imp-roots');
    this.dirs = q(layout, '.fl-imp-dirs');
    this.grid = q(layout, '.fl-imp-grid');
    this.status = q(layout, '.fl-imp-status');
    this.dest = q(layout, '.fl-imp-dest');
    this.summary = el('<span class="fl-imp-summary"></span>');
    this.foot.append(this.presetSel, this.summary);
    this.presetSel.addEventListener('change', () => void this.choosePreset(this.presetSel.value));
    this.button('Cancel', 'ghost', () => this.close());
    this.go = this.button('Import', 'primary', () => void this.start());

    q(layout, '.fl-imp-mode').addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-mode]');
      if (b) { this.prefs.mode = b.dataset.mode as string; this.sync(); }
    });
    layout.addEventListener('change', (e) => {
      const t = e.target as HTMLInputElement;
      const pk = t.dataset.presetFor as 'rename' | 'organize' | undefined;
      if (pk) {
        if (t.value !== '__custom') { this.prefs[pk] = t.value; this.save(); this.syncFields(); }
        else q<HTMLInputElement>(this.body, `input[data-pref="${pk}"]`).focus();
        return;
      }
      const k = t.dataset.pref as keyof Prefs | undefined;
      if (k) {
        (this.prefs as unknown as Record<string, unknown>)[k] = t.type === 'checkbox' ? t.checked : t.value;
        this.save();
        if (k === 'recursive') void this.scan();
        if (k === 'rename' || k === 'organize') this.syncFields();
        this.sync();
      }
      if (t.dataset.file !== undefined) {
        if (t.checked) this.checked.add(t.dataset.file); else this.checked.delete(t.dataset.file);
        this.sync();
      }
    });
    q(layout, '.fl-imp-bar').addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-all]');
      if (!b) return;
      this.checked.clear();
      if (b.dataset.all === '1') for (const f of this.files) if (!(f.duplicate && this.prefs.skipDup)) this.checked.add(f.path);
      this.renderFiles();
      this.sync();
    });
    this.roots.addEventListener('click', (e) => { const r = (e.target as HTMLElement).closest<HTMLElement>('[data-path]'); if (r) void this.browse(r.dataset.path as string); });
    this.dirs.addEventListener('click', (e) => { const r = (e.target as HTMLElement).closest<HTMLElement>('[data-path]'); if (r) void this.browse(r.dataset.path as string); });
    this.crumbs.addEventListener('click', (e) => { const r = (e.target as HTMLElement).closest<HTMLElement>('[data-path]'); if (r) void this.browse(r.dataset.path as string); });
  }

  private save(): void { try { localStorage.setItem(PREFS_KEY, JSON.stringify(this.prefs)); } catch { return; } }

  private onVolume(): boolean {
    return this.volumes.some((v) => v.length > 1 && this.path.startsWith(v));
  }

  private fillPresets(): void {
    const names = Object.keys(this.importPresets).sort();
    if (!names.includes(this.presetName)) this.presetName = '';
    const opts: Array<[string, string]> = [['', 'Import Preset: None'], ...names.map((n): [string, string] => [n, `Import Preset: ${n}`]), ['__save', 'Save Current Settings as New Preset...']];
    if (this.presetName) opts.push(['__delete', `Delete Preset "${this.presetName}"...`]);
    const key = opts.map((o) => o.join('=')).join('|');
    if (this.presetSel.dataset.key !== key) { this.presetSel.dataset.key = key; this.presetSel.replaceChildren(...opts.map(([v, l]) => new Option(l, v))); }
    this.presetSel.value = this.presetName;
  }

  private async storePresets(): Promise<void> {
    try { await this.ctx.api.cmd('prefs.set', { values: { importPresets: this.importPresets } }); } catch (err) { this.ctx.fail(err, 'Import presets'); }
  }

  private async choosePreset(v: string): Promise<void> {
    if (v === '__save') {
      const name = (await promptName('New Import Preset', this.presetName || 'My Import', 'Create'))?.trim();
      if (name) {
        this.importPresets[name] = Object.fromEntries(PRESET_KEYS.map((k) => [k, this.prefs[k]])) as ImportPreset;
        this.presetName = name;
        await this.storePresets();
      }
    } else if (v === '__delete') {
      const name = this.presetName;
      if (name && await confirmAction('Delete Import Preset', `Delete the import preset "${name}"? Photos already imported are not affected.`, 'Delete', true)) {
        delete this.importPresets[name];
        this.presetName = '';
        await this.storePresets();
      }
    } else {
      this.presetName = v;
      const p = this.importPresets[v];
      if (p) {
        this.prefs = { ...this.prefs, ...p };
        this.save();
        this.syncFields();
        this.sync();
        if (p.recursive !== undefined) void this.scan();
      }
    }
    this.fillPresets();
  }

  private async fillTemplates(): Promise<void> {
    if (this.templatesFilled) return;
    const [names, folders] = await Promise.all([patternOptions(this.ctx, 'filename'), patternOptions(this.ctx, 'folder')]);
    if (!names.length || !folders.length) return;
    this.templatesFilled = true;
    const fill = (key: 'rename' | 'organize', listed: Array<[string, string, string]>, base: Array<[string, string]>): void => {
      const rows = listed.map(([v, l, d]): [string, string, string] => [key === 'rename' && v === '{name}' ? '' : v, l, d]);
      for (const [v, l] of base) if (!rows.some(([x, y]) => x === v || y === l)) rows.push([v, l, '']);
      const sel = q<HTMLSelectElement>(this.body, `select[data-preset-for="${key}"]`);
      sel.replaceChildren(...rows.map(([v, l, d]) => { const o = new Option(l, v); o.title = d; return o; }), new Option('Custom', '__custom'));
    };
    fill('rename', names, RENAMES);
    fill('organize', folders, ORGANIZE);
    this.syncFields();
  }

  async show(start?: string): Promise<void> {
    await this.fillTemplates();
    this.open(this.go);
    const roots = await this.ctx.api.get<{ roots: Root[]; library: string }>('/api/files/roots');
    if (!this.prefs.destination) this.prefs.destination = roots.library;
    this.volumes = roots.roots.filter((r) => r.kind === 'volume').map((r) => r.path);
    patchList(this.roots, roots.roots, {
      key: (r) => r.path,
      create: (r) => el(`<button class="fl-imp-row" type="button" data-path="${escapeHtml(r.path)}">${icon(r.kind === 'volume' || r.kind === 'drive' ? 'download' : 'folder', 14)}<span>${escapeHtml(r.name)}</span></button>`),
      update: () => undefined,
    });
    const presets = await this.ctx.api.cmd<{ presets: Array<{ id: string; name: string; group: string }> }>('preset.list').catch(() => ({ presets: [] }));
    const sel = q<HTMLSelectElement>(this.body, '[data-pref="preset"]');
    if (sel.options.length <= 1) for (const p of presets.presets) sel.add(new Option(`${p.group} / ${p.name}`, p.id));
    this.metaPresets = await loadMetaPresets(this.ctx);
    const mp = q<HTMLSelectElement>(this.body, '[data-metapreset]');
    const keep = mp.value;
    mp.length = 1;
    for (const n of Object.keys(this.metaPresets).sort()) mp.add(new Option(n, n));
    mp.value = keep in this.metaPresets ? keep : '';
    const cols = q<HTMLSelectElement>(this.body, '[data-collection]');
    cols.length = 1;
    for (const c of catalog.tree.collections.filter((x) => x.kind === 'collection')) cols.add(new Option(c.name, String(c.id)));
    const stored = await this.ctx.api.cmd<Record<string, unknown>>('prefs.get').catch(() => ({} as Record<string, unknown>));
    this.importPresets = (stored.importPresets as Record<string, ImportPreset> | undefined) ?? {};
    this.fillPresets();
    this.syncFields();
    await this.browse(start || this.prefs.last || roots.roots.find((r) => r.kind === 'pictures')?.path || roots.roots[0]?.path || '/');
  }

  private syncFields(): void {
    for (const input of Array.from(this.body.querySelectorAll<HTMLInputElement>('[data-pref]'))) {
      const v = (this.prefs as unknown as Record<string, unknown>)[input.dataset.pref as string];
      if (input.type === 'checkbox') input.checked = !!v; else setValue(input, String(v ?? ''));
    }
    for (const sel of Array.from(this.body.querySelectorAll<HTMLSelectElement>('select[data-preset-for]'))) {
      const v = String((this.prefs as unknown as Record<string, unknown>)[sel.dataset.presetFor as string] ?? '');
      setValue(sel, Array.from(sel.options).some((o) => o.value === v) ? v : '__custom');
    }
  }

  private async browse(path: string): Promise<void> {
    const seq = ++this.seq;
    try {
      const r = await this.ctx.api.get<{ path: string; parent: string | null; dirs: Array<{ name: string; path: string }> }>(`/api/files/list?path=${encodeURIComponent(path)}`);
      if (seq !== this.seq) return;
      this.path = r.path;
      this.prefs.last = r.path;
      this.save();
      const parts = r.path.split(/[\\/]/).filter(Boolean);
      const sep = r.path.includes('\\') ? '\\' : '/';
      const crumbs = parts.map((p, i) => ({ name: p, path: (r.path.startsWith(sep) ? sep : '') + parts.slice(0, i + 1).join(sep) + (i === 0 && /^[A-Z]:$/.test(p) ? sep : '') }));
      this.crumbs.innerHTML = crumbs.map((c) => `<button type="button" data-path="${escapeHtml(c.path)}">${escapeHtml(c.name)}</button>`).join(`<span>${icon('chevronRight', 10)}</span>`);
      const dirs = [...(r.parent ? [{ name: '..', path: r.parent }] : []), ...r.dirs];
      this.dirs.replaceChildren(...dirs.map((d) => el(`<button class="fl-imp-row" type="button" data-path="${escapeHtml(d.path)}">${icon(d.name === '..' ? 'chevronUp' : 'folder', 14)}<span>${escapeHtml(d.name)}</span></button>`)));
      const rows = Array.from(this.roots.children) as HTMLElement[];
      const best = rows.map((b) => b.dataset.path ?? '').filter((p) => p && r.path.startsWith(p)).sort((a, b) => b.length - a.length)[0];
      for (const b of rows) setClass(b, 'is-on', b.dataset.path === best);
      await this.scan();
    } catch (err) { this.ctx.fail(err); }
  }

  private async scan(): Promise<void> {
    const seq = this.seq;
    setText(this.status, 'Looking for photos...');
    try {
      const r = await this.ctx.api.cmd<{ files: ScanFile[]; duplicates: number }>('library.scan', { paths: [this.path], recursive: this.prefs.recursive });
      if (seq !== this.seq) return;
      this.files = r.files.slice(0, 5000);
      this.checked.clear();
      for (const f of this.files) if (!(f.duplicate && this.prefs.skipDup)) this.checked.add(f.path);
      setText(this.status, `${r.files.length} photo${r.files.length === 1 ? '' : 's'}${r.duplicates ? ` · ${r.duplicates} already in the catalog` : ''}`);
      this.renderFiles();
      this.sync();
    } catch (err) { setText(this.status, ''); this.ctx.fail(err); }
  }

  private renderFiles(): void {
    patchList(this.grid, this.files, {
      key: (f) => f.path,
      create: (f) => {
        const n = el(`<label class="fl-imp-cell"><img loading="lazy" decoding="async" alt="" src="${this.ctx.api.url(`/api/files/thumb?path=${encodeURIComponent(f.path)}&long=240`)}"><input type="checkbox" data-file="${escapeHtml(f.path)}"><span class="fl-imp-name">${escapeHtml(f.name)}</span></label>`);
        return n;
      },
      update: (n, f) => {
        const cb = q<HTMLInputElement>(n, 'input');
        cb.checked = this.checked.has(f.path);
        setClass(n, 'is-dup', f.duplicate);
        setClass(n, 'is-on', cb.checked);
      },
    });
    for (const n of Array.from(this.grid.children) as HTMLElement[]) {
      const f = this.files.find((x) => x.path === (n.dataset.key ?? ''));
      if (!f) continue;
      const cb = q<HTMLInputElement>(n, 'input');
      cb.checked = this.checked.has(f.path);
      setClass(n, 'is-dup', f.duplicate);
      setClass(n, 'is-on', cb.checked);
    }
  }

  private sync(): void {
    for (const b of Array.from(this.body.querySelectorAll<HTMLElement>('[data-mode]'))) setClass(b, 'is-on', b.dataset.mode === this.prefs.mode);
    setText(q(this.body, '.fl-imp-modehint'), this.prefs.mode === 'add' ? 'Add photos to the catalog without moving them' : this.prefs.mode === 'copy' ? 'Copy photos to a new location and add them' : this.prefs.mode === 'dng' ? 'Convert raw files to DNG in a new location and add them' : 'Move photos to a new location and add them');
    setHidden(q(this.body, '.fl-imp-eject'), !this.onVolume());
    this.dest.hidden = this.prefs.mode === 'add';
    for (const n of Array.from(this.grid.children) as HTMLElement[]) setClass(n, 'is-on', this.checked.has(n.dataset.key ?? ''));
    const n = this.checked.size;
    const bytes = this.files.filter((f) => this.checked.has(f.path)).reduce((a, f) => a + f.size, 0);
    setText(this.summary, `${n} photo${n === 1 ? '' : 's'} · ${(bytes / 1073741824).toFixed(2)} GB`);
    this.go.disabled = n === 0;
  }

  private async start(): Promise<void> {
    const paths = this.files.filter((f) => this.checked.has(f.path)).map((f) => f.path);
    if (!paths.length) return;
    const keywords = q<HTMLInputElement>(this.body, '[data-keywords]').value.split(',').map((s) => s.trim()).filter(Boolean);
    const col = q<HTMLSelectElement>(this.body, '[data-collection]').value;
    const metaName = q<HTMLSelectElement>(this.body, '[data-metapreset]').value;
    const metadata: Record<string, string> = { ...(metaName ? this.metaPresets[metaName] ?? {} : {}) };
    if (this.prefs.creator) metadata.creator = this.prefs.creator;
    if (this.prefs.copyright) metadata.copyright = this.prefs.copyright;
    const params = {
      paths, mode: this.prefs.mode, destination: this.prefs.destination, folderTemplate: this.prefs.organize, renameTemplate: this.prefs.rename,
      custom: q<HTMLInputElement>(this.body, '[data-custom]').value, develop: this.prefs.preset || null, metadata, keywords, collection: col ? Number(col) : null,
      skipDuplicates: this.prefs.skipDup, recursive: false, buildPreviews: this.prefs.previews, backup: this.prefs.mode === 'add' ? '' : this.prefs.backup.trim(),
      smartPreviews: this.prefs.smart, eject: this.prefs.eject && this.onVolume() ? this.path : '',
    };
    this.close();
    try {
      await this.ctx.api.cmd('library.import', params);
      toast(`Importing ${paths.length} photo${paths.length === 1 ? '' : 's'}`);
    } catch (err) { this.ctx.fail(err, 'Import'); }
  }
}

let dialog: ImportDialog | null = null;

export function openImport(ctx: Ctx, start?: string): void {
  dialog ??= new ImportDialog(ctx);
  void dialog.show(start);
}

export async function importDropped(ctx: Ctx, files: FileList): Promise<void> {
  const form = new FormData();
  for (const f of Array.from(files)) form.append('files', f, f.name);
  try {
    const r = await ctx.api.upload<{ paths: string[]; skipped: string[] }>('/api/files/upload', form);
    if (!r.paths.length) { toast('No supported photos in what was dropped', 'error'); return; }
    await ctx.api.cmd('library.import', { paths: r.paths, mode: 'add' });
    toast(`Importing ${r.paths.length} photo${r.paths.length === 1 ? '' : 's'}`);
  } catch (err) { ctx.fail(err, 'Import'); }
}
