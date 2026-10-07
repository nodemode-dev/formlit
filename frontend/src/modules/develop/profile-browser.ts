import type { Ctx } from '../../app';
import { api } from '../../io/api';
import { develop, type Profile } from '../../state/develop';
import { Dialog } from '../../ui/dialogs';
import { el, patchList, q, setClass, setText, setTitle, swapMedia } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { toast } from '../../ui/toast';

interface Row { key: string; head?: string; profile?: Profile }

const LONG = 240;
const PARALLEL = 2;

export class ProfileBrowser extends Dialog {
  private readonly filter = el<HTMLSelectElement>('<select class="cv-select fl-pb-filter" aria-label="Show profiles"></select>');
  private readonly grid = el('<div class="fl-pb-grid"></div>');
  private readonly status = el('<span class="fl-pb-status"></span>');
  private readonly note = el('<div class="fl-pb-note"></div>');
  private readonly urls = new Map<string, string>();
  private favorites = new Set<string>();
  private stamp = '';
  private run = 0;

  constructor(private readonly ctx: Ctx) {
    super('Profile Browser', 780);
    q<HTMLElement>(this.scrim, '.cv-dialog').classList.add('fl-pb');
    const bar = el('<div class="fl-pb-bar"><span class="fl-pb-hint">Click a profile to apply it, double-click to apply and close. The star keeps it in Favorites.</span></div>');
    bar.prepend(this.filter);
    this.body.append(bar, this.note, this.grid);
    this.status.classList.add('cv-btn-apart');
    this.foot.appendChild(this.status);
    this.button('Close', 'primary', () => this.close());
    this.filter.addEventListener('change', () => this.paint());
    this.grid.addEventListener('click', (e) => {
      const t = e.target as HTMLElement;
      const tile = t.closest<HTMLElement>('[data-pid]');
      if (!tile) return;
      if (t.closest('.fl-pb-fav')) { void this.toggleFavorite(tile.dataset.pid as string); return; }
      this.apply(tile.dataset.pid as string);
    });
    this.grid.addEventListener('dblclick', (e) => {
      const tile = (e.target as HTMLElement).closest<HTMLElement>('[data-pid]');
      if (tile && !(e.target as HTMLElement).closest('.fl-pb-fav')) this.close();
    });
    this.ready = ctx.api.cmd<Record<string, unknown>>('prefs.get').then((p) => {
      this.favorites = new Set((p.profileFavorites as string[] | undefined) ?? []);
    }, () => undefined);
  }

  private readonly ready: Promise<void>;

  show(): void {
    if (develop.id == null) { toast('Choose a photo to browse its profiles'); return; }
    void this.ready.then(() => {
      if (this.isOpen) return;
      this.fillFilter();
      this.writeNote();
      this.paint();
      this.open(this.filter);
      void this.renderAll();
    });
  }

  private profiles(): Profile[] {
    const info = develop.info;
    return info ? info.profiles.filter((p) => !p.raw || info.raw) : [];
  }

  private current(): string {
    return String((develop.settings.profile as { id?: string } | undefined)?.id ?? 'fl.color');
  }

  private writeNote(): void {
    const info = develop.info;
    const style = info?.cameraStyle ? info.profiles.find((p) => p.id === info.cameraStyle)?.name : undefined;
    const text = !info?.raw ? '' : style ? `Camera Look matches this photo as it was shot (${style}); the other camera styles are built from it.`
      : 'The camera styles assume this photo was shot in the camera\'s standard style; Camera Look always matches it as shot.';
    setText(this.note, text);
    setClass(this.note, 'is-empty', !text);
  }

  private fillFilter(): void {
    const groups = ['All', 'Favorites', 'type:color', 'type:bw', ...new Set(this.profiles().map((p) => p.group))];
    const have = Array.from(this.filter.options).map((o) => o.value).join('|');
    if (have === groups.join('|')) return;
    const keep = this.filter.value || 'All';
    const label = (g: string) => (g === 'type:color' ? 'Color profiles' : g === 'type:bw' ? 'B&W profiles' : g);
    this.filter.replaceChildren(...groups.map((g) => new Option(label(g), g)));
    this.filter.value = groups.includes(keep) ? keep : 'All';
  }

  private rows(): Row[] {
    const kind = this.filter.value.startsWith('type:') ? this.filter.value : '';
    const show = kind ? 'All' : this.filter.value || 'All';
    const list = this.profiles().filter((p) => !kind || (kind === 'type:bw') === p.mono);
    const out: Row[] = [];
    const favs = list.filter((p) => this.favorites.has(p.id));
    if ((show === 'All' || show === 'Favorites') && favs.length) {
      out.push({ key: 'h:Favorites', head: 'Favorites' });
      for (const p of favs) out.push({ key: `f:${p.id}`, profile: p });
    }
    if (show === 'Favorites') {
      if (!favs.length) out.push({ key: 'h:none', head: 'No favorites yet. Star a profile to keep it here.' });
      return out;
    }
    for (const g of new Set(list.map((p) => p.group))) {
      if (show !== 'All' && show !== g) continue;
      out.push({ key: `h:${g}`, head: g });
      for (const p of list.filter((x) => x.group === g)) out.push({ key: `p:${p.id}`, profile: p });
    }
    return out;
  }

  private paint(): void {
    const cur = this.current();
    patchList<Row>(this.grid, this.rows(), {
      key: (r) => r.key,
      create: (r) => {
        if (r.head !== undefined) { const h = el('<div class="fl-pb-head"></div>'); setText(h, r.head); return h; }
        const p = r.profile as Profile;
        const tile = el(`<button class="fl-pb-tile" type="button"><span class="fl-pb-frame"><img alt="" draggable="false"></span><span class="fl-pb-name"></span><span class="fl-pb-fav" aria-label="Favorite"><span class="fl-pb-off">${icon('star', 13)}</span><span class="fl-pb-on">${icon('starFill', 13)}</span></span></button>`);
        tile.dataset.pid = p.id;
        setText(q(tile, '.fl-pb-name'), p.name);
        this.paintTile(tile, p, cur);
        return tile;
      },
      update: (node, r) => { if (r.profile) this.paintTile(node, r.profile, cur); },
    });
  }

  private paintTile(tile: HTMLElement, p: Profile, cur: string): void {
    setClass(tile, 'is-active', p.id === cur);
    const fav = this.favorites.has(p.id);
    setClass(tile, 'is-fav', fav);
    setTitle(tile, `${p.group}: ${p.name}${p.mono ? ' · black and white' : ''}`);
    const url = this.urls.get(p.id);
    const img = q<HTMLImageElement>(tile, 'img');
    if (url && img.dataset.src !== url) {
      img.dataset.src = url;
      void swapMedia(img, url).then(() => setClass(img, 'is-loaded', true), () => setClass(img, 'is-failed', true));
    }
  }

  private async renderAll(): Promise<void> {
    const id = develop.id;
    if (id == null) return;
    const base = { ...develop.settings };
    delete (base as Record<string, unknown>).profile;
    const stamp = `${id}|${JSON.stringify(base)}`;
    if (stamp === this.stamp) return;
    this.stamp = stamp;
    const run = ++this.run;
    const amount = develop.value('profile.amount');
    const queue = this.profiles().slice();
    let done = 0;
    setText(this.status, `Rendering 0 of ${queue.length}`);
    const work = async (): Promise<void> => {
      for (let p = queue.shift(); p; p = queue.shift()) {
        if (run !== this.run || !this.isOpen) return;
        try {
          const blob = await api.blob(`/api/photos/${id}/render`, { settings: { ...base, profile: { id: p.id, amount } }, long: LONG, quality: 82 });
          if (run !== this.run) return;
          const old = this.urls.get(p.id);
          this.urls.set(p.id, URL.createObjectURL(blob));
          if (old) window.setTimeout(() => URL.revokeObjectURL(old), 2000);
          this.paint();
        } catch {
          if (run === this.run) setText(this.status, `Could not render ${p.name}`);
        }
        done += 1;
        if (run === this.run) setText(this.status, done < this.profiles().length ? `Rendering ${done} of ${this.profiles().length}` : '');
      }
    };
    await Promise.all(Array.from({ length: PARALLEL }, () => work()));
    if (run === this.run && !this.isOpen) this.stamp = '';
  }

  private apply(pid: string): void {
    const p = this.profiles().find((x) => x.id === pid);
    if (!p || pid === this.current()) return;
    develop.patch('profile', { id: pid, amount: develop.value('profile.amount') }, 'end', `Profile: ${p.name}`);
    this.paint();
  }

  private async toggleFavorite(pid: string): Promise<void> {
    if (this.favorites.has(pid)) this.favorites.delete(pid); else this.favorites.add(pid);
    this.paint();
    try {
      await this.ctx.api.cmd('prefs.set', { values: { profileFavorites: Array.from(this.favorites) } });
    } catch (err) { this.ctx.fail(err); }
  }
}

let browser: ProfileBrowser | null = null;

export function openProfileBrowser(ctx: Ctx): void {
  browser ??= new ProfileBrowser(ctx);
  browser.show();
}
