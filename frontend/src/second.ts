import { events } from './io/events';
import { SECOND_MODES, SecondModes, type LoupeMode, type SecondMode, type SecondMsg } from './second-modes';
import { el, q, revealApp, setClass, setHidden, setText } from './ui/dom';
import { applyTheme } from './ui/themes';
import { bump } from './ui/thumbs';

export const SECOND_CHANNEL = 'formlit-second';

export function mountSecondWindow(host: HTMLElement): void {
  applyTheme();
  document.title = 'formlit · Second Window';
  const segs = SECOND_MODES.map(([m, l]) => `<button type="button" data-mode="${m}"${m === 'loupe' ? ' class="is-on"' : ''}>${l}</button>`).join('');
  const root = el(`<div class="fl-second"><div class="fl-second-bar"><div class="cv-seg fl-seg-sm" role="radiogroup" aria-label="View">${segs}</div><div class="cv-seg fl-seg-sm" role="radiogroup" aria-label="Loupe" data-g="loupe"><button type="button" data-m="normal" class="is-on">Normal</button><button type="button" data-m="live">Live</button><button type="button" data-m="locked">Locked</button></div><input class="cv-slider fl-second-size" type="range" min="80" max="320" step="8" value="160" aria-label="Thumbnail size" hidden><span class="fl-second-name"></span><span class="fl-tb-spacer"></span></div></div>`);
  const ch = new BroadcastChannel(SECOND_CHANNEL);
  const modes = new SecondModes(ch);
  root.appendChild(modes.stage);
  host.appendChild(root);
  const name = q(root, '.fl-second-name');
  const loupeSeg = q(root, '[data-g="loupe"]');
  const size = q<HTMLInputElement>(root, '.fl-second-size');
  modes.onShown = (p, m) => {
    setText(name, p ? p.file : m === 'grid' ? '' : 'Select a photo in the main window');
    setHidden(loupeSeg, m !== 'loupe');
    setHidden(size, m !== 'grid');
    for (const b of Array.from(root.querySelectorAll<HTMLElement>('[data-mode]'))) setClass(b, 'is-on', b.dataset.mode === m);
  };
  ch.onmessage = (e: MessageEvent) => modes.receive(e.data as SecondMsg);
  root.addEventListener('click', (e) => {
    const b = (e.target as HTMLElement).closest<HTMLElement>('[data-mode], [data-m]');
    if (!b) return;
    if (b.dataset.mode) { modes.setMode(b.dataset.mode as SecondMode); return; }
    modes.setLoupe(b.dataset.m as LoupeMode);
    for (const x of Array.from(loupeSeg.querySelectorAll<HTMLElement>('[data-m]'))) setClass(x, 'is-on', x === b);
  });
  size.addEventListener('input', () => modes.setSize(Number(size.value)));
  const want = new URLSearchParams(window.location.search).get('mode') as SecondMode | null;
  if (want && SECOND_MODES.some(([m]) => m === want)) modes.setMode(want);
  events.on('render', (e) => { if (e.size === 'p') { bump(Number(e.id), 'p'); modes.refresh(Number(e.id)); } });
  events.start();
  ch.postMessage({ hello: true });
  void document.fonts.ready.then(() => revealApp());
}
