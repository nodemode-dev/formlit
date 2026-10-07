import { Dialog } from '../../ui/dialogs';
import { el, q, setHidden, setText } from '../../ui/dom';
import { DEFAULT_OFF, GROUPS } from './groups';

export interface NewPreset { name: string; group: string; groups: string[] }

const NEW_GROUP = '__new';

export class PresetDialog extends Dialog {
  private resolve: ((v: NewPreset | null) => void) | null = null;
  private readonly boxes = new Map<string, HTMLInputElement>();
  private readonly name = el<HTMLInputElement>('<input class="cv-input" type="text" spellcheck="false">');
  private readonly group = el<HTMLSelectElement>('<select class="cv-select"></select>');
  private readonly newGroup = el<HTMLInputElement>('<input class="cv-input" type="text" spellcheck="false" placeholder="Group name">');
  private readonly newRow: HTMLElement;
  private readonly ok: HTMLButtonElement;

  constructor() {
    super('New Develop Preset', 560);
    this.field('Preset Name', this.name);
    this.field('Group', this.group);
    this.newRow = this.field('New Group', this.newGroup);
    this.group.addEventListener('change', () => setHidden(this.newRow, this.group.value !== NEW_GROUP));
    const sub = el('<div class="fl-sub">Settings</div>');
    const grid = el('<div class="fl-groups"></div>');
    for (const [k, l] of GROUPS) {
      const row = el('<label class="fl-check"><input type="checkbox"> <span></span></label>');
      setText(q(row, 'span'), l);
      this.boxes.set(k, q<HTMLInputElement>(row, 'input'));
      grid.appendChild(row);
    }
    const all = el('<div class="fl-row fl-row-end"><button class="cv-btn fl-btn-sm" type="button" data-all="1">Check All</button><button class="cv-btn fl-btn-sm" type="button" data-all="0">Check None</button></div>');
    all.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-all]');
      if (b) for (const cb of this.boxes.values()) cb.checked = b.dataset.all === '1';
    });
    this.body.append(sub, grid, all);
    this.button('Cancel', 'ghost', () => this.finish(null));
    this.ok = this.button('Create', 'primary', () => this.submit());
    this.onClose = () => this.finish(null);
    this.scrim.addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.target as HTMLElement).tagName === 'INPUT' && (e.target as HTMLInputElement).type === 'text') { e.preventDefault(); this.submit(); } });
  }

  ask(groups: string[], start: Partial<NewPreset> = {}, title = 'New Develop Preset', okLabel = 'Create'): Promise<NewPreset | null> {
    this.setTitle(title);
    setText(this.ok, okLabel);
    const names = Array.from(new Set(['User Presets', ...groups]));
    this.group.replaceChildren(...names.map((g) => new Option(g, g)), new Option('New Group...', NEW_GROUP));
    this.group.value = start.group && names.includes(start.group) ? start.group : 'User Presets';
    this.newGroup.value = '';
    setHidden(this.newRow, true);
    this.name.value = start.name ?? 'Untitled Preset';
    const on = start.groups ? new Set(start.groups) : null;
    for (const [k, cb] of this.boxes) cb.checked = on ? on.has(k) : !DEFAULT_OFF.has(k);
    this.open(this.name);
    this.name.select();
    return new Promise((r) => { this.resolve = r; });
  }

  private submit(): void {
    const name = this.name.value.trim();
    const group = this.group.value === NEW_GROUP ? this.newGroup.value.trim() : this.group.value;
    const groups = [...this.boxes].filter(([, cb]) => cb.checked).map(([k]) => k);
    if (!name || !group || !groups.length) return;
    this.finish({ name, group, groups });
  }

  private finish(v: NewPreset | null): void {
    const r = this.resolve;
    this.resolve = null;
    if (this.isOpen) this.close();
    r?.(v);
  }
}
