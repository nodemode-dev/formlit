import doc from '../../../shared/controls.json';

export type Dev = Record<string, unknown>;
export interface Spec { id: string; label: string; section: string; min: number; max: number; default: number; step: number; decimals: number; track?: { kind: string; band?: number; from?: string; to?: string } }

export const SPECS = new Map<string, Spec>((doc.controls as Spec[]).map((c) => [c.id, c]));
export const DOC = doc as unknown as { controls: Spec[]; mixerBands: Array<{ id: string; label: string; hue: number }>; aspects: Array<{ id: string; label: string; ratio: number[] | null }>; wbPresets: unknown[] };
export const BANDS = ['red', 'orange', 'yellow', 'green', 'aqua', 'blue', 'purple', 'magenta'];

export function getPath(obj: unknown, path: string): unknown {
  let cur: unknown = obj;
  for (const p of path.split('.')) {
    if (!cur || typeof cur !== 'object') return undefined;
    cur = (cur as Record<string, unknown>)[p];
  }
  return cur;
}

export function setPath(obj: Dev, path: string, value: unknown): void {
  const parts = path.split('.');
  let cur = obj;
  for (const p of parts.slice(0, -1)) {
    if (!cur[p] || typeof cur[p] !== 'object') cur[p] = {};
    cur = cur[p] as Dev;
  }
  cur[parts[parts.length - 1]] = value;
}

export const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v ?? {})) as T;

export function get(dev: Dev, cid: string): number {
  const spec = SPECS.get(cid);
  if (!spec) return 0;
  const v = getPath(dev, cid);
  return typeof v === 'number' && Number.isFinite(v) ? v : spec.default;
}

export function clamp(cid: string, value: number): number {
  const s = SPECS.get(cid);
  if (!s || !Number.isFinite(value)) return s?.default ?? 0;
  return Math.min(Math.max(value, s.min), s.max);
}

export function put(dev: Dev, cid: string, value: number): void {
  const s = SPECS.get(cid);
  if (!s) return;
  const v = clamp(cid, value);
  setPath(dev, cid, s.decimals === 0 ? Math.round(v) : Number(v.toFixed(4)));
}

export function sectionEnabled(dev: Dev, section: string): boolean {
  const off = dev.disabled;
  return !(Array.isArray(off) && off.includes(section));
}

function clean(d: Dev, top = false): void {
  for (const k of Object.keys(d)) {
    const v = d[k];
    if (v === null || v === undefined) delete d[k];
    else if (v && typeof v === 'object' && !Array.isArray(v)) {
      clean(v as Dev);
      if (!Object.keys(v as Dev).length && !(top && k === 'crop')) delete d[k];
    }
  }
}

export function prune(dev: Dev): Dev {
  const out = clone(dev);
  const wb = out.wb as Dev | undefined;
  const keepWb = !!wb && (wb.mode ?? 'asShot') !== 'asShot';
  for (const [cid, spec] of SPECS) {
    if (keepWb && cid.startsWith('wb.')) continue;
    const parts = cid.split('.');
    let cur: unknown = out;
    for (const p of parts.slice(0, -1)) cur = cur && typeof cur === 'object' ? (cur as Dev)[p] : undefined;
    if (cur && typeof cur === 'object') {
      const last = parts[parts.length - 1];
      const v = (cur as Dev)[last];
      if (typeof v === 'number' && Math.abs(v - spec.default) <= 1e-9) delete (cur as Dev)[last];
    }
  }
  clean(out, true);
  const curve = out.curve as Dev | undefined;
  if (curve) {
    for (const ch of ['master', 'red', 'green', 'blue']) {
      const pts = curve[ch];
      if (Array.isArray(pts) && pts.every((p) => Math.abs((p as number[])[0] - (p as number[])[1]) <= 1e-6)) delete curve[ch];
    }
    if (!Object.keys(curve).length) delete out.curve;
  }
  if (out.treatment === 'color') delete out.treatment;
  if (out.wb && JSON.stringify(out.wb) === '{"mode":"asShot"}') delete out.wb;
  const crop = out.crop as Dev | undefined;
  if (crop) {
    const r = crop.rect as number[] | undefined;
    if (Array.isArray(r) && r.length === 4 && r.every((x, k) => Math.abs(x - [0, 0, 1, 1][k]) <= 1e-9)) delete crop.rect;
    for (const k of ['flipH', 'flipV']) if (crop[k] === false) delete crop[k];
    if (typeof crop.angle === 'number' && crop.angle === 0) delete crop.angle;
    if (!Object.keys(crop).length) delete out.crop;
  }
  if (out.orientation === 0) delete out.orientation;
  return out;
}

export function merge(base: Dev, over: Dev): Dev {
  const out = clone(base);
  for (const [k, v] of Object.entries(over || {})) {
    if (v && typeof v === 'object' && !Array.isArray(v) && out[k] && typeof out[k] === 'object' && !Array.isArray(out[k])) out[k] = merge(out[k] as Dev, v as Dev);
    else out[k] = clone({ v }).v;
  }
  return out;
}

export const GROUPS: Record<string, string[]> = {
  whiteBalance: ['wb'], basicTone: ['light'], presence: ['effects', 'color'], toneCurve: ['curve'], colorMixer: ['mixer'], bwMix: ['bw'], treatment: ['treatment'],
  colorGrading: ['grading'], detail: ['detail'], transform: ['geometry'], effects: ['vignette', 'grain'], calibration: ['calibration'], crop: ['crop', 'orientation'],
};
export const GROUP_LABELS: Array<[string, string]> = [
  ['whiteBalance', 'White Balance'], ['basicTone', 'Basic Tone'], ['presence', 'Presence'], ['toneCurve', 'Tone Curve'], ['colorMixer', 'Color Mixer'], ['bwMix', 'Black and White Mix'],
  ['treatment', 'Treatment'], ['colorGrading', 'Color Grading'], ['detail', 'Sharpening'], ['transform', 'Transform'], ['effects', 'Effects'], ['calibration', 'Calibration'], ['crop', 'Crop and Orientation'],
];
const UNSYNCED = new Set(['crop']);

export function applyGroups(target: Dev, source: Dev, groups: string[]): Dev {
  const covered = new Set(groups.flatMap((g) => GROUPS[g] ?? []));
  const keep: Dev = {};
  for (const [k, v] of Object.entries(target)) if (!covered.has(k)) keep[k] = clone({ v }).v;
  const picked: Dev = {};
  for (const [k, v] of Object.entries(source)) if (covered.has(k)) picked[k] = clone({ v }).v;
  return prune(merge(keep, picked));
}

export const defaultSyncGroups = (): string[] => Object.keys(GROUPS).filter((g) => !UNSYNCED.has(g));
