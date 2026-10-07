import { api } from '../io/api';
import { Dialog } from './dialogs';
import { el, escapeHtml, patchList, setText } from './dom';
import { icon } from './icons';

interface Root { name: string; path: string; kind: string }
interface Listing { path: string; parent: string | null; dirs: Array<{ name: string; path: string }> }
interface Row { path: string; name: string; up?: boolean }

class FolderPicker extends Dialog {
  private readonly lead = el('<p class="cv-note fl-fp-lead"></p>');
  private readonly roots = el('<div class="fl-fp-roots"></div>');
  private readonly dirs = el('<div class="fl-fp-dirs"></div>');
  private readonly pathInput = el<HTMLInputElement>('<input class="cv-input fl-fp-path" type="text" spellcheck="false" aria-label="Folder">');
  private readonly ok: HTMLButtonElement;
  private resolve: ((v: string | null) => void) | null = null;
  private seq = 0;

  constructor() {
    super('Choose Folder', 640);
    const wrap = el('<div class="fl-fp"></div>');
    wrap.append(this.roots, this.dirs);
    this.body.append(this.lead, wrap, this.pathInput);
    this.button('Cancel', 'ghost', () => this.finish(null));
    this.ok = this.button('Choose', 'primary', () => this.finish(this.pathInput.value.trim() || null));
    this.onClose = () => this.finish(null);
    const go = (e: Event) => { const r = (e.target as HTMLElement).closest<HTMLElement>('[data-path]'); if (r) void this.browse(r.dataset.path as string); };
    this.roots.addEventListener('click', go);
    this.dirs.addEventListener('click', go);
    this.dirs.addEventListener('dblclick', (e) => { const r = (e.target as HTMLElement).closest<HTMLElement>('[data-path]'); if (r) this.finish(r.dataset.path as string); });
    this.pathInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); void this.browse(this.pathInput.value.trim()); } });
  }

  ask(title: string, lead: string, start: string, okLabel: string): Promise<string | null> {
    this.setTitle(title);
    setText(this.lead, lead);
    setText(this.ok, okLabel);
    this.open(this.pathInput);
    void this.load(start);
    return new Promise((r) => { this.resolve = r; });
  }

  private async load(start: string): Promise<void> {
    try {
      const r = await api.get<{ roots: Root[]; library: string }>('/api/files/roots');
      patchList<Root>(this.roots, r.roots, {
        key: (x) => x.path,
        create: (x) => el(`<button class="fl-imp-row" type="button" data-path="${escapeHtml(x.path)}">${icon(x.kind === 'volume' || x.kind === 'drive' ? 'download' : 'folder', 14)}<span>${escapeHtml(x.name)}</span></button>`),
        update: () => undefined,
      });
      await this.browse(start || r.library || r.roots[0]?.path || '/');
    } catch { await this.browse(start || '/'); }
  }

  private async browse(path: string): Promise<void> {
    const seq = ++this.seq;
    try {
      const r = await api.get<Listing>(`/api/files/list?path=${encodeURIComponent(path)}`);
      if (seq !== this.seq) return;
      if (this.pathInput.value !== r.path) this.pathInput.value = r.path;
      const rows: Row[] = [...(r.parent ? [{ path: r.parent, name: '..', up: true }] : []), ...r.dirs.map((d) => ({ path: d.path, name: d.name }))];
      patchList<Row>(this.dirs, rows, {
        key: (x) => (x.up ? `up:${x.path}` : x.path),
        create: (x) => el(`<button class="fl-imp-row" type="button" data-path="${escapeHtml(x.path)}">${icon(x.up ? 'chevronUp' : 'folder', 14)}<span>${escapeHtml(x.name)}</span></button>`),
        update: () => undefined,
      });
      this.dirs.scrollTop = 0;
    } catch {
      if (seq === this.seq && this.pathInput.value !== path) this.pathInput.value = path;
    }
  }

  private finish(v: string | null): void {
    const r = this.resolve;
    this.resolve = null;
    if (this.isOpen) this.close();
    r?.(v);
  }
}

let picker: FolderPicker | null = null;

export function pickFolder(title: string, lead: string, start = '', okLabel = 'Choose'): Promise<string | null> {
  picker ??= new FolderPicker();
  return picker.ask(title, lead, start, okLabel);
}

export function folderOf(path: string): string {
  const i = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
  return i > 0 ? path.slice(0, i) : path;
}
