import { library, type Filter, type Photo, type Sort, type Source } from './state/library';
import { el, q, setClass, setHidden, setText } from './ui/dom';
import { ThumbGrid } from './ui/grid';
import { icon } from './ui/icons';
import { previewUrl } from './ui/thumbs';
import { Viewer } from './ui/viewer';

export type SecondMode = 'grid' | 'loupe' | 'compare' | 'survey' | 'slideshow';
export type LoupeMode = 'normal' | 'live' | 'locked';
export const SECOND_MODES: Array<[SecondMode, string]> = [['grid', 'Grid'], ['loupe', 'Loupe'], ['compare', 'Compare'], ['survey', 'Survey'], ['slideshow', 'Slideshow']];

export interface SecondMsg {
  kind?: 'state' | 'hover' | 'mode' | 'select';
  hello?: boolean;
  photo?: Photo | null;
  photos?: Record<string, Photo>;
  sel?: number[];
  active?: number | null;
  id?: number | null;
  mode?: SecondMode;
  view?: { source: Source; filter: Filter; sort: Sort };
}

const SLIDE_MS = 4000;

export class SecondModes {
  readonly stage = el('<div class="fl-second-stage"></div>');
  private readonly grid = new ThumbGrid({ axis: 'y', cls: 'fl-lg', names: true, onOpen: () => this.setMode('loupe') });
  private readonly loupe = new Viewer('fl-second-view');
  private readonly compare = el('<div class="fl-second-compare" hidden><div class="fl-compare-pane"><span class="fl-compare-tag">Select</span></div><div class="fl-compare-pane"><span class="fl-compare-tag">Candidate</span></div></div>');
  private readonly cmpA = new Viewer();
  private readonly cmpB = new Viewer();
  private readonly survey = el('<div class="fl-lib-survey fl-second-survey" hidden></div>');
  private readonly show = el(`<div class="fl-second-show" hidden><div class="fl-second-show-bar"><button class="cv-icon-btn" type="button" data-s="prev" aria-label="Previous">${icon('chevronLeft', 16)}</button><button class="cv-icon-btn" type="button" data-s="play" aria-label="Play or Pause"><span data-on>${icon('pause', 16)}</span><span data-off hidden>${icon('play', 16)}</span></button><button class="cv-icon-btn" type="button" data-s="next" aria-label="Next">${icon('chevronRight', 16)}</button><span class="fl-second-count"></span></div></div>`);
  private readonly slide = new Viewer('fl-second-slide');
  mode: SecondMode = 'loupe';
  loupeMode: LoupeMode = 'normal';
  private hover: number | null = null;
  private sel: number[] = [];
  private act: number | null = null;
  private viewKey = '';
  private quiet = 0;
  private gesture = 0;
  private slideIdx = 0;
  private playing = true;
  private timer = 0;
  onShown: ((p: Photo | null, mode: SecondMode) => void) | null = null;

  constructor(private readonly ch: BroadcastChannel) {
    q(this.compare, '.fl-compare-pane:first-child').prepend(this.cmpA.root);
    q(this.compare, '.fl-compare-pane:last-child').prepend(this.cmpB.root);
    this.show.prepend(this.slide.root);
    this.slide.setInfo(0);
    setHidden(this.grid.root, true);
    this.stage.append(this.grid.root, this.loupe.root, this.compare, this.survey, this.show);
    for (const t of ['pointerdown', 'keydown']) this.stage.addEventListener(t, () => { this.gesture = performance.now(); }, true);
    library.listen('selection', () => {
      if (!this.quiet && performance.now() - this.gesture < 800) this.ch.postMessage({ kind: 'select', sel: library.selected(), active: library.active } satisfies SecondMsg);
      this.paint();
    });
    library.listen('photos', (ids) => { if (ids.some((id) => id === this.act || id === this.hover || this.sel.includes(id))) this.paint(); });
    this.loupe.onClick = (e) => this.loupe.toggleZoom(e);
    this.survey.addEventListener('click', (e) => {
      const tile = (e.target as HTMLElement).closest<HTMLElement>('.fl-survey-tile');
      if (tile?.dataset.id) library.setActive(Number(tile.dataset.id));
    });
    this.show.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-s]');
      if (b) this.slideCmd(b.dataset.s as string);
    });
    window.addEventListener('keydown', (e) => this.key(e));
  }

  setMode(m: SecondMode): void {
    if (this.mode === m) return;
    this.mode = m;
    setHidden(this.grid.root, m !== 'grid');
    setHidden(this.loupe.root, m !== 'loupe');
    setHidden(this.compare, m !== 'compare');
    setHidden(this.survey, m !== 'survey');
    setHidden(this.show, m !== 'slideshow');
    this.grid.show(m === 'grid');
    if (m === 'slideshow') { this.slideIdx = Math.max(0, this.deck().indexOf(this.act ?? -1)); this.playing = true; }
    this.paint();
  }

  setLoupe(m: LoupeMode): void { this.loupeMode = m; this.paint(); }

  refresh(id: number): void {
    for (const v of [this.loupe, this.cmpA, this.cmpB, this.slide]) if (v.photo?.id === id) v.refresh();
    if (this.mode === 'survey' && library.selection.has(id)) this.paintSurvey();
  }
  setSize(px: number): void { this.grid.setSize(px); }

  receive(d: SecondMsg): void {
    if (d.kind === 'mode' && d.mode) { this.setMode(d.mode); return; }
    for (const [k, p] of Object.entries(d.photos ?? {})) library.photos.set(Number(k), p);
    if (d.photo) library.photos.set(d.photo.id, d.photo);
    if (d.kind === 'hover') { this.hover = d.id ?? null; if (this.mode === 'loupe' && this.loupeMode === 'live') this.paint(); return; }
    if (d.kind !== 'state') return;
    this.sel = d.sel ?? [];
    this.act = d.active ?? null;
    const key = d.view ? JSON.stringify(d.view) : this.viewKey;
    if (d.view && key !== this.viewKey) {
      this.viewKey = key;
      library.source = d.view.source;
      library.filter = d.view.filter;
      library.sort = d.view.sort;
      this.quiet += 1;
      void library.refresh().catch(() => undefined).finally(() => { this.quiet -= 1; this.applySel(); });
      return;
    }
    this.applySel();
  }

  private applySel(): void {
    this.quiet += 1;
    library.selection.clear();
    for (const id of this.sel) library.selection.add(id);
    library.active = this.act;
    library.anchor = this.act;
    library.emitSelection();
    this.quiet -= 1;
  }

  private deck(): number[] {
    const sel = library.ids.filter((id) => library.selection.has(id));
    return sel.length > 1 ? sel : library.ids;
  }

  private paint(): void {
    if (this.mode === 'loupe') {
      const want = this.loupeMode === 'live' ? this.hover ?? this.act : this.act;
      if (this.loupeMode === 'locked' && this.loupe.photo) { this.onShown?.(this.loupe.photo, 'loupe'); return; }
      const p = library.photo(want) ?? null;
      void this.loupe.show(p);
      this.onShown?.(p, 'loupe');
    } else if (this.mode === 'compare') {
      const b = this.sel.find((id) => id !== this.act) ?? null;
      void this.cmpA.show(library.photo(this.act) ?? null);
      void this.cmpB.show(library.photo(b) ?? null);
      this.onShown?.(library.photo(this.act) ?? null, 'compare');
    } else if (this.mode === 'survey') {
      this.paintSurvey();
    } else if (this.mode === 'slideshow') {
      this.paintSlide();
    } else {
      this.onShown?.(library.photo(this.act) ?? null, 'grid');
    }
  }

  private paintSurvey(): void {
    const ids = library.selected().slice(0, 24);
    this.survey.style.setProperty('--cols', String(Math.ceil(Math.sqrt(ids.length * 1.5)) || 1));
    const keep = new Map<string, HTMLElement>();
    for (const c of Array.from(this.survey.children) as HTMLElement[]) keep.set(c.dataset.id ?? '', c);
    const next: HTMLElement[] = [];
    for (const id of ids) {
      const p = library.photo(id);
      if (!p) continue;
      const tile = keep.get(String(id)) ?? el(`<div class="fl-survey-tile" data-id="${id}"><img alt="" draggable="false"></div>`);
      const img = q<HTMLImageElement>(tile, 'img');
      const url = previewUrl(p);
      if (img.dataset.src !== url) {
        img.dataset.src = url;
        const pre = new Image();
        pre.src = url;
        void pre.decode().then(() => { if (img.dataset.src === url) img.src = url; }, () => undefined);
      }
      setClass(tile, 'is-active', id === library.active);
      next.push(tile);
    }
    const same = next.length === this.survey.children.length && next.every((t, i) => this.survey.children[i] === t);
    if (!same) this.survey.replaceChildren(...next);
    this.onShown?.(library.photo(library.active) ?? null, 'survey');
  }

  private paintSlide(): void {
    const deck = this.deck();
    window.clearTimeout(this.timer);
    if (!deck.length) { void this.slide.show(null); this.onShown?.(null, 'slideshow'); return; }
    this.slideIdx = ((this.slideIdx % deck.length) + deck.length) % deck.length;
    const p = library.photo(deck[this.slideIdx]) ?? null;
    void this.slide.show(p);
    const nxt = library.photo(deck[(this.slideIdx + 1) % deck.length]);
    if (nxt) { const pre = new Image(); pre.src = previewUrl(nxt); }
    setText(q(this.show, '.fl-second-count'), `${this.slideIdx + 1} / ${deck.length}`);
    setHidden(q(this.show, '[data-on]'), !this.playing);
    setHidden(q(this.show, '[data-off]'), this.playing);
    this.onShown?.(p, 'slideshow');
    if (this.playing && deck.length > 1) this.timer = window.setTimeout(() => { this.slideIdx += 1; this.paintSlide(); }, SLIDE_MS);
  }

  private slideCmd(c: string): void {
    if (c === 'play') this.playing = !this.playing;
    else this.slideIdx += c === 'next' ? 1 : -1;
    this.paintSlide();
  }

  private key(e: KeyboardEvent): void {
    if (e.metaKey || e.ctrlKey || e.altKey || (e.target as HTMLElement).closest('input, select, textarea')) return;
    const k = e.key;
    const modes: Record<string, SecondMode> = { g: 'grid', e: 'loupe', c: 'compare', n: 'survey', s: 'slideshow' };
    if (modes[k.toLowerCase()] && !e.shiftKey) { this.setMode(modes[k.toLowerCase()]); e.preventDefault(); return; }
    if (this.mode === 'slideshow') {
      if (k === ' ') this.slideCmd('play');
      else if (k === 'ArrowRight') this.slideCmd('next');
      else if (k === 'ArrowLeft') this.slideCmd('prev');
      else if (k === 'Escape') this.setMode('loupe');
      else return;
      e.preventDefault();
      return;
    }
    if (k === 'ArrowRight' || k === 'ArrowLeft') { this.gesture = performance.now(); library.step(k === 'ArrowRight' ? 1 : -1, e.shiftKey); e.preventDefault(); }
  }
}
