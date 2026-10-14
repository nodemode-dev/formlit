import type { Api } from '../io/api';
import { events, type EngineEvent } from '../io/events';
import { library } from '../state/library';
import { askForm } from './askform';
import { el, q, setClass, setHidden, setText } from './dom';
import { icon } from './icons';
import { MarkdownStream } from './markdown';
import { thumbUrl } from './thumbs';
import { locale } from '../i18n';

interface Part { kind: 'text' | 'tool'; text?: string; id?: string; name?: string; input?: string; status?: string; photos?: number[]; images?: string[] }
const STRIP = 8;
interface Meta { seconds?: number; turns?: number | null; costUsd?: number | null; inputTokens?: number; outputTokens?: number }
interface Message { role: 'user' | 'assistant'; text?: string; note?: string; parts?: Part[]; error?: string; meta?: Meta }
interface Usage { input: number; output: number; costUsd: number; context: number; window: number; model: string }
interface State { busy: boolean; messages: Message[]; turn: number; session: string; usage?: Usage }

function tokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n % 1_000_000 ? 1 : 0)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 100_000 ? 0 : 1)}k`;
  return String(n);
}

export class ChatPane {
  readonly root: HTMLElement;
  onBusy: (busy: boolean) => void = () => undefined;
  onFail: (err: unknown) => void = () => undefined;
  onHandoff: (session: string) => void = () => undefined;
  private readonly log: HTMLElement;
  private readonly empty: HTMLElement;
  private readonly meter: HTMLElement;
  private reply: HTMLElement | null = null;
  private md: MarkdownStream | null = null;
  private usage: Usage = { input: 0, output: 0, costUsd: 0, context: 0, window: 0, model: '' };
  private readonly chips = new Map<string, HTMLElement>();
  private busy = false;
  private loaded = false;

  constructor(private readonly api: Api) {
    this.root = el(`<div class="fl-chat" hidden>
<div class="fl-chat-bar"><span class="fl-chat-status cv-note"></span><span class="fl-chat-usage" title="Memory: how much of Claude's working memory this conversation uses (it reads all of it again with each message). Reply: tokens written so far. Chat: everything sent and written in this conversation, and what it has cost."></span><span class="fl-dock-spacer"></span>
<button type="button" class="cv-btn fl-btn-sm fl-chat-stop" hidden>Stop</button>
<button type="button" class="cv-btn fl-btn-sm fl-chat-adopt" title="Bring a conversation you had in a Claude Code tab into this chat">From Claude Code...</button>
<button type="button" class="cv-btn fl-btn-sm fl-chat-handoff" title="Continue this conversation in a Claude Code terminal tab">Open in Claude Code</button>
<button type="button" class="cv-btn fl-btn-sm fl-chat-new">New Chat</button></div>
<div class="fl-chat-log" role="log" aria-live="polite"><p class="fl-chat-empty cv-note">Ask Claude about your photos in the line below: cull a shoot, match a look, set up a job. It works through formlit's tools, every change shows here and in the window, and each one can be undone.</p></div>
</div>`);
    this.log = q(this.root, '.fl-chat-log');
    this.empty = q(this.root, '.fl-chat-empty');
    this.meter = q(this.root, '.fl-chat-usage');
    q(this.root, '.fl-chat-stop').addEventListener('click', () => void this.api.cmd('chat.cancel').catch((e) => this.onFail(e)));
    q(this.root, '.fl-chat-new').addEventListener('click', () => void this.api.cmd('chat.reset').catch((e) => this.onFail(e)));
    q(this.root, '.fl-chat-handoff').addEventListener('click', () => void this.handoff());
    q(this.root, '.fl-chat-adopt').addEventListener('click', () => void this.adopt());
    events.on('chat.usage', (e) => this.showUsage({ ...this.usage, context: Number(e.context ?? 0), window: Number(e.window ?? 0) || this.usage.window, model: String(e.model ?? this.usage.model) }, Number(e.output ?? 0)));
    events.on('chat.adopted', () => { this.loaded = false; this.log.replaceChildren(this.empty); this.reply = null; this.md = null; this.chips.clear(); void this.load(); });
    events.on('chat.start', (e) => { this.user(String(e.text ?? ''), String(e.note ?? '')); this.begin(); });
    events.on('chat.delta', (e) => this.delta(String(e.text ?? '')));
    events.on('chat.tool', (e) => this.tool({ kind: 'tool', id: String(e.id ?? ''), name: String(e.name ?? ''), input: String(e.input ?? ''), status: 'running', photos: Array.isArray(e.photos) ? (e.photos as number[]) : [] }));
    this.log.addEventListener('click', (e) => {
      const strip = (e.target as HTMLElement).closest<HTMLElement>('.fl-chat-photos');
      if (strip?.dataset.ids) this.pick(strip.dataset.ids.split(',').map(Number));
    });
    events.on('chat.toolDone', (e) => {
      const c = this.chips.get(String(e.id ?? ''));
      if (!c) return;
      this.status(c, String(e.status ?? 'done'));
      if (Array.isArray(e.images) && e.images.length) this.images(c, e.images as string[]);
    });
    events.on('chat.done', (e) => { this.finish(e); if (e.usage) this.showUsage(e.usage as Usage, -1); });
    events.on('chat.reset', () => {
      this.log.replaceChildren(this.empty); setHidden(this.empty, false); this.reply = null; this.md = null; this.chips.clear(); this.setBusy(false);
      this.showUsage({ input: 0, output: 0, costUsd: 0, context: 0, window: 0, model: '' }, -1);
    });
  }

  async load(): Promise<void> {
    if (this.loaded) return;
    this.loaded = true;
    try {
      const s = await this.api.cmd<State>('chat.state');
      for (const m of s.messages) {
        if (m.role === 'user') { this.user(m.text ?? '', m.note ?? ''); continue; }
        this.begin();
        for (const p of m.parts ?? []) {
          if (p.kind === 'text') this.delta(p.text ?? '');
          else this.tool(p);
        }
        this.close(m.error ?? '', m.meta ?? {});
      }
      if (s.usage) this.showUsage(s.usage, -1);
      if (s.busy) { this.begin(); this.setBusy(true); }
    } catch (err) { this.onFail(err); }
  }

  async send(text: string, context = '', note = ''): Promise<void> {
    try { await this.api.cmd('chat.send', { text, context, note }); } catch (err) { this.onFail(err); }
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

  private user(text: string, note = ''): void {
    setHidden(this.empty, true);
    const n = el('<div class="fl-chat-msg is-user"><span class="fl-chat-said"></span></div>');
    setText(q(n, '.fl-chat-said'), text);
    if (note) { const m = el('<span class="fl-chat-note"></span>'); setText(m, note); n.appendChild(m); }
    this.log.appendChild(n);
    this.scroll();
  }

  private begin(): void {
    setHidden(this.empty, true);
    this.endText();
    this.reply = el('<div class="fl-chat-msg is-claude"></div>');
    this.log.appendChild(this.reply);
    this.setBusy(true);
    this.scroll();
  }

  private delta(text: string): void {
    if (!this.reply) this.begin();
    if (!this.md) { this.md = new MarkdownStream('fl-chat-text fl-md'); this.reply?.appendChild(this.md.root); }
    this.md.push(text);
    this.scroll();
  }

  private endText(): void {
    this.md?.end();
    this.md = null;
  }

  private images(after: HTMLElement, paths: string[]): void {
    const row = el('<div class="fl-chat-images"></div>');
    for (const path of paths.slice(0, 6)) {
      const img = el<HTMLImageElement>('<img alt="What Claude looked at" decoding="async" draggable="false">');
      img.src = this.api.url(`/api/files/thumb?path=${encodeURIComponent(path)}&long=640`);
      row.appendChild(img);
    }
    after.after(row);
    this.scroll();
  }

  private showUsage(u: Usage, reply: number): void {
    this.usage = u;
    if (!u.context && !u.input && reply < 0) { setText(this.meter, ''); return; }
    const parts: string[] = [];
    if (u.context) parts.push(`Memory ${tokens(u.context)}${u.window ? ` of ${tokens(u.window)}` : ''}`);
    if (reply >= 0) parts.push(`Reply ${tokens(reply)} tokens`);
    if (u.input || u.output) parts.push(`Chat ${tokens(u.input + u.output)} tokens${u.costUsd ? ` · $${u.costUsd.toFixed(u.costUsd < 1 ? 3 : 2)}` : ''}`);
    setText(this.meter, parts.join(' · '));
    setClass(this.meter, 'is-high', !!u.window && u.context / u.window > 0.8);
  }

  private async handoff(): Promise<void> {
    try {
      const s = await this.api.cmd<State>('chat.state');
      if (!s.session) { this.onFail(new Error('Start a conversation here first; then it can continue in Claude Code')); return; }
      if (s.busy) { this.onFail(new Error('Wait for Claude to finish, or press Stop, before moving the conversation')); return; }
      this.onHandoff(s.session);
    } catch (err) { this.onFail(err); }
  }

  private async adopt(): Promise<void> {
    try {
      const r = await this.api.cmd<{ sessions: Array<{ id: string; title: string; modified: number; current: boolean }> }>('chat.sessions');
      if (!r.sessions.length) { this.onFail(new Error('No Claude Code conversation in formlit yet: open one with the robot button first')); return; }
      const when = (t: number) => new Date(t * 1000).toLocaleString(locale(), { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
      const opts = r.sessions.map((s): [string, string] => [s.id, `${when(s.modified)} · ${s.title || 'untitled'}${s.current ? ' (this chat)' : ''}`]);
      const v = await askForm('Continue from Claude Code', 'Brings a conversation from a Claude Code tab into this chat: its messages show here and your next message continues it.', [{ path: 'session', label: 'Conversation', kind: 'select', options: opts }], { session: opts[0][0] }, 'Continue Here');
      if (v) await this.api.cmd('chat.adopt', { session: String(v.session) });
    } catch (err) { this.onFail(err); }
  }

  private tool(p: Part): void {
    if (!this.reply) this.begin();
    this.endText();
    const chip = el(`<div class="fl-chat-tool" title=""><span class="fl-chat-tool-mark">${icon('terminal', 11)}</span><span class="fl-chat-tool-name"></span><span class="fl-chat-tool-input"></span></div>`);
    setText(q(chip, '.fl-chat-tool-name'), p.name ?? '');
    setText(q(chip, '.fl-chat-tool-input'), p.input ?? '');
    chip.title = p.input ?? '';
    this.status(chip, p.status ?? 'running');
    if (p.id) this.chips.set(p.id, chip);
    this.reply?.appendChild(chip);
    const ids = (p.photos ?? []).filter((id) => library.photo(id));
    if (ids.length) {
      const strip = el(`<button type="button" class="fl-chat-photos" title="Select ${ids.length === 1 ? 'this photo' : `these ${ids.length} photos`} in the window"></button>`);
      strip.dataset.ids = ids.join(',');
      for (const id of ids.slice(0, STRIP)) {
        const photo = library.photo(id);
        if (!photo) continue;
        const img = el<HTMLImageElement>('<img alt="" loading="lazy" decoding="async" draggable="false">');
        img.src = thumbUrl(photo);
        strip.appendChild(img);
      }
      if (ids.length > STRIP) { const more = el('<span class="fl-chat-more"></span>'); setText(more, `+${ids.length - STRIP}`); strip.appendChild(more); }
      this.reply?.appendChild(strip);
    }
    if (p.images?.length) this.images(chip, p.images);
    this.scroll();
  }

  private pick(ids: number[]): void {
    const shown = ids.filter((id) => library.photo(id));
    if (!shown.length) return;
    library.select(shown[0], 'only');
    for (const id of shown.slice(1)) library.select(id, 'add');
    library.setActive(shown[0]);
  }

  private status(chip: HTMLElement, s: string): void {
    for (const k of ['running', 'done', 'error']) setClass(chip, `is-${k}`, s === k);
  }

  private finish(e: EngineEvent): void {
    this.close(String(e.error ?? ''), (e.meta ?? {}) as Message['meta'] & object);
  }

  private close(error: string, meta: Meta): void {
    if (!this.reply) this.begin();
    this.endText();
    for (const c of this.reply?.querySelectorAll<HTMLElement>('.fl-chat-tool.is-running') ?? []) this.status(c, 'done');
    if (error) {
      const n = el('<div class="fl-chat-error"></div>');
      setText(n, error);
      this.reply?.appendChild(n);
    }
    if (meta.seconds !== undefined) {
      const n = el('<div class="fl-chat-meta"></div>');
      const used = meta.inputTokens || meta.outputTokens ? ` · ${tokens((meta.inputTokens ?? 0) + (meta.outputTokens ?? 0))} tokens` : '';
      setText(n, `${meta.seconds} s${meta.turns ? ` · ${meta.turns} steps` : ''}${used}${meta.costUsd ? ` · $${meta.costUsd.toFixed(3)}` : ''}`);
      this.reply?.appendChild(n);
    }
    this.reply = null;
    this.setBusy(false);
    this.scroll();
  }
}
