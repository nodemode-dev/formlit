import { el, q, setClass, setHidden } from './dom';
import { icon } from './icons';

const KEY = 'formlit_panels';

function readState(): Record<string, boolean> {
  try { return JSON.parse(localStorage.getItem(KEY) || '{}') as Record<string, boolean>; } catch { return {}; }
}

function writeState(id: string, open: boolean): void {
  try { const s = readState(); s[id] = open; localStorage.setItem(KEY, JSON.stringify(s)); } catch { return; }
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
  onOpen: ((open: boolean) => void) | null = null;

  constructor(readonly id: string, title: string, private readonly opts: PanelOptions = {}) {
    this.root = el(`<section class="fl-panel" data-panel="${id}"><button class="fl-panel-head" type="button" aria-expanded="true"><span class="fl-panel-chev">${icon('chevronDown', 12)}</span><span class="fl-panel-title"></span><span class="fl-panel-tools"></span></button><div class="fl-panel-body"></div></section>`);
    this.head = q<HTMLButtonElement>(this.root, '.fl-panel-head');
    this.body = q(this.root, '.fl-panel-body');
    this.tools = q(this.root, '.fl-panel-tools');
    q(this.root, '.fl-panel-title').textContent = title;
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
    const saved = readState()[id];
    this.setOpen(saved ?? opts.open ?? true, false);
    this.head.addEventListener('click', (e) => {
      if ((e.target as HTMLElement).closest('.fl-panel-tools > *')) return;
      if (e.altKey) { this.solo(); return; }
      this.setOpen(!this.isOpen, true);
    });
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
    for (const p of Array.from(col.querySelectorAll<HTMLElement>(':scope > .fl-panel'))) {
      const head = p.querySelector('.fl-panel-head');
      const body = p.querySelector<HTMLElement>('.fl-panel-body');
      if (!head || !body) continue;
      const open = p === this.root;
      head.setAttribute('aria-expanded', String(open));
      setHidden(body, !open);
      writeState(p.dataset.panel ?? '', open);
    }
  }

  sync(): void {
    if (!this.sw || !this.opts.toggle) return;
    const on = this.opts.toggle.on();
    setClass(this.sw, 'is-on', on);
    this.sw.setAttribute('aria-checked', String(on));
    setClass(this.root, 'is-off', !on);
  }
}
