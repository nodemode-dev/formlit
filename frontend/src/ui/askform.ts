import { Dialog } from './dialogs';
import { el, setText } from './dom';
import { Form, getPath, setPath, type FieldSpec } from './form';

type Values = Record<string, unknown>;

class FormDialog extends Dialog {
  private values: Values = {};
  private form: Form | null = null;
  private resolve: ((v: Values | null) => void) | null = null;
  private readonly lead = el('<p class="cv-note fl-ask-lead"></p>');
  private readonly preview = el('<p class="fl-ask-preview"></p>');
  private readonly ok: HTMLButtonElement;
  private previewFn: ((v: Values) => string) | null = null;

  constructor() {
    super('', 480);
    this.button('Cancel', 'ghost', () => this.finish(null));
    this.ok = this.button('OK', 'primary', () => this.finish(this.values));
    this.onClose = () => this.finish(null);
    this.scrim.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.target as HTMLElement).tagName === 'INPUT') { e.preventDefault(); this.finish(this.values); }
    });
  }

  ask(title: string, lead: string, specs: FieldSpec[], values: Values, okLabel: string, preview?: (v: Values) => string): Promise<Values | null> {
    this.setTitle(title);
    setText(this.ok, okLabel);
    setText(this.lead, lead);
    this.values = JSON.parse(JSON.stringify(values)) as Values;
    this.previewFn = preview ?? null;
    this.body.replaceChildren();
    if (lead) this.body.appendChild(this.lead);
    this.form = new Form(specs, (p) => getPath(this.values, p), (p, v) => { setPath(this.values, p, v); this.form?.sync(); this.paint(); });
    this.body.appendChild(this.form.root);
    if (preview) this.body.appendChild(this.preview);
    this.form.sync();
    this.paint();
    this.open();
    return new Promise((r) => { this.resolve = r; });
  }

  private paint(): void {
    if (this.previewFn) setText(this.preview, this.previewFn(this.values));
  }

  private finish(v: Values | null): void {
    const r = this.resolve;
    this.resolve = null;
    if (this.isOpen) this.close();
    r?.(v);
  }
}

let shared: FormDialog | null = null;

export function askForm(title: string, lead: string, specs: FieldSpec[], values: Values, okLabel = 'OK', preview?: (v: Values) => string): Promise<Values | null> {
  shared ??= new FormDialog();
  return shared.ask(title, lead, specs, values, okLabel, preview);
}
