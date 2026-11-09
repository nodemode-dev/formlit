import type { Ctx } from '../app';
import { Dialog } from '../ui/dialogs';
import { el } from '../ui/dom';
import { toast } from '../ui/toast';

export interface DemoCard { id: string; title: string; line: string; cover: string }

export const DEMOS: DemoCard[] = [
  { id: 'library', title: 'Library and Develop', line: 'Twenty-five photos in four collections, rated, flagged and keyworded, eighteen already developed.', cover: 'demos/library/lakes-01-walensee.jpg' },
  { id: 'develop', title: 'Masks and Presets', line: 'Nine photos edited with sky, subject, gradient and range masks, tone curves and colour grading.', cover: 'demos/library/coast-01-foggy-beach.jpg' },
  { id: 'share', title: 'Map, Book, Slideshow, Print and Web', line: 'Nineteen photos on the map, with a book, a slideshow with music, a print and a web gallery.', cover: 'demos/share/world-01-reine.jpg' },
];

const OPENED_KEY = 'formlit_demo_opened';

export function demosSectionHtml(): string {
  const cards = DEMOS.map((d) => `<button class="fl-demo-card" type="button" data-cmd="demo.${d.id}" data-demo-card="${d.id}"><span class="fl-demo-thumb"><img src="${d.cover}" alt="" decoding="async" draggable="false"></span><span class="fl-demo-title">${d.title}</span><span class="fl-demo-line">${d.line}</span></button>`).join('');
  return `<div class="fl-demos" data-demos-section><div class="fl-demos-head">Demos</div><div class="fl-demos-sub">Each demo opens as a new demo catalog with sample photos. Your own catalog is not changed.</div><div class="fl-demos-grid">${cards}</div></div>`;
}

class DemosDialog extends Dialog {
  constructor() {
    super('Demos', 720);
    this.body.appendChild(el(demosSectionHtml()));
    this.body.addEventListener('click', (e) => { if ((e.target as HTMLElement).closest('[data-demo-card]')) this.close(); });
    this.button('Close', 'primary', () => this.close());
  }
}

export function registerDemoCommands(ctx: Ctx): void {
  let dialog: DemosDialog | null = null;
  let opening = false;
  const open = async (d: DemoCard) => {
    if (opening) return;
    opening = true;
    const done = ctx.shell.busy(`Opening the ${d.title} demo`);
    try {
      try { sessionStorage.setItem(OPENED_KEY, d.id); } catch { /* storage off */ }
      await ctx.api.cmd('demo.open', { id: d.id });
    } catch (err) {
      try { sessionStorage.removeItem(OPENED_KEY); } catch { /* storage off */ }
      ctx.fail(err);
    } finally {
      opening = false;
      done();
    }
  };
  ctx.commands.add(
    { id: 'help.demos', label: 'Demos...', run: () => { dialog ??= new DemosDialog(); dialog.open(); } },
    ...DEMOS.map((d) => ({ id: `demo.${d.id}`, label: `${d.title} Demo`, enabled: () => !opening, run: () => { void open(d); } })),
  );
  let shown: string | null = null;
  try { shown = sessionStorage.getItem(OPENED_KEY); sessionStorage.removeItem(OPENED_KEY); } catch { shown = null; }
  const d = DEMOS.find((x) => x.id === shown);
  if (d) toast(`This is the ${d.title} demo catalog. Your own catalog is in File, Open Catalog.`);
}
