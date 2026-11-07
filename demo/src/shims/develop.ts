import { SPECS, clone, get, getPath, put, setPath, prune, type Dev, type Spec } from '../engine/settings';
import { store, type Item } from '../store';

export { getPath, clone };
export type { Dev };

type Why = 'drag' | 'end' | 'open' | 'history';

export class DevelopSession {
  readonly specs = SPECS as Map<string, Spec>;
  settings: Dev = {};
  item: Item | null = null;
  private readonly fns = new Set<(why: Why) => void>();

  listen(fn: (why: Why) => void): () => void { this.fns.add(fn); return () => { this.fns.delete(fn); }; }

  private emit(why: Why): void { for (const fn of this.fns) fn(why); }

  open(item: Item | null): void {
    this.item = item;
    this.settings = item ? clone(item.dev) : {};
    this.emit('open');
  }

  resync(): void {
    if (!this.item) return;
    this.settings = clone(this.item.dev);
    this.emit('history');
  }

  read(path: string): unknown { return getPath(this.settings, path); }

  value(cid: string): number { return get(this.settings, cid); }

  private finish(phase: 'drag' | 'end', label: string): void {
    if (phase === 'end' && this.item) {
      store.commit(this.item, this.settings, label);
      this.settings = clone(this.item.dev);
    }
    this.emit(phase);
  }

  set(cid: string, v: number, phase: 'drag' | 'end', label?: string): void {
    const spec = SPECS.get(cid);
    put(this.settings, cid, v);
    this.finish(phase, label ?? `${spec?.label ?? cid} ${v > 0 && (spec?.min ?? 0) < 0 ? '+' : ''}${v}`);
  }

  patch(path: string, value: unknown, phase: 'drag' | 'end', label: string): void {
    if (value === null || value === undefined) {
      const parts = path.split('.');
      let cur: Dev | undefined = this.settings;
      for (const p of parts.slice(0, -1)) cur = cur && typeof cur[p] === 'object' ? (cur[p] as Dev) : undefined;
      if (cur) delete cur[parts[parts.length - 1]];
    } else setPath(this.settings, path, clone({ v: value }).v);
    this.finish(phase, label);
  }

  replace(next: Dev, phase: 'drag' | 'end', label: string): void {
    this.settings = prune(clone(next));
    this.finish(phase, label);
  }

  undo(): void { if (this.item && store.undo(this.item)) this.resync(); }
  redo(): void { if (this.item && store.redo(this.item)) this.resync(); }
  goto(i: number): void { if (this.item) { store.goto(this.item, i); this.resync(); } }
}

export const develop = new DevelopSession();
