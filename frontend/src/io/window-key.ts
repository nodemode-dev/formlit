const HEADER = 'X-Formlit-Window-Key';
const STORE = 'formlit-window-key';

let key = '';

function remembered(): string {
  try { return sessionStorage.getItem(STORE) ?? ''; } catch { return ''; }
}

function remember(value: string): void {
  try { sessionStorage.setItem(STORE, value); } catch { return; }
}

export async function loadWindowKey(): Promise<void> {
  const holder = window as unknown as { __FORMLIT_WINDOW_KEY?: unknown };
  const given = holder.__FORMLIT_WINDOW_KEY;
  delete holder.__FORMLIT_WINDOW_KEY;
  if (typeof given === 'string' && given) { key = given; remember(key); return; }
  key = remembered();
  if (key && await socketTicket()) return;
  key = '';
  try {
    const res = await fetch('/api/window/key', { method: 'POST' });
    const body = res.ok ? await res.json() as { key?: unknown } : {};
    if (typeof body.key === 'string' && body.key) { key = body.key; remember(key); return; }
  } catch { key = ''; }
  key = remembered();
}

export const keyHeaders = (): Record<string, string> => (key ? { [HEADER]: key } : {});

export async function socketTicket(): Promise<string> {
  try {
    const res = await fetch('/api/window/ticket', { method: 'POST', headers: keyHeaders() });
    if (!res.ok) return '';
    const body = await res.json() as { ticket?: unknown };
    return typeof body.ticket === 'string' ? body.ticket : '';
  } catch { return ''; }
}
