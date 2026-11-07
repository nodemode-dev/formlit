import { PLACES, type Place } from './gazetteer';

interface Style { label: string; url: (z: number, x: number, y: number) => string; attr: string; max: number; overlay?: (z: number, x: number, y: number) => string; cls?: string }

const TILE = 256;
const CREDIT = 'Blue Marble Next Generation, NASA Earth Observatory (public domain)';
let base: ImageData | null = null;
const cache = new Map<string, string>();

export function setBasemap(data: ImageData): void {
  base = data;
  cache.clear();
}

function remember(key: string, make: () => string): string {
  const hit = cache.get(key);
  if (hit !== undefined) return hit;
  const out = make();
  cache.set(key, out);
  if (cache.size > 600) cache.delete(cache.keys().next().value as string);
  return out;
}

function lonOf(px: number, n: number): number { return (px / n) * 360 - 180; }
function latOf(py: number, n: number): number { const t = Math.PI * (1 - (2 * py) / n); return (Math.atan(Math.sinh(t)) * 180) / Math.PI; }
function pxOf(lon: number, lat: number, n: number): [number, number] {
  const s = Math.sin((Math.max(-85.0511, Math.min(85.0511, lat)) * Math.PI) / 180);
  return [((lon + 180) / 360) * n, (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * n];
}

type Look = 'satellite' | 'road' | 'topo' | 'light' | 'dark';

function sample(look: Look, z: number, tx: number, ty: number): HTMLCanvasElement {
  const c = document.createElement('canvas');
  c.width = TILE;
  c.height = TILE;
  const g = c.getContext('2d', { willReadFrequently: true }) as CanvasRenderingContext2D;
  const out = g.createImageData(TILE, TILE);
  if (!base) { g.putImageData(out, 0, 0); return c; }
  const n = TILE * 2 ** z, W = base.width, H = base.height, src = base.data;
  const sx = new Float32Array(TILE), sy = new Float32Array(TILE);
  for (let i = 0; i < TILE; i += 1) {
    sx[i] = ((lonOf(tx * TILE + i, n) + 180) / 360) * (W - 1);
    sy[i] = ((90 - latOf(ty * TILE + i, n)) / 180) * (H - 1);
  }
  const d = out.data;
  for (let j = 0; j < TILE; j += 1) {
    const fy = Math.max(0, Math.min(H - 1.001, sy[j])), y0 = Math.floor(fy), ay = fy - y0;
    for (let i = 0; i < TILE; i += 1) {
      const fx = ((sx[i] % (W - 1)) + (W - 1)) % (W - 1), x0 = Math.floor(fx), ax = fx - x0;
      const a = (y0 * W + x0) * 4, b = a + 4, c2 = a + W * 4, e = c2 + 4;
      const o = (j * TILE + i) * 4;
      let r = 0, gg = 0, bb = 0;
      for (let k = 0; k < 3; k += 1) {
        const v = (src[a + k] * (1 - ax) + src[b + k] * ax) * (1 - ay) + (src[c2 + k] * (1 - ax) + src[e + k] * ax) * ay;
        if (k === 0) r = v; else if (k === 1) gg = v; else bb = v;
      }
      const lum = 0.299 * r + 0.587 * gg + 0.114 * bb;
      const water = bb > r + 14 && bb >= gg * 0.92 && lum < 130;
      let R = r, G = gg, B = bb;
      if (look === 'road') {
        if (water) { R = 196; G = 218; B = 232; } else { R = 238; G = 234; B = 224; if (lum > 205 && Math.max(r, gg, bb) - Math.min(r, gg, bb) < 40) { R = 250; G = 250; B = 250; } else if (gg > r + 6) { R = 226; G = 232; B = 214; } }
      } else if (look === 'topo') {
        if (water) { R = 150; G = 190; B = 214; } else { const k = Math.min(1, Math.max(0, (lum - 40) / 150)); R = 150 + 90 * k; G = 170 + 60 * k; B = 110 + 70 * k; if (lum > 205 && Math.max(r, gg, bb) - Math.min(r, gg, bb) < 40) { R = 246; G = 246; B = 246; } }
      } else if (look === 'light') {
        const v = water ? 214 : 244 - Math.max(0, 140 - lum) * 0.18;
        R = v - (water ? 8 : 0); G = v - (water ? 2 : 0); B = v + (water ? 8 : 0);
      } else if (look === 'dark') {
        const v = water ? 14 : 34 + Math.min(40, lum * 0.22);
        R = v; G = v + 2; B = v + (water ? 8 : 6);
      } else {
        R = Math.min(255, (r - 128) * 1.08 + 128 + 4); G = Math.min(255, (gg - 128) * 1.08 + 128 + 4); B = Math.min(255, (bb - 128) * 1.08 + 128 + 6);
      }
      d[o] = R; d[o + 1] = G; d[o + 2] = B; d[o + 3] = 255;
    }
  }
  g.putImageData(out, 0, 0);
  return c;
}

function labels(g: CanvasRenderingContext2D, z: number, tx: number, ty: number, ink: string, halo: string): void {
  const n = TILE * 2 ** z;
  const wanted: Place[] = PLACES.filter((p) => p.z <= z);
  g.textBaseline = 'middle';
  for (const p of wanted) {
    const [px, py] = pxOf(p.lon, p.lat, n);
    const x = px - tx * TILE, y = py - ty * TILE;
    const size = p.kind === 'country' ? 12 : p.kind === 'sea' ? 12 : 11;
    g.font = `${p.kind === 'sea' ? 'italic ' : p.kind === 'country' ? '600 ' : ''}${size}px system-ui, sans-serif`;
    const text = p.kind === 'country' || p.kind === 'sea' ? p.name.toUpperCase() : p.name;
    const w = g.measureText(text).width;
    const centered = p.kind === 'country' || p.kind === 'sea';
    const left = centered ? x - w / 2 : x + 6;
    if (left > TILE + 4 || left + w < -4 || y < -14 || y > TILE + 14) continue;
    g.lineWidth = 3;
    g.strokeStyle = halo;
    g.fillStyle = ink;
    g.strokeText(text, left, y);
    g.fillText(text, left, y);
    if (!centered) { g.beginPath(); g.arc(x, y, 2.2, 0, Math.PI * 2); g.fill(); }
  }
}

function graticule(g: CanvasRenderingContext2D, z: number, tx: number, ty: number, color: string): void {
  const n = TILE * 2 ** z;
  const step = z < 3 ? 30 : z < 5 ? 10 : 5;
  g.strokeStyle = color;
  g.lineWidth = 1;
  g.beginPath();
  for (let lon = -180; lon <= 180; lon += step) {
    const x = Math.round(pxOf(lon, 0, n)[0] - tx * TILE) + 0.5;
    if (x >= -1 && x <= TILE + 1) { g.moveTo(x, 0); g.lineTo(x, TILE); }
  }
  for (let lat = -80; lat <= 80; lat += step) {
    const y = Math.round(pxOf(0, lat, n)[1] - ty * TILE) + 0.5;
    if (y >= -1 && y <= TILE + 1) { g.moveTo(0, y); g.lineTo(TILE, y); }
  }
  g.stroke();
}

function base64(look: Look, withLabels: boolean, z: number, tx: number, ty: number): string {
  return remember(`${look}/${withLabels}/${z}/${tx}/${ty}`, () => {
    const c = sample(look, z, tx, ty);
    const g = c.getContext('2d') as CanvasRenderingContext2D;
    const dark = look === 'dark';
    graticule(g, z, tx, ty, dark ? 'rgba(255,255,255,0.07)' : look === 'satellite' ? 'rgba(255,255,255,0.14)' : 'rgba(40,50,60,0.12)');
    if (withLabels) labels(g, z, tx, ty, dark ? '#d8dde3' : '#2b3138', dark ? 'rgba(10,12,14,0.85)' : 'rgba(255,255,255,0.9)');
    return c.toDataURL('image/jpeg', 0.86);
  });
}

function overlay(z: number, tx: number, ty: number): string {
  return remember(`overlay/${z}/${tx}/${ty}`, () => {
    const c = document.createElement('canvas');
    c.width = TILE;
    c.height = TILE;
    const g = c.getContext('2d') as CanvasRenderingContext2D;
    labels(g, z, tx, ty, '#ffffff', 'rgba(8,12,18,0.78)');
    return c.toDataURL('image/png');
  });
}

export const OFFLINE_STYLES: Record<string, Style> = {
  hybrid: { label: 'Hybrid', url: (z, x, y) => base64('satellite', false, z, x, y), overlay: (z, x, y) => overlay(z, x, y), attr: `${CREDIT}; place names from a small built-in list`, max: 6 },
  road: { label: 'Road Map', url: (z, x, y) => base64('road', true, z, x, y), attr: `Land and sea shapes from ${CREDIT}`, max: 6 },
  satellite: { label: 'Satellite', url: (z, x, y) => base64('satellite', false, z, x, y), attr: CREDIT, max: 6 },
  topo: { label: 'Terrain', url: (z, x, y) => base64('topo', true, z, x, y), attr: `Shading from ${CREDIT}`, max: 6 },
  light: { label: 'Light', url: (z, x, y) => base64('light', true, z, x, y), attr: `Land and sea shapes from ${CREDIT}`, max: 6, cls: 'is-light' },
  dark: { label: 'Dark', url: (z, x, y) => base64('dark', true, z, x, y), attr: `Land and sea shapes from ${CREDIT}`, max: 6, cls: 'is-dark' },
};
