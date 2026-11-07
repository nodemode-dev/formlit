import { srgbToWorking, srgbDecode } from './engine/colour';
import { makeSource, type Source } from './engine/geometry';
import { Renderer } from './engine/render';
import { clone, prune, type Dev } from './engine/settings';
import { largestEmbeddedJpeg, readExif, type Exif } from './exif';
import { SCENES, renderScene } from './data/scenes';

export const MAX_LONG = 3000;
const RAW_EXT = new Set(['dng', 'cr2', 'cr3', 'nef', 'arw', 'orf', 'rw2', 'raf', 'pef', 'srw']);
const SAMPLE_W = 1200, SAMPLE_H = 800;

export interface HistoryEntry { label: string; dev: Dev }

export interface Item {
  id: number; name: string; w: number; h: number; fullW: number; fullH: number; src: Source; bytes: number; sample: boolean; fmt: string; note: string;
  exif: Exif; keywords: string[]; dev: Dev; hist: HistoryEntry[]; hi: number; rating: number; flag: number; label: string; rev: number; added: number;
  thumb: string; preview: string; previewRev: number; thumbRev: number;
}

type Kind = 'list' | 'item' | 'render';
type Fn = (a?: number, b?: string) => void;

const decodeLut = new Float32Array(256);
for (let i = 0; i < 256; i += 1) decodeLut[i] = srgbDecode(i / 255);

export function toLinear(rgba: Uint8ClampedArray, w: number, h: number): Float32Array {
  const m = srgbToWorking;
  const out = new Float32Array(w * h * 3);
  for (let i = 0, j = 0, n = w * h; i < n; i += 1, j += 3) {
    const r = decodeLut[rgba[i * 4]], g = decodeLut[rgba[i * 4 + 1]], b = decodeLut[rgba[i * 4 + 2]];
    out[j] = m[0] * r + m[1] * g + m[2] * b;
    out[j + 1] = m[3] * r + m[4] * g + m[5] * b;
    out[j + 2] = m[6] * r + m[7] * g + m[8] * b;
  }
  return out;
}

function canvasOf(w: number, h: number): HTMLCanvasElement {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  return c;
}

export function toBlob(canvas: HTMLCanvasElement, type: string, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('encode failed'))), type, quality));
}

export class Store {
  readonly items = new Map<number, Item>();
  order: number[] = [];
  private nextId = 1;
  private readonly fns: Record<Kind, Set<Fn>> = { list: new Set(), item: new Set(), render: new Set() };
  readonly thumbRenderer = new Renderer();
  private thumbTimers = new Map<number, number>();
  private queue: Array<() => Promise<void>> = [];
  private running = false;
  clipboard: Dev | null = null;

  listen(kind: Kind, fn: Fn): () => void { this.fns[kind].add(fn); return () => { this.fns[kind].delete(fn); }; }

  emit(kind: Kind, a?: number, b?: string): void { for (const fn of this.fns[kind]) fn(a, b); }

  private enqueue(job: () => Promise<void>): void {
    this.queue.push(job);
    if (this.running) return;
    this.running = true;
    const next = (): void => {
      const j = this.queue.shift();
      if (!j) { this.running = false; return; }
      void j().catch(() => undefined).then(() => window.setTimeout(next, 0));
    };
    window.setTimeout(next, 0);
  }

  private make(name: string, w: number, h: number, fullW: number, fullH: number, lin: Float32Array, bytes: number, sample: boolean, fmt: string, exif: Exif, note: string, keywords: string[]): Item {
    const id = this.nextId++;
    const item: Item = {
      id, name, w, h, fullW, fullH, src: makeSource(id, w, h, lin), bytes, sample, fmt, note, exif, keywords, dev: {}, hist: [{ label: 'Import', dev: {} }], hi: 0,
      rating: 0, flag: 0, label: '', rev: 1, added: Date.now(), thumb: '', preview: '', previewRev: 0, thumbRev: 0,
    };
    this.items.set(id, item);
    this.order.push(id);
    return item;
  }

  addSample(index: number): Promise<Item> {
    const info = SCENES[index];
    return new Promise((resolve) => {
      this.enqueue(async () => {
        const rgba = renderScene(info.id, SAMPLE_W, SAMPLE_H);
        const item = this.make(`${info.name}.jpg`, SAMPLE_W, SAMPLE_H, SAMPLE_W, SAMPLE_H, toLinear(rgba, SAMPLE_W, SAMPLE_H), 0, true, 'JPEG', {
          make: info.make, model: info.model, lens: info.lens, iso: info.iso, exposure: info.shutter, fnumber: info.fnum, focal: info.focal, time: info.time,
        }, 'Procedural sample, generated in this page', info.keywords);
        this.afterAdd(item);
        resolve(item);
      });
    });
  }

  async addFile(file: File): Promise<Item> {
    const ext = (file.name.split('.').pop() || '').toLowerCase();
    const buf = await file.arrayBuffer();
    const exif = readExif(buf);
    let bitmap: ImageBitmap | null = null;
    let note = '';
    let fmt = (ext || 'file').toUpperCase();
    if (RAW_EXT.has(ext)) {
      const got = await largestEmbeddedJpeg(buf);
      if (!got) throw new Error(`${file.name}: no embedded preview found in this RAW file`);
      bitmap = got.bitmap;
      note = 'Embedded JPEG preview of a RAW file; the demo does not demosaic RAW';
      fmt = `${fmt} preview`;
    } else {
      bitmap = await createImageBitmap(new Blob([buf], { type: file.type || 'image/jpeg' }), { imageOrientation: 'from-image' });
    }
    const fullW = bitmap.width, fullH = bitmap.height;
    const k = Math.min(1, MAX_LONG / Math.max(fullW, fullH));
    const w = Math.max(1, Math.round(fullW * k)), h = Math.max(1, Math.round(fullH * k));
    const c = canvasOf(w, h);
    const ctx = c.getContext('2d', { willReadFrequently: true });
    if (!ctx) throw new Error('canvas unavailable');
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(bitmap, 0, 0, w, h);
    bitmap.close();
    const rgba = ctx.getImageData(0, 0, w, h).data;
    if (k < 1) note = note || `Processed at ${w} x ${h}; the original is ${fullW} x ${fullH}`;
    const item = this.make(file.name, w, h, fullW, fullH, toLinear(rgba, w, h), file.size, false, fmt, exif, note, []);
    this.afterAdd(item);
    return item;
  }

  private afterAdd(item: Item): void {
    this.emit('list');
    this.scheduleThumb(item.id, 0);
  }

  scheduleThumb(id: number, delay = 120): void {
    window.clearTimeout(this.thumbTimers.get(id));
    this.thumbTimers.set(id, window.setTimeout(() => {
      this.enqueue(async () => { await this.makeThumb(id); });
    }, delay));
  }

  private async makeThumb(id: number): Promise<void> {
    const item = this.items.get(id);
    if (!item) return;
    const r = this.thumbRenderer.render(item.src, item.dev, 360);
    const c = canvasOf(r.w, r.h);
    c.getContext('2d')?.putImageData(new ImageData(r.rgba, r.w, r.h), 0, 0);
    const blob = await toBlob(c, 'image/jpeg', 0.82);
    if (item.thumb) URL.revokeObjectURL(item.thumb);
    item.thumb = URL.createObjectURL(blob);
    item.thumbRev += 1;
    this.emit('render', id, 't');
  }

  async makePreview(id: number): Promise<void> {
    const item = this.items.get(id);
    if (!item || item.previewRev === item.rev) return;
    const rev = item.rev;
    const r = this.thumbRenderer.render(item.src, item.dev, 1800);
    const c = canvasOf(r.w, r.h);
    c.getContext('2d')?.putImageData(new ImageData(r.rgba, r.w, r.h), 0, 0);
    const blob = await toBlob(c, 'image/jpeg', 0.9);
    if (item.preview) URL.revokeObjectURL(item.preview);
    item.preview = URL.createObjectURL(blob);
    item.previewRev = rev;
    this.emit('render', id, 'p');
  }

  isEdited(item: Item): boolean { return Object.keys(prune(item.dev)).length > 0; }

  commit(item: Item, dev: Dev, label: string): void {
    const next = prune(dev);
    const cur = item.hist[item.hi];
    if (JSON.stringify(next) === JSON.stringify(cur.dev) && label !== 'Import') return;
    item.hist = item.hist.slice(0, item.hi + 1);
    item.hist.push({ label, dev: clone(next) });
    if (item.hist.length > 80) item.hist.shift();
    item.hi = item.hist.length - 1;
    this.apply(item, next);
  }

  apply(item: Item, dev: Dev): void {
    item.dev = clone(dev);
    item.rev += 1;
    this.scheduleThumb(item.id);
    this.emit('item', item.id);
  }

  goto(item: Item, index: number): void {
    const i = Math.max(0, Math.min(item.hist.length - 1, index));
    if (i === item.hi) return;
    item.hi = i;
    this.apply(item, item.hist[i].dev);
  }

  undo(item: Item): boolean { if (item.hi <= 0) return false; this.goto(item, item.hi - 1); return true; }
  redo(item: Item): boolean { if (item.hi >= item.hist.length - 1) return false; this.goto(item, item.hi + 1); return true; }

  setMeta(item: Item, patch: Partial<Pick<Item, 'rating' | 'flag' | 'label'>>): void {
    Object.assign(item, patch);
    this.emit('item', item.id);
  }

  remove(ids: number[]): void {
    for (const id of ids) {
      const it = this.items.get(id);
      if (!it) continue;
      if (it.thumb) URL.revokeObjectURL(it.thumb);
      if (it.preview) URL.revokeObjectURL(it.preview);
      this.items.delete(id);
      this.thumbRenderer.drop(id);
    }
    this.order = this.order.filter((id) => this.items.has(id));
    this.emit('list');
  }
}

export const store = new Store();
