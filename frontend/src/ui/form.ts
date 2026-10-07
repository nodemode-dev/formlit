import { el, escapeHtml, q, setChecked, setHidden, setText, setValue } from './dom';

export type FieldKind = 'select' | 'number' | 'check' | 'color' | 'text' | 'password' | 'range' | 'textarea' | 'seg' | 'note';

export interface FieldSpec {
  path: string;
  label: string;
  kind: FieldKind;
  options?: Array<[string, string]> | (() => Array<[string, string]>);
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  placeholder?: string;
  show?: (get: (path: string) => unknown) => boolean;
  wide?: boolean;
}

export function getPath(obj: unknown, path: string): unknown {
  let cur: unknown = obj;
  for (const k of path.split('.')) {
    if (cur === null || cur === undefined) return undefined;
    cur = (cur as Record<string, unknown>)[k];
  }
  return cur;
}

export function setPath(obj: Record<string, unknown>, path: string, value: unknown): void {
  const keys = path.split('.');
  let cur: Record<string, unknown> = obj;
  for (let i = 0; i < keys.length - 1; i += 1) {
    const k = keys[i];
    const next = cur[k];
    if (next === null || typeof next !== 'object') cur[k] = /^\d+$/.test(keys[i + 1]) ? [] : {};
    cur = cur[k] as Record<string, unknown>;
  }
  cur[keys[keys.length - 1]] = value;
}

interface Row { spec: FieldSpec; row: HTMLElement; input: HTMLElement; out?: HTMLElement; optKey: string }

export class Form {
  readonly root = el('<div class="fl-form"></div>');
  private readonly rows: Row[] = [];

  constructor(specs: FieldSpec[], private readonly get: (path: string) => unknown, private readonly set: (path: string, value: unknown, phase: 'input' | 'change') => void) {
    for (const spec of specs) this.add(spec);
  }

  private opts(spec: FieldSpec): Array<[string, string]> {
    return typeof spec.options === 'function' ? spec.options() : spec.options ?? [];
  }

  private add(spec: FieldSpec): void {
    if (spec.kind === 'note') {
      const row = el(`<p class="cv-note fl-form-note"></p>`);
      setText(row, spec.label);
      this.root.appendChild(row);
      this.rows.push({ spec, row, input: row, optKey: '' });
      return;
    }
    const row = el(`<div class="fl-form-row${spec.wide || spec.kind === 'textarea' ? ' is-wide' : ''}${spec.kind === 'check' ? ' is-check' : ''}"><span class="fl-form-label"></span><div class="fl-form-ctl"></div></div>`);
    setText(q(row, '.fl-form-label'), spec.label);
    const ctl = q(row, '.fl-form-ctl');
    let input: HTMLElement;
    let out: HTMLElement | undefined;
    const val = (v: unknown) => (spec.kind === 'number' || spec.kind === 'range' ? Number(v) : v);
    switch (spec.kind) {
      case 'select': {
        const s = el<HTMLSelectElement>('<select class="cv-select"></select>');
        s.addEventListener('change', () => this.set(spec.path, s.value, 'change'));
        input = s;
        break;
      }
      case 'seg': {
        const g = el('<div class="cv-seg fl-seg-sm" role="radiogroup"></div>');
        g.addEventListener('click', (e) => {
          const b = (e.target as HTMLElement).closest<HTMLElement>('button[data-v]');
          if (b) { this.set(spec.path, b.dataset.v, 'change'); this.sync(); }
        });
        input = g;
        break;
      }
      case 'check': {
        const c = el<HTMLInputElement>('<input type="checkbox">');
        c.addEventListener('change', () => this.set(spec.path, c.checked, 'change'));
        input = c;
        break;
      }
      case 'range': {
        const r = el<HTMLInputElement>(`<input class="cv-slider" type="range" min="${spec.min ?? 0}" max="${spec.max ?? 100}" step="${spec.step ?? 1}">`);
        out = el('<span class="fl-form-out"></span>');
        r.addEventListener('input', () => { this.set(spec.path, val(r.value), 'input'); this.paintOut(spec, out as HTMLElement, Number(r.value)); });
        r.addEventListener('change', () => this.set(spec.path, val(r.value), 'change'));
        input = r;
        break;
      }
      case 'textarea': {
        const t = el<HTMLTextAreaElement>(`<textarea class="cv-input fl-form-area" rows="3" spellcheck="true"></textarea>`);
        if (spec.placeholder) t.placeholder = spec.placeholder;
        t.addEventListener('input', () => this.set(spec.path, t.value, 'input'));
        t.addEventListener('change', () => this.set(spec.path, t.value, 'change'));
        input = t;
        break;
      }
      default: {
        const type = spec.kind === 'number' ? 'number' : spec.kind === 'color' ? 'color' : spec.kind === 'password' ? 'password' : 'text';
        const i = el<HTMLInputElement>(`<input class="${spec.kind === 'color' ? 'fl-color' : 'cv-input'}" type="${type}" spellcheck="false">`);
        if (spec.kind === 'number') { if (spec.min !== undefined) i.min = String(spec.min); if (spec.max !== undefined) i.max = String(spec.max); i.step = String(spec.step ?? 1); }
        if (spec.placeholder) i.placeholder = spec.placeholder;
        i.addEventListener('input', () => { if (spec.kind !== 'number' || i.value !== '') this.set(spec.path, val(i.value), 'input'); });
        i.addEventListener('change', () => { if (spec.kind !== 'number' || i.value !== '') this.set(spec.path, val(i.value), 'change'); });
        input = i;
      }
    }
    ctl.appendChild(input);
    if (out) ctl.appendChild(out);
    if (spec.unit && spec.kind !== 'range') ctl.appendChild(el(`<span class="fl-form-unit">${escapeHtml(spec.unit)}</span>`));
    this.root.appendChild(row);
    this.rows.push({ spec, row, input, out, optKey: '' });
  }

  private paintOut(spec: FieldSpec, out: HTMLElement, v: number): void {
    const d = (spec.step ?? 1) < 1 ? ((spec.step ?? 1) < 0.1 ? 2 : 1) : 0;
    setText(out, `${v.toFixed(d)}${spec.unit ?? ''}`);
  }

  sync(): void {
    for (const r of this.rows) {
      const { spec, row, input } = r;
      setHidden(row, spec.show ? !spec.show(this.get) : false);
      if (spec.kind === 'note') continue;
      const v = this.get(spec.path);
      if (spec.kind === 'select' || spec.kind === 'seg') {
        const opts = this.opts(spec);
        const key = opts.map((o) => o.join('=')).join('|');
        if (key !== r.optKey) {
          r.optKey = key;
          input.innerHTML = spec.kind === 'select'
            ? opts.map(([k, l]) => `<option value="${escapeHtml(k)}">${escapeHtml(l)}</option>`).join('')
            : opts.map(([k, l]) => `<button type="button" role="radio" data-v="${escapeHtml(k)}">${escapeHtml(l)}</button>`).join('');
        }
        if (spec.kind === 'select') setValue(input as HTMLSelectElement, String(v ?? ''));
        else for (const b of Array.from(input.querySelectorAll<HTMLElement>('button[data-v]'))) { const on = b.dataset.v === String(v); b.classList.toggle('is-on', on); b.setAttribute('aria-checked', String(on)); }
      } else if (spec.kind === 'check') {
        setChecked(input as HTMLInputElement, !!v);
      } else if (spec.kind === 'textarea') {
        const t = input as HTMLTextAreaElement;
        if (document.activeElement !== t && t.value !== String(v ?? '')) t.value = String(v ?? '');
      } else if (spec.kind === 'color') {
        if (typeof v === 'string' && /^#[0-9a-fA-F]{6}$/.test(v)) setValue(input as HTMLInputElement, v.toLowerCase());
      } else {
        setValue(input as HTMLInputElement, v === undefined || v === null ? '' : String(v));
        if (r.out) this.paintOut(spec, r.out, Number(v ?? 0));
      }
    }
  }
}
