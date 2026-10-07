import { library } from '../state/library';
import { el, escapeHtml, q, setHtml, setText } from './dom';
import { ThumbGrid } from './grid';
import { icon } from './icons';

export function sourceLabel(): string {
  return library.source.label || (library.source.kind === 'all' ? 'All Photographs' : library.source.kind);
}

export class Filmstrip {
  readonly grid: ThumbGrid;
  private readonly source: HTMLElement;
  private readonly count: HTMLElement;
  onOpen: ((id: number) => void) | null = null;
  onContext: ((id: number, e: MouseEvent) => void) | null = null;

  constructor(host: HTMLElement) {
    const head = el(`<div class="fl-fs-head"><button class="cv-icon-btn" type="button" data-cmd="photo.prev" aria-label="Previous Photo">${icon('chevronLeft', 14)}</button><button class="cv-icon-btn" type="button" data-cmd="photo.next" aria-label="Next Photo">${icon('chevronRight', 14)}</button><span class="fl-fs-source"></span><span class="fl-fs-count"></span><button class="cv-icon-btn" type="button" data-cmd="library.filterPicks" aria-label="Show Picks">${icon('flagPick', 14)}</button><button class="cv-icon-btn" type="button" data-cmd="library.filterOff" aria-label="Filters Off">${icon('funnel', 14)}</button></div>`);
    this.source = q(head, '.fl-fs-source');
    this.count = q(head, '.fl-fs-count');
    this.grid = new ThumbGrid({ axis: 'x', cls: 'fl-fs', names: false, compact: true, onOpen: (id) => this.onOpen?.(id), onContext: (id, e) => this.onContext?.(id, e) });
    host.append(head, this.grid.root);
    library.listen('list', () => this.sync());
    library.listen('selection', () => this.sync());
    this.grid.show(true);
  }

  private sync(): void {
    setHtml(this.source, `<strong>${escapeHtml(sourceLabel())}</strong>${library.hasFilter() ? ' · filtered' : ''}`, `${sourceLabel()}|${library.hasFilter()}`);
    const n = library.ids.length;
    const s = library.selected().length;
    const i = library.index(library.active);
    const p = library.photo(library.active);
    setText(this.count, n ? `${n} photo${n === 1 ? '' : 's'} · ${s} selected${p ? ` · ${i + 1} of ${n} · ${p.file}` : ''}` : 'No photos');
  }
}
