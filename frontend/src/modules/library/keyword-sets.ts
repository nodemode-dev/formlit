import type { Ctx } from '../../app';
import { library } from '../../state/library';
import { askForm } from '../../ui/askform';
import { el, escapeHtml, setDisabled, setText, setValue } from '../../ui/dom';
import { toast } from '../../ui/toast';

const BUILTIN: Record<string, string[]> = {
  'Outdoor Photography': ['Landscape', 'Wildlife', 'Macro', 'Sunset', 'Mountains', 'Forest', 'Water', 'Sky', 'Snow'],
  'Portrait Photography': ['Portrait', 'Headshot', 'Family', 'Couple', 'Children', 'Group', 'Studio', 'Natural Light', 'Black and White'],
  'Wedding Photography': ['Ceremony', 'Reception', 'Getting Ready', 'Details', 'Bride', 'Groom', 'Family', 'First Dance', 'Candid'],
  'Event Photography': ['Stage', 'Speaker', 'Audience', 'Venue', 'Candid', 'Group', 'Details', 'Food', 'Signage'],
};
const RECENT_KEY = 'formlit_recent_keywords';
const SET_KEY = 'formlit_keyword_set';

function recent(): string[] {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]') as string[]; } catch { return []; }
}

export function rememberKeywords(kws: string[]): void {
  const next = [...kws, ...recent().filter((k) => !kws.includes(k))].slice(0, 9);
  try { localStorage.setItem(RECENT_KEY, JSON.stringify(next)); } catch { return; }
}

export class KeywordSets {
  readonly root = el(`<div class="fl-kwset"><div class="fl-kwset-head"><select class="cv-select" aria-label="Keyword set"></select><button class="cv-btn fl-btn-sm" type="button" data-edit>Edit...</button></div><div class="fl-kwset-grid">${Array.from({ length: 9 }, (_, i) => `<button class="fl-kwset-btn" type="button" data-i="${i}" title="Alt+${i + 1}" disabled></button>`).join('')}</div></div>`);
  private readonly select = this.root.querySelector('select') as HTMLSelectElement;
  private readonly grid = this.root.querySelector('.fl-kwset-grid') as HTMLElement;
  private user: Record<string, string[]> = {};
  private current = 'Recent Keywords';

  constructor(private readonly ctx: Ctx) {
    try { this.current = localStorage.getItem(SET_KEY) || 'Recent Keywords'; } catch { this.current = 'Recent Keywords'; }
    this.render();
    void ctx.api.cmd<Record<string, unknown>>('prefs.get').then((p) => { this.user = (p.keywordSets as Record<string, string[]>) ?? {}; this.render(); }, () => this.render());
    this.select.addEventListener('change', () => { this.current = this.select.value; try { localStorage.setItem(SET_KEY, this.current); } catch { this.render(); } this.render(); });
    this.grid.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-i]');
      if (b) void this.apply(Number(b.dataset.i));
    });
    this.root.querySelector('[data-edit]')?.addEventListener('click', () => void this.edit());
    for (let i = 1; i <= 9; i += 1) ctx.commands.add({ id: `keyword.set${i}`, label: `Apply Keyword Shortcut ${i}`, keys: [`Alt+${i}`], run: () => void this.apply(i - 1), enabled: () => library.targets().length > 0 });
  }

  private sets(): Record<string, string[]> {
    return { 'Recent Keywords': recent(), ...BUILTIN, ...this.user };
  }

  words(): string[] { return (this.sets()[this.current] ?? []).slice(0, 9); }

  render(): void {
    const names = Object.keys(this.sets());
    if (!names.includes(this.current)) this.current = 'Recent Keywords';
    const opts = names.map((n) => `<option value="${escapeHtml(n)}">${escapeHtml(n)}</option>`).join('');
    if (this.select.dataset.key !== opts) { this.select.dataset.key = opts; this.select.innerHTML = opts; }
    setValue(this.select, this.current);
    const words = this.words();
    this.grid.querySelectorAll<HTMLButtonElement>('.fl-kwset-btn').forEach((b, i) => { setText(b, words[i] ?? ''); setDisabled(b, !words[i]); });
  }

  private async apply(i: number): Promise<void> {
    const kw = this.words()[i];
    const ids = library.targets();
    if (!kw || !ids.length) return;
    try {
      await this.ctx.api.cmd('photo.addKeywords', { ids, keywords: [kw] });
      if (this.current !== 'Recent Keywords') rememberKeywords([kw]);
      toast(`Added ${kw} to ${ids.length} ${ids.length === 1 ? 'photo' : 'photos'}`);
      this.render();
    } catch (err) { this.ctx.fail(err); }
  }

  private async edit(): Promise<void> {
    const words = this.words();
    const v = await askForm('Edit Keyword Set', 'Nine keywords, applied with Alt+1 to Alt+9. Saving under a new name makes a new set.', [
      { path: 'name', label: 'Set name', kind: 'text' },
      ...Array.from({ length: 9 }, (_, i) => ({ path: `w${i}`, label: `Keyword ${i + 1}`, kind: 'text' as const })),
    ], { name: this.current === 'Recent Keywords' ? 'My Keywords' : this.current, ...Object.fromEntries(words.map((w, i) => [`w${i}`, w])) }, 'Save');
    if (!v || !String(v.name ?? '').trim()) return;
    const name = String(v.name).trim();
    this.user = { ...this.user, [name]: Array.from({ length: 9 }, (_, i) => String(v[`w${i}`] ?? '').trim()).filter(Boolean) };
    try {
      await this.ctx.api.cmd('prefs.set', { values: { keywordSets: this.user } });
      this.current = name;
      try { localStorage.setItem(SET_KEY, name); } catch { this.render(); }
      this.render();
    } catch (err) { this.ctx.fail(err); }
  }
}
