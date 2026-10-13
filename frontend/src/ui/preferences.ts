import type { Ctx } from '../app';
import { Dialog } from './dialogs';
import { el, escapeHtml, q, setHtml, setText, setTitle, setValue } from './dom';
import { readChoice, setAccent, setIntensity, setTheme, themeSwatchesHtml, THEMES } from './themes';
import { events } from '../io/events';

interface Caps { version: string; platform: string; desktop: boolean; raw: boolean; heic: boolean; onnx: boolean; pdf: boolean; ffmpeg: boolean; workers: number; dataDir: string; catalog: string }

class Preferences extends Dialog {
  private readonly swatches = el('<div class="nm-theme-grid"></div>');
  private readonly accent = el<HTMLInputElement>('<input class="fl-color" type="color">');
  private readonly intensity = el<HTMLInputElement>('<input class="cv-slider" type="range" min="0" max="1.5" step="0.05">');
  private readonly themeName = el('<span class="fl-muted"></span>');
  private readonly engine = el('<div class="fl-prefs-engine"></div>');
  private readonly agents = el('<pre class="fl-code"></pre>');
  private readonly access = el<HTMLSelectElement>('<select class="cv-select"><option value="ask">Ask me</option><option value="allowed">Allowed</option><option value="blocked">Blocked</option></select>');
  private readonly seen = el('<div class="fl-meta-row"><span class="fl-meta-key">Seen</span><span class="fl-meta-val fl-agents-seen">none yet</span></div>');
  private readonly models = el('<div class="fl-models"></div>');
  private readonly autoXmp = el('<label class="fl-check"><input type="checkbox"> Automatically write changes into XMP</label>');
  private readonly intoFiles = el('<label class="fl-check"><input type="checkbox"> Write metadata into JPEG, TIFF and DNG files instead of sidecars</label>');
  private readonly identity: Record<'creator' | 'email' | 'url', HTMLInputElement> = {
    creator: el<HTMLInputElement>('<input class="cv-input" type="text" spellcheck="false" placeholder="your name or studio">'),
    email: el<HTMLInputElement>('<input class="cv-input" type="email" spellcheck="false" placeholder="optional">'),
    url: el<HTMLInputElement>('<input class="cv-input" type="url" spellcheck="false" placeholder="optional">'),
  };

  constructor(private readonly ctx: Ctx) {
    super('Preferences', 620);
    this.body.appendChild(el('<div class="fl-sub">Appearance</div>'));
    const themeRow = el('<div class="fl-prefs-theme"></div>');
    themeRow.append(this.swatches, this.themeName);
    this.field('Theme', themeRow);
    this.field('Accent', this.accent);
    this.field('Accent strength', this.intensity);
    this.body.appendChild(el('<div class="fl-sub">Metadata</div>'));
    this.body.append(this.autoXmp, this.intoFiles);
    for (const [box, key] of [[this.autoXmp, 'autoWriteXmp'], [this.intoFiles, 'xmpIntoFiles']] as Array<[HTMLElement, string]>) {
      q<HTMLInputElement>(box, 'input').addEventListener('change', (e) => void this.ctx.api.cmd('prefs.set', { values: { [key]: (e.target as HTMLInputElement).checked } }).catch((err) => this.ctx.fail(err)));
    }
    this.body.appendChild(el('<p class="cv-note">Your details for metadata templates, New Shoot from Template and agents: they fill {creator}, {email} and {url} in copyright and licence text.</p>'));
    this.field('Creator', this.identity.creator);
    this.field('Email', this.identity.email);
    this.field('Website', this.identity.url);
    for (const input of Object.values(this.identity)) {
      input.addEventListener('change', () => {
        const values = Object.fromEntries(Object.entries(this.identity).map(([k, i]) => [k, i.value.trim()]));
        void this.ctx.api.cmd('prefs.set', { values: { identity: values } }).catch((err) => this.ctx.fail(err));
      });
    }
    this.body.appendChild(el('<div class="fl-sub">AI agents</div>'));
    this.body.appendChild(el('<p class="cv-note">Claude and other AI agents can work in formlit through its plugin: add the formlit plugin from the Form marketplace in Claude (Customize, Plugins), keep formlit open, and ask in plain words. Agents use the same commands as this window and every change can be undone. Deleting files and switching catalogs always stay with you.</p>'));
    this.field('Agent access', this.access);
    this.body.appendChild(this.seen);
    this.body.appendChild(el('<p class="cv-note">For developers: point an MCP client at this endpoint, or run <code>./formlit agents install</code> in the formlit repository to register it with Claude Code, Codex and Cursor.</p>'));
    this.body.appendChild(this.agents);
    this.body.appendChild(el('<div class="fl-sub">Engine</div>'));
    this.body.appendChild(this.engine);
    this.body.appendChild(el('<div class="fl-sub">AI Models</div>'));
    this.body.appendChild(el('<p class="cv-note">Masks, Remove, Super Resolution, depth and faces run on this computer. Each model downloads once, is checked against its published SHA-256, and stays in your formlit folder.</p>'));
    this.body.appendChild(this.models);
    this.models.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-model]');
      if (!b) return;
      void this.ctx.api.cmd('ai.download', { model: b.dataset.model }).then(() => { b.setAttribute('disabled', ''); setText(b, 'Installing...'); }, (err) => this.ctx.fail(err));
    });
    this.button('Done', 'primary', () => this.close());
    this.swatches.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-theme-id]');
      if (b) { setTheme(b.dataset.themeId as string); this.sync(); }
    });
    this.accent.addEventListener('input', () => { setAccent(this.accent.value); this.sync(); });
    this.intensity.addEventListener('input', () => setIntensity(Number(this.intensity.value)));
    this.access.addEventListener('change', () => void this.ctx.api.cmd('prefs.set', { values: { outsideAgents: this.access.value } }).catch((err) => this.ctx.fail(err)));
    events.on('agents.changed', (e) => setValue(this.access, String(e.outsideAgents ?? 'ask')));
  }

  private sync(): void {
    const c = readChoice();
    setHtml(this.swatches, themeSwatchesHtml(c.theme, c.accentColor), `${c.theme}|${c.accentColor}`);
    setText(this.themeName, THEMES[c.theme]?.label ?? c.theme);
    this.accent.value = c.accentColor;
    this.intensity.value = String(c.intensity ?? 1);
  }

  async show(): Promise<void> {
    this.sync();
    const origin = window.location.origin.startsWith('http') ? window.location.origin : 'http://127.0.0.1:8390';
    setText(this.agents, JSON.stringify({ mcpServers: { formlit: { type: 'http', url: `${this.ctx.api.base || origin}/mcp` } } }, null, 2));
    this.open();
    void this.ctx.api.cmd<Record<string, unknown>>('prefs.get').then((p) => {
      q<HTMLInputElement>(this.autoXmp, 'input').checked = !!p.autoWriteXmp;
      q<HTMLInputElement>(this.intoFiles, 'input').checked = p.xmpIntoFiles !== false;
      setValue(this.access, typeof p.outsideAgents === 'string' ? p.outsideAgents : 'ask');
      const id = (p.identity ?? {}) as Record<string, unknown>;
      for (const [k, input] of Object.entries(this.identity)) if (document.activeElement !== input) setValue(input, String(id[k] ?? ''));
    }, () => undefined);
    void this.ctx.api.cmd<{ clients: Array<{ name: string }> }>('agents.status').then((s) => {
      const names = s.clients.map((c) => c.name).join(', ') || 'none yet';
      const val = q(this.seen, '.fl-meta-val');
      setText(val, names);
      setTitle(val, names);
    }, () => undefined);
    try {
      const caps = await this.ctx.api.get<Caps>('/api/capabilities');
      const yes = (b: boolean) => (b ? 'available' : 'not installed');
      this.engine.innerHTML = [
        ['Version', caps.version], ['Catalog', caps.catalog], ['Data folder', caps.dataDir], ['Raw decoding', yes(caps.raw)], ['HEIC', yes(caps.heic)],
        ['AI models runtime', yes(caps.onnx)], ['PDF output', yes(caps.pdf)], ['Video (ffmpeg)', yes(caps.ffmpeg)], ['Render workers', String(caps.workers)],
      ].map(([k, v]) => `<div class="fl-meta-row"><span class="fl-meta-key">${k}</span><span class="fl-meta-val">${escapeHtml(String(v))}</span></div>`).join('');
      const ms = await this.ctx.api.cmd<{ models: Array<{ id: string; name: string; license: string; sizeMB: number; ready: boolean; downloading: boolean }> }>('ai.models');
      this.models.innerHTML = ms.models.map((m) => `<div class="fl-meta-row fl-model-row"><span class="fl-meta-key">${escapeHtml(m.name)}</span><span class="fl-meta-val">${m.sizeMB} MB · ${escapeHtml(m.license)} ${m.ready ? '<em class="fl-ok">Installed</em>' : `<button class="cv-btn fl-btn-sm" type="button" data-model="${m.id}"${m.downloading ? ' disabled' : ''}>${m.downloading ? 'Installing...' : 'Install'}</button>`}</span></div>`).join('');
    } catch { setText(q(this.body, '.fl-prefs-engine'), 'The engine is not reachable.'); }
  }
}

let dialog: Preferences | null = null;

export function openPreferences(ctx: Ctx): void {
  dialog ??= new Preferences(ctx);
  void dialog.show();
}
