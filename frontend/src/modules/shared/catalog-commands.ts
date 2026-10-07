import type { Ctx } from '../../app';
import { events } from '../../io/events';
import { library } from '../../state/library';
import { askForm } from '../../ui/askform';
import { Dialog } from '../../ui/dialogs';
import { el, escapeHtml } from '../../ui/dom';
import { openPreferences } from '../../ui/preferences';
import { toast } from '../../ui/toast';
import { SECOND_CHANNEL } from '../../second';
import { whenDone } from './tasks';

class ShortcutsDialog extends Dialog {
  private readonly list = el('<div class="fl-keys"></div>');
  constructor(private readonly ctx: Ctx) {
    super('Keyboard Shortcuts', 640);
    this.body.appendChild(this.list);
    this.button('Done', 'primary', () => this.close());
  }
  show(): void {
    const groups = new Map<string, Array<[string, string]>>();
    for (const c of this.ctx.commands.all()) {
      const keys = this.ctx.commands.keyLabel(c);
      if (!keys) continue;
      const g = c.id.split('.')[0];
      const name = { app: 'Application', view: 'View', photo: 'Photo', develop: 'Develop', library: 'Library', edit: 'Edit', module: 'Modules', lib: 'Library' }[g] ?? 'Other';
      if (!groups.has(name)) groups.set(name, []);
      groups.get(name)?.push([this.ctx.commands.label(c), keys]);
    }
    const html = [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([g, rows]) => `<div class="fl-sub">${escapeHtml(g)}</div>${rows.sort((a, b) => a[0].localeCompare(b[0])).map(([l, k]) => `<div class="fl-keys-row"><span>${escapeHtml(l)}</span><kbd>${escapeHtml(k)}</kbd></div>`).join('')}`).join('');
    if (this.list.dataset.key !== html) { this.list.dataset.key = html; this.list.innerHTML = html; }
    this.open();
  }
}

async function openSecondWindow(): Promise<void> {
  const url = `${window.location.pathname}?second=1`;
  if ('__TAURI_INTERNALS__' in window) {
    const { WebviewWindow } = await import('@tauri-apps/api/webviewWindow');
    const existing = await WebviewWindow.getByLabel('second');
    if (existing) { await existing.setFocus(); return; }
    new WebviewWindow('second', { url, title: 'formlit · Second Window', width: 1200, height: 800 });
    return;
  }
  window.open(url, 'formlit-second', 'popup,width=1200,height=800');
}

function broadcastActive(): void {
  const ch = new BroadcastChannel(SECOND_CHANNEL);
  const send = () => ch.postMessage({ photo: library.active !== null ? library.photo(library.active) ?? null : null });
  library.listen('selection', send);
  library.listen('photos', (ids) => { if (library.active !== null && ids.includes(library.active)) send(); });
  ch.onmessage = (e: MessageEvent) => { if ((e.data as { hello?: boolean }).hello) send(); };
}

interface AutoImport { enabled: boolean; watch: string; destination: string; folderTemplate: string; renameTemplate: string; keywords: string[]; preset: string }

export function registerCatalogCommands(ctx: Ctx): void {
  let shortcuts: ShortcutsDialog | null = null;
  let autoOn = false;
  broadcastActive();
  void ctx.api.cmd<AutoImport>('autoImport.get').then((s) => { autoOn = !!s.enabled; }, () => undefined);
  events.on('autoImport', (e) => {
    if (e.error) toast(`Auto Import: ${String(e.error)}`, 'error');
    else if (e.count) toast(`Auto imported ${String(e.count)} ${Number(e.count) === 1 ? 'photo' : 'photos'}`);
  });
  events.on('catalog.changed', () => {
    try { localStorage.removeItem('formlit_library_view'); } finally { window.location.reload(); }
  });
  ctx.commands.add(
    {
      id: 'library.openCatalog', label: 'Open Catalog...',
      run: async () => {
        let recent: string[] = [];
        let current = '';
        try { const r = await ctx.api.cmd<{ current: string; recent: string[] }>('catalog.recent'); recent = r.recent.filter((p) => p !== r.current); current = r.current; } catch (err) { ctx.fail(err); return; }
        const v = await askForm('Open Catalog', `formlit restarts its window on the catalog you open. Now open: ${current}`, [
          { path: 'recent', label: 'Recent', kind: 'select', options: [['', recent.length ? 'Choose...' : 'No other recent catalogs'], ...recent.map((p) => [p, p.split(/[\\/]/).slice(-2).join('/')] as [string, string])] },
          { path: 'path', label: 'Or a path', kind: 'text', placeholder: '/Users/you/Pictures/Studio/Studio.fldb' },
        ], { recent: '', path: '' }, 'Open');
        const path = String(v?.path || v?.recent || '');
        if (!path) return;
        try { await ctx.api.cmd('catalog.open', { path }); } catch (err) { ctx.fail(err); }
      },
    },
    {
      id: 'library.newCatalog', label: 'New Catalog...',
      run: async () => {
        const v = await askForm('New Catalog', 'Creates an empty catalog in its own folder and switches to it. Your photos stay where they are; import them into the new catalog.', [
          { path: 'folder', label: 'Folder', kind: 'text', placeholder: '/Users/you/Pictures' },
          { path: 'name', label: 'Name', kind: 'text' },
        ], { folder: '', name: 'formlit Catalog' }, 'Create');
        if (!v?.folder) return;
        try { await ctx.api.cmd('catalog.create', { folder: v.folder, name: v.name }); } catch (err) { ctx.fail(err); }
      },
    },
    {
      id: 'library.buildPreviews', label: 'Build Standard-Sized Previews',
      run: async () => {
        const ids = library.selected().length ? library.selected() : library.ids.slice();
        try {
          const r = await ctx.api.cmd<{ task: number }>('library.buildPreviews', { ids, size: 'standard' });
          await whenDone(r.task);
          toast(`Built previews for ${ids.length} ${ids.length === 1 ? 'photo' : 'photos'}`);
        } catch (err) { ctx.fail(err); }
      },
    },
    {
      id: 'library.findMissing', label: 'Find Missing Photos',
      run: async () => {
        try {
          const r = await ctx.api.cmd<{ missing: number[] | number }>('library.findMissing');
          const n = Array.isArray(r.missing) ? r.missing.length : Number(r.missing ?? 0);
          if (n) { library.setSource({ kind: 'missing', label: 'Missing Photographs' }); toast(`${n} ${n === 1 ? 'photo is' : 'photos are'} missing. Right-click a folder to synchronize, or relink from the Library.`); }
          else toast('No photos are missing');
        } catch (err) { ctx.fail(err); }
      },
    },
    {
      id: 'library.autoImportSettings', label: 'Auto Import Settings...',
      run: async () => {
        let s: AutoImport;
        let presets: Array<{ id: string; name: string; group: string }> = [];
        try {
          [s, presets] = await Promise.all([ctx.api.cmd<AutoImport>('autoImport.get'), ctx.api.cmd<{ presets: typeof presets }>('preset.list').then((r) => r.presets)]);
        } catch (err) { ctx.fail(err); return; }
        const v = await askForm('Auto Import', 'Watches a folder and imports what lands in it, moving the files to the destination. Point tethering software (or a card reader script) at the watched folder for tethered capture.', [
          { path: 'enabled', label: 'Enable', kind: 'check' },
          { path: 'watch', label: 'Watched folder', kind: 'text', placeholder: '/Users/you/Pictures/Tether' },
          { path: 'destination', label: 'Destination', kind: 'text', placeholder: '/Users/you/Pictures/Imported' },
          { path: 'folderTemplate', label: 'Subfolders', kind: 'text', placeholder: '{date:%Y}/{date:%Y-%m-%d}' },
          { path: 'renameTemplate', label: 'Rename to', kind: 'text', placeholder: '{custom}-{seq:4} (leave empty to keep names)' },
          { path: 'keywords', label: 'Keywords', kind: 'text', placeholder: 'Studio, Client|Acme' },
          { path: 'preset', label: 'Develop preset', kind: 'select', options: [['', 'None'], ...presets.map((p) => [p.id, `${p.group}: ${p.name}`] as [string, string])] },
        ], { ...s, keywords: (s.keywords ?? []).join(', ') }, 'Save');
        if (!v) return;
        try {
          const r = await ctx.api.cmd<AutoImport & { running: boolean }>('autoImport.set', { ...v, keywords: String(v.keywords ?? '').split(',').map((k) => k.trim()).filter(Boolean) });
          autoOn = r.running;
          toast(r.running ? `Watching ${r.watch}` : 'Auto Import is off');
        } catch (err) { ctx.fail(err); }
      },
    },
    {
      id: 'library.autoImport', label: 'Enable Auto Import', checked: () => autoOn,
      run: async () => {
        try {
          const r = await ctx.api.cmd<AutoImport & { running: boolean }>('autoImport.set', { enabled: !autoOn });
          autoOn = r.running;
          toast(autoOn ? `Watching ${r.watch}` : 'Auto Import is off');
        } catch (err) { ctx.fail(err); }
      },
    },
    { id: 'view.secondWindow', label: 'Second Window', keys: ['F11'], run: () => void openSecondWindow() },
    { id: 'app.shortcuts', label: 'Keyboard Shortcuts', keys: ['Mod+/'], run: () => { shortcuts ??= new ShortcutsDialog(ctx); shortcuts.show(); } },
    { id: 'app.agents', label: 'Agents and MCP...', run: () => openPreferences(ctx) },
  );
}
