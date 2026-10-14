import type { Ctx } from '../../app';
import { library, type Photo } from '../../state/library';
import { el, patchList, q, setClass, setHidden, setHtml, setText } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { previewUrl, thumbUrl } from '../../ui/thumbs';
import { Viewer } from '../../ui/viewer';

interface Face { box: [number, number, number, number]; sharpness: number | null; eyesOpen: number | null }
interface Score { sharpness: number; exposure: number; eyesOpen: number | null; faceSharpness: number | null; faces: number; quality: number; best: boolean; faceList: Face[] | null }
interface Groups { groups: Array<{ ids: number[]; best: number | null }>; total: number; analyzed: number; scores: Record<string, Score> }

const LOW = 35;
const WARM_AHEAD = 5;
const WARM_BEHIND = 2;
const FACE_TILE = 124;

export class CullView {
  readonly root: HTMLElement;
  readonly viewer = new Viewer('fl-cull-viewer');
  private readonly pos: HTMLElement;
  private readonly best: HTMLElement;
  private readonly scores: HTMLElement;
  private readonly tally: HTMLElement;
  private readonly analyze: HTMLButtonElement;
  private readonly faces: HTMLElement;
  private readonly facesNote: HTMLElement;
  private readonly strip: HTMLElement;
  private data: Groups | null = null;
  private order: number[] = [];
  private groupOf = new Map<number, number>();
  private readonly warm = new Map<string, HTMLImageElement>();
  private loadSeq = 0;
  private faceSeq = 0;
  visible = false;

  constructor(private readonly ctx: Ctx) {
    this.root = el(`<div class="fl-lib-view fl-lib-cull" hidden>
<div class="fl-cull-head"><span class="fl-cull-pos"></span><span class="fl-cull-best" hidden>${icon('starFill', 11)} Best of burst</span><span class="fl-cull-scores"></span><span class="fl-tb-spacer"></span><span class="fl-cull-tally"></span><button class="cv-btn fl-btn-sm" type="button" data-cull="analyze"></button></div>
<div class="fl-cull-main"><div class="fl-cull-faces" aria-label="Faces at full size"><div class="fl-cull-faces-note"></div></div></div>
<div class="fl-cull-strip" role="listbox" aria-label="Frames in this burst"></div>
<div class="fl-cull-keys"><kbd>P</kbd> pick <kbd>X</kbd> reject <kbd>U</kbd> unflag <kbd>1</kbd>-<kbd>5</kbd> rate <kbd>Shift+P</kbd> keep this frame, reject the rest of the burst <kbd>Left</kbd> <kbd>Right</kbd> frames <kbd>Up</kbd> <kbd>Down</kbd> bursts <kbd>Esc</kbd> grid</div>
</div>`);
    this.pos = q(this.root, '.fl-cull-pos');
    this.best = q(this.root, '.fl-cull-best');
    this.scores = q(this.root, '.fl-cull-scores');
    this.tally = q(this.root, '.fl-cull-tally');
    this.analyze = q<HTMLButtonElement>(this.root, '[data-cull="analyze"]');
    this.faces = q(this.root, '.fl-cull-faces');
    this.facesNote = q(this.root, '.fl-cull-faces-note');
    this.strip = q(this.root, '.fl-cull-strip');
    q(this.root, '.fl-cull-main').prepend(this.viewer.root);
    this.viewer.onClick = (e) => this.viewer.toggleZoom(e);
    this.analyze.addEventListener('click', () => void this.runAnalysis());
    this.strip.addEventListener('click', (e) => {
      const t = (e.target as HTMLElement).closest<HTMLElement>('.fl-cull-frame');
      if (t) this.go(Number(t.dataset.key));
    });
    library.listen('list', () => { if (this.visible) void this.load(); });
    library.listen('photos', () => { if (this.visible) this.syncMarks(); });
  }

  show(on: boolean): void {
    this.visible = on;
    if (on) void this.load();
  }

  private async load(): Promise<void> {
    const seq = ++this.loadSeq;
    const ids = library.ids.slice();
    try {
      const d = await this.ctx.api.cmd<Groups>('cull.groups', { ids });
      if (seq !== this.loadSeq) return;
      this.data = d;
    } catch (err) {
      if (seq !== this.loadSeq) return;
      this.data = { groups: ids.map((id) => ({ ids: [id], best: null })), total: ids.length, analyzed: 0, scores: {} };
      this.ctx.fail(err, 'Culling groups');
    }
    this.order = [];
    this.groupOf.clear();
    for (const [gi, g] of this.data.groups.entries()) for (const id of g.ids) { this.order.push(id); this.groupOf.set(id, gi); }
    this.render();
  }

  private async runAnalysis(): Promise<void> {
    const ids = library.ids.slice();
    if (!ids.length) return;
    const done = this.ctx.shell.busy(`Assessing ${ids.length} photos for culling`);
    this.analyze.disabled = true;
    try {
      await this.ctx.api.cmd('cull.analyze', { ids, wait: true });
      await this.load();
    } catch (err) { this.ctx.fail(err, 'Assisted Culling'); }
    finally { done(); this.analyze.disabled = false; }
  }

  render(): void {
    if (!this.visible) return;
    if (!this.order.length) {
      void this.viewer.show(null);
      setText(this.pos, 'No photos in this source');
      this.syncMarks();
      return;
    }
    let id = library.active;
    if (id === null || !this.groupOf.has(id)) {
      id = this.order[0];
      library.setActive(id, false);
      return;
    }
    const p = library.photo(id) ?? null;
    void this.viewer.show(p);
    const d = this.data as Groups;
    const gi = this.groupOf.get(id) ?? 0;
    const g = d.groups[gi];
    const n = d.groups.length;
    setText(this.pos, g.ids.length > 1 ? `Burst ${gi + 1} of ${n} · frame ${g.ids.indexOf(id) + 1} of ${g.ids.length}` : `${gi + 1} of ${n}${d.analyzed ? '' : ' · not analyzed yet'}`);
    setHidden(this.best, !(g.ids.length > 1 && g.best === id));
    const s = d.scores[String(id)];
    const chip = (label: string, v: number | null | undefined) => v === null || v === undefined ? '' : `<span class="fl-cull-chip${v < LOW ? ' is-low' : ''}">${label} <b>${Math.round(v)}</b></span>`;
    const html = s ? chip('Sharpness', s.sharpness) + chip('Exposure', s.exposure) + chip('Eyes open', s.eyesOpen) + (s.faces ? `<span class="fl-cull-chip">${s.faces} ${s.faces === 1 ? 'face' : 'faces'}</span>` : '') : '<span class="fl-cull-chip">No scores; Analyze to score sharpness, exposure and eyes</span>';
    setHtml(this.scores, html, html);
    setText(this.analyze, d.analyzed < d.total ? `Analyze ${d.total - d.analyzed} ${d.total - d.analyzed === 1 ? 'Photo' : 'Photos'}` : 'Analyze Again');
    patchList(this.strip, g.ids, {
      key: (fid) => String(fid),
      create: (fid) => el(`<button class="fl-cull-frame" type="button" role="option" data-key="${fid}"><img alt="" draggable="false"><span class="fl-cull-mark"></span><span class="fl-cull-star">${icon('starFill', 10)}</span></button>`),
      update: () => undefined,
    });
    this.syncMarks();
    this.syncFaces(p, s?.faceList ?? []);
    this.warmAround(id);
  }

  private syncMarks(): void {
    const d = this.data;
    let picks = 0, rejects = 0;
    for (const id of library.ids) { const f = library.photo(id)?.f ?? 0; if (f > 0) picks++; else if (f < 0) rejects++; }
    setText(this.tally, `${picks} picked · ${rejects} rejected · ${library.ids.length - picks - rejects} left`);
    if (!d) return;
    for (const node of Array.from(this.strip.children) as HTMLElement[]) {
      const fid = Number(node.dataset.key);
      const p = library.photo(fid);
      const img = q<HTMLImageElement>(node, 'img');
      if (p) { const u = thumbUrl(p); if (img.dataset.src !== u) { img.dataset.src = u; img.src = u; } }
      setClass(node, 'is-active', fid === library.active);
      setClass(node, 'is-pick', (p?.f ?? 0) > 0);
      setClass(node, 'is-reject', (p?.f ?? 0) < 0);
      setClass(node, 'is-best', d.groups[this.groupOf.get(fid) ?? 0]?.best === fid && (d.groups[this.groupOf.get(fid) ?? 0]?.ids.length ?? 0) > 1);
      node.setAttribute('aria-selected', String(fid === library.active));
    }
  }

  private syncFaces(p: Photo | null, list: Face[]): void {
    const seq = ++this.faceSeq;
    setText(this.facesNote, !p ? '' : list.length ? '' : (this.data?.scores[String(p.id)] ? 'No faces found' : 'Faces appear here after Analyze, when the faces model is installed'));
    setHidden(this.facesNote, !!list.length);
    const url = p ? previewUrl(p) : '';
    const tiles = list.map((f, i) => ({ f, key: `${i}` }));
    const caption = (node: HTMLElement, f: Face) => {
      setText(q(node, '.fl-cull-face-cap'), `${f.eyesOpen !== null ? `Eyes ${Math.round(f.eyesOpen)}` : 'Eyes ?'} · Sharp ${f.sharpness !== null ? Math.round(f.sharpness) : '?'}`);
      setClass(node, 'is-low', (f.eyesOpen !== null && f.eyesOpen < LOW) || (f.sharpness !== null && f.sharpness < LOW));
    };
    patchList(this.faces, tiles, {
      key: (t) => t.key,
      create: (t) => { const n = el(`<div class="fl-cull-face"><div class="fl-cull-face-img"></div><div class="fl-cull-face-cap"></div></div>`); caption(n, t.f); return n; },
      update: (node, t) => caption(node, t.f),
    });
    if (!url || !list.length) return;
    const img = this.warmImage(url);
    const place = () => {
      if (seq !== this.faceSeq || !img.naturalWidth) return;
      const W = img.naturalWidth, H = img.naturalHeight;
      for (const [i, node] of (Array.from(this.faces.querySelectorAll<HTMLElement>('.fl-cull-face'))).entries()) {
        const f = tiles[i]?.f;
        if (!f) continue;
        const [x0, y0, x1, y1] = f.box;
        const side = Math.max((x1 - x0) * W, (y1 - y0) * H) * 1.6;
        const k = FACE_TILE / Math.max(1, side);
        const cx = (x0 + x1) / 2 * W, cy = (y0 + y1) / 2 * H;
        const box = q(node, '.fl-cull-face-img');
        const style = `url("${url}") ${Math.round(-(cx - side / 2) * k)}px ${Math.round(-(cy - side / 2) * k)}px / ${Math.round(W * k)}px ${Math.round(H * k)}px no-repeat`;
        if (box.dataset.bg !== style) { box.dataset.bg = style; box.style.background = style; }
      }
    };
    if (img.complete && img.naturalWidth) place(); else void img.decode().then(place, () => undefined);
  }

  private warmImage(url: string): HTMLImageElement {
    let img = this.warm.get(url);
    if (!img) {
      img = new Image();
      img.decoding = 'async';
      img.src = url;
      this.warm.set(url, img);
    }
    return img;
  }

  private warmAround(id: number): void {
    const i = this.order.indexOf(id);
    const want = new Set<string>();
    for (let j = i - WARM_BEHIND; j <= i + WARM_AHEAD; j++) {
      const p = library.photo(this.order[j]);
      if (p) want.add(previewUrl(p));
    }
    for (const u of want) void this.warmImage(u).decode().catch(() => undefined);
    for (const u of Array.from(this.warm.keys())) if (!want.has(u)) this.warm.delete(u);
  }

  private go(id: number | undefined): void {
    if (id === undefined || id === library.active) return;
    library.setActive(id, false);
  }

  private step(d: number): void {
    const i = this.order.indexOf(library.active ?? -1);
    this.go(this.order[Math.max(0, Math.min(this.order.length - 1, i + d))]);
  }

  private burst(d: number): void {
    const data = this.data;
    if (!data) return;
    const gi = this.groupOf.get(library.active ?? -1) ?? 0;
    const g = data.groups[Math.max(0, Math.min(data.groups.length - 1, gi + d))];
    if (g) this.go(g.best ?? g.ids[0]);
  }

  private async flag(flag: 'pick' | 'reject' | 'none', advance: boolean): Promise<void> {
    const id = library.active;
    if (id === null) return;
    try {
      await this.ctx.api.cmd('photo.flag', { ids: [id], flag });
      if (advance && library.active === id) this.step(1);
    } catch (err) { this.ctx.fail(err); }
  }

  private async rate(n: number): Promise<void> {
    const id = library.active;
    if (id === null) return;
    try {
      await this.ctx.api.cmd('photo.rate', { ids: [id], rating: n });
      if (library.active === id) this.step(1);
    } catch (err) { this.ctx.fail(err); }
  }

  private async keepOnly(): Promise<void> {
    const id = library.active;
    const data = this.data;
    if (id === null || !data) return;
    const g = data.groups[this.groupOf.get(id) ?? 0];
    const others = g.ids.filter((x) => x !== id);
    try {
      await this.ctx.api.cmd('photo.flag', { ids: [id], flag: 'pick' });
      if (others.length) await this.ctx.api.cmd('photo.flag', { ids: others, flag: 'reject' });
      this.burst(1);
    } catch (err) { this.ctx.fail(err); }
  }

  key(combo: string): boolean {
    if (!this.visible) return false;
    switch (combo) {
      case 'P': void this.flag('pick', true); return true;
      case 'X': void this.flag('reject', true); return true;
      case 'U': void this.flag('none', false); return true;
      case 'Shift+P': void this.keepOnly(); return true;
      case 'Right': this.step(1); return true;
      case 'Left': this.step(-1); return true;
      case 'Down': this.burst(1); return true;
      case 'Up': this.burst(-1); return true;
      case '0': case '1': case '2': case '3': case '4': case '5': void this.rate(Number(combo)); return true;
      default: return false;
    }
  }
}
