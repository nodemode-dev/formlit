import type { Ctx } from '../../app';
import { library, type Filter } from '../../state/library';
import { askForm } from '../../ui/askform';
import { el, escapeHtml, patchList, q, setClass, setHidden, setStyleVar, setText, setValue } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { LABELS } from '../shared/actions';

interface Facet { value: string | number; name?: string; count: number }
type Facets = Record<string, Facet[]>;
interface FilterPreset { name: string; builtin?: boolean; tab?: string; columns?: string[]; filter: Filter }

const COLS_KEY = 'formlit_filter_columns';
const DEFAULT_COLS = ['date', 'camera', 'lens', 'label'];
const MAX_COLS = 8;

function readCols(): string[] {
  try { const v = JSON.parse(localStorage.getItem(COLS_KEY) || 'null') as string[] | null; return Array.isArray(v) && v.length ? v.slice(0, MAX_COLS) : DEFAULT_COLS.slice(); } catch { return DEFAULT_COLS.slice(); }
}

export class FilterBar {
  readonly root: HTMLElement;
  private tab = '';
  private readonly text: HTMLInputElement;
  private readonly attr: HTMLElement;
  private readonly meta: HTMLElement;
  private readonly textRow: HTMLElement;
  private facets: Facets = {};
  private cols = readCols();
  private available: Array<[string, string]> = [];
  private presets: FilterPreset[] = [];
  private readonly presetSel: HTMLSelectElement;
  private readonly lock: HTMLElement;

  constructor(private readonly ctx: Ctx) {
    this.root = el(`<div class="fl-filterbar" hidden>
<div class="fl-fb-tabs"><span class="fl-fb-title">Library Filter:</span>
<button type="button" data-tab="text">Text</button><button type="button" data-tab="attribute">Attribute</button><button type="button" data-tab="metadata">Metadata</button><button type="button" data-tab="">None</button>
<span class="fl-tb-spacer"></span><select class="cv-select fl-fb-preset" aria-label="Filter preset"><option value="">Custom Filter</option></select><button class="cv-icon-btn fl-fb-lock" type="button" title="Lock the filter so it stays when you change source"><span data-on hidden>${icon('lock', 14)}</span><span data-off>${icon('unlock', 14)}</span></button><button class="cv-btn cv-btn-ghost fl-fb-off" type="button">Filters Off</button></div>
<div class="fl-fb-text" hidden><span class="fl-tb-label">Any Searchable Field</span><input class="cv-input" type="search" placeholder="Search: words, or field:value like camera:canon rating>=3" spellcheck="false"></div>
<div class="fl-fb-attr" hidden></div>
<div class="fl-fb-meta" hidden></div>
</div>`);
    this.text = q<HTMLInputElement>(this.root, '.fl-fb-text input');
    this.textRow = q(this.root, '.fl-fb-text');
    this.attr = q(this.root, '.fl-fb-attr');
    this.meta = q(this.root, '.fl-fb-meta');
    this.presetSel = q<HTMLSelectElement>(this.root, '.fl-fb-preset');
    this.lock = q(this.root, '.fl-fb-lock');
    this.lock.addEventListener('click', () => { library.setFilterLock(!library.filterLock); this.sync(); });
    this.presetSel.addEventListener('change', () => {
      const v = this.presetSel.value;
      if (v.startsWith('#')) this.presetSel.value = '';
      this.presetSel.blur();
      void this.pickPreset(v);
    });
    void this.loadPresets();
    this.buildAttr();
    q(this.root, '.fl-fb-tabs').addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-tab]');
      if (b) this.setTab(b.dataset.tab ?? '');
    });
    q(this.root, '.fl-fb-off').addEventListener('click', () => library.setFilter({}, true));
    let t = 0;
    this.text.addEventListener('input', () => { window.clearTimeout(t); t = window.setTimeout(() => library.setFilter({ text: this.text.value }), 180); });
    this.meta.addEventListener('click', (e) => {
      const t = e.target as HTMLElement;
      const colBtn = t.closest<HTMLElement>('[data-col-act]');
      if (colBtn) { this.colAction(colBtn.dataset.colAct as string, Number(colBtn.closest<HTMLElement>('[data-i]')?.dataset.i ?? -1)); return; }
      const row = t.closest<HTMLElement>('[data-v]');
      if (!row) return;
      const key = row.dataset.k as string;
      const raw = row.dataset.v as string;
      const v: string | number = ['keyword', 'collection', 'person'].includes(key) ? Number(raw) : raw;
      const meta = { ...(library.filter.meta ?? {}) };
      const cur = (meta[key] ?? []).slice();
      const mod = (e as MouseEvent).metaKey || (e as MouseEvent).ctrlKey;
      const has = cur.includes(v);
      const next = mod ? (has ? cur.filter((x) => x !== v) : [...cur, v]) : (has && cur.length === 1 ? [] : [v]);
      if (next.length) meta[key] = next; else delete meta[key];
      if (!mod) for (const k of this.cols.slice(this.cols.indexOf(key) + 1)) delete meta[k];
      library.setFilter({ meta: Object.keys(meta).length ? meta : undefined });
    });
    this.meta.addEventListener('change', (e) => {
      const s = (e.target as HTMLElement).closest<HTMLSelectElement>('select[data-i]');
      if (!s) return;
      const i = Number(s.dataset.i);
      const old = this.cols[i];
      this.cols[i] = s.value;
      this.saveCols();
      const meta = { ...(library.filter.meta ?? {}) };
      if (old && meta[old]) { delete meta[old]; library.setFilter({ meta: Object.keys(meta).length ? meta : undefined }); }
      void this.loadFacets();
    });
    library.listen('list', () => this.sync());
    this.sync();
  }

  get visible(): boolean { return !this.root.hidden; }

  toggle(): void { setHidden(this.root, !this.root.hidden); if (!this.root.hidden && !this.tab) this.setTab('attribute'); }

  focusText(): void {
    setHidden(this.root, false);
    this.setTab('text');
    this.text.focus();
    this.text.select();
  }

  setTab(tab: string): void {
    this.tab = tab;
    for (const b of Array.from(this.root.querySelectorAll<HTMLElement>('[data-tab]'))) setClass(b, 'is-on', b.dataset.tab === tab);
    setHidden(this.textRow, tab !== 'text');
    setHidden(this.attr, tab !== 'attribute');
    setHidden(this.meta, tab !== 'metadata');
    if (tab === 'metadata') void this.loadFacets();
  }

  private buildAttr(): void {
    const flag = (f: string, ic: string, title: string) => `<button class="cv-icon-btn" type="button" data-flag="${f}" title="${title}">${icon(ic, 14)}</button>`;
    this.attr.innerHTML = `<span class="fl-tb-label">Flag</span>${flag('pick', 'flagPickFill', 'Flagged')}${flag('none', 'flagPick', 'Unflagged')}${flag('reject', 'flagRejectFill', 'Rejected')}
<span class="fl-tb-sep"></span><span class="fl-tb-label">Rating</span><select class="cv-select fl-fb-op"><option value=">=">&ge;</option><option value="=">=</option><option value="<=">&le;</option></select><span class="fl-fb-stars">${[1, 2, 3, 4, 5].map((n) => `<button type="button" data-star="${n}" aria-label="${n} stars">${icon('starFill', 13)}</button>`).join('')}</span>
<span class="fl-tb-sep"></span><span class="fl-tb-label">Color</span>${LABELS.map((l) => `<button class="fl-swatch-btn" type="button" data-label="${l}" title="${l}"></button>`).join('')}<button class="fl-swatch-btn" type="button" data-label="none" title="No label"></button>
<span class="fl-tb-sep"></span><span class="fl-tb-label">Kind</span><button class="cv-btn cv-btn-ghost" type="button" data-edited="1">Edited</button><button class="cv-btn cv-btn-ghost" type="button" data-edited="0">Unedited</button><button class="cv-btn cv-btn-ghost" type="button" data-kind="video">Videos</button>`;
    this.attr.addEventListener('click', (e) => {
      const t = (e.target as HTMLElement).closest<HTMLElement>('button');
      if (!t) return;
      const f = library.filter;
      if (t.dataset.flag) {
        const cur = new Set(f.flags ?? []);
        if (cur.has(t.dataset.flag)) cur.delete(t.dataset.flag); else cur.add(t.dataset.flag);
        library.setFilter({ flags: [...cur] });
      } else if (t.dataset.star) {
        const n = Number(t.dataset.star);
        library.setFilter({ rating: f.rating === n ? null : n, ratingOp: q<HTMLSelectElement>(this.attr, '.fl-fb-op').value });
      } else if (t.dataset.label) {
        const cur = new Set(f.labels ?? []);
        if (cur.has(t.dataset.label)) cur.delete(t.dataset.label); else cur.add(t.dataset.label);
        library.setFilter({ labels: [...cur] });
      } else if (t.dataset.edited) {
        const v = t.dataset.edited === '1';
        library.setFilter({ edited: f.edited === v ? null : v });
      } else if (t.dataset.kind) {
        const cur = new Set(f.kinds ?? []);
        if (cur.has(t.dataset.kind)) cur.delete(t.dataset.kind); else cur.add(t.dataset.kind);
        library.setFilter({ kinds: [...cur] });
      }
    });
    q<HTMLSelectElement>(this.attr, '.fl-fb-op').addEventListener('change', (e) => { if (library.filter.rating) library.setFilter({ ratingOp: (e.target as HTMLSelectElement).value }); });
  }

  private sync(): void {
    const f = library.filter;
    setValue(this.text, f.text ?? '');
    for (const b of Array.from(this.attr.querySelectorAll<HTMLElement>('[data-flag]'))) setClass(b, 'is-active', (f.flags ?? []).includes(b.dataset.flag ?? ''));
    for (const b of Array.from(this.attr.querySelectorAll<HTMLElement>('[data-star]'))) setClass(b, 'is-on', !!f.rating && Number(b.dataset.star) <= f.rating);
    for (const b of Array.from(this.attr.querySelectorAll<HTMLElement>('[data-label]'))) setClass(b, 'is-on', (f.labels ?? []).includes(b.dataset.label ?? ''));
    for (const b of Array.from(this.attr.querySelectorAll<HTMLElement>('[data-edited]'))) setClass(b, 'is-on', f.edited === (b.dataset.edited === '1'));
    for (const b of Array.from(this.attr.querySelectorAll<HTMLElement>('[data-kind]'))) setClass(b, 'is-on', (f.kinds ?? []).includes(b.dataset.kind ?? ''));
    setValue(q<HTMLSelectElement>(this.attr, '.fl-fb-op'), f.ratingOp ?? '>=');
    setClass(q(this.root, '.fl-fb-off'), 'is-on', library.hasFilter());
    const locked = library.filterLock;
    setClass(this.lock, 'is-on', locked);
    setHidden(q(this.lock, '[data-on]'), !locked);
    setHidden(q(this.lock, '[data-off]'), locked);
    const match = this.presets.find((p) => JSON.stringify(p.filter) === JSON.stringify(f) && (!p.columns || p.columns.join() === this.cols.join()));
    setValue(this.presetSel, match?.name ?? '');
    if (this.tab === 'metadata') void this.loadFacets();
  }

  private async loadPresets(): Promise<void> {
    try { this.presets = (await this.ctx.api.cmd<{ presets: FilterPreset[] }>('library.filterPresets')).presets; } catch { return; }
    const opts = ['<option value="">Custom Filter</option>', ...this.presets.map((p) => `<option value="${escapeHtml(p.name)}">${escapeHtml(p.name)}</option>`), '<option value="#save">Save Current Settings as New Preset...</option>'];
    const mine = this.presets.filter((p) => !p.builtin);
    if (mine.length) opts.push(...mine.map((p) => `<option value="#del:${escapeHtml(p.name)}">Delete Preset "${escapeHtml(p.name)}"</option>`));
    const html = opts.join('');
    if (this.presetSel.dataset.key !== html) { this.presetSel.dataset.key = html; this.presetSel.innerHTML = html; }
    this.sync();
  }

  private async pickPreset(v: string): Promise<void> {
    if (v === '#save') {
      const got = await askForm('New Filter Preset', 'Saves the current filter and metadata columns.', [{ path: 'name', label: 'Preset Name', kind: 'text' }], { name: '' }, 'Create');
      const name = String(got?.name ?? '').trim();
      if (name) {
        try { await this.ctx.api.cmd('library.filterPresetSave', { name, filter: library.filter, columns: this.tab === 'metadata' ? this.cols : undefined, tab: this.tab }); } catch (err) { this.ctx.fail(err); }
      }
      await this.loadPresets();
      return;
    }
    if (v.startsWith('#del:')) {
      try { await this.ctx.api.cmd('library.filterPresetDelete', { name: v.slice(5) }); } catch (err) { this.ctx.fail(err); }
      await this.loadPresets();
      return;
    }
    const p = this.presets.find((x) => x.name === v);
    if (!p) return;
    if (p.columns?.length) { this.cols = p.columns.slice(0, MAX_COLS); this.saveCols(); }
    library.setFilter({ ...p.filter }, true);
    if (p.tab !== undefined) this.setTab(p.tab);
  }

  private saveCols(): void {
    try { localStorage.setItem(COLS_KEY, JSON.stringify(this.cols)); } catch { return; }
  }

  private colAction(act: string, i: number): void {
    if (act === 'add' && this.cols.length < MAX_COLS) {
      const next = this.available.find(([k]) => !this.cols.includes(k));
      if (next) this.cols.push(next[0]);
    } else if (act === 'remove' && this.cols.length > 1 && i >= 0) {
      const [gone] = this.cols.splice(i, 1);
      const meta = { ...(library.filter.meta ?? {}) };
      if (meta[gone]) { delete meta[gone]; library.setFilter({ meta: Object.keys(meta).length ? meta : undefined }); }
    }
    this.saveCols();
    void this.loadFacets();
  }

  private facetSeq = 0;

  private async loadFacets(): Promise<void> {
    const seq = ++this.facetSeq;
    const { meta, ...rest } = library.filter;
    let r: { columns: Facets; available: Array<[string, string]> };
    try { r = await this.ctx.api.cmd('library.facetColumns', { source: library.source, columns: this.cols, meta: meta ?? {}, filter: rest }); } catch { return; }
    if (seq !== this.facetSeq) return;
    this.facets = r.columns;
    this.available = r.available;
    this.renderFacets();
  }

  private renderFacets(): void {
    setStyleVar(this.meta, '--fl-fb-cols', String(this.cols.length));
    const sel = library.filter.meta ?? {};
    const optsHtml = this.available.map(([k, l]) => `<option value="${k}">${escapeHtml(l)}</option>`).join('');
    const fillCol = (n: HTMLElement, c: { k: string; i: number }) => {
      const pick = q<HTMLSelectElement>(n, 'select');
      if (pick.dataset.opts !== optsHtml) { pick.dataset.opts = optsHtml; pick.innerHTML = optsHtml; pick.value = c.k; }
      setValue(pick, c.k);
      setHidden(q(n, '.fl-fb-col-add'), c.i !== this.cols.length - 1 || this.cols.length >= MAX_COLS);
      setHidden(q(n, '.fl-fb-col-x'), this.cols.length <= 1);
      const on = new Set((sel[c.k] ?? []).map(String));
      const rows = (this.facets[c.k] ?? []).map((f) => ({ v: String(f.value), name: f.name ?? String(f.value), count: f.count }));
      const fillRow = (row: HTMLElement, r: { v: string; name: string; count: number }) => { row.dataset.k = c.k; setText(q(row, 'span'), r.name); setText(q(row, 'em'), String(r.count)); setClass(row, 'is-on', on.has(r.v)); };
      patchList(q(n, '.fl-fb-col-list'), rows, {
        key: (r) => `${c.k}|${r.v}`,
        create: (r) => { const row = el(`<button class="fl-fb-row" type="button" data-v="${escapeHtml(r.v)}"><span></span><em></em></button>`); fillRow(row, r); return row; },
        update: fillRow,
      });
    };
    patchList(this.meta, this.cols.map((k, i) => ({ k, i })), {
      key: (c) => String(c.i),
      create: (c) => {
        const n = el(`<div class="fl-fb-col" data-i="${c.i}"><div class="fl-fb-col-head"><select class="fl-fb-col-pick" data-i="${c.i}" aria-label="Column"></select><button class="cv-icon-btn fl-fb-col-x" type="button" data-col-act="remove" aria-label="Remove column">${icon('close', 10)}</button><button class="cv-icon-btn fl-fb-col-add" type="button" data-col-act="add" aria-label="Add column">${icon('add', 12)}</button></div><div class="fl-fb-col-list"></div></div>`);
        fillCol(n, c);
        return n;
      },
      update: fillCol,
    });
  }
}
