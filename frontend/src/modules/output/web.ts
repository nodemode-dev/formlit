import { el, setClass } from '../../ui/dom';
import { toast } from '../../ui/toast';
import { registerModule } from '../registry';
import { runOutput } from '../shared/tasks';
import { OutputModule } from './base';

class WebModule extends OutputModule {
  readonly id = 'web';
  readonly label = 'Web';
  readonly icon = 'modWeb';
  readonly key = 'Alt+Mod+7';
  readonly order = 7;
  protected readonly optionsCmd = 'web.options';
  protected readonly kind = 'web';
  private readonly frames = [el<HTMLIFrameElement>('<iframe class="fl-web-frame is-front" title="Web gallery preview" sandbox="allow-scripts"></iframe>'), el<HTMLIFrameElement>('<iframe class="fl-web-frame" title="Web gallery preview" sandbox="allow-scripts"></iframe>')];
  private front = 0;
  private seq = 0;
  private lastHtml = '';
  private readonly device = el('<div class="cv-seg fl-seg-sm"><button type="button" data-d="desktop" class="is-on">Desktop</button><button type="button" data-d="tablet">Tablet</button><button type="button" data-d="phone">Phone</button></div>');
  private readonly box = el('<div class="fl-web-box"></div>');

  protected buildToolbar(bar: HTMLElement): void {
    this.device.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-d]');
      if (!b) return;
      for (const x of Array.from(this.device.querySelectorAll<HTMLElement>('[data-d]'))) setClass(x, 'is-on', x === b);
      this.box.dataset.device = b.dataset.d;
    });
    bar.appendChild(this.device);
  }

  protected buildStage(stage: HTMLElement): void {
    const root = el('<div class="fl-out-stage fl-web-stage"></div>');
    this.box.dataset.device = 'desktop';
    this.box.append(...this.frames);
    root.appendChild(this.box);
    stage.appendChild(root);
  }

  protected buildPanels(right: HTMLElement): void {
    this.formPanel(right, 'site', 'Site Info', [
      { path: 'site.title', label: 'Site title', kind: 'text' },
      { path: 'site.collection', label: 'Collection title', kind: 'text' },
      { path: 'site.description', label: 'Description', kind: 'textarea' },
      { path: 'site.contact', label: 'Contact info', kind: 'text' },
      { path: 'site.link', label: 'Web or mail link', kind: 'text', placeholder: 'https:// or name@example.com' },
    ]);
    this.formPanel(right, 'colors', 'Color Palette', [
      { path: 'colors.background', label: 'Background', kind: 'color' },
      { path: 'colors.text', label: 'Text', kind: 'color' },
      { path: 'colors.muted', label: 'Detail text', kind: 'color' },
      { path: 'colors.cell', label: 'Cells', kind: 'color' },
      { path: 'colors.accent', label: 'Links', kind: 'color' },
    ]);
    this.formPanel(right, 'appearance', 'Appearance', [
      { path: 'layout', label: 'Layout', kind: 'select', options: [['grid', 'Grid'], ['square', 'Square Grid'], ['justified', 'Justified Track'], ['column', 'Single Column']] },
      { path: 'thumbSize', label: 'Thumbnail size', kind: 'range', min: 160, max: 1600, step: 20, unit: ' px' },
      { path: 'rowHeight', label: 'Row height', kind: 'range', min: 120, max: 520, step: 10, unit: ' px', show: () => this.get('layout') === 'justified' },
      { path: 'gap', label: 'Spacing', kind: 'range', min: 0, max: 64, unit: ' px' },
    ]);
    this.formPanel(right, 'info', 'Image Info', [
      { path: 'captions.field', label: 'Grid caption', kind: 'select', options: [['', 'None'], ['title', 'Title'], ['caption', 'Caption'], ['fileName', 'Filename'], ['date', 'Date']] },
      { path: 'captions.lightbox', label: 'Lightbox caption', kind: 'select', options: [['', 'None'], ['titleCaption', 'Title and Caption'], ['title', 'Title'], ['caption', 'Caption'], ['fileName', 'Filename']] },
      { path: 'captions.exposure', label: 'Show exposure', kind: 'check' },
    ]);
    this.formPanel(right, 'output', 'Output Settings', [
      { path: 'largeSize', label: 'Large images', kind: 'range', min: 640, max: 4096, step: 64, unit: ' px' },
      { path: 'quality', label: 'JPEG quality', kind: 'range', min: 40, max: 100 },
      { path: 'metadata', label: 'Metadata', kind: 'select', options: [['copyright', 'Copyright Only'], ['contact', 'Copyright and Contact'], ['noCamera', 'All Except Camera Info'], ['all', 'All Metadata'], ['none', 'None']] },
      { path: 'sharpen', label: 'Sharpening', kind: 'check' },
      { path: 'watermark.on', label: 'Watermark', kind: 'check' },
      { path: 'watermark.text', label: 'Text', kind: 'text', placeholder: '{copyright}', show: () => !!this.get('watermark.on') },
      { path: 'watermark.opacity', label: 'Opacity', kind: 'range', min: 0.1, max: 1, step: 0.05, show: () => !!this.get('watermark.on') },
    ]);
    this.formPanel(right, 'upload', 'Upload Settings', [
      { path: 'upload.host', label: 'FTP server', kind: 'text', placeholder: 'ftp.example.com' },
      { path: 'upload.port', label: 'Port', kind: 'number', min: 1, max: 65535 },
      { path: 'upload.user', label: 'Username', kind: 'text' },
      { path: 'upload.password', label: 'Password', kind: 'password' },
      { path: 'upload.path', label: 'Server path', kind: 'text', placeholder: '/public_html/gallery' },
      { path: 'upload.tls', label: 'Use FTPS (TLS)', kind: 'check' },
    ], false);
  }

  protected persist(): void {
    const up = (this.settings.upload ?? {}) as Record<string, unknown>;
    const safe = { ...this.settings, upload: { ...up, password: '' } };
    try { localStorage.setItem(`formlit_${this.id}_settings`, JSON.stringify(safe)); } catch { return; }
  }

  protected buildFoots(left: HTMLElement, right: HTMLElement): void {
    const l = el('<div class="fl-foot-row"><button class="cv-btn" type="button" data-x="browser">Preview in Browser</button></div>');
    l.addEventListener('click', () => this.openInBrowser());
    left.appendChild(l);
    const r = el('<div class="fl-foot-row"><button class="cv-btn" type="button" data-x="export">Export...</button><button class="cv-btn cv-btn-primary" type="button" data-x="upload">Upload</button></div>');
    r.addEventListener('click', (e) => { const b = (e.target as HTMLElement).closest<HTMLElement>('[data-x]'); if (b) void this.exportSite(b.dataset.x === 'upload'); });
    right.appendChild(r);
  }

  protected async refresh(): Promise<void> {
    const seq = ++this.seq;
    const base = this.ctx.api.base || window.location.origin;
    const r = await this.ctx.api.cmd<{ html: string }>('web.preview', { ids: this.ids(), settings: this.settings, base });
    if (seq !== this.seq || r.html === this.lastHtml) return;
    this.lastHtml = r.html;
    const back = this.frames[1 - this.front];
    back.onload = () => {
      if (seq !== this.seq) return;
      setClass(back, 'is-front', true);
      setClass(this.frames[this.front], 'is-front', false);
      this.front = 1 - this.front;
    };
    back.srcdoc = r.html;
    const n = this.ids().length;
    this.status.textContent = `${n} ${n === 1 ? 'photo' : 'photos'}`;
  }

  private openInBrowser(): void {
    if (!this.lastHtml) return;
    const url = URL.createObjectURL(new Blob([this.lastHtml], { type: 'text/html' }));
    window.open(url, '_blank', 'noopener');
    window.setTimeout(() => URL.revokeObjectURL(url), 60000);
  }

  private async exportSite(upload: boolean): Promise<void> {
    const ids = this.ids();
    if (!ids.length) { toast('Add photos to the filmstrip first'); return; }
    if (upload && !this.get('upload.host')) { toast('Fill in Upload Settings first', 'error'); return; }
    const name = String(this.get('site.collection') || this.get('site.title') || 'Web Gallery');
    await runOutput(this.ctx, 'web.export', { ids, settings: this.settings, name, upload }, (r) => upload ? `Uploaded ${String(r.uploaded ?? '')} files` : `Exported a gallery of ${String(r.photos ?? ids.length)} photos`);
  }
}

registerModule(new WebModule());
