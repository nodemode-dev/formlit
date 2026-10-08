import type { Ctx } from '../../app';
import { library } from '../../state/library';
import { catalog } from '../../state/catalog';
import { confirmAction } from '../../ui/dialogs';
import { toast } from '../../ui/toast';

const ADVANCE_KEY = 'formlit_auto_advance';
let autoAdvance = false;
try { autoAdvance = localStorage.getItem(ADVANCE_KEY) === '1'; } catch { autoAdvance = false; }

export const LABELS = ['red', 'yellow', 'green', 'blue', 'purple'] as const;

export function hasPhotos(): boolean { return library.targets().length > 0; }

async function act(ctx: Ctx, cmd: string, params: Record<string, unknown>, advance = false): Promise<void> {
  const ids = library.targets();
  if (!ids.length) return;
  try {
    await ctx.api.cmd(cmd, { ids, ...params });
    if (advance && autoAdvance && ids.length === 1) library.step(1);
  } catch (err) { ctx.fail(err); }
}

export async function removePhotos(ctx: Ctx, fromDisk = false): Promise<void> {
  const ids = library.targets();
  if (!ids.length) return;
  const src = library.source;
  if (!fromDisk && src.kind === 'collection' && src.id) {
    await ctx.api.cmd('collection.removePhotos', { id: src.id, ids }).catch((e) => ctx.fail(e));
    return;
  }
  if (!fromDisk && src.kind === 'quick') {
    await ctx.api.cmd('quick.toggle', { ids }).catch((e) => ctx.fail(e));
    return;
  }
  const n = ids.length;
  const what = `${n} photo${n === 1 ? '' : 's'}`;
  const ok = await confirmAction(fromDisk ? 'Delete from Disk' : 'Remove from Catalog',
    fromDisk ? `Move the originals of ${what} to the system trash and remove them from the catalog? This cannot be undone from formlit; restore the files from the trash and import them again.` : `Remove ${what} from the catalog? The files on disk are not touched.`,
    fromDisk ? 'Delete' : 'Remove', fromDisk);
  if (!ok) return;
  await ctx.api.cmd(fromDisk ? 'photo.delete' : 'photo.remove', { ids }).catch((e) => ctx.fail(e));
}

export async function undoRedo(ctx: Ctx, redo: boolean): Promise<void> {
  try {
    const r = await ctx.api.cmd<{ label: string }>(redo ? 'edit.redo' : 'edit.undo');
    toast(`${redo ? 'Redo' : 'Undo'} ${r.label}`);
  } catch (err) { ctx.fail(err); }
}

export function registerPhotoActions(ctx: Ctx): void {
  const has = () => hasPhotos();
  const c = ctx.commands;
  c.add(
    { id: 'edit.undo', label: 'Undo', keys: ['Mod+Z'], run: () => void undoRedo(ctx, false) },
    { id: 'edit.redo', label: 'Redo', keys: ['Shift+Mod+Z', 'Mod+Y'], run: () => void undoRedo(ctx, true) },
    { id: 'edit.selectAll', label: 'Select All', keys: ['Mod+A'], run: () => library.selectAll() },
    { id: 'edit.selectNone', label: 'Select None', keys: ['Mod+D'], run: () => library.selectNone() },
    { id: 'edit.invertSelection', label: 'Invert Selection', run: () => library.invert() },
    { id: 'edit.selectPicks', label: 'Select Flagged Photos', keys: ['Alt+Mod+A'], run: () => library.selectWhere((p) => p.f > 0) },
    { id: 'edit.deselectUnflagged', label: 'Deselect Unflagged Photos', keys: ['Alt+Shift+Mod+D'], run: () => { for (const id of Array.from(library.selection)) if ((library.photo(id)?.f ?? 0) === 0) library.selection.delete(id); library.emitSelection(); } },
    { id: 'photo.prev', label: 'Previous Photo', keys: ['Left'], run: () => library.step(-1) },
    { id: 'photo.next', label: 'Next Photo', keys: ['Right'], run: () => library.step(1) },
    { id: 'photo.prevExtend', label: 'Add Previous to Selection', keys: ['Shift+Left'], run: () => library.step(-1, true) },
    { id: 'photo.nextExtend', label: 'Add Next to Selection', keys: ['Shift+Right'], run: () => library.step(1, true) },
    { id: 'photo.pick', label: 'Flag as Pick', keys: ['P'], run: () => void act(ctx, 'photo.flag', { flag: 'pick' }, true), enabled: has },
    { id: 'photo.reject', label: 'Set Flag: Rejected', keys: ['X'], run: () => void act(ctx, 'photo.flag', { flag: 'reject' }, true), enabled: has },
    { id: 'photo.unflag', label: 'Unflag', keys: ['U'], run: () => void act(ctx, 'photo.flag', { flag: 'none' }, true), enabled: has },
    { id: 'photo.toggleFlag', label: 'Toggle Flag', keys: ['`'], run: () => void act(ctx, 'photo.flag', { flag: 'pick', toggle: true }), enabled: has },
    { id: 'photo.flagUp', label: 'Increase Flag Status', keys: ['Mod+Up'], run: () => { const p = library.photo(library.active); void act(ctx, 'photo.flag', { flag: (p?.f ?? 0) < 0 ? 'none' : 'pick' }); }, enabled: has },
    { id: 'photo.flagDown', label: 'Decrease Flag Status', keys: ['Mod+Down'], run: () => { const p = library.photo(library.active); void act(ctx, 'photo.flag', { flag: (p?.f ?? 0) > 0 ? 'none' : 'reject' }); }, enabled: has },
    { id: 'photo.rateUp', label: 'Increase Rating', keys: [']'], run: () => void act(ctx, 'photo.rate', { delta: 1 }), enabled: has },
    { id: 'photo.rateDown', label: 'Decrease Rating', keys: ['['], run: () => void act(ctx, 'photo.rate', { delta: -1 }), enabled: has },
    { id: 'photo.rotateLeft', label: 'Rotate Left (CCW)', keys: ['Mod+['], run: () => void act(ctx, 'photo.rotate', { turns: -1 }), enabled: has },
    { id: 'photo.rotateRight', label: 'Rotate Right (CW)', keys: ['Mod+]'], run: () => void act(ctx, 'photo.rotate', { turns: 1 }), enabled: has },
    { id: 'photo.virtualCopy', label: 'Create Virtual Copy', keys: ["Mod+'"], run: () => void act(ctx, 'photo.virtualCopy', {}), enabled: has },
    { id: 'photo.setMaster', label: 'Set Copy as Master', run: () => { const id = library.active; if (id !== null) void ctx.api.cmd('photo.setMasterCopy', { id }).catch((e) => ctx.fail(e)); }, enabled: () => !!library.photo(library.active)?.m },
    { id: 'photo.quick', label: 'Add to Quick Collection', keys: ['B'], run: () => void act(ctx, 'quick.toggle', {}), enabled: has },
    { id: 'photo.quickClear', label: 'Clear Quick Collection', keys: ['Shift+Mod+B'], run: () => void ctx.api.cmd('quick.clear').then(() => toast('Quick Collection cleared'), (e) => ctx.fail(e)), enabled: () => catalog.tree.catalog.quick > 0 },
    { id: 'photo.target', label: 'Add to Target Collection', keys: ['Shift+B'], run: () => { const t = catalog.targetCollection(); if (t) void act(ctx, 'collection.addPhotos', { id: t.id }); else toast('Set a target collection first (right-click a collection)'); }, enabled: has },
    { id: 'photo.stack', label: 'Group into Stack', keys: ['Mod+G'], run: () => void act(ctx, 'stack.group', {}), enabled: () => library.targets().length > 1 },
    { id: 'photo.unstack', label: 'Unstack', keys: ['Shift+Mod+G'], run: () => void act(ctx, 'stack.ungroup', {}), enabled: has },
    { id: 'photo.toggleStack', label: 'Collapse or Expand Stack', keys: ['S'], run: () => void act(ctx, 'stack.toggle', {}), enabled: has },
    { id: 'photo.stackTop', label: 'Move to Top of Stack', keys: ['Shift+S'], run: () => { const id = library.active; if (id !== null) void ctx.api.cmd('stack.setTop', { id }).catch((e) => ctx.fail(e)); }, enabled: has },
    { id: 'photo.autoStack', label: 'Auto-Stack by Capture Time...', run: () => void ctx.api.cmd('stack.auto', { seconds: 60, ids: library.targets().length > 1 ? library.targets() : undefined }).then((r) => toast(`${(r as { stacks: number }).stacks} stacks made`), (e) => ctx.fail(e)) },
    { id: 'photo.remove', label: 'Remove Photos...', keys: ['Backspace', 'Delete'], run: () => void removePhotos(ctx), enabled: has },
    { id: 'photo.delete', label: 'Delete Photos from Disk...', keys: ['Alt+Shift+Mod+Backspace'], run: () => void removePhotos(ctx, true), enabled: has },
    { id: 'photo.deleteRejected', label: 'Delete Rejected Photos...', keys: ['Mod+Backspace'], run: () => { library.selectWhere((p) => p.f < 0); void removePhotos(ctx); }, enabled: () => library.ids.some((id) => (library.photo(id)?.f ?? 0) < 0) },
    { id: 'photo.reveal', label: /Mac/.test(navigator.platform) ? 'Show in Finder' : 'Show in Explorer', keys: ['Mod+R'], run: () => { const id = library.active; if (id !== null) void ctx.api.cmd('photo.reveal', { id }).catch((e) => ctx.fail(e)); }, enabled: has },
    { id: 'photo.saveMetadata', label: 'Save Metadata to Files', keys: ['Mod+S'], run: () => void act(ctx, 'photo.saveMetadata', {}).then(() => toast('Metadata saved to XMP')), enabled: has },
    { id: 'photo.readMetadata', label: 'Read Metadata from Files', run: () => void act(ctx, 'photo.readMetadata', {}), enabled: has },
    { id: 'photo.autoAdvance', label: 'Auto Advance', run: () => { autoAdvance = !autoAdvance; try { localStorage.setItem(ADVANCE_KEY, autoAdvance ? '1' : '0'); } catch { return; } }, checked: () => autoAdvance },
  );
  for (let r = 0; r <= 5; r += 1) {
    c.add({ id: `photo.rate${r}`, label: r === 0 ? 'No Rating' : `${r} Star${r > 1 ? 's' : ''}`, keys: [String(r)], run: () => void act(ctx, 'photo.rate', { rating: r }, true), enabled: has });
  }
  LABELS.forEach((l, i) => {
    c.add({ id: `photo.label.${l}`, label: () => catalog.labelName(l), keys: i < 4 ? [String(6 + i)] : [], run: () => void act(ctx, 'photo.label', { label: l, toggle: true }, true), enabled: has });
  });
  c.add({ id: 'photo.label.none', label: 'No Color Label', run: () => void act(ctx, 'photo.label', { label: 'none', toggle: false }), enabled: has });
}
