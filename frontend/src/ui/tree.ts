import { el, escapeHtml, patchList, q, setClass, setHtml, setText, setTitle } from './dom';
import { icon } from './icons';

export interface TreeNode {
  key: string;
  label: string;
  icon: string;
  count?: number | null;
  depth: number;
  hasKids: boolean;
  dim?: boolean;
  badge?: string;
  data?: unknown;
}

export interface TreeOptions {
  id: string;
  onPick: (n: TreeNode, e: MouseEvent) => void;
  onContext?: (n: TreeNode, e: MouseEvent) => void;
  onDrop?: (n: TreeNode, ids: number[], e: DragEvent) => void;
  canDrop?: (n: TreeNode) => boolean;
  onRename?: (n: TreeNode, name: string) => void;
  empty?: string;
}

const OPEN_KEY = 'formlit_tree_open';

function readOpen(): Record<string, boolean> {
  try { return JSON.parse(localStorage.getItem(OPEN_KEY) || '{}') as Record<string, boolean>; } catch { return {}; }
}

export class Tree {
  readonly root: HTMLElement;
  private nodes: TreeNode[] = [];
  private byKey = new Map<string, TreeNode>();
  private open: Record<string, boolean> = readOpen();
  private active = '';
  private readonly empty: HTMLElement;
  private readonly list: HTMLElement;

  constructor(private readonly opts: TreeOptions) {
    this.root = el(`<div class="fl-tree" role="tree"><div class="fl-tree-list"></div><div class="fl-tree-empty" hidden></div></div>`);
    this.list = q(this.root, '.fl-tree-list');
    this.empty = q(this.root, '.fl-tree-empty');
    setText(this.empty, opts.empty ?? 'Nothing here yet');
    this.list.addEventListener('click', (e) => {
      const row = (e.target as HTMLElement).closest<HTMLElement>('.fl-tree-row');
      if (!row) return;
      const n = this.byKey.get(row.dataset.key ?? '');
      if (!n) return;
      if ((e.target as HTMLElement).closest('.fl-tree-chev') || (n.hasKids && n.data === undefined)) { this.toggle(n.key); return; }
      this.opts.onPick(n, e);
    });
    this.list.addEventListener('dblclick', (e) => {
      const row = (e.target as HTMLElement).closest<HTMLElement>('.fl-tree-row');
      const n = row ? this.byKey.get(row.dataset.key ?? '') : undefined;
      if (n?.hasKids && !(e.target as HTMLElement).closest('.fl-tree-chev')) this.toggle(n.key);
    });
    this.list.addEventListener('contextmenu', (e) => {
      const row = (e.target as HTMLElement).closest<HTMLElement>('.fl-tree-row');
      const n = row ? this.byKey.get(row.dataset.key ?? '') : undefined;
      if (!n || !this.opts.onContext) return;
      e.preventDefault();
      this.opts.onContext(n, e);
    });
    if (opts.onDrop) {
      this.list.addEventListener('dragover', (e) => {
        const n = this.nodeOf(e);
        if (!n || !e.dataTransfer?.types.includes('application/x-formlit-ids') || (this.opts.canDrop && !this.opts.canDrop(n))) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
        this.mark(n.key);
      });
      this.list.addEventListener('dragleave', (e) => { if (!this.list.contains(e.relatedTarget as Node)) this.mark(''); });
      this.list.addEventListener('drop', (e) => {
        const n = this.nodeOf(e);
        this.mark('');
        const raw = e.dataTransfer?.getData('application/x-formlit-ids');
        if (!n || !raw) return;
        e.preventDefault();
        try { this.opts.onDrop?.(n, JSON.parse(raw) as number[], e); } catch { return; }
      });
    }
  }

  private nodeOf(e: Event): TreeNode | undefined {
    const row = (e.target as HTMLElement).closest<HTMLElement>('.fl-tree-row');
    return row ? this.byKey.get(row.dataset.key ?? '') : undefined;
  }

  private mark(key: string): void {
    for (const row of Array.from(this.list.children) as HTMLElement[]) setClass(row, 'is-drop', row.dataset.key === key);
  }

  isOpen(key: string): boolean { return this.open[`${this.opts.id}:${key}`] ?? false; }

  toggle(key: string, on?: boolean): void {
    const k = `${this.opts.id}:${key}`;
    this.open[k] = on ?? !this.isOpen(key);
    try { const all = readOpen(); all[k] = this.open[k]; localStorage.setItem(OPEN_KEY, JSON.stringify(all)); } catch { this.render(); }
    this.render();
  }

  set(nodes: TreeNode[]): void {
    this.nodes = nodes;
    this.byKey = new Map(nodes.map((n) => [n.key, n]));
    this.render();
  }

  setActive(key: string): void {
    if (this.active === key) return;
    this.active = key;
    for (const row of Array.from(this.list.children) as HTMLElement[]) setClass(row, 'is-active', row.dataset.key === key);
  }

  private visible(): TreeNode[] {
    const out: TreeNode[] = [];
    const closedAt: number[] = [];
    for (const n of this.nodes) {
      while (closedAt.length && n.depth <= closedAt[closedAt.length - 1]) closedAt.pop();
      if (closedAt.length) continue;
      out.push(n);
      if (n.hasKids && !this.isOpen(n.key)) closedAt.push(n.depth);
    }
    return out;
  }

  private render(): void {
    const rows = this.visible();
    this.empty.hidden = this.nodes.length > 0;
    patchList(this.list, rows, {
      key: (n) => n.key,
      create: (n) => {
        const row = el(`<div class="fl-tree-row" role="treeitem"><span class="fl-tree-chev"></span><span class="fl-tree-icon"></span><span class="fl-tree-label"></span><span class="fl-tree-badge"></span><span class="fl-tree-count"></span></div>`);
        this.fill(row, n);
        return row;
      },
      update: (row, n) => this.fill(row, n),
    });
  }

  private fill(row: HTMLElement, n: TreeNode): void {
    row.style.setProperty('--depth', String(n.depth));
    setHtml(q(row, '.fl-tree-chev'), n.hasKids ? icon('chevronRight', 11) : '', String(n.hasKids));
    setClass(row, 'is-open', n.hasKids && this.isOpen(n.key));
    setHtml(q(row, '.fl-tree-icon'), icon(n.icon, 14), n.icon);
    setText(q(row, '.fl-tree-label'), n.label);
    setHtml(q(row, '.fl-tree-badge'), n.badge ? escapeHtml(n.badge) : '', n.badge ?? '');
    setText(q(row, '.fl-tree-count'), n.count === null || n.count === undefined ? '' : String(n.count));
    setClass(row, 'is-dim', !!n.dim);
    setClass(row, 'is-active', n.key === this.active);
    setTitle(row, n.label);
    row.setAttribute('aria-expanded', String(n.hasKids && this.isOpen(n.key)));
  }
}
