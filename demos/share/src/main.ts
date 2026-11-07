import '../../../frontend/src/styles/fonts.css';
import '../../../frontend/src/styles/tokens.css';
import '../../../frontend/src/styles/lit-tokens.css';
import '../../../frontend/src/styles/shell.css';
import '../../../frontend/src/styles/panels.css';
import '../../../frontend/src/styles/dialogs.css';
import '../../../frontend/src/styles/lit-shell.css';
import '../../../frontend/src/styles/lit-library.css';
import '../../../frontend/src/styles/lit-develop.css';
import '../../../frontend/src/styles/lit-modules.css';
import '../../../frontend/src/styles/lit-control.css';
import '../../../frontend/src/styles/lit-dock.css';
import '../../../frontend/src/styles/light-mode.css';
import '../../../frontend/src/styles/scrollbars.css';
import '../../../demo/src/demo.css';
import './share.css';
import '../../../frontend/src/ui/icons-lit';
import '../../../frontend/src/modules/output/map';
import '../../../frontend/src/modules/output/book';
import '../../../frontend/src/modules/output/slideshow';
import '../../../frontend/src/modules/output/print';
import '../../../frontend/src/modules/output/web';
import type { Ctx } from '../../../frontend/src/app';
import { registerExport } from '../../../frontend/src/modules/shared/export';
import { moduleById, modules } from '../../../frontend/src/modules/registry';
import { events } from './shims/events';
import { api, errorText } from './shims/api';
import { catalog } from '../../../frontend/src/state/catalog';
import { library } from '../../../frontend/src/state/library';
import { Commands, comboOf, type Command } from '../../../frontend/src/ui/commands';
import { Dialog, anyDialogOpen } from '../../../frontend/src/ui/dialogs';
import { el, q, revealApp, setClass, setHidden } from '../../../frontend/src/ui/dom';
import { Filmstrip } from '../../../frontend/src/ui/filmstrip';
import { MenuBar, type MenuDef } from '../../../frontend/src/ui/menu';
import { Shell } from '../../../frontend/src/ui/shell';
import { THEMES, applyTheme, readChoice, setTheme, themeSwatchesHtml } from '../../../frontend/src/ui/themes';
import { toast } from '../../../frontend/src/ui/toast';
import markUrl from '../site/favicon.png';
import { LOCATIONS, MUSIC, ROWS } from './data';
import { openFiles } from './engine';
import { setBasemap } from './map-styles';
import { dataBytes, loadPack, releasePack } from './media';
import { seedCollections } from './seed';
import { rowInput, store } from './store';

const host = document.getElementById('app') as HTMLElement;
applyTheme();
const shell = new Shell(host);
setClass(q(host, '.fl-app'), 'is-booting', true);
const commands = new Commands();
const opened = new Set<string>();
let current = '';

const ctx: Ctx = {
  api: api as unknown as Ctx['api'],
  shell,
  commands,
  menus: [],
  module: () => current,
  toModule: (id) => toModule(id),
  run: (id) => { commands.run(id); },
  fail: (err, what = '') => toast(what ? `${what}: ${errorText(err)}` : errorText(err), 'error'),
};

const strip = new Filmstrip(shell.filmstrip);
strip.onOpen = (id) => { library.setActive(id, false); };

const picker = el<HTMLInputElement>('<input type="file" accept="image/jpeg,image/png,image/webp" multiple hidden>');
document.body.appendChild(picker);

function toModule(id: string): void {
  const m = moduleById(id);
  if (!m || id === current) return;
  const prev = moduleById(current);
  prev?.deactivate?.();
  current = id;
  shell.show(id);
  const first = !opened.has(id);
  opened.add(id);
  const row = catalog.tree.collections.find((c) => c.kind === id);
  if (first && row) (m as unknown as { openCreation(c: unknown): void }).openCreation(row);
  m.activate?.();
  syncSource();
}

const sourceSel = el<HTMLSelectElement>('<select class="cv-select fl-demo-source" aria-label="Photos in the filmstrip"></select>');
q(shell.filmstrip, '.fl-fs-head').insertBefore(sourceSel, q(shell.filmstrip, '.fl-fs-count').nextSibling);
sourceSel.addEventListener('change', () => {
  const v = sourceSel.value;
  if (v === 'all') library.setSource({ kind: 'all', label: 'All Photographs' });
  else {
    const c = catalog.tree.collections.find((x) => String(x.id) === v);
    if (c) library.setSource({ kind: 'collection', id: c.id, label: c.name });
  }
});

function syncSource(): void {
  const rows = catalog.tree.collections;
  const key = rows.map((c) => `${c.id}:${c.name}`).join('|');
  if (sourceSel.dataset.key !== key) {
    sourceSel.dataset.key = key;
    sourceSel.replaceChildren(el<HTMLOptionElement>('<option value="all">All Photographs</option>'), ...rows.map((c) => {
      const o = el<HTMLOptionElement>('<option></option>');
      o.value = String(c.id);
      o.textContent = `${c.name} (${c.count})`;
      return o;
    }));
  }
  const want = library.source.kind === 'collection' ? String(library.source.id) : 'all';
  if (sourceSel.value !== want) sourceSel.value = want;
}

catalog.listen(syncSource);
library.listen('list', syncSource);

function rate(n: number): void { const ids = library.selected(); if (ids.length) void api.cmd('photo.setRating', { ids, rating: n }); }
function flag(n: number): void { const ids = library.selected(); if (ids.length) void api.cmd('photo.setFlag', { ids, flag: n }); }

const cmds: Command[] = [
  { id: 'file.open', label: 'Open Photos', keys: ['Mod+O'], icon: 'importLit', run: () => picker.click() },
  { id: 'edit.selectAll', label: 'Select All', keys: ['Mod+A'], run: () => library.selectAll() },
  { id: 'edit.selectNone', label: 'Select None', keys: ['Mod+D'], run: () => library.selectNone() },
  { id: 'photo.pick', label: 'Flag as Pick', keys: ['P'], run: () => flag(1) },
  { id: 'photo.reject', label: 'Flag as Rejected', keys: ['X'], run: () => flag(-1) },
  { id: 'photo.unflag', label: 'Unflag', keys: ['U'], run: () => flag(0) },
  { id: 'photo.next', label: 'Next Photo', keys: ['Right'], run: () => library.step(1) },
  { id: 'photo.prev', label: 'Previous Photo', keys: ['Left'], run: () => library.step(-1) },
  { id: 'view.togglePanels', label: 'Hide Side Panels', keys: ['Tab'], run: () => shell.togglePanels() },
  { id: 'view.toggleFilmstrip', label: 'Show Filmstrip', keys: ['F6'], run: () => shell.toggle('is-filmstrip-hidden'), checked: () => !shell.app.classList.contains('is-filmstrip-hidden') },
  { id: 'view.filmstripCollapse', label: 'Collapse Filmstrip', keys: ['Alt+F6'], run: () => { shell.toggle('is-filmstrip-hidden', false); shell.toggle('is-filmstrip-collapsed'); } },
  { id: 'view.filmstripTop', label: 'Filmstrip at Top', run: () => { shell.toggle('is-filmstrip-hidden', false); shell.toggle('is-filmstrip-top'); } },
  { id: 'app.lights', label: 'Lights Out', keys: ['L'], run: () => shell.cycleLights() },
  { id: 'app.preferences', label: 'Appearance', run: () => openAppearance() },
  { id: 'app.about', label: 'About This Demo', run: () => openAbout() },
];
for (const n of [0, 1, 2, 3, 4, 5]) cmds.push({ id: `photo.rate${n}`, label: n ? `Rate ${n} Star${n === 1 ? '' : 's'}` : 'Clear Rating', keys: [String(n)], run: () => rate(n) });
commands.add(...cmds);

for (const m of modules()) {
  shell.addModuleTab(m.id, m.label, m.icon, `${m.label} (${m.key.replace('Mod', 'Ctrl')})`);
  commands.add({ id: `module.${m.id}`, label: m.label, keys: [m.key], run: () => toModule(m.id), checked: () => current === m.id });
  m.mount(ctx, shell.hostsFor(m.id));
}
shell.onModule = (id) => toModule(id);
registerExport(ctx);

const defs: MenuDef[] = [
  { label: 'File', items: ['file.open', 'library.export', '-', 'app.preferences'] },
  { label: 'Edit', items: ['edit.selectAll', 'edit.selectNone'] },
  { label: 'Photo', items: ['photo.pick', 'photo.reject', 'photo.unflag', '-', 'photo.rate0', 'photo.rate1', 'photo.rate2', 'photo.rate3', 'photo.rate4', 'photo.rate5', '-', 'photo.prev', 'photo.next'] },
  { label: 'View', items: ['view.togglePanels', 'view.toggleFilmstrip', 'view.filmstripCollapse', 'view.filmstripTop', '-', 'app.lights'] },
  { label: 'Window', items: modules().map((m) => `module.${m.id}`) },
  { label: 'Help', items: ['app.about'] },
];
new MenuBar(shell.menubar, commands, defs);

host.addEventListener('click', (e) => {
  const id = (e.target as HTMLElement).closest<HTMLElement>('[data-cmd]')?.dataset.cmd;
  if (id) commands.run(id);
});
for (const id of ['agent.claude', 'view.terminal', 'edit.undo', 'edit.redo']) {
  const b = host.querySelector<HTMLElement>(`[data-cmd="${id}"]`);
  if (b) setClass(b, 'hidden', true);
}
for (const img of Array.from(host.querySelectorAll<HTMLImageElement>('.fl-brand-mark img'))) img.src = markUrl;

window.addEventListener('keydown', (e) => {
  if (anyDialogOpen()) return;
  const t = e.target as HTMLElement;
  const combo = comboOf(e);
  if (t.closest('input, textarea, select, [contenteditable="true"]') && !combo.includes('Mod')) return;
  const m = moduleById(current);
  if (m?.onKey?.(e, combo)) { e.preventDefault(); return; }
  const c = commands.forEvent(e);
  if (!c || !commands.enabled(c)) return;
  e.preventDefault();
  commands.run(c.id);
});

const running = new Map<number, () => void>();
events.on('task', (e) => {
  const id = Number(e.id);
  if (e.state === 'running') {
    if (!running.has(id)) running.set(id, shell.busy(String(e.label ?? 'Working')));
    const done = Number(e.done ?? 0), total = Number(e.total ?? 0);
    shell.setHint(total ? `${String(e.label ?? '')} · ${done} of ${total}` : String(e.label ?? ''));
    return;
  }
  running.get(id)?.();
  running.delete(id);
  shell.setHint('Everything runs in this page');
});

let appearance: Dialog | null = null;
function openAppearance(): void {
  appearance ??= new Dialog('Appearance', 420);
  const d = appearance;
  d.body.textContent = '';
  d.foot.textContent = '';
  const row = el(`<div class="nm-theme-swatches">${themeSwatchesHtml()}</div>`);
  row.addEventListener('click', (e) => {
    const id = (e.target as HTMLElement).closest<HTMLElement>('[data-theme-id]')?.dataset.themeId;
    if (!id || !(id in THEMES)) return;
    setTheme(id);
    row.innerHTML = themeSwatchesHtml(id, readChoice().accentColor);
  });
  d.body.append(el('<p class="cv-note">Choose one of the fourteen Studio Dark and light profiles.</p>'), row);
  d.button('Done', 'primary', () => d.close());
  d.open();
}

let about: Dialog | null = null;
function openAbout(): void {
  about ??= new Dialog('About This Demo', 520);
  const d = about;
  d.body.textContent = '';
  d.foot.textContent = '';
  d.body.appendChild(el(`<div class="fl-about-lines">
<p>This is formlit's output side running in your browser: the Map, Book, Slideshow, Print and Web modules and the Export dialog, with no engine and no network. The windows, panels and module code are the app's own; the layout, export and metadata work is ported to run in the page.</p>
<p>Map: drag photos from the filmstrip onto the map to place them, edit coordinates, save locations (mark one private and its photos lose their location on export), load a GPX track log, search the small place list. Book, Slideshow and Print lay out the filmstrip photos and save PDF or JPEG pages. Web previews a gallery and exports it as a ZIP. Export (Shift+Ctrl+E) writes JPEG, PNG or WebP with size, sharpening, watermark and metadata options.</p>
<p>The map uses NASA Blue Marble imagery cut into tiles in the page, with a small built-in list of place names. The nineteen photographs are from Pexels and the piano piece is CC0; sources and licences are in demos/share/CREDITS.md.</p>
<p>Open your own photos with Open Photos or by dropping them on the window; a photo with a location in its EXIF appears on the map. Nothing is uploaded. Not in the demo: video export, printer output, TIFF, FTP upload, book printer packages, address lookup against a street map.</p>
</div>`));
  d.button('Close', 'primary', () => d.close());
  d.open();
}

picker.addEventListener('change', () => {
  const files = Array.from(picker.files ?? []);
  picker.value = '';
  if (files.length) void addFiles(files);
});

async function addFiles(files: File[]): Promise<void> {
  const done = shell.busy(`Opening ${files.length} photo${files.length === 1 ? '' : 's'}`);
  try {
    const ids = await openFiles(files);
    library.setSource({ kind: 'all', label: 'All Photographs' });
    await library.refresh();
    if (ids.length) library.setActive(ids[0], false);
    toast(`Opened ${ids.length} photo${ids.length === 1 ? '' : 's'}`);
  } catch (err) { ctx.fail(err); }
  done();
}

const drop = el('<div class="fl-demo-drop" hidden>Drop photos to open them here</div>');
host.appendChild(drop);
let depth = 0;
const hasFiles = (e: DragEvent): boolean => !!e.dataTransfer?.types.includes('Files');
window.addEventListener('dragenter', (e) => { if (hasFiles(e)) { depth += 1; setHidden(drop, false); } });
window.addEventListener('dragleave', (e) => { if (hasFiles(e)) { depth = Math.max(0, depth - 1); if (!depth) setHidden(drop, true); } });
window.addEventListener('dragover', (e) => { if (hasFiles(e)) e.preventDefault(); });
window.addEventListener('drop', (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  depth = 0;
  setHidden(drop, true);
  void addFiles(Array.from(e.dataTransfer?.files ?? []));
});

q(host, '.fl-identity').appendChild(el('<span class="fl-demo-badge">demo</span>'));
q(host, '.fl-status').appendChild(el('<nav class="fl-demo-links" aria-label="formlit demos"><a href="../../demo/index.html">Overview</a><i></i><a href="../develop/index.html">Develop</a><i></i><a href="./index.html" aria-current="page">Share</a></nav>'));
shell.setHint('Everything runs in this page');

async function decodeBasemap(uri: string): Promise<void> {
  const bmp = await createImageBitmap(new Blob([dataBytes(uri)], { type: 'image/jpeg' }));
  const c = document.createElement('canvas');
  c.width = bmp.width;
  c.height = bmp.height;
  const g = c.getContext('2d', { willReadFrequently: true }) as CanvasRenderingContext2D;
  g.drawImage(bmp, 0, 0);
  setBasemap(g.getImageData(0, 0, c.width, c.height));
}

function audioSeconds(url: string): Promise<number> {
  return new Promise((ok) => {
    const a = new Audio();
    a.preload = 'metadata';
    a.addEventListener('loadedmetadata', () => ok(Number.isFinite(a.duration) ? a.duration : 0));
    a.addEventListener('error', () => ok(0));
    a.src = url;
  });
}

async function openLibrary(): Promise<void> {
  const done = shell.busy('Opening the library');
  try {
    const [alps, world, more, map, music] = await Promise.all([loadPack('alps'), loadPack('world'), loadPack('more'), loadPack('map'), loadPack(MUSIC.pack)]);
    await decodeBasemap(map['bmng.jpg']);
    const packs: Record<string, Record<string, string>> = { alps, world, more };
    for (const row of ROWS) {
      const uri = packs[row.pack]?.[`${row.slug}.jpg`];
      if (uri) await store.add(rowInput(row, dataBytes(uri)));
    }
    const song = dataBytes(music[MUSIC.file]);
    const url = URL.createObjectURL(new Blob([song], { type: 'audio/ogg' }));
    store.audio.set(`${MUSIC.folder}/${MUSIC.file}`, { url, seconds: await audioSeconds(url) });
    for (const l of LOCATIONS) store.addLocation(l);
    seedCollections();
    for (const n of ['alps', 'world', 'more', 'map', MUSIC.pack]) releasePack(n);
    store.announce(Array.from(store.recs.keys()));
    await library.refresh();
    await catalog.refresh();
  } catch (err) {
    toast(`${errorText(err)}; open your own photos instead`, 'error');
  }
  done();
  library.setActive(library.ids[0] ?? null, false);
  toModule('map');
  syncSource();
  window.setTimeout(() => setClass(q(host, '.fl-app'), 'is-booting', false), 500);
}

void openLibrary();
requestAnimationFrame(() => revealApp());
