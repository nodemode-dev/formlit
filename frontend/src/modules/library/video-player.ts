import type { Ctx } from '../../app';
import { api } from '../../io/api';
import type { Photo } from '../../state/library';
import { el, q, setHidden, setStyleVar, setText } from '../../ui/dom';
import { toast } from '../../ui/toast';

interface Trim { trimStart?: number; trimEnd?: number }

const fmt = (s: number) => {
  if (!Number.isFinite(s)) return '0:00.0';
  const m = Math.floor(s / 60);
  return `${m}:${(s - m * 60).toFixed(1).padStart(4, '0')}`;
};

export class VideoPlayer {
  readonly root = el(`<div class="fl-video" hidden><video class="fl-video-el" controls preload="metadata" playsinline></video>
<div class="fl-video-bar"><div class="fl-video-track"><div class="fl-video-range"></div><div class="fl-video-head"></div></div>
<div class="fl-video-row"><span class="fl-video-time">0:00.0</span><span class="fl-tb-spacer"></span><button class="cv-btn fl-btn-sm" type="button" data-v="in" title="Set In Point (I)">Set In</button><button class="cv-btn fl-btn-sm" type="button" data-v="out" title="Set Out Point (O)">Set Out</button><button class="cv-btn fl-btn-sm" type="button" data-v="clear">Clear Trim</button><button class="cv-btn fl-btn-sm" type="button" data-v="frame">Capture Frame</button></div></div></div>`);
  private readonly video = q<HTMLVideoElement>(this.root, 'video');
  private photo: Photo | null = null;
  private trim: Trim = {};
  private seq = 0;

  constructor(private readonly ctx: Ctx) {
    this.video.addEventListener('timeupdate', () => this.tick());
    this.video.addEventListener('loadedmetadata', () => this.paint());
    this.root.addEventListener('click', (e) => {
      const a = (e.target as HTMLElement).closest<HTMLElement>('[data-v]')?.dataset.v;
      if (a) void this.act(a);
    });
    q(this.root, '.fl-video-track').addEventListener('pointerdown', (e) => {
      const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
      if (this.video.duration) this.video.currentTime = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * this.video.duration;
    });
  }

  get active(): boolean { return !this.root.hidden; }

  async show(p: Photo | null): Promise<void> {
    const isVideo = p?.kind === 'video';
    setHidden(this.root, !isVideo);
    if (!isVideo || !p) { if (!this.video.paused) this.video.pause(); this.photo = null; return; }
    if (this.photo?.id === p.id) return;
    this.photo = p;
    const src = api.url(`/api/photos/${p.id}/original`);
    if (this.video.getAttribute('src') !== src) this.video.src = src;
    const seq = ++this.seq;
    try {
      const d = await this.ctx.api.cmd<{ settings?: Record<string, unknown> }>('develop.get', { id: p.id });
      if (seq !== this.seq) return;
      this.trim = ((d.settings ?? d) as Record<string, unknown>).video as Trim ?? {};
    } catch { this.trim = {}; }
    this.paint();
  }

  key(combo: string): boolean {
    if (!this.active) return false;
    if (combo === 'I') { void this.act('in'); return true; }
    if (combo === 'O') { void this.act('out'); return true; }
    if (combo === 'Space') { if (this.video.paused) void this.video.play(); else this.video.pause(); return true; }
    return false;
  }

  private async act(a: string): Promise<void> {
    const p = this.photo;
    if (!p) return;
    const t = this.video.currentTime;
    const dur = this.video.duration || 0;
    let start = this.trim.trimStart ?? 0, end = this.trim.trimEnd ?? 0;
    if (a === 'frame') {
      try {
        const r = await this.ctx.api.cmd<{ ids: number[] }>('video.captureFrame', { id: p.id, time: t });
        toast(r.ids.length ? `Captured the frame at ${fmt(t)} and stacked it with the video` : 'The frame was already in the catalog');
      } catch (err) { this.ctx.fail(err); }
      return;
    }
    if (a === 'in') start = t;
    else if (a === 'out') end = t >= dur - 0.05 ? 0 : t;
    else { start = 0; end = 0; }
    if (end && end <= start) { if (a === 'in') end = 0; else start = 0; }
    try {
      const r = await this.ctx.api.cmd<{ trimStart: number; trimEnd: number }>('video.trim', { id: p.id, start, end });
      this.trim = { trimStart: r.trimStart, trimEnd: r.trimEnd };
      this.paint();
    } catch (err) { this.ctx.fail(err); }
  }

  private paint(): void {
    const dur = this.video.duration || 0;
    const a = dur ? (this.trim.trimStart ?? 0) / dur : 0;
    const b = dur && this.trim.trimEnd ? this.trim.trimEnd / dur : 1;
    const range = q(this.root, '.fl-video-range');
    setStyleVar(range, 'left', `${(a * 100).toFixed(3)}%`);
    setStyleVar(range, 'width', `${(Math.max(0, b - a) * 100).toFixed(3)}%`);
    this.tick();
  }

  private tick(): void {
    const dur = this.video.duration || 0;
    const t = this.video.currentTime;
    setStyleVar(q(this.root, '.fl-video-head'), 'left', `${dur ? ((t / dur) * 100).toFixed(3) : 0}%`);
    const tr = this.trim.trimStart || this.trim.trimEnd ? ` · trimmed ${fmt(this.trim.trimStart ?? 0)} to ${fmt(this.trim.trimEnd || dur)}` : '';
    setText(q(this.root, '.fl-video-time'), `${fmt(t)} / ${fmt(dur)}${tr}`);
    if (this.trim.trimEnd && t > this.trim.trimEnd && !this.video.paused) { this.video.pause(); this.video.currentTime = this.trim.trimEnd; }
  }
}
