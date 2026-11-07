import { zipStore } from '../../../demo/src/zip';

interface Output { blob: Blob; group: string }

const outputs = new Map<string, Output>();
const urls = new Map<string, string>();

export function unique(path: string): string {
  if (!outputs.has(path)) return path;
  const dot = path.lastIndexOf('.');
  const stem = dot > path.lastIndexOf('/') ? path.slice(0, dot) : path, ext = dot > path.lastIndexOf('/') ? path.slice(dot) : '';
  for (let n = 2; n < 10000; n += 1) if (!outputs.has(`${stem}-${n}${ext}`)) return `${stem}-${n}${ext}`;
  return path;
}

export function putOutput(path: string, blob: Blob, group = ''): string {
  outputs.set(path, { blob, group });
  const old = urls.get(path);
  if (old) { URL.revokeObjectURL(old); urls.delete(path); }
  return path;
}

export function hasOutput(path: string): boolean {
  return outputs.has(path);
}

export function outputUrl(path: string): string {
  const hit = urls.get(path);
  if (hit) return hit;
  const o = outputs.get(path);
  if (!o) return '';
  const u = URL.createObjectURL(o.blob);
  urls.set(path, u);
  return u;
}

export function openable(path: string): boolean {
  const t = outputs.get(path)?.blob.type ?? '';
  return t === 'application/pdf' || t.startsWith('image/') || t === 'text/html';
}

function download(blob: Blob, name: string): void {
  const u = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = u;
  a.download = name;
  a.hidden = true;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(u), 30000);
}

export async function saveOutput(path: string): Promise<void> {
  const o = outputs.get(path);
  if (!o) throw new Error('That file is no longer available');
  const siblings = o.group ? Array.from(outputs.entries()).filter(([, v]) => v.group === o.group) : [];
  if (siblings.length > 1) {
    const entries = await Promise.all(siblings.map(async ([p, v]) => ({ name: p.slice(o.group.length + 1) || p, data: new Uint8Array(await v.blob.arrayBuffer()) })));
    download(zipStore(entries), `${o.group.split('/').pop() ?? 'files'}.zip`);
    return;
  }
  download(o.blob, path.split('/').pop() ?? 'file');
}
