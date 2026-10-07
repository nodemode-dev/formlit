import type { Ctx } from '../../app';
import { library } from '../../state/library';
import { confirmAction, Dialog, promptName } from '../../ui/dialogs';
import { el, escapeHtml, patchList, q, setClass, setDisabled, setText } from '../../ui/dom';
import { Form, getPath, setPath, type FieldSpec } from '../../ui/form';
import { toast } from '../../ui/toast';
import { actionToast, openOutput, whenDone } from './tasks';

type Settings = Record<string, Record<string, unknown>>;
interface Preset { id: string; name: string; settings: Settings; builtin: boolean }
interface Options { formats: Record<string, { ext: string; label: string; depths: number[]; quality: boolean }>; spaces: Record<string, string>; metadata: Record<string, string>; tokens: Record<string, string>; defaults: Settings; ffmpeg: boolean }

const LAST_KEY = 'formlit_export_last';

function clone<T>(v: T): T { return JSON.parse(JSON.stringify(v)) as T; }

function merge(base: Settings, over: Partial<Settings>): Settings {
  const out = clone(base);
  for (const [k, v] of Object.entries(over ?? {})) out[k] = { ...(out[k] ?? {}), ...(v ?? {}) };
  return out;
}

class ExportDialog extends Dialog {
  private opts: Options | null = null;
  private settings: Settings = {};
  private presets: Preset[] = [];
  private current = '';
  private ids: number[] = [];
  private readonly list = el('<div class="fl-exp-presets"></div>');
  private readonly main = el('<div class="fl-exp-main"></div>');
  private readonly forms: Form[] = [];
  private readonly runBtn: HTMLButtonElement;
  private readonly removeBtn: HTMLButtonElement;

  constructor(private readonly ctx: Ctx) {
    super('Export', 880);
    q<HTMLElement>(this.scrim, '.cv-dialog').classList.add('fl-exp');
    const side = el('<div class="fl-exp-side"><div class="fl-sub">Presets</div></div>');
    side.appendChild(this.list);
    const wrap = el('<div class="fl-exp-wrap"></div>');
    wrap.append(side, this.main);
    this.body.appendChild(wrap);
    this.list.addEventListener('click', (e) => {
      const r = (e.target as HTMLElement).closest<HTMLElement>('[data-key]');
      if (r) this.apply(r.dataset.key as string);
    });
    this.button('Add Preset...', 'ghost', () => void this.savePreset()).classList.add('cv-btn-apart');
    this.removeBtn = this.button('Remove', 'ghost', () => void this.removePreset());
    this.button('Cancel', 'ghost', () => this.close());
    this.runBtn = this.button('Export', 'primary', () => void this.run());
  }

  private sections(o: Options): Array<[string, FieldSpec[]]> {
    const fmt = () => String(getPath(this.settings, 'file.format'));
    const rendered = () => !['original', 'dng'].includes(fmt());
    const sizeMode = () => String(getPath(this.settings, 'size.mode'));
    const resize = () => rendered() && !!getPath(this.settings, 'size.resize');
    const wm = () => rendered() && !!getPath(this.settings, 'watermark.on');
    const metaOpts = Object.entries(o.metadata) as Array<[string, string]>;
    return [
      ['Export Location', [
        { path: 'destination.sameAsOriginal', label: 'Same folder as original', kind: 'check' },
        { path: 'destination.folder', label: 'Folder', kind: 'text', wide: true, show: () => !getPath(this.settings, 'destination.sameAsOriginal') },
        { path: 'destination.useSubfolder', label: 'Put in subfolder', kind: 'check' },
        { path: 'destination.subfolder', label: 'Subfolder', kind: 'text', placeholder: '{date:%Y-%m-%d}', show: () => !!getPath(this.settings, 'destination.useSubfolder') },
        { path: 'destination.existing', label: 'Existing files', kind: 'select', options: [['unique', 'Choose a new name'], ['overwrite', 'Overwrite without warning'], ['skip', 'Skip']] },
        { path: 'destination.addToCatalog', label: 'Add to catalog', kind: 'check' },
        { path: 'destination.stack', label: 'Stack with original', kind: 'check', show: () => !!getPath(this.settings, 'destination.addToCatalog') },
      ]],
      ['File Naming', [
        { path: 'naming.rename', label: 'Rename', kind: 'check' },
        { path: 'naming.template', label: 'Template', kind: 'text', placeholder: '{name}-{seq:3}', show: () => !!getPath(this.settings, 'naming.rename') },
        { path: 'naming.custom', label: 'Custom text', kind: 'text', show: () => !!getPath(this.settings, 'naming.rename') && String(getPath(this.settings, 'naming.template')).includes('{custom}') },
        { path: 'naming.start', label: 'Start number', kind: 'number', min: 0, show: () => !!getPath(this.settings, 'naming.rename') && String(getPath(this.settings, 'naming.template')).includes('{seq') },
        { path: 'naming.case', label: 'Extensions', kind: 'select', options: [['keep', 'Keep case'], ['lower', 'lower case'], ['upper', 'UPPER CASE']] },
        { path: '', label: `Tokens: ${Object.keys(o.tokens).map((t) => `{${t}}`).join(' ')}`, kind: 'note', show: () => !!getPath(this.settings, 'naming.rename') },
      ]],
      ['File Settings', [
        { path: 'file.format', label: 'Image format', kind: 'select', options: Object.entries(o.formats).map(([k, v]) => [k, v.label] as [string, string]) },
        { path: 'file.quality', label: 'Quality', kind: 'range', min: 1, max: 100, show: () => !!o.formats[fmt()]?.quality },
        { path: 'file.limitKB', label: 'Limit file size', kind: 'number', min: 0, step: 50, unit: 'KB, 0 is off', show: () => !!o.formats[fmt()]?.quality },
        { path: 'file.depth', label: 'Bit depth', kind: 'seg', options: [['8', '8 bit'], ['16', '16 bit']], show: () => ['png', 'tiff'].includes(fmt()) },
        { path: 'file.compression', label: 'Compression', kind: 'select', options: [['none', 'None'], ['zip', 'ZIP']], show: () => fmt() === 'tiff' },
        { path: 'file.hdr', label: 'HDR Output', kind: 'check', show: () => ['jpeg', 'avif', 'jxl', 'tiff'].includes(fmt()) },
        { path: 'file.hdrStops', label: 'HDR headroom', kind: 'select', options: [['1', '+1 stop'], ['2', '+2 stops'], ['3', '+3 stops'], ['4', '+4 stops']], show: () => ['jpeg', 'avif', 'jxl', 'tiff'].includes(fmt()) && !!getPath(this.settings, 'file.hdr') },
        { path: '', label: 'Writes an Ultra HDR JPEG: a normal JPEG for every viewer, plus a gain map that HDR screens use to brighten highlights.', kind: 'note', show: () => fmt() === 'jpeg' && !!getPath(this.settings, 'file.hdr') },
        { path: '', label: 'Writes 10-bit Rec. 2100 PQ with SDR white at 203 nits; HDR screens show the highlights above it.', kind: 'note', show: () => (fmt() === 'avif' || fmt() === 'jxl') && !!getPath(this.settings, 'file.hdr') },
        { path: '', label: 'Writes 32-bit floating point linear Rec. 2020, 1.0 at SDR white, for HDR finishing in other apps.', kind: 'note', show: () => fmt() === 'tiff' && !!getPath(this.settings, 'file.hdr') },
        { path: 'file.space', label: 'Color space', kind: 'select', options: Object.entries(o.spaces) as Array<[string, string]>, show: rendered },
        { path: '', label: 'Original exports the untouched file with an XMP sidecar holding your edits. DNG writes a linear DNG of the original plus the sidecar.', kind: 'note', show: () => !rendered() },
      ]],
      ['Image Sizing', [
        { path: 'size.resize', label: 'Resize to fit', kind: 'check', show: rendered },
        { path: 'size.mode', label: 'Fit', kind: 'select', options: [['long', 'Long Edge'], ['short', 'Short Edge'], ['wh', 'Width and Height'], ['dims', 'Dimensions'], ['mp', 'Megapixels'], ['percent', 'Percentage']], show: resize },
        { path: 'size.value', label: 'Size', kind: 'number', min: 16, unit: 'px', show: () => resize() && ['long', 'short'].includes(sizeMode()) },
        { path: 'size.w', label: 'Width', kind: 'number', min: 16, unit: 'px', show: () => resize() && ['wh', 'dims'].includes(sizeMode()) },
        { path: 'size.h', label: 'Height', kind: 'number', min: 16, unit: 'px', show: () => resize() && ['wh', 'dims'].includes(sizeMode()) },
        { path: 'size.mp', label: 'Megapixels', kind: 'number', min: 0.1, step: 0.5, unit: 'MP', show: () => resize() && sizeMode() === 'mp' },
        { path: 'size.percent', label: 'Percent', kind: 'number', min: 1, max: 400, unit: '%', show: () => resize() && sizeMode() === 'percent' },
        { path: 'size.noEnlarge', label: 'Don’t enlarge', kind: 'check', show: resize },
        { path: 'size.ppi', label: 'Resolution', kind: 'number', min: 10, max: 2400, unit: 'ppi', show: rendered },
      ]],
      ['Output Sharpening', [
        { path: 'sharpen.on', label: 'Sharpen for', kind: 'check', show: rendered },
        { path: 'sharpen.for', label: 'Medium', kind: 'select', options: [['screen', 'Screen'], ['matte', 'Matte Paper'], ['glossy', 'Glossy Paper']], show: () => rendered() && !!getPath(this.settings, 'sharpen.on') },
        { path: 'sharpen.amount', label: 'Amount', kind: 'select', options: [['low', 'Low'], ['standard', 'Standard'], ['high', 'High']], show: () => rendered() && !!getPath(this.settings, 'sharpen.on') },
      ]],
      ['Metadata', [
        { path: 'metadata.include', label: 'Include', kind: 'select', options: metaOpts },
        { path: 'metadata.removePerson', label: 'Remove person info', kind: 'check' },
        { path: 'metadata.removeLocation', label: 'Remove location info', kind: 'check' },
      ]],
      ['Watermarking', [
        { path: 'watermark.on', label: 'Watermark', kind: 'check', show: rendered },
        { path: 'watermark.kind', label: 'Style', kind: 'seg', options: [['text', 'Text'], ['image', 'Graphic']], show: wm },
        { path: 'watermark.text', label: 'Text', kind: 'text', placeholder: '{copyright}', show: () => wm() && getPath(this.settings, 'watermark.kind') !== 'image' },
        { path: 'watermark.image', label: 'PNG file', kind: 'text', placeholder: '/path/to/logo.png', show: () => wm() && getPath(this.settings, 'watermark.kind') === 'image' },
        { path: 'watermark.size', label: 'Size', kind: 'range', min: 0.01, max: 0.3, step: 0.005, show: wm },
        { path: 'watermark.opacity', label: 'Opacity', kind: 'range', min: 0.05, max: 1, step: 0.05, show: wm },
        { path: 'watermark.anchor', label: 'Anchor', kind: 'select', options: [['tl', 'Top Left'], ['t', 'Top'], ['tr', 'Top Right'], ['l', 'Left'], ['c', 'Center'], ['r', 'Right'], ['bl', 'Bottom Left'], ['b', 'Bottom'], ['br', 'Bottom Right']], show: wm },
        { path: 'watermark.inset', label: 'Inset', kind: 'range', min: 0, max: 0.15, step: 0.005, show: wm },
        { path: 'watermark.color', label: 'Color', kind: 'color', show: () => wm() && getPath(this.settings, 'watermark.kind') !== 'image' },
        { path: 'watermark.shadow', label: 'Shadow', kind: 'check', show: () => wm() && getPath(this.settings, 'watermark.kind') !== 'image' },
      ]],
      ['Video', [
        { path: 'video.include', label: 'Include videos', kind: 'check' },
        { path: 'video.format', label: 'Format', kind: 'select', options: o.ffmpeg ? [['original', 'Original'], ['h264', 'H.264 (MP4)']] : [['original', 'Original']], show: () => !!getPath(this.settings, 'video.include') },
        { path: 'video.quality', label: 'Quality', kind: 'select', options: [['max', 'Maximum'], ['high', 'High'], ['medium', 'Medium, 1080p'], ['low', 'Low, 1080p']], show: () => !!getPath(this.settings, 'video.include') && getPath(this.settings, 'video.format') === 'h264' },
      ]],
      ['Post-Processing', [
        { path: 'post.action', label: 'After export', kind: 'select', options: [['none', 'Do nothing'], ['reveal', 'Show in folder'], ['open', 'Open in application']] },
        { path: 'post.app', label: 'Application', kind: 'text', placeholder: '/Applications/formvis.app', show: () => getPath(this.settings, 'post.action') === 'open' },
      ]],
    ];
  }

  private build(o: Options): void {
    for (const [title, specs] of this.sections(o)) {
      const sec = el('<section class="fl-exp-sec"><div class="fl-sub"></div></section>');
      setText(q(sec, '.fl-sub'), title);
      const f = new Form(specs, (p) => (p === 'file.depth' ? String(getPath(this.settings, p)) : getPath(this.settings, p)), (p, v) => {
        setPath(this.settings, p, p === 'file.depth' ? Number(v) : v);
        if (this.current && !this.current.startsWith('~')) this.current = `~${this.current}`;
        this.syncAll();
      });
      sec.appendChild(f.root);
      this.forms.push(f);
      this.main.appendChild(sec);
    }
  }

  private syncAll(): void {
    for (const f of this.forms) f.sync();
    patchList(this.list, this.presets, {
      key: (p) => p.id,
      create: (p) => el(`<button class="fl-list-row" type="button"><span>${escapeHtml(p.name)}</span>${p.builtin ? '' : '<em>User</em>'}</button>`),
      update: (n, p) => { setText(q(n, 'span'), p.name); setClass(n, 'is-on', this.current === p.id || this.current === `~${p.id}`); },
    });
    const cur = this.presets.find((p) => p.id === this.current.replace(/^~/, ''));
    setDisabled(this.removeBtn, !cur || cur.builtin);
  }

  private apply(id: string): void {
    const p = this.presets.find((x) => x.id === id);
    if (!p || !this.opts) return;
    this.settings = merge(this.opts.defaults, p.settings);
    this.current = id;
    this.syncAll();
  }

  private async savePreset(): Promise<void> {
    const name = await promptName('New Export Preset', 'My Export', 'Save');
    if (!name) return;
    try {
      const r = await this.ctx.api.cmd<{ id: string }>('export.savePreset', { name, settings: this.settings });
      await this.loadPresets();
      this.current = r.id;
      this.syncAll();
    } catch (err) { this.ctx.fail(err); }
  }

  private async removePreset(): Promise<void> {
    const p = this.presets.find((x) => x.id === this.current.replace(/^~/, ''));
    if (!p || p.builtin) return;
    if (!(await confirmAction('Remove Preset', `Remove the export preset "${p.name}"?`, 'Remove', true))) return;
    try { await this.ctx.api.cmd('export.deletePreset', { id: p.id }); this.current = ''; await this.loadPresets(); } catch (err) { this.ctx.fail(err); }
  }

  private async loadPresets(): Promise<void> {
    const r = await this.ctx.api.cmd<{ presets: Preset[] }>('export.presets');
    this.presets = r.presets;
    this.syncAll();
  }

  async show(ids: number[]): Promise<void> {
    this.ids = ids;
    try {
      if (!this.opts) {
        this.opts = await this.ctx.api.cmd<Options>('export.options');
        this.build(this.opts);
      }
      let last: Settings | null = null;
      try { last = JSON.parse(localStorage.getItem(LAST_KEY) || 'null') as Settings | null; } catch { last = null; }
      this.settings = merge(this.opts.defaults, last ?? {});
      await this.loadPresets();
    } catch (err) { this.ctx.fail(err); return; }
    this.setTitle(`Export ${ids.length} ${ids.length === 1 ? 'File' : 'Files'}`);
    this.syncAll();
    this.open(this.runBtn);
  }

  private async run(): Promise<void> {
    const ids = this.ids;
    const settings = clone(this.settings);
    try { localStorage.setItem(LAST_KEY, JSON.stringify(settings)); } catch { toast('Export settings were not remembered'); }
    this.close();
    await exportWith(this.ctx, ids, settings);
  }
}

export function exportWith(ctx: Ctx, ids: number[], settings: Settings | null, preset?: string): Promise<void> {
  return exportCall(ctx, 'export.run', { ids, settings: settings ?? undefined, preset });
}

async function exportCall(ctx: Ctx, cmd: string, params: Record<string, unknown>): Promise<void> {
  try {
    const start = await ctx.api.cmd<{ task: number }>(cmd, params);
    const r = await whenDone(start.task);
    const paths = (r.paths as string[]) ?? [];
    const failed = (r.failed as Array<{ error: string }>) ?? [];
    if (failed.length) toast(`${failed.length} could not be exported: ${failed[0].error}`, 'error');
    if (!paths.length) { if (!failed.length) toast('Nothing was exported'); return; }
    actionToast(`Exported ${paths.length} ${paths.length === 1 ? 'file' : 'files'}`, [
      ['Open', () => openOutput(paths[0])],
      ['Show in Folder', () => void ctx.api.cmd('output.reveal', { path: paths[0] }).catch((e) => ctx.fail(e))],
    ]);
  } catch (err) { ctx.fail(err); }
}

let dialog: ExportDialog | null = null;

export function registerExport(ctx: Ctx): void {
  const targets = () => library.targets();
  ctx.commands.add(
    { id: 'library.export', label: 'Export...', keys: ['Shift+Mod+E'], run: () => { const ids = targets(); if (!ids.length) { toast('Select photos to export'); return; } dialog ??= new ExportDialog(ctx); void dialog.show(ids); }, enabled: () => library.ids.length > 0 },
    { id: 'library.exportPrevious', label: 'Export with Previous', keys: ['Alt+Shift+Mod+E'], run: () => void exportCall(ctx, 'export.previous', { ids: targets() }), enabled: () => library.ids.length > 0 },
  );
}
