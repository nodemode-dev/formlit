import type { Ctx } from '../../app';
import { askForm } from '../../ui/askform';
import { promptName } from '../../ui/dialogs';
import { PopupMenu, type MenuItem } from '../../ui/menu';
import { applyPanelState, arrange, isPanelHidden, isSolo, PANELS, panelState, setPanelVisible, setSolo, sideOf, type PanelState, type Side } from '../../ui/panel';
import type { ShellLayout } from '../../ui/shell';
import { toast } from '../../ui/toast';
import { modules } from '../registry';

interface Workspace { name: string; layout: Partial<ShellLayout>; dock: boolean; panels?: Partial<PanelState> }
interface Builtin extends Workspace { id: string }

const CURRENT_KEY = 'formlit_workspace';
const BUILTIN: Builtin[] = [
  { id: 'default', name: 'Default', dock: false, layout: { left: null, right: null, leftHidden: false, rightHidden: false, filmstripHidden: false, toolbarHidden: false, dockH: null, stripH: null, stripCollapsed: false, stripTop: false }, panels: { solo: { left: false, right: false } } },
  { id: 'culling', name: 'Culling: Big Grid', dock: false, layout: { leftHidden: true, rightHidden: true, filmstripHidden: true, toolbarHidden: false } },
  { id: 'editing', name: 'Editing: Wide Panels, One at a Time', dock: false, layout: { left: 220, right: 380, leftHidden: false, rightHidden: false, filmstripHidden: false, toolbarHidden: false }, panels: { solo: { left: false, right: true } } },
  { id: 'agent', name: 'Working with Claude', dock: true, layout: { leftHidden: true, rightHidden: false, filmstripHidden: false, toolbarHidden: false, dockH: 340, stripCollapsed: true } },
  { id: 'photo', name: 'Photo Only', dock: false, layout: { leftHidden: true, rightHidden: true, filmstripHidden: true, toolbarHidden: true } },
];

const slug = (name: string): string => name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'workspace';

function current(): string { try { return localStorage.getItem(CURRENT_KEY) ?? ''; } catch { return ''; } }
function setCurrent(id: string): void { try { localStorage.setItem(CURRENT_KEY, id); } catch { return; } }

export function registerWorkspace(ctx: Ctx): void {
  let saved: Record<string, Workspace> = {};
  const userIds = new Set<string>();

  const apply = async (id: string, w: Workspace): Promise<void> => {
    ctx.shell.applyLayout(w.layout);
    if (w.panels) applyPanelState(w.panels);
    if (w.dock !== ctx.shell.dockOpen()) {
      if (w.dock) ctx.run('agent.chat'); else ctx.run('view.terminal');
    }
    setCurrent(id);
    toast(`Workspace: ${w.name}`);
  };

  const snapshot = (name: string): Workspace => ({ name, layout: ctx.shell.layout(), dock: ctx.shell.dockOpen(), panels: panelState() });

  const persist = async (next: Record<string, Workspace>): Promise<void> => {
    await ctx.api.cmd('prefs.set', { values: { workspaces: next } });
    saved = next;
    for (const id of [...userIds]) if (!(id in next)) { ctx.commands.remove(`workspace.user.${id}`); userIds.delete(id); }
    for (const id of Object.keys(next)) addUser(id);
  };

  const addUser = (id: string): void => {
    if (userIds.has(id)) return;
    userIds.add(id);
    ctx.commands.add({ id: `workspace.user.${id}`, label: () => saved[id]?.name ?? id, run: () => { const w = saved[id]; if (w) void apply(`user.${id}`, w); }, checked: () => current() === `user.${id}`, enabled: () => !!saved[id] });
  };

  ctx.commands.add(
    ...BUILTIN.map((b) => ({ id: `workspace.${b.id}`, label: b.name, run: () => void apply(b.id, b), checked: () => current() === b.id })),
    { id: 'workspace.save', label: 'Save Workspace...', run: async () => {
      const name = await promptName('Save Workspace', 'My Workspace', 'Save');
      if (!name) return;
      try {
        await persist({ ...saved, [slug(name)]: snapshot(name) });
        setCurrent(`user.${slug(name)}`);
        toast(`Saved workspace ${name}: panel widths, what is shown, panel order and Solo Mode`);
      } catch (err) { ctx.fail(err, 'Save Workspace'); }
    } },
    { id: 'workspace.delete', label: 'Delete Workspace...', enabled: () => Object.keys(saved).length > 0, run: async () => {
      const opts = Object.entries(saved).map(([id, w]): [string, string] => [id, w.name]);
      const v = await askForm('Delete Workspace', 'The built-in workspaces stay.', [{ path: 'id', label: 'Workspace', kind: 'select', options: opts }], { id: opts[0]?.[0] ?? '' }, 'Delete');
      if (!v) return;
      const next = { ...saved };
      delete next[String(v.id)];
      try { await persist(next); toast('Workspace deleted'); } catch (err) { ctx.fail(err, 'Delete Workspace'); }
    } },
    { id: 'workspace.resetPanels', label: 'Reset Panels', run: () => { applyPanelState({ hidden: [], order: {}, solo: { left: false, right: false } }); toast('Every panel is shown again in its original order'); } },
    ...(['left', 'right'] as Side[]).map((side) => ({
      id: `view.solo.${side}`, label: `Solo Mode: ${side === 'left' ? 'Left' : 'Right'} Panels`, checked: () => isSolo(side),
      run: () => { setSolo(side, !isSolo(side)); toast(`Solo Mode ${isSolo(side) ? 'on' : 'off'}: opening a ${side} panel ${isSolo(side) ? 'closes the others' : 'leaves the others as they are'}`); },
    })),
  );

  const panelCommand = (id: string): string => {
    const cid = `panel.show.${id}`;
    if (!ctx.commands.get(cid)) {
      ctx.commands.add({ id: cid, label: () => PANELS.get(id)?.title ?? id, checked: () => !isPanelHidden(id), run: () => setPanelVisible(id, isPanelHidden(id)) });
    }
    return cid;
  };

  const menu = new PopupMenu(ctx.commands, null, true);
  document.addEventListener('fl-panel-menu', (e) => {
    const { id, x, y } = (e as CustomEvent<{ id: string; x: number; y: number }>).detail;
    const root = PANELS.get(id)?.root;
    const col = root?.parentElement;
    if (!root || !col) return;
    const side = sideOf(root);
    const ids = Array.from(col.children).map((n) => (n as HTMLElement).dataset?.panel).filter((x): x is string => !!x && PANELS.has(x));
    const items: MenuItem[] = [...ids.map(panelCommand), '-', ...(side ? [`view.solo.${side}`] : []), 'workspace.resetPanels'];
    menu.setItems(items);
    menu.openAt(x, y);
  });

  const moduleCommand = (id: string, label: string): string => {
    const cid = `module.show.${id}`;
    if (!ctx.commands.get(cid)) {
      ctx.commands.add({ id: cid, label, checked: () => !ctx.shell.hiddenModules().includes(id), run: () => {
        const show = ctx.shell.hiddenModules().includes(id);
        if (!show && modules().filter((m) => !ctx.shell.hiddenModules().includes(m.id)).length <= 1) { toast('Keep at least one module in the picker'); return; }
        ctx.shell.setModuleShown(id, show);
      } });
    }
    return cid;
  };
  ctx.shell.modulesBar.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    menu.setItems([...modules().map((m) => moduleCommand(m.id, m.label))]);
    menu.openAt(e.clientX, e.clientY);
  });
  const stripHead = (e: Event): boolean => {
    const t = e.target as HTMLElement;
    return !!t.closest('.fl-fs-head') && !t.closest('button');
  };
  ctx.shell.filmstrip.addEventListener('contextmenu', (e) => {
    if (!stripHead(e)) return;
    e.preventDefault();
    menu.setItems(['view.filmstripCollapse', 'view.filmstripTop', '-', 'view.toggleFilmstrip']);
    menu.openAt(e.clientX, e.clientY);
  });
  ctx.shell.filmstrip.addEventListener('dblclick', (e) => { if (stripHead(e)) ctx.run('view.filmstripCollapse'); });

  const watch = (sel: string) => {
    const host = document.querySelector(sel);
    if (!host) return;
    new MutationObserver((ms) => {
      const parents = new Set<Element>();
      for (const m of ms) for (const n of Array.from(m.addedNodes)) {
        if (n instanceof HTMLElement && (n.classList.contains('fl-panel') || n.querySelector('.fl-panel'))) {
          if (n.classList.contains('fl-panel') && n.parentElement) parents.add(n.parentElement);
          for (const p of Array.from(n.querySelectorAll('.fl-panel'))) if (p.parentElement) parents.add(p.parentElement);
        }
      }
      for (const c of parents) arrange(c);
    }).observe(host, { childList: true, subtree: true });
    for (const p of Array.from(host.querySelectorAll('.fl-panel'))) if (p.parentElement) arrange(p.parentElement);
  };
  watch('.fl-left .fl-col-pages');
  watch('.fl-right .fl-col-pages');

  void ctx.api.cmd<Record<string, unknown>>('prefs.get').then((p) => {
    saved = (p.workspaces as Record<string, Workspace> | undefined) ?? {};
    for (const id of Object.keys(saved)) addUser(id);
  }, () => undefined);
}

export function workspaceMenu(ctx: Ctx): MenuItem {
  const ids = (prefix: string) => ctx.commands.all().map((c) => c.id).filter((id) => id.startsWith(prefix));
  return {
    label: 'Workspace',
    items: [...BUILTIN.map((b) => `workspace.${b.id}`), ...(ids('workspace.user.').length ? ['-', ...ids('workspace.user.')] : []), '-', 'workspace.save', 'workspace.delete', '-', 'view.solo.left', 'view.solo.right', 'workspace.resetPanels'],
  };
}
