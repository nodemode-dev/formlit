import type { Ctx } from '../../app';
import type { FolderRow } from '../../state/catalog';
import { library } from '../../state/library';
import { Dialog } from '../../ui/dialogs';
import { el, q, setHidden, setText } from '../../ui/dom';
import { toast } from '../../ui/toast';

interface Scan { new: number; missing: number; changed: number; path: string }
interface Synced { imported: number; missing: number; removed: number; changed: number[]; conflicts: number[] }

class SyncDialog extends Dialog {
  private readonly status = el('<p class="cv-note fl-sync-status">Scanning the folder...</p>');
  private readonly opts = el(`<div class="fl-sync-opts">
<label class="fl-check"><input type="checkbox" data-k="importNew" checked> <span data-l="importNew">Import New Photos</span></label>
<label class="fl-check"><input type="checkbox" data-k="removeMissing"> <span data-l="removeMissing">Remove Missing Photos from Catalog</span></label>
<div class="fl-sync-row"><button class="cv-btn cv-btn-ghost fl-sync-show" type="button">Show Missing Photos</button></div>
<label class="fl-check"><input type="checkbox" data-k="scanMetadata" checked> <span data-l="scanMetadata">Scan for Metadata Updates and Changed Files</span></label>
</div>`);
  private readonly ok: HTMLButtonElement;
  private folder: FolderRow | null = null;
  private seq = 0;
  private resolve: ((v: Record<string, boolean> | null) => void) | null = null;

  constructor(private readonly ctx: Ctx) {
    super('Synchronize Folder', 460);
    this.body.append(this.status, this.opts);
    this.button('Cancel', 'ghost', () => this.finish(null));
    this.ok = this.button('Synchronize', 'primary', () => this.finish(this.values()));
    this.onClose = () => this.finish(null);
    q(this.opts, '.fl-sync-show').addEventListener('click', () => {
      library.setSource({ kind: 'missing', label: 'Missing Photographs' });
      this.finish(null);
    });
  }

  async ask(f: FolderRow): Promise<Record<string, boolean> | null> {
    this.folder = f;
    const seq = ++this.seq;
    this.setTitle(`Synchronize Folder "${f.name}"`);
    setText(this.status, 'Scanning the folder...');
    this.ok.disabled = true;
    this.label('importNew', 'Import New Photos', null);
    this.label('removeMissing', 'Remove Missing Photos from Catalog', null);
    this.label('scanMetadata', 'Scan for Metadata Updates and Changed Files', null);
    setHidden(q(this.opts, '.fl-sync-row'), true);
    this.open(this.ok);
    const done = new Promise<Record<string, boolean> | null>((r) => { this.resolve = r; });
    try {
      const s = await this.ctx.api.cmd<Scan>('folder.synchronize', { id: f.id, dryRun: true });
      if (seq !== this.seq || !this.isOpen) return done;
      setText(this.status, s.new || s.missing || s.changed ? `Synchronizing ${s.path}` : `${s.path} is up to date with the catalog. Scanning for metadata updates is still available.`);
      this.label('importNew', 'Import New Photos', s.new);
      this.label('removeMissing', 'Remove Missing Photos from Catalog', s.missing);
      this.label('scanMetadata', 'Scan for Metadata Updates and Changed Files', s.changed);
      q<HTMLInputElement>(this.opts, '[data-k="importNew"]').disabled = !s.new;
      q<HTMLInputElement>(this.opts, '[data-k="removeMissing"]').disabled = !s.missing;
      setHidden(q(this.opts, '.fl-sync-row'), !s.missing);
      this.ok.disabled = false;
    } catch (err) {
      if (seq === this.seq) setText(this.status, err instanceof Error ? err.message : String(err));
    }
    return done;
  }

  private label(k: string, text: string, n: number | null): void {
    setText(q(this.opts, `[data-l="${k}"]`), n === null ? text : `${text} (${n})`);
  }

  private values(): Record<string, boolean> {
    const v = (k: string) => { const i = q<HTMLInputElement>(this.opts, `[data-k="${k}"]`); return i.checked && !i.disabled; };
    return { importNew: v('importNew'), removeMissing: v('removeMissing'), scanMetadata: q<HTMLInputElement>(this.opts, '[data-k="scanMetadata"]').checked };
  }

  private finish(v: Record<string, boolean> | null): void {
    const r = this.resolve;
    this.resolve = null;
    this.seq += 1;
    if (this.isOpen) this.close();
    r?.(v);
  }
}

let dialog: SyncDialog | null = null;

export async function synchronizeFolder(ctx: Ctx, f: FolderRow): Promise<void> {
  dialog ??= new SyncDialog(ctx);
  const v = await dialog.ask(f);
  if (!v) return;
  try {
    const done = ctx.shell.busy(`Synchronizing ${f.name}`);
    let r: Synced;
    try { r = await ctx.api.cmd<Synced>('folder.synchronize', { id: f.id, ...v }); } finally { done(); }
    const parts = [`${r.imported} imported`];
    if (r.removed) parts.push(`${r.removed} removed`);
    else if (r.missing) parts.push(`${r.missing} missing`);
    if (v.scanMetadata) parts.push(`${r.changed.length} changed on disk`, `${r.conflicts.length} with newer metadata`);
    toast(`Synchronized ${f.name}: ${parts.join(', ')}`);
  } catch (err) { ctx.fail(err, 'Synchronize Folder'); }
}
