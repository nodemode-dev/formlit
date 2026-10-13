import { el, q, setClass, setHidden } from './dom';
import { icon } from './icons';

const KEY = 'formlit_panels';
const HIDDEN_KEY = 'formlit_panels_hidden';
const ORDER_KEY = 'formlit_panels_order';
const SOLO_KEY = 'formlit_panels_solo';

export type Side = 'left' | 'right';
export interface PanelState { open: Record<string, boolean>; hidden: string[]; order: Record<string, string[]>; solo: Record<Side, boolean> }

function read<T>(key: string, fallback: T): T {
  try { return (JSON.parse(localStorage.getItem(key) || 'null') as T | null) ?? fallback; } catch { return fallback; }
}

function write(key: string, value: unknown): void {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { return; }
}

function readState(): Record<string, boolean> { return read<Record<string, boolean>>(KEY, {}); }

function writeState(id: string, open: boolean): void { const s = readState(); s[id] = open; write(KEY, s); }

export const PANELS = new Map<string, Panel>();

export function sideOf(node: Element): Side | '' {
  return node.closest('.fl-left') ? 'left' : node.closest('.fl-right') ? 'right' : '';
}

export function orderKey(container: Element): string {
  return `${container.closest<HTMLElement>('[data-module]')?.dataset.module ?? ''}:${sideOf(container)}`;
}

export function isSolo(side: Side | ''): boolean { return !!side && !!read<Record<string, boolean>>(SOLO_KEY, {})[side]; }

export function setSolo(side: Side, on: boolean): void { write(SOLO_KEY, { ...read<Record<string, boolean>>(SOLO_KEY, {}), [side]: on }); }

export function isPanelHidden(id: string): boolean { return read<string[]>(HIDDEN_KEY, []).includes(id); }

export function setPanelVisible(id: string, on: boolean): void {
  const hidden = new Set(read<string[]>(HIDDEN_KEY, []));
  if (on) hidden.delete(id); else hidden.add(id);
  write(HIDDEN_KEY, [...hidden]);
  const p = PANELS.get(id);
  if (p) setHidden(p.root, !on);
}

function panelsIn(container: Element): HTMLElement[] {
  return Array.from(container.children).filter((n): n is HTMLElement => n instanceof HTMLElement && n.classList.contains('fl-panel'));
}

const natural = new Map<Element, string[]>();

export function restoreOrder(): void {
  for (const [c, ids] of natural) {
    const now = panelsIn(c);
    if (!now.length) continue;
    const sorted = [...now].sort((a, b) => ids.indexOf(a.dataset.panel ?? '') - ids.indexOf(b.dataset.panel ?? ''));
    if (sorted.every((p, i) => p === now[i])) continue;
    const anchor = now[now.length - 1].nextSibling;
    for (const p of sorted) c.insertBefore(p, anchor);
  }
}

export function arrange(container: Element): void {
  const seen = natural.get(container) ?? [];
  for (const p of panelsIn(container)) if (!seen.includes(p.dataset.panel ?? '')) seen.push(p.dataset.panel ?? '');
  natural.set(container, seen);
  const want = read<Record<string, string[]>>(ORDER_KEY, {})[orderKey(container)];
  if (!want?.length) return;
  const now = panelsIn(container);
  const rank = (p: HTMLElement) => { const i = want.indexOf(p.dataset.panel ?? ''); return i < 0 ? want.length + now.indexOf(p) : i; };
  const sorted = [...now].sort((a, b) => rank(a) - rank(b));
  if (sorted.every((p, i) => p === now[i])) return;
  const anchor = now[now.length - 1].nextSibling;
  for (const p of sorted) container.insertBefore(p, anchor);
}

function saveOrder(container: Element): void {
  write(ORDER_KEY, { ...read<Record<string, string[]>>(ORDER_KEY, {}), [orderKey(container)]: panelsIn(container).map((p) => p.dataset.panel ?? '') });
}

export function panelState(): PanelState {
  return { open: readState(), hidden: read<string[]>(HIDDEN_KEY, []), order: read<Record<string, string[]>>(ORDER_KEY, {}), solo: { left: isSolo('left'), right: isSolo('right') } };
}

export function applyPanelState(s: Partial<PanelState>): void {
  if (s.open) write(KEY, s.open);
  if (s.hidden) write(HIDDEN_KEY, s.hidden);
  if (s.order) write(ORDER_KEY, s.order);
  if (s.solo) write(SOLO_KEY, s.solo);
  const hidden = new Set(read<string[]>(HIDDEN_KEY, []));
  const open = readState();
  const parents = new Set<Element>();
  for (const [id, p] of PANELS) {
    setHidden(p.root, hidden.has(id));
    if (id in open) p.setOpen(open[id], false);
    if (p.root.parentElement) parents.add(p.root.parentElement);
  }
  if (s.order && !Object.keys(s.order).length) restoreOrder();
  for (const c of parents) arrange(c);
}

export interface PanelOptions {
  open?: boolean;
  toggle?: { on: () => boolean; set: (on: boolean) => void; title: string };
  tools?: HTMLElement[];
}

export class Panel {
  readonly root: HTMLElement;
  readonly body: HTMLElement;
  readonly head: HTMLButtonElement;
  readonly tools: HTMLElement;
  private readonly sw: HTMLElement | null;
  private dragged = false;
  onOpen: ((open: boolean) => void) | null = null;

  constructor(readonly id: string, readonly title: string, private readonly opts: PanelOptions = {}) {
    this.root = el(`<section class="fl-panel" data-panel="${id}"><button class="fl-panel-head" type="button" aria-expanded="true"><span class="fl-panel-chev">${icon('chevronDown', 12)}</span><span class="fl-panel-title"></span><span class="fl-panel-tools"></span></button><div class="fl-panel-body"></div></section>`);
    this.head = q<HTMLButtonElement>(this.root, '.fl-panel-head');
    this.body = q(this.root, '.fl-panel-body');
    this.tools = q(this.root, '.fl-panel-tools');
    q(this.root, '.fl-panel-title').textContent = title;
    this.head.title = 'Click to open or close; Alt-click for this panel alone; drag to reorder; right-click to choose panels';
    this.sw = null;
    if (opts.toggle) {
      const t = opts.toggle;
      const sw = el(`<span class="fl-panel-switch" role="switch" tabindex="0"></span>`);
      sw.title = t.title;
      sw.addEventListener('click', (e) => { e.stopPropagation(); t.set(!t.on()); this.sync(); });
      this.tools.appendChild(sw);
      this.sw = sw;
    }
    for (const tool of opts.tools ?? []) this.tools.appendChild(tool);
    PANELS.set(id, this);
    if (isPanelHidden(id)) setHidden(this.root, true);
    const saved = readState()[id];
    this.setOpen(saved ?? opts.open ?? true, false);
    this.head.addEventListener('click', (e) => {
      if (this.dragged) { this.dragged = false; return; }
      if ((e.target as HTMLElement).closest('.fl-panel-tools > *')) return;
      if (e.altKey) { this.solo(); return; }
      const open = !this.isOpen;
      if (open && isSolo(sideOf(this.root))) this.solo();
      else this.setOpen(open, true);
    });
    this.head.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      this.root.dispatchEvent(new CustomEvent('fl-panel-menu', { bubbles: true, detail: { id, x: e.clientX, y: e.clientY } }));
    });
    this.dragging();
    this.sync();
  }

  get isOpen(): boolean { return this.head.getAttribute('aria-expanded') === 'true'; }

  setOpen(open: boolean, persist = true): void {
    if (this.isOpen !== open) this.head.setAttribute('aria-expanded', String(open));
    setHidden(this.body, !open);
    if (persist) writeState(this.id, open);
    this.onOpen?.(open);
  }

  private solo(): void {
    const col = this.root.parentElement;
    if (!col) return;
    for (const p of panelsIn(col)) {
      const panel = PANELS.get(p.dataset.panel ?? '');
      if (panel) panel.setOpen(p === this.root, true);
    }
  }

  private dragging(): void {
    this.head.addEventListener('pointerdown', (e) => {
      if (e.button !== 0 || (e.target as HTMLElement).closest('.fl-panel-tools > *')) return;
      const col = this.root.parentElement;
      if (!col) return;
      const startY = e.clientY;
      const scroller = col.closest<HTMLElement>('.fl-col-page');
      let active = false;
      let lastY = startY;
      let frame = 0;
      const place = () => {
        const others = panelsIn(col).filter((p) => p !== this.root && !p.hidden);
        const before = others.find((p) => { const r = p.getBoundingClientRect(); return lastY < r.top + r.height / 2; }) ?? null;
        const anchor = before ?? (others.length ? others[others.length - 1].nextSibling : null);
        if (this.root.nextSibling !== anchor && this.root !== anchor) col.insertBefore(this.root, anchor);
      };
      const edge = () => {
        frame = 0;
        if (!active || !scroller) return;
        const r = scroller.getBoundingClientRect();
        const step = lastY < r.top + 36 ? -16 : lastY > r.bottom - 36 ? 16 : 0;
        if (!step) return;
        const was = scroller.scrollTop;
        scroller.scrollTop += step;
        if (scroller.scrollTop !== was) place();
        frame = window.requestAnimationFrame(edge);
      };
      const move = (ev: PointerEvent) => {
        lastY = ev.clientY;
        if (!active) {
          if (Math.abs(lastY - startY) < 6) return;
          active = true;
          setClass(this.root, 'is-dragging', true);
        }
        place();
        if (!frame) frame = window.requestAnimationFrame(edge);
      };
      const up = () => {
        if (frame) { window.cancelAnimationFrame(frame); frame = 0; }
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', up);
        window.removeEventListener('pointercancel', up);
        if (!active) return;
        setClass(this.root, 'is-dragging', false);
        this.dragged = true;
        window.setTimeout(() => { this.dragged = false; }, 0);
        saveOrder(col);
      };
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', up);
      window.addEventListener('pointercancel', up);
    });
  }

  sync(): void {
    if (!this.sw || !this.opts.toggle) return;
    const on = this.opts.toggle.on();
    setClass(this.sw, 'is-on', on);
    this.sw.setAttribute('aria-checked', String(on));
    setClass(this.root, 'is-off', !on);
  }
}
