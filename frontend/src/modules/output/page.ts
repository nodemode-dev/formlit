import { api } from '../../io/api';
import { library } from '../../state/library';
import { el, patchList, setClass, setHidden, setStyleVar, setText } from '../../ui/dom';
import { previewUrl, thumbUrl } from '../../ui/thumbs';

export interface Rect { x: number; y: number; w: number; h: number }
export interface Cell extends Rect { photo: number | null; rot?: boolean; img?: Rect | null }
export interface Overlay { x: number; y: number; size: number; text: string; align: string; color: string; wrap?: number; font?: string; bold?: boolean; italic?: boolean; rotate?: number }
export interface TextFrame extends Rect { text: string; title?: boolean }
export interface LayoutPage { cells: Cell[]; texts?: TextFrame[]; overlays?: Overlay[]; number: number; cover?: boolean; template?: string; w?: number; h?: number; spine?: [number, number] }
export interface Layout { page: { w: number; h: number }; pages: LayoutPage[]; settings: Record<string, unknown> }

export function photoSrc(id: number, small: boolean): string {
  const p = library.photo(id);
  if (p) return small ? thumbUrl(p) : previewUrl(p);
  return api.url(`/api/photos/${id}/${small ? 'thumb' : 'preview'}`);
}

const pct = (v: number) => `${(v * 100).toFixed(4)}%`;

export class PageView {
  readonly root = el('<div class="fl-page"><div class="fl-page-cells"></div><div class="fl-page-texts"></div><div class="fl-page-spine" hidden></div></div>');
  private readonly cells = this.root.children[0] as HTMLElement;
  private readonly texts = this.root.children[1] as HTMLElement;
  private readonly spine = this.root.children[2] as HTMLElement;
  onCell: ((index: number, e: MouseEvent) => void) | null = null;
  onDropIds: ((index: number, ids: number[]) => void) | null = null;
  index = -1;

  constructor() {
    this.cells.addEventListener('click', (e) => {
      const c = (e.target as HTMLElement).closest<HTMLElement>('.fl-pcell');
      if (c && this.onCell) this.onCell(Number(c.dataset.key), e);
    });
    this.cells.addEventListener('dragover', (e) => {
      const c = (e.target as HTMLElement).closest<HTMLElement>('.fl-pcell');
      if (!c || !this.onDropIds || !e.dataTransfer?.types.includes('application/x-formlit-ids')) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
      setClass(c, 'is-drop', true);
    });
    this.cells.addEventListener('dragleave', (e) => { const c = (e.target as HTMLElement).closest<HTMLElement>('.fl-pcell'); if (c) setClass(c, 'is-drop', false); });
    this.cells.addEventListener('drop', (e) => {
      const c = (e.target as HTMLElement).closest<HTMLElement>('.fl-pcell');
      if (!c || !this.onDropIds) return;
      e.preventDefault();
      setClass(c, 'is-drop', false);
      try { this.onDropIds(Number(c.dataset.key), JSON.parse(e.dataTransfer?.getData('application/x-formlit-ids') || '[]') as number[]); } catch { setClass(c, 'is-drop', false); }
    });
  }

  render(lay: Layout, page: LayoutPage, widthPx: number, opts: { background?: string; stroke?: number; strokeColor?: string; empty?: boolean; editable?: boolean } = {}): void {
    const pw = page.w ?? lay.page.w, ph = page.h ?? lay.page.h;
    const pp = widthPx / pw;
    setStyleVar(this.root, '--pw', `${Math.round(widthPx)}px`);
    setStyleVar(this.root, '--pa', `${pw} / ${ph}`);
    setStyleVar(this.root, '--pp', pp.toFixed(4));
    setStyleVar(this.root, '--page-bg', opts.background ?? '#ffffff');
    const small = widthPx < 360;
    const stroke = opts.stroke ? Math.max(1, (opts.stroke / 72) * pp) : 0;
    setStyleVar(this.root, '--cell-stroke', stroke ? `${stroke.toFixed(2)}px solid ${opts.strokeColor ?? '#000'}` : '0');
    const items = page.cells.map((c, i) => ({ c, i }));
    patchList(this.cells, items, {
      key: (it) => String(it.i),
      create: () => el('<div class="fl-pcell"><img alt="" decoding="async" draggable="false"></div>'),
      update: () => undefined,
    });
    for (const [i, n] of Array.from(this.cells.children).entries()) this.cell(n as HTMLElement, page.cells[i], pw, ph, small, opts);
    const texts = [...(page.overlays ?? [])];
    patchList(this.texts, texts.map((t, i) => ({ t, i })), {
      key: (it) => `${it.i}`,
      create: () => el('<div class="fl-ptext"></div>'),
      update: () => undefined,
    });
    for (const [i, n] of Array.from(this.texts.children).entries()) {
      const t = texts[i];
      if (!t) continue;
      setText(n, t.text);
      setStyleVar(n as HTMLElement, '--tx', pct(t.x / pw));
      setStyleVar(n as HTMLElement, '--ty', pct(t.y / ph));
      setStyleVar(n as HTMLElement, '--fs', `${(t.size / 72).toFixed(4)}`);
      setStyleVar(n as HTMLElement, '--tc', t.color);
      setStyleVar(n as HTMLElement, '--tw', t.wrap ? pct(t.wrap / pw) : 'auto');
      setClass(n, 'is-left', t.align === 'left' || (t.align !== 'center' && t.align !== 'right'));
      setClass(n, 'is-right', t.align === 'right');
      setClass(n, 'is-serif', t.font === 'serif');
      setClass(n, 'is-mono', t.font === 'mono');
      setClass(n, 'is-bold', !!t.bold);
      setClass(n, 'is-italic', !!t.italic);
      setClass(n, 'is-spine', !!t.rotate);
    }
    setHidden(this.spine, !page.spine);
    if (page.spine) {
      setStyleVar(this.spine, '--sx', pct(page.spine[0] / pw));
      setStyleVar(this.spine, '--sw', pct(page.spine[1] / pw));
    }
  }

  private cell(n: HTMLElement, c: Cell, pw: number, ph: number, small: boolean, opts: { empty?: boolean; editable?: boolean }): void {
    setStyleVar(n, '--cx', pct(c.x / pw));
    setStyleVar(n, '--cy', pct(c.y / ph));
    setStyleVar(n, '--cw', pct(c.w / pw));
    setStyleVar(n, '--ch', pct(c.h / ph));
    setClass(n, 'is-empty', c.photo === null || c.photo === undefined);
    setClass(n, 'is-editable', !!opts.editable);
    const img = n.firstElementChild as HTMLImageElement;
    if (c.photo === null || c.photo === undefined || !c.img) {
      if (img.getAttribute('src')) img.removeAttribute('src');
      return;
    }
    const r = c.img;
    const rot = !!c.rot;
    const bw = rot ? r.h : r.w, bh = rot ? r.w : r.h;
    setStyleVar(n, '--ix', pct((r.x + r.w / 2 - bw / 2 - c.x) / c.w));
    setStyleVar(n, '--iy', pct((r.y + r.h / 2 - bh / 2 - c.y) / c.h));
    setStyleVar(n, '--iw', pct(bw / c.w));
    setStyleVar(n, '--ih', pct(bh / c.h));
    setClass(n, 'is-rot', rot);
    const src = photoSrc(c.photo, small);
    if (img.getAttribute('src') !== src) img.src = src;
  }
}
