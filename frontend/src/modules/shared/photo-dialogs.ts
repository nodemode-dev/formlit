import type { Ctx } from '../../app';
import { catalog } from '../../state/catalog';
import { library } from '../../state/library';
import { askForm } from '../../ui/askform';
import { pickFolder } from '../../ui/folder-picker';
import { toast } from '../../ui/toast';
import { whenDone } from './tasks';

interface Editors { editors: Array<{ name: string; path: string }>; options: { format: string; space: string; depth: number } }

function pad(n: number): string { return String(n).padStart(2, '0'); }

function localIso(t: string | null): string {
  if (!t) return '';
  return t.slice(0, 16);
}

function example(template: string, custom: string, start: number): string {
  const id = library.active ?? library.targets()[0];
  const p = id !== undefined && id !== null ? library.photo(id) : undefined;
  const name = (p?.file ?? 'IMG_0001.CR3').replace(/\.[^.]+$/, '');
  const ext = (p?.file ?? '.cr3').split('.').pop()?.toLowerCase() ?? '';
  const when = p?.t ? new Date(p.t.slice(0, 19)) : new Date();
  const num = /(\d+)$/.exec(name)?.[1] ?? String(start);
  const out = template.replace(/\{([a-z]+)(?::([^}]*))?\}/g, (m, k: string, arg: string | undefined) => {
    switch (k) {
      case 'name': return name;
      case 'ext': return ext;
      case 'seq': return String(start).padStart(Number(arg) || 1, '0');
      case 'num': return num;
      case 'year': return String(when.getFullYear());
      case 'month': return pad(when.getMonth() + 1);
      case 'day': return pad(when.getDate());
      case 'date': return `${when.getFullYear()}${pad(when.getMonth() + 1)}${pad(when.getDate())}`;
      case 'hour': return pad(when.getHours());
      case 'minute': return pad(when.getMinutes());
      case 'custom': return custom;
      default: return m;
    }
  });
  return `Example: ${out}.${ext}`;
}

export function registerPhotoDialogs(ctx: Ctx): void {
  const has = () => library.targets().length > 0;
  ctx.commands.add(
    {
      id: 'library.labelSet', label: 'Edit Color Label Set...',
      run: async () => {
        const labels: Array<[string, string]> = [['red', 'Red'], ['yellow', 'Yellow'], ['green', 'Green'], ['blue', 'Blue'], ['purple', 'Purple']];
        const v = await askForm('Edit Color Label Set', 'Name what each color means in your workflow. The names show in menus, filters and tooltips.', labels.map(([k, l]) => ({ path: k, label: l, kind: 'text' as const })),
          Object.fromEntries(labels.map(([k]) => [k, catalog.labelName(k)])), 'Save');
        if (!v) return;
        try {
          await ctx.api.cmd('library.labelNames', { names: Object.fromEntries(labels.map(([k, l]) => [k, String(v[k] ?? '').trim() || l])) });
          await catalog.refresh();
          toast('Color label set saved');
        } catch (err) { ctx.fail(err); }
      },
    },
    {
      id: 'library.locate', label: 'Locate Missing Photo...', enabled: () => !!library.photo(library.active)?.miss,
      run: async () => {
        const id = library.active;
        const p = id !== null ? library.photo(id) : undefined;
        if (id === null || !p) return;
        const dir = await pickFolder('Locate Missing Photo', `Choose the folder that now holds ${p.file}. Other missing photos from its old folder are found there too.`, '', 'Locate');
        if (!dir) return;
        try {
          const r = await ctx.api.cmd<{ found: number[] }>('photo.relink', { id, path: dir, nearby: true });
          toast(r.found.length > 1 ? `Found ${p.file} and ${r.found.length - 1} more` : `Found ${p.file}`);
        } catch (err) { ctx.fail(err); }
      },
    },
    {
      id: 'library.editIn', label: 'Edit In...', keys: ['Mod+E'], enabled: has,
      run: async () => {
        const ids = library.targets();
        let eds: Editors;
        try { eds = await ctx.api.cmd<Editors>('editIn.apps'); } catch (err) { ctx.fail(err); return; }
        const apps: Array<[string, string]> = eds.editors.map((e) => [e.path, e.name] as [string, string]);
        apps.push(['', apps.length ? 'Other application...' : 'Choose an application...']);
        const v = await askForm('Edit In', `Open ${ids.length === 1 ? 'this photo' : `${ids.length} photos`} in another application. Copies are stacked with their originals.`, [
          { path: 'app', label: 'Application', kind: 'select', options: apps },
          { path: 'custom', label: 'Path', kind: 'text', placeholder: '/Applications/formvis.app', show: (g) => !g('app') },
          { path: 'mode', label: 'Edit', kind: 'select', options: [['copy', 'A copy with formlit adjustments'], ['copyNoEdits', 'A copy without adjustments'], ['original', 'The original'], ['layers', 'All selected photos as layers of one PSD']] },
          { path: 'format', label: 'File format', kind: 'select', options: [['tiff', 'TIFF'], ['psd', 'PSD'], ['png', 'PNG'], ['jpeg', 'JPEG']], show: (g) => g('mode') !== 'layers' },
          { path: 'space', label: 'Color space', kind: 'select', options: [['prophoto', 'ProPhoto RGB'], ['adobergb', 'Adobe RGB (1998)'], ['p3', 'Display P3'], ['srgb', 'sRGB']] },
          { path: 'depth', label: 'Bit depth', kind: 'select', options: [['16', '16 bits/component'], ['8', '8 bits/component']] },
        ], { app: apps[0][0], custom: '', mode: 'copy', format: eds.options.format, space: eds.options.space, depth: String(eds.options.depth) }, 'Edit');
        if (!v) return;
        const app = String(v.custom || v.app || '');
        try {
          if (v.custom) await ctx.api.cmd('editIn.addApp', { name: '', path: v.custom });
          const start = await ctx.api.cmd<{ task: number }>('photo.editIn', { ids, app, mode: v.mode, format: v.format, space: v.space, depth: Number(v.depth), wait: false });
          const r = await whenDone(start.task);
          toast(r.launched ? `Opened in ${String(app).split(/[\\/]/).pop()}` : `Saved ${(r.paths as string[]).length} for editing. Add an editor in Edit In to open it automatically.`);
        } catch (err) { ctx.fail(err); }
      },
    },
    {
      id: 'library.captureTime', label: 'Edit Capture Time...', enabled: has,
      run: async () => {
        const ids = library.targets();
        const first = library.photo(library.active ?? ids[0]);
        const v = await askForm('Edit Capture Time', `Changes the capture time of ${ids.length} ${ids.length === 1 ? 'photo' : 'photos'} in the catalog. Use Save Metadata to write it to the files.`, [
          { path: 'mode', label: 'Type', kind: 'select', options: [['set', 'Adjust to a date and time'], ['shift', 'Shift by hours (time zone)']] },
          { path: 'time', label: 'New time', kind: 'text', placeholder: 'YYYY-MM-DDTHH:MM', show: (g) => g('mode') === 'set' },
          { path: 'hours', label: 'Shift hours', kind: 'number', step: 1, min: -48, max: 48, show: (g) => g('mode') === 'shift' },
          { path: 'minutes', label: 'Shift minutes', kind: 'number', step: 1, min: -59, max: 59, show: (g) => g('mode') === 'shift' },
          { path: '', label: 'With several photos, Adjust moves all of them by the same amount the active photo moves.', kind: 'note', show: (g) => g('mode') === 'set' },
        ], { mode: 'set', time: localIso(first?.t ?? null), hours: 0, minutes: 0 }, 'Change All');
        if (!v) return;
        try {
          if (v.mode === 'shift') await ctx.api.cmd('photo.setCaptureTime', { ids, shiftSeconds: Number(v.hours || 0) * 3600 + Number(v.minutes || 0) * 60 });
          else await ctx.api.cmd('photo.setCaptureTime', { ids, time: `${String(v.time)}${String(v.time).length === 16 ? ':00' : ''}` });
          toast(`Changed the capture time of ${ids.length} ${ids.length === 1 ? 'photo' : 'photos'}`);
        } catch (err) { ctx.fail(err); }
      },
    },
    {
      id: 'library.rename', label: 'Rename Photos...', keys: ['F2'], enabled: has,
      run: async () => {
        const ids = library.targets();
        const v = await askForm(`Rename ${ids.length} ${ids.length === 1 ? 'Photo' : 'Photos'}`, 'Renames the files on disk and in the catalog. Sidecars follow their photos.', [
          { path: 'template', label: 'Template', kind: 'select', options: [['{custom}-{seq:3}', 'Custom Name - Sequence'], ['{date:%Y%m%d}-{seq:4}', 'Date - Sequence'], ['{name}', 'Filename'], ['{custom}-{num}', 'Custom Name - Original Number'], ['{date:%Y-%m-%d}_{name}', 'Date_Filename']] },
          { path: 'free', label: 'Or type', kind: 'text', placeholder: '{custom}-{seq:3}' },
          { path: 'custom', label: 'Custom text', kind: 'text' },
          { path: 'start', label: 'Start number', kind: 'number', min: 0 },
        ], { template: '{custom}-{seq:3}', free: '', custom: 'Untitled', start: 1 }, 'Rename', (vals) => example(String(vals.free || vals.template), String(vals.custom ?? ''), Number(vals.start ?? 1)));
        if (!v) return;
        try {
          await ctx.api.cmd('photo.rename', { ids, template: String(v.free || v.template), custom: String(v.custom ?? ''), start: Number(v.start ?? 1) });
          toast(`Renamed ${ids.length} ${ids.length === 1 ? 'photo' : 'photos'}`);
        } catch (err) { ctx.fail(err); }
      },
    },
  );
}
