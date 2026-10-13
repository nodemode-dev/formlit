import type { Ctx } from '../../app';
import { library } from '../../state/library';
import { TerminalDock } from '../../ui/terminal-dock';

export function registerTerminal(ctx: Ctx): void {
  let dock: TerminalDock | null = null;
  const shell = ctx.shell;
  const get = (): TerminalDock => {
    if (dock) return dock;
    dock = new TerminalDock(shell.dock, ctx.api, () => shell.setDock(false));
    dock.onFail = (err) => ctx.fail(err);
    dock.context = () => {
      const ids = library.targets();
      if (!ids.length) return '';
      return `formlit selection: photo ${ids.length === 1 ? 'id' : 'ids'} ${ids.slice(0, 200).join(', ')}${ids.length > 200 ? ` and ${ids.length - 200} more` : ''}`;
    };
    dock.note = () => {
      const n = library.targets().length;
      return n ? `with ${n} selected ${n === 1 ? 'photo' : 'photos'}` : '';
    };
    return dock;
  };
  const show = async (): Promise<TerminalDock> => {
    const d = get();
    if (!shell.dockOpen()) {
      shell.setDock(true);
      await d.ensure();
    }
    return d;
  };
  ctx.commands.add(
    { id: 'view.terminal', label: 'Show Terminal', keys: ['Mod+J'], checked: () => shell.dockOpen(), run: async () => {
      if (shell.dockOpen()) shell.setDock(false);
      else await show();
    } },
    { id: 'view.newTerminal', label: 'New Terminal', run: async () => { const wasOpen = shell.dockOpen(); const d = await show(); if (wasOpen) await d.open(); } },
    { id: 'agent.claude', label: 'Claude Code', keys: ['Shift+Mod+J'], run: async () => {
      const d = get();
      if (!shell.dockOpen()) shell.setDock(true);
      await d.claude();
    } },
    { id: 'agent.chat', label: 'Chat with Claude', keys: ['Alt+Mod+J'], run: async () => {
      const d = get();
      if (!shell.dockOpen()) shell.setDock(true);
      await d.showChat();
    } },
  );
}
