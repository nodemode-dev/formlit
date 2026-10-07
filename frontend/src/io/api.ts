export class EngineError extends Error {
  constructor(message: string, readonly status: number, readonly detail: unknown = null) {
    super(message);
  }
}

async function failure(r: Response): Promise<EngineError> {
  let detail: unknown = null;
  let message = `${r.status} ${r.statusText}`;
  try {
    detail = await r.json();
    const d = (detail as { detail?: unknown }).detail;
    if (typeof d === 'string') message = d;
    else if (d && typeof d === 'object' && 'message' in (d as object)) message = String((d as { message: unknown }).message);
  } catch {
    message = `${r.status} ${r.statusText}`;
  }
  return new EngineError(message, r.status, detail);
}

export interface CommandResult<T = unknown> { ok: boolean; result: T; revision: number; undo?: string }

export class Api {
  base = '';

  url(path: string): string { return this.base + path; }

  async get<T>(path: string, signal?: AbortSignal): Promise<T> {
    const r = await fetch(this.url(path), { signal });
    if (!r.ok) throw await failure(r);
    return (await r.json()) as T;
  }

  async post<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
    const r = await fetch(this.url(path), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body), signal });
    if (!r.ok) throw await failure(r);
    return (await r.json()) as T;
  }

  async upload<T>(path: string, form: FormData): Promise<T> {
    const r = await fetch(this.url(path), { method: 'POST', body: form });
    if (!r.ok) throw await failure(r);
    return (await r.json()) as T;
  }

  async cmd<T = unknown>(id: string, params: Record<string, unknown> = {}): Promise<T> {
    const r = await this.post<CommandResult<T>>(`/api/commands/${encodeURIComponent(id)}`, params);
    return r.result;
  }

  async binary(path: string, signal?: AbortSignal): Promise<{ buffer: ArrayBuffer; headers: Headers }> {
    const r = await fetch(this.url(path), { signal });
    if (!r.ok) throw await failure(r);
    return { buffer: await r.arrayBuffer(), headers: r.headers };
  }

  async blob(path: string, body: unknown): Promise<Blob> {
    const r = await fetch(this.url(path), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!r.ok) throw await failure(r);
    return r.blob();
  }
}

export const api = new Api();

export function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
