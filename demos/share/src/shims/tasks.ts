import type { Ctx } from '../../../../frontend/src/app';
import { el, setText } from '../../../../frontend/src/ui/dom';
import { errorText } from './api';
import { openable, outputUrl as blobUrl, saveOutput } from '../outputs';
import { events } from './events';

type Result = Record<string, unknown>;
const waiting = new Map<number, { ok: (r: Result) => void; fail: (e: Error) => void }>();
let wired = false;

function wire(): void {
  if (wired) return;
  wired = true;
  events.on('task', (e) => {
    const w = waiting.get(Number(e.id));
    if (!w) return;
    if (e.state === 'done' || e.state === 'cancelled') { waiting.delete(Number(e.id)); w.ok((e.result ?? {}) as Result); }
    else if (e.state === 'failed') { waiting.delete(Number(e.id)); w.fail(new Error(String(e.error ?? 'Failed'))); }
  });
}

export function whenDone(task: number): Promise<Result> {
  wire();
  return new Promise((ok, fail) => waiting.set(task, { ok, fail }));
}

export function outputUrl(path: string): string {
  return blobUrl(path);
}

export function openOutput(path: string): void {
  if (openable(path)) window.open(blobUrl(path), '_blank', 'noopener');
  else void saveOutput(path);
}

export function actionToast(text: string, actions: Array<[string, () => void]>, ms = 9000): void {
  const root = document.getElementById('toast-root');
  if (!root) return;
  const node = el('<div class="cv-toast fl-toast-act" role="status"><span></span></div>');
  setText(node.firstElementChild, text);
  for (const [label, run] of actions) {
    const b = el<HTMLButtonElement>('<button class="fl-toast-btn" type="button"></button>');
    setText(b, label === 'Show in Folder' ? 'Save' : label);
    b.addEventListener('click', () => { run(); node.remove(); });
    node.appendChild(b);
  }
  root.prepend(node);
  window.setTimeout(() => node.remove(), ms);
}

export async function runOutput(ctx: Ctx, cmd: string, params: Record<string, unknown>, describe: (r: Result) => string): Promise<Result | null> {
  try {
    const start = await ctx.api.cmd<{ task: number }>(cmd, params);
    const r = await whenDone(start.task);
    const path = (r.path as string | undefined) ?? ((r.paths as string[] | undefined)?.[0]);
    const acts: Array<[string, () => void]> = [];
    if (path) acts.push(['Open', () => openOutput(path)]);
    if (path) acts.push(['Show in Folder', () => void ctx.api.cmd('output.reveal', { path }).catch((e: unknown) => ctx.fail(errorText(e)))]);
    actionToast(describe(r), acts);
    return r;
  } catch (err) {
    ctx.fail(err);
    return null;
  }
}
