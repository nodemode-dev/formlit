import { events } from './shims/events';
import { store } from './store';
import type { Dict } from './layout';

export type Progress = (done: number, total: number, label: string) => void;

let taskSeq = 0;

export function startTask(label: string, job: (progress: Progress) => Promise<Dict>): { task: number } {
  const id = (taskSeq += 1);
  events.emit({ type: 'task', id, state: 'running', label, done: 0, total: 0 });
  const progress: Progress = (done, total, text) => events.emit({ type: 'task', id, state: 'running', label: text || label, done, total });
  window.setTimeout(() => {
    job(progress).then(
      (result) => events.emit({ type: 'task', id, state: 'done', label, result }),
      (err: unknown) => events.emit({ type: 'task', id, state: 'failed', label, error: err instanceof Error ? err.message : String(err) }),
    );
  }, 0);
  return { task: id };
}

export function changed(ids: number[], fields: string[]): void {
  store.revision += 1;
  const photos: Record<string, string[]> = {};
  for (const id of ids) photos[String(id)] = fields;
  events.emit({ type: 'photos.changed', photos, revision: store.revision });
}
