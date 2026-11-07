import { deepMerge, type Dict } from './layout';
import { caption, exposureText } from './pages';

export const DEFAULTS: Dict = {
  layout: 'grid',
  site: { title: 'Photographs', collection: '', description: '', contact: '', link: '' },
  colors: { background: '#111113', text: '#e9e9ea', muted: '#8b8b90', cell: '#1b1b1e', accent: '#ff7a1a' },
  thumbSize: 480, largeSize: 2048, quality: 82, rowHeight: 240, gap: 8,
  captions: { field: 'title', lightbox: 'titleCaption', exposure: false },
  watermark: { on: false, text: '{copyright}', size: 0.025, opacity: 0.6, anchor: 'br' },
  metadata: 'copyright', sharpen: true,
  upload: { host: '', port: 21, user: '', password: '', path: '/', tls: true },
};

export const TEMPLATES: Dict[] = [
  { id: 'studio', name: 'Studio Dark Grid', settings: {} },
  { id: 'paper', name: 'Paper Light Grid', settings: { colors: { background: '#f6f4ef', text: '#1d1d1f', muted: '#6d6d72', cell: '#ebe8e1', accent: '#b5531b' } } },
  { id: 'track', name: 'Justified Track', settings: { layout: 'justified', rowHeight: 280, gap: 6 } },
  { id: 'square', name: 'Square Thumbnails', settings: { layout: 'square', thumbSize: 360, gap: 4 } },
  { id: 'folio', name: 'Folio Single Column', settings: { layout: 'column', thumbSize: 1600, gap: 48 } },
];

export const merged = (s: Dict | null | undefined): Dict => deepMerge(DEFAULTS, s ?? {});

export interface Entry { id: number; n: number; aspect: number; title: string; long: string; exif: string; name: string }

export function entriesFor(ids: number[], s: Dict, recOf: (id: number) => { w: number; h: number; file: string; rec: Parameters<typeof exposureText>[0] } | null): Entry[] {
  const out: Entry[] = [];
  ids.forEach((id, i) => {
    const r = recOf(id);
    if (!r) return;
    const cap = s.captions;
    out.push({ id, n: i + 1, aspect: r.w / Math.max(1, r.h), title: caption(id, cap.field ?? 'title'), long: caption(id, cap.lightbox ?? 'titleCaption'), exif: cap.exposure ? exposureText(r.rec) : '', name: r.file.replace(/\.[^.]+$/, '') });
  });
  return out;
}

const esc = (v: string): string => v.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

function css(s: Dict): string {
  const c = s.colors;
  const gap = Math.trunc(Number(s.gap ?? 8));
  const thumb = Math.trunc(Number(s.thumbSize ?? 480));
  const row = Math.trunc(Number(s.rowHeight ?? 240));
  const grid: Record<string, string> = {
    grid: `.g{display:grid;grid-template-columns:repeat(auto-fill,minmax(${Math.max(140, Math.trunc(thumb / 2))}px,1fr));gap:${gap}px}.c{aspect-ratio:3/2}.c img{object-fit:contain}`,
    square: `.g{display:grid;grid-template-columns:repeat(auto-fill,minmax(${Math.max(110, Math.trunc(thumb / 2))}px,1fr));gap:${gap}px}.c{aspect-ratio:1}.c img{object-fit:cover}`,
    justified: `.g{display:flex;flex-wrap:wrap;gap:${gap}px}.g::after{content:'';flex-grow:999}.c{height:${row}px;flex-grow:calc(var(--a)*100);flex-basis:calc(var(--a)*${row}px)}.c img{object-fit:cover}`,
    column: `.g{display:flex;flex-direction:column;gap:${gap}px;max-width:1100px;margin:0 auto}.c{aspect-ratio:var(--a);background:none}.c img{object-fit:contain}`,
  };
  return `*{box-sizing:border-box}html,body{margin:0;background:${c.background};color:${c.text};font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}`
    + `header{padding:40px 28px 18px}h1{margin:0;font-size:26px;font-weight:600;letter-spacing:-.01em}h2{margin:4px 0 0;font-size:15px;font-weight:500;color:${c.muted}}`
    + `header p{max-width:720px;color:${c.muted}}main{padding:0 28px 40px}`
    + `.c{position:relative;display:block;overflow:hidden;border-radius:6px;background:${c.cell};cursor:zoom-in}.c img{display:block;width:100%;height:100%}`
    + '.c span{position:absolute;left:0;right:0;bottom:0;padding:18px 10px 8px;background:linear-gradient(transparent,rgba(0,0,0,.6));color:#fff;font-size:12px;opacity:0;transition:opacity .2s}'
    + `.c:hover span,.c:focus span{opacity:1}${grid[s.layout] ?? ''}`
    + `footer{padding:20px 28px 40px;color:${c.muted};font-size:13px}footer a{color:${c.accent}}`
    + '#lb{position:fixed;inset:0;display:none;grid-template-rows:1fr auto;background:rgba(8,8,10,.96)}#lb.on{display:grid}'
    + '#lb img{max-width:100%;max-height:100%;margin:auto;object-fit:contain;align-self:center;justify-self:center;width:auto;height:auto;padding:24px}'
    + '#lb .meta{padding:10px 24px 18px;color:#ddd;font-size:13px;text-align:center;min-height:44px}'
    + '#lb button{position:absolute;top:50%;width:52px;height:72px;margin-top:-36px;border:0;background:none;color:#fff;font-size:30px;cursor:pointer;opacity:.6}'
    + '#lb button:hover{opacity:1}#lb .p{left:4px}#lb .n{right:4px}#lb .x{top:28px;right:4px;margin:0;height:52px;font-size:24px}';
}

const JS = "const L=document.getElementById('lb'),I=L.querySelector('img'),M=L.querySelector('.meta'),A=[...document.querySelectorAll('.c')];let k=0;"
  + 'function show(i){k=(i+A.length)%A.length;const a=A[k];I.src=a.href;I.alt=a.dataset.t||\'\';M.textContent=a.dataset.l||\'\';L.classList.add(\'on\');}'
  + 'A.forEach((a,i)=>a.addEventListener(\'click\',e=>{e.preventDefault();show(i);}));'
  + 'L.querySelector(\'.p\').onclick=()=>show(k-1);L.querySelector(\'.n\').onclick=()=>show(k+1);L.querySelector(\'.x\').onclick=()=>L.classList.remove(\'on\');'
  + 'document.addEventListener(\'keydown\',e=>{if(!L.classList.contains(\'on\'))return;if(e.key===\'ArrowLeft\')show(k-1);else if(e.key===\'ArrowRight\')show(k+1);else if(e.key===\'Escape\')L.classList.remove(\'on\');});'
  + 'let sx=0;L.addEventListener(\'touchstart\',e=>{sx=e.touches[0].clientX},{passive:true});L.addEventListener(\'touchend\',e=>{const d=e.changedTouches[0].clientX-sx;if(Math.abs(d)>40)show(k+(d<0?1:-1));});';

export function buildHtml(entries: Entry[], s: Dict, thumbUrl: (e: Entry) => string, largeUrl: (e: Entry) => string): string {
  const site = s.site;
  const cells = entries.map((it) => {
    const meta = [it.long, it.exif].filter(Boolean).join(' · ');
    return `<a class="c" href="${esc(largeUrl(it))}" style="--a:${it.aspect.toFixed(4)}" data-t="${esc(it.title)}" data-l="${esc(meta)}">`
      + `<img src="${esc(thumbUrl(it))}" alt="${esc(it.title || it.name)}" loading="lazy" decoding="async">${it.title ? `<span>${esc(it.title)}</span>` : ''}</a>`;
  }).join('');
  let contact = '';
  if (site.contact) {
    const link = String(site.link || '');
    const href = /^https?:\/\//.test(link) ? link : link.includes('@') ? `mailto:${link}` : '';
    contact = href ? `<a href="${esc(href)}">${esc(site.contact)}</a>` : esc(site.contact);
  }
  return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    + `<meta name="generator" content="formlit"><title>${esc(site.title || 'Photographs')}</title><style>${css(s)}</style></head><body>`
    + `<header><h1>${esc(site.title || '')}</h1>${site.collection ? `<h2>${esc(site.collection)}</h2>` : ''}${site.description ? `<p>${esc(site.description)}</p>` : ''}</header><main><div class="g">${cells}</div></main>`
    + `<footer>${contact}</footer><div id="lb" role="dialog" aria-modal="true"><img alt=""><div class="meta"></div>`
    + '<button class="p" aria-label="Previous">&#8249;</button><button class="n" aria-label="Next">&#8250;</button><button class="x" aria-label="Close">&#215;</button></div>'
    + `<script>${JS}</script></body></html>`;
}
