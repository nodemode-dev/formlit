export interface Exif {
  make?: string; model?: string; lens?: string; iso?: number; exposure?: string; fnumber?: number; focal?: number; time?: string; orientation?: number; software?: string;
}

const TAGS: Record<number, keyof Exif> = { 0x010f: 'make', 0x0110: 'model', 0x0131: 'software', 0x0112: 'orientation', 0x829a: 'exposure', 0x829d: 'fnumber', 0x8827: 'iso', 0x9003: 'time', 0x920a: 'focal', 0xa434: 'lens' };

function readTiff(view: DataView, base: number, out: Exif): void {
  const le = view.getUint16(base) === 0x4949;
  const u16 = (o: number): number => view.getUint16(base + o, le);
  const u32 = (o: number): number => view.getUint32(base + o, le);
  if (u16(2) !== 42) return;
  const ascii = (o: number, n: number): string => {
    let s = '';
    for (let i = 0; i < n; i += 1) { const c = view.getUint8(base + o + i); if (c === 0) break; s += String.fromCharCode(c); }
    return s.trim();
  };
  const walk = (ifd: number, depth: number): void => {
    if (depth > 3 || ifd <= 0 || base + ifd + 2 > view.byteLength) return;
    const n = u16(ifd);
    for (let i = 0; i < n; i += 1) {
      const e = ifd + 2 + i * 12;
      if (base + e + 12 > view.byteLength) return;
      const tag = u16(e), type = u16(e + 2), count = u32(e + 4);
      const valOff = count * ({ 1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8 }[type] ?? 1) <= 4 ? e + 8 : u32(e + 8);
      if (tag === 0x8769) { walk(u32(e + 8), depth + 1); continue; }
      const key = TAGS[tag];
      if (!key) continue;
      try {
        if (type === 2) (out as Record<string, unknown>)[key] = ascii(valOff, count);
        else if (type === 3) (out as Record<string, unknown>)[key] = u16(valOff);
        else if (type === 4) (out as Record<string, unknown>)[key] = u32(valOff);
        else if (type === 5) {
          const num = u32(valOff), den = u32(valOff + 4) || 1;
          if (key === 'exposure') out.exposure = num / den >= 1 ? `${(num / den).toFixed(1)} s` : `1/${Math.round(den / num)}`;
          else (out as Record<string, unknown>)[key] = num / den;
        }
      } catch { return; }
    }
  };
  walk(u32(4), 0);
}

export function readExif(buf: ArrayBuffer): Exif {
  const out: Exif = {};
  try {
    const view = new DataView(buf);
    if (view.getUint16(0) === 0xffd8) {
      let o = 2;
      while (o + 4 < view.byteLength) {
        if (view.getUint8(o) !== 0xff) break;
        const marker = view.getUint8(o + 1), len = view.getUint16(o + 2);
        if (marker === 0xe1 && view.getUint32(o + 4) === 0x45786966) { readTiff(view, o + 10, out); break; }
        if (marker === 0xda) break;
        o += 2 + len;
      }
    } else if (view.getUint16(0) === 0x4949 || view.getUint16(0) === 0x4d4d) readTiff(view, 0, out);
  } catch { return out; }
  if (out.time) out.time = out.time.replace(/^(\d{4}):(\d\d):(\d\d) /, '$1-$2-$3T');
  return out;
}

export async function largestEmbeddedJpeg(buf: ArrayBuffer): Promise<{ bitmap: ImageBitmap; bytes: ArrayBuffer } | null> {
  const u8 = new Uint8Array(buf);
  const starts: number[] = [];
  for (let i = 0; i + 3 < u8.length && starts.length < 24; i += 1) if (u8[i] === 0xff && u8[i + 1] === 0xd8 && u8[i + 2] === 0xff) starts.push(i);
  let best: { bitmap: ImageBitmap; bytes: ArrayBuffer } | null = null;
  for (let k = 0; k < starts.length; k += 1) {
    const end = k + 1 < starts.length ? starts[k + 1] : u8.length;
    const slice = buf.slice(starts[k], end);
    try {
      const bm = await createImageBitmap(new Blob([slice], { type: 'image/jpeg' }), { imageOrientation: 'from-image' });
      if (!best || bm.width * bm.height > best.bitmap.width * best.bitmap.height) { best?.bitmap.close(); best = { bitmap: bm, bytes: slice }; } else bm.close();
    } catch { continue; }
  }
  return best;
}
