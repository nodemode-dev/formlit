import { clone, merge, prune, type Dev } from '../../../demo/src/engine/settings';
import { develop } from '../../../demo/src/shims/develop';
import { PresetDialog } from '../../../frontend/src/modules/develop/preset-dialog';
import { el, patchList, q, setClass, setText } from '../../../frontend/src/ui/dom';
import { icon } from '../../../frontend/src/ui/icons';
import { Panel } from '../../../frontend/src/ui/panel';
import { Slider } from '../../../frontend/src/ui/slider';
import { toast } from '../../../frontend/src/ui/toast';

export interface UserPreset { id: string; name: string; group: string; groups: string[]; dev: Dev }

const KEY = 'formlit-demo-develop-presets';

const KEYS: Record<string, string[]> = {
  whiteBalance: ['wb'], basicTone: ['light'], presence: ['effects', 'color'], toneCurve: ['curve'], colorMixer: ['mixer'], pointColor: ['pointColor'], bwMix: ['bw'], treatment: ['treatment'],
  colorGrading: ['grading'], detail: ['detail'], lensCorrections: ['optics'], transform: ['geometry'], effects: ['vignette', 'grain'], calibration: ['calibration'], profile: ['profile'],
  lensBlur: ['lensBlur'], hdr: ['hdr'], masks: ['masks'], crop: ['crop', 'orientation'],
};

function scale(o: Dev, k: number): void {
  for (const [key, v] of Object.entries(o)) {
    if (typeof v === 'number' && key !== 'hue' && key !== 'temp' && key !== 'tint') o[key] = v * k;
    else if (v && typeof v === 'object' && !Array.isArray(v)) scale(v as Dev, k);
  }
}

export function pick(dev: Dev, groups: string[]): Dev {
  const out: Dev = {};
  for (const g of groups) for (const key of KEYS[g] ?? []) if (dev[key] !== undefined) out[key] = clone({ v: dev[key] }).v;
  return out;
}

export function applyPreset(base: Dev, p: UserPreset, amount: number): Dev {
  const covered = new Set(p.groups.flatMap((g) => KEYS[g] ?? []));
  const keep: Dev = {};
  for (const [k, v] of Object.entries(base)) if (!covered.has(k)) keep[k] = clone({ v }).v;
  const over = clone(p.dev);
  if (amount !== 1) scale(over, amount);
  return prune(merge(keep, over));
}

function load(): UserPreset[] {
  try { return JSON.parse(localStorage.getItem(KEY) ?? '[]') as UserPreset[]; } catch { return []; }
}

function save(list: UserPreset[]): void {
  try { localStorage.setItem(KEY, JSON.stringify(list)); } catch { /* storage blocked */ }
}

export class UserPresets {
  readonly panel: Panel;
  private list: UserPreset[] = [];
  private readonly rows: HTMLElement;
  private readonly amount: Slider;
  private dialog: PresetDialog | null = null;
  private seq = 1;

  constructor(host: HTMLElement, before: Element | null, seed: UserPreset[]) {
    const add = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" title="Create Preset from the current settings" aria-label="Create Preset">${icon('plus', 14)}</button>`);
    this.panel = new Panel('dev.userpresets', 'My Presets', { open: true, tools: [add] });
    add.addEventListener('click', (e) => { e.stopPropagation(); void this.create(); });
    this.amount = new Slider({ id: 'userpreset.amount', label: 'Amount', min: 0, max: 200, default: 100, step: 1, decimals: 0 }, { input: () => undefined });
    this.rows = el('<div class="fl-list fl-userpresets"></div>');
    this.panel.body.append(this.amount.root, this.rows);
    if (before) host.insertBefore(this.panel.root, before); else host.appendChild(this.panel.root);
    this.list = load();
    if (!this.list.length) { this.list = seed; save(this.list); }
    this.seq = this.list.length + 1;
    this.rows.addEventListener('click', (e) => {
      const t = e.target as HTMLElement;
      const id = t.closest<HTMLElement>('[data-id]')?.dataset.id;
      const p = this.list.find((x) => x.id === id);
      if (!p) return;
      if (t.closest('[data-del]')) { this.list = this.list.filter((x) => x.id !== p.id); save(this.list); this.paint(); toast(`Deleted preset ${p.name}`); return; }
      if (!develop.item) return;
      develop.replace(applyPreset(develop.settings, p, this.amount.get() / 100), 'end', `Preset: ${p.name}`);
    });
    this.paint();
  }

  async create(): Promise<void> {
    const item = develop.item;
    if (!item) { toast('Open a photo in Develop first', 'error'); return; }
    this.dialog ??= new PresetDialog();
    const groups = Array.from(new Set(this.list.map((p) => p.group)));
    const got = await this.dialog.ask(groups, { name: 'My Look', groups: ['basicTone', 'presence', 'toneCurve', 'colorMixer', 'colorGrading', 'effects', 'detail', 'treatment', 'whiteBalance'] });
    if (!got) return;
    const dev = pick(develop.settings, got.groups);
    if (!Object.keys(dev).length) { toast('Nothing in those groups is set on this photo', 'error'); return; }
    const p: UserPreset = { id: `user-${Date.now()}-${this.seq++}`, name: got.name, group: got.group, groups: got.groups, dev };
    this.list = [...this.list.filter((x) => !(x.name === p.name && x.group === p.group)), p];
    save(this.list);
    this.paint();
    toast(`Saved preset ${p.name}`);
  }

  private paint(): void {
    patchList(this.rows, this.list, {
      key: (p) => p.id,
      create: (p) => {
        const row = el(`<div class="fl-list-row fl-user-row" role="button" tabindex="0"><span></span><em></em><button class="cv-icon-btn" type="button" data-del aria-label="Delete preset" title="Delete preset">${icon('close', 11)}</button></div>`);
        row.dataset.id = p.id;
        setText(q(row, 'span'), p.name);
        setText(q(row, 'em'), p.group);
        row.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); row.click(); } });
        return row;
      },
      update: (node, p) => { setText(q(node, 'span'), p.name); setText(q(node, 'em'), p.group); setClass(node, 'is-user', true); },
    });
  }
}
