import { Dialog } from '../../frontend/src/ui/dialogs';
import { el, escapeHtml, q, setText } from '../../frontend/src/ui/dom';
import { toast } from '../../frontend/src/ui/toast';
import { Renderer } from './engine/render';
import { GROUPS, GROUP_LABELS, applyGroups, clone, defaultSyncGroups, prune, type Dev } from './engine/settings';
import { develop } from './shims/develop';
import { store, toBlob, type Item } from './store';
import { zipStore } from './zip';

export interface ExportOptions { format: 'jpeg' | 'png' | 'webp'; quality: number; long: number; suffix: string }

const EXT = { jpeg: 'jpg', png: 'png', webp: 'webp' } as const;
const MIME = { jpeg: 'image/jpeg', png: 'image/png', webp: 'image/webp' } as const;
const exporter = new Renderer();

export async function renderExport(item: Item, o: ExportOptions): Promise<{ blob: Blob; name: string; w: number; h: number }> {
  await store.ensureFull(item.id);
  const r = exporter.render(item.src, item.dev, o.long > 0 ? o.long : null);
  const c = document.createElement('canvas');
  c.width = r.w;
  c.height = r.h;
  c.getContext('2d')?.putImageData(new ImageData(r.rgba, r.w, r.h), 0, 0);
  const blob = await toBlob(c, MIME[o.format], o.quality / 100);
  exporter.drop(item.src.id);
  const base = item.name.replace(/\.[^.]+$/, '');
  return { blob, name: `${base}${o.suffix}.${EXT[o.format]}`, w: r.w, h: r.h };
}

export function save(blob: Blob, name: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 4000);
}

const SIZES: Array<[string, number]> = [['Full size', 0], ['4096 px long edge', 4096], ['2048 px long edge', 2048], ['1600 px long edge', 1600], ['1080 px long edge', 1080], ['640 px long edge', 640]];

let exportDialog: Dialog | null = null;

export function openExport(items: Item[]): void {
  if (!items.length) { toast('Select a photo to export', 'error'); return; }
  exportDialog ??= new Dialog('Export', 460);
  const d = exportDialog;
  d.body.textContent = '';
  d.foot.textContent = '';
  const fmt = el<HTMLSelectElement>('<select class="cv-select"><option value="jpeg">JPEG</option><option value="png">PNG</option><option value="webp">WebP</option></select>');
  const size = el<HTMLSelectElement>(`<select class="cv-select">${SIZES.map(([l, v]) => `<option value="${v}">${l}</option>`).join('')}</select>`);
  const qual = el<HTMLInputElement>('<input class="cv-input" type="number" min="10" max="100" value="90">');
  const suffix = el<HTMLInputElement>('<input class="cv-input" type="text" value="-formlit">');
  const zip = el<HTMLInputElement>('<input type="checkbox">');
  d.field('Format', fmt);
  d.field('Size', size);
  d.field('Quality', qual);
  d.field('File name suffix', suffix);
  if (items.length > 1) {
    zip.checked = true;
    const row = d.field('Bundle as one ZIP', zip);
    row.classList.add('cv-field-check');
  }
  const note = el('<p class="cv-note"></p>');
  setText(note, items.length > 1 ? `${items.length} photos are rendered here in your browser, then saved.` : `${items[0].name} is rendered here in your browser, then saved.`);
  d.body.appendChild(note);
  const go = d.button(items.length > 1 ? `Export ${items.length}` : 'Export', 'primary', () => { void run(); });
  d.button('Cancel', 'ghost', () => d.close());
  const run = async (): Promise<void> => {
    const o: ExportOptions = { format: fmt.value as ExportOptions['format'], quality: Math.max(10, Math.min(100, Number(qual.value) || 90)), long: Number(size.value), suffix: suffix.value };
    go.disabled = true;
    try {
      const made: Array<{ blob: Blob; name: string }> = [];
      for (const it of items) {
        setText(note, `Rendering ${made.length + 1} of ${items.length}: ${it.name}`);
        await new Promise((r) => window.setTimeout(r, 0));
        made.push(await renderExport(it, o));
      }
      if (made.length === 1) save(made[0].blob, made[0].name);
      else if (zip.checked) {
        const used = new Set<string>();
        const entries = await Promise.all(made.map(async (m) => {
          let name = m.name;
          for (let n = 2; used.has(name); n += 1) name = m.name.replace(/(\.[^.]+)$/, `-${n}$1`);
          used.add(name);
          return { name, data: new Uint8Array(await m.blob.arrayBuffer()) };
        }));
        save(zipStore(entries), 'formlit-demo-export.zip');
      } else for (const m of made) save(m.blob, m.name);
      toast(`Exported ${made.length} file${made.length === 1 ? '' : 's'}`);
      d.close();
    } catch (err) {
      toast(String((err as Error).message || err), 'error');
    } finally {
      go.disabled = false;
    }
  };
  d.open();
}

export function copySettings(item: Item | null): void {
  if (!item) return;
  store.clipboard = clone(item.dev);
  toast('Settings copied');
}

export function pasteSettings(items: Item[]): void {
  const clip = store.clipboard;
  if (!clip) { toast('Copy settings from a photo first', 'error'); return; }
  const groups = defaultSyncGroups();
  for (const it of items) {
    const next = applyGroups(clone(it.dev), clone(clip), groups);
    store.commit(it, prune(next), 'Paste Settings');
    if (develop.item?.id === it.id) develop.resync();
  }
  toast(`Pasted settings to ${items.length} photo${items.length === 1 ? '' : 's'}`);
}

let syncDialog: Dialog | null = null;

export function openSync(source: Item | null, targets: Item[]): void {
  if (!source) return;
  const others = targets.filter((t) => t.id !== source.id);
  if (!others.length) { toast('Select more than one photo to sync settings', 'error'); return; }
  syncDialog ??= new Dialog('Synchronize Settings', 400);
  const d = syncDialog;
  d.body.textContent = '';
  d.foot.textContent = '';
  const on = new Set(defaultSyncGroups());
  const list = el('<div class="fl-sync"></div>');
  for (const [id, label] of GROUP_LABELS) {
    if (!(id in GROUPS)) continue;
    const row = el(`<label class="cv-field cv-field-check"><input type="checkbox"><span></span></label>`);
    const box = q<HTMLInputElement>(row, 'input');
    box.checked = on.has(id);
    setText(q(row, 'span'), label);
    box.addEventListener('change', () => { if (box.checked) on.add(id); else on.delete(id); });
    list.appendChild(row);
  }
  d.body.appendChild(list);
  d.button('Synchronize', 'primary', () => {
    for (const it of others) {
      store.commit(it, prune(applyGroups(clone(it.dev), clone(source.dev), [...on])), 'Sync Settings');
      if (develop.item?.id === it.id) develop.resync();
    }
    toast(`Synchronized ${others.length} photo${others.length === 1 ? '' : 's'} from ${source.name}`);
    d.close();
  });
  d.button('Cancel', 'ghost', () => d.close());
  d.open();
}

export function exportSettings(item: Item | null): void {
  if (!item) return;
  const body = JSON.stringify({ formlit: 'develop-settings', version: 1, photo: item.name, settings: item.dev }, null, 2);
  save(new Blob([body], { type: 'application/json' }), `${item.name.replace(/\.[^.]+$/, '')}.formlit.json`);
}

export function importSettings(items: Item[]): void {
  if (!items.length) return;
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.json,application/json';
  input.addEventListener('change', () => {
    const f = input.files?.[0];
    if (!f) return;
    void f.text().then((t) => {
      const j = JSON.parse(t) as { formlit?: string; settings?: Dev };
      if (j.formlit !== 'develop-settings' || !j.settings) throw new Error('Not a formlit settings file');
      for (const it of items) {
        store.commit(it, prune(clone(j.settings as Dev)), 'Import Settings');
        if (develop.item?.id === it.id) develop.resync();
      }
      toast(`Applied ${f.name} to ${items.length} photo${items.length === 1 ? '' : 's'}`);
    }).catch((err: Error) => toast(err.message, 'error'));
  });
  input.click();
}

export function resetSettings(item: Item | null): void {
  if (!item) return;
  store.commit(item, {}, 'Reset');
  if (develop.item?.id === item.id) develop.resync();
}

let infoDialog: Dialog | null = null;

export function openInfo(item: Item | null): void {
  if (!item) return;
  infoDialog ??= new Dialog('Photo Information', 440);
  const d = infoDialog;
  d.body.textContent = '';
  d.foot.textContent = '';
  const e = item.exif;
  const rows: Array<[string, string]> = [
    ['File', item.name], ['Format', item.fmt], ['Dimensions', `${item.fullW} x ${item.fullH}`], ['Size', item.bytes ? `${(item.bytes / 1048576).toFixed(2)} MB` : 'generated'],
    ['Camera', [e.make, e.model].filter(Boolean).join(' ') || 'unknown'], ['Lens', e.lens ?? 'unknown'], ['ISO', e.iso ? String(e.iso) : 'unknown'],
    ['Shutter', e.exposure ?? 'unknown'], ['Aperture', e.fnumber ? `f/${e.fnumber}` : 'unknown'], ['Focal length', e.focal ? `${e.focal} mm` : 'unknown'],
    ['Captured', e.time ?? 'unknown'], ['Software', e.software ?? 'none'], ['Edits', String(Object.keys(prune(item.dev)).length)],
  ];
  if (item.note) rows.push(['Note', item.note]);
  const table = el(`<div class="fl-kv">${rows.map(([k, v]) => `<div class="fl-kv-row"><span>${escapeHtml(k)}</span><strong>${escapeHtml(v)}</strong></div>`).join('')}</div>`);
  d.body.appendChild(table);
  d.button('Close', 'primary', () => d.close());
  d.open();
}
