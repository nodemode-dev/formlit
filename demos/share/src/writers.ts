import type { Dict } from './layout';
import { withOverlays } from './pages';
import { faceName, PdfDoc } from './pdf';
import { canvasBlob, cellRaster, rasterPage, textWidth, wrapText, type Overlay } from './render';

type Progress = (done: number, total: number, label: string) => void;

export async function writePdf(lay: Dict, title: string, progress?: Progress): Promise<Blob> {
  withOverlays(lay);
  const s = lay.settings, job = s.job ?? {};
  const ppi = Number(job.ppi ?? 300), quality = Number(job.quality ?? 92) / 100;
  const doc = new PdfDoc();
  const total = lay.pages.length;
  for (let n = 0; n < total; n += 1) {
    const page = lay.pages[n] as Dict;
    const pw = page.w ?? lay.page.w, ph = page.h ?? lay.page.h;
    const trim = page.cover ? 0 : Number(job.gutterTrim ?? 0);
    const odd = trim > 0 && Number(page.number ?? 0) % 2 === 1;
    const W = (pw - trim) * 72, H = ph * 72;
    const dx = odd ? -trim * 72 : 0;
    const out = doc.addPage(W, H);
    const bg = String(s.background ?? '#ffffff');
    if (bg.toLowerCase() !== '#ffffff') out.fill(bg, 0, 0, pw * 72 + dx, H);
    for (const cell of page.cells as Dict[]) {
      if (cell.photo === null || cell.photo === undefined) continue;
      const got = await cellRaster(Number(cell.photo), cell, ppi, job.sharpen, job);
      if (!got) continue;
      const blob = await canvasBlob(got.canvas, 'image/jpeg', quality);
      const x = got.x * 72 + dx, y = (ph - got.y - got.h) * 72, w = got.w * 72, h = got.h * 72;
      out.image(new Uint8Array(await blob.arrayBuffer()), got.canvas.width, got.canvas.height, x, y, w, h);
      const stroke = Number(s.stroke ?? 0);
      if (stroke > 0) out.strokeRect(String(s.strokeColor ?? '#000000'), stroke, x, y, w, h);
      if (s.cropMarks) {
        const L = 14, G = 4;
        for (const [cx, cy] of [[got.x, got.y], [got.x + got.w, got.y], [got.x, got.y + got.h], [got.x + got.w, got.y + got.h]]) {
          const X = cx * 72 + dx, Y = (ph - cy) * 72;
          const sx = cx === got.x ? -1 : 1, sy = cy === got.y ? 1 : -1;
          out.line('#000000', 0.4, X + sx * G, Y, X + sx * (G + L), Y);
          out.line('#000000', 0.4, X, Y + sy * G, X, Y + sy * (G + L));
        }
      }
    }
    for (const t of (page.overlays ?? []) as Overlay[]) {
      const bold = !!(t.bold ?? t.size >= 20), italic = !!t.italic, family = t.font ?? 'sans';
      const face = faceName(family, bold, italic);
      if (t.rotate) {
        out.text(face, t.size, t.color, t.x * 72 + dx, (ph - t.y) * 72 - t.size * 0.35, t.text, -t.rotate);
        continue;
      }
      const lines = t.wrap ? wrapText(t.text, family, bold, italic, t.size, t.wrap * 72) : [t.text];
      lines.forEach((line, i) => {
        const width = (t.align === 'center' || t.align === 'right') ? textWidth(line, family, bold, italic, t.size) : 0;
        const X = t.x * 72 + dx - (t.align === 'center' ? width / 2 : t.align === 'right' ? width : 0);
        out.text(face, t.size, t.color, X, (ph - t.y) * 72 - i * t.size * 1.3, line);
      });
    }
    progress?.(n + 1, total, `Page ${n + 1} of ${total}`);
  }
  return new Blob([doc.finish(title) as BlobPart], { type: 'application/pdf' });
}

export async function writeJpegs(lay: Dict, stem: string, progress?: Progress): Promise<Array<{ name: string; blob: Blob }>> {
  withOverlays(lay);
  const job = lay.settings.job ?? {};
  const q = Number(job.quality ?? 92) / 100;
  const out: Array<{ name: string; blob: Blob }> = [];
  const total = lay.pages.length;
  for (let i = 0; i < total; i += 1) {
    const page = lay.pages[i] as Dict;
    const pw = page.w ?? lay.page.w, ph = page.h ?? lay.page.h;
    const ppi = Math.min(Number(job.ppi ?? 300), 7200 / Math.max(pw, ph));
    const c = await rasterPage(lay, page, ppi);
    out.push({ name: `${stem}-${String(i + 1).padStart(2, '0')}.jpg`, blob: await canvasBlob(c, 'image/jpeg', q) });
    progress?.(i + 1, total, `Page ${i + 1} of ${total}`);
  }
  return out;
}
