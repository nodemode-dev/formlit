import type { Ctx } from '../../app';
import { ERR, ExtensionHost, HostError, PERMISSION_WORDS, type ExtensionRecord, type Frame, type Permission, type Theme } from '../../ui/host-bridge';
import { Dialog } from '../../ui/dialogs';
import { el, escapeHtml, patchList, q, setClass, setHidden, setHtml, setText } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { toast } from '../../ui/toast';
import { pickFolder } from '../../ui/folder-picker';
import { EngineError } from '../../io/api';
import { events } from '../../io/events';
import { library } from '../../state/library';
import { VERSION } from '../../version';

interface Listing { stamp: string; changed: boolean; root?: string; extensions?: ExtensionRecord[] }
interface CatalogueRow { id: string; label: string; group: string; params: Record<string, unknown> }
interface Open { ext: ExtensionRecord; panel: string; frame: Frame; node: HTMLElement; title: HTMLElement; dialog: Dialog | null }

const PRODUCT = 'formlit';
const MANAGE_URL = `formai://extensions?product=${PRODUCT}`;
const WHAT = ['summary', 'selection', 'photo', 'catalog'];
const WINDOW_GROUPS = new Set(['terminal', 'claudecode', 'chat', 'extensions']);
const STAYS = new Set(['photo.delete', 'folder.remove', 'catalog.open', 'catalog.create', 'agents.respond']);
const SOURCE: Record<string, string> = { catalogue: 'Catalogue', sideload: 'File', development: 'Development' };
const TOKENS: Array<[string, string]> = [['--bg', '--surface-0'], ['--panel', '--surface-1'], ['--text', '--text-primary'], ['--muted', '--text-muted'], ['--accent', '--accent-color'], ['--border', '--line-1'], ['--surface', '--surface-2'], ['--text-secondary', '--text-secondary'], ['--danger', '--danger']];
const MAX_OPEN = 200 * 1024 * 1024;

const cmdId = (ext: ExtensionRecord, command: string) => `ext.${ext.id}.${command}`;
const signature = (ext: ExtensionRecord) => JSON.stringify([ext.version, ext.state, ext.reason, ext.entryUi, ext.permissions, ext.panels, ext.commands, ext.base, ext.name]);

class ExtConsent extends Dialog {
  private readonly who = el('<strong translate="no"></strong>');
  private readonly what = el('<span></span>');
  private readonly list = el('<ul class="fl-ext-consent-list"></ul>');
  private readonly allow: HTMLButtonElement;
  private resolve: ((ok: boolean) => void) | null = null;

  constructor() {
    super('Extension permissions', 440);
    q<HTMLElement>(this.scrim, '.cv-dialog').classList.add('cv-savechanges');
    const lead = el('<p class="cv-save-q"></p>');
    lead.append(this.who, this.what);
    this.body.append(lead, el('<p class="cv-note">It asks to:</p>'), this.list, el('<p class="cv-note">formlit asks again for a new version or when it asks for more. Every change it makes to the catalog can be undone; files it saves stay where you put them.</p>'));
    this.button('Not Now', 'ghost', () => this.finish(false));
    this.allow = this.button('Allow', 'primary', () => this.finish(true));
    this.onClose = () => this.finish(false);
  }

  ask(ext: ExtensionRecord): Promise<boolean> {
    setText(this.who, ext.name);
    setText(this.what, ` ${ext.version} (${SOURCE[ext.source] ?? ext.source}) wants to run in formlit.`);
    setHtml(this.list, ext.permissions.map((p) => `<li>${escapeHtml(PERMISSION_WORDS[p as Permission] ?? p)}</li>`).join(''), ext.permissions.join(','));
    this.open(this.allow);
    return new Promise((r) => { this.resolve = r; });
  }

  private finish(ok: boolean): void {
    const r = this.resolve;
    this.resolve = null;
    if (this.isOpen) this.close();
    r?.(ok);
  }
}

class Extensions {
  readonly host: ExtensionHost;
  private list: ExtensionRecord[] = [];
  private readonly seen = new Map<string, string>();
  private stamp = '';
  private root = '';
  private loaded = false;
  private readonly open = new Map<string, Open>();
  private readonly rows: HTMLElement;
  private readonly empty: HTMLElement;
  private readonly docks: HTMLElement;
  private readonly where: HTMLElement;
  private readonly hidden: HTMLElement;
  private readonly probe: HTMLElement;
  private consent: ExtConsent | null = null;
  private catalogue: CatalogueRow[] | null = null;
  private timer = 0;

  constructor(private readonly ctx: Ctx) {
    const page = ctx.shell.extPage;
    page.append(
      el(`<div class="fl-ext-bar"><span class="fl-ext-bar-title">Extensions</span>
<button class="cv-tt-btn" type="button" data-cmd="ext.reload" aria-label="Reload Extensions">${icon('refresh', 15)}</button>
<button class="cv-tt-btn" type="button" data-cmd="ext.manage" aria-label="Manage in FormPortal">${icon('externalEdit', 15)}</button>
<button class="cv-tt-btn" type="button" data-cmd="ext.close" aria-label="Close Extensions">${icon('close', 15)}</button></div>`),
      el(`<section class="fl-panel fl-ext-list"><div class="fl-panel-body"><div class="fl-ext-rows"></div><div class="fl-ext-empty" hidden><p class="cv-note">No extensions yet. Find them in FormPortal or make one with form.ext.</p><button class="cv-btn" type="button" data-cmd="ext.manage">Manage in FormPortal</button></div><p class="cv-note fl-ext-where"></p></div></section>`),
      el('<div class="fl-ext-docks"></div>'),
    );
    this.rows = q(page, '.fl-ext-rows');
    this.empty = q(page, '.fl-ext-empty');
    this.docks = q(page, '.fl-ext-docks');
    this.where = q(page, '.fl-ext-where');
    this.hidden = el('<div class="fl-ext-hidden" aria-hidden="true"></div>');
    this.probe = el('<span class="fl-ext-probe" aria-hidden="true"></span>');
    document.body.append(this.hidden, this.probe);
    this.rows.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-open]');
      const row = b?.closest<HTMLElement>('[data-ext]');
      const ext = row && this.list.find((x) => x.id === row.dataset.ext);
      if (b && ext) void this.openPanel(ext, b.dataset.open as string);
    });
    this.host = new ExtensionHost({
      product: PRODUCT,
      app: 'formlit',
      appVersion: VERSION,
      theme: () => this.theme(),
      notify: (ext, message, level) => toast(`${ext.name}: ${message}`, level === 'error' ? 'error' : 'info'),
      setTitle: (_ext, frame, title) => { const o = [...this.open.values()].find((x) => x.frame.frame === frame); if (o) this.title(o, title); },
      consent: (ext) => { this.consent ??= new ExtConsent(); return this.consent.ask(ext); },
      readDocument: (_ext, params) => this.read(params.what),
      applyDocument: (_ext, label, ops) => this.engine<{ applied: number; results: unknown[] }>('extensions.apply', { label, ops }),
      commands: () => this.commands(),
      run: async (ext, command, args) => {
        if (args !== null && typeof args !== 'object') throw new HostError(ERR.INVALID, 'args must be an object');
        const r = await this.engine<{ results: unknown[] }>('extensions.apply', { label: `${ext.name}: ${command}`, ops: [{ command, args }] });
        return r.results[0] ?? null;
      },
      openFiles: (_ext, accept, multiple) => this.openFiles(accept, multiple),
      saveFile: (ext, name, _type, data) => this.saveFile(ext, name, data),
    });
  }

  start(): void {
    void this.poll(false);
    window.setInterval(() => { if (document.hasFocus() && !document.hidden) void this.poll(false); }, 2000);
    window.addEventListener('focus', () => void this.poll(false));
    document.addEventListener('nm:ui-settings-changed', () => this.host.setTheme(this.theme()));
    let changed: { photos: Set<number>; lists: Set<string>; label: string; revision: number } | null = null;
    const flush = () => {
      if (!changed) return;
      const c = changed;
      changed = null;
      this.host.broadcast('document.changed', { revision: c.revision, photos: [...c.photos], lists: [...c.lists], label: c.label });
    };
    const note = (e: Record<string, unknown>) => {
      if (!changed) { changed = { photos: new Set(), lists: new Set(), label: '', revision: 0 }; requestAnimationFrame(flush); }
      if (typeof e.revision === 'number') changed.revision = e.revision;
      if (Array.isArray(e.ids)) for (const i of e.ids) changed.photos.add(Number(i));
      if (e.photos && typeof e.photos === 'object') for (const k of Object.keys(e.photos)) changed.photos.add(Number(k));
      if (typeof e.list === 'string') changed.lists.add(e.list);
      if (typeof e.label === 'string') changed.label = e.label;
      if (e.type === 'undo' || e.type === 'redo') changed.label = `${e.type === 'undo' ? 'Undo' : 'Redo'} ${String(e.label ?? '')}`;
    };
    for (const t of ['photos.changed', 'photos.added', 'photos.removed', 'list.changed', 'undo', 'redo']) events.on(t, note);
    library.listen('selection', () => this.host.broadcast('selection.changed', { selection: library.selected(), active: library.active }));
    let module = this.ctx.module();
    new MutationObserver(() => { const m = this.ctx.module(); if (m !== module) { module = m; this.host.broadcast('module.changed', { module: m }); } })
      .observe(this.ctx.shell.app, { attributes: true, attributeFilter: ['data-module'] });
    events.on('extensions.request', (e) => void this.answer(e));
  }

  menuItems(): string[] {
    const items: string[] = [];
    for (const ext of this.list) if (ext.state === 'ready') for (const c of ext.commands) items.push(cmdId(ext, c.id));
    return [...items, ...(items.length ? ['-'] : []), 'ext.panel', 'ext.reload', 'ext.manage'];
  }

  togglePanel(): void { this.ctx.shell.setExtensions(!this.ctx.shell.extensionsOpen()); }

  manage(): void { void this.ctx.api.cmd('extensions.manage').catch(() => { window.location.href = MANAGE_URL; }); }

  async reload(): Promise<void> {
    await this.poll(true);
    const ready = this.list.filter((x) => x.state === 'ready').length;
    toast(`${this.list.length} ${this.list.length === 1 ? 'extension' : 'extensions'}${this.list.length - ready ? `, ${this.list.length - ready} refused` : ''}`);
  }

  private async poll(force: boolean): Promise<void> {
    try {
      const r = await this.ctx.api.get<Listing>(`/api/extensions?since=${encodeURIComponent(force ? '' : this.stamp)}${force ? '&reload=true' : ''}`);
      this.stamp = r.stamp;
      if (r.changed && r.extensions) { this.root = r.root ?? ''; this.apply(r.extensions); }
    } catch {
      return;
    }
  }

  private apply(next: ExtensionRecord[]): void {
    const ids = new Set(next.map((x) => x.id));
    for (const old of this.list) {
      const now = next.find((x) => x.id === old.id);
      if (now && this.seen.get(old.id) === signature(now)) continue;
      this.close(old.id);
      for (const c of old.commands) this.ctx.commands.remove(cmdId(old, c.id));
      if (!ids.has(old.id)) this.seen.delete(old.id);
    }
    for (const ext of next) {
      if (this.seen.get(ext.id) === signature(ext) && this.list.some((x) => x.id === ext.id)) continue;
      this.seen.set(ext.id, signature(ext));
      if (ext.state !== 'ready') continue;
      for (const c of ext.commands) this.ctx.commands.add({ id: cmdId(ext, c.id), label: `${ext.name}: ${c.title}`, run: () => void this.command(ext, c.id) });
    }
    this.list = next;
    this.loaded = true;
    this.paint();
  }

  private state(ext: ExtensionRecord): string {
    if (ext.state === 'refused') return `Refused: ${ext.reason}`;
    return this.host.isGranted(ext) ? 'Ready' : 'Needs Permission';
  }

  paint(): void {
    const update = (n: HTMLElement, ext: ExtensionRecord) => {
      setText(q(n, '.fl-ext-name'), ext.name);
      setText(q(n, '.fl-ext-ver'), ext.version);
      setText(q(n, '.fl-ext-source'), SOURCE[ext.source] ?? ext.source);
      setText(q(n, '.fl-ext-desc'), ext.description ?? '');
      const chips = ext.permissions.map((p) => `<span class="fl-ext-chip">${escapeHtml(p)}</span>`).join('');
      setHtml(q(n, '.fl-ext-chips'), chips, ext.permissions.join(','));
      const st = q(n, '.fl-ext-state');
      setText(st, this.state(ext));
      setClass(st, 'is-refused', ext.state === 'refused');
      setClass(st, 'is-asking', ext.state === 'ready' && !this.host.isGranted(ext));
      const open = ext.state === 'ready' ? ext.panels.map((p) => `<button class="cv-btn" type="button" data-open="${escapeHtml(p.id)}">${escapeHtml(ext.panels.length > 1 ? `Open ${p.title}` : 'Open')}</button>`).join('') : '';
      setHtml(q(n, '.fl-ext-actions'), open, `${ext.state}:${JSON.stringify(ext.panels)}`);
      const path = q(n, '.fl-ext-path');
      setText(path, ext.source === 'development' ? ext.path ?? '' : '');
      setHidden(path, ext.source !== 'development');
    };
    patchList(this.rows, this.list, {
      key: (x) => x.id,
      create: (x) => {
        const n = el(`<div class="fl-ext-row" data-ext="${escapeHtml(x.id)}"><div class="fl-ext-row-head"><span class="fl-ext-name" translate="no"></span><span class="fl-ext-ver" translate="no"></span><em class="fl-ext-source"></em></div><div class="fl-ext-desc"></div><div class="fl-ext-chips"></div><div class="fl-ext-state"></div><div class="fl-ext-path" translate="no" hidden></div><div class="fl-ext-actions"></div></div>`);
        update(n, x);
        return n;
      },
      update,
    });
    setHidden(this.empty, !this.loaded || this.list.length > 0);
    setText(this.where, this.root ? `FormPortal folder: ${this.root}` : '');
  }

  private async command(ext: ExtensionRecord, commandId: string, args: unknown = {}): Promise<unknown> {
    const c = ext.commands.find((x) => x.id === commandId);
    if (!c) throw new HostError(ERR.NOT_FOUND, `${ext.name} has no command ${commandId}`);
    if (c.panel) {
      await this.openPanel(ext, c.panel, { reason: 'command', command: c.id, args });
      return { opened: c.panel };
    }
    try {
      const result = await this.host.runCommand(ext, c.id, args, this.hidden);
      this.paint();
      return result;
    } catch (err) {
      this.paint();
      toast(`${ext.name}: ${(err as Error).message}`, 'error');
      throw err;
    }
  }

  async openPanel(ext: ExtensionRecord, panelId: string, activation?: { reason: 'command'; command: string; args?: unknown }): Promise<void> {
    const def = ext.panels.find((p) => p.id === panelId);
    if (!def || ext.state !== 'ready') return;
    const key = `${ext.id}:${def.id}`;
    const have = this.open.get(key);
    if (have) {
      if (have.dialog) have.dialog.open();
      else { this.ctx.shell.setExtensions(true); have.node.scrollIntoView({ block: 'nearest' }); }
      if (activation) await have.frame.activate(activation).catch(() => undefined);
      return;
    }
    const frameHost = el('<div class="fl-ext-frame"></div>');
    const frame = await this.host.open(ext, frameHost, { onResize: (h) => frameHost.style.setProperty('--fl-ext-frame-h', `${Math.round(h)}px`) });
    this.paint();
    if (!frame) { toast(`${ext.name} was not allowed to run. Open it again to choose.`); return; }
    if (this.open.has(key)) { frame.dispose(); return; }
    const name = `${ext.name}: ${def.title}`;
    let node: HTMLElement;
    let dialog: Dialog | null = null;
    let title: HTMLElement;
    if (def.location === 'dialog') {
      dialog = new Dialog(name, 640);
      q<HTMLElement>(dialog.scrim, '.cv-dialog').classList.add('fl-ext-dialog');
      dialog.body.append(frameHost);
      dialog.onClose = () => this.dispose(key);
      node = dialog.scrim;
      title = q(dialog.scrim, '.cv-dialog-title');
    } else {
      node = el(`<section class="fl-panel fl-ext-dock"><div class="fl-panel-head fl-ext-dock-head"><span class="fl-panel-title" translate="no"></span><span class="fl-panel-tools"><button class="cv-tt-btn" type="button" aria-label="Close panel">${icon('close', 13)}</button></span></div></section>`);
      title = q(node, '.fl-panel-title');
      setText(title, name);
      node.append(frameHost);
      q(node, '.fl-panel-tools button').addEventListener('click', () => this.dispose(key));
      this.docks.append(node);
    }
    this.open.set(key, { ext, panel: def.id, frame, node, title, dialog });
    if (dialog) dialog.open();
    else this.ctx.shell.setExtensions(true);
    await frame.activate(activation ?? { reason: 'panel', panel: def.id }).catch(() => undefined);
  }

  private title(o: Open, text: string): void {
    const def = o.ext.panels.find((p) => p.id === o.panel);
    const full = `${o.ext.name}: ${text || def?.title || ''}`;
    if (o.dialog) o.dialog.setTitle(full); else setText(o.title, full);
  }

  private dispose(key: string): void {
    const o = this.open.get(key);
    if (!o) return;
    this.open.delete(key);
    o.frame.dispose();
    if (o.dialog) { if (o.dialog.isOpen) o.dialog.close(); o.dialog.scrim.remove(); } else o.node.remove();
  }

  private close(id: string): void {
    for (const [key, o] of [...this.open]) if (o.ext.id === id) this.dispose(key);
    this.host.disposeExtension(id);
  }

  private theme(): Theme {
    const out: Record<string, string> = {};
    for (const [name, from] of TOKENS) {
      this.probe.style.color = `var(${from})`;
      const v = getComputedStyle(this.probe).color;
      if (v) out[name] = v;
    }
    const style = getComputedStyle(document.documentElement);
    out['--radius'] = style.getPropertyValue('--radius').trim() || '6px';
    out['--font'] = style.getPropertyValue('--font-ui').trim();
    return { mode: document.body.classList.contains('theme-light') ? 'light' : 'dark', tokens: out };
  }

  private async engine<T>(id: string, params: Record<string, unknown>): Promise<T> {
    try {
      return await this.ctx.api.cmd<T>(id, params);
    } catch (err) {
      throw new HostError(ERR.REFUSED, err instanceof EngineError ? err.message : String(err));
    }
  }

  private read(what: string | undefined): Promise<unknown> {
    const w = what ?? 'summary';
    if (!WHAT.includes(w)) return Promise.reject(new HostError(ERR.INVALID, `what is one of ${WHAT.join(', ')}`));
    return this.engine('extensions.document', { what: w, ids: library.selected(), ...(library.active !== null ? { active: library.active } : {}), module: this.ctx.module(), source: library.source });
  }

  private async commands(): Promise<unknown[]> {
    this.catalogue ??= (await this.ctx.api.get<{ commands: CatalogueRow[] }>('/api/commands')).commands;
    return this.catalogue.filter((c) => !WINDOW_GROUPS.has(c.group) && !WINDOW_GROUPS.has(c.id.split('.')[0]) && !STAYS.has(c.id)).map((c) => ({ id: c.id, title: c.label, args: c.params }));
  }

  private openFiles(accept: string[], multiple: boolean): Promise<{ name: string; type: string; size: number; data: string }[]> {
    return new Promise((resolve, reject) => {
      const input = el<HTMLInputElement>('<input type="file" hidden>');
      if (accept.length) input.accept = accept.join(',');
      input.multiple = multiple;
      input.addEventListener('cancel', () => { input.remove(); reject(new HostError(ERR.CANCELLED, 'cancelled')); });
      input.addEventListener('change', async () => {
        const files = [...(input.files ?? [])];
        input.remove();
        if (!files.length) { reject(new HostError(ERR.CANCELLED, 'cancelled')); return; }
        if (files.reduce((n, f) => n + f.size, 0) > MAX_OPEN) { reject(new HostError(ERR.REFUSED, 'the files are larger than 200 MB together')); return; }
        const out = [];
        for (const f of files) {
          const bytes = new Uint8Array(await f.arrayBuffer());
          let bin = '';
          for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
          out.push({ name: f.name, type: f.type, size: f.size, data: btoa(bin) });
        }
        resolve(out);
      });
      this.hidden.append(input);
      input.click();
    });
  }

  private async saveFile(ext: ExtensionRecord, name: string, data: string): Promise<{ saved: boolean; name: string }> {
    const folder = await pickFolder('Save File', `${ext.name} saves ${name}. Choose the folder.`, '', 'Save');
    if (!folder) throw new HostError(ERR.CANCELLED, 'cancelled');
    const r = await this.engine<{ saved: boolean; name: string }>('extensions.saveFile', { folder, name, data });
    toast(`Saved ${r.name}`);
    return { saved: r.saved, name: r.name };
  }

  private async answer(e: Record<string, unknown>): Promise<void> {
    const request = String(e.request ?? '');
    const send = (body: Record<string, unknown>) => this.ctx.api.cmd('extensions.reply', { request, ...body }).catch(() => undefined);
    try {
      if (e.kind === 'list') {
        await this.poll(false);
        await send({ result: this.list.map((x) => ({ id: x.id, name: x.name, version: x.version, source: x.source, state: x.state === 'refused' ? 'refused' : this.host.isGranted(x) ? 'ready' : 'needs-permission', reason: x.reason ?? '', commands: x.commands })) });
        return;
      }
      if (e.kind === 'command') {
        await this.poll(false);
        const ext = this.list.find((x) => x.id === e.id && x.state === 'ready');
        if (!ext) throw new Error(`No ready extension ${String(e.id)}`);
        await send({ result: (await this.command(ext, String(e.command), e.args ?? {})) ?? null });
      }
    } catch (err) {
      await send({ error: (err as Error).message || String(err) });
    }
  }
}

let ext: Extensions | null = null;

export function extensionMenuItems(): string[] { return ext?.menuItems() ?? ['ext.panel', 'ext.reload', 'ext.manage']; }

export function registerExtensions(ctx: Ctx): void {
  const x = new Extensions(ctx);
  ext = x;
  ctx.commands.add(
    { id: 'ext.panel', label: 'Extensions Panel', checked: () => ctx.shell.extensionsOpen(), run: () => x.togglePanel() },
    { id: 'ext.close', label: 'Close Extensions', run: () => ctx.shell.setExtensions(false) },
    { id: 'ext.reload', label: 'Reload Extensions', run: () => void x.reload() },
    { id: 'ext.manage', label: 'Manage in FormPortal', run: () => x.manage() },
  );
  x.start();
}
