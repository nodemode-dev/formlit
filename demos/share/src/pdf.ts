const WIN: Record<number, number> = { 0x2018: 0x91, 0x2019: 0x92, 0x201c: 0x93, 0x201d: 0x94, 0x2022: 0x95, 0x2013: 0x96, 0x2014: 0x97, 0x2026: 0x85, 0x20ac: 0x80, 0x2122: 0x99 };
const BASE: Record<string, string[]> = {
  sans: ['Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique', 'Helvetica-BoldOblique'],
  serif: ['Times-Roman', 'Times-Bold', 'Times-Italic', 'Times-BoldItalic'],
  mono: ['Courier', 'Courier-Bold', 'Courier-Oblique', 'Courier-BoldOblique'],
};

const bytesOf = (s: string): Uint8Array => {
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i += 1) out[i] = s.charCodeAt(i) & 0xff;
  return out;
};

const num = (v: number): string => (Math.round(v * 1000) / 1000).toString();

function encodeText(text: string): string {
  let out = '';
  for (const ch of text) {
    const c = ch.codePointAt(0) ?? 63;
    const b = WIN[c] ?? (c < 256 ? c : 63);
    const s = String.fromCharCode(b);
    out += s === '(' || s === ')' || s === '\\' ? `\\${s}` : s;
  }
  return out;
}

const rgb = (hex: string): string => {
  const h = hex.replace('#', '');
  if (h.length !== 6) return '1 1 1';
  return [0, 2, 4].map((i) => num(parseInt(h.slice(i, i + 2), 16) / 255)).join(' ');
};

export class PdfPage {
  readonly ops: string[] = [];
  readonly images: Array<{ name: string; obj: number }> = [];
  readonly fonts = new Set<string>();

  constructor(private readonly doc: PdfDoc, readonly w: number, readonly h: number) {}

  fill(hex: string, x: number, y: number, w: number, h: number): void {
    this.ops.push(`${rgb(hex)} rg ${num(x)} ${num(y)} ${num(w)} ${num(h)} re f`);
  }

  strokeRect(hex: string, width: number, x: number, y: number, w: number, h: number): void {
    this.ops.push(`${rgb(hex)} RG ${num(width)} w ${num(x + width / 2)} ${num(y + width / 2)} ${num(w - width)} ${num(h - width)} re S`);
  }

  line(hex: string, width: number, x0: number, y0: number, x1: number, y1: number): void {
    this.ops.push(`${rgb(hex)} RG ${num(width)} w ${num(x0)} ${num(y0)} m ${num(x1)} ${num(y1)} l S`);
  }

  image(jpeg: Uint8Array, pw: number, ph: number, x: number, y: number, w: number, h: number): void {
    const obj = this.doc.imageObject(jpeg, pw, ph);
    const name = `Im${this.images.length + 1}`;
    this.images.push({ name, obj });
    this.ops.push(`q ${num(w)} 0 0 ${num(h)} ${num(x)} ${num(y)} cm /${name} Do Q`);
  }

  text(face: string, size: number, hex: string, x: number, y: number, text: string, angle = 0): void {
    this.fonts.add(face);
    const a = (angle * Math.PI) / 180;
    this.ops.push(`BT /${face} ${num(size)} Tf ${rgb(hex)} rg ${num(Math.cos(a))} ${num(Math.sin(a))} ${num(-Math.sin(a))} ${num(Math.cos(a))} ${num(x)} ${num(y)} Tm (${encodeText(text)}) Tj ET`);
  }
}

export function faceName(family: string, bold: boolean, italic: boolean): string {
  return (BASE[family] ?? BASE.sans)[(bold ? 1 : 0) + (italic ? 2 : 0)];
}

export class PdfDoc {
  private readonly objects: Uint8Array[] = [];
  private readonly pages: Array<{ page: PdfPage; obj: number }> = [];
  private readonly fonts = new Map<string, number>();

  private alloc(): number {
    this.objects.push(new Uint8Array(0));
    return this.objects.length;
  }

  private set(n: number, head: string, stream?: Uint8Array): void {
    const a = bytesOf(stream ? `${n} 0 obj\n${head}\nstream\n` : `${n} 0 obj\n${head}\nendobj\n`);
    if (!stream) { this.objects[n - 1] = a; return; }
    const tail = bytesOf('\nendstream\nendobj\n');
    const out = new Uint8Array(a.length + stream.length + tail.length);
    out.set(a);
    out.set(stream, a.length);
    out.set(tail, a.length + stream.length);
    this.objects[n - 1] = out;
  }

  imageObject(jpeg: Uint8Array, w: number, h: number): number {
    const n = this.alloc();
    this.set(n, `<< /Type /XObject /Subtype /Image /Width ${w} /Height ${h} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpeg.length} >>`, jpeg);
    return n;
  }

  addPage(w: number, h: number): PdfPage {
    const page = new PdfPage(this, w, h);
    this.pages.push({ page, obj: 0 });
    return page;
  }

  private font(face: string): number {
    let n = this.fonts.get(face);
    if (!n) {
      n = this.alloc();
      this.set(n, `<< /Type /Font /Subtype /Type1 /BaseFont /${face} /Encoding /WinAnsiEncoding >>`);
      this.fonts.set(face, n);
    }
    return n;
  }

  finish(title: string): Uint8Array {
    const catalog = this.alloc(), tree = this.alloc();
    const kids: number[] = [];
    for (const entry of this.pages) {
      const content = this.alloc();
      const body = bytesOf(entry.page.ops.join('\n'));
      this.set(content, `<< /Length ${body.length} >>`, body);
      const pageObj = this.alloc();
      entry.obj = pageObj;
      const fonts = Array.from(entry.page.fonts).map((f) => `/${f} ${this.font(f)} 0 R`).join(' ');
      const xobjs = entry.page.images.map((i) => `/${i.name} ${i.obj} 0 R`).join(' ');
      this.set(pageObj, `<< /Type /Page /Parent ${tree} 0 R /MediaBox [0 0 ${num(entry.page.w)} ${num(entry.page.h)}] /Contents ${content} 0 R /Resources << /Font << ${fonts} >> /XObject << ${xobjs} >> >> >>`);
      kids.push(pageObj);
    }
    const info = this.alloc();
    this.set(info, `<< /Title (${encodeText(title)}) /Creator (formlit share demo) /Producer (formlit share demo) >>`);
    this.set(tree, `<< /Type /Pages /Kids [${kids.map((k) => `${k} 0 R`).join(' ')}] /Count ${kids.length} >>`);
    this.set(catalog, `<< /Type /Catalog /Pages ${tree} 0 R >>`);
    const head = bytesOf('%PDF-1.4\n%\xe2\xe3\xcf\xd3\n');
    const offsets: number[] = [];
    let pos = head.length;
    for (const o of this.objects) { offsets.push(pos); pos += o.length; }
    const xref = [`xref\n0 ${this.objects.length + 1}\n0000000000 65535 f \n`, ...offsets.map((o) => `${String(o).padStart(10, '0')} 00000 n \n`)].join('');
    const trailer = `trailer\n<< /Size ${this.objects.length + 1} /Root ${catalog} 0 R /Info ${info} 0 R >>\nstartxref\n${pos}\n%%EOF\n`;
    const tail = bytesOf(xref + trailer);
    const out = new Uint8Array(pos + tail.length);
    out.set(head);
    let at = head.length;
    for (const o of this.objects) { out.set(o, at); at += o.length; }
    out.set(tail, pos);
    return out;
  }
}
