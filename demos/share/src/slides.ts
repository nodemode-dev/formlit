import { deepMerge, place, type Dict } from './layout';
import { store } from './store';

export const SIZES: Record<string, [number, number]> = { '480p': [854, 480], '720p': [1280, 720], '1080p': [1920, 1080], '4k': [3840, 2160] };

export const DEFAULTS: Dict = {
  fill: false, background: '#0d0d0f', margin: 0.05, stroke: 0, strokeColor: '#ffffff', shadow: true,
  duration: 4, fade: 1, panZoom: 0, random: false, repeat: true,
  caption: { on: false, field: 'title', size: 9, custom: '', color: '#e8e8e8' },
  identity: { on: false, text: '', size: 18, x: 0.5, y: 0.06, color: '#ffffff' },
  intro: { on: false, text: '', seconds: 3 }, ending: { on: false, text: '', seconds: 3 },
  music: { path: '', fit: false, balance: 50 },
  video: { size: '1080p', fps: 30, quality: 'high' },
};

export const TEMPLATES: Dict[] = [
  { id: 'default', name: 'Default', settings: {} },
  { id: 'widescreen', name: 'Widescreen Fill', settings: { fill: true, margin: 0, shadow: false } },
  { id: 'captions', name: 'Caption and Exposure', settings: { caption: { on: true, field: 'exposure', size: 9 }, margin: 0.08 } },
  { id: 'gallery', name: 'Gallery White', settings: { background: '#f2f0ec', margin: 0.09, stroke: 2, strokeColor: '#ffffff', shadow: true, caption: { on: true, field: 'title', size: 9, color: '#333333' } } },
  { id: 'kenburns', name: 'Pan and Zoom', settings: { fill: true, margin: 0, panZoom: 0.6, shadow: false, duration: 5, fade: 1.5 } },
];

export function merged(s: Dict | null | undefined): Dict {
  const out = deepMerge(DEFAULTS, s && typeof s === 'object' ? s : {});
  for (const [key, lo, hi] of [['duration', 0.5, 600], ['fade', 0, 30], ['panZoom', 0, 1]] as Array<[string, number, number]>) {
    const v = Number(out[key]);
    out[key] = Number.isFinite(v) ? Math.min(hi, Math.max(lo, v)) : DEFAULTS[key];
  }
  return out;
}

export function tracks(s: Dict): string[] {
  const m = s.music ?? {};
  const raw: string[] = [...(m.tracks ?? []), ...String(m.path ?? '').split('\n')].map((p) => String(p).trim());
  const out: string[] = [];
  for (const p of raw) if (p && !out.includes(p) && store.audio.has(p)) out.push(p);
  return out.slice(0, 10);
}

export function stillSeconds(pages: Dict[], s: Dict, music: string[]): number {
  const duration = Number(s.duration), fade = Number(s.fade);
  const stills = pages.filter((p) => !p.seconds).length;
  if (!music.length || !s.music?.fit || !stills) return duration;
  const total = music.reduce((t, m) => t + (store.audio.get(m)?.seconds ?? 0), 0);
  if (total <= 0) return duration;
  return Math.max(fade + 0.5, (total + fade * (pages.length - 1)) / stills);
}

export function gains(s: Dict): [number, number] {
  const b = Math.max(0, Math.min(100, Number(s.music?.balance ?? 50)));
  return [Math.min(1, (100 - b) / 50), Math.min(1, b / 50)];
}

function shuffle(ids: number[]): number[] {
  const out = ids.slice();
  let seed = out.length * 2654435761 + 1;
  const next = (): number => { seed = (Math.imul(seed ^ (seed >>> 15), 2246822507) + 0x9e3779b9) >>> 0; return seed / 4294967296; };
  for (let i = out.length - 1; i > 0; i -= 1) { const j = Math.floor(next() * (i + 1)); [out[i], out[j]] = [out[j], out[i]]; }
  return out;
}

export function pageLayout(ids: number[], s: Dict, forPdf: boolean): Dict {
  const [fw, fh] = SIZES[s.video?.size ?? '1080p'] ?? SIZES['1080p'];
  const pw = 10, ph = (10 * fh) / fw;
  const m = Number(s.margin ?? 0.05) * pw;
  const cell = { x: m, y: m, w: pw - 2 * m, h: ph - 2 * m };
  const pages: Dict[] = [];
  let n = 0;
  if (s.intro?.on && s.intro.text) {
    n += 1;
    pages.push({ cells: [], texts: [{ x: 0.5, y: ph / 2 - 0.2, w: pw - 1, h: 1, text: s.intro.text, title: true }], number: n, cover: true });
  }
  for (const pid of s.random ? shuffle(ids) : ids) {
    n += 1;
    const item = place(cell, store.aspect(pid), !!s.fill, false);
    item.photo = pid;
    pages.push({ cells: [item], texts: [], number: n, cover: true });
  }
  if (s.ending?.on && s.ending.text) {
    n += 1;
    pages.push({ cells: [], texts: [{ x: 0.5, y: ph / 2 - 0.2, w: pw - 1, h: 1, text: s.ending.text, title: true }], number: n, cover: true });
  }
  const cap = { ...(s.caption ?? {}) };
  const settings = {
    background: s.background, stroke: s.stroke ?? 0, strokeColor: s.strokeColor, identity: s.identity, caption: cap, textColor: cap.color ?? '#e8e8e8', titleSize: 30, textSize: 14,
    job: { ppi: forPdf ? 150 : fw / pw, space: 'srgb', quality: 90, sharpen: { on: true, for: 'screen', amount: 'standard' } },
  };
  return { page: { w: pw, h: ph }, pages, settings };
}
