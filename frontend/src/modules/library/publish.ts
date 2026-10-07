import type { Ctx } from '../../app';
import { events } from '../../io/events';
import { library } from '../../state/library';
import { askForm } from '../../ui/askform';
import { confirmAction, promptName } from '../../ui/dialogs';
import { el, patchList, q, setClass, setHidden, setText } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { Panel } from '../../ui/panel';
import { toast } from '../../ui/toast';
import { whenDone } from '../shared/tasks';

interface PubCollection { id: number; name: string; new: number[]; modified: number[]; published: number[]; removed: number[] }
interface Service { id: number; kind: string; name: string; label: string; settings: Record<string, unknown>; collections: PubCollection[] }
type Row = { key: string; service: Service; col?: PubCollection };

export class PublishPanel {
  readonly panel: Panel;
  private readonly list = el('<div class="fl-pub"></div>');
  private readonly empty = el('<p class="cv-note">Publish keeps a folder or an FTP site in step with a collection: new and edited photos go out, removed ones are deleted.</p>');
  private services: Service[] = [];
  private timer = 0;

  constructor(private readonly ctx: Ctx) {
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
        const n = r.col
          ? el(`<div class="fl-pub-row is-col" data-col="${r.col.id}" role="button" tabindex="0">${icon('publish', 13)}<span class="fl-pub-name"></span><em class="fl-pub-badge"></em><button class="cv-btn fl-btn-sm" type="button" data-publish>Publish</button></div>`)
          : el(`<div class="fl-pub-row is-service" data-svc="${r.service.id}">${icon(r.service.kind === 'ftp' ? 'modWeb' : 'folder', 13)}<span class="fl-pub-name"></span><em class="fl-muted"></em><button class="cv-icon-btn" type="button" data-newcol aria-label="Create Published Collection">${icon('plus', 12)}</button></div>`);
        update(n, r);
        return n;
      },
      update,
    });
  }

  private paintRow(n: HTMLElement, r: Row): void {
    if (r.col) {
      const c = r.col;
      setText(q(n, '.fl-pub-name'), c.name);
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
      library.setSource({ kind: 'collection', id: f.c.id, label: `${f.s.name}: ${f.c.name}` });
      return;
    }
    const sRow = t.closest<HTMLElement>('.is-service');
    if (sRow && t.closest('[data-newcol]')) {
      const s = this.services.find((x) => String(x.id) === sRow.dataset.svc);
      if (s) void this.newCollection(s);
    }
  }

  private onContext(e: MouseEvent): void {
    const t = e.target as HTMLElement;
    const colRow = t.closest<HTMLElement>('[data-col]');
    const sRow = t.closest<HTMLElement>('.is-service');
    if (colRow) {
      e.preventDefault();
      const f = this.find(Number(colRow.dataset.col));
      if (f) void confirmAction('Delete Published Collection', `Delete "${f.c.name}"? Files already published stay where they are.`, 'Delete', true).then((ok) => { if (ok) void this.ctx.api.cmd('collection.delete', { id: f.c.id }).catch((err) => this.ctx.fail(err)); });
    } else if (sRow) {
      e.preventDefault();
      const s = this.services.find((x) => String(x.id) === sRow.dataset.svc);
      if (s) void confirmAction('Remove Publish Service', `Remove "${s.name}" and its published collections from the catalog?`, 'Remove', true).then((ok) => { if (ok) void this.ctx.api.cmd('publish.deleteService', { id: s.id }).catch((err) => this.ctx.fail(err)); });
    }
  }

  private async publish(c: PubCollection): Promise<void> {
    try {
      const start = await this.ctx.api.cmd<{ task: number }>('publish.run', { collection: c.id });
      const r = await whenDone(start.task);
      const done = (r.published as number[]).length, removed = (r.removed as number[]).length, failed = (r.failed as unknown[]).length;
      toast(failed ? `Published ${done}, ${failed} failed` : `Published ${done}${removed ? `, removed ${removed}` : ''} in ${c.name}`, failed ? 'error' : 'info');
    } catch (err) { this.ctx.fail(err); }
  }

  private async newCollection(s: Service): Promise<void> {
    const name = await promptName(`New Published Collection in ${s.name}`, 'Untitled', 'Create');
    if (!name) return;
    const ids = library.selected();
    try {
      await this.ctx.api.cmd('collection.create', { name, kind: 'published', service: s.id, ids });
      toast(ids.length ? `Created ${name} with ${ids.length} photos to publish` : `Created ${name}. Drag photos onto it to mark them for publishing`);
    } catch (err) { this.ctx.fail(err); }
  }

  private async setup(): Promise<void> {
    let presets: Array<{ id: string; name: string; settings: Record<string, unknown> }> = [];
    try { presets = (await this.ctx.api.cmd<{ presets: typeof presets }>('export.presets')).presets; } catch (err) { this.ctx.fail(err); return; }
    const v = await askForm('Set Up Publish Service', 'A publish service exports with a preset to a folder or FTP site, then keeps it in step.', [
      { path: 'kind', label: 'Service', kind: 'seg', options: [['folder', 'Hard Drive'], ['ftp', 'FTP Server']] },
      { path: 'name', label: 'Name', kind: 'text' },
      { path: 'preset', label: 'Export with', kind: 'select', options: presets.filter((p) => !/original|dng/i.test(p.id)).map((p) => [p.id, p.name] as [string, string]) },
      { path: 'folder', label: 'Folder', kind: 'text', placeholder: '~/Pictures/Published', show: (g) => g('kind') === 'folder' },
      { path: 'host', label: 'FTP server', kind: 'text', placeholder: 'ftp.example.com', show: (g) => g('kind') === 'ftp' },
      { path: 'user', label: 'Username', kind: 'text', show: (g) => g('kind') === 'ftp' },
      { path: 'password', label: 'Password', kind: 'password', show: (g) => g('kind') === 'ftp' },
      { path: 'path', label: 'Server path', kind: 'text', placeholder: '/public_html/photos', show: (g) => g('kind') === 'ftp' },
    ], { kind: 'folder', name: 'My Portfolio', preset: 'builtin.web', folder: '', host: '', user: '', password: '', path: '/', tls: true }, 'Save');
    if (!v) return;
    const preset = presets.find((p) => p.id === v.preset);
    const settings: Record<string, unknown> = { export: preset?.settings ?? {} };
    if (v.kind === 'ftp') Object.assign(settings, { host: v.host, user: v.user, password: v.password, path: v.path || '/', tls: true, port: 21 });
    else if (v.folder) settings.folder = v.folder;
    try {
      await this.ctx.api.cmd('publish.createService', { kind: v.kind, name: v.name, settings });
      this.panel.setOpen(true);
      this.load();
      toast(`Set up ${String(v.name)}. Press + on it to make a published collection.`);
    } catch (err) { this.ctx.fail(err); }
  }
}
