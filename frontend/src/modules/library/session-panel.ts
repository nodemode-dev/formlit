import type { Ctx } from '../../app';
import { events } from '../../io/events';
import { catalog } from '../../state/catalog';
import { library } from '../../state/library';
import { askForm } from '../../ui/askform';
import { Panel } from '../../ui/panel';
import { toast } from '../../ui/toast';
import { Tree, type TreeNode } from '../../ui/tree';

interface SessionFolder { name: string; path: string; id: number | null; count: number }
interface SessionState { active: { name: string; path: string; folders: Record<'capture' | 'selects' | 'output' | 'trash', SessionFolder> } | null; recent: string[] }

const ORDER: Array<['capture' | 'selects' | 'output' | 'trash', string]> = [['capture', 'camera'], ['selects', 'tStar'], ['output', 'upload'], ['trash', 'delete']];

let state: SessionState = { active: null, recent: [] };
const listeners = new Set<() => void>();
let pending = 0;

async function refresh(ctx: Ctx): Promise<void> {
  try { state = await ctx.api.cmd<SessionState>('session.state'); } catch { return; }
  for (const fn of listeners) fn();
}

function later(ctx: Ctx): void {
  window.clearTimeout(pending);
  pending = window.setTimeout(() => void refresh(ctx), 250);
}

function picked(): number[] {
  return library.selection.size ? [...library.selection] : library.active !== null ? [library.active] : [];
}

async function move(ctx: Ctx, cmd: string): Promise<void> {
  const ids = picked();
  if (!ids.length) return;
  try {
    const r = await ctx.api.cmd<{ moved: number[]; to: string }>(cmd, { ids });
    toast(`Moved ${r.moved.length} photo${r.moved.length === 1 ? '' : 's'} to ${r.to}`);
  } catch (err) { ctx.fail(err); }
}

export function registerSessionCommands(ctx: Ctx): void {
  const open = (): boolean => !!state.active;
  ctx.commands.add(
    {
      id: 'session.new', label: 'New Session...',
      run: async () => {
        const v = await askForm('New Session', 'A session is a folder with Capture, Selects, Output and Trash folders. Tethered shots land in Capture, exports go to Output, and every photo\'s settings are kept inside the folder, so it opens on any machine.', [
          { path: 'name', label: 'Name', kind: 'text', placeholder: 'Client Shoot' },
          { path: 'parent', label: 'Inside', kind: 'text', placeholder: '~/Pictures/Sessions' },
        ], { name: '', parent: '~/Pictures' }, 'Create');
        if (!v || !String(v.name || '').trim()) return;
        try { await ctx.api.cmd('session.new', { name: String(v.name), parent: String(v.parent || '~/Pictures') }); toast(`Session ${String(v.name)} is open`); } catch (err) { ctx.fail(err); }
      },
    },
    {
      id: 'session.open', label: 'Open Session...',
      run: async () => {
        const recent = state.recent.filter((p) => p !== state.active?.path);
        const v = await askForm('Open Session', 'Open a session folder, or its .flsession file. Photos are added to this catalog and their saved settings come back.', [
          { path: 'recent', label: 'Recent', kind: 'select', options: [['', recent.length ? 'Choose...' : 'No other recent sessions'], ...recent.map((p) => [p, p.split(/[\\/]/).slice(-2).join('/')] as [string, string])] },
          { path: 'path', label: 'Or a path', kind: 'text', placeholder: '~/Pictures/Sessions/Client Shoot' },
        ], { recent: '', path: '' }, 'Open');
        const path = String(v?.path || v?.recent || '');
        if (!path) return;
        try {
          const r = await ctx.api.cmd<SessionState & { imported: number; restored: number }>('session.open', { path });
          toast(`Session ${r.active?.name ?? ''} is open${r.imported ? ` · ${r.imported} photos added` : ''}${r.restored ? ` · ${r.restored} with their settings` : ''}`);
        } catch (err) { ctx.fail(err); }
      },
    },
    { id: 'session.close', label: 'Close Session', enabled: open, run: async () => { try { await ctx.api.cmd('session.close'); } catch (err) { ctx.fail(err); } } },
    { id: 'session.select', label: 'Move to Selects', keys: ['Alt+Shift+J'], enabled: () => open() && picked().length > 0, run: () => move(ctx, 'session.select') },
    { id: 'session.trash', label: 'Move to Session Trash', enabled: () => open() && picked().length > 0, run: () => move(ctx, 'session.trash') },
    { id: 'session.restore', label: 'Move Back to Capture', enabled: () => open() && picked().length > 0, run: () => move(ctx, 'session.restore') },
  );
  events.on('session', () => later(ctx));
  catalog.listen(() => later(ctx));
  void refresh(ctx);
}

export class SessionPanel {
  readonly panel = new Panel('lib.session', 'Session');
  private readonly tree: Tree;

  constructor(private readonly ctx: Ctx) {
    this.tree = new Tree({
      id: 'session', empty: 'No session open. File, New Session or Open Session.',
      onPick: (n) => { const f = n.data as SessionFolder | undefined; if (f?.id) library.setSource({ kind: 'folder', id: f.id, label: f.name, recursive: false }); },
    });
    this.panel.body.appendChild(this.tree.root);
    listeners.add(() => this.render());
    this.render();
  }

  private render(): void {
    const a = state.active;
    const nodes: TreeNode[] = a ? [{ key: 'session:head', label: a.name, icon: 'folderOpen', depth: 0, hasKids: false, head: true },
      ...ORDER.map(([k, ic]) => ({ key: `session:${k}`, label: a.folders[k].name, icon: ic, count: a.folders[k].count, depth: 1, hasKids: false, data: a.folders[k] }))] : [];
    this.tree.set(nodes);
    const src = library.source;
    const hit = a && src.kind === 'folder' ? ORDER.find(([k]) => a.folders[k].id === src.id) : undefined;
    this.tree.setActive(hit ? `session:${hit[0]}` : '');
  }
}
