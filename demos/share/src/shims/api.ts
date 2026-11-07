import { engine } from '../engine';

export class EngineError extends Error {
  constructor(message: string, readonly status: number = 400, readonly detail: unknown = null) {
    super(message);
  }
}

export interface CommandResult<T = unknown> { ok: boolean; result: T; revision: number }

export class Api {
  base = '';

  url(path: string): string { return engine.url(path); }

  async cmd<T = unknown>(id: string, params: Record<string, unknown> = {}): Promise<T> {
    return engine.run(id, params) as Promise<T>;
  }
}

export const api = new Api();

export function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
