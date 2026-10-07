import { library } from '../../state/library';
import { el, q, setClass, setStyleVar } from '../../ui/dom';
import { Panel } from '../../ui/panel';
import { loadInto, thumbUrl } from '../../ui/thumbs';
import type { Viewer, Zoom } from '../../ui/viewer';

export class LibraryNavigator {
  readonly panel = new Panel('lib.navigator', 'Navigator');
  private readonly img: HTMLImageElement;
  private readonly rect: HTMLElement;
  private readonly pic: HTMLElement;
  private readonly zooms = el(`<span class="fl-nav-zooms">${[['fit', 'Fit'], ['fill', 'Fill'], ['1', '1:1'], ['2', '2:1']].map(([z, l]) => `<button type="button" data-z="${z}">${l}</button>`).join('')}</span>`);
  private shown = -1;
  private hover: number | null = null;

  constructor(private readonly loupe: Viewer, private readonly toLoupe: () => void) {
    this.panel.tools.appendChild(this.zooms);
    const box = el('<div class="fl-nav fl-lib-nav"><span class="fl-nav-pic"><img alt="" draggable="false"><span class="fl-nav-rect"></span></span></div>');
    this.pic = q(box, '.fl-nav-pic');
    this.img = q<HTMLImageElement>(box, 'img');
    this.rect = q(box, '.fl-nav-rect');
    this.panel.body.appendChild(box);
    this.zooms.addEventListener('click', (e) => {
      e.stopPropagation();
      const z = (e.target as HTMLElement).closest<HTMLElement>('[data-z]')?.dataset.z;
      if (!z) return;
      this.toLoupe();
      this.loupe.setZoom(z === 'fit' || z === 'fill' ? z : Number(z));
    });
    box.addEventListener('pointerdown', (e) => {
      if (library.active === null) return;
      const move = (ev: PointerEvent) => {
        const r = this.img.getBoundingClientRect();
        const at = { x: Math.max(0, Math.min(1, (ev.clientX - r.left) / Math.max(1, r.width))), y: Math.max(0, Math.min(1, (ev.clientY - r.top) / Math.max(1, r.height))) };
        const z: Zoom = this.loupe.zoom === 'fit' || this.loupe.zoom === 'fill' ? 1 : this.loupe.zoom;
        this.toLoupe();
        this.loupe.setZoom(z, at);
      };
      move(e);
      box.setPointerCapture(e.pointerId);
      box.addEventListener('pointermove', move);
      box.addEventListener('pointerup', () => box.removeEventListener('pointermove', move), { once: true });
    });
    this.loupe.onView = () => this.sync();
    library.listen('selection', () => this.load());
    library.listen('photos', (ids) => { if (library.active !== null && ids.includes(library.active)) this.load(true); });
    document.addEventListener('pointerover', (e) => {
      const cell = (e.target as HTMLElement).closest?.<HTMLElement>('.fl-lib-grid .fl-cell[data-id]');
      const id = cell ? Number(cell.dataset.id) : null;
      if (id === this.hover) return;
      this.hover = id;
      this.load();
    }, { passive: true });
    new ResizeObserver(() => this.sync()).observe(this.loupe.root);
    this.load();
  }

  private load(force = false): void {
    const id = this.hover ?? library.active;
    const p = library.photo(id);
    if (!p) { this.shown = -1; this.img.removeAttribute('src'); setClass(this.img, 'is-loaded', false); this.sync(); return; }
    if (force || p.id !== this.shown) { this.shown = p.id; void loadInto(this.img, thumbUrl(p)); }
    this.sync();
  }

  private sync(): void {
    const z = this.loupe.zoom;
    for (const b of Array.from(this.zooms.children) as HTMLElement[]) setClass(b, 'is-on', String(z) === b.dataset.z);
    const v = this.hover === null && this.loupe.photo?.id === this.shown ? this.loupe.visible() : null;
    setClass(this.rect, 'is-shown', !!v);
    setClass(this.pic, 'is-zoomed', !!v);
    if (!v) return;
    setStyleVar(this.rect, '--l', `${(v[0] * 100).toFixed(2)}%`);
    setStyleVar(this.rect, '--t', `${(v[1] * 100).toFixed(2)}%`);
    setStyleVar(this.rect, '--w', `${((v[2] - v[0]) * 100).toFixed(2)}%`);
    setStyleVar(this.rect, '--h', `${((v[3] - v[1]) * 100).toFixed(2)}%`);
  }
}
