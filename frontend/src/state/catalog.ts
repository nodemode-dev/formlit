import { api } from '../io/api';
import { events } from '../io/events';

export interface FolderRow { id: number; path: string; name: string; parent: number | null; count: number; missing: number; online: boolean }
export interface CollectionRow { id: number; name: string; kind: string; parent: number | null; count: number; target: boolean; rules: unknown; settings: Record<string, unknown> | null; service: number | null; cover: number | null }
export interface KeywordRow { id: number; name: string; parent: number | null; count: number; synonyms: string[]; export: boolean; person: boolean }
export interface CatalogInfo { name: string; path: string; total: number; previousImport: number; quick: number; missing: number; revision: number }
export interface Tree { catalog: CatalogInfo; folders: FolderRow[]; collections: CollectionRow[]; keywords: KeywordRow[]; labelNames: Record<string, string> }

type Fn = () => void;

export class CatalogState {
  tree: Tree = { catalog: { name: 'formlit', path: '', total: 0, previousImport: 0, quick: 0, missing: 0, revision: 0 }, folders: [], collections: [], keywords: [], labelNames: {} };
  private readonly fns = new Set<Fn>();
  private timer = 0;
  private seq = 0;

  constructor() {
    const soon = () => this.refreshSoon();
    for (const t of ['photos.added', 'photos.removed', 'list.changed', 'undo', 'redo', 'resync']) events.on(t, soon);
    events.on('photos.changed', (e) => {
      const fields = Object.values((e.photos ?? {}) as Record<string, string[]>).flat();
      if (fields.some((f) => f === 'folder_id' || f === 'missing')) soon();
    });
  }

  listen(fn: Fn): Fn { this.fns.add(fn); return () => { this.fns.delete(fn); }; }

  async refresh(): Promise<void> {
    const seq = ++this.seq;
    const t = await api.cmd<Tree>('library.tree');
    if (seq !== this.seq) return;
    this.tree = t;
    for (const fn of this.fns) fn();
  }

  refreshSoon(ms = 120): void {
    window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => { void this.refresh().catch(() => undefined); }, ms);
  }

  keywordPath(id: number): string {
    const byId = new Map(this.tree.keywords.map((k) => [k.id, k]));
    const parts: string[] = [];
    let k = byId.get(id);
    while (k) { parts.unshift(k.name); k = k.parent !== null ? byId.get(k.parent) : undefined; }
    return parts.join('|');
  }

  labelName(label: string): string {
    return this.tree.labelNames[label] || label.charAt(0).toUpperCase() + label.slice(1);
  }

  targetCollection(): CollectionRow | undefined { return this.tree.collections.find((c) => c.target); }
}

export const catalog = new CatalogState();
