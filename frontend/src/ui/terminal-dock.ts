import { FitAddon } from '@xterm/addon-fit';
import { Terminal } from '@xterm/xterm';
import '@xterm/xterm/css/xterm.css';
import type { Api } from '../io/api';
import { escapeHtml, isMac, q, setDisabled, setHidden, setText, el } from './dom';
import { icon } from './icons';

export interface TermInfo { id: string; title: string; kind?: string; alive?: boolean }

interface Tab {
  id: string;
  term: Terminal;
  fit: FitAddon;
  host: HTMLElement;
  tab: HTMLElement;
  socket: WebSocket | null;
  kind: string;
}

const mod = isMac ? 'Cmd' : 'Ctrl';

function token(name: string, fallback: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

function isToggle(e: KeyboardEvent): boolean {
  return (isMac ? e.metaKey : e.ctrlKey) && !e.altKey && e.code === 'KeyJ';
}

export class TerminalDock {
  readonly root: HTMLElement;
  onFail: (err: unknown) => void = () => undefined;
  context: () => string = () => '';
  private readonly tabsEl: HTMLElement;
  private readonly stage: HTMLElement;
  private readonly empty: HTMLElement;
  private readonly ask: HTMLInputElement;
  private readonly tabs = new Map<string, Tab>();
  private active: string | null = null;

  constructor(host: HTMLElement, private readonly api: Api, onHide: () => void) {
    this.root = host;
    host.append(el(`<div class="fl-dock-rsz" role="separator" aria-orientation="horizontal" aria-label="Resize the terminal"></div>`),
      el(`<div class="fl-dock-head">
<div class="fl-dock-tabs" role="tablist" aria-label="Terminals"></div>
<span class="fl-dock-spacer"></span>
<button type="button" class="cv-tt-btn fl-dock-new" title="New Terminal" aria-label="New Terminal">${icon('plus', 15)}</button>
<button type="button" class="cv-tt-btn fl-dock-claude" title="Claude Code" aria-label="Claude Code">${icon('sparkle', 15)}</button>
<button type="button" class="cv-tt-btn fl-dock-restart" title="Restart this tab" aria-label="Restart this tab">${icon('refresh', 15)}</button>
<button type="button" class="cv-tt-btn fl-dock-hide" title="Hide Terminal (${mod}+J); programs keep running" aria-label="Hide Terminal">${icon('close', 15)}</button>
</div>`),
      el(`<div class="fl-dock-stage"><p class="fl-dock-empty cv-note" hidden>No terminal is open. Start a shell with the plus button or Claude Code with the sparkle.</p></div>`),
      el(`<form class="fl-dock-ask" autocomplete="off">
<span class="fl-dock-ask-mark">${icon('sparkle', 14)}</span>
<input class="cv-input fl-dock-ask-input" type="text" spellcheck="false" placeholder="Ask Claude Code to work on your photos" aria-label="Ask Claude Code">
<button type="submit" class="cv-tt-btn" title="Send to Claude Code" aria-label="Send to Claude Code">${icon('send', 14)}</button>
</form>`));
    this.tabsEl = q(host, '.fl-dock-tabs');
    this.stage = q(host, '.fl-dock-stage');
    this.empty = q(host, '.fl-dock-empty');
    this.ask = q<HTMLInputElement>(host, '.fl-dock-ask-input');
    q(host, '.fl-dock-new').addEventListener('click', () => void this.open());
    q(host, '.fl-dock-claude').addEventListener('click', () => void this.claude());
    q(host, '.fl-dock-restart').addEventListener('click', () => void this.restart());
    q(host, '.fl-dock-hide').addEventListener('click', onHide);
    q(host, '.fl-dock-ask').addEventListener('submit', (e) => { e.preventDefault(); void this.send(); });
    this.stage.addEventListener('keydown', (e) => { if (!isToggle(e)) e.stopPropagation(); });
    new ResizeObserver(() => this.fitActive()).observe(this.stage);
  }

  async ensure(): Promise<void> {
    const listed = await this.api.cmd<{ terminals: TermInfo[] }>('terminal.list').catch(() => ({ terminals: [] as TermInfo[] }));
    for (const t of listed.terminals) if (!this.tabs.has(t.id)) this.mount(t, false);
    if (!this.tabs.size) await this.open();
    else if (!this.active) this.select([...this.tabs.keys()][0]);
    else this.fitActive();
    this.focus();
  }

  focus(): void {
    if (this.active) this.tabs.get(this.active)?.term.focus();
  }

  async open(): Promise<void> {
    try {
      const info = await this.api.cmd<TermInfo>('terminal.open', { cols: 100, rows: 20 });
      this.mount(info, true);
    } catch (err) { this.onFail(err); }
  }

  async claude(prompt?: string): Promise<void> {
    const size = this.size();
    try {
      const info = await this.api.cmd<TermInfo>('claudecode.open', { prompt: prompt || undefined, cols: size.cols, rows: size.rows });
      if (this.tabs.has(info.id)) this.select(info.id);
      else this.mount(info, true);
    } catch (err) { this.onFail(err); }
  }

  private async send(): Promise<void> {
    const text = this.ask.value.trim();
    if (!text) return;
    const extra = this.context();
    this.ask.value = '';
    await this.claude(extra ? `${text} (${extra})` : text);
  }

  private size(): { cols: number; rows: number } {
    const t = this.active ? this.tabs.get(this.active) : null;
    return t ? { cols: t.term.cols, rows: t.term.rows } : { cols: 100, rows: 20 };
  }

  private theme() {
    return {
      background: token('--surface-0', '#111111'),
      foreground: token('--text-primary', '#f7f7f7'),
      cursor: token('--accent-color', '#f97316'),
      cursorAccent: token('--surface-0', '#111111'),
      selectionBackground: token('--accent-color-dim', '#f9731633'),
    };
  }

  private mount(info: TermInfo, show: boolean): void {
    const kind = info.kind ?? 'shell';
    const term = new Terminal({
      fontFamily: token('--font-mono', 'monospace'), fontSize: 12, lineHeight: 1.2, cursorBlink: true,
      scrollback: 5000, allowProposedApi: false, theme: this.theme(), overviewRuler: { width: 0 },
    });
    term.attachCustomKeyEventHandler((e) => !isToggle(e));
    const fit = new FitAddon();
    term.loadAddon(fit);
    const host = el(`<div class="fl-term" data-id="${escapeHtml(info.id)}" hidden></div>`);
    const tab = el(`<button type="button" class="fl-dock-tab${kind === 'claude' ? ' is-claude' : ''}" role="tab" aria-selected="false">${icon(kind === 'claude' ? 'sparkle' : 'terminal', 12)}<span class="fl-dock-tab-title"></span><span class="fl-dock-tab-x" role="button" aria-label="Close this tab">${icon('close', 11)}</span></button>`);
    setText(q(tab, '.fl-dock-tab-title'), info.title);
    tab.addEventListener('click', (e) => {
      if ((e.target as HTMLElement).closest('.fl-dock-tab-x')) void this.close(info.id);
      else this.select(info.id);
    });
    this.stage.appendChild(host);
    this.tabsEl.appendChild(tab);
    const t: Tab = { id: info.id, term, fit, host, tab, socket: null, kind };
    this.tabs.set(info.id, t);
    setHidden(this.empty, true);
    term.open(host);
    if (show || !this.active) this.select(info.id);
    this.connect(t);
  }

  private connect(t: Tab): void {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(`${proto}//${location.host}/api/terminal/${encodeURIComponent(t.id)}`);
    t.socket = socket;
    socket.addEventListener('open', () => this.sendSize(t));
    socket.addEventListener('message', (msg) => {
      const data = String(msg.data);
      if (data === '{"type": "exit"}') {
        t.term.write(`\r\n\x1b[2m[${t.kind === 'claude' ? 'Claude Code' : 'shell'} exited · Restart runs it again]\x1b[0m\r\n`);
        return;
      }
      t.term.write(data);
    });
    t.term.onData((data) => {
      if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'input', data }));
    });
  }

  private sendSize(t: Tab): void {
    if (t.socket?.readyState === WebSocket.OPEN) t.socket.send(JSON.stringify({ type: 'resize', cols: t.term.cols, rows: t.term.rows }));
  }

  fitActive(): void {
    const t = this.active ? this.tabs.get(this.active) : null;
    if (!t || t.host.hidden || this.stage.clientHeight < 20) return;
    const before = `${t.term.cols}x${t.term.rows}`;
    t.fit.fit();
    if (`${t.term.cols}x${t.term.rows}` !== before) this.sendSize(t);
  }

  private select(id: string): void {
    this.active = id;
    for (const [tid, t] of this.tabs) {
      const on = tid === id;
      setHidden(t.host, !on);
      t.tab.classList.toggle('is-on', on);
      t.tab.setAttribute('aria-selected', String(on));
    }
    setDisabled(q<HTMLButtonElement>(this.root, '.fl-dock-restart'), false);
    this.fitActive();
    this.focus();
  }

  private async restart(): Promise<void> {
    const t = this.active ? this.tabs.get(this.active) : null;
    if (!t) return;
    try {
      await this.api.cmd('terminal.restart', { id: t.id });
      this.sendSize(t);
      t.term.focus();
    } catch (err) { this.onFail(err); }
  }

  private async close(id: string): Promise<void> {
    const t = this.tabs.get(id);
    if (!t) return;
    t.socket?.close();
    t.term.dispose();
    t.host.remove();
    t.tab.remove();
    this.tabs.delete(id);
    await this.api.cmd('terminal.close', { id }).catch(() => undefined);
    if (this.active === id) {
      this.active = null;
      const next = [...this.tabs.keys()].pop();
      if (next) this.select(next);
      else setDisabled(q<HTMLButtonElement>(this.root, '.fl-dock-restart'), true);
    }
    setHidden(this.empty, this.tabs.size > 0);
  }
}
