import { clone } from '../../../demo/src/engine/settings';
import { library } from '../../../demo/src/shims/library';
import { store, type Item } from '../../../demo/src/store';

const stems = new Map<number, string>();
const masters = new Map<number, number>();
const SHARED = ['src', 'small', 'full', 'blob', 'used'] as const;

export const stemOf = (item: Item): string => stems.get(item.id) ?? item.name.replace(/\.[^.]+$/, '');
export const masterOf = (item: Item): number | null => masters.get(item.id) ?? null;
export const isVirtual = (item: Item): boolean => masters.has(item.id);

let seq = 900000;

export function createVirtualCopy(master: Item): Item {
  const root = store.items.get(masters.get(master.id) ?? master.id) ?? master;
  const n = Array.from(masters.values()).filter((m) => m === root.id).length + 1;
  const id = seq++;
  const stem = stemOf(root);
  const copy = {
    ...root,
    id,
    name: `${stem}-copy-${n}.jpg`,
    dev: clone(master.dev),
    hist: [{ label: 'Virtual Copy', dev: clone(master.dev) }],
    hi: 0,
    rev: 1,
    added: Date.now(),
    thumb: '',
    preview: '',
    previewRev: 0,
    thumbRev: 0,
    rating: master.rating,
    flag: 0,
    label: 'purple',
    keywords: [...master.keywords, 'virtual copy'],
    collection: 'virtual',
    note: `Virtual copy of ${root.name}; it shares the photo and keeps its own settings and history`,
  } as Item;
  for (const k of SHARED) Object.defineProperty(copy, k, { get: () => root[k], set: (v) => { (root as unknown as Record<string, unknown>)[k] = v; }, enumerable: true, configurable: true });
  stems.set(id, stem);
  masters.set(id, root.id);
  store.items.set(id, copy);
  const at = store.order.indexOf(master.id);
  store.order.splice(at < 0 ? store.order.length : at + 1, 0, id);
  store.emit('list');
  store.scheduleThumb(id, 0);
  library.setActive(id, false);
  return copy;
}
