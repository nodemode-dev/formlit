import type { Ctx } from '../../app';
import { events } from '../../io/events';
import { library } from '../../state/library';
import { askForm } from '../../ui/askform';
import { confirmAction, promptName } from '../../ui/dialogs';
import { el, patchList, q, setClass, setHidden, setStyleVar, setText } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { PopupMenu } from '../../ui/menu';
import { Panel } from '../../ui/panel';
import { toast } from '../../ui/toast';
import type { CollectionRow } from '../../state/catalog';
import { whenDone } from '../shared/tasks';
import { openSmartCollection } from './smart';

interface PubCollection { id: number; name: string; depth: number; parent: number | null; set: boolean; smart: boolean; rules: unknown; new: number[]; modified: number[]; published: number[]; removed: number[] }
interface Service { id: number; kind: string; name: string; label: string; settings: Record<string, unknown>; collections: PubCollection[] }
type Row = { key: string; service: Service; col?: PubCollection };

const SVC_ITEMS = ['pub.editService', '-', 'pub.newCol', 'pub.newSmart', 'pub.newSet', '-', 'pub.removeService'];
const COL_ITEMS = ['pub.publishNow', '-', 'pub.markRepublish', 'pub.markUpToDate', '-', 'pub.editSmart', 'pub.rename', 'pub.delete'];
const SET_ITEMS = ['pub.newCol', 'pub.newSmart', 'pub.newSet', '-', 'pub.rename', 'pub.delete'];

export class PublishPanel {
  readonly panel: Panel;
  private readonly list = el('<div class="fl-pub"></div>');
  private readonly empty = el('<p class="cv-note">Publish keeps a folder or an FTP site in step with a collection: new and edited photos go out, removed ones are deleted.</p>');
  private services: Service[] = [];
  private timer = 0;
  private readonly menu: PopupMenu;
  private at: { s: Service; c?: PubCollection } | null = null;

  constructor(private readonly ctx: Ctx) {
    this.menu = new PopupMenu(ctx.commands, null, true);
    const fail = (e: unknown) => ctx.fail(e);
    const col = () => (this.at?.c && !this.at.c.set ? this.at.c : null);
    const container = () => this.at?.c ?? null;
    const sel = () => { const c = col(); const ids = library.selected().filter((id) => c && [...c.new, ...c.modified, ...c.published].includes(id)); return library.source.kind === 'collection' && library.source.id === c?.id && ids.length ? ids : undefined; };
    ctx.commands.add(
      { id: 'pub.editService', label: 'Edit Settings...', run: () => { if (this.at) void this.setup(this.at.s); }, enabled: () => !!this.at && !this.at.c },
      { id: 'pub.removeService', label: 'Remove Service...', run: () => { const s = this.at?.s; if (s) void confirmAction('Remove Publish Service', `Remove "${s.name}" and its published collections from the catalog?`, 'Remove', true).then((ok) => { if (ok) void ctx.api.cmd('publish.deleteService', { id: s.id }).catch(fail); }); }, enabled: () => !!this.at && !this.at.c },
      { id: 'pub.newCol', label: 'Create Published Collection...', run: () => { if (this.at) void this.newCollection(this.at.s, container()?.id ?? null); }, enabled: () => !!this.at && (!this.at.c || this.at.c.set) },
      { id: 'pub.newSmart', label: 'Create Published Smart Collection...', run: () => { if (this.at) openSmartCollection(ctx, null, container()?.id ?? null, { kind: 'published', service: this.at.s.id }); }, enabled: () => !!this.at && (!this.at.c || this.at.c.set) },
      { id: 'pub.newSet', label: 'Create Published Collection Set...', run: () => { if (this.at) void this.newSet(this.at.s, container()?.id ?? null); }, enabled: () => !!this.at && (!this.at.c || this.at.c.set) },
      { id: 'pub.publishNow', label: 'Publish Now', run: () => { const c = col(); if (c) void this.publish(c); }, enabled: () => !!col() },
      { id: 'pub.markRepublish', label: () => (sel() ? 'Mark Selected to Republish' : 'Mark All to Republish'), run: () => { const c = col(); if (c) void ctx.api.cmd<{ marked: number[] }>('publish.markRepublish', { collection: c.id, ids: sel() }).then((r) => toast(`Marked ${r.marked.length} to republish`), fail); }, enabled: () => !!col()?.published.length },
      { id: 'pub.markUpToDate', label: () => (sel() ? 'Mark Selected as Up-to-Date' : 'Mark All as Up-to-Date'), run: () => { const c = col(); if (c) void ctx.api.cmd<{ marked: number[] }>('publish.markUpToDate', { collection: c.id, ids: sel() }).then((r) => toast(`Marked ${r.marked.length} as up to date`), fail); }, enabled: () => { const c = col(); return !!c && c.new.length + c.modified.length > 0; } },
      { id: 'pub.editSmart', label: 'Edit Smart Collection...', run: () => { const c = col(); if (c) openSmartCollection(ctx, { id: c.id, name: c.name, kind: 'published', parent: c.parent, count: 0, target: false, rules: c.rules, settings: null, service: this.at?.s.id ?? null, cover: null } as CollectionRow); }, enabled: () => !!col()?.smart },
      { id: 'pub.rename', label: 'Rename...', run: () => { const c = container(); if (c) void promptName('Rename', c.name, 'Rename').then((name) => { if (name) void ctx.api.cmd('collection.update', { id: c.id, name }).catch(fail); }); }, enabled: () => !!container() },
      { id: 'pub.delete', label: 'Delete...', run: () => { const c = container(); if (c) void confirmAction('Delete', `Delete "${c.name}"${c.set ? ' and the published collections inside it' : ''}? Files already published stay where they are.`, 'Delete', true).then((ok) => { if (ok) void ctx.api.cmd('collection.delete', { id: c.id }).catch(fail); }); }, enabled: () => !!container() },
    );
    const add = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" aria-label="Set Up Publish Service">${icon('plus', 14)}</button>`);
    add.addEventListener('click', () => void this.setup());
    this.panel = new Panel('lib.publish', 'Publish Services', { open: false, tools: [add] });
    this.panel.body.append(this.empty, this.list);
    this.panel.onOpen = (open) => { if (open) this.load(); };
    this.list.addEventListener('click', (e) => this.onClick(e));
    this.list.addEventListener('contextmenu', (e) => this.onContext(e));
    this.list.addEventListener('dragover', (e) => {
      const r = (e.target as HTMLElement).closest<HTMLElement>('[data-col]');
      if (r && e.dataTransfer?.types.includes('application/x-formlit-ids')) { e.preventDefault(); setClass(r, 'is-drop', true); }
    });
    this.list.addEventListener('dragleave', (e) => { const r = (e.target as HTMLElement).closest<HTMLElement>('[data-col]'); if (r) setClass(r, 'is-drop', false); });
    this.list.addEventListener('drop', (e) => {
      const r = (e.target as HTMLElement).closest<HTMLElement>('[data-col]');
      if (!r) return;
      e.preventDefault();
      setClass(r, 'is-drop', false);
      const ids = JSON.parse(e.dataTransfer?.getData('application/x-formlit-ids') || '[]') as number[];
      void this.ctx.api.cmd('collection.addPhotos', { id: Number(r.dataset.col), ids }).then(() => toast(`Marked ${ids.length} to publish`), (err) => this.ctx.fail(err));
    });
    events.on('list.changed', (e) => { if (e.list === 'publish' || e.list === 'collections') this.soon(); });
    events.on('photos.changed', () => this.soon(800));
    if (this.panel.isOpen) this.load();
  }

  private soon(ms = 250): void {
    if (!this.panel.isOpen) return;
    window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => this.load(), ms);
  }

  private load(): void {
    void this.ctx.api.cmd<{ services: Service[] }>('publish.services').then((r) => { this.services = r.services; this.render(); }, () => undefined);
  }

  private render(): void {
    setHidden(this.empty, this.services.length > 0);
    const rows: Row[] = [];
    for (const s of this.services) {
      rows.push({ key: `s${s.id}`, service: s });
      for (const c of s.collections) rows.push({ key: `c${c.id}`, service: s, col: c });
    }
    const update = (n: HTMLElement, r: Row) => this.paintRow(n, r);
    patchList(this.list, rows, {
      key: (r) => r.key,
      create: (r) => {
        const n = r.col?.set
          ? el(`<div class="fl-pub-row is-col is-set" data-col="${r.col.id}" role="button" tabindex="0">${icon('collectionSet', 13)}<span class="fl-pub-name"></span><em class="fl-pub-badge"></em><button class="cv-icon-btn" type="button" data-newcol aria-label="Create Published Collection">${icon('plus', 12)}</button></div>`)
          : r.col
          ? el(`<div class="fl-pub-row is-col" data-col="${r.col.id}" role="button" tabindex="0">${icon(r.col.smart ? 'smartCollection' : 'publish', 13)}<span class="fl-pub-name"></span><em class="fl-pub-badge"></em><button class="cv-btn fl-btn-sm" type="button" data-publish>Publish</button></div>`)
          : el(`<div class="fl-pub-row is-service" data-svc="${r.service.id}">${icon(r.service.kind === 'ftp' ? 'modWeb' : 'folder', 13)}<span class="fl-pub-name"></span><em class="fl-muted"></em><button class="cv-icon-btn" type="button" data-newcol aria-label="Create Published Collection">${icon('plus', 12)}</button></div>`);
        update(n, r);
        return n;
      },
      update,
    });
  }

  private paintRow(n: HTMLElement, r: Row): void {
    if (r.col?.set) {
      setText(q(n, '.fl-pub-name'), r.col.name);
      setStyleVar(n, '--fl-depth', String(r.col.depth));
      setClass(n, 'is-active', library.source.kind === 'collection' && library.source.id === r.col.id);
    } else if (r.col) {
      const c = r.col;
      setText(q(n, '.fl-pub-name'), c.name);
      setStyleVar(n, '--fl-depth', String(c.depth));
      const pending = c.new.length + c.modified.length + c.removed.length;
      setText(q(n, '.fl-pub-badge'), pending ? `${pending} to publish` : `${c.published.length}`);
      setClass(n, 'is-pending', pending > 0);
      setClass(n, 'is-active', library.source.kind === 'collection' && library.source.id === c.id);
    } else {
      setText(q(n, '.fl-pub-name'), r.service.name);
      setText(q(n, 'em'), r.service.label);
    }
  }

  private find(id: number): { s: Service; c: PubCollection } | null {
    for (const s of this.services) for (const c of s.collections) if (c.id === id) return { s, c };
    return null;
  }

  private onClick(e: MouseEvent): void {
    const t = e.target as HTMLElement;
    const colRow = t.closest<HTMLElement>('[data-col]');
    if (colRow) {
      const f = this.find(Number(colRow.dataset.col));
      if (!f) return;
      if (t.closest('[data-publish]')) { void this.publish(f.c); return; }
      if (t.closest('[data-newcol]')) { void this.newCollection(f.s, f.c.id); return; }
      library.setSource({ kind: 'collection', id: f.c.id, label: `${f.s.name}: ${f.c.name}` });
      return;
    }
    const sRow = t.closest<HTMLElement>('.is-service');
    if (sRow && t.closest('[data-newcol]')) {
      const s = this.services.find((x) => String(x.id) === sRow.dataset.svc);
      if (s) { this.at = { s }; this.menu.setItems(['pub.newCol', 'pub.newSmart', 'pub.newSet']); const r = (t.closest('[data-newcol]') as HTMLElement).getBoundingClientRect(); this.menu.openAt(r.left, r.bottom + 2); }
    }
  }

  private onContext(e: MouseEvent): void {
    const t = e.target as HTMLElement;
    const colRow = t.closest<HTMLElement>('[data-col]');
    const sRow = t.closest<HTMLElement>('.is-service');
    if (colRow) {
      e.preventDefault();
      const f = this.find(Number(colRow.dataset.col));
      if (!f) return;
      this.at = { s: f.s, c: f.c };
      this.menu.setItems(f.c.set ? SET_ITEMS : COL_ITEMS);
      this.menu.openAt(e.clientX, e.clientY);
    } else if (sRow) {
      e.preventDefault();
      const s = this.services.find((x) => String(x.id) === sRow.dataset.svc);
      if (!s) return;
      this.at = { s };
      this.menu.setItems(SVC_ITEMS);
      this.menu.openAt(e.clientX, e.clientY);
    }
  }

  private async newSet(s: Service, parent: number | null): Promise<void> {
    const name = await promptName(`New Published Collection Set in ${s.name}`, 'Untitled Set', 'Create');
    if (!name) return;
    try { await this.ctx.api.cmd('collection.create', { name, kind: 'publishedSet', service: s.id, parent }); } catch (err) { this.ctx.fail(err); }
  }

  private async publish(c: PubCollection): Promise<void> {
    try {
      const start = await this.ctx.api.cmd<{ task: number }>('publish.run', { collection: c.id });
      const r = await whenDone(start.task);
      const done = (r.published as number[]).length, removed = (r.removed as number[]).length, failed = (r.failed as unknown[]).length;
      toast(failed ? `Published ${done}, ${failed} failed` : `Published ${done}${removed ? `, removed ${removed}` : ''} in ${c.name}`, failed ? 'error' : 'info');
    } catch (err) { this.ctx.fail(err); }
  }

  private async newCollection(s: Service, parent: number | null = null): Promise<void> {
    const name = await promptName(`New Published Collection in ${s.name}`, 'Untitled', 'Create');
    if (!name) return;
    const ids = library.selected();
    try {
      await this.ctx.api.cmd('collection.create', { name, kind: 'published', service: s.id, ids, parent });
      toast(ids.length ? `Created ${name} with ${ids.length} photos to publish` : `Created ${name}. Drag photos onto it to mark them for publishing`);
    } catch (err) { this.ctx.fail(err); }
  }

  private async setup(edit: Service | null = null): Promise<void> {
    let presets: Array<{ id: string; name: string; settings: Record<string, unknown> }> = [];
    try { presets = (await this.ctx.api.cmd<{ presets: typeof presets }>('export.presets')).presets; } catch (err) { this.ctx.fail(err); return; }
    const st = (edit?.settings ?? {}) as Record<string, unknown>;
    const options = presets.filter((p) => !/original|dng/i.test(p.id)).map((p) => [p.id, p.name] as [string, string]);
    if (edit) options.unshift(['', 'Keep current export settings']);
    const v = await askForm(edit ? `Edit ${edit.name}` : 'Set Up Publish Service', edit ? 'Changes apply the next time a collection publishes. Use Mark to Republish to send everything again with new settings.' : 'A publish service exports with a preset to a folder or FTP site, then keeps it in step.', [
      { path: 'kind', label: 'Service', kind: 'seg', options: [['folder', 'Hard Drive'], ['ftp', 'FTP Server']], show: () => !edit },
      { path: 'name', label: 'Name', kind: 'text' },
      { path: 'preset', label: 'Export with', kind: 'select', options },
      { path: 'folder', label: 'Folder', kind: 'text', placeholder: '~/Pictures/Published', show: (g) => g('kind') === 'folder' },
      { path: 'host', label: 'FTP server', kind: 'text', placeholder: 'ftp.example.com', show: (g) => g('kind') === 'ftp' },
      { path: 'user', label: 'Username', kind: 'text', show: (g) => g('kind') === 'ftp' },
      { path: 'password', label: 'Password', kind: 'password', placeholder: edit ? 'unchanged' : '', show: (g) => g('kind') === 'ftp' },
      { path: 'path', label: 'Server path', kind: 'text', placeholder: '/public_html/photos', show: (g) => g('kind') === 'ftp' },
    ], edit
      ? { kind: edit.kind, name: edit.name, preset: '', folder: String(st.folder ?? ''), host: String(st.host ?? ''), user: String(st.user ?? ''), password: '', path: String(st.path ?? '/'), tls: true }
      : { kind: 'folder', name: 'My Portfolio', preset: 'builtin.web', folder: '', host: '', user: '', password: '', path: '/', tls: true }, 'Save');
    if (!v) return;
    const preset = presets.find((p) => p.id === v.preset);
    const settings: Record<string, unknown> = { export: preset?.settings ?? st.export ?? {} };
    if (v.kind === 'ftp') { Object.assign(settings, { host: v.host, user: v.user, path: v.path || '/', tls: true, port: Number(st.port ?? 21) }); if (v.password) settings.password = v.password; }
    else if (v.folder) settings.folder = v.folder;
    try {
      if (edit) { await this.ctx.api.cmd('publish.updateService', { id: edit.id, name: v.name, settings }); toast(`Saved ${String(v.name)}`); return; }
      await this.ctx.api.cmd('publish.createService', { kind: v.kind, name: v.name, settings });
      this.panel.setOpen(true);
      this.load();
      toast(`Set up ${String(v.name)}. Press + on it to make a published collection.`);
    } catch (err) { this.ctx.fail(err); }
  }
}
