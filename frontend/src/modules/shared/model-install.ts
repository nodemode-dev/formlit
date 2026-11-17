import type { Ctx } from '../../app';
import { EngineError } from '../../io/api';
import { Dialog } from '../../ui/dialogs';
import { el, setText } from '../../ui/dom';
import { whenDone } from './tasks';

const MAX_INSTALLS = 3;

export interface ModelCard { model: string; name: string; sizeMB: number; license?: string }
export interface MissingModel extends ModelCard { choices?: ModelCard[] }

export function missingModel(err: unknown): MissingModel | null {
  if (!(err instanceof EngineError)) return null;
  const m = (err.detail as { missingModel?: MissingModel } | null)?.missingModel;
  return m && typeof m.model === 'string' ? m : null;
}

export async function installModel(ctx: Ctx, model: string): Promise<boolean> {
  const r = await ctx.api.cmd<{ task: number }>('ai.download', { model });
  await whenDone(r.task);
  const list = await ctx.api.cmd<{ models: Array<{ id: string; ready: boolean }> }>('ai.models');
  return list.models.some((m) => m.id === model && m.ready);
}

class ModelChoice extends Dialog {
  private readonly text = el('<p class="cv-note"></p>');
  private readonly small: HTMLButtonElement;
  private readonly best: HTMLButtonElement;
  private picks: [string, string] = ['', ''];
  private resolve: ((v: string | null) => void) | null = null;
  constructor() {
    super('Install', 460);
    this.body.appendChild(this.text);
    this.button('Cancel', 'ghost', () => this.finish(null));
    this.small = this.button('Small and Fast', 'ghost', () => this.finish(this.picks[1]));
    this.best = this.button('Install Now', 'primary', () => this.finish(this.picks[0]));
    this.onClose = () => this.finish(null);
  }
  ask(title: string, text: string, best: ModelCard, small: ModelCard | null): Promise<string | null> {
    this.setTitle(title);
    setText(this.text, text);
    this.picks = [best.model, small?.model ?? ''];
    setText(this.best, `Install Now (${best.sizeMB} MB)`);
    setText(this.small, small ? `Small and Fast (${small.sizeMB} MB)` : '');
    this.small.hidden = !small;
    this.open(this.best);
    return new Promise((r) => { this.resolve = r; });
  }
  private finish(v: string | null): void {
    const r = this.resolve;
    this.resolve = null;
    if (this.isOpen) this.close();
    r?.(v);
  }
}

let choice: ModelChoice | null = null;

function describeOffer(m: MissingModel, what: string): { title: string; text: string; best: ModelCard; small: ModelCard | null } {
  const choices = m.choices?.length ? m.choices : [m];
  const best = choices[0];
  const small = choices.length > 1 ? choices[choices.length - 1] : null;
  const text = small
    ? `${what} works best with ${best.name} (${best.sizeMB} MB). ${small.name} (${small.sizeMB} MB) is smaller and faster but less precise. Each downloads once and is checked against its published SHA-256.`
    : `${what} needs ${best.name} on this computer (${best.sizeMB} MB, downloaded once and checked against its published SHA-256). Install it now and continue?`;
  return { title: `Install ${best.name}?`, text, best, small };
}

export async function offerModel(ctx: Ctx, m: MissingModel, what: string): Promise<boolean> {
  const o = describeOffer(m, what);
  choice ??= new ModelChoice();
  const pick = await choice.ask(o.title, o.text, o.best, o.small);
  if (!pick) return false;
  const name = pick === o.best.model ? o.best.name : o.small?.name ?? pick;
  const done = ctx.shell.busy(`Installing ${name}`);
  try { return await installModel(ctx, pick); } finally { done(); }
}

export async function withModel<T>(ctx: Ctx, what: string, run: () => Promise<T>): Promise<T> {
  for (let tries = 0; ; tries++) {
    try {
      return await run();
    } catch (err) {
      const m = missingModel(err);
      if (!m || tries >= MAX_INSTALLS || !(await offerModel(ctx, m, what))) throw err;
    }
  }
}
