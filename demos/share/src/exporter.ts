import type { ExifWrite } from './exif';
import { deepMerge, type Dict } from './layout';
import { hasOutput, putOutput, unique } from './outputs';
import { tokensOf } from './pages';
import { encodeImage, renderPhoto, sharpen, watermark } from './render';
import { store, type Rec } from './store';

export const FORMATS: Dict = {
  jpeg: { ext: 'jpg', label: 'JPEG', depths: [8], quality: true },
  png: { ext: 'png', label: 'PNG', depths: [8], quality: false },
  webp: { ext: 'webp', label: 'WebP', depths: [8], quality: true },
  original: { ext: '', label: 'Original', depths: [], quality: false },
};
export const SPACES: Dict = { srgb: 'sRGB' };
export const METADATA: Dict = {
  none: 'None', copyright: 'Copyright Only', contact: 'Copyright and Contact Info Only', noCamera: 'All Except Camera and Camera Raw Info', noRaw: 'All Except Camera Raw Info', all: 'All Metadata',
};
export const TOKENS: Dict = {
  name: 'Original file name without its extension', ext: 'Original extension, lower case', seq: 'Sequence number; {seq:4} pads to 4 digits', num: 'Number found at the end of the original name',
  date: 'Capture date; {date:%Y-%m-%d} takes a strftime pattern', year: 'Capture year', month: 'Capture month (01 to 12)', day: 'Capture day (01 to 31)', camera: 'Camera model', lens: 'Lens', iso: 'ISO',
  focal: 'Focal length in mm', aperture: 'Aperture', rating: 'Star rating', label: 'Colour label', title: 'Title', creator: 'Creator', custom: 'Custom text passed with the template',
};

export const DEFAULTS: Dict = {
  destination: { folder: 'Browser downloads', subfolder: '', useSubfolder: false, sameAsOriginal: false, existing: 'unique', addToCatalog: false, stack: false },
  naming: { rename: false, template: '{name}', custom: '', start: 1, case: 'keep' },
  file: { format: 'jpeg', quality: 85, limitKB: 0, depth: 8, compression: 'none', space: 'srgb', hdr: false, hdrStops: '2' },
  size: { resize: false, mode: 'long', w: 2048, h: 2048, value: 2048, mp: 12, percent: 50, noEnlarge: true, ppi: 240 },
  sharpen: { on: false, for: 'screen', amount: 'standard' },
  metadata: { include: 'all', removePerson: true, removeLocation: false },
  watermark: { on: false, kind: 'text', text: '{copyright}', image: '', size: 0.035, opacity: 0.7, anchor: 'br', inset: 0.025, color: '#ffffff', shadow: true },
  video: { include: true, format: 'original', quality: 'high' },
  post: { action: 'none', app: '' },
};

const E = (id: string, name: string, group: string, description: string, settings: Dict): Dict => ({ id: `builtin.${id}`, name, group, description, settings, builtin: true });
const SRGB = { format: 'jpeg', space: 'srgb', depth: 8 };

export const PRESETS: Dict[] = [
  E('web', 'JPEG for Web (2048 px)', 'General', '', { file: { format: 'jpeg', quality: 82, space: 'srgb' }, size: { resize: true, mode: 'long', value: 2048 }, sharpen: { on: true, for: 'screen', amount: 'standard' }, metadata: { include: 'copyright' } }),
  E('full', 'Full Size JPEG', 'General', '', { file: { format: 'jpeg', quality: 92, space: 'srgb' }, metadata: { include: 'all' } }),
  E('email', 'For Email (1200 px)', 'General', '', { file: { format: 'jpeg', quality: 75, space: 'srgb' }, size: { resize: true, mode: 'long', value: 1200 }, sharpen: { on: true, for: 'screen', amount: 'low' }, metadata: { include: 'copyright' } }),
  E('original', 'Original Files', 'General', '', { file: { format: 'original' } }),
  E('client-gallery', 'Client Gallery (2048 px, signed)', 'Client Delivery', 'Online gallery size with a small copyright mark bottom right and the copyright in the file.',
    { file: { ...SRGB, quality: 85 }, size: { resize: true, mode: 'long', value: 2048 }, sharpen: { on: true, for: 'screen', amount: 'standard' }, metadata: { include: 'copyright' }, watermark: { on: true, kind: 'text', text: '{copyright}', size: 0.022, opacity: 0.6, anchor: 'br' } }),
  E('proof', 'Proofs (1200 px, centred watermark)', 'Client Delivery', 'Small proofs for choosing, with a large faint watermark across the middle.',
    { file: { ...SRGB, quality: 70 }, size: { resize: true, mode: 'long', value: 1200 }, sharpen: { on: true, for: 'screen', amount: 'low' }, metadata: { include: 'copyright' }, watermark: { on: true, kind: 'text', text: 'PROOF {copyright}', size: 0.06, opacity: 0.3, anchor: 'c', shadow: false } }),
  E('print-lab', 'Print Lab (sRGB JPEG, 300 ppi)', 'Print', 'Full size, high-quality sRGB JPEG for print labs.', { file: { ...SRGB, quality: 93 }, size: { ppi: 300 }, sharpen: { on: true, for: 'glossy', amount: 'standard' }, metadata: { include: 'copyright' } }),
  E('instagram', 'Instagram (1080 px wide)', 'Web and Social', '1080 px wide sRGB JPEG.', { file: { ...SRGB, quality: 88 }, size: { resize: true, mode: 'wh', w: 1080, h: 10000 }, sharpen: { on: true, for: 'screen', amount: 'standard' }, metadata: { include: 'copyright' } }),
  E('blog', 'Blog and Website (1600 px)', 'Web and Social', '1600 px long side, lighter file for web pages.', { file: { ...SRGB, quality: 80 }, size: { resize: true, mode: 'long', value: 1600 }, sharpen: { on: true, for: 'screen', amount: 'standard' }, metadata: { include: 'copyright' } }),
];

export const merged = (s: Dict | null | undefined): Dict => deepMerge(DEFAULTS, s ?? {});

export function metaFor(r: Rec, mode: string, removeLocation: boolean, w: number, h: number): ExifWrite {
  const out: ExifWrite = { width: w, height: h };
  if (mode === 'none') return out;
  out.copyright = r.copyright;
  if (mode !== 'copyright') out.creator = r.creator;
  if (mode === 'noCamera' || mode === 'noRaw' || mode === 'all') {
    out.time = r.time;
    out.caption = r.caption;
  }
  if (mode === 'noRaw' || mode === 'all') {
    Object.assign(out, { make: r.make, model: r.camera, lens: r.lens, iso: r.iso, shutter: r.shutter, fnumber: r.aperture, focal: r.focal });
    if (!removeLocation && r.gps) { out.gps = r.gps; out.alt = r.alt; }
  }
  return out;
}

const pad = (n: number, w = 2): string => String(n).padStart(w, '0');

function strftime(fmt: string, d: Date): string {
  return fmt.replace(/%([YmdHMSy%])/g, (_m, k: string) => ({ Y: String(d.getFullYear()), m: pad(d.getMonth() + 1), d: pad(d.getDate()), H: pad(d.getHours()), M: pad(d.getMinutes()), S: pad(d.getSeconds()), y: pad(d.getFullYear() % 100), '%': '%' })[k] ?? '');
}

export function expandName(template: string, r: Rec, seq: number, custom: string): string {
  const stem = r.file.replace(/\.[^.]+$/, '');
  const when = r.time ? new Date(r.time) : null;
  const found = /(\d+)$/.exec(stem);
  const out = template.replace(/\{([a-z]+)(?::([^}]*))?\}/g, (m, key: string, arg?: string) => {
    switch (key) {
      case 'name': return stem;
      case 'ext': return (r.file.split('.').pop() ?? '').toLowerCase();
      case 'seq': return String(seq).padStart(arg && /^\d+$/.test(arg) ? Number(arg) : 1, '0');
      case 'num': return found ? found[1] : String(seq);
      case 'date': return when ? strftime(arg || '%Y%m%d', when) : 'undated';
      case 'year': return when ? strftime('%Y', when) : 'undated';
      case 'month': return when ? strftime('%m', when) : 'undated';
      case 'day': return when ? strftime('%d', when) : 'undated';
      case 'camera': return r.camera || 'camera';
      case 'lens': return r.lens || 'lens';
      case 'iso': return r.iso ? String(r.iso) : '';
      case 'focal': return r.focal ? `${Math.round(r.focal)}mm` : '';
      case 'aperture': return r.aperture ? `f${r.aperture.toFixed(1)}` : '';
      case 'rating': return String(r.rating);
      case 'label': return r.label;
      case 'title': return r.title;
      case 'creator': return r.creator;
      case 'custom': return custom;
      default: return m;
    }
  });
  return out.replace(/[\\/:*?"<>|\u0000-\u001f]/g, '-').trim().replace(/^\.+|\.+$/g, '') || 'untitled';
}

type Progress = (done: number, total: number, label: string) => void;
let runs = 0;

export async function exportOne(id: number, s: Dict, seq: number, folder: string): Promise<string | null> {
  const r = store.rec(id);
  const f = s.file, fmt = String(f.format ?? 'jpeg');
  let stem = expandName(s.naming.rename ? String(s.naming.template || '{name}') : '{name}', r, seq, String(s.naming.custom ?? ''));
  const kase = s.naming.case;
  if (kase === 'lower') stem = stem.toLowerCase(); else if (kase === 'upper') stem = stem.toUpperCase();
  const ext = fmt === 'original' ? (r.file.split('.').pop() ?? 'jpg') : String(FORMATS[fmt].ext);
  let path = `${folder}/${stem}.${ext}`;
  const existing = String(s.destination.existing ?? 'unique');
  if (hasOutput(path)) {
    if (existing === 'skip') return null;
    if (existing === 'unique') path = unique(path);
  }
  if (fmt === 'original') {
    putOutput(path, new Blob([r.bytes as BlobPart], { type: r.mime }), folder);
    return path;
  }
  const ppi = Number(s.size.ppi ?? 240);
  const c = await renderPhoto(id, s.size);
  sharpen(c, s.sharpen, ppi);
  watermark(c, s.watermark, tokensOf(r));
  const m = s.metadata;
  const exif = metaFor(r, String(m.include ?? 'all'), !!m.removeLocation || store.inPrivate(r), c.width, c.height);
  let q = Number(f.quality ?? 85);
  let blob = await encodeImage(c, fmt, q, exif);
  const limit = Number(f.limitKB ?? 0) * 1000;
  while (limit > 0 && fmt !== 'png' && blob.size > limit && q > 20) {
    q -= 6;
    blob = await encodeImage(c, fmt, q, exif);
  }
  putOutput(path, blob, folder);
  return path;
}

export async function runExport(ids: number[], settings: Dict, progress: Progress): Promise<Dict> {
  const s = merged(settings);
  const written: string[] = [];
  const skipped: number[] = [];
  const failed: Array<{ id: number; error: string }> = [];
  runs += 1;
  const sub = s.destination.useSubfolder && s.destination.subfolder ? expandName(String(s.destination.subfolder), store.rec(ids[0]), 1, '') : '';
  const folder = `Exports/${sub || `Export ${runs}`}`;
  const start = Number(s.naming.start ?? 1);
  for (let i = 0; i < ids.length; i += 1) {
    try {
      const p = await exportOne(ids[i], s, start + i, folder);
      if (p === null) skipped.push(ids[i]); else written.push(p);
    } catch (err) {
      failed.push({ id: ids[i], error: err instanceof Error ? err.message : String(err) });
    }
    progress(i + 1, ids.length, `Exporting ${i + 1} of ${ids.length}`);
  }
  return { paths: written, skipped, failed, folder, settings: s };
}
