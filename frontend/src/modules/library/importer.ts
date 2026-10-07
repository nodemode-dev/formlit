import type { Ctx } from '../../app';
import { catalog } from '../../state/catalog';
import { Dialog } from '../../ui/dialogs';
import { el, escapeHtml, patchList, q, setClass, setText, setValue } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { toast } from '../../ui/toast';

interface Root { name: string; path: string; kind: string }
interface ScanFile { path: string; name: string; size: number; mtime: number; kind: string; duplicate: boolean; inCatalog: boolean }

const PREFS_KEY = 'formlit_import';
const RENAMES: Array<[string, string]> = [['', 'Filename (unchanged)'], ['{date:%Y%m%d}-{name}', 'Date - Filename'], ['{custom}-{seq:3}', 'Custom Name - Sequence'], ['{date:%Y-%m-%d}-{seq:4}', 'Date - Sequence'], ['{shoot}-{name}', 'Shoot Name - Filename']];
const ORGANIZE: Array<[string, string]> = [['{date:%Y}/{date:%Y-%m-%d}', 'By date: 2026/2026-10-07'], ['{date:%Y}/{date:%m}', 'By date: 2026/10'], ['{date:%Y-%m-%d}', 'By date: 2026-10-07'], ['', 'Into one folder']];

interface Prefs { mode: string; recursive: boolean; skipDup: boolean; previews: string; rename: string; organize: string; destination: string; preset: string; copyright: string; creator: string; last: string }

function readPrefs(): Prefs {
  const d: Prefs = { mode: 'add', recursive: true, skipDup: true, previews: 'embedded', rename: '', organize: ORGANIZE[0][0], destination: '', preset: '', copyright: '', creator: '', last: '' };
  try { return { ...d, ...(JSON.parse(localStorage.getItem(PREFS_KEY) || '{}') as Partial<Prefs>) }; } catch { return d; }
}

class ImportDialog extends Dialog {
  private prefs = readPrefs();
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
  private seq = 0;

  constructor(private readonly ctx: Ctx) {
    super('Import Photos and Videos', 1180);
    q<HTMLElement>(this.scrim, '.cv-dialog').classList.add('fl-import');
    const layout = el(`<div class="fl-imp">
<div class="fl-imp-top"><div class="cv-seg fl-imp-mode"><button type="button" data-mode="add">Add</button><button type="button" data-mode="copy">Copy</button><button type="button" data-mode="move">Move</button></div><span class="fl-imp-modehint"></span><span class="fl-tb-spacer"></span><div class="fl-imp-crumbs"></div></div>
<div class="fl-imp-body">
<aside class="fl-imp-side"><div class="fl-sub">Source</div><div class="fl-imp-roots"></div><div class="fl-sub">Folders</div><div class="fl-imp-dirs"></div><label class="fl-check"><input type="checkbox" data-pref="recursive"> Include Subfolders</label></aside>
<section class="fl-imp-main"><div class="fl-imp-bar"><span class="fl-imp-status"></span><span class="fl-tb-spacer"></span><button class="cv-btn cv-btn-ghost" type="button" data-all="1">Check All</button><button class="cv-btn cv-btn-ghost" type="button" data-all="0">Uncheck All</button></div><div class="fl-imp-grid"></div></section>
<aside class="fl-imp-opts">
<div class="fl-sub">File Handling</div>
<label class="fl-opt"><span>Build Previews</span><select class="cv-select" data-pref="previews"><option value="embedded">Embedded and Sidecar</option><option value="standard">Standard</option><option value="1:1">1:1</option></select></label>
<label class="fl-check"><input type="checkbox" data-pref="skipDup"> Don't Import Suspected Duplicates</label>
<label class="fl-opt"><span>Add to Collection</span><select class="cv-select" data-collection><option value="">None</option></select></label>
<div class="fl-sub">File Renaming</div>
<label class="fl-opt"><span>Template</span><select class="cv-select" data-pref="rename">${RENAMES.map(([v, l]) => `<option value="${escapeHtml(v)}">${l}</option>`).join('')}</select></label>
<label class="fl-opt"><span>Custom Text</span><input class="cv-input" type="text" data-custom placeholder="Shoot name"></label>
<div class="fl-sub">Apply During Import</div>
<label class="fl-opt"><span>Develop Settings</span><select class="cv-select" data-pref="preset"><option value="">None</option></select></label>
<label class="fl-opt"><span>Creator</span><input class="cv-input" type="text" data-pref="creator" spellcheck="false"></label>
<label class="fl-opt"><span>Copyright</span><input class="cv-input" type="text" data-pref="copyright" spellcheck="false"></label>
<label class="fl-opt"><span>Keywords</span><input class="cv-input" type="text" data-keywords placeholder="comma separated" spellcheck="false"></label>
<div class="fl-imp-dest"><div class="fl-sub">Destination</div>
<label class="fl-opt"><span>To</span><input class="cv-input" type="text" data-pref="destination" spellcheck="false"></label>
<label class="fl-opt"><span>Organize</span><select class="cv-select" data-pref="organize">${ORGANIZE.map(([v, l]) => `<option value="${escapeHtml(v)}">${l}</option>`).join('')}</select></label></div>
</aside></div></div>`);
    this.body.appendChild(layout);
    this.crumbs = q(layout, '.fl-imp-crumbs');
    this.roots = q(layout, '.fl-imp-roots');
    this.dirs = q(layout, '.fl-imp-dirs');
    this.grid = q(layout, '.fl-imp-grid');
    this.status = q(layout, '.fl-imp-status');
    this.dest = q(layout, '.fl-imp-dest');
    this.summary = el('<span class="fl-imp-summary"></span>');
    this.foot.appendChild(this.summary);
    this.button('Cancel', 'ghost', () => this.close());
    this.go = this.button('Import', 'primary', () => void this.start());

    q(layout, '.fl-imp-mode').addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-mode]');
      if (b) { this.prefs.mode = b.dataset.mode as string; this.sync(); }
    });
    layout.addEventListener('change', (e) => {
      const t = e.target as HTMLInputElement;
      const k = t.dataset.pref as keyof Prefs | undefined;
      if (k) {
        (this.prefs as unknown as Record<string, unknown>)[k] = t.type === 'checkbox' ? t.checked : t.value;
        this.save();
        if (k === 'recursive') void this.scan();
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

  async show(start?: string): Promise<void> {
    this.open(this.go);
    const roots = await this.ctx.api.get<{ roots: Root[]; library: string }>('/api/files/roots');
    if (!this.prefs.destination) this.prefs.destination = roots.library;
    patchList(this.roots, roots.roots, {
      key: (r) => r.path,
      create: (r) => el(`<button class="fl-imp-row" type="button" data-path="${escapeHtml(r.path)}">${icon(r.kind === 'volume' || r.kind === 'drive' ? 'download' : 'folder', 14)}<span>${escapeHtml(r.name)}</span></button>`),
      update: () => undefined,
    });
    const presets = await this.ctx.api.cmd<{ presets: Array<{ id: string; name: string; group: string }> }>('preset.list').catch(() => ({ presets: [] }));
    const sel = q<HTMLSelectElement>(this.body, '[data-pref="preset"]');
    if (sel.options.length <= 1) for (const p of presets.presets) sel.add(new Option(`${p.group} / ${p.name}`, p.id));
    const cols = q<HTMLSelectElement>(this.body, '[data-collection]');
    cols.length = 1;
    for (const c of catalog.tree.collections.filter((x) => x.kind === 'collection')) cols.add(new Option(c.name, String(c.id)));
    this.syncFields();
    await this.browse(start || this.prefs.last || roots.roots.find((r) => r.kind === 'pictures')?.path || roots.roots[0]?.path || '/');
  }

  private syncFields(): void {
    for (const input of Array.from(this.body.querySelectorAll<HTMLInputElement>('[data-pref]'))) {
      const v = (this.prefs as unknown as Record<string, unknown>)[input.dataset.pref as string];
      if (input.type === 'checkbox') input.checked = !!v; else setValue(input, String(v ?? ''));
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
      for (const b of Array.from(this.roots.children) as HTMLElement[]) setClass(b, 'is-on', r.path.startsWith(b.dataset.path ?? '\u0000'));
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
    setText(q(this.body, '.fl-imp-modehint'), this.prefs.mode === 'add' ? 'Add photos to the catalog without moving them' : this.prefs.mode === 'copy' ? 'Copy photos to a new location and add them' : 'Move photos to a new location and add them');
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
    const metadata: Record<string, string> = {};
    if (this.prefs.creator) metadata.creator = this.prefs.creator;
    if (this.prefs.copyright) metadata.copyright = this.prefs.copyright;
    const params = {
      paths, mode: this.prefs.mode, destination: this.prefs.destination, folderTemplate: this.prefs.organize, renameTemplate: this.prefs.rename,
      custom: q<HTMLInputElement>(this.body, '[data-custom]').value, develop: this.prefs.preset || null, metadata, keywords, collection: col ? Number(col) : null,
      skipDuplicates: this.prefs.skipDup, recursive: false, buildPreviews: this.prefs.previews,
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
