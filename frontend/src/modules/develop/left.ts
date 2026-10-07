import type { Ctx } from '../../app';
import { develop } from '../../state/develop';
import { library } from '../../state/library';
import { promptName, confirmAction } from '../../ui/dialogs';
import { el, escapeHtml, patchList, q, setClass, setStyleVar, setText, swapMedia } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { PopupMenu } from '../../ui/menu';
import { Panel } from '../../ui/panel';
import { thumbUrl, loadInto } from '../../ui/thumbs';
import { Tree, type TreeNode } from '../../ui/tree';
import { toast } from '../../ui/toast';
import { outputUrl } from '../shared/tasks';
import { PresetDialog } from './preset-dialog';
import type { DevelopView } from './view';

interface Preset { id: string; group: string; name: string; builtin: boolean; favorite: boolean }
interface Step { id: number; name: string; time: string }
interface Snap { id: number; name: string; time: string }

export class LeftPanels {
  private readonly navImg: HTMLImageElement;
  private readonly navBox: HTMLElement;
  private readonly navRect: HTMLElement;
  private readonly presets: Tree;
  private readonly history: HTMLElement;
  private readonly snaps: HTMLElement;
  private readonly amount: HTMLInputElement;
  private presetList: Preset[] = [];
  private menu: PopupMenu;
  private ctxPreset: Preset | null = null;
  private ctxSnap: number | null = null;
  private ctxStep: number | null = null;
  private presetDialog: PresetDialog | null = null;
  private hoverTimer = 0;
  private hoverSeq = 0;
  private hoverUrl = '';
  private histTimer = 0;

  constructor(private readonly ctx: Ctx, host: HTMLElement, private readonly view: DevelopView) {
    const pNav = new Panel('dev.navigator', 'Navigator');
    const zooms = el(`<span class="fl-nav-zooms">${[['fit', 'Fit'], ['fill', 'Fill'], ['1', '100%'], ['2', '200%']].map(([z, l]) => `<button type="button" data-z="${z}">${l}</button>`).join('')}</span>`);
    zooms.addEventListener('click', (e) => {
      e.stopPropagation();
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-z]');
      if (!b) return;
      const z = b.dataset.z as string;
      view.setZoom(z === 'fit' || z === 'fill' ? z : Number(z));
    });
    pNav.tools.appendChild(zooms);
    this.navBox = el('<div class="fl-nav"><img alt="" draggable="false"><div class="fl-nav-rect"></div></div>');
    this.navImg = q<HTMLImageElement>(this.navBox, 'img');
    this.navRect = q(this.navBox, '.fl-nav-rect');
    this.navBox.addEventListener('pointerdown', (e) => {
      const move = (ev: PointerEvent) => {
        const r = this.navImg.getBoundingClientRect();
        const at = { x: Math.max(0, Math.min(1, (ev.clientX - r.left) / r.width)), y: Math.max(0, Math.min(1, (ev.clientY - r.top) / r.height)) };
        view.setZoom(view.zoom === 'fit' ? 1 : view.zoom, at);
      };
      move(e);
      this.navBox.setPointerCapture(e.pointerId);
      this.navBox.addEventListener('pointermove', move);
      this.navBox.addEventListener('pointerup', () => this.navBox.removeEventListener('pointermove', move), { once: true });
    });
    pNav.body.appendChild(this.navBox);

    const pPresets = new Panel('dev.presets', 'Presets');
    const addPreset = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" data-cmd="develop.newPreset" aria-label="New Preset">${icon('plus', 14)}</button>`);
    pPresets.tools.appendChild(addPreset);
    this.amount = el<HTMLInputElement>('<input class="cv-slider" type="range" min="0" max="200" step="1" value="100" aria-label="Preset amount">');
    const amountRow = el('<div class="fl-row"><span class="fl-row-label">Amount</span><span class="fl-preset-amt">100</span></div>');
    amountRow.insertBefore(this.amount, amountRow.lastChild);
    this.amount.addEventListener('input', () => setText(q(amountRow, '.fl-preset-amt'), this.amount.value));
    this.presets = new Tree({
      id: 'presets', empty: 'No presets',
      onPick: (n) => { const p = n.data as Preset | undefined; if (p) void this.applyPreset(p); },
      onContext: (n, e) => { const p = n.data as Preset | undefined; if (!p) return; this.ctxPreset = p; this.menu.setItems(['dev.presetFavorite', 'dev.presetUpdate', 'dev.presetRename', 'dev.presetExport', '-', 'develop.newPreset', 'preset.importFiles', '-', 'dev.presetDelete']); this.menu.openAt(e.clientX, e.clientY); },
    });
    pPresets.body.append(amountRow, this.presets.root);
    this.presets.root.addEventListener('pointerover', (e) => {
      const key = (e.target as HTMLElement).closest<HTMLElement>('.fl-tree-row')?.dataset.key ?? '';
      const p = /^[pf]:/.test(key) ? this.presetList.find((x) => x.id === key.slice(2)) : undefined;
      window.clearTimeout(this.hoverTimer);
      if (p) this.hoverTimer = window.setTimeout(() => void this.previewPreset(p), 140);
      else this.endPreview();
    });
    this.presets.root.addEventListener('pointerleave', () => { window.clearTimeout(this.hoverTimer); this.endPreview(); });

    const pSnap = new Panel('dev.snapshots', 'Snapshots', { open: false });
    const addSnap = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" data-cmd="develop.snapshot" aria-label="New Snapshot">${icon('plus', 14)}</button>`);
    pSnap.tools.appendChild(addSnap);
    this.snaps = el('<div class="fl-list"></div>');
    this.snaps.addEventListener('click', (e) => {
      const row = (e.target as HTMLElement).closest<HTMLElement>('[data-snap]');
      if (!row) return;
      if ((e.target as HTMLElement).closest('[data-del]')) { void this.ctx.api.cmd('snapshot.delete', { snapshot: Number(row.dataset.snap) }).then(() => this.loadSnaps()); return; }
      void develop.flush().then(() => this.ctx.api.cmd('snapshot.apply', { snapshot: Number(row.dataset.snap) })).catch((err) => this.ctx.fail(err));
    });
    this.snaps.addEventListener('contextmenu', (e) => {
      const row = (e.target as HTMLElement).closest<HTMLElement>('[data-snap]');
      if (!row) return;
      e.preventDefault();
      this.ctxSnap = Number(row.dataset.snap);
      this.menu.setItems(['dev.snapUpdate', 'dev.snapRename', 'dev.snapBefore', '-', 'dev.snapDelete']);
      this.menu.openAt(e.clientX, e.clientY);
    });
    pSnap.body.appendChild(this.snaps);

    const pHist = new Panel('dev.history', 'History');
    const clear = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" aria-label="Clear History">${icon('close', 13)}</button>`);
    clear.addEventListener('click', async () => {
      if (develop.id !== null && await confirmAction('Clear History', 'Clear the history of this photo? The current settings stay.', 'Clear')) {
        await this.ctx.api.cmd('develop.historyClear', { id: develop.id });
        this.loadHistory();
      }
    });
    pHist.tools.appendChild(clear);
    this.history = el('<div class="fl-list fl-history"></div>');
    this.history.addEventListener('click', (e) => {
      const row = (e.target as HTMLElement).closest<HTMLElement>('[data-step]');
      if (row && develop.id !== null) void develop.flush().then(() => this.ctx.api.cmd('develop.historyRestore', { id: develop.id, step: Number(row.dataset.step) })).catch((err) => this.ctx.fail(err));
    });
    this.history.addEventListener('contextmenu', (e) => {
      const row = (e.target as HTMLElement).closest<HTMLElement>('[data-step]');
      if (!row) return;
      e.preventDefault();
      this.ctxStep = Number(row.dataset.step);
      this.menu.setItems(['dev.histBefore', '-', 'develop.copyAfterToBefore', 'develop.resetBefore']);
      this.menu.openAt(e.clientX, e.clientY);
    });
    pHist.body.appendChild(this.history);

    host.append(pNav.root, pPresets.root, pSnap.root, pHist.root);
    this.menu = new PopupMenu(ctx.commands, null, true);
    this.commands();
    develop.listen((why) => {
      if (why === 'photo' || why === 'reload') { this.loadHistory(); this.loadSnaps(); this.nav(); }
      if (why === 'edit') { window.clearTimeout(this.histTimer); this.histTimer = window.setTimeout(() => this.loadHistory(), 1200); }
    });
    view.onZoom = () => this.navSync();
    void this.loadPresets();
  }

  private commands(): void {
    const ctx = this.ctx;
    ctx.commands.add(
      { id: 'dev.presetFavorite', label: () => (this.ctxPreset?.favorite ? 'Remove from Favorites' : 'Add to Favorites'), run: () => { const p = this.ctxPreset; if (p) void ctx.api.cmd('preset.favorite', { id: p.id, on: !p.favorite }).then(() => this.loadPresets()); } },
      { id: 'dev.presetUpdate', label: 'Update with Current Settings', run: () => { const p = this.ctxPreset; if (p) void develop.flush().then(() => ctx.api.cmd('preset.update', { id: p.id, photo: develop.id })).then(() => toast(`Updated ${p.name}`), (e) => ctx.fail(e)); }, enabled: () => !!this.ctxPreset && !this.ctxPreset.builtin },
      { id: 'dev.presetDelete', label: 'Delete', run: async () => { const p = this.ctxPreset; if (p && await confirmAction('Delete Preset', `Delete the preset "${p.name}"?`, 'Delete', true)) { await ctx.api.cmd('preset.delete', { id: p.id }).catch((e) => ctx.fail(e)); void this.loadPresets(); } }, enabled: () => !!this.ctxPreset && !this.ctxPreset.builtin },
      { id: 'develop.newPreset', label: 'New Develop Preset...', keys: ['Shift+Mod+N'], run: async () => {
        if (develop.id === null) return;
        this.presetDialog ??= new PresetDialog();
        const v = await this.presetDialog.ask(this.userGroups(), { group: this.ctxPreset && !this.ctxPreset.builtin ? this.ctxPreset.group : undefined });
        if (!v || develop.id === null) return;
        await develop.flush();
        await ctx.api.cmd('preset.create', { name: v.name, group: v.group, groups: v.groups, id: develop.id }).then(() => toast(`Created ${v.name} in ${v.group}`), (e) => ctx.fail(e));
        void this.loadPresets();
      } },
      { id: 'dev.presetRename', label: 'Rename...', run: async () => { const p = this.ctxPreset; if (!p) return; const name = await promptName('Rename Preset', p.name, 'Rename'); if (name && name !== p.name) { await ctx.api.cmd('preset.update', { id: p.id, name }).catch((e) => ctx.fail(e)); void this.loadPresets(); } }, enabled: () => !!this.ctxPreset && !this.ctxPreset.builtin },
      { id: 'dev.presetExport', label: 'Export...', run: () => { const p = this.ctxPreset; if (p) void ctx.api.cmd<{ path: string }>('preset.export', { id: p.id }).then((r) => { const a = document.createElement('a'); a.href = outputUrl(r.path); a.download = r.path.split(/[\\/]/).pop() ?? 'preset.xmp'; a.click(); toast(`Exported ${p.name} as XMP`); }, (e) => ctx.fail(e)); }, enabled: () => !!this.ctxPreset },
      { id: 'preset.importFiles', label: 'Import Develop Profiles and Presets...', run: () => this.pickPresetFiles() },
      { id: 'dev.snapUpdate', label: 'Update with Current Settings', run: () => { const s = this.ctxSnap; if (s) void develop.flush().then(() => ctx.api.cmd('snapshot.update', { snapshot: s, settings: true })).then(() => toast('Snapshot updated'), (e) => ctx.fail(e)); }, enabled: () => this.ctxSnap !== null },
      { id: 'dev.snapRename', label: 'Rename...', run: async () => { const s = this.ctxSnap; if (s === null) return; const row = this.snaps.querySelector<HTMLElement>(`[data-snap="${s}"] span`); const name = await promptName('Rename Snapshot', row?.textContent ?? '', 'Rename'); if (name) { await ctx.api.cmd('snapshot.update', { snapshot: s, name }).catch((e) => ctx.fail(e)); this.loadSnaps(); } }, enabled: () => this.ctxSnap !== null },
      { id: 'dev.snapBefore', label: 'Copy Snapshot Settings to Before', run: () => { const s = this.ctxSnap; if (s !== null && develop.id !== null) void ctx.api.cmd('develop.setBefore', { id: develop.id, source: 'snapshot', snapshot: s }).then(() => toast('Before now shows the snapshot'), (e) => ctx.fail(e)); }, enabled: () => this.ctxSnap !== null },
      { id: 'dev.histBefore', label: 'Copy History Step Settings to Before', run: () => { const s = this.ctxStep; if (s !== null && develop.id !== null) void ctx.api.cmd('develop.setBefore', { id: develop.id, source: 'history', step: s }).then(() => toast('Before now shows that history step'), (e) => ctx.fail(e)); }, enabled: () => this.ctxStep !== null },
      { id: 'dev.snapDelete', label: 'Delete', run: () => { const s = this.ctxSnap; if (s !== null) void ctx.api.cmd('snapshot.delete', { snapshot: s }).then(() => this.loadSnaps(), (e) => ctx.fail(e)); }, enabled: () => this.ctxSnap !== null },
      { id: 'develop.snapshot', label: 'New Snapshot...', keys: ['Mod+N'], run: async () => {
        if (develop.id === null) return;
        const name = await promptName('New Snapshot', new Date().toLocaleString(), 'Create');
        if (!name) return;
        await develop.flush();
        await ctx.api.cmd('snapshot.create', { id: develop.id, name }).catch((e) => ctx.fail(e));
        this.loadSnaps();
      } },
    );
  }

  async loadPresets(): Promise<void> {
    try {
      const r = await this.ctx.api.cmd<{ presets: Preset[] }>('preset.list');
      this.presetList = r.presets;
    } catch { return; }
    const nodes: TreeNode[] = [];
    const favs = this.presetList.filter((p) => p.favorite);
    if (favs.length) {
      nodes.push({ key: 'g:Favorites', label: 'Favorites', icon: 'starFill', depth: 0, hasKids: true, count: favs.length });
      for (const p of favs) nodes.push({ key: `f:${p.id}`, label: p.name, icon: 'presetsLit', depth: 1, hasKids: false, data: p });
    }
    const groups = new Map<string, Preset[]>();
    for (const p of this.presetList) { if (!groups.has(p.group)) groups.set(p.group, []); groups.get(p.group)?.push(p); }
    for (const [g, items] of groups) {
      nodes.push({ key: `g:${g}`, label: g, icon: 'folder', depth: 0, hasKids: true, count: items.length });
      for (const p of items) nodes.push({ key: `p:${p.id}`, label: p.name, icon: 'presetsLit', depth: 1, hasKids: false, data: p });
    }
    this.presets.set(nodes);
  }

  private userGroups(): string[] {
    return Array.from(new Set(this.presetList.filter((p) => !p.builtin).map((p) => p.group)));
  }

  private async previewPreset(p: Preset): Promise<void> {
    const id = develop.id;
    if (id === null) return;
    const seq = ++this.hoverSeq;
    try {
      await develop.flush();
      const blob = await this.ctx.api.blob(`/api/photos/${id}/render`, { preset: p.id, presetAmount: Number(this.amount.value), long: 480, quality: 82 });
      if (seq !== this.hoverSeq || develop.id !== id) return;
      const url = URL.createObjectURL(blob);
      const old = this.hoverUrl;
      this.hoverUrl = url;
      await swapMedia(this.navImg, url);
      if (old) URL.revokeObjectURL(old);
      setClass(this.navBox, 'is-preview', true);
    } catch { return; }
  }

  private endPreview(): void {
    this.hoverSeq += 1;
    if (!this.hoverUrl) return;
    const p = library.photo(develop.id);
    const old = this.hoverUrl;
    this.hoverUrl = '';
    setClass(this.navBox, 'is-preview', false);
    if (p) {
      delete this.navImg.dataset.src;
      void loadInto(this.navImg, thumbUrl(p)).then(() => URL.revokeObjectURL(old));
    }
  }

  private pickPresetFiles(): void {
    const input = el<HTMLInputElement>('<input type="file" multiple accept=".xmp,.lrtemplate,.flpreset,.cube,.dcp" hidden>');
    input.addEventListener('change', () => {
      const files = Array.from(input.files ?? []);
      input.remove();
      if (!files.length) return;
      const form = new FormData();
      for (const f of files) form.append('files', f, f.name);
      void this.ctx.api.upload<{ paths: string[] }>('/api/files/upload/presets', form)
        .then((r) => this.ctx.api.cmd<{ imported: string[] }>('preset.import', { paths: r.paths }))
        .then((r) => { toast(r.imported.length ? `Imported ${r.imported.length}: ${r.imported.slice(0, 3).join(', ')}${r.imported.length > 3 ? '...' : ''}` : 'Nothing to import in those files'); void this.loadPresets(); void develop.refreshInfo(); }, (e) => this.ctx.fail(e));
    });
    document.body.appendChild(input);
    input.click();
  }

  private async applyPreset(p: Preset): Promise<void> {
    const ids = library.targets();
    if (!ids.length) return;
    await develop.flush();
    try { await this.ctx.api.cmd('preset.apply', { ids: develop.id !== null && ids.length === 1 ? [develop.id] : ids, preset: p.id, amount: Number(this.amount.value) }); } catch (err) { this.ctx.fail(err); }
  }

  loadHistory(): void {
    const id = develop.id;
    if (id === null) return;
    void this.ctx.api.cmd<{ steps: Step[] }>('develop.history', { id }).then((r) => {
      if (id !== develop.id) return;
      patchList(this.history, r.steps.slice(0, 120), {
        key: (s) => String(s.id),
        create: (s) => el(`<button class="fl-list-row" type="button" data-step="${s.id}"><span>${escapeHtml(s.name)}</span><em>${escapeHtml(s.time.slice(11, 16))}</em></button>`),
        update: () => undefined,
      });
    }, () => undefined);
  }

  loadSnaps(): void {
    const id = develop.id;
    if (id === null) return;
    void this.ctx.api.cmd<{ snapshots: Snap[] }>('snapshot.list', { id }).then((r) => {
      if (id !== develop.id) return;
      patchList(this.snaps, r.snapshots, {
        key: (s) => String(s.id),
        create: (s) => el(`<div class="fl-list-row" data-snap="${s.id}"><span>${escapeHtml(s.name)}</span><button class="cv-icon-btn" type="button" data-del aria-label="Delete">${icon('close', 12)}</button></div>`),
        update: () => undefined,
      });
      if (!r.snapshots.length) this.snaps.replaceChildren(el('<div class="fl-muted fl-list-empty">No snapshots yet</div>'));
      else this.snaps.querySelector('.fl-list-empty')?.remove();
    }, () => undefined);
  }

  nav(): void {
    const p = library.photo(develop.id);
    if (p) void loadInto(this.navImg, thumbUrl(p));
    this.navSync();
  }

  navSync(): void {
    const v = this.view;
    for (const b of Array.from(this.navBox.parentElement?.parentElement?.querySelectorAll<HTMLElement>('[data-z]') ?? [])) {
      const z = b.dataset.z;
      setClass(b, 'is-on', String(v.zoom) === z);
    }
    const r = v.displayRect();
    const stage = v.root.getBoundingClientRect();
    const zoomed = r.w > stage.width + 1 || r.h > stage.height + 1;
    setClass(this.navRect, 'is-shown', zoomed);
    if (!zoomed) return;
    const x0 = Math.max(0, -r.x / r.w), y0 = Math.max(0, -r.y / r.h);
    const x1 = Math.min(1, (stage.width - r.x) / r.w), y1 = Math.min(1, (stage.height - r.y) / r.h);
    setStyleVar(this.navRect, '--l', `${(x0 * 100).toFixed(2)}%`);
    setStyleVar(this.navRect, '--t', `${(y0 * 100).toFixed(2)}%`);
    setStyleVar(this.navRect, '--w', `${((x1 - x0) * 100).toFixed(2)}%`);
    setStyleVar(this.navRect, '--h', `${((y1 - y0) * 100).toFixed(2)}%`);
  }
}
