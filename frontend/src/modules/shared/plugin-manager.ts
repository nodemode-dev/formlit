import type { Ctx } from '../../app';
import { Dialog } from '../../ui/dialogs';
import { el, escapeHtml, patchList, q, setHidden, setHtml, setText } from '../../ui/dom';
import { toast } from '../../ui/toast';

interface PluginRow { kind: string; label: string; version: string; author: string; url: string; description: string; comments: boolean; builtin: boolean; file: string }
interface PluginError { file: string; error: string }
interface PluginInfo { plugins: PluginRow[]; errors: PluginError[]; folder: string; api: number }

class PluginManager extends Dialog {
  private readonly list = el('<div class="fl-plug-list"></div>');
  private readonly errors = el('<div class="fl-plug-errors" hidden></div>');
  private readonly where = el('<p class="cv-note fl-plug-folder"></p>');

  constructor(private readonly ctx: Ctx) {
    super('Plug-in Manager', 560);
    this.body.append(el('<p class="cv-note">Publish plug-ins add services to the Publish Services panel. Put a plug-in (a .py file, or a folder with __init__.py) in the Plugins folder, then press Reload. The API is described in docs/plugins and the wiki.</p>'), this.list, this.errors, this.where);
    this.button('Extensions Panel', 'ghost', () => { this.close(); this.ctx.run('ext.panel'); });
    this.button('Show Plugins Folder', 'ghost', () => void this.reveal());
    this.button('Reload Plug-ins', '', () => void this.load(true));
    this.button('Done', 'primary', () => this.close());
  }

  async show(): Promise<void> {
    this.open();
    await this.load(false);
  }

  private async reveal(): Promise<void> {
    const folder = this.where.dataset.folder;
    if (folder) try { await this.ctx.api.cmd('output.reveal', { path: folder }); } catch (err) { this.ctx.fail(err); }
  }

  private async load(reload: boolean): Promise<void> {
    try {
      const r = await this.ctx.api.cmd<PluginInfo>(reload ? 'publish.reloadPlugins' : 'publish.plugins');
      this.paint(r);
      if (reload) toast(`${r.plugins.length} plug-ins loaded${r.errors.length ? `, ${r.errors.length} failed` : ''}`, r.errors.length ? 'error' : 'info');
    } catch (err) { this.ctx.fail(err); }
  }

  private paint(r: PluginInfo): void {
    const update = (n: HTMLElement, p: PluginRow) => {
      setText(q(n, '.fl-plug-name'), p.label);
      setText(q(n, '.fl-plug-badge'), p.builtin ? 'Built in' : 'Installed');
      setText(q(n, '.fl-plug-desc'), p.description);
      setText(q(n, '.fl-plug-meta'), [p.version && `v${p.version}`, p.author, p.comments ? 'Comments' : '', `kind ${p.kind}`, p.file].filter(Boolean).join(' · '));
    };
    patchList(this.list, r.plugins, {
      key: (p) => p.kind,
      create: (p) => { const n = el('<div class="fl-plug"><div class="fl-plug-head"><span class="fl-plug-name"></span><em class="fl-plug-badge"></em></div><div class="fl-plug-desc"></div><div class="fl-plug-meta"></div></div>'); update(n, p); return n; },
      update,
    });
    setHidden(this.errors, r.errors.length === 0);
    const html = r.errors.map((e) => `<div class="fl-plug-error"><b>${escapeHtml(e.file.split(/[\\/]/).pop() ?? e.file)}</b> ${escapeHtml(e.error)}</div>`).join('');
    setHtml(this.errors, html, html);
    this.where.dataset.folder = r.folder;
    setText(this.where, `Plugins folder: ${r.folder} · plug-in API ${r.api}`);
  }
}

let dialog: PluginManager | null = null;

export function registerPluginManager(ctx: Ctx): void {
  ctx.commands.add({
    id: 'app.pluginManager', label: 'Plug-in Manager...', keys: ['Alt+Shift+Mod+,'],
    run: () => { dialog ??= new PluginManager(ctx); void dialog.show(); },
  });
}
