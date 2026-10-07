import type { Ctx } from '../../app';
import type { CollectionRow } from '../../state/catalog';
import { Dialog } from '../../ui/dialogs';
import { el, escapeHtml, q } from '../../ui/dom';
import { icon } from '../../ui/icons';

type Kind = 'num' | 'text' | 'date' | 'bool' | 'flag' | 'label' | 'keyword' | 'kind';

export const RULE_FIELDS: Array<[string, string, Kind]> = [
  ['rating', 'Rating', 'num'], ['flag', 'Pick Flag', 'flag'], ['label', 'Label Color', 'label'], ['kind', 'File Type', 'kind'], ['edited', 'Has Adjustments', 'bool'],
  ['keyword', 'Keywords', 'keyword'], ['fileName', 'Filename', 'text'], ['folder', 'Folder', 'text'], ['title', 'Title', 'text'], ['caption', 'Caption', 'text'],
  ['creator', 'Creator', 'text'], ['copyright', 'Copyright', 'text'], ['camera', 'Camera', 'text'], ['lens', 'Lens', 'text'], ['iso', 'ISO Speed Rating', 'num'],
  ['focal', 'Focal Length', 'num'], ['aperture', 'Aperture', 'num'], ['shutter', 'Shutter Speed (s)', 'num'], ['captureTime', 'Capture Date', 'date'],
  ['importTime', 'Import Date', 'date'], ['editTime', 'Edit Date', 'date'], ['city', 'City', 'text'], ['state', 'State / Province', 'text'], ['country', 'Country', 'text'],
  ['location', 'Sublocation', 'text'], ['hasGps', 'Has GPS Data', 'bool'], ['virtualCopy', 'Virtual Copy', 'bool'], ['missing', 'Missing File', 'bool'],
  ['width', 'Width', 'num'], ['height', 'Height', 'num'], ['fileSize', 'File Size (bytes)', 'num'],
];

const OPS: Record<Kind, Array<[string, string]>> = {
  num: [['>=', 'is greater than or equal to'], ['<=', 'is less than or equal to'], ['=', 'is'], ['!=', 'is not'], ['>', 'is greater than'], ['<', 'is less than']],
  text: [['contains', 'contains'], ['notContains', "doesn't contain"], ['startsWith', 'starts with'], ['endsWith', 'ends with'], ['=', 'is'], ['!=', 'is not'], ['isEmpty', 'is empty'], ['notEmpty', "isn't empty"]],
  date: [['inLast', 'is in the last (days)'], ['>=', 'is after'], ['<=', 'is before'], ['between', 'is in the range']],
  bool: [['=', 'is']],
  flag: [['=', 'is'], ['!=', 'is not']],
  label: [['=', 'is'], ['!=', 'is not'], ['isEmpty', 'is none']],
  keyword: [['contains', 'contains'], ['=', 'is'], ['notContains', "doesn't contain"]],
  kind: [['=', 'is'], ['!=', 'is not']],
};

const CHOICES: Partial<Record<Kind, Array<[string, string]>>> = {
  bool: [['true', 'true'], ['false', 'false']],
  flag: [['pick', 'flagged'], ['none', 'unflagged'], ['reject', 'rejected']],
  label: [['red', 'Red'], ['yellow', 'Yellow'], ['green', 'Green'], ['blue', 'Blue'], ['purple', 'Purple']],
  kind: [['raw', 'Raw'], ['image', 'Image'], ['tiff', 'TIFF'], ['video', 'Video']],
};

interface Rule { field: string; op: string; value: unknown }

const kindOf = (field: string): Kind => RULE_FIELDS.find((f) => f[0] === field)?.[2] ?? 'text';
const opts = (pairs: Array<[string, string]>, sel: string) => pairs.map(([v, l]) => `<option value="${v}"${v === sel ? ' selected' : ''}>${escapeHtml(l)}</option>`).join('');

class SmartDialog extends Dialog {
  private readonly name = el<HTMLInputElement>('<input class="cv-input" type="text" spellcheck="false">');
  private readonly match = el<HTMLSelectElement>('<select class="cv-select"><option value="all">all</option><option value="any">any</option><option value="none">none</option></select>');
  private readonly rows = el('<div class="fl-rules"></div>');
  private target: CollectionRow | null = null;
  private parent: number | null = null;

  constructor(private readonly ctx: Ctx) {
    super('Create Smart Collection', 640);
    this.field('Name', this.name);
    const head = el('<div class="fl-rules-head">Match <span></span> of the following rules:</div>');
    q(head, 'span').replaceWith(this.match);
    const addBtn = el<HTMLButtonElement>(`<button class="cv-btn" type="button">${icon('plus', 14)} Add Rule</button>`);
    addBtn.addEventListener('click', () => this.addRow({ field: 'rating', op: '>=', value: 3 }));
    this.body.append(head, this.rows, addBtn);
    this.button('Cancel', 'ghost', () => this.close());
    this.button('Save', 'primary', () => void this.save());
  }

  private extra: Record<string, unknown> = {};

  edit(c: CollectionRow | null, parent: number | null, extra: Record<string, unknown> = {}): void {
    this.target = c;
    this.parent = parent;
    this.extra = extra;
    const what = extra.kind === 'published' ? 'Smart Published Collection' : 'Smart Collection';
    this.setTitle(c ? `Edit ${what}: ${c.name}` : `Create ${what}`);
    this.name.value = c?.name ?? 'Smart Collection';
    const rules = (c?.rules as { match?: string; rules?: Rule[] } | null) ?? { match: 'all', rules: [{ field: 'rating', op: '>=', value: 3 }] };
    this.match.value = rules.match ?? 'all';
    this.rows.replaceChildren();
    for (const r of rules.rules ?? []) this.addRow(r);
    this.open(this.name);
  }

  private addRow(r: Rule): void {
    const row = el(`<div class="fl-rule"><select class="cv-select fl-rule-field">${opts(RULE_FIELDS.map(([k, l]) => [k, l]), r.field)}</select><select class="cv-select fl-rule-op"></select><span class="fl-rule-value"></span><button class="cv-icon-btn" type="button" aria-label="Remove Rule">${icon('minus', 14)}</button></div>`);
    const field = q<HTMLSelectElement>(row, '.fl-rule-field');
    const op = q<HTMLSelectElement>(row, '.fl-rule-op');
    const valueHost = q(row, '.fl-rule-value');
    const fill = (keepValue: unknown) => {
      const k = kindOf(field.value);
      const ops = OPS[k];
      op.innerHTML = opts(ops, ops.some(([v]) => v === op.value) ? op.value : ops[0][0]);
      const choices = CHOICES[k];
      const v = keepValue === undefined ? '' : String(Array.isArray(keepValue) ? keepValue.join(',') : keepValue);
      valueHost.innerHTML = choices ? `<select class="cv-select">${opts(choices, v)}</select>` : `<input class="cv-input" type="${k === 'num' ? 'number' : k === 'date' ? 'text' : 'text'}" value="${escapeHtml(v)}" placeholder="${k === 'date' ? 'days, or YYYY-MM-DD' : ''}">`;
    };
    op.innerHTML = opts(OPS[kindOf(r.field)], r.op);
    fill(r.value);
    op.value = r.op;
    field.addEventListener('change', () => fill(undefined));
    q(row, 'button').addEventListener('click', () => row.remove());
    this.rows.appendChild(row);
  }

  private collect(): { match: string; rules: Rule[] } {
    const rules: Rule[] = [];
    for (const row of Array.from(this.rows.children) as HTMLElement[]) {
      const field = q<HTMLSelectElement>(row, '.fl-rule-field').value;
      const op = q<HTMLSelectElement>(row, '.fl-rule-op').value;
      const input = q<HTMLInputElement | HTMLSelectElement>(row, '.fl-rule-value > *');
      const k = kindOf(field);
      let value: unknown = input.value;
      if (k === 'num') value = Number(input.value);
      if (k === 'bool') value = input.value === 'true';
      if (op === 'between') value = String(input.value).split(',').map((s) => s.trim());
      if (op === 'inLast') value = Number(input.value);
      rules.push({ field, op, value });
    }
    return { match: this.match.value, rules };
  }

  private async save(): Promise<void> {
    const rules = this.collect();
    const name = this.name.value.trim() || 'Smart Collection';
    try {
      if (this.target) await this.ctx.api.cmd('collection.update', { id: this.target.id, name, rules });
      else await this.ctx.api.cmd('collection.create', { name, kind: 'smart', rules, parent: this.parent, ...this.extra });
      this.close();
    } catch (err) { this.ctx.fail(err); }
  }
}

let dialog: SmartDialog | null = null;

export function openSmartCollection(ctx: Ctx, c: CollectionRow | null, parent: number | null = null, extra: Record<string, unknown> = {}): void {
  dialog ??= new SmartDialog(ctx);
  dialog.edit(c, parent, extra);
}
