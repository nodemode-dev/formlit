import { api } from './api';

export interface EngineEvent {
  seq?: number;
  type: string;
  revision?: number;
  [key: string]: unknown;
}

type Handler = (e: EngineEvent) => void;

export class Events {
  private source: EventSource | null = null;
  private readonly handlers = new Map<string, Set<Handler>>();
  private lastSeq = 0;
  connected = false;
  onStatus: ((connected: boolean) => void) | null = null;

  start(): void {
    if (this.source) return;
    const src = new EventSource(api.url('/api/events'));
    this.source = src;
    src.onopen = () => this.status(true);
    src.onerror = () => this.status(false);
    src.onmessage = (m) => {
      let e: EngineEvent;
      try { e = JSON.parse(m.data) as EngineEvent; } catch { return; }
      if (e.type === 'hello') {
        const resync = this.lastSeq > 0;
        this.emit({ type: resync ? 'resync' : 'hello', revision: e.revision });
        return;
      }
      if (typeof e.seq === 'number') this.lastSeq = e.seq;
      this.emit(e);
    };
  }

  on(type: string, fn: Handler): () => void {
    let set = this.handlers.get(type);
    if (!set) { set = new Set(); this.handlers.set(type, set); }
    set.add(fn);
    return () => set?.delete(fn);
  }

  private emit(e: EngineEvent): void {
    for (const fn of this.handlers.get(e.type) ?? []) fn(e);
    for (const fn of this.handlers.get('*') ?? []) fn(e);
  }

  private status(on: boolean): void {
    if (this.connected === on) return;
    this.connected = on;
    this.onStatus?.(on);
  }
}

export const events = new Events();
