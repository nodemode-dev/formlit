export interface EngineEvent {
  seq?: number;
  type: string;
  revision?: number;
  [key: string]: unknown;
}

type Handler = (e: EngineEvent) => void;

export class Events {
  private readonly handlers = new Map<string, Set<Handler>>();
  connected = true;
  onStatus: ((connected: boolean) => void) | null = null;

  start(): void { return; }

  on(type: string, fn: Handler): () => void {
    let set = this.handlers.get(type);
    if (!set) { set = new Set(); this.handlers.set(type, set); }
    set.add(fn);
    return () => set?.delete(fn);
  }

  emit(e: EngineEvent): void {
    for (const fn of this.handlers.get(e.type) ?? []) fn(e);
    for (const fn of this.handlers.get('*') ?? []) fn(e);
  }
}

export const events = new Events();
