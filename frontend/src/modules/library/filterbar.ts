import type { Ctx } from '../../app';
import { library, type Filter } from '../../state/library';
import { el, escapeHtml, patchList, q, setClass, setHidden, setText, setValue } from '../../ui/dom';
import { icon } from '../../ui/icons';
import { LABELS } from '../shared/actions';

interface Facet { value: string | number; name?: string; count: number }
type Facets = Record<string, Facet[]>;

const COLUMNS: Array<[string, string, keyof Filter]> = [['dates', 'Date', 'dates'], ['cameras', 'Camera', 'cameras'], ['lenses', 'Lens', 'lenses'], ['keywords', 'Keyword', 'keywords']];

export class FilterBar {
  readonly root: HTMLElement;
  private tab = '';
  private readonly text: HTMLInputElement;
  private readonly attr: HTMLElement;
  private readonly meta: HTMLElement;
  private readonly textRow: HTMLElement;
  private facets: Facets = {};

  constructor(private readonly ctx: Ctx) {
    this.root = el(`<div class="fl-filterbar" hidden>
<div class="fl-fb-tabs"><span class="fl-fb-title">Library Filter:</span>
<button type="button" data-tab="text">Text</button><button type="button" data-tab="attribute">Attribute</button><button type="button" data-tab="metadata">Metadata</button><button type="button" data-tab="">None</button>
<span class="fl-tb-spacer"></span><button class="cv-btn cv-btn-ghost fl-fb-off" type="button">Filters Off</button></div>
<div class="fl-fb-text" hidden><span class="fl-tb-label">Any Searchable Field</span><input class="cv-input" type="search" placeholder="Search: words, or field:value like camera:canon rating>=3" spellcheck="false"></div>
<div class="fl-fb-attr" hidden></div>
<div class="fl-fb-meta" hidden></div>
</div>`);
    this.text = q<HTMLInputElement>(this.root, '.fl-fb-text input');
    this.textRow = q(this.root, '.fl-fb-text');
    this.attr = q(this.root, '.fl-fb-attr');
    this.meta = q(this.root, '.fl-fb-meta');
    this.buildAttr();
    q(this.root, '.fl-fb-tabs').addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-tab]');
      if (b) this.setTab(b.dataset.tab ?? '');
    });
    q(this.root, '.fl-fb-off').addEventListener('click', () => library.setFilter({}, true));
    let t = 0;
    this.text.addEventListener('input', () => { window.clearTimeout(t); t = window.setTimeout(() => library.setFilter({ text: this.text.value }), 180); });
    this.meta.addEventListener('click', (e) => {
      const row = (e.target as HTMLElement).closest<HTMLElement>('[data-v]');
      if (!row) return;
      const key = row.dataset.k as keyof Filter;
      const raw = row.dataset.v as string;
      const v: string | number = key === 'keywords' ? Number(raw) : raw;
      const cur = ((library.filter[key] as Array<string | number> | undefined) ?? []).slice();
      const mod = (e as MouseEvent).metaKey || (e as MouseEvent).ctrlKey;
      const has = cur.includes(v);
      const next = mod ? (has ? cur.filter((x) => x !== v) : [...cur, v]) : (has && cur.length === 1 ? [] : [v]);
      library.setFilter({ [key]: next } as Partial<Filter>);
    });
    library.listen('list', () => { this.sync(); if (this.tab === 'metadata') void this.loadFacets(); });
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
    if (this.tab === 'metadata') this.renderFacets();
  }

  private async loadFacets(): Promise<void> {
    try { this.facets = await this.ctx.api.cmd<Facets>('library.facets', { source: library.source }); } catch { return; }
    this.renderFacets();
  }

  private renderFacets(): void {
    if (!this.meta.childElementCount) {
      for (const [k, label] of COLUMNS) this.meta.appendChild(el(`<div class="fl-fb-col" data-col="${k}"><div class="fl-fb-col-head">${label}</div><div class="fl-fb-col-list"></div></div>`));
    }
    for (const [k, , fk] of COLUMNS) {
      const list = q(this.meta, `[data-col="${k}"] .fl-fb-col-list`);
      const rows = (this.facets[k] ?? []).map((f) => ({ v: String(f.value), name: f.name ?? String(f.value), count: f.count }));
      const sel = new Set(((library.filter[fk] as Array<string | number> | undefined) ?? []).map(String));
      patchList(list, rows, {
        key: (r) => r.v,
        create: (r) => { const n = el(`<button class="fl-fb-row" type="button" data-k="${fk}" data-v="${escapeHtml(r.v)}"><span></span><em></em></button>`); return n; },
        update: (n, r) => { setText(q(n, 'span'), r.name); setText(q(n, 'em'), String(r.count)); setClass(n, 'is-on', sel.has(r.v)); },
      });
      for (const n of Array.from(list.children) as HTMLElement[]) { const r = rows.find((x) => x.v === n.dataset.v); if (r) { setText(q(n, 'span'), r.name); setText(q(n, 'em'), String(r.count)); setClass(n, 'is-on', sel.has(r.v)); } }
    }
  }
}
