import { api } from '../io/api';
import { catalog } from '../state/catalog';
import { library, type Photo } from '../state/library';
import { el, setHidden, setStyleVar } from './dom';
import { bump, ThumbCell } from './thumbs';

export interface GridOptions {
  axis: 'y' | 'x';
  cls: string;
  names: boolean;
  compact?: boolean;
  onOpen?: (id: number) => void;
  onContext?: (id: number, e: MouseEvent) => void;
  paint?: (id: number) => boolean;
}

const isMod = (e: MouseEvent | KeyboardEvent): boolean => (/Mac|iPhone|iPad/.test(navigator.platform) ? e.metaKey : e.ctrlKey);

export class ThumbGrid {
  readonly root: HTMLElement;
  readonly track: HTMLElement;
  private readonly live = new Map<number, ThumbCell>();
  private readonly free: ThumbCell[] = [];
  private size = 160;
  private gap = 8;
  private cols = 1;
  private viewW = 0;
  private viewH = 0;
  private raf = 0;
  private visible = false;
  private readonly marker: HTMLElement;

  constructor(private readonly opts: GridOptions) {
    this.root = el(`<div class="fl-grid fl-grid-${opts.axis} ${opts.cls}" tabindex="-1" role="grid" aria-label="Photos"><div class="fl-grid-track"></div></div>`);
    this.track = this.root.firstElementChild as HTMLElement;
    this.root.addEventListener('scroll', () => this.schedule(), { passive: true });
    new ResizeObserver(() => this.measure()).observe(this.root);
    this.root.addEventListener('pointerdown', (e) => this.pointer(e));
    this.root.addEventListener('dblclick', (e) => {
      const id = this.idAt(e.target);
      if (id !== null) this.opts.onOpen?.(id);
    });
    this.root.addEventListener('contextmenu', (e) => {
      const id = this.idAt(e.target);
      if (id === null || !this.opts.onContext) return;
      e.preventDefault();
      if (!library.selection.has(id)) library.select(id, 'only');
      this.opts.onContext(id, e);
    });
    this.root.addEventListener('dragstart', (e) => {
      const id = this.idAt(e.target);
      if (id === null || !e.dataTransfer) return;
      if (!library.selection.has(id)) library.select(id, 'only');
      e.dataTransfer.setData('application/x-formlit-ids', JSON.stringify(library.selected()));
      e.dataTransfer.effectAllowed = 'copyMove';
    });
    this.marker = el('<div class="fl-grid-drop" hidden></div>');
    this.track.appendChild(this.marker);
    this.root.addEventListener('dragover', (e) => {
      if (!this.canReorder() || !e.dataTransfer?.types.includes('application/x-formlit-ids')) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      this.showMarker(this.dropIndex(e));
    });
    this.root.addEventListener('dragleave', (e) => { if (!this.root.contains(e.relatedTarget as Node | null)) setHidden(this.marker, true); });
    this.root.addEventListener('dragend', () => setHidden(this.marker, true));
    this.root.addEventListener('drop', (e) => {
      setHidden(this.marker, true);
      const raw = e.dataTransfer?.getData('application/x-formlit-ids');
      if (!raw || !this.canReorder()) return;
      e.preventDefault();
      const moving = (JSON.parse(raw) as number[]).filter((id) => library.ids.includes(id));
      const at = this.dropIndex(e);
      const order = [...library.ids.slice(0, at).filter((id) => !moving.includes(id)), ...moving, ...library.ids.slice(at).filter((id) => !moving.includes(id))];
      const src = library.source as { id?: number };
      const desc = library.sort.by === 'userOrder' && library.sort.desc;
      void api.cmd('collection.reorder', { id: src.id, ids: desc ? order.slice().reverse() : order }).then(() => {
        if (library.sort.by !== 'userOrder') library.setSort({ by: 'userOrder', desc: false });
      }, () => undefined);
    });
    library.listen('list', () => this.layout());
    library.listen('selection', () => this.syncState());
    library.listen('photos', (ids) => this.rebind(ids));
    library.listen('render', (id, size) => {
      if (size !== 't') return;
      bump(id, 't');
      this.rebind([id]);
    });
  }

  setSize(px: number): void {
    const s = Math.round(Math.max(64, Math.min(480, px)));
    if (s === this.size) return;
    this.size = s;
    this.layout();
  }

  get cellSize(): number { return this.size; }
  get columns(): number { return this.cols; }

  show(on: boolean): void {
    this.visible = on;
    if (on) { this.measure(); this.reveal(library.active); }
  }

  private measure(): void {
    const w = this.root.clientWidth;
    const h = this.root.clientHeight;
    if (w === this.viewW && h === this.viewH) return;
    this.viewW = w;
    this.viewH = h;
    this.layout();
  }

  private extent(): number { return this.opts.axis === 'y' ? this.size : this.cellLong(); }

  private cellLong(): number { return Math.max(40, this.viewH - 14); }

  layout(): void {
    if (this.opts.axis === 'y') {
      const inner = Math.max(1, this.viewW - this.gap);
      this.cols = Math.max(1, Math.floor(inner / (this.size + this.gap)));
      const rows = Math.ceil(library.ids.length / this.cols);
      setStyleVar(this.track, 'height', `${rows * (this.size + this.gap) + this.gap}px`);
      setStyleVar(this.root, '--fl-cell', `${this.size}px`);
    } else {
      this.cols = 1;
      const span = library.ids.length * (this.cellLong() + this.gap) + this.gap;
      setStyleVar(this.track, 'width', `${span}px`);
      setStyleVar(this.root, '--fl-cell', `${this.cellLong()}px`);
    }
    this.schedule();
  }

  private schedule(): void {
    if (this.raf) return;
    this.raf = requestAnimationFrame(() => { this.raf = 0; this.paint(); });
  }

  private range(): [number, number] {
    const n = library.ids.length;
    if (!n) return [0, -1];
    const step = this.extent() + this.gap;
    if (this.opts.axis === 'y') {
      const top = this.root.scrollTop;
      const r0 = Math.max(0, Math.floor(top / step) - 2);
      const r1 = Math.ceil((top + this.viewH) / step) + 2;
      return [r0 * this.cols, Math.min(n - 1, r1 * this.cols - 1)];
    }
    const left = this.root.scrollLeft;
    return [Math.max(0, Math.floor(left / step) - 4), Math.min(n - 1, Math.ceil((left + this.viewW) / step) + 4)];
  }

  private paint(): void {
    const [a, b] = this.range();
    const want = new Set<number>();
    for (let i = a; i <= b; i += 1) want.add(library.ids[i]);
    for (const [id, cell] of this.live) {
      if (!want.has(id)) {
        this.live.delete(id);
        cell.root.hidden = true;
        this.free.push(cell);
      }
    }
    const step = this.extent() + this.gap;
    for (let i = a; i <= b; i += 1) {
      const id = library.ids[i];
      const p = library.photos.get(id);
      if (!p) continue;
      let cell = this.live.get(id);
      if (!cell) {
        cell = this.free.pop() ?? this.make();
        cell.bind(p, this.opts.compact);
        this.live.set(id, cell);
        cell.root.hidden = false;
      }
      const x = this.opts.axis === 'y' ? this.gap + (i % this.cols) * step : this.gap + i * step;
      const y = this.opts.axis === 'y' ? this.gap + Math.floor(i / this.cols) * step : 0;
      const t = `translate(${x}px, ${y}px)`;
      if (cell.root.style.transform !== t) cell.root.style.transform = t;
      cell.setState(library.selection.has(id), library.active === id);
    }
  }

  private make(): ThumbCell {
    const c = new ThumbCell(this.opts.cls + '-cell', this.opts.names);
    c.root.draggable = true;
    this.track.appendChild(c.root);
    return c;
  }

  private syncState(): void {
    for (const [id, cell] of this.live) cell.setState(library.selection.has(id), library.active === id);
    if (this.visible) this.reveal(library.active);
  }

  private rebind(ids: number[]): void {
    for (const id of ids) {
      const cell = this.live.get(id);
      const p = library.photos.get(id);
      if (cell && p) cell.bind(p, this.opts.compact);
    }
  }

  reveal(id: number | null): void {
    if (id === null) return;
    const i = library.index(id);
    if (i < 0) return;
    const step = this.extent() + this.gap;
    if (this.opts.axis === 'y') {
      const top = Math.floor(i / this.cols) * step;
      if (top < this.root.scrollTop) this.root.scrollTop = top;
      else if (top + step + this.gap > this.root.scrollTop + this.viewH) this.root.scrollTop = top + step + this.gap - this.viewH;
    } else {
      const left = i * step;
      if (left < this.root.scrollLeft) this.root.scrollLeft = Math.max(0, left - step);
      else if (left + step + this.gap > this.root.scrollLeft + this.viewW) this.root.scrollLeft = left + 2 * step - this.viewW;
    }
    this.schedule();
  }

  idAt(target: EventTarget | null): number | null {
    const c = (target as HTMLElement | null)?.closest?.<HTMLElement>('.fl-cell');
    return c?.dataset.id ? Number(c.dataset.id) : null;
  }

  private pointer(e: PointerEvent): void {
    if (e.button !== 0) return;
    const id = this.idAt(e.target);
    this.root.focus({ preventScroll: true });
    if (id === null) return;
    if (this.opts.paint?.(id)) return;
    if (e.shiftKey) library.select(id, 'range');
    else if (isMod(e)) library.select(id, 'toggle');
    else if (!library.selection.has(id) || library.selection.size <= 1) library.select(id, 'only');
    else library.setActive(id);
  }

  photoAt(i: number): Photo | undefined { return library.photos.get(library.ids[i]); }

  private canReorder(): boolean {
    const src = library.source as { kind: string; id?: number };
    return src.kind === 'collection' && catalog.tree.collections.some((c) => c.id === src.id && c.kind === 'collection');
  }

  private dropIndex(e: DragEvent): number {
    const r = this.track.getBoundingClientRect();
    const step = this.extent() + this.gap;
    const n = library.ids.length;
    if (this.opts.axis === 'x') return Math.max(0, Math.min(n, Math.round((e.clientX - r.left - this.gap) / step)));
    const col = Math.max(0, Math.min(this.cols, Math.round((e.clientX - r.left - this.gap) / step)));
    const row = Math.max(0, Math.floor((e.clientY - r.top - this.gap / 2) / step));
    return Math.max(0, Math.min(n, row * this.cols + col));
  }

  private showMarker(at: number): void {
    const step = this.extent() + this.gap;
    let col = this.opts.axis === 'x' ? at : at % this.cols;
    let row = this.opts.axis === 'x' ? 0 : Math.floor(at / this.cols);
    if (this.opts.axis === 'y' && col === 0 && at > 0 && at === library.ids.length) { row -= 1; col = this.cols; }
    const x = this.gap + col * step - this.gap / 2 - 1;
    const y = this.opts.axis === 'x' ? 0 : this.gap + row * step;
    setStyleVar(this.marker, 'transform', `translate(${x}px, ${y}px)`);
    setStyleVar(this.marker, 'height', `${this.extent()}px`);
    setHidden(this.marker, false);
  }
}
