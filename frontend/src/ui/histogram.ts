import { el, q } from './dom';

export interface Bins { r: Uint32Array; g: Uint32Array; b: Uint32Array }

const N = 128;

export function binsOf(data: Uint8ClampedArray | Uint8Array, stride = 4): Bins {
  const r = new Uint32Array(N), g = new Uint32Array(N), b = new Uint32Array(N);
  for (let i = 0; i + 2 < data.length; i += stride) {
    r[data[i] >> 1] += 1;
    g[data[i + 1] >> 1] += 1;
    b[data[i + 2] >> 1] += 1;
  }
  return { r, g, b };
}

export class Histogram {
  readonly root: HTMLElement;
  private readonly canvas: HTMLCanvasElement;
  private readonly scratch = document.createElement('canvas');
  private seq = 0;
  private last: Bins | null = null;
  private hdr: { bins: number[]; stops: number } | null = null;
  clipShadows = 0;
  clipHighlights = 0;

  setHdr(bins: number[] | null, stops = 0): void {
    const next = bins && bins.length && stops > 0 ? { bins, stops } : null;
    if (JSON.stringify(next) === JSON.stringify(this.hdr)) return;
    this.hdr = next;
    if (this.last) this.draw(this.last);
  }

  constructor(cls = '') {
    this.root = el(`<div class="fl-hist ${cls}"><canvas width="512" height="200"></canvas></div>`);
    this.canvas = q<HTMLCanvasElement>(this.root, 'canvas');
    new ResizeObserver(() => { if (this.last) this.draw(this.last); }).observe(this.root);
  }

  async fromUrl(url: string): Promise<void> {
    const seq = ++this.seq;
    const img = new Image();
    img.decoding = 'async';
    img.src = url;
    try { await img.decode(); } catch { return; }
    if (seq !== this.seq) return;
    this.fromImage(img);
  }

  fromImage(img: CanvasImageSource & { width: number; height: number }): void {
    const s = Math.min(1, 256 / Math.max(img.width, img.height));
    const w = Math.max(1, Math.round(img.width * s)), h = Math.max(1, Math.round(img.height * s));
    this.scratch.width = w;
    this.scratch.height = h;
    const c = this.scratch.getContext('2d', { willReadFrequently: true });
    if (!c) return;
    c.drawImage(img, 0, 0, w, h);
    this.draw(binsOf(c.getImageData(0, 0, w, h).data));
  }

  draw(bins: Bins): void {
    this.last = bins;
    const c = this.canvas.getContext('2d');
    if (!c) return;
    const W = this.canvas.width, H = this.canvas.height;
    c.clearRect(0, 0, W, H);
    let max = 1;
    const smooth = (a: Uint32Array) => Array.from(a, (_, i) => (a[Math.max(0, i - 1)] + 2 * a[i] + a[Math.min(N - 1, i + 1)]) / 4);
    const ch = [smooth(bins.r), smooth(bins.g), smooth(bins.b)];
    const sorted = ch.flat().slice().sort((x, y) => x - y);
    max = Math.max(1, sorted[Math.floor(sorted.length * 0.995)] * 1.08);
    const Ws = this.hdr ? W * 0.72 : W;
    c.globalCompositeOperation = 'lighter';
    const colors = ['rgba(225,70,70,0.75)', 'rgba(70,200,90,0.7)', 'rgba(70,120,240,0.8)'];
    ch.forEach((v, k) => {
      c.beginPath();
      c.moveTo(0, H);
      for (let i = 0; i < N; i += 1) c.lineTo((i / (N - 1)) * Ws, H - Math.min(1, v[i] / max) * (H - 4));
      c.lineTo(Ws, H);
      c.closePath();
      c.fillStyle = colors[k];
      c.fill();
    });
    c.globalCompositeOperation = 'source-over';
    c.strokeStyle = 'rgba(255,255,255,0.08)';
    c.lineWidth = 1;
    for (let i = 1; i < 4; i += 1) { c.beginPath(); c.moveTo((i / 4) * Ws + 0.5, 0); c.lineTo((i / 4) * Ws + 0.5, H); c.stroke(); }
    if (this.hdr) {
      const { bins: hb, stops } = this.hdr;
      c.fillStyle = 'rgba(255,255,255,0.05)';
      c.fillRect(Ws, 0, W - Ws, H);
      const hmax = Math.max(1, ...hb.map((x) => x * 1.08));
      const top = Math.max(max / 3, hmax);
      c.beginPath();
      c.moveTo(Ws, H);
      hb.forEach((v, i) => c.lineTo(Ws + ((i + 0.5) / hb.length) * (W - Ws), H - Math.min(1, v / top) * (H - 4)));
      c.lineTo(W, H);
      c.closePath();
      c.fillStyle = 'rgba(235,235,245,0.55)';
      c.fill();
      c.strokeStyle = 'rgba(255,255,255,0.35)';
      c.beginPath(); c.moveTo(Ws + 0.5, 0); c.lineTo(Ws + 0.5, H); c.stroke();
      c.strokeStyle = 'rgba(255,255,255,0.1)';
      for (let s = 1; s < stops; s += 1) { const x = Ws + (s / stops) * (W - Ws); c.beginPath(); c.moveTo(x + 0.5, 0); c.lineTo(x + 0.5, H); c.stroke(); }
      c.fillStyle = 'rgba(255,255,255,0.55)';
      c.font = `600 ${Math.round(H * 0.11)}px Inter, sans-serif`;
      c.fillText('HDR', Ws + 6, Math.round(H * 0.14));
    }
    this.clipShadows = bins.r[0] + bins.g[0] + bins.b[0];
    this.clipHighlights = bins.r[N - 1] + bins.g[N - 1] + bins.b[N - 1];
  }
}
