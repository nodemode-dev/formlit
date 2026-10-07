import type { Ctx } from '../app';
import { Dialog } from './dialogs';
import { el, escapeHtml, q, setHtml, setText } from './dom';
import { readChoice, setAccent, setIntensity, setTheme, themeSwatchesHtml, THEMES } from './themes';

interface Caps { version: string; platform: string; desktop: boolean; raw: boolean; heic: boolean; onnx: boolean; pdf: boolean; ffmpeg: boolean; workers: number; dataDir: string; catalog: string }

class Preferences extends Dialog {
  private readonly swatches = el('<div class="nm-theme-grid"></div>');
  private readonly accent = el<HTMLInputElement>('<input class="cv-color-input" type="color">');
  private readonly intensity = el<HTMLInputElement>('<input class="cv-slider" type="range" min="0" max="1.5" step="0.05">');
  private readonly themeName = el('<span class="fl-muted"></span>');
  private readonly engine = el('<div class="fl-prefs-engine"></div>');
  private readonly agents = el('<pre class="fl-code"></pre>');

  constructor(private readonly ctx: Ctx) {
    super('Preferences', 620);
    this.body.appendChild(el('<div class="fl-sub">Appearance</div>'));
    const themeRow = el('<div class="fl-prefs-theme"></div>');
    themeRow.append(this.swatches, this.themeName);
    this.field('Theme', themeRow);
    this.field('Accent', this.accent);
    this.field('Accent strength', this.intensity);
    this.body.appendChild(el('<div class="fl-sub">Engine</div>'));
    this.body.appendChild(this.engine);
    this.body.appendChild(el('<div class="fl-sub">Agents (MCP)</div>'));
    this.body.appendChild(el('<p class="cv-note">Agents drive formlit through the same commands as this window. Point an MCP client at the endpoint below, or run <code>./formlit agents install</code> to register it with Claude Code, Codex and Cursor.</p>'));
    this.body.appendChild(this.agents);
    this.button('Done', 'primary', () => this.close());
    this.swatches.addEventListener('click', (e) => {
      const b = (e.target as HTMLElement).closest<HTMLElement>('[data-theme-id]');
      if (b) { setTheme(b.dataset.themeId as string); this.sync(); }
    });
    this.accent.addEventListener('input', () => { setAccent(this.accent.value); this.sync(); });
    this.intensity.addEventListener('input', () => setIntensity(Number(this.intensity.value)));
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
    this.open();
    try {
      const caps = await this.ctx.api.get<Caps>('/api/capabilities');
      const yes = (b: boolean) => (b ? 'available' : 'not installed');
      this.engine.innerHTML = [
        ['Version', caps.version], ['Catalog', caps.catalog], ['Data folder', caps.dataDir], ['Raw decoding', yes(caps.raw)], ['HEIC', yes(caps.heic)],
        ['AI models runtime', yes(caps.onnx)], ['PDF output', yes(caps.pdf)], ['Video (ffmpeg)', yes(caps.ffmpeg)], ['Render workers', String(caps.workers)],
      ].map(([k, v]) => `<div class="fl-meta-row"><span class="fl-meta-key">${k}</span><span class="fl-meta-val">${escapeHtml(String(v))}</span></div>`).join('');
      const origin = window.location.origin.startsWith('http') ? window.location.origin : 'http://127.0.0.1:8390';
      setText(this.agents, JSON.stringify({ mcpServers: { formlit: { type: 'http', url: `${this.ctx.api.base || origin}/mcp` } } }, null, 2));
    } catch { setText(q(this.body, '.fl-prefs-engine'), 'The engine is not reachable.'); }
  }
}

let dialog: Preferences | null = null;

export function openPreferences(ctx: Ctx): void {
  dialog ??= new Preferences(ctx);
  void dialog.show();
}
