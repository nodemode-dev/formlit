import type { Dict } from './layout';
import { expandTokens, type Overlay, type Tokens } from './render';
import { store, type Rec } from './store';

const g = (v: number): string => String(Number(v.toPrecision(6)));

export function shutterText(v: number | null): string {
  if (!v) return '';
  return v < 1 ? `1/${Math.round(1 / v)} s` : `${g(v)} s`;
}

export function tokensOf(r: Rec): Tokens {
  return { copyright: r.copyright, creator: r.creator, title: r.title, name: r.file.replace(/\.[^.]+$/, ''), year: (r.time ?? '').slice(0, 4) || String(new Date().getFullYear()), caption: r.caption };
}

export function exposureText(r: Rec): string {
  return [shutterText(r.shutter), r.aperture ? `f/${g(r.aperture)}` : '', r.iso ? `ISO ${r.iso}` : '', r.focal ? `${g(r.focal)} mm` : ''].filter(Boolean).join(', ');
}

export function caption(pid: number | null | undefined, field: string, custom = ''): string {
  if (pid === null || pid === undefined) return '';
  const r = store.recs.get(Number(pid));
  if (!r) return '';
  if (field === 'fileName') return r.file;
  if (field === 'exposure') return exposureText(r);
  if (field === 'date') return (r.time ?? '').slice(0, 10);
  if (field === 'custom') return expandTokens(custom, tokensOf(r));
  if (field === 'titleCaption') return [r.title, r.caption].filter(Boolean).join(' · ');
  if (field === 'caption') return r.caption;
  return field === 'title' ? r.title : '';
}

export function overlays(page: Dict, lay: Dict, s: Dict, total: number): Overlay[] {
  const out: Overlay[] = [];
  const pw = page.w ?? lay.page.w, ph = page.h ?? lay.page.h;
  const ident = s.identity ?? {};
  if (ident.on && ident.text) out.push({ x: Number(ident.x ?? 0.5) * pw, y: Number(ident.y ?? 0.05) * ph, size: Number(ident.size ?? 18), text: ident.text, align: 'center', color: ident.color ?? '#333333' });
  if (s.pageNumbers && !page.cover) out.push({ x: pw / 2, y: ph - 0.3, size: 8, text: String(page.number), align: 'center', color: '#555555' });
  if (s.pageInfo) {
    const job = s.job ?? {};
    out.push({ x: 0.3, y: ph - 0.3, size: 7, text: `Page ${page.number} of ${total} · ${job.ppi ?? 300} ppi · sharpening ${job.sharpen?.on ? 'on' : 'off'} · formlit`, align: 'left', color: '#777777' });
  }
  const cap = s.caption ?? {};
  if (cap.on) {
    for (const c of page.cells as Dict[]) {
      const text = caption(c.photo, cap.field ?? 'title', cap.custom ?? '');
      if (text) out.push({ x: c.x + c.w / 2, y: c.y + c.h + (Number(cap.size ?? 9) / 72) * 1.3, size: Number(cap.size ?? 9), text, align: 'center', color: '#333333' });
    }
  }
  for (const t of (page.texts ?? []) as Dict[]) {
    if (!t.text) continue;
    const size = Number(t.size || (t.title ? s.titleSize ?? 28 : s.textSize ?? 11));
    if (t.rotate) {
      out.push({ x: t.x + t.w / 2, y: t.y + t.h / 2, size, text: t.text, align: 'center', rotate: Number(t.rotate), color: t.color || s.textColor || '#222222', font: t.font ?? 'sans', bold: true, italic: false });
      continue;
    }
    const align = String(t.align || 'center');
    const x = align === 'left' ? t.x : align === 'right' ? t.x + t.w : t.x + t.w / 2;
    out.push({ x, y: t.y + size / 72, size, text: t.text, align, color: t.color || s.textColor || '#222222', wrap: t.w, font: t.font ?? 'sans', bold: t.bold ?? size >= 20, italic: !!t.italic });
  }
  if (s.captions && 'captionField' in s) {
    for (const c of page.cells as Dict[]) {
      const text = caption(c.photo, s.captionField ?? 'title');
      if (text) out.push({ x: c.x + c.w / 2, y: c.y + c.h + 0.18, size: 9, text, align: 'center', color: s.textColor ?? '#222222' });
    }
  }
  return out;
}

export function withOverlays(lay: Dict): Dict {
  const total = lay.pages.length;
  for (const page of lay.pages as Dict[]) page.overlays = overlays(page, lay, lay.settings, total);
  return lay;
}
