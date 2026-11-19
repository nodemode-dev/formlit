import type { Ctx } from './app';
import type { ConsentChoice, ConsentRequest, DockAdapter, DockAgentStatus, DockChannel, DockErrorKind, DockOwnChat, DockProgram, DockTerminal, StoredChoice, StoredChoiceState } from './dock/adapter';
import type { Dock } from './dock/dock';
import { t } from './i18n';
import { EngineError } from './io/api';
import { events, type EngineEvent } from './io/events';
import { keyHeaders, socketTicket } from './io/window-key';
import { library } from './state/library';
import { ChatPane } from './ui/chat-pane';
import { anyDialogOpen } from './ui/dialogs';
import { isMac, setHidden } from './ui/dom';
import { openPreferences } from './ui/preferences';
import { toast } from './ui/toast';

export const DOCK_KEY = 'formlit.dock';
export const DOCK_OLD_HEIGHT_KEY = 'formlit_dock_h';
const WORDS = { app: 'formlit', noun: 'photos', start: './formlit boot' } as const;
const SCOPE = 'It can search your catalog, develop photos and export files on this computer with the same commands you use here, and every change can be undone. Deleting files and switching catalogs stay with you. Allow applies to every agent on this computer until you change it in Preferences, AI agents.';
const CHOICES: ConsentChoice[] = ['deny', 'once', 'always'];

interface Pending { request?: unknown; agent?: unknown; client?: unknown; what?: unknown; answers?: unknown; alwaysCovers?: unknown; expiresAt?: unknown }
interface AgentsStatus { outsideAgents: string; pending: Pending[] }
interface EngineProgram { installed?: boolean; version?: string | null; install?: string; signedIn?: boolean | null }
interface EngineTerminal { id: string; title: string; alive?: boolean; kind?: string; cwd?: string }

export function windowContext(ctx: Ctx): string {
  const ids = library.targets();
  const where = `formlit window: ${ctx.module()} module${library.active !== null ? `, active photo id ${library.active}` : ''}`;
  if (!ids.length) return where;
  return `${where}; selection: photo ${ids.length === 1 ? 'id' : 'ids'} ${ids.slice(0, 200).join(', ')}${ids.length > 200 ? ` and ${ids.length - 200} more` : ''}`;
}

function selectionNote(): string {
  const n = library.targets().length;
  return n ? `with ${n} selected ${n === 1 ? 'photo' : 'photos'}` : '';
}

function toRequest(p: Pending): ConsentRequest | null {
  if (typeof p.request !== 'string' || !p.request) return null;
  const agent = String(p.agent ?? p.client ?? '');
  const offers = Array.isArray(p.answers) ? CHOICES.filter((c) => (p.answers as unknown[]).includes(c)) : CHOICES;
  return {
    id: p.request, agent: agent === 'an outside agent' ? '' : agent, what: String(p.what ?? 'use formlit'), offers,
    always: p.alwaysCovers === 'agent' ? 'agent' : 'all', escape: 'deny', notes: [t(SCOPE)],
    ...(typeof p.expiresAt === 'number' ? { expires: Math.round(p.expiresAt * 1000) } : {}),
  };
}

function record(x: EngineTerminal): DockTerminal {
  const kind = x.kind === 'claude' || x.kind === 'codex' || x.kind === 'cursor' ? x.kind : 'shell';
  return { id: x.id, title: x.title, alive: x.alive !== false, kind, ...(x.cwd ? { tip: x.cwd } : {}) };
}

function socketChannel(socket: WebSocket): DockChannel {
  let data = (_chunk: string | Uint8Array): void => undefined;
  let exit = (): void => undefined;
  let closed = (): void => undefined;
  socket.binaryType = 'arraybuffer';
  socket.addEventListener('message', (msg) => {
    if (typeof msg.data === 'string') { data(msg.data); return; }
    try {
      const type = (JSON.parse(new TextDecoder().decode(msg.data as ArrayBuffer)) as { type?: string }).type;
      if (type === 'exit') exit();
      else if (type === 'hello') data('');
    } catch { return; }
  });
  socket.addEventListener('close', () => closed());
  const send = (text: string): void => {
    if (socket.readyState === WebSocket.OPEN) socket.send(text);
    else if (socket.readyState === WebSocket.CONNECTING) socket.addEventListener('open', () => socket.send(text), { once: true });
  };
  return {
    send: (chunk) => send(JSON.stringify({ type: 'input', data: chunk })),
    resize: (cols, rows) => send(JSON.stringify({ type: 'resize', cols, rows })),
    onData: (handler) => { data = handler; },
    onExit: (handler) => { exit = handler; },
    onClose: (handler) => { closed = handler; },
    close: () => socket.close(),
  };
}

function errorKind(err: unknown): DockErrorKind | null {
  if (err instanceof TypeError) return 'unreachable';
  if (!(err instanceof EngineError)) return null;
  if (err.status === 403) return 'refused';
  if (err.status === 404 && /^Unknown command/i.test(err.message)) return 'oldEngine';
  if (/not installed/i.test(err.message)) return 'notInstalled';
  return err.status === 502 || err.status === 503 || err.status === 504 ? 'unreachable' : null;
}

export function formlitDock(ctx: Ctx, dock: () => Dock): DockAdapter {
  const api = ctx.api;
  const open = new Set<string>();
  const chord = (e: KeyboardEvent): boolean => (isMac ? e.metaKey && !e.ctrlKey : e.ctrlKey && !e.metaKey) && e.code === 'KeyJ';

  const chatPane = (host: HTMLElement): DockOwnChat => {
    const pane = new ChatPane(api);
    pane.onFail = (err) => ctx.fail(err);
    pane.onHandoff = (session) => void dock().claude(undefined, session);
    setHidden(pane.root, false);
    host.appendChild(pane.root);
    return {
      send: (text) => pane.send(text, windowContext(ctx), selectionNote()),
      busy: () => pane.isBusy(),
      shown: () => pane.shown(),
      hidden: () => pane.hidden(),
      closed: () => pane.closed(),
    };
  };

  const pull = (add: (r: ConsentRequest) => void, withdraw: (id: string) => void): void => {
    void api.cmd<AgentsStatus>('agents.status').then((s) => {
      const waiting = s.outsideAgents === 'ask' ? s.pending.map(toRequest).filter((r): r is ConsentRequest => r !== null) : [];
      const live = new Set(waiting.map((r) => r.id));
      for (const id of [...open]) if (!live.has(id)) { open.delete(id); withdraw(id); }
      for (const r of waiting) { open.add(r.id); add(r); }
    }, () => undefined);
  };

  return {
    words: {
      ...WORDS, example: 'cull this shoot',
      lead: "Ask Claude about your photos in the line below: cull a shoot, match a look, set up a job. It works through formlit's tools, every change shows here and in the window, and each one can be undone.",
    },
    strings: {
      consentTitle: 'Allow an agent calling itself {agent} to use {app}?',
      consentTitleUnnamed: 'Allow an outside agent to use {app}?',
      consentChanged: 'The saved agent permission was changed outside formlit, so it is back to "Ask me".',
      outsideAgents: 'AI agents',
      tourAskBody: 'If another AI program on this computer wants to use {app}, {app} asks you first in a box in the middle of the window. Choose Deny, Allow once or Always allow. You can change your answer later under AI agents in the menu here.',
      tourMissingBody: "For Chat and the bigger jobs, {app} uses a program called Claude Code. To add it, copy the line below, open your computer's command window, paste it and press Enter.",
    },
    placement: {
      mode: 'own',
      storage: {
        key: DOCK_KEY,
        legacy: {
          keys: [DOCK_OLD_HEIGHT_KEY],
          read: (store) => { const h = Number(store.getItem(DOCK_OLD_HEIGHT_KEY)); return h > 0 ? { h, seen: true } : null; },
        },
      },
      sizes: { minHeight: 140, maxHeightShare: 0.7, defaultHeight: 280, minWidth: 320, maxWidthShare: 0.4, defaultWidth: 440 },
    },
    isDockChord: (e) => chord(e) && !e.shiftKey && !e.altKey && !(anyDialogOpen() && !(e.target instanceof Element && e.target.closest('.ft-dock'))),
    chordLabel: () => `${isMac ? 'Cmd' : 'Ctrl'}+J`,
    passKey: (e) => chord(e) && e.shiftKey !== e.altKey,
    tabs: () => ({ builtin: ['chat', 'shell', 'claude', 'codex', 'cursor'] }),
    classes: { iconButton: 'cv-tt-btn', button: 'cv-btn', primaryButton: 'cv-btn-primary', input: 'cv-input', select: 'cv-select', note: 'cv-note' },
    t: (_key, english) => t(english.replace(/\{(app|noun|start)\}/g, (_m, name: keyof typeof WORDS) => WORDS[name])),
    onTheme: (handler) => { document.addEventListener('nm:ui-settings-changed', handler); },
    keyHeaders,
    errors: { message: (err) => (err instanceof EngineError ? err.message : null), kind: errorKind },
    firstRun: () => !anyDialogOpen(),
    terminal: {
      list: async () => (await api.cmd<{ terminals: EngineTerminal[] }>('terminal.list')).terminals.map(record),
      open: async (kind, o) => {
        if (kind === 'shell') return record(await api.cmd<EngineTerminal>('terminal.open', { cols: o.cols, rows: o.rows }));
        if (kind === 'claude') {
          const extra = o.prompt ? windowContext(ctx) : '';
          const prompt = o.prompt ? (extra ? `${o.prompt} (${extra})` : o.prompt) : undefined;
          return record(await api.cmd<EngineTerminal>('claudecode.open', { prompt, resume: o.resume || undefined, cols: o.cols, rows: o.rows }));
        }
        return record(await api.cmd<EngineTerminal>('terminal.openAgent', { kind, cols: o.cols, rows: o.rows }));
      },
      restart: async (id) => { await api.cmd('terminal.restart', { id }); },
      close: async (id) => { await api.cmd('terminal.close', { id }).catch(() => undefined); },
      channel: async (id) => {
        const ticket = await socketTicket();
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        return socketChannel(new WebSocket(`${proto}//${location.host}/api/terminal/${encodeURIComponent(id)}?ticket=${encodeURIComponent(ticket)}&control=binary`));
      },
      scrollback: 5000,
    },
    agentStatus: async () => {
      const now = await api.cmd<Partial<Record<DockProgram, EngineProgram>>>('terminal.agents');
      const out: DockAgentStatus = {};
      for (const kind of ['claude', 'codex', 'cursor'] as const) {
        const p = now[kind];
        if (p) out[kind] = { installed: p.installed === true, version: p.version ?? null, install: p.install ?? '', signedIn: p.signedIn ?? null };
      }
      return out;
    },
    chat: { pane: chatPane, ask: 'line' },
    consent: {
      subscribe: (add, withdraw) => {
        const gone = (id: string): void => { if (open.delete(id)) withdraw(id); };
        events.on('agents.consent', (e: EngineEvent) => { const r = toRequest(e as Pending); if (r) { open.add(r.id); add(r); } });
        events.on('agents.withdrawn', (e) => gone(String(e.request ?? '')));
        events.on('agents.changed', (e) => { if (e.outsideAgents !== 'ask') for (const id of [...open]) gone(id); });
        events.on('hello', () => pull(add, withdraw));
        events.on('resync', () => pull(add, withdraw));
      },
      answer: async (id, choice) => {
        open.delete(id);
        const params = choice === 'always' ? { choice: 'allow' } : { choice: choice === 'once' ? 'once' : 'later', request: id };
        try {
          await api.cmd('agents.respond', params);
          if (choice === 'always') toast(t('AI agents allowed. Change this in Preferences, AI agents.'));
        } catch (err) {
          if (!(err instanceof EngineError && err.status === 409)) ctx.fail(err);
        }
      },
    },
    storedChoice: {
      get: async (): Promise<StoredChoiceState> => {
        const p = await api.cmd<{ outsideAgents?: unknown; sealBroken?: unknown }>('prefs.get');
        const value: StoredChoice = p.outsideAgents === 'allowed' || p.outsideAgents === 'blocked' ? p.outsideAgents : 'ask';
        return { value, changedOutside: p.sealBroken === true && value === 'ask' };
      },
      set: async (value) => { await api.cmd('prefs.set', { values: { outsideAgents: value } }); },
    },
    openSettings: () => openPreferences(ctx),
  };
}
