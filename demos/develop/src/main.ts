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
import './develop.css';
import '../../../frontend/src/ui/icons-lit';
import { copySettings, exportSettings, importSettings, openExport, openInfo, openSync, pasteSettings, resetSettings } from '../../../demo/src/actions';
import { DevelopModule } from '../../../demo/src/develop-module';
import { LibraryView } from '../../../demo/src/library-view';
import { dataBytes, jpegSize, loadPack, releasePack } from '../../../demo/src/media';
import { merge, type Dev } from '../../../demo/src/engine/settings';
import { develop } from '../../../demo/src/shims/develop';
import { SOURCES, library } from '../../../demo/src/shims/library';
import { store, type PhotoInput } from '../../../demo/src/store';
import { Commands, type Command } from '../../../frontend/src/ui/commands';
import { Dialog, anyDialogOpen } from '../../../frontend/src/ui/dialogs';
import { el, q, revealApp, setClass, setHidden } from '../../../frontend/src/ui/dom';
import { MenuBar, type MenuDef } from '../../../frontend/src/ui/menu';
import { PANELS } from '../../../frontend/src/ui/panel';
import { Shell } from '../../../frontend/src/ui/shell';
import { THEMES, applyTheme, readChoice, setTheme, themeSwatchesHtml } from '../../../frontend/src/ui/themes';
import { toast } from '../../../frontend/src/ui/toast';
import markUrl from '../site/favicon.png';
import { COLLECTIONS, PHOTOS } from './data';
import { MaskOverlay } from './mask-overlay';
import { MaskPanel } from './mask-panel';
import { loadBitmaps } from './masks/eval';
import { UserPresets, pick, type UserPreset } from './user-presets';
import { VersionsPanel } from './versions-panel';

const host = document.getElementById('app') as HTMLElement;
applyTheme();
SOURCES.splice(1, 4, ...COLLECTIONS.map((c) => ({ kind: 'collection', value: c.id, label: c.name })));
const shell = new Shell(host);
setClass(q(host, '.fl-app'), 'is-booting', true);
const commands = new Commands();
let module: 'library' | 'develop' = 'develop';

shell.addModuleTab('library', 'Library', 'modLibrary', 'Library (G)');
shell.addModuleTab('develop', 'Develop', 'modDevelop', 'Develop (D)');
const libHosts = shell.hostsFor('library');
const devHosts = shell.hostsFor('develop');
const picker = el<HTMLInputElement>('<input type="file" accept="image/*,.dng,.cr2,.cr3,.nef,.arw,.orf,.rw2,.raf,.pef,.srw" multiple hidden>');
document.body.appendChild(picker);

const lib = new LibraryView({ left: libHosts.left, stage: libHosts.stage, toolbar: libHosts.toolbar, right: libHosts.right, strip: shell.filmstrip }, { openDevelop: (id) => goDevelop(id), pickFiles: () => picker.click() });
const dev = new DevelopModule({ left: devHosts.left, stage: devHosts.stage, toolbar: devHosts.toolbar, right: devHosts.right, rightFoot: devHosts.rightFoot });

const seeds: UserPreset[] = [];
const merged = (file: string): Dev => PHOTOS.find((p) => p.file === file)?.edits.reduce((a, e) => merge(a, e.patch), {} as Dev) ?? {};
seeds.push({ id: 'seed-pink', name: 'Alpine Pink Sky', group: 'My Looks', groups: ['toneCurve', 'colorMixer', 'colorGrading'], dev: pick(merged('lakes-01-walensee.jpg'), ['toneCurve', 'colorMixer', 'colorGrading']) });
seeds.push({ id: 'seed-film', name: 'Soft Film Mist', group: 'My Looks', groups: ['basicTone', 'toneCurve', 'effects'], dev: pick(merged('autumn-01-mist-branch.jpg'), ['basicTone', 'toneCurve', 'effects']) });

PANELS.get('dev.presets')?.setOpen(false, false);
new MaskPanel(devHosts.right, devHosts.right.children[1] ?? null);
const presets = new UserPresets(devHosts.left, devHosts.left.children[2] ?? null, seeds);
const versions = new VersionsPanel(devHosts.left, devHosts.left.children[3] ?? null);
new MaskOverlay(dev.view);

async function addFiles(files: File[]): Promise<void> {
  const done = shell.busy(`Opening ${files.length} photo${files.length === 1 ? '' : 's'}`);
  let last: number | null = null;
  for (const f of files) {
    try {
      const it = await store.addFile(f);
      last = it.id;
    } catch (err) {
      toast(`${f.name}: ${(err as Error).message}`, 'error');
    }
  }
  done();
  if (last !== null) {
    library.setSource({ kind: 'all', label: 'All Photographs' });
    library.setActive(last, false);
  }
}

picker.addEventListener('change', () => {
  const files = Array.from(picker.files ?? []);
  picker.value = '';
  if (files.length) void addFiles(files);
});

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

function goDevelop(id?: number): void {
  if (id !== undefined) library.setActive(id);
  const item = library.active === null ? null : store.items.get(library.active) ?? null;
  if (!item) { toast('Select a photo first', 'error'); return; }
  if (item.blob && !item.full) {
    const done = shell.busy('Opening photo');
    void store.ensureFull(item.id).then(() => { done(); if (library.active === item.id) setModule('develop'); });
    return;
  }
  void store.ensureFull(item.id);
  setModule('develop');
}

function setModule(m: 'library' | 'develop'): void {
  module = m;
  shell.show(m);
  lib.show(m === 'library');
  dev.activate(m === 'develop');
  if (m === 'develop') {
    const item = library.active === null ? null : store.items.get(library.active) ?? null;
    develop.open(item);
    dev.open();
  }
  syncStatus();
}

shell.onModule = (m) => { if (m === 'develop') goDevelop(); else setModule('library'); };

let loadingLibrary = true;

function syncStatus(): void {
  const n = library.ids.length;
  shell.setCount(loadingLibrary ? '' : `${n} photo${n === 1 ? '' : 's'}`);
  const s = library.selected().length;
  shell.setSelection(s ? `${s} selected` : '');
  shell.setHint('Everything runs in this page');
}

library.listen('list', syncStatus);
library.listen('selection', () => {
  syncStatus();
  if (module === 'develop') {
    const item = library.active === null ? null : store.items.get(library.active) ?? null;
    if (item && item.id !== develop.item?.id) {
      void store.ensureFull(item.id).then(() => {
        if (module === 'develop' && library.active === item.id && item.id !== develop.item?.id) { develop.open(item); dev.open(); }
      });
    } else if (!item && develop.item) { develop.open(null); dev.open(); }
  }
});

const active = (): ReturnType<typeof lib.current> => (module === 'develop' ? develop.item : lib.current());
const targets = (): ReturnType<typeof lib.targets> => (module === 'develop' && develop.item ? [develop.item] : lib.targets());

const cmds: Command[] = [
  { id: 'file.open', label: 'Open Photos', keys: ['Mod+O'], icon: 'importLit', run: () => picker.click() },
  { id: 'file.export', label: 'Export Selected', keys: ['Mod+Shift+E'], icon: 'exportLit', run: () => openExport(targets()) },
  { id: 'file.info', label: 'Photo Information', keys: ['Mod+I'], run: () => openInfo(active()) },
  { id: 'file.remove', label: 'Remove from Demo', keys: ['Delete'], enabled: () => library.ids.length > 0, run: () => { store.remove(library.selected()); if (module === 'develop' && !library.ids.length) setModule('library'); } },
  { id: 'edit.undo', label: 'Undo', keys: ['Mod+Z'], enabled: () => !!develop.item || !!lib.current(), run: () => { const it = active(); if (it && store.undo(it)) { if (develop.item?.id === it.id) develop.resync(); } } },
  { id: 'edit.redo', label: 'Redo', keys: ['Mod+Shift+Z'], run: () => { const it = active(); if (it && store.redo(it)) { if (develop.item?.id === it.id) develop.resync(); } } },
  { id: 'edit.copy', label: 'Copy Settings', keys: ['Mod+Shift+C'], run: () => copySettings(active()) },
  { id: 'edit.paste', label: 'Paste Settings', keys: ['Mod+Shift+V'], run: () => pasteSettings(targets()) },
  { id: 'edit.sync', label: 'Synchronize Settings', keys: ['Mod+Shift+S'], run: () => openSync(active(), lib.targets()) },
  { id: 'edit.reset', label: 'Reset Settings', run: () => resetSettings(active()) },
  { id: 'edit.save', label: 'Save Settings File', run: () => exportSettings(active()) },
  { id: 'edit.load', label: 'Load Settings File', run: () => importSettings(targets()) },
  { id: 'edit.all', label: 'Select All', keys: ['Mod+A'], run: () => library.selectAll() },
  { id: 'photo.pick', label: 'Flag as Pick', keys: ['P'], run: () => lib.flag(1) },
  { id: 'photo.reject', label: 'Flag as Rejected', keys: ['X'], run: () => lib.flag(-1) },
  { id: 'photo.unflag', label: 'Unflag', keys: ['U'], run: () => { for (const it of targets()) store.setMeta(it, { flag: 0 }); } },
  { id: 'photo.next', label: 'Next Photo', keys: ['Right'], run: () => library.step(1) },
  { id: 'photo.prev', label: 'Previous Photo', keys: ["Left"], run: () => library.step(-1) },
  { id: 'photo.virtualCopy', label: 'Create Virtual Copy', keys: ['Mod+Shift+K'], enabled: () => !!active(), run: () => versions.make() },
  { id: 'dev.newPreset', label: 'New Preset from Settings', keys: ['Mod+Shift+N'], enabled: () => module === 'develop', run: () => void presets.create() },
  { id: 'view.library', label: 'Library', keys: ['G'], checked: () => module === 'library', run: () => setModule('library') },
  { id: 'view.develop', label: 'Develop', keys: ['D'], checked: () => module === 'develop', run: () => goDevelop() },
  { id: 'view.grid', label: 'Grid', run: () => { setModule('library'); lib.setView('grid'); } },
  { id: 'view.loupe', label: 'Loupe', keys: ['E'], run: () => { setModule('library'); lib.setView('loupe'); } },
  { id: 'view.compare', label: 'Before and After', keys: ['Y'], enabled: () => module === 'develop', run: () => dev.cycleMode() },
  { id: 'view.clipping', label: 'Show Clipping', keys: ['J'], enabled: () => module === 'develop', run: () => dev.toggleClip() },
  { id: 'dev.crop', label: 'Crop and Straighten', keys: ['R'], enabled: () => module === 'develop', run: () => dev.setTool(dev.view.tool === 'crop' ? 'none' : 'crop') },
  { id: 'dev.wb', label: 'White Balance Selector', keys: ['W'], enabled: () => module === 'develop', run: () => dev.setTool(dev.view.tool === 'wb' ? 'none' : 'wb') },
  { id: 'dev.auto', label: 'Auto Tone', keys: ['Shift+A'], enabled: () => module === 'develop', run: () => dev.auto() },
  { id: 'app.lights', label: 'Lights Out', keys: ['L'], run: () => shell.cycleLights() },
  { id: 'app.preferences', label: 'Appearance', run: () => openAppearance() },
  { id: 'app.about', label: 'About This Demo', run: () => openAbout() },
  { id: 'view.panels', label: 'Hide Side Panels', keys: ['Tab'], run: () => shell.togglePanels() },
];
for (const n of [0, 1, 2, 3, 4, 5]) cmds.push({ id: `photo.rate${n}`, label: n ? `Rate ${n} Star${n === 1 ? '' : 's'}` : 'Clear Rating', keys: [String(n)], run: () => { for (const it of targets()) store.setMeta(it, { rating: n }); } });
commands.add(...cmds);

const defs: MenuDef[] = [
  { label: 'File', items: ['file.open', 'file.export', '-', 'file.info', '-', 'file.remove'] },
  { label: 'Edit', items: ['edit.undo', 'edit.redo', '-', 'edit.copy', 'edit.paste', 'edit.sync', '-', 'edit.reset', 'edit.save', 'edit.load', '-', 'edit.all'] },
  { label: 'Photo', items: ['photo.pick', 'photo.reject', 'photo.unflag', '-', 'photo.rate0', 'photo.rate1', 'photo.rate2', 'photo.rate3', 'photo.rate4', 'photo.rate5', '-', 'photo.virtualCopy', '-', 'photo.prev', 'photo.next'] },
  { label: 'Develop', items: ['dev.auto', 'dev.crop', 'dev.wb', '-', 'view.compare', 'view.clipping', '-', 'dev.newPreset'] },
  { label: 'View', items: ['view.library', 'view.develop', '-', 'view.grid', 'view.loupe', '-', 'view.panels', 'app.lights', 'app.preferences'] },
  { label: 'Help', items: ['app.about'] },
];
new MenuBar(shell.menubar, commands, defs);

host.addEventListener('click', (e) => {
  const id = (e.target as HTMLElement).closest<HTMLElement>('[data-cmd]')?.dataset.cmd;
  if (id) commands.run(id);
});
for (const id of ['agent.claude', 'view.terminal']) {
  const b = host.querySelector<HTMLElement>(`[data-cmd="${id}"]`);
  if (b) setClass(b, 'hidden', true);
}
for (const img of Array.from(host.querySelectorAll<HTMLImageElement>('.fl-brand-mark img'))) img.src = markUrl;

window.addEventListener('keydown', (e) => {
  if (anyDialogOpen()) return;
  const t = e.target as HTMLElement;
  if (t.closest('input, textarea, select') && e.key !== 'Escape') return;
  const c = commands.forEvent(e);
  if (!c) return;
  if (!commands.enabled(c)) return;
  e.preventDefault();
  commands.run(c.id);
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
  about ??= new Dialog('About This Demo', 500);
  const d = about;
  d.body.textContent = '';
  d.foot.textContent = '';
  d.body.appendChild(el(`<div class="fl-about-lines">
<p>This is the formlit Develop module running entirely in your browser, with no engine and no network. It goes deeper than the first demo: masks and local adjustments, the tone curve, the colour mixer and colour grading, presets you make, virtual copies and Before and After.</p>
<p>Masks: Sky and Subject use selections prepared in advance for the nine demo photos, so those two buttons work on those photos. Linear and radial gradients, the brush, Color Range and Luminance Range work on any photo, including your own. Edge controls snap, shift and feather a mask. Each mask carries its own sliders, applied only where the mask is.</p>
<p>The nine photographs are from Pexels, with their camera data from the photo pages. Sources and licences are in demos/develop/CREDITS.md.</p>
<p>Open your own photos with Open Photos or by dropping them on the window. Nothing is uploaded. Not in the demo: people and landscape parts, depth range, point colour, healing, and RAW demosaicing.</p>
</div>`));
  d.button('Close', 'primary', () => d.close());
  d.open();
}

setModule('develop');
q(host, '.fl-identity').appendChild(el('<span class="fl-demo-badge">demo</span>'));
q(host, '.fl-status').appendChild(el('<nav class="fl-demo-links" aria-label="formlit demos"><a href="../../demo/index.html">Overview</a><i></i><a href="./index.html" aria-current="page">Develop</a><i></i><a href="../share/index.html">Share</a></nav>'));

async function openLibrary(): Promise<void> {
  const done = shell.busy('Opening the library');
  try {
    const [pack, masks] = await Promise.all([loadPack('develop'), loadPack('masks')]);
    await loadBitmaps(masks);
    const inputs: PhotoInput[] = [];
    for (const p of PHOTOS) {
      const uri = pack[p.file];
      if (!uri) continue;
      const bytes = dataBytes(uri);
      const [width, height] = jpegSize(bytes);
      inputs.push({ name: p.file, blob: new Blob([bytes], { type: 'image/jpeg' }), bytes: bytes.buffer, width, height, collection: p.collection, keywords: p.keywords, rating: p.rating, flag: p.flag, label: p.label, edits: p.edits });
    }
    await store.addPhotos(inputs);
    releasePack('develop');
    releasePack('masks');
  } catch (err) {
    toast(`${(err as Error).message}; open your own photos instead`, 'error');
  }
  done();
  if (library.ids.length) {
    library.setActive(library.ids[0], false);
    await store.ensureFull(library.ids[0]);
    setModule('develop');
  }
  loadingLibrary = false;
  syncStatus();
  lib.setLoading(false);
  const first = dev.view.onBins;
  dev.view.onBins = (...a) => {
    first?.(...a);
    setClass(q(host, '.fl-app'), 'is-booting', false);
  };
  dev.view.schedule(false);
}

(window as unknown as Record<string, unknown>).__dbg = { develop, store, library, dev };
void openLibrary();
requestAnimationFrame(() => revealApp());
