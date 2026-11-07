type Pack = Record<string, string>;

declare global {
  interface Window { __formlitMedia?: Record<string, Pack> }
}

const loading = new Map<string, Promise<Pack>>();

export function loadPack(name: string): Promise<Pack> {
  const hit = loading.get(name);
  if (hit) return hit;
  const job = new Promise<Pack>((resolve, reject) => {
    const tag = document.createElement('script');
    tag.src = `./assets/media/${name}.js`;
    tag.onload = () => {
      tag.remove();
      const pack = window.__formlitMedia?.[name];
      if (pack) resolve(pack);
      else reject(new Error(`The ${name} photos did not load`));
    };
    tag.onerror = () => {
      tag.remove();
      loading.delete(name);
      reject(new Error(`The ${name} photos did not load`));
    };
    document.head.appendChild(tag);
  });
  loading.set(name, job);
  return job;
}

export function releasePack(name: string): void {
  if (window.__formlitMedia) delete window.__formlitMedia[name];
}

export function jpegSize(b: Uint8Array): [number, number] {
  let o = 2;
  while (o + 9 < b.length) {
    if (b[o] !== 0xff) { o += 1; continue; }
    const m = b[o + 1];
    if (m >= 0xc0 && m <= 0xcf && m !== 0xc4 && m !== 0xc8 && m !== 0xcc) return [(b[o + 7] << 8) | b[o + 8], (b[o + 5] << 8) | b[o + 6]];
    o += 2 + ((b[o + 2] << 8) | b[o + 3]);
  }
  throw new Error('not a JPEG');
}

export function dataBytes(uri: string): Uint8Array<ArrayBuffer> {
  const bin = atob(uri.slice(uri.indexOf(',') + 1));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i);
  return out;
}
