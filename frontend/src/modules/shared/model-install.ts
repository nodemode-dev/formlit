import type { Ctx } from '../../app';
import { EngineError } from '../../io/api';
import { confirmAction } from '../../ui/dialogs';
import { whenDone } from './tasks';

const MAX_INSTALLS = 3;

export interface MissingModel { model: string; name: string; sizeMB: number; license?: string }

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

export async function offerModel(ctx: Ctx, m: MissingModel, what: string): Promise<boolean> {
  const yes = await confirmAction(`Install ${m.name}?`, `${what} needs ${m.name} on this computer (${m.sizeMB} MB, downloaded once and checked against its published SHA-256). Install it now and continue?`, `Install Now (${m.sizeMB} MB)`);
  if (!yes) return false;
  const done = ctx.shell.busy(`Installing ${m.name}`);
  try { return await installModel(ctx, m.model); } finally { done(); }
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
