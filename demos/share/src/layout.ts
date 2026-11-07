export type Dict = Record<string, any>;

export const PAPER: Record<string, [string, number, number]> = {
  letter: ['Letter', 8.5, 11], legal: ['Legal', 8.5, 14], tabloid: ['Tabloid', 11, 17], a5: ['A5', 5.83, 8.27], a4: ['A4', 8.27, 11.69],
  a3: ['A3', 11.69, 16.54], a3plus: ['A3+ / Super B', 13, 19], a2: ['A2', 16.54, 23.39], '4x6': ['4 x 6 in', 4, 6], '5x7': ['5 x 7 in', 5, 7],
  '8x10': ['8 x 10 in', 8, 10], '11x14': ['11 x 14 in', 11, 14], '13x19': ['13 x 19 in', 13, 19], '16x20': ['16 x 20 in', 16, 20], '17x22': ['17 x 22 in', 17, 22],
};
export const PACKAGE_SIZES: Record<string, [number, number]> = { wallet: [2.5, 3.5], '2x3': [2, 3], '3x5': [3, 5], '4x6': [4, 6], '5x7': [5, 7], '8x10': [8, 10] };

export const PRINT_DEFAULTS: Dict = {
  style: 'grid', paper: 'letter', orientation: 'portrait', size: null,
  margins: [0.5, 0.5, 0.5, 0.5], rows: 1, cols: 1, gapX: 0.25, gapY: 0.25, cellW: null, cellH: null,
  fill: false, rotate: true, repeat: false, stroke: 0, strokeColor: '#000000', background: '#ffffff',
  package: [{ size: '5x7' }, { size: 'wallet' }, { size: 'wallet' }], cells: [{ x: 0.5, y: 0.5, w: 4, h: 6 }],
  identity: { on: false, text: '', size: 18, x: 0.5, y: 0.035, color: '#333333' },
  pageNumbers: false, pageInfo: false, cropMarks: false,
  caption: { on: false, field: 'title', size: 9, custom: '' },
  job: { output: 'pdf', ppi: 300, sharpen: { on: true, for: 'matte', amount: 'standard' }, space: 'srgb', printer: '', copies: 1, quality: 92, bits: '16', profile: '', intent: 'perceptual', adjust: { on: false, brightness: 0, contrast: 0 } },
};

export const PRINT_TEMPLATES: Dict[] = [
  { id: 'fine-art', name: 'Gallery Mat', settings: { margins: [1, 1, 1, 1.75], identity: { on: true, text: '', size: 14, x: 0.5, y: 0.93 } } },
  { id: 'maximize', name: 'Full Page', settings: { margins: [0.25, 0.25, 0.25, 0.25] } },
  { id: '1-large', name: 'One Photo with Keyline', settings: { margins: [0.75, 0.75, 0.75, 0.75], stroke: 1 } },
  { id: '2x2', name: 'Four Up', settings: { rows: 2, cols: 2, gapX: 0.2, gapY: 0.2, margins: [0.4, 0.4, 0.4, 0.4] } },
  { id: '4x5-contact', name: 'Proof Sheet, 20 per Page', settings: { rows: 5, cols: 4, gapX: 0.12, gapY: 0.35, margins: [0.4, 0.4, 0.5, 0.5], caption: { on: true, field: 'fileName', size: 7 }, pageNumbers: true } },
  { id: '5x8-contact', name: 'Proof Sheet, 40 per Page', settings: { rows: 8, cols: 5, gapX: 0.1, gapY: 0.28, margins: [0.35, 0.35, 0.4, 0.45], caption: { on: true, field: 'fileName', size: 6 }, pageNumbers: true } },
  { id: 'triptych', name: 'Triptych', settings: { orientation: 'landscape', rows: 1, cols: 3, gapX: 0.15, fill: true, margins: [0.6, 0.6, 2, 2] } },
  { id: 'package-1-2', name: 'Print Set: One 5x7, Two Wallet', settings: { style: 'package', fill: true, package: [{ size: '5x7' }, { size: 'wallet' }, { size: 'wallet' }] } },
  { id: 'package-2-5x7', name: 'Print Set: Two 5x7', settings: { style: 'package', fill: true, package: [{ size: '5x7' }, { size: '5x7' }] } },
  { id: 'package-4-4x6', name: 'Print Set: Four 4x6', settings: { style: 'package', fill: true, paper: 'a3plus', package: [{ size: '4x6' }, { size: '4x6' }, { size: '4x6' }, { size: '4x6' }] } },
  { id: 'custom-overlap', name: 'One over Two', settings: { style: 'custom', cells: [{ x: 1.25, y: 1.5, w: 6, h: 4 }, { x: 1.25, y: 6, w: 2.8, h: 3.5 }, { x: 4.45, y: 6, w: 2.8, h: 3.5 }] } },
];

export const BOOK_SIZES: Record<string, [string, number, number]> = {
  'small-square': ['Small Square 7 x 7 in', 7, 7], 'standard-landscape': ['Standard Landscape 10 x 8 in', 10, 8],
  'standard-portrait': ['Standard Portrait 8 x 10 in', 8, 10], 'large-landscape': ['Large Landscape 13 x 11 in', 13, 11],
  'large-square': ['Large Square 12 x 12 in', 12, 12], letter: ['Letter 8.5 x 11 in', 8.5, 11], a4: ['A4 210 x 297 mm', 8.27, 11.69],
  'a4-landscape': ['A4 Landscape', 11.69, 8.27],
};

type Box = [number, number, number, number];
export interface TemplateDef { name: string; cells: Box[]; texts: Box[]; spread?: boolean; wrap?: boolean; hidden?: boolean; custom?: boolean }

const gridCells = (rows: number, cols: number, x0: number, y0: number, dx: number, dy: number, w: number, h: number): Box[] => {
  const out: Box[] = [];
  for (let r = 0; r < rows; r += 1) for (let c = 0; c < cols; c += 1) out.push([x0 + c * dx, y0 + r * dy, w, h]);
  return out;
};

export const BOOK_TEMPLATES: Record<string, TemplateDef> = {
  full: { name: 'Full Bleed', cells: [[0, 0, 1, 1]], texts: [] },
  single: { name: 'One Photo', cells: [[0.08, 0.08, 0.84, 0.84]], texts: [] },
  'single-caption': { name: 'One Photo with Caption', cells: [[0.08, 0.07, 0.84, 0.72]], texts: [[0.08, 0.83, 0.84, 0.1]] },
  'single-small': { name: 'One Small Centred', cells: [[0.22, 0.2, 0.56, 0.5]], texts: [[0.22, 0.74, 0.56, 0.08]] },
  'two-h': { name: 'Two Side by Side', cells: [[0.06, 0.2, 0.425, 0.6], [0.515, 0.2, 0.425, 0.6]], texts: [] },
  'two-v': { name: 'Two Stacked', cells: [[0.12, 0.06, 0.76, 0.425], [0.12, 0.515, 0.76, 0.425]], texts: [] },
  three: { name: 'One Large Two Small', cells: [[0.06, 0.06, 0.88, 0.52], [0.06, 0.61, 0.43, 0.33], [0.51, 0.61, 0.43, 0.33]], texts: [] },
  'three-col': { name: 'Three Columns', cells: [[0.05, 0.22, 0.28, 0.56], [0.36, 0.22, 0.28, 0.56], [0.67, 0.22, 0.28, 0.56]], texts: [] },
  four: { name: 'Four Grid', cells: [[0.06, 0.06, 0.43, 0.43], [0.51, 0.06, 0.43, 0.43], [0.06, 0.51, 0.43, 0.43], [0.51, 0.51, 0.43, 0.43]], texts: [] },
  'two-h-caption': { name: 'Two Side by Side with Captions', cells: [[0.06, 0.18, 0.425, 0.56], [0.515, 0.18, 0.425, 0.56]], texts: [[0.06, 0.77, 0.425, 0.08], [0.515, 0.77, 0.425, 0.08]] },
  'two-big-small': { name: 'One Large One Small', cells: [[0.05, 0.08, 0.6, 0.84], [0.68, 0.36, 0.27, 0.3]], texts: [[0.68, 0.7, 0.27, 0.12]] },
  'three-row': { name: 'Three in a Row', cells: [[0.04, 0.3, 0.3, 0.4], [0.35, 0.3, 0.3, 0.4], [0.66, 0.3, 0.3, 0.4]], texts: [] },
  'three-left': { name: 'One Tall Two Stacked', cells: [[0.05, 0.06, 0.5, 0.88], [0.57, 0.06, 0.38, 0.43], [0.57, 0.51, 0.38, 0.43]], texts: [] },
  'three-stack': { name: 'Three Stacked', cells: [[0.2, 0.04, 0.6, 0.29], [0.2, 0.355, 0.6, 0.29], [0.2, 0.67, 0.6, 0.29]], texts: [] },
  'four-row': { name: 'Four in a Row', cells: [[0.04, 0.34, 0.215, 0.32], [0.27, 0.34, 0.215, 0.32], [0.5, 0.34, 0.215, 0.32], [0.73, 0.34, 0.215, 0.32]], texts: [] },
  'four-feature': { name: 'One Large Three Small', cells: [[0.05, 0.06, 0.62, 0.88], [0.7, 0.06, 0.25, 0.28], [0.7, 0.36, 0.25, 0.28], [0.7, 0.66, 0.25, 0.28]], texts: [] },
  'four-caption': { name: 'Four Grid with Caption', cells: [[0.08, 0.05, 0.41, 0.37], [0.51, 0.05, 0.41, 0.37], [0.08, 0.44, 0.41, 0.37], [0.51, 0.44, 0.41, 0.37]], texts: [[0.08, 0.85, 0.84, 0.08]] },
  five: { name: 'Five Mosaic', cells: [[0.04, 0.05, 0.56, 0.58], [0.62, 0.05, 0.34, 0.28], [0.62, 0.35, 0.34, 0.28], [0.04, 0.66, 0.45, 0.29], [0.51, 0.66, 0.45, 0.29]], texts: [] },
  six: { name: 'Six Grid', cells: gridCells(2, 3, 0.04, 0.12, 0.31, 0.39, 0.3, 0.37), texts: [] },
  nine: { name: 'Nine Grid', cells: gridCells(3, 3, 0.05, 0.05, 0.305, 0.305, 0.29, 0.29), texts: [] },
  twelve: { name: 'Contact Sheet', cells: gridCells(3, 4, 0.04, 0.06, 0.235, 0.31, 0.22, 0.28), texts: [] },
  'photo-text-right': { name: 'Photo with Text Beside', cells: [[0.05, 0.08, 0.55, 0.84]], texts: [[0.64, 0.3, 0.31, 0.08], [0.64, 0.4, 0.31, 0.3]] },
  'photo-text-left': { name: 'Text Beside Photo', cells: [[0.4, 0.08, 0.55, 0.84]], texts: [[0.05, 0.3, 0.31, 0.08], [0.05, 0.4, 0.31, 0.3]] },
  'full-caption': { name: 'Full Bleed with Caption', cells: [[0, 0, 1, 0.86]], texts: [[0.08, 0.89, 0.84, 0.07]] },
  'title-photo': { name: 'Title over Photo', cells: [[0.08, 0.24, 0.84, 0.7]], texts: [[0.08, 0.06, 0.84, 0.1], [0.08, 0.16, 0.84, 0.05]] },
  quote: { name: 'Quote Page', cells: [], texts: [[0.18, 0.36, 0.64, 0.2], [0.18, 0.6, 0.64, 0.06]] },
  text: { name: 'Text Page', cells: [], texts: [[0.15, 0.3, 0.7, 0.4]] },
  blank: { name: 'Blank', cells: [], texts: [] },
  cover: { name: 'Cover', cells: [[0, 0, 1, 0.72]], texts: [[0.08, 0.76, 0.84, 0.1], [0.08, 0.87, 0.84, 0.06]] },
  spread: { name: 'Two-Page Spread', spread: true, cells: [[0, 0, 2, 1]], texts: [] },
  'spread-caption': { name: 'Spread with Caption', spread: true, cells: [[0, 0, 2, 0.86]], texts: [[1.08, 0.89, 0.84, 0.07]] },
  'spread-text': { name: 'Spread with Text Left', spread: true, cells: [[0.62, 0, 1.38, 1]], texts: [[0.08, 0.32, 0.46, 0.08], [0.08, 0.42, 0.46, 0.3]] },
  'spread-two': { name: 'Two Facing Bleeds', spread: true, cells: [[0, 0, 1, 1], [1, 0, 1, 1]], texts: [] },
  'spread-cont': { name: 'Spread (right page)', hidden: true, cells: [], texts: [] },
  wrap: { name: 'Wrap Photo', wrap: true, cells: [[0, 0, 1, 1]], texts: [[0.56, 0.08, 0.4, 0.1], [0.56, 0.18, 0.4, 0.06], [0.05, 0.7, 0.38, 0.2]] },
  'wrap-front': { name: 'Front Photo, Text Back', wrap: true, cells: [[0.52, 0, 0.48, 1]], texts: [[0.56, 0.06, 0.4, 0.1], [0.56, 0.16, 0.4, 0.06], [0.05, 0.3, 0.38, 0.4]] },
  'wrap-both': { name: 'Front and Back Photos', wrap: true, cells: [[0, 0, 0.48, 1], [0.52, 0, 0.48, 1]], texts: [[0.56, 0.08, 0.4, 0.1], [0.56, 0.18, 0.4, 0.06], [0.05, 0.82, 0.38, 0.1]] },
};

const SPINE_PER_PAGE = 0.0025;
const SPINE_BOARD = 0.25;
export const BLEED = 0.125;

export const BOOK_PRESETS: Dict[] = [
  { id: 'clean', name: 'Clean White', settings: { background: '#ffffff', textColor: '#222222', pageNumbers: true, captions: false } },
  { id: 'gallery', name: 'Gallery Black', settings: { background: '#111111', textColor: '#e6e6e6', pageNumbers: false, captions: true, captionField: 'title' } },
  { id: 'travel', name: 'Travel Journal', settings: { background: '#f4efe6', textColor: '#3a3128', captions: true, captionField: 'titleCaption', autoLayout: 'mixed' } },
  { id: 'portfolio', name: 'Portfolio, One per Page', settings: { background: '#ffffff', textColor: '#222222', autoLayout: 'one', size: 'large-landscape', pageNumbers: false } },
  { id: 'square', name: 'Square Keepsake', settings: { size: 'small-square', background: '#ffffff', textColor: '#222222' } },
];

export const BOOK_DEFAULTS: Dict = {
  size: 'standard-landscape', background: '#ffffff', textColor: '#222222', font: 'Helvetica', titleSize: 28, textSize: 11,
  pageNumbers: true, captions: false, captionField: 'title', autoLayout: 'mixed',
  cover: { template: 'cover', photos: [], texts: ['Untitled', ''] }, pages: [],
  job: { output: 'pdf', ppi: 300, space: 'srgb', quality: 92, sharpen: { on: true, for: 'glossy', amount: 'standard' } },
};

export const TEXT_STYLES: Dict = {
  title: { font: 'sans', bold: true, size: 30, align: 'center' },
  heading: { font: 'sans', bold: true, size: 18, align: 'left' },
  body: { font: 'serif', bold: false, size: 11, align: 'left' },
  caption: { font: 'sans', bold: false, italic: true, size: 9, align: 'center' },
  quote: { font: 'serif', bold: false, italic: true, size: 20, align: 'center' },
  mono: { font: 'mono', bold: false, size: 10, align: 'left' },
};

export function templates(user: Record<string, TemplateDef>): Record<string, TemplateDef> {
  return { ...BOOK_TEMPLATES, ...Object.fromEntries(Object.entries(user).filter(([, v]) => v && Array.isArray(v.cells))) };
}

export const spineWidth = (pages: number): number => Math.round((SPINE_BOARD + SPINE_PER_PAGE * Math.max(20, pages)) * 1000) / 1000;

const padded = (x: number, y: number, w: number, h: number, pad: number): Box => {
  const p = Math.max(0, Math.min(0.45, pad)) * Math.min(w, h);
  return [x + p, y + p, w - 2 * p, h - 2 * p];
};

export function deepMerge(base: Dict, over: Dict | null | undefined): Dict {
  const out: Dict = JSON.parse(JSON.stringify(base));
  for (const [k, v] of Object.entries(over ?? {})) {
    if (v && typeof v === 'object' && !Array.isArray(v) && out[k] && typeof out[k] === 'object' && !Array.isArray(out[k])) out[k] = deepMerge(out[k], v);
    else out[k] = JSON.parse(JSON.stringify(v ?? null));
  }
  return out;
}

export function pageSize(s: Dict): [number, number] {
  let w: number, h: number;
  if (s.size) { w = Number(s.size[0]); h = Number(s.size[1]); } else { const p = PAPER[s.paper] ?? PAPER.letter; w = p[1]; h = p[2]; }
  if ((s.orientation === 'landscape') !== (w > h)) [w, h] = [h, w];
  return [w, h];
}

export function panZoom(cell: Dict, img: Dict, z0: number, x0: number, y0: number): Dict {
  const z = Math.max(1, Math.min(4, z0));
  const x = Math.max(-1, Math.min(1, x0)), y = Math.max(-1, Math.min(1, y0));
  const iw = img.w * z, ih = img.h * z;
  const sx = Math.max(0, iw - cell.w), sy = Math.max(0, ih - cell.h);
  return { x: cell.x - sx * (0.5 + 0.5 * x) + Math.min(0, iw - cell.w) * -0.5, y: cell.y - sy * (0.5 + 0.5 * y) + Math.min(0, ih - cell.h) * -0.5, w: iw, h: ih };
}

export function place(cell: Dict, aspect: number | null | undefined, fill: boolean, rotate: boolean): Dict {
  const { x: cx, y: cy, w: cw, h: ch } = cell;
  if (!aspect) return { ...cell, rot: false, img: null };
  const rot = !!(rotate && (aspect > 1) !== (cw > ch) && Math.abs(aspect - 1) > 0.02 && Math.abs(cw - ch) > 0.02);
  const a = rot ? 1 / aspect : aspect;
  let iw: number, ih: number;
  if ((cw / ch > a) === fill) { iw = cw; ih = cw / a; } else { iw = ch * a; ih = ch; }
  return { ...cell, rot, img: { x: cx + (cw - iw) / 2, y: cy + (ch - ih) / 2, w: iw, h: ih } };
}

function shelf(sizes: Array<[number, number]>, areaW: number, areaH: number, gap: number): Box[] | null {
  const out: Box[] = [];
  let x = 0, y = 0, rowH = 0;
  for (let [w, h] of sizes) {
    if (w > areaW && h <= areaW) [w, h] = [h, w];
    if (x > 0 && x + w > areaW + 1e-6) { x = 0; y += rowH + gap; rowH = 0; }
    if (y + h > areaH + 1e-6) return null;
    out.push([x, y, w, h]);
    x += w + gap;
    rowH = Math.max(rowH, h);
  }
  return out;
}

export function printPages(settings: Dict, photos: Array<{ id: number; aspect: number }>): Dict {
  const s = deepMerge(PRINT_DEFAULTS, settings);
  const [pw, ph] = pageSize(s);
  const [ml, mr, mt, mb] = (s.margins as number[]).map(Number);
  const areaW = Math.max(0.1, pw - ml - mr), areaH = Math.max(0.1, ph - mt - mb);
  const style = s.style ?? 'grid';
  let cells: Dict[] = [];
  if (style === 'grid') {
    const rows = Math.max(1, Math.min(15, Math.trunc(s.rows))), cols = Math.max(1, Math.min(15, Math.trunc(s.cols)));
    const gx = Math.max(0, Math.min(Number(s.gapX), cols > 1 ? (areaW / Math.max(1, cols - 1)) * 0.9 : 0));
    const gy = Math.max(0, Math.min(Number(s.gapY), rows > 1 ? (areaH / Math.max(1, rows - 1)) * 0.9 : 0));
    const cw = s.cellW ? Math.max(0.05, Number(s.cellW)) : (areaW - gx * (cols - 1)) / cols;
    const chh = s.cellH ? Math.max(0.05, Number(s.cellH)) : (areaH - gy * (rows - 1)) / rows;
    const totalW = cw * cols + gx * (cols - 1), totalH = chh * rows + gy * (rows - 1);
    const ox = ml + (areaW - totalW) / 2, oy = mt + (areaH - totalH) / 2;
    for (let r = 0; r < rows; r += 1) for (let c = 0; c < cols; c += 1) cells.push({ x: ox + c * (cw + gx), y: oy + r * (chh + gy), w: cw, h: chh });
  } else if (style === 'package') {
    const sizes: Array<[number, number]> = (s.package as Dict[]).map((it) => PACKAGE_SIZES[it.size] ?? [Number(it.w ?? 4), Number(it.h ?? 6)]);
    sizes.sort((a, b) => b[0] * b[1] - a[0] * a[1]);
    const packed = shelf(sizes, areaW, areaH, 0.125) ?? shelf(sizes.map(([w, h]) => [h, w] as [number, number]), areaW, areaH, 0.125) ?? [];
    cells = packed.map(([x, y, w, h]) => ({ x: ml + x, y: mt + y, w, h }));
  } else {
    cells = (s.cells as Dict[]).map((c) => ({ x: Number(c.x), y: Number(c.y), w: Number(c.w), h: Number(c.h) }));
  }
  const onePerPage = style === 'package' || !!s.repeat;
  const per = onePerPage ? 1 : Math.max(1, cells.length);
  const nPages = photos.length ? Math.max(1, Math.ceil(photos.length / per)) : 1;
  const pages: Dict[] = [];
  for (let p = 0; p < nPages; p += 1) {
    const chunk = photos.slice(p * per, (p + 1) * per);
    const placed = cells.map((c, i) => {
      const ph0 = onePerPage && chunk.length ? chunk[0] : i < chunk.length ? chunk[i] : null;
      const it = place(c, ph0 ? ph0.aspect : null, !!s.fill, !!s.rotate);
      it.photo = ph0 ? ph0.id : null;
      return it;
    });
    pages.push({ cells: placed, number: p + 1 });
  }
  return { page: { w: pw, h: ph }, pages, settings: s, cellCount: cells.length, fits: cells.length > 0 };
}

function bookItems(page: Dict, t: TemplateDef, photos: Map<number, number>, W: number, H: number, title: boolean, bleed = 0, span = 0): [Dict[], Dict[]] {
  const ids: Array<number | null> = page.photos ?? [];
  const crops: Dict[] = page.crops ?? [];
  const pads: Array<number | null> = page.pads ?? [];
  const cells = t.cells.map(([cx, cy, cw, chh], i) => {
    const pid = i < ids.length ? ids[i] : null;
    let [x, y, w, h] = padded(cx * W, cy * H, cw * W, chh * H, i < pads.length && pads[i] ? Number(pads[i]) : 0);
    if (bleed) {
      const right = span || W;
      const x0 = x <= 1e-6 ? x - bleed : x;
      const y0 = y <= 1e-6 ? y - bleed : y;
      const x1 = x + w >= right - 1e-6 ? x + w + bleed : x + w;
      const y1 = y + h >= H - 1e-6 ? y + h + bleed : y + h;
      x = x0 + bleed; y = y0 + bleed; w = x1 - x0; h = y1 - y0;
    }
    const c = { x, y, w, h };
    const item = place(c, pid !== null && pid !== undefined ? photos.get(Number(pid)) : null, true, false);
    item.photo = pid ?? null;
    const adj = i < crops.length && crops[i] && typeof crops[i] === 'object' ? crops[i] : null;
    if (adj && item.img) {
      item.img = panZoom(c, item.img, Number(adj.z ?? 1), Number(adj.x ?? 0), Number(adj.y ?? 0));
      item.crop = { z: Number(adj.z ?? 1), x: Number(adj.x ?? 0), y: Number(adj.y ?? 0) };
    }
    return item;
  });
  const values: string[] = page.texts ?? [];
  const styles: Dict[] = page.styles ?? [];
  const texts = t.texts.map(([x, y, w, h], i) => {
    const frame: Dict = { x: x * W + bleed, y: y * H + bleed, w: w * W, h: h * H, text: i < values.length ? values[i] : '', title: title && i === 0 };
    const st = i < styles.length && styles[i] && typeof styles[i] === 'object' ? styles[i] : null;
    if (st) {
      const merged = { ...(TEXT_STYLES[String(st.style ?? '')] ?? {}), ...st };
      for (const k of ['font', 'bold', 'italic', 'size', 'align', 'color']) if (k in merged) frame[k] = merged[k];
    }
    return frame;
  });
  return [cells, texts];
}

function half(items: Dict[], x0: number, x1: number, shift: number, key: 'cells' | 'texts'): Dict[] {
  const out: Dict[] = [];
  for (const it of items) {
    if (key === 'cells') {
      const a = Math.max(x0, it.x), b = Math.min(x1, it.x + it.w);
      if (b - a <= 1e-6) continue;
      const c: Dict = { ...it, x: a - shift, w: b - a };
      if (it.img) c.img = { ...it.img, x: it.img.x - shift };
      out.push(c);
    } else if (x0 - 1e-6 <= it.x && it.x < x1) out.push({ ...it, x: it.x - shift });
  }
  return out;
}

export function bookPages(settings: Dict, photos: Map<number, number>, user: Record<string, TemplateDef>): Dict {
  const s = deepMerge(BOOK_DEFAULTS, settings);
  const size = BOOK_SIZES[s.size] ?? BOOK_SIZES['standard-landscape'];
  const pw = size[1], ph = size[2];
  const tpl = templates(user);
  const job = s.job ?? {};
  const b = job.bleed || ['blurb', 'lulu', 'kdp', 'ingramspark'].includes(job.output) ? BLEED : 0;
  const src: Dict[] = [s.cover, ...(s.pages as Dict[])];
  const spine = spineWidth(src.length - 1);
  const out: Dict[] = [];
  let carry: Dict | null = null;
  src.forEach((page, idx) => {
    const t = tpl[page.template ?? 'single'] ?? BOOK_TEMPLATES.single;
    const base = { template: page.template ?? 'single', cover: idx === 0, number: idx };
    if (idx === 0 && t.wrap) {
      const W = 2 * pw + spine;
      const [cells, texts] = bookItems(page, t, photos, W, ph, true, b);
      const spineText = String(page.spine !== undefined && page.spine !== null ? page.spine : (page.texts ?? ['Untitled'])[0]);
      if (spineText) texts.push({ x: pw + b, y: b, w: spine, h: ph, text: spineText, rotate: 90, size: Math.max(7, Math.min(18, spine * 72 * 0.45)) });
      out.push({ ...base, cells, texts, w: W + 2 * b, h: ph + 2 * b, spine: [pw + b, spine] });
      return;
    }
    if (t.spread && idx > 0) {
      const [cells, texts] = bookItems(page, t, photos, pw, ph, false, b, 2 * pw);
      out.push({ ...base, cells: half(cells, 0, pw + b, 0, 'cells'), texts: half(texts, 0, pw + b, 0, 'texts'), w: pw + 2 * b, h: ph + 2 * b, spreadLeft: true });
      carry = { cells: half(cells, pw + b, 2 * pw + 2 * b, pw, 'cells'), texts: half(texts, pw + b, 2 * pw + 2 * b, pw, 'texts') };
      return;
    }
    if (page.template === 'spread-cont' && carry !== null) {
      out.push({ ...base, ...carry, w: pw + 2 * b, h: ph + 2 * b, spreadRight: true });
      carry = null;
      return;
    }
    carry = null;
    const [cells, texts] = bookItems(page, t, photos, pw, ph, idx === 0, b);
    out.push({ ...base, cells, texts, w: pw + 2 * b, h: ph + 2 * b });
  });
  return { page: { w: pw + 2 * b, h: ph + 2 * b }, pages: out, settings: s, bleed: b, spine };
}

export function autoBook(ids: number[], aspects: Map<number, number>, mode: string): Dict[] {
  const pages: Dict[] = [];
  const cycle = mode === 'mixed' ? ['single', 'two-h', 'full', 'three', 'single-caption', 'four'] : ['single'];
  let i = 0, k = 0;
  while (i < ids.length) {
    let t = cycle[k % cycle.length];
    k += 1;
    let n = BOOK_TEMPLATES[t].cells.length;
    const chunk = ids.slice(i, i + n);
    if (t === 'two-h' && chunk.some((c) => (aspects.get(c) ?? 1.5) > 1.2)) t = 'two-v';
    if (chunk.length < n) {
      t = ({ 1: 'single', 2: 'two-v', 3: 'three' } as Record<number, string>)[chunk.length] ?? 'single';
      n = chunk.length;
    }
    pages.push({ template: t, photos: chunk, texts: BOOK_TEMPLATES[t].texts.map(() => '') });
    i += n;
  }
  if (pages.length % 2) pages.push({ template: 'blank', photos: [], texts: [] });
  return pages;
}
