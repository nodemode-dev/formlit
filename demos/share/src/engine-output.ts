import { FORMATS, METADATA, PRESETS as EXPORT_PRESETS, SPACES, TOKENS, merged as exportMerged, metaFor, runExport } from './exporter';
import { BLEED, BOOK_DEFAULTS, BOOK_PRESETS, BOOK_SIZES, PACKAGE_SIZES, PAPER, PRINT_DEFAULTS, PRINT_TEMPLATES, TEXT_STYLES, autoBook, bookPages, deepMerge, printPages, templates, type Dict } from './layout';
import { encodeImage, renderPhoto, sharpen, watermark } from './render';
import { DEFAULTS as SLIDE_DEFAULTS, SIZES, TEMPLATES as SLIDE_TEMPLATES, gains, merged as slideMerged, pageLayout, stillSeconds, tracks } from './slides';
import { DEFAULTS as WEB_DEFAULTS, TEMPLATES as WEB_TEMPLATES, buildHtml, entriesFor, merged as webMerged, type Entry } from './site';
import { startTask, type Progress } from './jobs';
import { putOutput, unique } from './outputs';
import { tokensOf, withOverlays } from './pages';
import { store } from './store';
import { writeJpegs, writePdf } from './writers';

export type Handler = (p: Dict) => unknown | Promise<unknown>;

const idList = (p: Dict): number[] => (Array.isArray(p.ids) ? (p.ids as unknown[]).map(Number).filter((i) => store.recs.has(i)) : []);
const stemOf = (name: unknown, fallback: string): string => String(name || fallback).replace(/[\\/:*?"<>|]/g, '-').trim() || fallback;

function printLayout(p: Dict): Dict {
  const ids = idList(p);
  return withOverlays(printPages((p.settings ?? {}) as Dict, ids.map((id) => ({ id, aspect: store.aspect(id) }))));
}

function bookLayout(settings: Dict | undefined): Dict {
  const s = deepMerge(BOOK_DEFAULTS, settings);
  const used = [s.cover, ...(s.pages as Dict[])].flatMap((pg: Dict) => (pg.photos ?? []) as Array<number | null>).filter((x): x is number => x !== null && x !== undefined && store.recs.has(Number(x))).map(Number);
  return withOverlays(bookPages(s, store.aspects(used), store.prefs.bookTemplates));
}

function slideLayout(p: Dict): Dict {
  const ids = idList(p);
  const s = slideMerged((p.settings ?? {}) as Dict);
  const lay = withOverlays(pageLayout(ids, s, false));
  lay.slideshow = s;
  const music = tracks(s);
  if (music.length && s.music?.fit) {
    const still = Math.round(stillSeconds(lay.pages, s, music) * 1000) / 1000;
    for (const page of lay.pages as Dict[]) if (page.seconds === undefined) page.seconds = still;
  }
  lay.tracks = music;
  const [video, mus] = gains(s);
  lay.gains = { video, music: mus };
  return lay;
}

async function savePages(lay: Dict, stem: string, kind: string, format: string, progress: Progress): Promise<Dict> {
  const base = `${kind}/${stem}`;
  if (format === 'jpeg') {
    const files = await writeJpegs(lay, stem, progress);
    const folder = `${kind}/${stem} pages`;
    const paths = files.map((f) => putOutput(unique(`${folder}/${f.name}`), f.blob, folder));
    return { paths, folder };
  }
  const blob = await writePdf(lay, stem, progress);
  return { path: putOutput(unique(`${base}.pdf`), blob), pages: lay.pages.length };
}

const thumbData = new Map<string, string>();

async function webImage(id: number, size: number, s: Dict, mark: boolean): Promise<{ blob: Blob; url: string }> {
  const r = store.rec(id);
  const c = await renderPhoto(id, { resize: true, mode: 'long', value: size, noEnlarge: true });
  if (s.sharpen) sharpen(c, { on: true, for: 'screen', amount: 'standard' }, 240);
  if (mark && s.watermark?.on) watermark(c, { ...s.watermark, kind: 'text', anchor: s.watermark.anchor ?? 'br', inset: 0.025, color: '#ffffff', shadow: true }, tokensOf(r));
  const mode = String(s.metadata ?? 'copyright');
  const blob = await encodeImage(c, 'jpeg', Number(s.quality ?? 82), metaFor(r, mode, store.inPrivate(r), c.width, c.height));
  return { blob, url: '' };
}

async function previewUrl(id: number, size: number, s: Dict, quality: number): Promise<string> {
  const r = store.rec(id);
  const wm = s.watermark?.on ? `${s.watermark.text}|${s.watermark.opacity}|${s.watermark.anchor}|${s.watermark.size}` : '';
  const key = `${id}|${r.rev}|${size}|${wm}`;
  const hit = thumbData.get(key);
  if (hit) return hit;
  const c = await renderPhoto(id, { resize: true, mode: 'long', value: size, noEnlarge: true });
  if (s.watermark?.on) watermark(c, { ...s.watermark, kind: 'text', inset: 0.025, color: '#ffffff', shadow: true }, tokensOf(r));
  const url = c.toDataURL('image/jpeg', quality);
  thumbData.set(key, url);
  if (thumbData.size > 120) thumbData.delete(thumbData.keys().next().value as string);
  return url;
}

function recOf(id: number): { w: number; h: number; file: string; rec: ReturnType<typeof store.rec> } | null {
  const r = store.recs.get(id);
  return r ? { w: r.w, h: r.h, file: r.file, rec: r } : null;
}

export const OUTPUT_COMMANDS: Record<string, Handler> = {
  'export.options': () => ({ formats: FORMATS, spaces: SPACES, metadata: METADATA, tokens: TOKENS, defaults: exportMerged({}), anchors: ['tl', 't', 'tr', 'l', 'c', 'r', 'bl', 'b', 'br'], ffmpeg: false }),
  'export.presets': () => ({ presets: [...EXPORT_PRESETS, ...store.prefs.exportPresets.map((x) => ({ ...x, builtin: false, group: 'My Presets', description: '' }))], previous: null }),
  'export.savePreset': (p) => {
    const name = String(p.name ?? '').trim();
    if (!name) throw new Error('A preset needs a name');
    const id = `user.${Date.now().toString(36)}`;
    store.prefs.exportPresets.push({ id, name, settings: (p.settings ?? {}) as Dict });
    return { id };
  },
  'export.deletePreset': (p) => {
    const at = store.prefs.exportPresets.findIndex((x) => x.id === String(p.id));
    if (at < 0) throw new Error('Only your own presets can be deleted');
    store.prefs.exportPresets.splice(at, 1);
    return { deleted: String(p.id) };
  },
  'export.run': (p) => {
    const ids = idList(p);
    let settings = (p.settings ?? {}) as Dict;
    if (p.preset) {
      const hit = EXPORT_PRESETS.find((x) => x.id === p.preset);
      if (hit) settings = deepMerge(hit.settings, settings);
    }
    return startTask(`Exporting ${ids.length} ${ids.length === 1 ? 'photo' : 'photos'}`, (progress) => runExport(ids, settings, progress));
  },
  'export.previous': () => { throw new Error('Nothing has been exported yet'); },

  'print.options': () => ({ paper: Object.fromEntries(Object.entries(PAPER).map(([k, v]) => [k, { name: v[0], w: v[1], h: v[2] }])), packages: PACKAGE_SIZES, templates: PRINT_TEMPLATES, defaults: PRINT_DEFAULTS }),
  'print.layout': (p) => printLayout(p),
  'print.printers': () => ({ printers: [] }),
  'print.printerOptions': () => ({ options: [], dialog: false }),
  'print.printerDialog': () => ({ opened: false }),
  'print.run': (p) => {
    const lay = printLayout(p);
    const out = String(p.output ?? lay.settings.job?.output ?? 'pdf');
    if (out === 'tiff') throw new Error('TIFF output is part of the desktop app; choose PDF or JPEG here');
    return startTask(`Rendering ${lay.pages.length} ${lay.pages.length === 1 ? 'page' : 'pages'}`, (progress) => savePages(lay, stemOf(p.name, 'Print'), 'Print', out === 'jpeg' ? 'jpeg' : 'pdf', progress));
  },

  'book.options': () => ({
    sizes: Object.fromEntries(Object.entries(BOOK_SIZES).map(([k, v]) => [k, { name: v[0], w: v[1], h: v[2] }])),
    templates: templates(store.prefs.bookTemplates), defaults: BOOK_DEFAULTS, presets: BOOK_PRESETS, textStyles: TEXT_STYLES, bleed: BLEED, cmykProfiles: [],
  }),
  'book.autoLayout': (p) => {
    const ids = idList(p);
    return { pages: autoBook(ids, store.aspects(ids), String(p.mode ?? 'mixed')), cover: { template: 'cover', photos: ids.slice(0, 1), texts: ['Untitled', ''] } };
  },
  'book.layout': (p) => bookLayout((p.settings ?? {}) as Dict),
  'book.saveTemplate': (p) => {
    const s = deepMerge(BOOK_DEFAULTS, (p.settings ?? {}) as Dict);
    const src = [s.cover, ...(s.pages as Dict[])];
    const pg = src[Number(p.page ?? 1)];
    const t = pg ? templates(store.prefs.bookTemplates)[String(pg.template ?? 'single')] : undefined;
    if (!t || t.spread || t.wrap || t.hidden) throw new Error('Custom pages are made from single-page templates');
    const name = String(p.name ?? 'Custom');
    const key = `custom-${name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
    store.prefs.bookTemplates[key] = { name, cells: t.cells.map((c) => c.map((v) => Math.round(v * 10000) / 10000) as [number, number, number, number]), texts: t.texts, custom: true };
    return { template: key };
  },
  'book.deleteTemplate': (p) => {
    if (!store.prefs.bookTemplates[String(p.template)]) throw new Error('No such custom page');
    delete store.prefs.bookTemplates[String(p.template)];
    return { template: String(p.template) };
  },
  'book.export': (p) => {
    const format = String(p.format ?? 'pdf');
    if (format !== 'pdf' && format !== 'jpeg') throw new Error('Print-ready files for a book printer come from the desktop app; PDF and JPEG pages work here');
    const lay = bookLayout((p.settings ?? {}) as Dict);
    return startTask(`Exporting book, ${lay.pages.length} pages`, (progress) => savePages(lay, stemOf(p.name, 'Book'), 'Books', format, progress));
  },

  'slideshow.options': () => ({ templates: SLIDE_TEMPLATES, defaults: SLIDE_DEFAULTS, sizes: Object.fromEntries(Object.entries(SIZES).map(([k, v]) => [k, { w: v[0], h: v[1] }])), ffmpeg: false }),
  'slideshow.layout': (p) => slideLayout(p),
  'slideshow.musicIn': (p) => {
    const folder = String(p.folder ?? '');
    return { tracks: Array.from(store.audio.keys()).filter((k) => k.startsWith(`${folder}/`)).sort().map((path) => ({ path, name: path.split('/').pop() })) };
  },
  'slideshow.export': (p) => {
    const format = String(p.format ?? 'pdf');
    if (format === 'mp4') throw new Error('Video export needs the desktop app; PDF and JPEG pages work here');
    const ids = idList(p);
    const s = slideMerged((p.settings ?? {}) as Dict);
    const lay = pageLayout(ids, s, format === 'pdf');
    return startTask(`Exporting slideshow (${format.toUpperCase()})`, (progress) => savePages(lay, stemOf(p.name, 'Slideshow'), 'Slideshows', format === 'jpeg' ? 'jpeg' : 'pdf', progress));
  },

  'web.options': () => ({ templates: WEB_TEMPLATES, defaults: WEB_DEFAULTS }),
  'web.preview': async (p) => {
    const ids = idList(p);
    const s = webMerged((p.settings ?? {}) as Dict);
    const entries = entriesFor(ids, s, recOf);
    const thumbs = new Map<number, string>(), larges = new Map<number, string>();
    await Promise.all(entries.map(async (e) => {
      thumbs.set(e.id, await previewUrl(e.id, Math.min(640, Math.max(240, Number(s.thumbSize ?? 480))), s, 0.8));
      larges.set(e.id, await previewUrl(e.id, 1280, s, 0.82));
    }));
    return { html: buildHtml(entries, s, (e: Entry) => thumbs.get(e.id) ?? '', (e: Entry) => larges.get(e.id) ?? '') };
  },
  'web.export': (p) => {
    const ids = idList(p);
    const s = webMerged((p.settings ?? {}) as Dict);
    if (p.upload) throw new Error('Upload sends files to an FTP server and is part of the desktop app; Export saves the gallery as a ZIP');
    const stem = stemOf(p.name, 'Web Gallery');
    return startTask('Exporting web gallery', async (progress) => {
      const entries = entriesFor(ids, s, recOf);
      const folder = unique(`Web/${stem}/x`).replace(/\/x(-\d+)?$/, '');
      const names = new Map<number, string>();
      let n = 0;
      for (const e of entries) {
        const large = await webImage(e.id, Number(s.largeSize ?? 2048), s, true);
        const thumb = await webImage(e.id, Number(s.thumbSize ?? 480), s, false);
        putOutput(`${folder}/images/${e.name}.jpg`, large.blob, folder);
        putOutput(`${folder}/thumbs/${e.name}.jpg`, thumb.blob, folder);
        names.set(e.id, e.name);
        n += 1;
        progress(n, entries.length, `Photo ${n} of ${entries.length}`);
      }
      const html = buildHtml(entries, s, (e: Entry) => `thumbs/${e.name}.jpg`, (e: Entry) => `images/${e.name}.jpg`);
      const index = putOutput(`${folder}/index.html`, new Blob([html], { type: 'text/html' }), folder);
      return { path: index, folder, photos: entries.length };
    });
  },
};
