import type { Ctx } from '../../app';
import { api } from '../../io/api';
import { events } from '../../io/events';
import { library } from '../../state/library';
import { promptName } from '../../ui/dialogs';
import { el, patchList, q, setClass, setHidden, setText, setTitle } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { Panel } from '../../ui/panel';
import { toast } from '../../ui/toast';

interface Named { id: number; name: string; count: number; confirmed: number; cover: number | null }
interface Unnamed { faces: number[]; count: number; cover: number; photos: number[] }
interface People { named: Named[]; unnamed: Unnamed[]; faces: number }
type Tile = { key: string; named?: Named; unnamed?: Unnamed };

const faceUrl = (fid: number | null) => (fid === null ? '' : `${api.base}/api/faces/${fid}.jpg`);

export class PeoplePanel {
  readonly panel: Panel;
  private readonly named = el('<div class="fl-faces"></div>');
  private readonly unnamed = el('<div class="fl-faces"></div>');
  private readonly namedHead = el('<div class="fl-faces-head">Named</div>');
  private readonly unnamedHead = el('<div class="fl-faces-head">Unnamed</div>');
  private readonly empty = el('<div class="fl-faces-empty"><p class="cv-note">Find Faces groups the people in your photos so you can name them once and find them anywhere.</p><button class="cv-btn fl-btn-sm" type="button" data-cmd="library.findFaces">Find Faces</button></div>');
  private data: People = { named: [], unnamed: [], faces: 0 };
  private timer = 0;
  private loaded = false;

  constructor(private readonly ctx: Ctx) {
    const find = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" data-cmd="library.findFaces" aria-label="Find Faces">${icon('search', 14)}</button>`);
    this.panel = new Panel('lib.people', 'People', { open: false, tools: [find] });
    this.panel.body.append(this.empty, this.namedHead, this.named, this.unnamedHead, this.unnamed);
    this.panel.body.classList.add('fl-people');
    this.panel.onOpen = (open) => { if (open) this.load(); };
    events.on('list.changed', (e) => { if (e.list === 'people') this.soon(); });
    library.listen('list', () => this.syncActive());
    this.panel.body.addEventListener('keydown', (e) => this.onKey(e));
    this.panel.body.addEventListener('click', (e) => this.onClick(e));
    this.panel.body.addEventListener('contextmenu', (e) => this.onContext(e));
    this.load();
  }

  private soon(): void {
    window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => this.load(), 200);
  }

  private load(): void {
    void this.ctx.api.cmd<People>('people.list').then((d) => { this.data = d; this.loaded = true; this.render(); }, () => undefined);
  }

  private render(): void {
    const d = this.data;
    setHidden(this.empty, d.faces > 0 || !this.loaded);
    setHidden(this.namedHead, d.named.length === 0);
    setHidden(this.unnamedHead, d.unnamed.length === 0);
    const tile = (t: Tile) => this.tile(t);
    const update = (n: HTMLElement, t: Tile) => this.update(n, t);
    patchList<Tile>(this.named, d.named.map((n) => ({ key: `p${n.id}`, named: n })), { key: (t) => t.key, create: tile, update });
    patchList<Tile>(this.unnamed, d.unnamed.map((u) => ({ key: `u${u.cover}`, unnamed: u })), { key: (t) => t.key, create: tile, update });
    this.syncActive();
  }

  private tile(t: Tile): HTMLElement {
    const n = el(`<div class="fl-face"><button class="fl-face-pic" type="button"><img alt="" width="64" height="64" decoding="async"><span class="fl-face-count"></span></button><button class="fl-face-ok" type="button" hidden></button><input class="fl-face-name" type="text" spellcheck="false" placeholder="Who is this?"></div>`);
    this.update(n, t);
    return n;
  }

  private update(n: HTMLElement, t: Tile): void {
    const img = q<HTMLImageElement>(n, 'img');
    const input = q<HTMLInputElement>(n, '.fl-face-name');
    const ok = q<HTMLButtonElement>(n, '.fl-face-ok');
    const src = faceUrl(t.named ? t.named.cover : t.unnamed?.cover ?? null);
    if (src && img.getAttribute('src') !== src) img.src = src;
    setClass(n, 'is-named', !!t.named);
    if (t.named) {
      const p = t.named;
      const pending = p.count - p.confirmed;
      setText(q(n, '.fl-face-count'), String(p.confirmed));
      if (document.activeElement !== input && input.value !== p.name) input.value = p.name;
      input.readOnly = true;
      setHidden(ok, pending <= 0);
      setText(ok, `+${pending}`);
      setTitle(ok, `Confirm ${pending} suggested ${pending === 1 ? 'face' : 'faces'} as ${p.name}`);
      setTitle(q(n, '.fl-face-pic'), `Show photos of ${p.name}`);
    } else if (t.unnamed) {
      setText(q(n, '.fl-face-count'), String(t.unnamed.count));
      input.readOnly = false;
      setHidden(ok, true);
      setTitle(q(n, '.fl-face-pic'), `Show ${t.unnamed.photos.length} ${t.unnamed.photos.length === 1 ? 'photo' : 'photos'}`);
    }
  }

  private item(target: EventTarget | null): Tile | null {
    const n = (target as HTMLElement | null)?.closest<HTMLElement>('.fl-face');
    const k = n?.dataset.key;
    if (!k) return null;
    if (k.startsWith('p')) { const p = this.data.named.find((x) => `p${x.id}` === k); return p ? { key: k, named: p } : null; }
    const u = this.data.unnamed.find((x) => `u${x.cover}` === k);
    return u ? { key: k, unnamed: u } : null;
  }

  private onClick(e: MouseEvent): void {
    const t = this.item(e.target);
    if (!t) return;
    const target = e.target as HTMLElement;
    if (target.closest('.fl-face-ok') && t.named) {
      void this.ctx.api.cmd<{ confirmed: number }>('people.confirm', { person: t.named.id }).then((r) => toast(`Confirmed ${r.confirmed} as ${t.named?.name ?? ''}`), (err) => this.ctx.fail(err));
      return;
    }
    if (target.closest('.fl-face-name') && t.unnamed) return;
    if (t.named) library.setSource({ kind: 'person', id: t.named.id, label: t.named.name });
    else if (t.unnamed) library.setSource({ kind: 'ids', ids: t.unnamed.photos, label: 'Unnamed Person' });
  }

  private onKey(e: KeyboardEvent): void {
    const input = (e.target as HTMLElement).closest<HTMLInputElement>('.fl-face-name');
    if (!input || input.readOnly) return;
    if (e.key === 'Escape') { input.value = ''; input.blur(); return; }
    if (e.key !== 'Enter') return;
    const t = this.item(input);
    const name = input.value.trim();
    if (!t?.unnamed || !name) return;
    e.preventDefault();
    input.blur();
    void this.ctx.api.cmd<{ photos: number[] }>('people.name', { faces: t.unnamed.faces, name }).then((r) => toast(`Named ${name} in ${r.photos.length} ${r.photos.length === 1 ? 'photo' : 'photos'}`), (err) => this.ctx.fail(err));
  }

  private onContext(e: MouseEvent): void {
    const t = this.item(e.target);
    if (!t?.named) return;
    e.preventDefault();
    const p = t.named;
    void promptName('Rename Person', p.name, 'Rename').then((name) => {
      if (name && name !== p.name) void this.ctx.api.cmd('people.rename', { person: p.id, name }).catch((err) => this.ctx.fail(err));
    });
  }

  private syncActive(): void {
    const s = library.source;
    for (const n of Array.from(this.panel.body.querySelectorAll<HTMLElement>('.fl-face'))) {
      const k = n.dataset.key ?? '';
      const on = (s.kind === 'person' && k === `p${s.id}`) || (s.kind === 'ids' && s.label === 'Unnamed Person' && k.startsWith('u') && this.data.unnamed.some((u) => `u${u.cover}` === k && u.photos.length === s.ids?.length && u.photos.every((x, i) => s.ids?.[i] === x)));
      setClass(n, 'is-active', on);
    }
  }
}
