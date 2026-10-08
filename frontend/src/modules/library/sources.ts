import type { Ctx } from '../../app';
import { catalog, type CollectionRow, type FolderRow, type VolumeRow } from '../../state/catalog';
import { library, type Source } from '../../state/library';
import { promptName, confirmAction } from '../../ui/dialogs';
import { el } from '../../ui/dom';
import { folderOf, pickFolder } from '../../ui/folder-picker';
import { icon } from '../../ui/icons';
import { PopupMenu } from '../../ui/menu';
import { Panel } from '../../ui/panel';
import { toast } from '../../ui/toast';
import { Tree, type TreeNode } from '../../ui/tree';
import { synchronizeFolder } from './folder-sync';
import { openSmartCollection } from './smart';

function home(path: string): string {
  return path.replace(/^\/(Users|home)\/[^/]+/, '~');
}

function sourceKey(s: Source): string { return `${s.kind}:${s.id ?? s.value ?? ''}`; }

function bytes(n: number): string {
  const gb = n / 1e9;
  return gb >= 1000 ? `${(gb / 1000).toFixed(1)} TB` : `${gb >= 100 ? gb.toFixed(0) : gb.toFixed(1)} GB`;
}

export function folderNodes(rows: FolderRow[], volumes: VolumeRow[] = []): TreeNode[] {
  const kids = new Map<number | null, FolderRow[]>();
  const ids = new Set(rows.map((r) => r.id));
  for (const r of rows) {
    const parent = r.parent !== null && ids.has(r.parent) ? r.parent : null;
    if (!kids.has(parent)) kids.set(parent, []);
    kids.get(parent)?.push(r);
  }
  const total = (r: FolderRow): number => r.count + (kids.get(r.id) ?? []).reduce((a, k) => a + total(k), 0);
  const out: TreeNode[] = [];
  const walk = (list: FolderRow[], depth: number, top: boolean) => {
    for (const r of list) {
      const hasKids = (kids.get(r.id) ?? []).length > 0;
      out.push({ key: `folder:${r.id}`, label: top ? home(r.path) : r.name, icon: r.online ? 'folder' : 'warning', count: total(r), depth, hasKids, dim: !r.online, data: r });
      walk(kids.get(r.id) ?? [], depth + 1, false);
    }
  };
  const roots = kids.get(null) ?? [];
  if (!volumes.length) { walk(roots, 0, true); return out; }
  for (const v of volumes) {
    const mine = roots.filter((r) => r.volume === v.mount);
    if (!mine.length) continue;
    out.push({ key: `volume:${v.mount}`, label: v.name, icon: v.online ? 'drive' : 'warning', depth: 0, hasKids: true, head: true, dim: !v.online,
      note: v.online ? `${bytes(v.free)} / ${bytes(v.total)}` : 'Offline', count: null });
    walk(mine, 1, true);
  }
  walk(roots.filter((r) => !volumes.some((v) => v.mount === r.volume)), 0, true);
  return out;
}

export function collectionNodes(rows: CollectionRow[]): TreeNode[] {
  const list = rows.filter((c) => c.kind === 'collection' || c.kind === 'set' || c.kind === 'smart');
  const kids = new Map<number | null, CollectionRow[]>();
  const ids = new Set(list.map((r) => r.id));
  for (const r of list) {
    const parent = r.parent !== null && ids.has(r.parent) ? r.parent : null;
    if (!kids.has(parent)) kids.set(parent, []);
    kids.get(parent)?.push(r);
  }
  const out: TreeNode[] = [];
  const walk = (parent: number | null, depth: number) => {
    const items = (kids.get(parent) ?? []).slice().sort((a, b) => (a.kind === 'set' ? 0 : 1) - (b.kind === 'set' ? 0 : 1) || a.name.localeCompare(b.name));
    for (const r of items) {
      const hasKids = (kids.get(r.id) ?? []).length > 0;
      const ic = r.kind === 'set' ? 'collectionSet' : r.kind === 'smart' ? 'smartCollection' : 'collection';
      out.push({ key: `collection:${r.id}`, label: r.name, icon: ic, count: r.kind === 'set' ? null : r.count, depth, hasKids, badge: r.target ? '+' : '', data: r });
      walk(r.id, depth + 1);
    }
  };
  walk(null, 0);
  return out;
}

export class SourcePanels {
  private readonly catalogTree: Tree;
  private readonly folders: Tree;
  private readonly collections: Tree;
  private readonly menu: PopupMenu;
  private ctxNode: TreeNode | null = null;

  constructor(private readonly ctx: Ctx, host: HTMLElement) {
    this.catalogTree = new Tree({ id: 'catalog', onPick: (n) => library.setSource(n.data as Source) });
    this.folders = new Tree({
      id: 'folders', empty: 'Import photos to see their folders here',
      onPick: (n) => { const r = n.data as FolderRow; library.setSource({ kind: 'folder', id: r.id, label: r.name, recursive: true }); },
      onContext: (n, e) => { if (!n.head) this.context(n, e, ['lib.folderShow', 'lib.folderSync', 'lib.folderRename', 'lib.folderCreate', 'lib.folderMove', 'lib.folderRelocate', '-', 'lib.folderShowParent', 'lib.folderHideParent', '-', 'lib.folderRemove']); },
      canDrop: (n) => (n.data as FolderRow).online !== false,
      onDrop: (n, ids) => void this.movePhotos(n.data as FolderRow, ids),
    });
    this.collections = new Tree({
      id: 'collections', empty: 'Drag photos here, or press + to make a collection',
      onPick: (n) => { const r = n.data as CollectionRow; library.setSource({ kind: 'collection', id: r.id, label: r.name }); },
      onContext: (n, e) => this.context(n, e, ['lib.colTarget', 'lib.colRename', 'lib.colEditSmart', '-', 'lib.colNew', 'lib.colNewSmart', 'lib.colNewSet', '-', 'lib.colDelete']),
      canDrop: (n) => (n.data as CollectionRow).kind === 'collection',
      onDrop: (n, ids) => void ctx.api.cmd('collection.addPhotos', { id: (n.data as CollectionRow).id, ids }).then(() => toast(`Added ${ids.length} to ${(n.data as CollectionRow).name}`), (e) => ctx.fail(e)),
    });
    this.menu = new PopupMenu(ctx.commands, null, true);
    this.commands();

    const add = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" title="New Collection" aria-label="New Collection">${icon('plus', 14)}</button>`);
    add.addEventListener('click', (e) => { this.ctxNode = null; const r = add.getBoundingClientRect(); this.menu.setItems(['lib.colNew', 'lib.colNewSmart', 'lib.colNewSet']); this.menu.openAt(r.left, r.bottom + 4); e.stopPropagation(); });
    const addFolder = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" data-cmd="library.import" aria-label="Add Folder">${icon('plus', 14)}</button>`);

    const pCatalog = new Panel('lib.catalog', 'Catalog');
    pCatalog.body.appendChild(this.catalogTree.root);
    const pFolders = new Panel('lib.folders', 'Folders', { tools: [addFolder] });
    pFolders.body.appendChild(this.folders.root);
    const pCollections = new Panel('lib.collections', 'Collections', { tools: [add] });
    pCollections.body.appendChild(this.collections.root);
    host.append(pCatalog.root, pFolders.root, pCollections.root);

    catalog.listen(() => this.render());
    library.listen('list', () => this.syncActive());
  }

  private context(n: TreeNode, e: MouseEvent, items: string[]): void {
    this.ctxNode = n;
    this.menu.setItems(items);
    this.menu.openAt(e.clientX, e.clientY);
  }

  private node<T>(): T | null { return (this.ctxNode?.data as T) ?? null; }

  private async movePhotos(f: FolderRow, ids: number[]): Promise<void> {
    const n = ids.length;
    if (!await confirmAction('Move Photos', `Move ${n} photo${n === 1 ? '' : 's'} into "${f.name}" on disk? Their sidecars move with them.`, 'Move')) return;
    try {
      const r = await this.ctx.api.cmd<{ moved: number[]; skipped: number[] }>('photo.move', { ids, folder: f.id });
      toast(`Moved ${r.moved.length} photo${r.moved.length === 1 ? '' : 's'} to ${f.name}${r.skipped.length ? ` · ${r.skipped.length} missing` : ''}`);
    } catch (err) { this.ctx.fail(err); }
  }

  private commands(): void {
    const ctx = this.ctx;
    const fail = (e: unknown) => ctx.fail(e);
    const folder = () => this.node<FolderRow>();
    const col = () => this.node<CollectionRow>();
    const parentSet = () => { const c = col(); return c ? (c.kind === 'set' ? c.id : c.parent) : null; };
    ctx.commands.add(
      { id: 'lib.folderShow', label: /Mac/.test(navigator.platform) ? 'Show in Finder' : 'Show in Explorer', run: () => { const f = folder(); const first = f ? library.ids.find((id) => library.photo(id)?.folder === f.id) : undefined; if (first !== undefined) void ctx.api.cmd('photo.reveal', { id: first }).catch(fail); } },
      { id: 'lib.folderSync', label: 'Synchronize Folder...', run: () => { const f = folder(); if (f) void synchronizeFolder(ctx, f); } },
      { id: 'lib.folderShowParent', label: 'Show Parent Folder', enabled: () => folder()?.parent === null, run: () => { const f = folder(); if (f) void ctx.api.cmd('folder.showParent', { id: f.id }).catch(fail); } },
      { id: 'lib.folderHideParent', label: 'Hide This Parent', enabled: () => { const f = folder(); return !!f && f.count === 0 && catalog.tree.folders.some((x) => x.parent === f.id); }, run: () => { const f = folder(); if (f) void ctx.api.cmd('folder.hideParent', { id: f.id }).catch(fail); } },
      { id: 'lib.folderRename', label: 'Rename...', run: async () => { const f = folder(); if (!f) return; const name = await promptName('Rename Folder', f.name, 'Rename'); if (name && name !== f.name) await ctx.api.cmd('folder.update', { id: f.id, name }).then(() => library.relabel('folder', f.id, name), fail); } },
      { id: 'lib.folderCreate', label: 'Create Folder inside...', run: async () => { const f = folder(); if (!f) return; const name = await promptName('New Folder', 'Untitled', 'Create'); if (name) await ctx.api.cmd('folder.create', { parent: f.id, name }).catch(fail); } },
      { id: 'lib.folderRelocate', label: 'Update Folder Location...', run: async () => { const f = folder(); if (!f) return; const to = await pickFolder('Update Folder Location', `Where is "${f.name}" now? Photos in it are found again by name.`, folderOf(f.path), 'Choose'); if (to) { const r = await ctx.api.cmd<{ found: number }>('folder.relocate', { id: f.id, path: to }).catch(fail); if (r) toast(`Found ${r.found} photo${r.found === 1 ? '' : 's'} in ${to}`); } } },
      { id: 'lib.folderMove', label: 'Move Folder Into...', run: async () => { const f = folder(); if (!f) return; const into = await pickFolder('Move Folder', `Move "${f.name}" and everything in it on disk. Choose a folder that is already in the catalog.`, folderOf(f.path), 'Move'); if (!into) return; const t = catalog.tree.folders.find((x) => x.path === into); if (!t) { toast('Choose a folder that is in the catalog (import or create it first)'); return; } await ctx.api.cmd('folder.move', { id: f.id, into: t.id }).catch(fail); } },
      { id: 'lib.folderRemove', label: 'Remove from Catalog...', run: async () => { const f = folder(); if (!f) return; if (await confirmAction('Remove Folder', `Remove "${f.name}" and its photos from the catalog? Files on disk stay where they are.`, 'Remove', true)) await ctx.api.cmd('folder.remove', { id: f.id }).catch(fail); } },
      { id: 'lib.colTarget', label: 'Set as Target Collection', run: () => { const c = col(); if (c) void ctx.api.cmd('collection.setTarget', { id: c.target ? null : c.id }).catch(fail); }, checked: () => !!col()?.target, enabled: () => col()?.kind === 'collection' },
      { id: 'lib.colRename', label: 'Rename...', run: async () => { const c = col(); if (!c) return; const name = await promptName('Rename', c.name, 'Rename'); if (name && name !== c.name) await ctx.api.cmd('collection.update', { id: c.id, name }).then(() => library.relabel('collection', c.id, name), fail); }, enabled: () => !!col() },
      { id: 'lib.colEditSmart', label: 'Edit Smart Collection...', run: () => { const c = col(); if (c) openSmartCollection(ctx, c); }, enabled: () => col()?.kind === 'smart' },
      { id: 'lib.colNew', label: 'Create Collection...', keys: ['Mod+N'], run: async () => { const name = await promptName('Create Collection', 'Untitled Collection', 'Create'); if (!name) return; const ids = library.targets(); const r = await ctx.api.cmd<{ id: number }>('collection.create', { name, parent: parentSet(), ids }).catch(fail); if (r) toast(ids.length ? `Created ${name} with ${ids.length} photos` : `Created ${name}`); } },
      { id: 'lib.colNewSmart', label: 'Create Smart Collection...', run: () => openSmartCollection(ctx, null, parentSet()) },
      { id: 'lib.colNewSet', label: 'Create Collection Set...', run: async () => { const name = await promptName('Create Collection Set', 'Untitled Set', 'Create'); if (name) await ctx.api.cmd('collection.create', { name, kind: 'set', parent: parentSet() }).catch(fail); } },
      { id: 'lib.colDelete', label: 'Delete...', run: async () => { const c = col(); if (!c) return; if (await confirmAction('Delete', `Delete "${c.name}"? The photos stay in the catalog.`, 'Delete', true)) { await ctx.api.cmd('collection.delete', { id: c.id }).catch(fail); if (library.source.kind === 'collection' && library.source.id === c.id) library.setSource({ kind: 'all', label: 'All Photographs' }); } }, enabled: () => !!col() },
    );
  }

  private render(): void {
    const t = catalog.tree;
    const cat: TreeNode[] = [
      { key: 'all:', label: 'All Photographs', icon: 'catalog', count: t.catalog.total, depth: 0, hasKids: false, data: { kind: 'all', label: 'All Photographs' } },
      { key: 'quick:', label: 'Quick Collection +', icon: 'quickCollection', count: t.catalog.quick, depth: 0, hasKids: false, data: { kind: 'quick', label: 'Quick Collection' } },
      { key: 'previousImport:', label: 'Previous Import', icon: 'importLit', count: t.catalog.previousImport, depth: 0, hasKids: false, data: { kind: 'previousImport', label: 'Previous Import' } },
    ];
    if (t.catalog.missing) cat.push({ key: 'missing:', label: 'Missing Photographs', icon: 'warning', count: t.catalog.missing, depth: 0, hasKids: false, data: { kind: 'missing', label: 'Missing Photographs' } });
    this.catalogTree.set(cat);
    this.folders.set(folderNodes(t.folders, t.volumes ?? []));
    this.collections.set(collectionNodes(t.collections));
    this.syncActive();
  }

  private syncActive(): void {
    const key = sourceKey(library.source);
    this.catalogTree.setActive(key);
    this.folders.setActive(key);
    this.collections.setActive(key);
  }
}
