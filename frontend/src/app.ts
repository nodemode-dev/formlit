import { Commands, comboOf, type Command } from './ui/commands';
import { MenuBar, type MenuDef } from './ui/menu';
import { Shell } from './ui/shell';
import { applyTheme } from './ui/themes';
import { revealApp, setClass, setDisabled, setTitle } from './ui/dom';
import { anyDialogOpen } from './ui/dialogs';
import { toast } from './ui/toast';
import { api, errorText, type Api } from './io/api';
import { events } from './io/events';
import { registerPhotoActions } from './modules/shared/actions';
import { registerTemplateActions } from './modules/shared/templates';
import { registerWorkspace, workspaceMenu } from './modules/shared/workspace';
import { showReference } from './modules/develop/index';
import { registerAiCommands } from './modules/shared/ai';
import { registerExport } from './modules/shared/export';
import { registerCaptions } from './modules/shared/captions';
import { registerPhotoDialogs } from './modules/shared/photo-dialogs';
import { registerCatalogCommands } from './modules/shared/catalog-commands';
import { registerSessionCommands } from './modules/library/session-panel';
import { registerProofing } from './modules/shared/proofing';
import { registerTether } from './modules/shared/tether';
import { registerPluginManager } from './modules/shared/plugin-manager';
import { registerAgentConsent } from './modules/shared/agent-consent';
import { registerTerminal } from './modules/shared/terminal';
import { openPreferences } from './ui/preferences';
import { library, type Source } from './state/library';
import { develop } from './state/develop';
import { catalog } from './state/catalog';
import { moduleById, modules, type LitModule } from './modules/registry';
import { VERSION } from './version';

export interface Ctx {
  api: Api;
  shell: Shell;
  commands: Commands;
  module(): string;
  toModule(id: string): void;
  run(id: string): void;
  fail(err: unknown, what?: string): void;
  menus: MenuDef[];
}

const MODULE_KEY = 'formlit_module';

export class App implements Ctx {
  readonly api = api;
  readonly shell: Shell;
  readonly commands = new Commands();
  readonly menus: MenuDef[] = [];
  private current = '';
  private readonly mounted = new Set<string>();

  constructor(host: HTMLElement) {
    applyTheme();
    this.shell = new Shell(host);
    this.shell.onModule = (id) => this.toModule(id);
    this.globalCommands();
  }

  module(): string { return this.current; }

  run(id: string): void {
    if (!this.commands.run(id)) {
      const cmd = this.commands.get(id);
      if (cmd && !this.commands.enabled(cmd)) toast('Not available here');
    }
    this.syncButtons();
  }

  fail(err: unknown, what = ''): void {
    toast(what ? `${what}: ${errorText(err)}` : errorText(err), 'error');
  }

  start(): void {
    for (const m of modules()) this.shell.addModuleTab(m.id, m.label, m.icon, `${m.label} (${this.keyText(m)})`);
    registerPhotoActions(this);
    registerTemplateActions(this);
    registerAiCommands(this);
    registerExport(this);
    registerCaptions(this);
    registerPhotoDialogs(this);
    registerCatalogCommands(this);
    registerSessionCommands(this);
    registerProofing(this);
    registerTether(this);
    registerPluginManager(this);
    registerAgentConsent(this);
    registerTerminal(this);
    registerWorkspace(this);
    this.engineStatus();
    for (const m of modules()) {
      m.mount(this, this.shell.hostsFor(m.id));
      this.mounted.add(m.id);
    }
    this.buildMenus();
    document.addEventListener('keydown', (e) => this.onKey(e));
    document.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-cmd]');
      if (b && !b.closest('.cv-menu')) this.run(b.dataset.cmd as string);
    });
    let first = modules()[0]?.id ?? '';
    try { const saved = localStorage.getItem(MODULE_KEY); if (saved && moduleById(saved)) first = saved; } catch { first = modules()[0]?.id ?? ''; }
    if (first) this.toModule(first);
    this.syncButtons();
    let queued = 0;
    const sync = (): void => { if (!queued) queued = requestAnimationFrame(() => { queued = 0; this.syncButtons(); }); };
    library.listen('selection', sync);
    library.listen('list', sync);
    library.listen('photos', () => sync());
    catalog.listen(sync);
    develop.listen((why) => { if (why !== 'drag') sync(); });
    events.on('undo', sync);
    events.on('redo', sync);
    document.addEventListener('pointerup', sync, true);
    document.addEventListener('keyup', sync, true);
    const tree = new Promise<void>((done) => { const off = catalog.listen(() => { off(); done(); }); window.setTimeout(done, 2500); });
    void Promise.all([document.fonts.ready, tree]).then(() => revealApp());
  }

  toModule(id: string): void {
    const m = moduleById(id);
    if (!m || id === this.current) return;
    const prev = moduleById(this.current);
    if (!this.mounted.has(id)) {
      m.mount(this, this.shell.hostsFor(id));
      this.mounted.add(id);
    }
    prev?.deactivate?.();
    this.current = id;
    this.shell.show(id);
    m.activate?.();
    try { localStorage.setItem(MODULE_KEY, id); } catch { this.syncButtons(); }
    this.syncButtons();
  }

  private engineStatus(): void {
    const running = new Map<number, () => void>();
    events.on('task', (e) => {
      const id = Number(e.id);
      const state = String(e.state);
      if (state === 'running') {
        if (!running.has(id)) running.set(id, this.shell.busy(String(e.label ?? 'Working')));
        const done = Number(e.done ?? 0), total = Number(e.total ?? 0);
        this.shell.setHint(total ? `${String(e.label ?? '')} · ${done} of ${total}` : String(e.label ?? ''));
        return;
      }
      running.get(id)?.();
      running.delete(id);
      this.shell.setHint(state === 'failed' ? `${String(e.label ?? 'Task')} failed: ${String(e.error ?? '')}` : '');
      if (state === 'failed') toast(`${String(e.label ?? 'Task')} failed: ${String(e.error ?? '')}`, 'error');
    });
    let agentTimer = 0;
    events.on('agent.activity', (e) => {
      this.shell.setHint(`Agent · ${String(e.label ?? e.tool ?? '')}`);
      window.clearTimeout(agentTimer);
      agentTimer = window.setTimeout(() => this.shell.setHint(''), 4000);
    });
    events.on('agent.show', (e) => {
      if (typeof e.module === 'string' && moduleById(e.module)) this.toModule(e.module);
      if (e.source && typeof e.source === 'object') library.setSource(e.source as Source);
      if (typeof e.photo === 'number') library.setActive(e.photo, false);
      if (typeof e.reference === 'number') { if (this.current !== 'develop') this.toModule('develop'); showReference(e.reference); }
      if (typeof e.message === 'string' && e.message) toast(e.message);
    });
    events.onStatus = (on) => this.shell.setGpu(on ? '' : 'Engine offline · reconnecting');
    events.start();
  }

  private keyText(m: LitModule): string {
    return m.key.replace('Mod', /Mac|iPhone|iPad/.test(navigator.platform) ? 'Cmd' : 'Ctrl').split('+').join('+');
  }

  private onKey(e: KeyboardEvent): void {
    if (anyDialogOpen()) return;
    const t = e.target as HTMLElement;
    const typing = t.closest('input, textarea, select, [contenteditable="true"]') !== null;
    const combo = comboOf(e);
    if (typing && !combo.includes('Mod')) return;
    const m = moduleById(this.current);
    if (m?.onKey?.(e, combo)) { e.preventDefault(); this.syncButtons(); return; }
    const cmd = this.commands.forCombo(combo);
    if (cmd) {
      e.preventDefault();
      this.run(cmd.id);
    }
  }

  syncButtons(): void {
    for (const b of Array.from(document.querySelectorAll<HTMLButtonElement>('[data-cmd]'))) {
      const cmd = this.commands.get(b.dataset.cmd as string);
      if (!cmd) continue;
      const keys = this.commands.keyLabel(cmd);
      const label = this.commands.label(cmd);
      setTitle(b, keys ? `${label} (${keys})` : label);
      setDisabled(b, !this.commands.enabled(cmd));
      setClass(b, 'is-on', !!cmd.checked?.());
    }
  }

  private globalCommands(): void {
    const s = this.shell;
    const add = (...c: Command[]) => this.commands.add(...c);
    add(
      { id: 'view.toggleLeft', label: 'Show Left Panels', keys: ['Shift+Tab'], run: () => s.toggle('is-left-hidden'), checked: () => !s.app.classList.contains('is-left-hidden') },
      { id: 'view.togglePanels', label: 'Show Side Panels', keys: ['Tab'], run: () => s.togglePanels() },
      { id: 'view.toggleRight', label: 'Show Right Panels', run: () => s.toggle('is-right-hidden'), checked: () => !s.app.classList.contains('is-right-hidden') },
      { id: 'view.toggleFilmstrip', label: 'Show Filmstrip', keys: ['F6'], run: () => s.toggle('is-filmstrip-hidden'), checked: () => !s.app.classList.contains('is-filmstrip-hidden') },
      { id: 'view.filmstripCollapse', label: 'Collapse Filmstrip', keys: ['Alt+F6'], run: () => { s.toggle('is-filmstrip-hidden', false); s.toggle('is-filmstrip-collapsed'); }, checked: () => s.app.classList.contains('is-filmstrip-collapsed') },
      { id: 'view.filmstripTop', label: 'Filmstrip at Top', run: () => { s.toggle('is-filmstrip-hidden', false); s.toggle('is-filmstrip-top'); }, checked: () => s.app.classList.contains('is-filmstrip-top') },
      { id: 'view.toggleToolbar', label: 'Show Toolbar', keys: ['T'], run: () => s.toggleToolbar(), checked: () => !s.center.classList.contains('is-toolbar-hidden') },
      { id: 'view.toggleAll', label: 'Hide All Panels', keys: ['Shift+F6'], run: () => s.toggleAll() },
      { id: 'app.screen', label: 'Full Screen', keys: ['Shift+F'], run: () => s.cycleScreen(), checked: () => s.app.classList.contains('is-screen-full') },
      { id: 'app.lights', label: 'Lights Out', keys: ['L'], run: () => s.cycleLights() },
      { id: 'app.about', label: 'About formlit', run: () => toast(`formlit ${VERSION} · photo library and raw developer`) },
      { id: 'app.preferences', label: 'Preferences...', keys: ['Mod+,'], run: () => openPreferences(this) },
    );
    for (const [i, m] of modules().entries()) {
      add({ id: `module.${m.id}`, label: m.label, keys: [m.key], run: () => this.toModule(m.id), checked: () => this.current === m.id });
      if (i > 8) break;
    }
  }

  private buildMenus(): void {
    const has = (id: string) => !!this.commands.get(id);
    const pick = (items: Array<string | '-'>) => items.filter((i) => i === '-' || has(i));
    const tidy = (items: Array<string | '-'>) => pick(items).filter((x, i, a) => !(x === '-' && (i === 0 || a[i - 1] === '-' || i === a.length - 1)));
    const defs = this.menus.length ? this.menus : [
      { label: 'File', items: () => tidy(['library.newCatalog', 'library.openCatalog', '-', 'session.new', 'session.open', 'session.close', '-', 'library.import', 'library.importCatalog', 'library.exportCatalog','library.autoImport', 'library.autoImportSettings', 'library.tether', 'library.tetherStop', '-', 'library.export', 'library.exportPrevious', 'library.proofExport', 'library.proofImport', '-', 'library.editIn', '-', 'preset.importFiles', 'app.pluginManager', '-', 'app.preferences', 'app.about']) },
      { label: 'Edit', items: () => tidy(['edit.undo', 'edit.redo', '-', 'edit.selectAll', 'edit.selectNone', 'edit.invertSelection', 'edit.selectPicks', 'edit.deselectUnflagged', '-', 'view.find']) },
      { label: 'Library', items: () => tidy(['workflow.newShoot', '-', 'lib.colNew', 'lib.colNewSmart', 'template.smart', 'lib.colNewSet', '-','view.filterBar', 'library.filterPicks', 'library.filterOff', '-', 'library.cull', 'library.refine', 'library.findFaces', 'library.drawFace', '-', 'session.select', 'session.trash', 'session.restore', '-', 'library.syncFolder', 'library.checkFiles', 'library.findMissing', 'library.locate', 'library.buildPreviews', 'library.buildSmartPreviews', 'library.discardSmartPreviews', 'library.syncMetadata', '-', 'photo.prev', 'photo.next']) },
      { label: 'Photo', items: () => tidy(['photo.autoAdvance', '-', 'photo.reveal', 'library.editIn', '-', 'photo.enhance', 'photo.hdr', 'photo.pano', 'photo.hdrPano', 'photo.focusStack', 'photo.astroStack', '-', 'photo.stack', 'photo.unstack', 'photo.toggleStack', 'photo.autoStack', '-', 'photo.virtualCopy', 'photo.setMaster', '-', 'photo.rotateLeft', 'photo.rotateRight', '-', 'photo.pick', 'photo.reject', 'photo.unflag', 'photo.rate0', 'photo.rate1', 'photo.rate2', 'photo.rate3', 'photo.rate4', 'photo.rate5', 'photo.label.red', 'photo.label.yellow', 'photo.label.green', 'photo.label.blue', 'photo.label.purple', 'photo.label.none', '-', 'photo.quick', 'photo.quickClear', 'photo.target', '-', 'photo.remove', 'photo.deleteRejected', 'photo.delete']) },
      { label: 'Metadata', items: () => tidy(['photo.saveMetadata', 'photo.readMetadata', '-', 'template.metadata', 'template.keywords', '-', 'metadata.codes', 'metadata.codesChoose', 'metadata.codesImport', 'metadata.required', 'metadata.checkRequired', '-', 'library.syncMetadata', 'library.captureTime', 'library.rename', '-', 'library.labelSet']) },
      { label: 'Develop', items: () => tidy(['develop.auto', 'develop.copy', 'develop.paste', 'develop.pastePrevious', 'develop.syncSettings', 'develop.reset', '-', 'develop.profileBrowser', 'develop.snapshot', 'develop.beforeAfter', 'develop.preset', '-', 'develop.copyAfterToBefore', 'develop.copyBeforeToAfter', 'develop.swapBeforeAfter', 'develop.resetBefore', '-', 'develop.referenceView', 'develop.setReference', 'develop.matchReference', '-', 'develop.matchExposure', 'develop.noiseByIso', 'develop.autoBw']) },
      { label: 'View', items: () => tidy(['view.grid', 'view.loupe', 'view.compare', 'view.survey', 'view.cull', '-', 'view.zoomToggle', 'view.zoomIn', 'view.zoomOut', 'view.info', 'view.faceRegions', '-', 'view.togglePanels', 'view.toggleLeft', 'view.toggleRight', 'view.toggleFilmstrip', 'view.filmstripCollapse', 'view.filmstripTop', 'view.toggleToolbar', 'view.toggleAll', '-', 'app.lights', 'app.screen']) },
      { label: 'Window', items: () => [workspaceMenu(this), '-', ...tidy([...modules().map((m) => `module.${m.id}`), '-', 'view.secondWindow', 'view.second.grid', 'view.second.loupe', 'view.second.compare', 'view.second.survey', 'view.second.slideshow', '-', 'library.impromptuSlideshow', '-', 'view.terminal', 'view.newTerminal', 'agent.claude', 'agent.chat'])] },
      { label: 'Help', items: () => tidy(['app.shortcuts', 'agent.chat', 'agent.claude', 'app.agents', 'app.about']) },
    ];
    new MenuBar(this.shell.menubar, this.commands, defs);
  }
}
