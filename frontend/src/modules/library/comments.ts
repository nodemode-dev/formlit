import type { Ctx } from '../../app';
import { library } from '../../state/library';
import { el, escapeHtml, patchList, q, setHidden, setHtml, setText } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { Panel } from '../../ui/panel';

interface Comment { id?: string; author: string; text: string; time: string }
interface Thread { collection: number; name: string; comments: Comment[]; error: string }

const when = (t: string) => { const d = new Date(t); return Number.isNaN(d.getTime()) ? t : d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }); };

export class CommentsPanel {
  readonly panel: Panel;
  private readonly note = el('<p class="cv-note fl-cmt-note"></p>');
  private readonly threads = el('<div class="fl-cmt-threads"></div>');
  private seq = 0;
  private timer = 0;
  private shown: number | null = null;

  constructor(private readonly ctx: Ctx) {
    const refresh = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" title="Refresh Comments" aria-label="Refresh Comments">${icon('refresh', 14)}</button>`);
    refresh.addEventListener('click', () => void this.fetch(true));
    this.panel = new Panel('lib.comments', 'Comments', { open: false, tools: [refresh] });
    this.panel.body.append(this.note, this.threads);
    this.panel.onOpen = (open) => { if (open) this.soon(0); };
    this.threads.addEventListener('submit', (e) => {
      e.preventDefault();
      const f = e.target as HTMLFormElement;
      const input = q<HTMLInputElement>(f, 'input');
      void this.add(Number(f.dataset.col), input);
    });
    library.listen('selection', () => this.soon(150));
    this.paintNote('Select a published photo to read and add comments from its services.');
  }

  private soon(ms: number): void {
    if (!this.panel.isOpen) return;
    window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => void this.fetch(false), ms);
  }

  private paintNote(text: string): void {
    setText(this.note, text);
    setHidden(this.note, !text);
  }

  private async fetch(force: boolean): Promise<void> {
    const id = library.active;
    if (id === this.shown && !force) return;
    const seq = ++this.seq;
    if (id === null) { this.shown = null; this.paint([]); this.paintNote('Select a published photo to read and add comments from its services.'); return; }
    try {
      const r = await this.ctx.api.cmd<{ threads: Thread[] }>('publish.comments', { id });
      if (seq !== this.seq) return;
      this.shown = id;
      this.paint(r.threads);
      this.paintNote(r.threads.length ? '' : 'This photo is not published to a service that takes comments.');
    } catch (err) { if (seq === this.seq) this.paintNote(String((err as Error).message ?? err)); }
  }

  private paint(threads: Thread[]): void {
    const update = (n: HTMLElement, t: Thread) => {
      setText(q(n, '.fl-cmt-name'), t.name);
      const html = t.error ? `<p class="fl-cmt-error">${escapeHtml(t.error)}</p>` : t.comments.length
        ? t.comments.map((c) => `<div class="fl-cmt"><div class="fl-cmt-head"><b>${escapeHtml(c.author)}</b><span>${escapeHtml(when(c.time))}</span></div><div class="fl-cmt-text">${escapeHtml(c.text)}</div></div>`).join('')
        : '<p class="fl-muted">No comments yet</p>';
      setHtml(q(n, '.fl-cmt-list'), html, html);
    };
    patchList(this.threads, threads, {
      key: (t) => String(t.collection),
      create: (t) => { const n = el(`<div class="fl-cmt-thread"><div class="fl-sub fl-cmt-name"></div><div class="fl-cmt-list"></div><form class="fl-cmt-add" data-col="${t.collection}"><input class="cv-input" type="text" placeholder="Add a comment" spellcheck="true"><button class="cv-btn fl-btn-sm" type="submit">Post</button></form></div>`); update(n, t); return n; },
      update,
    });
  }

  private async add(collection: number, input: HTMLInputElement): Promise<void> {
    const id = library.active;
    const text = input.value.trim();
    if (id === null || !text) return;
    input.disabled = true;
    try {
      const r = await this.ctx.api.cmd<{ threads: Thread[] }>('publish.addComment', { collection, id, text });
      input.value = '';
      if (library.active === id) this.paint(r.threads);
    } catch (err) { this.ctx.fail(err); } finally { input.disabled = false; }
  }
}
