import type { Ctx } from '../../app';
import { catalog, type CollectionRow } from '../../state/catalog';
import { library } from '../../state/library';
import { confirmAction, promptName } from '../../ui/dialogs';
import { el, escapeHtml, patchList, q, setClass, setHidden, setText } from '../../ui/dom';
import { Form, getPath, setPath, type FieldSpec } from '../../ui/form';
import { icon } from '../../ui/icons';
import { Panel } from '../../ui/panel';
import { toast } from '../../ui/toast';
import type { LitModule, ModuleHosts } from '../registry';

export interface Template { id: string; name: string; settings: Record<string, unknown>; user?: boolean }
type Use = 'all' | 'selected' | 'flagged';

function clone<T>(v: T): T { return JSON.parse(JSON.stringify(v ?? null)) as T; }

export function deepMerge(base: Record<string, unknown>, over: Record<string, unknown> | undefined | null): Record<string, unknown> {
  const out = clone(base) ?? {};
  for (const [k, v] of Object.entries(over ?? {})) {
    const cur = out[k];
    out[k] = v && typeof v === 'object' && !Array.isArray(v) && cur && typeof cur === 'object' && !Array.isArray(cur) ? deepMerge(cur as Record<string, unknown>, v as Record<string, unknown>) : clone(v);
  }
  return out;
}

export abstract class OutputModule implements LitModule {
  abstract readonly id: string;
  abstract readonly label: string;
  abstract readonly icon: string;
  abstract readonly key: string;
  abstract readonly order: number;
  protected abstract readonly optionsCmd: string;
  protected abstract readonly kind: string;
  protected ctx!: Ctx;
  protected hosts!: ModuleHosts;
  protected settings: Record<string, unknown> = {};
  protected defaults: Record<string, unknown> = {};
  protected options: Record<string, unknown> | null = null;
  protected active = false;
  protected use: Use = 'all';
  protected creation: number | null = null;
  private readonly forms: Form[] = [];
  private readonly templateList = el('<div class="fl-list fl-out-list"></div>');
  private readonly savedList = el('<div class="fl-list fl-out-list"></div>');
  private readonly savedEmpty = el('<div class="fl-list-empty fl-muted"></div>');
  private builtins: Template[] = [];
  private userTemplates: Template[] = [];
  private timer = 0;
  private loading: Promise<void> | null = null;
  private readonly bar = el('<div class="fl-tb fl-out-tb"></div>');
  private readonly useSel = el<HTMLSelectElement>('<select class="cv-select fl-out-use" aria-label="Use"><option value="all">All Filmstrip Photos</option><option value="selected">Selected Photos</option><option value="flagged">Flagged Photos</option></select>');
  protected readonly status = el('<span class="fl-tb-label fl-out-status"></span>');

  mount(ctx: Ctx, hosts: ModuleHosts): void {
    this.ctx = ctx;
    this.hosts = hosts;
    try { this.use = (localStorage.getItem(`formlit_${this.id}_use`) as Use) || 'all'; } catch { this.use = 'all'; }
    this.useSel.value = this.use;
    this.useSel.addEventListener('change', () => {
      this.use = this.useSel.value as Use;
      try { localStorage.setItem(`formlit_${this.id}_use`, this.use); } catch { this.schedule(0); }
      this.schedule(0);
    });
    const saveTpl = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" aria-label="Save Template">${icon('plus', 14)}</button>`);
    saveTpl.addEventListener('click', () => void this.saveTemplate());
    const pT = new Panel(`${this.id}.templates`, 'Template Browser', { tools: [saveTpl] });
    pT.body.appendChild(this.templateList);
    const saveCol = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" aria-label="Save ${this.label}">${icon('plus', 14)}</button>`);
    saveCol.addEventListener('click', () => void this.saveCreation());
    const pC = new Panel(`${this.id}.saved`, `Saved ${this.label}s`, { tools: [saveCol] });
    setText(this.savedEmpty, `Press + to save this ${this.label.toLowerCase()} with its photos`);
    pC.body.append(this.savedList, this.savedEmpty);
    hosts.left.append(pT.root, pC.root);
    this.templateList.addEventListener('click', (e) => this.onTemplateClick(e));
    this.templateList.addEventListener('contextmenu', (e) => this.onTemplateContext(e));
    this.savedList.addEventListener('click', (e) => this.onSavedClick(e));
    this.savedList.addEventListener('contextmenu', (e) => this.onSavedContext(e));
    this.bar.append(this.useSel, el('<span class="fl-tb-sep"></span>'));
    this.buildToolbar(this.bar);
    this.bar.append(el('<span class="fl-tb-spacer"></span>'), this.status);
    hosts.toolbar.appendChild(this.bar);
    this.buildStage(hosts.stage);
    this.buildPanels(hosts.right);
    this.buildFoots(hosts.leftFoot, hosts.rightFoot);
    catalog.listen(() => this.renderSaved());
    library.listen('list', () => { if (this.active) this.schedule(120); });
    library.listen('selection', () => { if (this.active && this.use !== 'all') this.schedule(120); });
    library.listen('photos', () => { if (this.active && this.use === 'flagged') this.schedule(200); });
    library.listen('render', (_id, size) => { if (this.active && size === 'p') this.schedule(400); });
  }

  activate(): void {
    this.active = true;
    void this.ensure().then(() => this.schedule(0));
  }

  deactivate(): void { this.active = false; }

  protected ensure(): Promise<void> {
    if (this.options) return Promise.resolve();
    this.loading ??= (async () => {
      const [opts, prefs] = await Promise.all([this.ctx.api.cmd<Record<string, unknown>>(this.optionsCmd), this.ctx.api.cmd<Record<string, unknown>>('prefs.get')]);
      this.options = opts;
      this.defaults = (opts.defaults as Record<string, unknown>) ?? {};
      const list = Array.isArray(opts.templates) ? opts.templates : Array.isArray(opts.presets) ? opts.presets : [];
      this.builtins = (list as Template[]).map((t) => ({ ...t, id: `b.${t.id}` }));
      this.userTemplates = (((prefs.templates as Record<string, Template[]>) ?? {})[this.kind] ?? []).map((t) => ({ ...t, user: true }));
      let saved: Record<string, unknown> | null = null;
      try { saved = JSON.parse(localStorage.getItem(`formlit_${this.id}_settings`) || 'null') as Record<string, unknown> | null; } catch { saved = null; }
      this.settings = deepMerge(this.defaults, saved ?? (this.builtins[0]?.settings ?? {}));
      this.onOptions();
      this.renderTemplates();
      this.renderSaved();
      this.syncForms();
    })().catch((err) => { this.loading = null; this.ctx.fail(err); });
    return this.loading;
  }

  protected onOptions(): void { return; }

  ids(): number[] {
    if (this.use === 'selected') return library.selected().length ? library.selected() : library.ids.slice();
    if (this.use === 'flagged') return library.ids.filter((id) => (library.photo(id)?.f ?? 0) === 1);
    return library.ids.slice();
  }

  get(path: string): unknown { return getPath(this.settings, path); }

  set(path: string, value: unknown, phase: 'input' | 'change' = 'change'): void {
    setPath(this.settings, path, value);
    this.persist();
    this.syncForms();
    this.schedule(phase === 'input' ? 160 : 40);
  }

  protected persist(): void {
    try { localStorage.setItem(`formlit_${this.id}_settings`, JSON.stringify(this.settings)); } catch { return; }
  }

  protected schedule(ms: number): void {
    window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => { if (this.active && this.options) void this.refresh().catch((err) => this.ctx.fail(err)); }, ms);
  }

  protected formPanel(host: HTMLElement, id: string, title: string, specs: FieldSpec[], open = true): Panel {
    const p = new Panel(`${this.id}.${id}`, title, { open });
    const f = new Form(specs, (path) => this.get(path), (path, v, phase) => this.set(path, v, phase));
    p.body.appendChild(f.root);
    this.forms.push(f);
    host.appendChild(p.root);
    return p;
  }

  protected syncForms(): void { for (const f of this.forms) f.sync(); }

  private renderTemplates(): void {
    const all = [...this.builtins, ...this.userTemplates];
    patchList(this.templateList, all, {
      key: (t) => t.id,
      create: (t) => el(`<button class="fl-list-row" type="button">${icon(t.user ? 'paintbrush' : 'layers', 13)}<span>${escapeHtml(t.name)}</span></button>`),
      update: (n, t) => setText(q(n, 'span:not(.icon)'), t.name),
    });
  }

  private renderSaved(): void {
    const rows = catalog.tree.collections.filter((c) => c.kind === this.kind);
    patchList(this.savedList, rows, {
      key: (c) => String(c.id),
      create: (c) => el(`<button class="fl-list-row" type="button">${icon('collection', 13)}<span>${escapeHtml(c.name)}</span><em>${c.count}</em></button>`),
      update: (n, c) => { setText(q(n, 'span:not(.icon)'), c.name); setText(q(n, 'em'), String(c.count)); setClass(n, 'is-on', this.creation === c.id); },
    });
    setHidden(this.savedEmpty, rows.length > 0);
  }

  private onTemplateClick(e: MouseEvent): void {
    const r = (e.target as HTMLElement).closest<HTMLElement>('[data-key]');
    if (!r) return;
    const t = [...this.builtins, ...this.userTemplates].find((x) => x.id === r.dataset.key);
    if (!t) return;
    this.settings = deepMerge(this.defaults, this.keepOnTemplate(t.settings));
    this.persist();
    this.syncForms();
    this.schedule(0);
  }

  protected keepOnTemplate(s: Record<string, unknown>): Record<string, unknown> { return s; }

  private onTemplateContext(e: MouseEvent): void {
    const r = (e.target as HTMLElement).closest<HTMLElement>('[data-key]');
    const t = r ? this.userTemplates.find((x) => x.id === r.dataset.key) : undefined;
    if (!t) return;
    e.preventDefault();
    void confirmAction('Delete Template', `Delete the template "${t.name}"?`, 'Delete', true).then((ok) => {
      if (!ok) return;
      this.userTemplates = this.userTemplates.filter((x) => x.id !== t.id);
      void this.storeTemplates().then(() => this.renderTemplates());
    });
  }

  private async storeTemplates(): Promise<void> {
    const prefs = await this.ctx.api.cmd<Record<string, unknown>>('prefs.get');
    const all = { ...((prefs.templates as Record<string, unknown>) ?? {}), [this.kind]: this.userTemplates.map(({ id, name, settings }) => ({ id, name, settings })) };
    await this.ctx.api.cmd('prefs.set', { values: { templates: all } });
  }

  private async saveTemplate(): Promise<void> {
    const name = await promptName('New Template', `My ${this.label} Template`, 'Save');
    if (!name) return;
    this.userTemplates.push({ id: `u.${Date.now().toString(36)}`, name, settings: clone(this.settings), user: true });
    try { await this.storeTemplates(); this.renderTemplates(); toast(`Saved template ${name}`); } catch (err) { this.ctx.fail(err); }
  }

  private async saveCreation(): Promise<void> {
    const ids = this.ids();
    if (!ids.length) { toast(`Add photos to the filmstrip to save a ${this.label.toLowerCase()}`); return; }
    const name = await promptName(`Save ${this.label}`, `Untitled ${this.label}`, 'Save');
    if (!name) return;
    try {
      const r = await this.ctx.api.cmd<{ id: number }>('collection.create', { name, kind: this.kind, ids, settings: this.settings });
      this.creation = r.id;
      toast(`Saved ${name} with ${ids.length} ${ids.length === 1 ? 'photo' : 'photos'}`);
    } catch (err) { this.ctx.fail(err); }
  }

  private onSavedClick(e: MouseEvent): void {
    const r = (e.target as HTMLElement).closest<HTMLElement>('[data-key]');
    const c = r ? catalog.tree.collections.find((x) => String(x.id) === r.dataset.key) : undefined;
    if (!c) return;
    this.openCreation(c);
  }

  protected openCreation(c: CollectionRow): void {
    this.creation = c.id;
    if (c.settings) this.settings = deepMerge(this.defaults, c.settings as Record<string, unknown>);
    this.persist();
    this.syncForms();
    this.use = 'all';
    this.useSel.value = 'all';
    library.setSource({ kind: 'collection', id: c.id, label: c.name });
    this.renderSaved();
    this.schedule(0);
  }

  private onSavedContext(e: MouseEvent): void {
    const r = (e.target as HTMLElement).closest<HTMLElement>('[data-key]');
    const c = r ? catalog.tree.collections.find((x) => String(x.id) === r.dataset.key) : undefined;
    if (!c) return;
    e.preventDefault();
    void confirmAction(`Update ${c.name}`, `Store the current settings in "${c.name}"? Use Delete in the Library Collections panel to remove it.`, 'Update').then((ok) => {
      if (ok) void this.ctx.api.cmd('collection.update', { id: c.id, settings: this.settings }).then(() => toast(`Updated ${c.name}`), (err) => this.ctx.fail(err));
    });
  }

  protected abstract buildToolbar(bar: HTMLElement): void;
  protected abstract buildStage(stage: HTMLElement): void;
  protected abstract buildPanels(right: HTMLElement): void;
  protected abstract buildFoots(left: HTMLElement, right: HTMLElement): void;
  protected abstract refresh(): Promise<void>;
}
