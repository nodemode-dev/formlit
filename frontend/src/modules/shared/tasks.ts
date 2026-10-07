import type { Ctx } from '../../app';
import { api } from '../../io/api';
import { events } from '../../io/events';
import { el, setText } from '../../ui/dom';

type Result = Record<string, unknown>;
const waiting = new Map<number, { ok: (r: Result) => void; fail: (e: Error) => void }>();
let wired = false;

function wire(): void {
  if (wired) return;
  wired = true;
  events.on('task', (e) => {
    const w = waiting.get(Number(e.id));
    if (!w) return;
    if (e.state === 'done') { waiting.delete(Number(e.id)); w.ok((e.result ?? {}) as Result); }
    else if (e.state === 'failed') { waiting.delete(Number(e.id)); w.fail(new Error(String(e.error ?? 'Failed'))); }
  });
}

export function whenDone(task: number): Promise<Result> {
  wire();
  return new Promise((ok, fail) => waiting.set(task, { ok, fail }));
}

export function outputUrl(path: string): string {
  const p = path.replace(/\\/g, '/').replace(/^\/+/, '');
  return api.url(`/api/output/fs/${p.split('/').map(encodeURIComponent).join('/')}`);
}

export function openOutput(path: string): void {
  window.open(outputUrl(path), '_blank', 'noopener');
}

export function actionToast(text: string, actions: Array<[string, () => void]>, ms = 8000): void {
  const root = document.getElementById('toast-root');
  if (!root) return;
  const node = el('<div class="cv-toast fl-toast-act" role="status"><span></span></div>');
  setText(node.firstElementChild, text);
  for (const [label, run] of actions) {
    const b = el<HTMLButtonElement>('<button class="fl-toast-btn" type="button"></button>');
    setText(b, label);
    b.addEventListener('click', () => { run(); node.remove(); });
    node.appendChild(b);
  }
  root.appendChild(node);
  window.setTimeout(() => node.remove(), ms);
}

export async function runOutput(ctx: Ctx, cmd: string, params: Record<string, unknown>, describe: (r: Result) => string): Promise<Result | null> {
  try {
    const start = await ctx.api.cmd<{ task: number }>(cmd, params);
    const r = await whenDone(start.task);
    const path = (r.path as string | undefined) ?? ((r.paths as string[] | undefined)?.[0]);
    const folder = (r.folder as string | undefined) ?? path;
    const acts: Array<[string, () => void]> = [];
    if (path) acts.push(['Open', () => openOutput(path)]);
    if (folder) acts.push(['Show in Folder', () => void ctx.api.cmd('output.reveal', { path: path ?? folder }).catch((e) => ctx.fail(e))]);
    actionToast(describe(r), acts);
    return r;
  } catch (err) {
    ctx.fail(err);
    return null;
  }
}
