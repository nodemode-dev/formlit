import type { Ctx } from '../../app';
import { Dock } from '../../dock/dock';
import { formlitDock } from '../../dock-adapter';

let mounted: Dock | null = null;

export const dockOpen = (): boolean => mounted?.isOpen() === true;

export function registerTerminal(ctx: Ctx): void {
  const dock: Dock = new Dock(formlitDock(ctx, () => dock));
  mounted = dock;
  dock.mount(ctx.shell.app, ctx.shell.status);
  ctx.commands.add(
    { id: 'view.terminal', label: 'Show Terminal', keys: ['Mod+J'], checked: () => dock.isOpen(), run: () => dock.toggle() },
    { id: 'view.newTerminal', label: 'New Terminal', run: () => dock.newTerminal() },
    { id: 'agent.claude', label: 'Claude Code', keys: ['Shift+Mod+J'], run: async () => { if (!dock.isOpen()) dock.toggle(true, 'none'); await dock.claude(); } },
    { id: 'agent.chat', label: 'Chat with Claude', keys: ['Alt+Mod+J'], run: () => dock.show('chat') },
  );
}
