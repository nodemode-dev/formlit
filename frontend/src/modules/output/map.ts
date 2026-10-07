import type { Ctx } from '../../app';
import { events } from '../../io/events';
import { library, type Photo } from '../../state/library';
import { askForm } from '../../ui/askform';
import { confirmAction } from '../../ui/dialogs';
import { el, patchList, q, setClass, setHidden, setStyleVar, setText, setValue } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { Panel } from '../../ui/panel';
import { toast } from '../../ui/toast';
import { registerModule, type LitModule, type ModuleHosts } from '../registry';

interface Loc { id: number; name: string; lat: number; lon: number; radius: number; private: boolean; count: number }
const TILE = 256;
const OSM = (z: number, x: number, y: number) => `https://tile.openstreetmap.org/${z}/${x}/${y}.png`;
const S2 = (z: number, x: number, y: number) => `https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/${z}/${y}/${x}.jpg`;
const S2_ATTR = 'Sentinel-2 cloudless 2016 by EOX IT Services GmbH (CC BY 4.0, contains modified Copernicus Sentinel data 2016)';
const STYLES: Record<string, { label: string; url: (z: number, x: number, y: number) => string; attr: string; max: number; overlay?: (z: number, x: number, y: number) => string; cls?: string }> = {
  hybrid: { label: 'Hybrid', url: S2, overlay: OSM, attr: `${S2_ATTR} · roads © OpenStreetMap contributors`, max: 15 },
  road: { label: 'Road Map', url: OSM, attr: '© OpenStreetMap contributors', max: 19 },
  satellite: { label: 'Satellite', url: S2, attr: S2_ATTR, max: 15 },
  topo: { label: 'Terrain', url: (z, x, y) => `https://${'abc'[(x + y) % 3]}.tile.opentopomap.org/${z}/${x}/${y}.png`, attr: '© OpenStreetMap contributors, SRTM · style © OpenTopoMap (CC-BY-SA)', max: 17 },
  light: { label: 'Light', url: OSM, attr: '© OpenStreetMap contributors', max: 19, cls: 'is-light' },
  dark: { label: 'Dark', url: OSM, attr: '© OpenStreetMap contributors', max: 19, cls: 'is-dark' },
};
const VIEW_KEY = 'formlit_map_view';

function worldX(lon: number, z: number): number { return ((lon + 180) / 360) * TILE * 2 ** z; }
function worldY(lat: number, z: number): number {
  const s = Math.sin((Math.max(-85.0511, Math.min(85.0511, lat)) * Math.PI) / 180);
  return (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * TILE * 2 ** z;
}
function lonOf(x: number, z: number): number { return (x / (TILE * 2 ** z)) * 360 - 180; }
function latOf(y: number, z: number): number { const n = Math.PI - (2 * Math.PI * y) / (TILE * 2 ** z); return (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n))); }

class TileMap {
  readonly root = el('<div class="fl-map"><div class="fl-map-tiles"></div><div class="fl-map-overlay"></div><svg class="fl-map-track" aria-hidden="true"><polyline/></svg><div class="fl-map-locs"></div><div class="fl-map-marks"></div><div class="fl-map-attr"></div><div class="fl-map-zoom"><button class="cv-icon-btn" type="button" data-z="1" aria-label="Zoom In"></button><button class="cv-icon-btn" type="button" data-z="-1" aria-label="Zoom Out"></button></div></div>');
  private readonly tiles = q(this.root, '.fl-map-tiles');
  private readonly ghost = el('<div class="fl-map-ghost"></div>');
  private lastKey = '';
  private readonly marks = q(this.root, '.fl-map-marks');
  private readonly locs = q(this.root, '.fl-map-locs');
  private readonly track = q<SVGPolylineElement>(this.root, '.fl-map-track polyline');
  lat = 30;
  lon = 0;
  z = 2;
  style = 'road';
  points: Array<{ id: number; lat: number; lon: number }> = [];
  locations: Loc[] = [];
  trackPts: Array<[number, number]> = [];
  selected = new Set<number>();
  onPick: ((ids: number[], add: boolean) => void) | null = null;
  onDrop: ((lat: number, lon: number, ids: number[]) => void) | null = null;
  onMove: (() => void) | null = null;
  private raf = 0;

  constructor() {
    this.root.insertBefore(this.ghost, this.tiles);
    const zb = q(this.root, '.fl-map-zoom');
    (zb.children[0] as HTMLElement).innerHTML = icon('plus', 16);
    (zb.children[1] as HTMLElement).innerHTML = icon('minus', 16);
    zb.addEventListener('click', (e) => { const b = (e.target as HTMLElement).closest<HTMLElement>('[data-z]'); if (b) this.zoomAt(Number(b.dataset.z), this.root.clientWidth / 2, this.root.clientHeight / 2); });
    let drag: { x: number; y: number; cx: number; cy: number; moved: boolean } | null = null;
    this.root.addEventListener('pointerdown', (e) => {
      if ((e.target as HTMLElement).closest('.fl-map-zoom, .fl-mark')) return;
      drag = { x: e.clientX, y: e.clientY, cx: worldX(this.lon, this.z), cy: worldY(this.lat, this.z), moved: false };
      this.root.setPointerCapture(e.pointerId);
      setClass(this.root, 'is-dragging', true);
    });
    this.root.addEventListener('pointermove', (e) => {
      if (!drag) return;
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
      this.lon = lonOf(drag.cx - dx, this.z);
      this.lat = latOf(drag.cy - dy, this.z);
      this.schedule();
    });
    const end = () => { if (drag) { drag = null; setClass(this.root, 'is-dragging', false); this.onMove?.(); } };
    this.root.addEventListener('pointerup', end);
    this.root.addEventListener('pointercancel', end);
    this.root.addEventListener('wheel', (e) => {
      e.preventDefault();
      const r = this.root.getBoundingClientRect();
      this.zoomAt(e.deltaY < 0 ? 1 : -1, e.clientX - r.left, e.clientY - r.top);
    }, { passive: false });
    this.root.addEventListener('dblclick', (e) => {
      if ((e.target as HTMLElement).closest('.fl-mark, .fl-map-zoom')) return;
      const r = this.root.getBoundingClientRect();
      this.zoomAt(1, e.clientX - r.left, e.clientY - r.top);
    });
    this.marks.addEventListener('click', (e) => {
      const m = (e.target as HTMLElement).closest<HTMLElement>('.fl-mark');
      if (m && this.onPick) this.onPick((m.dataset.ids ?? '').split(',').map(Number), e.shiftKey || e.metaKey || e.ctrlKey);
    });
    this.root.addEventListener('dragover', (e) => { if (e.dataTransfer?.types.includes('application/x-formlit-ids')) { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; setClass(this.root, 'is-drop', true); } });
    this.root.addEventListener('dragleave', (e) => { if (e.target === this.root) setClass(this.root, 'is-drop', false); });
    this.root.addEventListener('drop', (e) => {
      setClass(this.root, 'is-drop', false);
      const raw = e.dataTransfer?.getData('application/x-formlit-ids');
      if (!raw || !this.onDrop) return;
      e.preventDefault();
      const r = this.root.getBoundingClientRect();
      const [la, lo] = this.toLatLon(e.clientX - r.left, e.clientY - r.top);
      try { this.onDrop(la, lo, JSON.parse(raw) as number[]); } catch { toast('Could not read the dragged photos', 'error'); }
    });
    new ResizeObserver(() => this.schedule()).observe(this.root);
  }

  toLatLon(px: number, py: number): [number, number] {
    const cx = worldX(this.lon, this.z) - this.root.clientWidth / 2;
    const cy = worldY(this.lat, this.z) - this.root.clientHeight / 2;
    return [latOf(cy + py, this.z), lonOf(cx + px, this.z)];
  }

  private zoomAt(d: number, px: number, py: number): void {
    const nz = Math.max(2, Math.min(STYLES[this.style].max, this.z + d));
    if (nz === this.z) return;
    const [la, lo] = this.toLatLon(px, py);
    const W = this.root.clientWidth, H = this.root.clientHeight;
    this.z = nz;
    this.lon = lonOf(worldX(lo, nz) - px + W / 2, nz);
    this.lat = latOf(worldY(la, nz) - py + H / 2, nz);
    this.schedule();
    this.onMove?.();
  }

  fit(pts: Array<{ lat: number; lon: number }>): void {
    if (!pts.length) return;
    const W = Math.max(200, this.root.clientWidth - 80), H = Math.max(200, this.root.clientHeight - 80);
    const la = pts.map((p) => p.lat), lo = pts.map((p) => p.lon);
    let z = STYLES[this.style].max - 2;
    while (z > 2) {
      const w = worldX(Math.max(...lo), z) - worldX(Math.min(...lo), z);
      const h = worldY(Math.min(...la), z) - worldY(Math.max(...la), z);
      if (w <= W && h <= H) break;
      z -= 1;
    }
    this.z = z;
    this.lon = lonOf((worldX(Math.max(...lo), z) + worldX(Math.min(...lo), z)) / 2, z);
    this.lat = latOf((worldY(Math.max(...la), z) + worldY(Math.min(...la), z)) / 2, z);
    this.schedule();
  }

  schedule(): void {
    if (this.raf) return;
    this.raf = requestAnimationFrame(() => { this.raf = 0; this.paint(); });
  }

  private paint(): void {
    const W = this.root.clientWidth, H = this.root.clientHeight;
    if (!W || !H) return;
    const z = this.z, n = 2 ** z;
    const cx = worldX(this.lon, z) - W / 2, cy = worldY(this.lat, z) - H / 2;
    const st = STYLES[this.style];
    const want: Array<{ k: string; x: number; y: number; tx: number; ty: number }> = [];
    for (let ty = Math.floor(cy / TILE); ty <= Math.floor((cy + H) / TILE); ty += 1) {
      if (ty < 0 || ty >= n) continue;
      for (let tx = Math.floor(cx / TILE); tx <= Math.floor((cx + W) / TILE); tx += 1) {
        const wx = ((tx % n) + n) % n;
        want.push({ k: `${this.style}/${z}/${wx}/${ty}/${tx}`, x: tx * TILE - cx, y: ty * TILE - cy, tx: wx, ty });
      }
    }
    if (this.lastKey !== `${this.style}/${z}`) {
      if (this.lastKey.startsWith(`${this.style}/`)) this.ghost.replaceChildren(...Array.from(this.tiles.children));
      else this.ghost.replaceChildren();
      this.lastKey = `${this.style}/${z}`;
    }
    for (const node of Array.from(this.ghost.children) as HTMLElement[]) {
      const k = 2 ** (z - Number(node.dataset.z));
      node.style.transform = `translate(${Math.round(Number(node.dataset.wx) * k - cx)}px, ${Math.round(Number(node.dataset.wy) * k - cy)}px) scale(${k})`;
    }
    const settle = () => { if (Array.from(this.tiles.children).every((i) => (i as HTMLImageElement).complete)) this.ghost.replaceChildren(); };
    patchList(this.tiles, want, {
      key: (t) => t.k,
      create: (t) => {
        const i = el<HTMLImageElement>('<img class="fl-tile" alt="" draggable="false" decoding="async">');
        i.dataset.wx = String(t.x + cx);
        i.dataset.wy = String(t.y + cy);
        i.dataset.z = String(z);
        i.addEventListener('load', () => { setClass(i, 'is-in', true); settle(); });
        i.addEventListener('error', settle);
        i.src = st.url(z, t.tx, t.ty);
        return i;
      },
      update: () => undefined,
    });
    for (const [i, node] of Array.from(this.tiles.children).entries()) {
      const t = want[i];
      if (t) (node as HTMLElement).style.transform = `translate(${Math.round(t.x)}px, ${Math.round(t.y)}px)`;
    }
    settle();
    setClass(this.root, 'is-light', st.cls === 'is-light');
    setClass(this.root, 'is-dark', st.cls === 'is-dark');
    const over = q(this.root, '.fl-map-overlay');
    const ov = st.overlay;
    patchList(over, ov ? want : [], {
      key: (t) => `o/${t.k}`,
      create: (t) => {
        const i = el<HTMLImageElement>('<img class="fl-tile" alt="" draggable="false" decoding="async">');
        i.addEventListener('load', () => setClass(i, 'is-in', true));
        i.src = (ov as (z: number, x: number, y: number) => string)(z, t.tx, t.ty);
        return i;
      },
      update: () => undefined,
    });
    for (const [i, node] of Array.from(over.children).entries()) {
      const t = want[i];
      if (t) (node as HTMLElement).style.transform = `translate(${Math.round(t.x)}px, ${Math.round(t.y)}px)`;
    }
    setText(q(this.root, '.fl-map-attr'), st.attr);
    const cell = 46;
    const groups = new Map<string, { ids: number[]; x: number; y: number; first: number }>();
    for (const p of this.points) {
      const x = worldX(p.lon, z) - cx, y = worldY(p.lat, z) - cy;
      if (x < -40 || y < -40 || x > W + 40 || y > H + 40) continue;
      const k = `${Math.floor(x / cell)}:${Math.floor(y / cell)}`;
      const g = groups.get(k);
      if (g) { g.ids.push(p.id); g.x += x; g.y += y; } else groups.set(k, { ids: [p.id], x, y, first: p.id });
    }
    const list = Array.from(groups.values()).map((g) => ({ ...g, x: g.x / g.ids.length, y: g.y / g.ids.length }));
    patchList(this.marks, list, {
      key: (g) => String(g.first),
      create: () => el(`<button class="fl-mark" type="button"><span class="fl-mark-n"></span></button>`),
      update: () => undefined,
    });
    for (const [i, node] of Array.from(this.marks.children).entries()) {
      const g = list[i];
      if (!g) continue;
      const m = node as HTMLElement;
      m.style.transform = `translate(${Math.round(g.x)}px, ${Math.round(g.y)}px)`;
      m.dataset.ids = g.ids.join(',');
      setText(q(m, '.fl-mark-n'), g.ids.length > 1 ? String(g.ids.length) : '');
      setClass(m, 'is-multi', g.ids.length > 1);
      setClass(m, 'is-on', g.ids.some((id) => this.selected.has(id)));
      m.title = g.ids.length > 1 ? `${g.ids.length} photos` : library.photo(g.ids[0])?.file ?? '';
    }
    patchList(this.locs, this.locations, {
      key: (l) => String(l.id),
      create: () => el('<div class="fl-loc"><span></span></div>'),
      update: () => undefined,
    });
    const mPerPx = (40075016.686 * Math.cos((this.lat * Math.PI) / 180)) / (TILE * n);
    for (const [i, node] of Array.from(this.locs.children).entries()) {
      const l = this.locations[i];
      if (!l) continue;
      const r = Math.max(6, (l.radius * 1000) / mPerPx);
      const x = worldX(l.lon, z) - cx, y = worldY(l.lat, z) - cy;
      const d = node as HTMLElement;
      d.style.transform = `translate(${Math.round(x - r)}px, ${Math.round(y - r)}px)`;
      setStyleVar(d, '--d', `${Math.round(r * 2)}px`);
      setText(d.firstElementChild, l.name);
      setClass(d, 'is-private', l.private);
    }
    this.track.setAttribute('points', this.trackPts.map(([la, lo]) => `${(worldX(lo, z) - cx).toFixed(1)},${(worldY(la, z) - cy).toFixed(1)}`).join(' '));
  }
}

class MapModule implements LitModule {
  readonly id = 'map';
  readonly label = 'Map';
  readonly icon = 'modMap';
  readonly key = 'Alt+Mod+3';
  readonly order = 3;
  private ctx!: Ctx;
  private hosts!: ModuleHosts;
  private readonly map = new TileMap();
  private locations: Loc[] = [];
  private active = false;
  private fitted = false;
  private gpx = '';
  private readonly locList = el('<div class="fl-list fl-out-list"></div>');
  private readonly locEmpty = el('<div class="fl-list-empty fl-muted">Press + to save the map centre as a location</div>');
  private readonly coord = el('<div class="fl-form"></div>');
  private readonly trackInfo = el('<p class="cv-note">Load a GPX track log, then tag the photos taken along it.</p>');
  private readonly status = el('<span class="fl-tb-label fl-out-status"></span>');
  private readonly search = el(`<div class="fl-map-search">${icon('search', 14)}<input class="cv-input" type="search" placeholder="Search Map" spellcheck="false" aria-label="Search Map"><div class="fl-map-results" hidden></div></div>`);
  private locFilter = '';
  private lfTimer = 0;

  private setLocFilter(mode: string): void {
    this.locFilter = mode;
    for (const b of Array.from(document.querySelectorAll<HTMLElement>('.fl-map-lf [data-lf]'))) setClass(b, 'is-on', b.dataset.lf === mode && !!mode);
    const W = this.map.root.clientWidth, H = this.map.root.clientHeight;
    const [la0, lo0] = this.map.toLatLon(0, H), [la1, lo1] = this.map.toLatLon(W, 0);
    library.setFilter({ hasGps: mode === 'tagged' ? true : mode === 'untagged' ? false : undefined, gpsBox: mode === 'visible' ? [la0, lo0, la1, lo1] : undefined });
  }

  mount(ctx: Ctx, hosts: ModuleHosts): void {
    this.ctx = ctx;
    this.hosts = hosts;
    try { const v = JSON.parse(localStorage.getItem(VIEW_KEY) || 'null') as { lat: number; lon: number; z: number; style: string } | null; if (v) { Object.assign(this.map, { lat: v.lat, lon: v.lon, z: v.z, style: STYLES[v.style] ? v.style : 'road' }); this.fitted = true; } } catch { this.fitted = false; }
    const stage = el('<div class="fl-out-stage fl-map-stage"></div>');
    stage.appendChild(this.map.root);
    hosts.stage.appendChild(stage);
    this.map.onPick = (ids, add) => {
      if (!add) library.selectNone();
      for (const id of ids) library.select(id, 'add');
      library.setActive(ids[0]);
    };
    this.map.onDrop = (lat, lon, ids) => void ctx.api.cmd('photo.setGps', { ids, lat: Number(lat.toFixed(7)), lon: Number(lon.toFixed(7)) }).then(() => toast(`Placed ${ids.length} ${ids.length === 1 ? 'photo' : 'photos'} on the map`), (e) => ctx.fail(e));
    this.map.onMove = () => {
      if (this.locFilter === 'visible') { window.clearTimeout(this.lfTimer); this.lfTimer = window.setTimeout(() => this.setLocFilter('visible'), 250); }
      try { localStorage.setItem(VIEW_KEY, JSON.stringify({ lat: this.map.lat, lon: this.map.lon, z: this.map.z, style: this.map.style })); } catch { return; }
    };
    this.toolbar();
    this.panels();
    library.listen('list', () => this.sync());
    library.listen('photos', () => this.sync());
    library.listen('selection', () => { this.sync(); this.syncCoords(); });
    events.on('list.changed', (e) => { if (e.list === 'locations') void this.loadLocations(); });
  }

  activate(): void {
    this.active = true;
    void this.loadLocations();
    this.sync();
    if (!this.fitted) { this.fitted = true; this.map.fit(this.points()); }
    this.map.schedule();
  }

  deactivate(): void { this.active = false; }

  private points(): Array<{ id: number; lat: number; lon: number }> {
    const out: Array<{ id: number; lat: number; lon: number }> = [];
    for (const id of library.ids) { const p = library.photo(id); if (p?.gps) out.push({ id, lat: p.gps[0], lon: p.gps[1] }); }
    return out;
  }

  private sync(): void {
    if (!this.active) return;
    this.map.points = this.points();
    this.map.selected = new Set(library.selected());
    this.map.schedule();
    const tagged = this.map.points.length;
    setText(this.status, `${tagged} of ${library.ids.length} photos have a location`);
  }

  private toolbar(): void {
    const bar = el(`<div class="fl-tb fl-out-tb"><span class="fl-tb-label">Map style</span><select class="cv-select" aria-label="Map style">${Object.entries(STYLES).map(([k, v]) => `<option value="${k}">${v.label}</option>`).join('')}</select><span class="fl-tb-sep"></span><span class="fl-tb-label">Location Filter</span><div class="cv-seg fl-seg-sm fl-map-lf"><button type="button" data-lf="visible" title="Show only the photos visible on the map">Visible</button><button type="button" data-lf="tagged">Tagged</button><button type="button" data-lf="untagged">Untagged</button><button type="button" data-lf="">None</button></div><span class="fl-tb-sep"></span><select class="cv-select fl-map-select" aria-label="Select photos"><option value="">Select...</option><option value="tagged">Select Tagged</option><option value="untagged">Select Untagged</option><option value="visible">Select Visible on Map</option></select><button class="cv-btn fl-btn-sm" type="button" data-fit>Fit Photos</button><span class="fl-tb-spacer"></span></div>`);
    bar.appendChild(this.status);
    const sel = q<HTMLSelectElement>(bar, 'select');
    sel.value = this.map.style;
    sel.addEventListener('change', () => { this.map.style = sel.value; this.map.z = Math.min(this.map.z, STYLES[sel.value].max); this.map.schedule(); this.map.onMove?.(); });
    this.hosts.stage.querySelector('.fl-map-stage')?.appendChild(this.search);
    const input = q<HTMLInputElement>(this.search, 'input');
    const results = q(this.search, '.fl-map-results');
    let found: Array<{ name: string; lat: number; lon: number; bbox: number[] | null }> = [];
    const go = (r: { lat: number; lon: number; bbox: number[] | null }) => {
      if (r.bbox) this.map.fit([{ lat: r.bbox[0], lon: r.bbox[2] }, { lat: r.bbox[1], lon: r.bbox[3] }]);
      else { this.map.lat = r.lat; this.map.lon = r.lon; this.map.z = Math.max(this.map.z, 14); this.map.schedule(); }
      this.map.onMove?.();
      setHidden(results, true);
    };
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { setHidden(results, true); input.blur(); return; }
      if (e.key !== 'Enter' || !input.value.trim()) return;
      e.preventDefault();
      setClass(this.search, 'is-busy', true);
      void this.ctx.api.cmd<{ results: typeof found }>('gps.search', { query: input.value }).then((r) => {
        found = r.results;
        if (found.length === 1) { go(found[0]); return; }
        patchList(results, found.map((x, i) => ({ ...x, i })), {
          key: (x) => `${x.i}|${x.name}`,
          create: (x) => { const b = el(`<button class="fl-map-result" type="button" data-i="${x.i}"></button>`); setText(b, x.name); return b; },
          update: (b, x) => { b.dataset.i = String(x.i); setText(b, x.name); },
        });
        setHidden(results, !found.length);
        if (!found.length) toast('No places found');
      }, (err) => this.ctx.fail(err)).finally(() => setClass(this.search, 'is-busy', false));
    });
    results.addEventListener('click', (e) => { const b = (e.target as HTMLElement).closest<HTMLElement>('[data-i]'); if (b) go(found[Number(b.dataset.i)]); });
    bar.addEventListener('click', (e) => {
      const t = e.target as HTMLElement;
      const lf = t.closest<HTMLElement>('[data-lf]');
      if (lf) { this.setLocFilter(lf.dataset.lf ?? ''); return; }
      if (t.closest('[data-fit]')) this.map.fit(this.points());
    });
    const pick = q<HTMLSelectElement>(bar, '.fl-map-select');
    pick.addEventListener('change', () => {
      const mode = pick.value;
      pick.value = '';
      pick.blur();
      if (!mode) return;
      const W = this.map.root.clientWidth, H = this.map.root.clientHeight;
      const [la0, lo0] = this.map.toLatLon(0, H), [la1, lo1] = this.map.toLatLon(W, 0);
      library.selectWhere((p: Photo) => mode === 'tagged' ? !!p.gps : mode === 'untagged' ? !p.gps : !!p.gps && p.gps[0] >= la0 && p.gps[0] <= la1 && p.gps[1] >= lo0 && p.gps[1] <= lo1);
    });
    this.hosts.toolbar.appendChild(bar);
  }

  private panels(): void {
    const add = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" aria-label="Save Location">${icon('plus', 14)}</button>`);
    add.addEventListener('click', () => void this.editLocation(null));
    const pl = new Panel('map.locations', 'Saved Locations', { tools: [add] });
    pl.body.append(this.locList, this.locEmpty);
    this.locList.addEventListener('click', (e) => {
      const r = (e.target as HTMLElement).closest<HTMLElement>('[data-key]');
      const l = r ? this.locations.find((x) => String(x.id) === r.dataset.key) : undefined;
      if (!l) return;
      if ((e.target as HTMLElement).closest('[data-edit]')) { void this.editLocation(l); return; }
      this.map.lat = l.lat; this.map.lon = l.lon; this.map.z = Math.max(this.map.z, l.radius < 1 ? 15 : l.radius < 10 ? 12 : 9);
      this.map.schedule(); this.map.onMove?.();
    });
    this.locList.addEventListener('contextmenu', (e) => {
      const r = (e.target as HTMLElement).closest<HTMLElement>('[data-key]');
      const l = r ? this.locations.find((x) => String(x.id) === r.dataset.key) : undefined;
      if (!l) return;
      e.preventDefault();
      void confirmAction('Delete Location', `Delete the saved location "${l.name}"? Photos keep their coordinates.`, 'Delete', true).then((ok) => { if (ok) void this.ctx.api.cmd('location.delete', { id: l.id }).catch((err) => this.ctx.fail(err)); });
    });
    this.hosts.left.appendChild(pl.root);
    const pc = new Panel('map.metadata', 'Location');
    this.coord.innerHTML = `<div class="fl-form-row"><span class="fl-form-label">Latitude</span><div class="fl-form-ctl"><input class="cv-input" type="number" step="0.000001" data-c="lat"></div></div>
<div class="fl-form-row"><span class="fl-form-label">Longitude</span><div class="fl-form-ctl"><input class="cv-input" type="number" step="0.000001" data-c="lon"></div></div>
<p class="cv-note fl-coord-note"></p>
<div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm" type="button" data-c="center">Use Map Centre</button><button class="cv-btn fl-btn-sm" type="button" data-c="clear">Remove Location</button></div>
<div class="fl-row fl-row-end"><span class="fl-muted fl-grow">Fills City, State and Country from OpenStreetMap.</span><button class="cv-btn fl-btn-sm" type="button" data-c="lookup">Look Up Address</button></div>`;
    pc.body.appendChild(this.coord);
    this.coord.addEventListener('change', (e) => {
      const i = (e.target as HTMLElement).closest<HTMLInputElement>('input[data-c]');
      if (!i) return;
      const la = Number(q<HTMLInputElement>(this.coord, '[data-c="lat"]').value), lo = Number(q<HTMLInputElement>(this.coord, '[data-c="lon"]').value);
      if (Number.isFinite(la) && Number.isFinite(lo)) void this.ctx.api.cmd('photo.setGps', { ids: library.targets(), lat: la, lon: lo }).catch((err) => this.ctx.fail(err));
    });
    this.coord.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('button[data-c]');
      const ids = library.targets();
      if (!b || !ids.length) return;
      if (b.dataset.c === 'lookup') void this.ctx.api.cmd<{ photos: number; places: number }>('gps.lookupAddress', { ids, wait: true }).then((r) => toast(`Filled addresses for ${r.photos} ${r.photos === 1 ? 'photo' : 'photos'} from ${r.places} ${r.places === 1 ? 'place' : 'places'}`), (err) => this.ctx.fail(err));
      else if (b.dataset.c === 'center') void this.ctx.api.cmd('photo.setGps', { ids, lat: Number(this.map.lat.toFixed(7)), lon: Number(this.map.lon.toFixed(7)) }).catch((err) => this.ctx.fail(err));
      else void this.ctx.api.cmd('photo.setGps', { ids }).then(() => toast(`Removed the location from ${ids.length} ${ids.length === 1 ? 'photo' : 'photos'}`), (err) => this.ctx.fail(err));
    });
    this.hosts.right.appendChild(pc.root);
    const pt = new Panel('map.tracklog', 'Track Log');
    const file = el<HTMLInputElement>('<input type="file" accept=".gpx,application/gpx+xml" hidden>');
    const body = el(`<div class="fl-form"><div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm" type="button" data-t="load">Load GPX...</button></div><div class="fl-form-row"><span class="fl-form-label">Time offset</span><div class="fl-form-ctl"><input class="cv-input" type="number" step="0.5" value="0" data-t="offset"><span class="fl-form-unit">hours from UTC</span></div></div><div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm" type="button" data-t="tag">Auto-Tag Selected</button></div></div>`);
    body.prepend(this.trackInfo);
    body.appendChild(file);
    pt.body.appendChild(body);
    const off = q<HTMLInputElement>(body, '[data-t="offset"]');
    setValue(off, String(-new Date().getTimezoneOffset() / 60));
    body.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('button[data-t]');
      if (b?.dataset.t === 'load') file.click();
      else if (b?.dataset.t === 'tag') void this.tag(Number(off.value) * 60, true);
    });
    file.addEventListener('change', () => {
      const f = file.files?.[0];
      if (!f) return;
      void f.text().then((t) => { this.gpx = t; return this.tag(Number(off.value) * 60, false); });
      file.value = '';
    });
    this.hosts.right.appendChild(pt.root);
    this.syncCoords();
  }

  private async tag(offsetMinutes: number, apply: boolean): Promise<void> {
    if (!this.gpx) { toast('Load a GPX track log first'); return; }
    const ids = apply ? library.targets() : library.ids.slice();
    if (!ids.length) { toast('Select the photos to tag'); return; }
    try {
      const r = await this.ctx.api.cmd<{ count: number; points: number; track: Array<[number, number]>; start: string; end: string }>('gps.tracklog', { ids, gpx: this.gpx, offsetMinutes, apply });
      this.map.trackPts = r.track;
      this.map.fit(r.track.map(([lat, lon]) => ({ lat, lon })));
      setText(this.trackInfo, `${r.points} points, ${r.start.slice(0, 16).replace('T', ' ')} to ${r.end.slice(11, 16)} UTC. ${apply ? `Tagged ${r.count} ${r.count === 1 ? 'photo' : 'photos'}.` : `${r.count} of the filmstrip photos fall on the track.`}`);
    } catch (err) { this.ctx.fail(err); }
  }

  private syncCoords(): void {
    const id = library.active ?? library.selected()[0];
    const p = id !== undefined && id !== null ? library.photo(id) : undefined;
    setValue(q<HTMLInputElement>(this.coord, '[data-c="lat"]'), p?.gps ? p.gps[0].toFixed(6) : '');
    setValue(q<HTMLInputElement>(this.coord, '[data-c="lon"]'), p?.gps ? p.gps[1].toFixed(6) : '');
    const n = library.targets().length;
    setText(q(this.coord, '.fl-coord-note'), !n ? 'Select photos, then drag them onto the map or type coordinates.' : p?.gps ? `${n > 1 ? `${n} photos selected. ` : ''}Edits apply to every selected photo.` : `${n} ${n === 1 ? 'photo has' : 'photos have'} no location yet. Drag from the filmstrip onto the map.`);
  }

  private async loadLocations(): Promise<void> {
    try {
      const r = await this.ctx.api.cmd<{ locations: Loc[] }>('location.list');
      this.locations = r.locations;
      this.map.locations = r.locations;
      this.map.schedule();
      const update = (n: HTMLElement, l: Loc) => { setText(q(n, 'span:not(.icon)'), `${l.name}${l.private ? ' (private)' : ''}`); setText(q(n, 'em'), String(l.count)); };
      patchList(this.locList, r.locations, {
        key: (l) => String(l.id),
        create: (l) => { const n = el(`<div class="fl-list-row" role="button" tabindex="0">${icon('pin', 13)}<span></span><em></em><button class="cv-icon-btn" type="button" data-edit aria-label="Edit">${icon('settings', 12)}</button></div>`); update(n, l); return n; },
        update,
      });
      setHidden(this.locEmpty, r.locations.length > 0);
    } catch (err) { this.ctx.fail(err); }
  }

  private async editLocation(l: Loc | null): Promise<void> {
    const v = await askForm(l ? 'Edit Location' : 'New Location', l ? '' : 'Saves the centre of the map. Photos inside the radius count toward it.', [
      { path: 'name', label: 'Name', kind: 'text' },
      { path: 'radius', label: 'Radius', kind: 'number', min: 0.01, step: 0.1, unit: 'km' },
      { path: 'private', label: 'Private', kind: 'check' },
      { path: '', label: 'Private locations are removed from exported photos.', kind: 'note' },
    ], { name: l?.name ?? 'New Location', radius: l?.radius ?? 0.5, private: l?.private ?? false }, l ? 'Save' : 'Create');
    if (!v) return;
    try {
      await this.ctx.api.cmd('location.save', { id: l?.id, name: v.name, lat: l?.lat ?? this.map.lat, lon: l?.lon ?? this.map.lon, radius: Number(v.radius), private: !!v.private });
    } catch (err) { this.ctx.fail(err); }
  }
}

registerModule(new MapModule());
