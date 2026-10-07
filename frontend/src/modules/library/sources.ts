import type { Ctx } from '../../app';
import { catalog, type CollectionRow, type FolderRow } from '../../state/catalog';
import { library, type Source } from '../../state/library';
import { promptName, confirmAction } from '../../ui/dialogs';
import { el } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { PopupMenu } from '../../ui/menu';
import { Panel } from '../../ui/panel';
import { toast } from '../../ui/toast';
import { Tree, type TreeNode } from '../../ui/tree';
import { openSmartCollection } from './smart';

function home(path: string): string {
  return path.replace(/^\/(Users|home)\/[^/]+/, '~');
}

function sourceKey(s: Source): string { return `${s.kind}:${s.id ?? s.value ?? ''}`; }

export function folderNodes(rows: FolderRow[]): TreeNode[] {
  const kids = new Map<number | null, FolderRow[]>();
  const ids = new Set(rows.map((r) => r.id));
  for (const r of rows) {
    const parent = r.parent !== null && ids.has(r.parent) ? r.parent : null;
    if (!kids.has(parent)) kids.set(parent, []);
    kids.get(parent)?.push(r);
  }
  const total = (r: FolderRow): number => r.count + (kids.get(r.id) ?? []).reduce((a, k) => a + total(k), 0);
  const out: TreeNode[] = [];
  const walk = (parent: number | null, depth: number) => {
    for (const r of kids.get(parent) ?? []) {
      const hasKids = (kids.get(r.id) ?? []).length > 0;
      out.push({ key: `folder:${r.id}`, label: depth === 0 ? home(r.path) : r.name, icon: r.online ? 'folder' : 'warning', count: total(r), depth, hasKids, dim: !r.online, data: r });
      walk(r.id, depth + 1);
    }
  };
  walk(null, 0);
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
      onContext: (n, e) => this.context(n, e, ['lib.folderShow', 'lib.folderSync', 'lib.folderRename', 'lib.folderCreate', '-', 'lib.folderRemove']),
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

  private commands(): void {
    const ctx = this.ctx;
    const fail = (e: unknown) => ctx.fail(e);
    const folder = () => this.node<FolderRow>();
    const col = () => this.node<CollectionRow>();
    const parentSet = () => { const c = col(); return c ? (c.kind === 'set' ? c.id : c.parent) : null; };
    ctx.commands.add(
      { id: 'lib.folderShow', label: /Mac/.test(navigator.platform) ? 'Show in Finder' : 'Show in Explorer', run: () => { const f = folder(); const first = f ? library.ids.find((id) => library.photo(id)?.folder === f.id) : undefined; if (first !== undefined) void ctx.api.cmd('photo.reveal', { id: first }).catch(fail); } },
      { id: 'lib.folderSync', label: 'Synchronize Folder...', run: () => { const f = folder(); if (f) void ctx.api.cmd<{ added: number; missing: number }>('folder.synchronize', { id: f.id, importNew: true }).then((r) => toast(`Synchronized: ${r.added ?? 0} new, ${r.missing ?? 0} missing`), fail); } },
      { id: 'lib.folderRename', label: 'Rename...', run: async () => { const f = folder(); if (!f) return; const name = await promptName('Rename Folder', f.name, 'Rename'); if (name && name !== f.name) await ctx.api.cmd('folder.update', { id: f.id, name }).catch(fail); } },
      { id: 'lib.folderCreate', label: 'Create Folder inside...', run: async () => { const f = folder(); if (!f) return; const name = await promptName('New Folder', 'Untitled', 'Create'); if (name) await ctx.api.cmd('folder.create', { parent: f.id, name }).catch(fail); } },
      { id: 'lib.folderRemove', label: 'Remove from Catalog...', run: async () => { const f = folder(); if (!f) return; if (await confirmAction('Remove Folder', `Remove "${f.name}" and its photos from the catalog? Files on disk stay where they are.`, 'Remove', true)) await ctx.api.cmd('folder.remove', { id: f.id }).catch(fail); } },
      { id: 'lib.colTarget', label: 'Set as Target Collection', run: () => { const c = col(); if (c) void ctx.api.cmd('collection.setTarget', { id: c.target ? null : c.id }).catch(fail); }, checked: () => !!col()?.target, enabled: () => col()?.kind === 'collection' },
      { id: 'lib.colRename', label: 'Rename...', run: async () => { const c = col(); if (!c) return; const name = await promptName('Rename', c.name, 'Rename'); if (name && name !== c.name) await ctx.api.cmd('collection.update', { id: c.id, name }).catch(fail); }, enabled: () => !!col() },
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
    this.folders.set(folderNodes(t.folders));
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
