import { develop } from '../../../demo/src/shims/develop';
import { library } from '../../../demo/src/shims/library';
import { store, type Item } from '../../../demo/src/store';
import { el, patchList, q, setClass, setText } from '../../../frontend/src/ui/dom';
import { icon } from '../../../frontend/src/ui/icons';
import { Panel } from '../../../frontend/src/ui/panel';
import { toast } from '../../../frontend/src/ui/toast';
import { createVirtualCopy, isVirtual, masterOf } from './virtual-copy';

interface Row { id: number; label: string; kind: string; on: boolean; edits: number }

export class VersionsPanel {
  readonly panel: Panel;
  private readonly rows: HTMLElement;
  private readonly note: HTMLElement;

  constructor(host: HTMLElement, before: Element | null) {
    const add = el<HTMLButtonElement>(`<button class="cv-icon-btn" type="button" title="Create Virtual Copy" aria-label="Create Virtual Copy">${icon('virtualCopy', 14)}</button>`);
    this.panel = new Panel('dev.versions', 'Virtual Copies', { open: true, tools: [add] });
    add.addEventListener('click', (e) => { e.stopPropagation(); this.make(); });
    this.rows = el('<div class="fl-list fl-versions"></div>');
    this.note = el('<div class="fl-muted fl-versions-note">A virtual copy shares the original photo and keeps its own settings, history and masks.</div>');
    this.panel.body.append(this.rows, this.note);
    if (before) host.insertBefore(this.panel.root, before); else host.appendChild(this.panel.root);
    this.rows.addEventListener('click', (e) => {
      const id = Number((e.target as HTMLElement).closest<HTMLElement>('[data-id]')?.dataset.id);
      if (id) library.setActive(id, false);
    });
    store.listen('list', () => this.sync());
    store.listen('item', () => this.sync());
    develop.listen((why) => { if (why === 'open') this.sync(); });
    this.sync();
  }

  make(): void {
    const item = develop.item;
    if (!item) { toast('Open a photo first', 'error'); return; }
    createVirtualCopy(item);
    toast('Virtual copy created: its settings and history are its own');
  }

  private family(item: Item): Item[] {
    const root = masterOf(item) ?? item.id;
    return store.order.map((id) => store.items.get(id)).filter((x): x is Item => !!x && (x.id === root || masterOf(x) === root));
  }

  sync(): void {
    const cur = develop.item;
    const list = cur ? this.family(cur) : [];
    let n = 0;
    const rows: Row[] = list.map((it) => ({ id: it.id, label: isVirtual(it) ? `Copy ${(n += 1)}` : 'Master', kind: isVirtual(it) ? 'virtual' : 'master', on: it.id === cur?.id, edits: Math.max(0, it.hist.length - 1) }));
    patchList(this.rows, rows, {
      key: (r) => String(r.id),
      create: (r) => {
        const row = el('<button class="fl-list-row" type="button"><span></span><em></em></button>');
        row.dataset.id = String(r.id);
        setText(q(row, 'span'), r.label);
        setText(q(row, 'em'), `${r.edits} steps`);
        setClass(row, 'is-on', r.on);
        return row;
      },
      update: (node, r) => { node.dataset.id = String(r.id); setText(q(node, 'span'), r.label); setText(q(node, 'em'), `${r.edits} steps`); setClass(node, 'is-on', r.on); },
    });
  }
}
