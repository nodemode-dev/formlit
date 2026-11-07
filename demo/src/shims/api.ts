import { store } from '../store';

const BLANK = 'data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==';
const inflight = new Map<number, Promise<void>>();

function ensurePreview(id: number): void {
  const item = store.items.get(id);
  if (!item || item.previewRev === item.rev || inflight.has(id)) return;
  const job = store.makePreview(id).catch(() => undefined).then(() => { inflight.delete(id); });
  inflight.set(id, job);
}

export const api = {
  url(path: string): string {
    const m = /\/api\/photos\/(\d+)\/(thumb|preview|full)/.exec(path);
    if (!m) return BLANK;
    const item = store.items.get(Number(m[1]));
    if (!item) return BLANK;
    if (m[2] === 'thumb') return item.thumb || BLANK;
    ensurePreview(item.id);
    return item.preview || item.thumb || BLANK;
  },
  async cmd<T = unknown>(): Promise<T> {
    throw new Error('The demo has no engine; commands run in the page');
  },
};
