import { exifPayload, withExifJpeg, withExifPng, withExifWebp, type ExifWrite } from './exif';
import type { Dict } from './layout';

const sources = new Map<number, { bytes: Uint8Array; mime: string }>();
const bitmaps = new Map<number, Promise<ImageBitmap>>();

export function registerSource(id: number, bytes: Uint8Array, mime: string): void {
  sources.set(id, { bytes, mime });
  bitmaps.delete(id);
}

export function dropSource(id: number): void {
  sources.delete(id);
  bitmaps.delete(id);
}

export function bitmapOf(id: number): Promise<ImageBitmap> {
  const hit = bitmaps.get(id);
  if (hit) return hit;
  const src = sources.get(id);
  if (!src) return Promise.reject(new Error('That photo is no longer open'));
  const job = createImageBitmap(new Blob([src.bytes as BlobPart], { type: src.mime }), { imageOrientation: 'from-image' });
  bitmaps.set(id, job);
  return job;
}

export function newCanvas(w: number, h: number): HTMLCanvasElement {
  const c = document.createElement('canvas');
  c.width = Math.max(1, Math.round(w));
  c.height = Math.max(1, Math.round(h));
  return c;
}

export function resample(src: CanvasImageSource & { width: number; height: number }, w: number, h: number): HTMLCanvasElement {
  let cur: CanvasImageSource & { width: number; height: number } = src;
  let cw = src.width, ch = src.height;
  const tw = Math.max(1, Math.round(w)), th = Math.max(1, Math.round(h));
  while (cw / 2 >= tw && ch / 2 >= th) {
    const next = newCanvas(Math.ceil(cw / 2), Math.ceil(ch / 2));
    const g = next.getContext('2d') as CanvasRenderingContext2D;
    g.imageSmoothingQuality = 'high';
    g.drawImage(cur, 0, 0, next.width, next.height);
    cur = next; cw = next.width; ch = next.height;
  }
  const out = newCanvas(tw, th);
  const g = out.getContext('2d') as CanvasRenderingContext2D;
  g.imageSmoothingQuality = 'high';
  g.drawImage(cur, 0, 0, tw, th);
  return out;
}

export function canvasBlob(c: HTMLCanvasElement, mime: string, quality?: number): Promise<Blob> {
  return new Promise((ok, fail) => c.toBlob((b) => (b ? ok(b) : fail(new Error('The browser could not encode that image'))), mime, quality));
}

export async function encodeImage(c: HTMLCanvasElement, fmt: string, quality: number, exif: ExifWrite | null): Promise<Blob> {
  const mime = fmt === 'png' ? 'image/png' : fmt === 'webp' ? 'image/webp' : 'image/jpeg';
  const blob = await canvasBlob(c, mime, fmt === 'png' ? undefined : quality / 100);
  if (!exif) return blob;
  const bytes = new Uint8Array(await blob.arrayBuffer());
  const payload = exifPayload(exif);
  const out = fmt === 'png' ? withExifPng(bytes, payload) : fmt === 'webp' ? withExifWebp(bytes, payload, c.width, c.height) : withExifJpeg(bytes, payload);
  return new Blob([out as BlobPart], { type: mime });
}

const SHARPEN: Record<string, [number, Record<string, number>]> = {
  screen: [0.6, { low: 0.35, standard: 0.6, high: 0.9 }],
  matte: [1, { low: 0.55, standard: 0.85, high: 1.25 }],
  glossy: [0.8, { low: 0.4, standard: 0.65, high: 1 }],
};

function boxBlur(src: Float32Array, w: number, h: number, r: number): Float32Array {
  const tmp = new Float32Array(src.length), out = new Float32Array(src.length);
  const n = 2 * r + 1;
  for (let y = 0; y < h; y += 1) {
    const row = y * w;
    let sum = 0;
    for (let k = -r; k <= r; k += 1) sum += src[row + Math.min(w - 1, Math.max(0, k))];
    for (let x = 0; x < w; x += 1) {
      tmp[row + x] = sum / n;
      sum += src[row + Math.min(w - 1, x + r + 1)] - src[row + Math.max(0, x - r)];
    }
  }
  for (let x = 0; x < w; x += 1) {
    let sum = 0;
    for (let k = -r; k <= r; k += 1) sum += tmp[Math.min(h - 1, Math.max(0, k)) * w + x];
    for (let y = 0; y < h; y += 1) {
      out[y * w + x] = sum / n;
      sum += tmp[Math.min(h - 1, y + r + 1) * w + x] - tmp[Math.max(0, y - r) * w + x];
    }
  }
  return out;
}

export function sharpen(c: HTMLCanvasElement, opts: Dict | undefined, ppi: number): void {
  if (!opts?.on) return;
  const [base, amounts] = SHARPEN[opts.for ?? 'screen'] ?? SHARPEN.screen;
  const sigma = (opts.for ?? 'screen') === 'screen' ? base : base * Math.max(0.5, ppi / 300);
  const amt = amounts[opts.amount ?? 'standard'] ?? 0.6;
  const g = c.getContext('2d', { willReadFrequently: true }) as CanvasRenderingContext2D;
  const img = g.getImageData(0, 0, c.width, c.height);
  const d = img.data;
  const n = c.width * c.height;
  let y: Float32Array = new Float32Array(n);
  for (let i = 0; i < n; i += 1) y[i] = (0.2126 * d[i * 4] + 0.7152 * d[i * 4 + 1] + 0.0722 * d[i * 4 + 2]) / 255;
  const r = Math.max(1, Math.round(Math.sqrt((12 * sigma * sigma) / 3 + 1) / 2));
  let blur = y;
  for (let pass = 0; pass < 3; pass += 1) blur = boxBlur(blur, c.width, c.height, r);
  y = y.map((v, i) => Math.max(-0.25, Math.min(0.25, (v - blur[i]) * amt)));
  for (let i = 0; i < n; i += 1) {
    const add = y[i] * 255;
    d[i * 4] += add; d[i * 4 + 1] += add; d[i * 4 + 2] += add;
  }
  g.putImageData(img, 0, 0);
}

export function adjust(c: HTMLCanvasElement, job: Dict | undefined): void {
  const a = job?.adjust;
  if (!a?.on) return;
  const b = Math.max(-100, Math.min(100, Number(a.brightness ?? 0))) / 100;
  const k = Math.max(-100, Math.min(100, Number(a.contrast ?? 0))) / 100;
  if (!b && !k) return;
  const lut = new Uint8ClampedArray(256);
  for (let i = 0; i < 256; i += 1) {
    let x = i / 255;
    if (b) x **= 2 ** (-b * 0.6);
    if (k) x = Math.max(0, Math.min(1, x - k * 0.08 * Math.sin(2 * Math.PI * x)));
    lut[i] = Math.round(x * 255);
  }
  const g = c.getContext('2d', { willReadFrequently: true }) as CanvasRenderingContext2D;
  const img = g.getImageData(0, 0, c.width, c.height);
  for (let i = 0; i < img.data.length; i += 4) { img.data[i] = lut[img.data[i]]; img.data[i + 1] = lut[img.data[i + 1]]; img.data[i + 2] = lut[img.data[i + 2]]; }
  g.putImageData(img, 0, 0);
}

export interface Tokens { copyright: string; creator: string; title: string; name: string; year: string; caption: string }

export function expandTokens(text: string, t: Tokens): string {
  let out = text;
  for (const [k, v] of Object.entries(t)) out = out.split(`{${k}}`).join(v);
  return out.trim();
}

const ANCHORS: Record<string, [number, number]> = { tl: [0, 0], t: [0.5, 0], tr: [1, 0], l: [0, 0.5], c: [0.5, 0.5], r: [1, 0.5], bl: [0, 1], b: [0.5, 1], br: [1, 1] };

export function watermark(c: HTMLCanvasElement, wm: Dict, tokens: Tokens): void {
  if (!wm.on) return;
  const long = Math.max(c.width, c.height);
  const inset = Math.trunc(Number(wm.inset ?? 0.025) * long);
  const opacity = Number(wm.opacity ?? 0.7);
  const text = expandTokens(String(wm.text ?? ''), tokens);
  if (!text) return;
  const px = Math.max(8, Math.trunc(Number(wm.size ?? 0.035) * long));
  const g = c.getContext('2d') as CanvasRenderingContext2D;
  g.font = `${px}px sans-serif`;
  const m = g.measureText(text);
  const aw = Math.ceil(m.width) + 4, ah = Math.ceil(m.actualBoundingBoxAscent + m.actualBoundingBoxDescent) + 4;
  if (aw > c.width || ah > c.height) return;
  const [fx, fy] = ANCHORS[wm.anchor ?? 'br'] ?? [1, 1];
  const x = Math.max(0, Math.min(c.width - aw, Math.round(inset + (c.width - aw - 2 * inset) * fx)));
  const y = Math.max(0, Math.min(c.height - ah, Math.round(inset + (c.height - ah - 2 * inset) * fy)));
  g.save();
  g.textBaseline = 'alphabetic';
  g.globalAlpha = opacity;
  if (wm.shadow !== false) {
    g.shadowColor = `rgba(0,0,0,${(0.55).toFixed(2)})`;
    g.shadowBlur = Math.max(2, px / 9);
    g.shadowOffsetX = g.shadowOffsetY = Math.max(1, ah / 24);
  }
  g.fillStyle = String(wm.color ?? '#ffffff');
  g.fillText(text, x + 2, y + 2 + m.actualBoundingBoxAscent);
  g.restore();
}

export function scaleFor(nw: number, nh: number, size: Dict): number {
  if (!size.resize) return 1;
  const long = Math.max(nw, nh), short = Math.min(nw, nh);
  let s: number;
  switch (size.mode ?? 'long') {
    case 'long': s = Number(size.value ?? 2048) / long; break;
    case 'short': s = Number(size.value ?? 2048) / short; break;
    case 'wh': s = Math.min(Number(size.w ?? 2048) / nw, Number(size.h ?? 2048) / nh); break;
    case 'dims': { const a = Number(size.w ?? 2048), b = Number(size.h ?? 2048); s = Math.min(Math.max(a, b) / long, Math.min(a, b) / short); break; }
    case 'mp': s = Math.sqrt((Number(size.mp ?? 12) * 1e6) / Math.max(1, nw * nh)); break;
    case 'percent': s = Number(size.percent ?? 100) / 100; break;
    default: s = 1;
  }
  return size.noEnlarge === false ? s : Math.min(s, 1);
}

export async function renderPhoto(id: number, size: Dict): Promise<HTMLCanvasElement> {
  const bmp = await bitmapOf(id);
  const k = scaleFor(bmp.width, bmp.height, size);
  return resample(bmp, bmp.width * k, bmp.height * k);
}

const FAMILY: Record<string, string> = { sans: "Helvetica, Arial, 'Liberation Sans', sans-serif", serif: "'Times New Roman', 'Liberation Serif', Times, serif", mono: "'Courier New', 'Liberation Mono', monospace" };
let ruler: CanvasRenderingContext2D | null = null;

export function fontCss(family: string, bold: boolean, italic: boolean, px: number): string {
  return `${italic ? 'italic ' : ''}${bold ? 'bold ' : ''}${px}px ${FAMILY[family] ?? FAMILY.sans}`;
}

export function textWidth(text: string, family: string, bold: boolean, italic: boolean, size: number): number {
  ruler ??= newCanvas(8, 8).getContext('2d') as CanvasRenderingContext2D;
  ruler.font = fontCss(family, bold, italic, 100);
  return (ruler.measureText(text).width * size) / 100;
}

export function wrapText(text: string, family: string, bold: boolean, italic: boolean, size: number, width: number): string[] {
  const out: string[] = [];
  for (const para of text.split('\n')) {
    let line = '';
    for (const word of para.split(/\s+/).filter(Boolean)) {
      const next = line ? `${line} ${word}` : word;
      if (line && textWidth(next, family, bold, italic, size) > width) { out.push(line); line = word; } else line = next;
    }
    out.push(line);
  }
  return out;
}

export interface CellRaster { canvas: HTMLCanvasElement; x: number; y: number; w: number; h: number }

export async function cellRaster(photo: number, cell: Dict, ppi: number, sharpenOpts: Dict | undefined, job: Dict | undefined): Promise<CellRaster | null> {
  const img = cell.img;
  if (!img) return null;
  const bmp = await bitmapOf(photo);
  const rot = !!cell.rot;
  let wpx = img.w * ppi, hpx = img.h * ppi;
  const k = Math.min(1, (rot ? bmp.height : bmp.width) / wpx);
  wpx = Math.max(2, Math.round(wpx * k));
  hpx = Math.max(2, Math.round(hpx * k));
  const full = newCanvas(wpx, hpx);
  const g = full.getContext('2d') as CanvasRenderingContext2D;
  g.imageSmoothingQuality = 'high';
  if (rot) {
    const scaled = resample(bmp, hpx, wpx);
    g.translate(wpx / 2, hpx / 2);
    g.rotate(Math.PI / 2);
    g.drawImage(scaled, -hpx / 2, -wpx / 2);
  } else g.drawImage(resample(bmp, wpx, hpx), 0, 0);
  sharpen(full, sharpenOpts, Math.round(ppi));
  adjust(full, job);
  const x0 = Math.max(cell.x, img.x), y0 = Math.max(cell.y, img.y);
  const x1 = Math.min(cell.x + cell.w, img.x + img.w), y1 = Math.min(cell.y + cell.h, img.y + img.h);
  if (x1 <= x0 || y1 <= y0) return null;
  const px0 = Math.round(((x0 - img.x) / img.w) * wpx), py0 = Math.round(((y0 - img.y) / img.h) * hpx);
  const px1 = Math.max(px0 + 1, Math.round(((x1 - img.x) / img.w) * wpx)), py1 = Math.max(py0 + 1, Math.round(((y1 - img.y) / img.h) * hpx));
  const crop = newCanvas(px1 - px0, py1 - py0);
  (crop.getContext('2d') as CanvasRenderingContext2D).drawImage(full, px0, py0, px1 - px0, py1 - py0, 0, 0, px1 - px0, py1 - py0);
  return { canvas: crop, x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

export interface Overlay { x: number; y: number; size: number; text: string; align: string; color: string; wrap?: number; font?: string; bold?: boolean; italic?: boolean; rotate?: number }

export async function rasterPage(lay: Dict, page: Dict, ppi: number): Promise<HTMLCanvasElement> {
  const s = lay.settings, job = s.job ?? {};
  const pw = page.w ?? lay.page.w, ph = page.h ?? lay.page.h;
  const c = newCanvas(pw * ppi, ph * ppi);
  const g = c.getContext('2d') as CanvasRenderingContext2D;
  g.fillStyle = s.background ?? '#ffffff';
  g.fillRect(0, 0, c.width, c.height);
  for (const cell of page.cells as Dict[]) {
    if (cell.photo === null || cell.photo === undefined) continue;
    const got = await cellRaster(Number(cell.photo), cell, ppi, job.sharpen, job);
    if (!got) continue;
    g.imageSmoothingQuality = 'high';
    g.drawImage(got.canvas, got.x * ppi, got.y * ppi, got.w * ppi, got.h * ppi);
    const stroke = Number(s.stroke ?? 0);
    if (stroke > 0) {
      const sp = Math.max(1, Math.round((stroke / 72) * ppi));
      g.strokeStyle = s.strokeColor ?? '#000000';
      g.lineWidth = sp;
      g.strokeRect(got.x * ppi + sp / 2, got.y * ppi + sp / 2, got.w * ppi - sp, got.h * ppi - sp);
    }
  }
  for (const t of (page.overlays ?? []) as Overlay[]) {
    const px = Math.max(6, (t.size / 72) * ppi);
    g.font = fontCss(t.font ?? 'sans', !!(t.bold ?? t.size >= 20), !!t.italic, px);
    g.fillStyle = t.color;
    g.textAlign = t.align === 'center' ? 'center' : t.align === 'right' ? 'right' : 'left';
    g.textBaseline = 'alphabetic';
    if (t.rotate) {
      g.save();
      g.translate(t.x * ppi, t.y * ppi);
      g.rotate((t.rotate * Math.PI) / 180);
      g.textAlign = 'center';
      g.fillText(t.text, 0, px * 0.35);
      g.restore();
      continue;
    }
    const lines = t.wrap ? wrapText(t.text, t.font ?? 'sans', !!(t.bold ?? t.size >= 20), !!t.italic, t.size, t.wrap) : [t.text];
    lines.forEach((line, i) => g.fillText(line, t.x * ppi, t.y * ppi + i * px * 1.3));
  }
  return c;
}
