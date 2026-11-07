import { el, mountOnce, pendingClass, q, setClass, setHidden, setStyleVar, setText, type Disposer } from './dom';
import { icon } from './icons';
import { brandMark } from './brand';
import type { ModuleHosts } from '../modules/registry';

const SHELL = `<div class="fl-app">
<header class="fl-titlebar">
<div class="fl-identity cv-brand">${brandMark(22)}<span class="cv-brand-name">formlit</span><span class="fl-catalog-name"></span></div>
<nav class="cv-menubar" aria-label="Main menu"></nav>
<div></div>
<div class="fl-modules" role="tablist" aria-label="Modules"></div>
<div class="fl-title-tools">
<button class="cv-tt-btn" type="button" data-cmd="edit.undo" title="Undo" aria-label="Undo">${icon('undo', 16)}</button>
<button class="cv-tt-btn" type="button" data-cmd="edit.redo" title="Redo" aria-label="Redo">${icon('redo', 16)}</button>
<button class="cv-tt-btn" type="button" data-cmd="agent.claude" title="Claude Code" aria-label="Claude Code">${icon('agent', 16)}</button>
<button class="cv-tt-btn" type="button" data-cmd="view.terminal" title="Show Terminal" aria-label="Show Terminal">${icon('terminal', 16)}</button>
<button class="cv-tt-btn" type="button" data-cmd="app.lights" title="Lights Out (L)" aria-label="Lights Out">${icon('lightsOut', 16)}</button>
<button class="cv-tt-btn" type="button" data-cmd="app.preferences" title="Preferences" aria-label="Preferences">${icon('settings', 16)}</button>
</div>
</header>
<div class="fl-main">
<aside class="fl-col fl-left" aria-label="Left panels"><div class="fl-col-pages"></div><div class="fl-col-foots"></div></aside>
<div class="fl-rsz fl-rsz-left" role="separator" aria-orientation="vertical" aria-label="Resize the left panels"></div>
<section class="fl-center"><div class="fl-stage"></div><div class="fl-toolbar"></div></section>
<div class="fl-rsz fl-rsz-right" role="separator" aria-orientation="vertical" aria-label="Resize the right panels"></div>
<aside class="fl-col fl-right" aria-label="Right panels"><div class="fl-col-pages"><div class="fl-col-page fl-ext-page" aria-label="Extensions" hidden></div></div><div class="fl-col-foots"></div></aside>
</div>
<div class="fl-filmstrip"><div class="fl-strip-rsz" role="separator" aria-orientation="horizontal" aria-label="Resize the filmstrip"></div></div>
<section class="fl-dock" aria-label="Terminal" hidden></section>
<footer class="cv-status fl-status">
<span class="fl-st-count"></span><span class="fl-st-sel"></span><span class="fl-st-busy">${icon('loading', 12)}<span class="fl-st-busy-label"></span></span><span class="fl-st-gpu"></span><span class="fl-st-hint"></span>
</footer>
</div>`;

const WIDTH_KEY = 'formlit_cols';
const DOCK_KEY = 'formlit_dock_h';
const LAYOUT_KEY = 'formlit_layout';
const STRIP_KEY = 'formlit_filmstrip_h';
const MODULES_KEY = 'formlit_modules_hidden';
const AREAS = ['is-left-hidden', 'is-right-hidden', 'is-filmstrip-hidden', 'is-filmstrip-collapsed', 'is-filmstrip-top'] as const;
export type ShellArea = typeof AREAS[number];

export interface ShellLayout { left: number | null; right: number | null; leftHidden: boolean; rightHidden: boolean; filmstripHidden: boolean; toolbarHidden: boolean; dockH: number | null; stripH?: number | null; stripCollapsed?: boolean; stripTop?: boolean }

export class Shell {
  readonly app: HTMLElement;
  readonly menubar: HTMLElement;
  readonly modulesBar: HTMLElement;
  readonly filmstrip: HTMLElement;
  readonly center: HTMLElement;
  readonly dock: HTMLElement;
  private readonly leftPages: HTMLElement;
  private readonly rightPages: HTMLElement;
  private readonly leftFoots: HTMLElement;
  private readonly rightFoots: HTMLElement;
  readonly extPage: HTMLElement;
  private extOpen = false;
  private readonly stage: HTMLElement;
  private readonly toolbar: HTMLElement;
  private readonly hosts = new Map<string, ModuleHosts>();
  private readonly tabs = new Map<string, HTMLButtonElement>();
  private busyCount = 0;
  private busyDone: Disposer | null = null;
  lights = 0;
  onModule: ((id: string) => void) | null = null;

  constructor(host: HTMLElement) {
    mountOnce(host, SHELL);
    this.app = q(host, '.fl-app');
    this.menubar = q(host, '.cv-menubar');
    this.modulesBar = q(host, '.fl-modules');
    this.filmstrip = q(host, '.fl-filmstrip');
    this.center = q(host, '.fl-center');
    this.dock = q(host, '.fl-dock');
    this.stage = q(host, '.fl-stage');
    this.toolbar = q(host, '.fl-toolbar');
    this.leftPages = q(host, '.fl-left .fl-col-pages');
    this.rightPages = q(host, '.fl-right .fl-col-pages');
    this.leftFoots = q(host, '.fl-left .fl-col-foots');
    this.rightFoots = q(host, '.fl-right .fl-col-foots');
    this.extPage = q(host, '.fl-ext-page');
    this.restoreWidths();
    try {
      const saved = JSON.parse(localStorage.getItem(LAYOUT_KEY) || '{}') as Record<string, boolean>;
      for (const cls of AREAS) if (saved[cls]) setClass(this.app, cls, true);
      if (saved['is-toolbar-hidden']) setClass(this.center, 'is-toolbar-hidden', true);
    } catch { /* first run */ }
    this.resizer(q(host, '.fl-rsz-left'), '--fl-left-w', 1);
    this.resizer(q(host, '.fl-rsz-right'), '--fl-right-w', -1);
    this.dockResizer();
    this.stripResizer();
  }

  private stripResizer(): void {
    try {
      const h = Number(localStorage.getItem(STRIP_KEY));
      if (h) setStyleVar(this.app, '--fl-filmstrip-h', `${h}px`);
    } catch { /* first run */ }
    const handle = q(this.filmstrip, '.fl-strip-rsz');
    handle.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      const start = e.clientY;
      const from = this.filmstrip.getBoundingClientRect().height;
      const dir = this.app.classList.contains('is-filmstrip-top') ? 1 : -1;
      handle.setPointerCapture(e.pointerId);
      setClass(handle, 'is-dragging', true);
      const move = (ev: PointerEvent) => setStyleVar(this.app, '--fl-filmstrip-h', `${Math.round(Math.max(72, Math.min(320, from + (ev.clientY - start) * dir)))}px`);
      const up = () => {
        handle.removeEventListener('pointermove', move);
        handle.removeEventListener('pointerup', up);
        setClass(handle, 'is-dragging', false);
        try { localStorage.setItem(STRIP_KEY, String(Math.round(this.filmstrip.getBoundingClientRect().height))); } catch { return; }
      };
      handle.addEventListener('pointermove', move);
      handle.addEventListener('pointerup', up);
    });
  }

  hiddenModules(): string[] {
    try { return JSON.parse(localStorage.getItem(MODULES_KEY) || '[]') as string[]; } catch { return []; }
  }

  setModuleShown(id: string, on: boolean): void {
    const hidden = new Set(this.hiddenModules());
    if (on) hidden.delete(id); else hidden.add(id);
    try { localStorage.setItem(MODULES_KEY, JSON.stringify([...hidden])); } catch { /* kept for this session */ }
    const tab = this.tabs.get(id);
    if (tab) setHidden(tab, !on);
  }

  dockOpen(): boolean { return this.app.classList.contains('is-dock-open'); }

  setDock(open: boolean): void {
    setHidden(this.dock, !open);
    setClass(this.app, 'is-dock-open', open);
  }

  private dockResizer(): void {
    try {
      const h = Number(localStorage.getItem(DOCK_KEY));
      if (h) setStyleVar(this.app, '--fl-dock-open-h', `${h}px`);
    } catch { return; }
    this.dock.addEventListener('pointerdown', (e) => {
      const handle = e.target as HTMLElement;
      if (e.button !== 0 || !handle.classList.contains('fl-dock-rsz')) return;
      const start = e.clientY;
      const from = this.dock.getBoundingClientRect().height;
      handle.setPointerCapture(e.pointerId);
      setClass(handle, 'is-dragging', true);
      const move = (ev: PointerEvent) => {
        const h = Math.round(Math.max(140, Math.min(window.innerHeight * 0.7, from - (ev.clientY - start))));
        setStyleVar(this.app, '--fl-dock-open-h', `${h}px`);
      };
      const up = () => {
        handle.removeEventListener('pointermove', move);
        handle.removeEventListener('pointerup', up);
        setClass(handle, 'is-dragging', false);
        try { localStorage.setItem(DOCK_KEY, String(Math.round(this.dock.getBoundingClientRect().height))); } catch { return; }
      };
      handle.addEventListener('pointermove', move);
      handle.addEventListener('pointerup', up);
    });
  }

  addModuleTab(id: string, label: string, iconName: string, title: string): void {
    const b = el<HTMLButtonElement>(`<button class="fl-module" type="button" role="tab" aria-selected="false">${icon(iconName, 14)}<span class="fl-module-label"></span></button>`);
    setText(q(b, '.fl-module-label'), label);
    b.title = title;
    b.addEventListener('click', () => this.onModule?.(id));
    if (this.hiddenModules().includes(id)) setHidden(b, true);
    this.modulesBar.appendChild(b);
    this.tabs.set(id, b);
  }

  hostsFor(id: string): ModuleHosts {
    let h = this.hosts.get(id);
    if (h) return h;
    const page = (cls: string) => el(`<div class="${cls}" data-module="${id}" hidden></div>`);
    h = { left: page('fl-col-page'), leftFoot: page('fl-col-foot'), stage: page('fl-stage-page'), toolbar: page('fl-toolbar-page'), right: page('fl-col-page'), rightFoot: page('fl-col-foot') };
    this.leftPages.appendChild(h.left);
    this.leftFoots.appendChild(h.leftFoot);
    this.stage.appendChild(h.stage);
    this.toolbar.appendChild(h.toolbar);
    this.rightPages.appendChild(h.right);
    this.rightFoots.appendChild(h.rightFoot);
    this.hosts.set(id, h);
    return h;
  }

  show(id: string): void {
    for (const [mid, h] of this.hosts) {
      const on = mid === id;
      setHidden(h.left, !on);
      setHidden(h.stage, !on);
      setHidden(h.toolbar, !on);
      setHidden(h.right, !on || this.extOpen);
      setHidden(h.leftFoot, !on || h.leftFoot.childElementCount === 0);
      setHidden(h.rightFoot, !on || this.extOpen || h.rightFoot.childElementCount === 0);
    }
    setHidden(this.extPage, !this.extOpen);
    for (const [mid, b] of this.tabs) {
      setClass(b, 'is-active', mid === id);
      b.setAttribute('aria-selected', String(mid === id));
    }
    this.app.dataset.module = id;
  }

  extensionsOpen(): boolean { return this.extOpen; }

  setExtensions(open: boolean): void {
    this.extOpen = open;
    if (open) this.toggle('is-right-hidden', false);
    this.show(this.app.dataset.module ?? '');
  }

  toggle(cls: ShellArea, on?: boolean): void {
    setClass(this.app, cls, on ?? !this.app.classList.contains(cls));
    this.saveAreas();
  }

  toggleToolbar(): void { setClass(this.center, 'is-toolbar-hidden', !this.center.classList.contains('is-toolbar-hidden')); this.saveAreas(); }

  private saveAreas(): void {
    const s: Record<string, boolean> = { 'is-toolbar-hidden': this.center.classList.contains('is-toolbar-hidden') };
    for (const cls of AREAS) s[cls] = this.app.classList.contains(cls);
    try { localStorage.setItem(LAYOUT_KEY, JSON.stringify(s)); } catch { return; }
  }

  layout(): ShellLayout {
    const px = (prop: string): number | null => { const v = this.app.style.getPropertyValue(prop); return v ? Math.round(parseFloat(v)) : null; };
    return {
      left: px('--fl-left-w'), right: px('--fl-right-w'), dockH: px('--fl-dock-open-h'), stripH: px('--fl-filmstrip-h'),
      leftHidden: this.app.classList.contains('is-left-hidden'), rightHidden: this.app.classList.contains('is-right-hidden'),
      filmstripHidden: this.app.classList.contains('is-filmstrip-hidden'), toolbarHidden: this.center.classList.contains('is-toolbar-hidden'),
      stripCollapsed: this.app.classList.contains('is-filmstrip-collapsed'), stripTop: this.app.classList.contains('is-filmstrip-top'),
    };
  }

  applyLayout(l: Partial<ShellLayout>): void {
    const width = (prop: string, v: number | null | undefined) => {
      if (v === undefined) return;
      if (v === null) this.app.style.removeProperty(prop); else setStyleVar(this.app, prop, `${Math.round(Math.max(200, Math.min(520, v)))}px`);
    };
    width('--fl-left-w', l.left);
    width('--fl-right-w', l.right);
    if (l.dockH !== undefined) {
      if (l.dockH === null) this.app.style.removeProperty('--fl-dock-open-h'); else setStyleVar(this.app, '--fl-dock-open-h', `${Math.round(Math.max(140, l.dockH))}px`);
    }
    if (l.stripH !== undefined) {
      if (l.stripH === null) this.app.style.removeProperty('--fl-filmstrip-h'); else setStyleVar(this.app, '--fl-filmstrip-h', `${Math.round(Math.max(72, Math.min(320, l.stripH)))}px`);
      try { if (l.stripH) localStorage.setItem(STRIP_KEY, String(Math.round(l.stripH))); else localStorage.removeItem(STRIP_KEY); } catch { /* kept for this session */ }
    }
    if (l.leftHidden !== undefined) setClass(this.app, 'is-left-hidden', l.leftHidden);
    if (l.rightHidden !== undefined) setClass(this.app, 'is-right-hidden', l.rightHidden);
    if (l.filmstripHidden !== undefined) setClass(this.app, 'is-filmstrip-hidden', l.filmstripHidden);
    if (l.stripCollapsed !== undefined) setClass(this.app, 'is-filmstrip-collapsed', l.stripCollapsed);
    if (l.stripTop !== undefined) setClass(this.app, 'is-filmstrip-top', l.stripTop);
    if (l.toolbarHidden !== undefined) setClass(this.center, 'is-toolbar-hidden', l.toolbarHidden);
    this.saveAreas();
    try {
      const cur = this.layout();
      localStorage.setItem(WIDTH_KEY, JSON.stringify({ ...(cur.left ? { left: cur.left } : {}), ...(cur.right ? { right: cur.right } : {}) }));
      if (cur.dockH) localStorage.setItem(DOCK_KEY, String(cur.dockH)); else localStorage.removeItem(DOCK_KEY);
    } catch { return; }
  }

  togglePanels(): void {
    const hide = !(this.app.classList.contains('is-left-hidden') && this.app.classList.contains('is-right-hidden'));
    this.toggle('is-left-hidden', hide);
    this.toggle('is-right-hidden', hide);
  }

  toggleAll(): void {
    const hide = !this.app.classList.contains('is-filmstrip-hidden');
    this.toggle('is-left-hidden', hide);
    this.toggle('is-right-hidden', hide);
    this.toggle('is-filmstrip-hidden', hide);
  }

  cycleScreen(): void { setClass(this.app, 'is-screen-full', !this.app.classList.contains('is-screen-full')); }

  cycleLights(): void {
    this.lights = (this.lights + 1) % 3;
    setClass(this.app, 'is-lights-dim', this.lights === 1);
    setClass(this.app, 'is-lights-off', this.lights === 2);
  }

  setCatalogName(name: string): void { setText(q(this.app, '.fl-catalog-name'), name); }
  setCount(text: string): void { setText(q(this.app, '.fl-st-count'), text); }
  setSelection(text: string): void { setText(q(this.app, '.fl-st-sel'), text); }
  setGpu(text: string): void { setText(q(this.app, '.fl-st-gpu'), text); }
  setHint(text: string): void { setText(q(this.app, '.fl-st-hint'), text); }

  busy(label: string): Disposer {
    const node = q(this.app, '.fl-st-busy');
    setText(q(node, '.fl-st-busy-label'), label);
    this.busyCount += 1;
    if (this.busyCount === 1) this.busyDone = pendingClass(node);
    let done = false;
    return () => {
      if (done) return;
      done = true;
      this.busyCount -= 1;
      if (this.busyCount === 0) { this.busyDone?.(); this.busyDone = null; }
    };
  }

  private restoreWidths(): void {
    try {
      const w = JSON.parse(localStorage.getItem(WIDTH_KEY) || '{}') as Record<string, number>;
      if (w.left) setStyleVar(this.app, '--fl-left-w', `${w.left}px`);
      if (w.right) setStyleVar(this.app, '--fl-right-w', `${w.right}px`);
    } catch { return; }
  }

  private resizer(handle: HTMLElement, prop: string, dir: 1 | -1): void {
    handle.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      const start = e.clientX;
      const from = parseFloat(getComputedStyle(this.app).getPropertyValue(prop)) || 260;
      handle.setPointerCapture(e.pointerId);
      setClass(handle, 'is-dragging', true);
      const move = (ev: PointerEvent) => {
        const w = Math.round(Math.max(200, Math.min(520, from + (ev.clientX - start) * dir)));
        setStyleVar(this.app, prop, `${w}px`);
      };
      const up = () => {
        handle.removeEventListener('pointermove', move);
        handle.removeEventListener('pointerup', up);
        setClass(handle, 'is-dragging', false);
        try {
          const w = JSON.parse(localStorage.getItem(WIDTH_KEY) || '{}') as Record<string, number>;
          w[dir === 1 ? 'left' : 'right'] = parseFloat(getComputedStyle(this.app).getPropertyValue(prop));
          localStorage.setItem(WIDTH_KEY, JSON.stringify(w));
        } catch { return; }
      };
      handle.addEventListener('pointermove', move);
      handle.addEventListener('pointerup', up);
    });
  }
}
