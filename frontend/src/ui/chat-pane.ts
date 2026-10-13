import type { Api } from '../io/api';
import { events, type EngineEvent } from '../io/events';
import { el, q, setClass, setHidden, setText } from './dom';
import { icon } from './icons';

interface Part { kind: 'text' | 'tool'; text?: string; id?: string; name?: string; input?: string; status?: string }
interface Message { role: 'user' | 'assistant'; text?: string; parts?: Part[]; error?: string; meta?: { seconds?: number; turns?: number | null } }
interface State { busy: boolean; messages: Message[]; turn: number }

export class ChatPane {
  readonly root: HTMLElement;
  onBusy: (busy: boolean) => void = () => undefined;
  onFail: (err: unknown) => void = () => undefined;
  private readonly log: HTMLElement;
  private readonly empty: HTMLElement;
  private reply: HTMLElement | null = null;
  private text: HTMLElement | null = null;
  private readonly chips = new Map<string, HTMLElement>();
  private busy = false;
  private loaded = false;

  constructor(private readonly api: Api) {
    this.root = el(`<div class="fl-chat" hidden>
<div class="fl-chat-bar"><span class="fl-chat-status cv-note"></span><span class="fl-dock-spacer"></span>
<button type="button" class="cv-btn fl-btn-sm fl-chat-stop" hidden>Stop</button><button type="button" class="cv-btn fl-btn-sm fl-chat-new">New Chat</button></div>
<div class="fl-chat-log" role="log" aria-live="polite"><p class="fl-chat-empty cv-note">Ask Claude about your photos in the line below: cull a shoot, match a look, set up a job. It works through formlit's tools, every change shows here and in the window, and each one can be undone.</p></div>
</div>`);
    this.log = q(this.root, '.fl-chat-log');
    this.empty = q(this.root, '.fl-chat-empty');
    q(this.root, '.fl-chat-stop').addEventListener('click', () => void this.api.cmd('chat.cancel').catch((e) => this.onFail(e)));
    q(this.root, '.fl-chat-new').addEventListener('click', () => void this.api.cmd('chat.reset').catch((e) => this.onFail(e)));
    events.on('chat.start', (e) => { this.user(String(e.text ?? '')); this.begin(); });
    events.on('chat.delta', (e) => this.delta(String(e.text ?? '')));
    events.on('chat.tool', (e) => this.tool({ kind: 'tool', id: String(e.id ?? ''), name: String(e.name ?? ''), input: String(e.input ?? ''), status: 'running' }));
    events.on('chat.toolDone', (e) => { const c = this.chips.get(String(e.id ?? '')); if (c) this.status(c, String(e.status ?? 'done')); });
    events.on('chat.done', (e) => this.finish(e));
    events.on('chat.reset', () => { this.log.replaceChildren(this.empty); setHidden(this.empty, false); this.reply = null; this.text = null; this.chips.clear(); this.setBusy(false); });
  }

  async load(): Promise<void> {
    if (this.loaded) return;
    this.loaded = true;
    try {
      const s = await this.api.cmd<State>('chat.state');
      for (const m of s.messages) {
        if (m.role === 'user') { this.user(m.text ?? ''); continue; }
        this.begin();
        for (const p of m.parts ?? []) {
          if (p.kind === 'text') this.delta(p.text ?? '');
          else this.tool(p);
        }
        this.close(m.error ?? '', m.meta ?? {});
      }
      if (s.busy) { this.begin(); this.setBusy(true); }
    } catch (err) { this.onFail(err); }
  }

  async send(text: string): Promise<void> {
    try { await this.api.cmd('chat.send', { text }); } catch (err) { this.onFail(err); }
  }

  isBusy(): boolean { return this.busy; }

  private setBusy(on: boolean): void {
    this.busy = on;
    setHidden(q(this.root, '.fl-chat-stop'), !on);
    setText(q(this.root, '.fl-chat-status'), on ? 'Claude is working...' : '');
    this.onBusy(on);
  }

  private scroll(): void {
    const l = this.log;
    if (l.scrollHeight - l.scrollTop - l.clientHeight < 80) l.scrollTop = l.scrollHeight;
  }

  private user(text: string): void {
    setHidden(this.empty, true);
    const n = el('<div class="fl-chat-msg is-user"></div>');
    setText(n, text);
    this.log.appendChild(n);
    this.scroll();
  }

  private begin(): void {
    setHidden(this.empty, true);
    this.reply = el('<div class="fl-chat-msg is-claude"></div>');
    this.text = null;
    this.log.appendChild(this.reply);
    this.setBusy(true);
    this.scroll();
  }

  private delta(text: string): void {
    if (!this.reply) this.begin();
    if (!this.text) { this.text = el('<div class="fl-chat-text"></div>'); this.reply?.appendChild(this.text); }
    this.text.textContent = (this.text.textContent ?? '') + text;
    this.scroll();
  }

  private tool(p: Part): void {
    if (!this.reply) this.begin();
    const chip = el(`<div class="fl-chat-tool" title=""><span class="fl-chat-tool-mark">${icon('terminal', 11)}</span><span class="fl-chat-tool-name"></span><span class="fl-chat-tool-input"></span></div>`);
    setText(q(chip, '.fl-chat-tool-name'), p.name ?? '');
    setText(q(chip, '.fl-chat-tool-input'), p.input ?? '');
    chip.title = p.input ?? '';
    this.status(chip, p.status ?? 'running');
    if (p.id) this.chips.set(p.id, chip);
    this.reply?.appendChild(chip);
    this.text = null;
    this.scroll();
  }

  private status(chip: HTMLElement, s: string): void {
    for (const k of ['running', 'done', 'error']) setClass(chip, `is-${k}`, s === k);
  }

  private finish(e: EngineEvent): void {
    this.close(String(e.error ?? ''), (e.meta ?? {}) as Message['meta'] & object);
  }

  private close(error: string, meta: { seconds?: number; turns?: number | null }): void {
    if (!this.reply) this.begin();
    for (const c of this.reply?.querySelectorAll<HTMLElement>('.fl-chat-tool.is-running') ?? []) this.status(c, 'done');
    if (error) {
      const n = el('<div class="fl-chat-error"></div>');
      setText(n, error);
      this.reply?.appendChild(n);
    }
    if (meta.seconds !== undefined) {
      const n = el('<div class="fl-chat-meta"></div>');
      setText(n, `${meta.seconds} s${meta.turns ? ` · ${meta.turns} steps` : ''}`);
      this.reply?.appendChild(n);
    }
    this.reply = null;
    this.text = null;
    this.setBusy(false);
    this.scroll();
  }
}
