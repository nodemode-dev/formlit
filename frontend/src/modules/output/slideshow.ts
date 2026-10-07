import { api } from '../../io/api';
import { library } from '../../state/library';
import { el, setClass, setDisabled, setStyleVar, setText } from '../../ui/dom';
import { folderOf, pickFolder } from '../../ui/folder-picker';
import { icon } from '../../ui/icons';
import { toast } from '../../ui/toast';
import { registerModule } from '../registry';
import { runOutput } from '../shared/tasks';
import { OutputModule } from './base';
import { PageView, type Layout, type LayoutPage } from './page';

type SlidePage = LayoutPage & { clip?: { start: number; len: number; audio: boolean }; seconds?: number };
type SlideLayout = Layout & { tracks?: string[]; gains?: { video: number; music: number } };

class Player {
  private readonly music = new Audio();
  private tracks: string[] = [];
  private track = 0;
  private gains = { video: 1, music: 1 };
  readonly root = el('<div class="fl-player" hidden><div class="fl-player-stage"></div><div class="fl-player-bar"><button class="cv-icon-btn" type="button" data-p="prev" aria-label="Previous"></button><button class="cv-icon-btn" type="button" data-p="toggle" aria-label="Pause"></button><button class="cv-icon-btn" type="button" data-p="next" aria-label="Next"></button><span class="fl-player-count"></span><button class="cv-icon-btn" type="button" data-p="close" aria-label="Exit"></button></div></div>');
  private readonly stage = this.root.firstElementChild as HTMLElement;
  private readonly a = new PageView();
  private readonly b = new PageView();
  private front: PageView = this.a;
  private lay: Layout | null = null;
  private i = 0;
  private timer = 0;
  private paused = false;
  private opts: { duration: number; fade: number; zoom: number; repeat: boolean; bg: string; stroke: number; strokeColor: string } = { duration: 4, fade: 1, zoom: 0, repeat: true, bg: '#000', stroke: 0, strokeColor: '#fff' };
  private readonly keyFn = (e: KeyboardEvent) => this.onKey(e);

  constructor() {
    this.stage.append(this.a.root, this.b.root);
    const bar = this.root.querySelector('.fl-player-bar') as HTMLElement;
    const set = (sel: string, ic: string) => { (bar.querySelector(`[data-p="${sel}"]`) as HTMLElement).innerHTML = icon(ic, 18); };
    set('prev', 'chevronLeft'); set('toggle', 'pause'); set('next', 'chevronRight'); set('close', 'close');
    bar.addEventListener('click', (e) => {
      const p = (e.target as HTMLElement).closest<HTMLElement>('[data-p]')?.dataset.p;
      if (p === 'prev') this.show(this.i - 1, true); else if (p === 'next') this.show(this.i + 1, true); else if (p === 'toggle') this.toggle(); else if (p === 'close') this.stop();
    });
    this.root.addEventListener('dblclick', () => this.stop());
    this.music.addEventListener('ended', () => {
      this.track += 1;
      if (this.track >= this.tracks.length) { if (!this.opts.repeat) return; this.track = 0; }
      this.startMusic();
    });
    document.getElementById('overlay-root')?.appendChild(this.root);
  }

  private startMusic(): void {
    const t = this.tracks[this.track];
    if (!t || this.gains.music <= 0) return;
    this.music.src = api.url(`/api/output/audio?path=${encodeURIComponent(t)}`);
    this.music.volume = Math.min(1, this.gains.music);
    void this.music.play().catch(() => undefined);
  }

  private clipFor(view: PageView, page: SlidePage | null): void {
    const cell = view.root.querySelector<HTMLElement>('.fl-pcell');
    let v = view.root.querySelector<HTMLVideoElement>('video.fl-pcell-video');
    const clip = page?.clip;
    const photo = page?.cells[0]?.photo;
    if (!clip || !cell || photo === null || photo === undefined) {
      if (v) { v.pause(); setClass(v, 'is-ready', false); }
      return;
    }
    if (!v) {
      const nv = el<HTMLVideoElement>('<video class="fl-pcell-video" playsinline preload="auto"></video>');
      nv.addEventListener('playing', () => setClass(nv, 'is-ready', true));
      v = nv;
    }
    if (v.parentElement !== cell) cell.appendChild(v);
    setClass(v, 'is-ready', false);
    const src = `${api.url(`/api/photos/${photo}/original`)}#t=${clip.start},${clip.start + clip.len}`;
    if (v.getAttribute('src') !== src) v.src = src;
    else v.currentTime = clip.start;
    v.volume = Math.min(1, this.gains.video);
    v.muted = this.gains.video <= 0 || !clip.audio;
    if (!this.paused) void v.play().catch(() => undefined);
  }

  private seconds(): number {
    const page = this.lay?.pages[this.i] as SlidePage | undefined;
    if (!page?.clip) return page?.seconds ?? this.opts.duration;
    const v = this.front.root.querySelector<HTMLVideoElement>('video.fl-pcell-video');
    return Math.max(0.2, page.clip.len - (v && v.currentTime > page.clip.start ? v.currentTime - page.clip.start : 0));
  }

  play(lay: Layout, s: Record<string, unknown>, start = 0): void {
    this.lay = lay;
    const sl = lay as SlideLayout;
    this.tracks = sl.tracks ?? [];
    this.gains = sl.gains ?? { video: 1, music: 1 };
    this.track = 0;
    this.opts = { duration: Number(s.duration ?? 4), fade: Number(s.fade ?? 1), zoom: Number(s.panZoom ?? 0) * 0.18, repeat: !!s.repeat, bg: String(s.background ?? '#000'), stroke: Number(s.stroke ?? 0), strokeColor: String(s.strokeColor ?? '#fff') };
    this.startMusic();
    setStyleVar(this.root, '--player-bg', this.opts.bg);
    setStyleVar(this.root, '--fade', `${this.opts.fade}s`);
    this.root.hidden = false;
    this.paused = false;
    document.addEventListener('keydown', this.keyFn, true);
    void this.root.requestFullscreen?.().catch(() => undefined);
    this.show(start, true);
  }

  private size(): number {
    const lay = this.lay as Layout;
    return Math.min(window.innerWidth, window.innerHeight * lay.page.w / lay.page.h);
  }

  private show(i: number, now: boolean): void {
    const lay = this.lay;
    if (!lay || !lay.pages.length) return;
    const n = lay.pages.length;
    if (i >= n && !this.opts.repeat && !now) { this.stop(); return; }
    this.i = ((i % n) + n) % n;
    const back = this.front === this.a ? this.b : this.a;
    back.render(lay, lay.pages[this.i], this.size(), { background: this.opts.bg, stroke: this.opts.stroke, strokeColor: this.opts.strokeColor });
    setClass(back.root, 'is-front', true);
    setClass(this.front.root, 'is-front', false);
    const old = this.front;
    window.setTimeout(() => { if (this.front !== old) this.clipFor(old, null); }, this.opts.fade * 1000);
    this.front = back;
    this.clipFor(back, lay.pages[this.i] as SlidePage);
    if (this.opts.zoom > 0) {
      const z = 1 + this.opts.zoom;
      const dx = (this.i % 2 ? -1 : 1) * this.opts.zoom * 30, dy = (this.i % 3 ? 1 : -1) * this.opts.zoom * 20;
      for (const img of Array.from(back.root.querySelectorAll<HTMLImageElement>('.fl-pcell img'))) {
        img.animate([{ transform: `${img.parentElement?.classList.contains('is-rot') ? 'rotate(90deg) ' : ''}scale(1) translate(0,0)` }, { transform: `${img.parentElement?.classList.contains('is-rot') ? 'rotate(90deg) ' : ''}scale(${z}) translate(${dx}px, ${dy}px)` }], { duration: (this.opts.duration + this.opts.fade) * 1000, easing: 'linear', fill: 'forwards' });
      }
    }
    setText(this.root.querySelector('.fl-player-count'), `${this.i + 1} / ${n}`);
    window.clearTimeout(this.timer);
    if (!this.paused) this.timer = window.setTimeout(() => this.show(this.i + 1, false), this.seconds() * 1000);
  }

  private toggle(): void {
    this.paused = !this.paused;
    (this.root.querySelector('[data-p="toggle"]') as HTMLElement).innerHTML = icon(this.paused ? 'play' : 'pause', 18);
    window.clearTimeout(this.timer);
    const v = this.front.root.querySelector<HTMLVideoElement>('video.fl-pcell-video.is-ready');
    if (this.paused) { this.music.pause(); v?.pause(); return; }
    if (this.tracks.length && this.gains.music > 0) void this.music.play().catch(() => undefined);
    if (v) void v.play().catch(() => undefined);
    this.timer = window.setTimeout(() => this.show(this.i + 1, false), this.seconds() * 1000);
  }

  private onKey(e: KeyboardEvent): void {
    e.stopPropagation();
    if (e.key === 'Escape') { e.preventDefault(); this.stop(); } else if (e.key === 'ArrowRight') this.show(this.i + 1, true); else if (e.key === 'ArrowLeft') this.show(this.i - 1, true); else if (e.key === ' ') { e.preventDefault(); this.toggle(); }
  }

  stop(): void {
    window.clearTimeout(this.timer);
    this.music.pause();
    this.clipFor(this.a, null);
    this.clipFor(this.b, null);
    this.root.hidden = true;
    document.removeEventListener('keydown', this.keyFn, true);
    if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined);
  }
}

class SlideshowModule extends OutputModule {
  readonly id = 'slideshow';
  readonly label = 'Slideshow';
  readonly icon = 'modSlideshow';
  readonly key = 'Alt+Mod+5';
  readonly order = 5;
  protected readonly optionsCmd = 'slideshow.options';
  protected readonly kind = 'slideshow';
  private lay: Layout | null = null;
  private slide = 0;
  private seq = 0;
  private player: Player | null = null;
  private readonly view = new PageView();
  private readonly frame = el('<div class="fl-out-frame fl-slide-frame"></div>');
  private readonly label2 = el('<span class="fl-tb-label fl-out-pages"></span>');
  private readonly prev = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" aria-label="Previous Slide">${icon('chevronLeft', 16)}</button>`);
  private readonly next = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" aria-label="Next Slide">${icon('chevronRight', 16)}</button>`);

  protected buildToolbar(bar: HTMLElement): void {
    const play = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" aria-label="Play (Enter)">${icon('play', 16)}</button>`);
    play.addEventListener('click', () => this.play());
    this.prev.addEventListener('click', () => this.go(this.slide - 1));
    this.next.addEventListener('click', () => this.go(this.slide + 1));
    bar.append(this.prev, play, this.next, this.label2);
  }

  protected buildStage(stage: HTMLElement): void {
    const root = el('<div class="fl-out-stage fl-slide-stage"></div>');
    this.frame.appendChild(this.view.root);
    root.appendChild(this.frame);
    stage.appendChild(root);
    new ResizeObserver(() => this.paint()).observe(root);
  }

  protected buildPanels(right: HTMLElement): void {
    this.formPanel(right, 'options', 'Options', [
      { path: 'fill', label: 'Zoom to fill frame', kind: 'check' },
      { path: 'margin', label: 'Margins', kind: 'range', min: 0, max: 0.25, step: 0.005 },
      { path: 'stroke', label: 'Stroke border', kind: 'range', min: 0, max: 12, step: 0.5, unit: ' pt' },
      { path: 'strokeColor', label: 'Stroke color', kind: 'color', show: () => Number(this.get('stroke')) > 0 },
      { path: 'shadow', label: 'Cast shadow', kind: 'check' },
    ]);
    this.formPanel(right, 'overlays', 'Overlays', [
      { path: 'identity.on', label: 'Identity plate', kind: 'check' },
      { path: 'identity.text', label: 'Text', kind: 'text', show: () => !!this.get('identity.on') },
      { path: 'identity.size', label: 'Size', kind: 'range', min: 8, max: 72, unit: ' pt', show: () => !!this.get('identity.on') },
      { path: 'identity.y', label: 'Position', kind: 'range', min: 0.02, max: 0.98, step: 0.01, show: () => !!this.get('identity.on') },
      { path: 'identity.color', label: 'Color', kind: 'color', show: () => !!this.get('identity.on') },
      { path: 'caption.on', label: 'Text overlay', kind: 'check' },
      { path: 'caption.field', label: 'Field', kind: 'select', options: [['title', 'Title'], ['caption', 'Caption'], ['titleCaption', 'Title and Caption'], ['fileName', 'Filename'], ['date', 'Date'], ['exposure', 'Exposure'], ['custom', 'Custom Text']], show: () => !!this.get('caption.on') },
      { path: 'caption.custom', label: 'Custom', kind: 'text', show: () => !!this.get('caption.on') && this.get('caption.field') === 'custom' },
      { path: 'caption.size', label: 'Size', kind: 'range', min: 6, max: 30, unit: ' pt', show: () => !!this.get('caption.on') },
      { path: 'caption.color', label: 'Color', kind: 'color', show: () => !!this.get('caption.on') },
    ]);
    this.formPanel(right, 'backdrop', 'Backdrop', [{ path: 'background', label: 'Color', kind: 'color' }]);
    this.formPanel(right, 'titles', 'Titles', [
      { path: 'intro.on', label: 'Intro screen', kind: 'check' },
      { path: 'intro.text', label: 'Intro text', kind: 'text', show: () => !!this.get('intro.on') },
      { path: 'ending.on', label: 'Ending screen', kind: 'check' },
      { path: 'ending.text', label: 'Ending text', kind: 'text', show: () => !!this.get('ending.on') },
    ]);
    const playback = this.formPanel(right, 'playback', 'Playback', [
      { path: 'duration', label: 'Slide length', kind: 'range', min: 1, max: 20, step: 0.5, unit: ' s' },
      { path: 'fade', label: 'Crossfade', kind: 'range', min: 0, max: 4, step: 0.1, unit: ' s' },
      { path: 'panZoom', label: 'Pan and zoom', kind: 'range', min: 0, max: 1, step: 0.05 },
      { path: 'random', label: 'Random order', kind: 'check' },
      { path: 'repeat', label: 'Repeat', kind: 'check' },
      { path: 'music.path', label: 'Music', kind: 'textarea', placeholder: 'One audio file per line, up to 10 tracks played in order' },
      { path: 'music.fit', label: 'Fit to music', kind: 'check', show: () => !!this.get('music.path') },
      { path: 'music.balance', label: 'Audio balance', kind: 'range', min: 0, max: 100, step: 1, unit: '% music' },
    ]);
    const addMusic = el<HTMLButtonElement>('<button class="cv-btn fl-btn-sm" type="button">Add Music from Folder...</button>');
    const row = el('<div class="fl-row fl-row-end"></div>');
    row.appendChild(addMusic);
    playback.body.appendChild(row);
    addMusic.addEventListener('click', () => void this.addMusic());
    this.formPanel(right, 'video', 'Video Export', [
      { path: '', label: 'Video export writes H.264 MP4 with your music and the sound of video clips, mixed by Audio balance.', kind: 'note', show: () => !!this.options?.ffmpeg },
      { path: '', label: 'Video export needs ffmpeg on this computer. PDF export works without it.', kind: 'note', show: () => !this.options?.ffmpeg },
      { path: 'video.size', label: 'Size', kind: 'seg', options: [['480p', '480p'], ['720p', '720p'], ['1080p', '1080p'], ['4k', '4K']] },
      { path: 'video.fps', label: 'Frame rate', kind: 'select', options: [['24', '24 fps'], ['25', '25 fps'], ['30', '30 fps'], ['60', '60 fps']] },
      { path: 'video.quality', label: 'Quality', kind: 'select', options: [['max', 'Maximum'], ['high', 'High'], ['medium', 'Medium'], ['low', 'Low']] },
    ], false);
  }

  protected buildFoots(left: HTMLElement, right: HTMLElement): void {
    const l = el('<div class="fl-foot-row"><button class="cv-btn" type="button" data-x="pdf">Export PDF...</button><button class="cv-btn" type="button" data-x="mp4">Export Video...</button></div>');
    l.addEventListener('click', (e) => { const b = (e.target as HTMLElement).closest<HTMLElement>('[data-x]'); if (b) void this.exportAs(b.dataset.x as string); });
    left.appendChild(l);
    this.ctx.commands.add({ id: 'library.impromptuSlideshow', label: 'Impromptu Slideshow', keys: ['Mod+Enter'], run: () => void this.impromptu(), enabled: () => library.ids.length > 0 });
    const r = el('<div class="fl-foot-row"><button class="cv-btn" type="button" data-x="preview">Preview</button><button class="cv-btn cv-btn-primary" type="button" data-x="play">Play</button></div>');
    r.addEventListener('click', (e) => { const b = (e.target as HTMLElement).closest<HTMLElement>('[data-x]'); if (b?.dataset.x === 'play') this.play(); else if (b) this.play(this.slide); });
    right.appendChild(r);
  }

  onKey(e: KeyboardEvent, combo: string): boolean {
    if (combo === 'Enter') { this.play(); return true; }
    if (combo === 'ArrowRight') { this.go(this.slide + 1); return true; }
    if (combo === 'ArrowLeft') { this.go(this.slide - 1); return true; }
    return e.defaultPrevented;
  }

  private async addMusic(): Promise<void> {
    const have = String(this.get('music.path') ?? '').split('\n').map((s) => s.trim()).filter(Boolean);
    const folder = await pickFolder('Add Music', 'Choose a folder; its audio files (MP3, M4A, AAC, WAV, FLAC, OGG, AIFF) are added in name order, up to ten tracks in all.', have.length ? folderOf(have[have.length - 1]) : '', 'Add Music');
    if (!folder) return;
    try {
      const r = await this.ctx.api.cmd<{ tracks: Array<{ path: string }> }>('slideshow.musicIn', { folder });
      if (!r.tracks.length) { toast('That folder has no audio files'); return; }
      const next = [...have, ...r.tracks.map((t) => t.path).filter((p) => !have.includes(p))].slice(0, 10);
      this.set('music.path', next.join('\n'));
      toast(`${next.length} music track${next.length === 1 ? '' : 's'}`);
    } catch (err) { this.ctx.fail(err); }
  }

  private async impromptu(): Promise<void> {
    await this.ensure();
    const ids = library.selected().length > 1 ? library.selected() : library.ids.slice();
    try {
      this.lay = await this.ctx.api.cmd<Layout>('slideshow.layout', { ids, settings: this.settings });
      this.play(0);
    } catch (err) { this.ctx.fail(err); }
  }

  private play(from = 0): void {
    if (!this.lay || !this.lay.pages.length) { toast('Add photos to the filmstrip to play a slideshow'); return; }
    this.player ??= new Player();
    this.player.play(this.lay, this.settings, from);
  }

  protected async refresh(): Promise<void> {
    const seq = ++this.seq;
    const ids = this.ids();
    const lay = await this.ctx.api.cmd<Layout>('slideshow.layout', { ids, settings: this.settings });
    if (seq !== this.seq) return;
    this.lay = lay;
    this.slide = Math.max(0, Math.min(this.slide, lay.pages.length - 1));
    this.paint();
  }

  private go(i: number): void {
    if (!this.lay) return;
    this.slide = Math.max(0, Math.min(this.lay.pages.length - 1, i));
    this.paint();
  }

  private paint(): void {
    const lay = this.lay;
    if (!lay) return;
    const stage = this.frame.parentElement as HTMLElement;
    const W = stage.clientWidth - 64, H = stage.clientHeight - 64;
    if (W <= 0 || H <= 0) return;
    const scale = Math.min(W / lay.page.w, H / lay.page.h);
    const page = lay.pages[this.slide];
    if (page) this.view.render(lay, page, lay.page.w * scale, { background: String(this.get('background') ?? '#000'), stroke: Number(this.get('stroke') ?? 0), strokeColor: String(this.get('strokeColor') ?? '#fff') });
    setClass(this.view.root, 'is-shadow', !!this.get('shadow') && !this.get('fill'));
    const n = lay.pages.length;
    setText(this.label2, n ? `Slide ${this.slide + 1} of ${n}` : 'No slides');
    setDisabled(this.prev, this.slide <= 0);
    setDisabled(this.next, this.slide >= n - 1);
    const secs = (lay.pages as SlidePage[]).reduce((t, p) => t + (p.seconds ?? Number(this.get('duration') ?? 4)), 0);
    setText(this.status, `${n} slides · ${Math.floor(secs / 60)}:${String(Math.round(secs % 60)).padStart(2, '0')}`);
  }

  private async exportAs(fmt: string): Promise<void> {
    const ids = this.ids();
    if (!ids.length) { toast('Add photos to the filmstrip first'); return; }
    if (fmt === 'mp4' && !this.options?.ffmpeg) { toast('Video export needs ffmpeg on this computer', 'error'); return; }
    await runOutput(this.ctx, 'slideshow.export', { ids, settings: this.settings, format: fmt, name: 'Slideshow' }, () => fmt === 'mp4' ? 'Exported the slideshow video' : 'Exported the slideshow PDF');
  }
}

registerModule(new SlideshowModule());
