import { events } from './io/events';
import type { Photo } from './state/library';
import { el, q, revealApp, setClass, setText } from './ui/dom';
import { applyTheme } from './ui/themes';
import { bump } from './ui/thumbs';
import { Viewer } from './ui/viewer';

export const SECOND_CHANNEL = 'formlit-second';

export function mountSecondWindow(host: HTMLElement): void {
  applyTheme();
  document.title = 'formlit · Second Window';
  const root = el(`<div class="fl-second"><div class="fl-second-bar"><span class="fl-second-name"></span><span class="fl-tb-spacer"></span><div class="cv-seg fl-seg-sm" role="radiogroup"><button type="button" data-m="follow" class="is-on">Follow</button><button type="button" data-m="locked">Locked</button></div></div></div>`);
  const viewer = new Viewer('fl-second-view');
  root.appendChild(viewer.root);
  host.appendChild(root);
  let mode: 'follow' | 'locked' = 'follow';
  const ch = new BroadcastChannel(SECOND_CHANNEL);
  const show = (p: Photo | null) => {
    if (mode === 'locked' && viewer.photo) return;
    setText(q(root, '.fl-second-name'), p ? p.file : 'Select a photo in the main window');
    void viewer.show(p);
  };
  ch.onmessage = (e: MessageEvent) => { const d = e.data as { photo?: Photo | null }; if ('photo' in d) show(d.photo ?? null); };
  q(root, '.cv-seg').addEventListener('click', (e) => {
    const b = (e.target as HTMLElement).closest<HTMLElement>('[data-m]');
    if (!b) return;
    mode = b.dataset.m as 'follow' | 'locked';
    for (const x of Array.from(root.querySelectorAll<HTMLElement>('[data-m]'))) setClass(x, 'is-on', x === b);
    if (mode === 'follow') ch.postMessage({ hello: true });
  });
  events.on('render', (e) => {
    if (e.size === 'p' && viewer.photo && Number(e.id) === viewer.photo.id) { bump(viewer.photo.id, 'p'); viewer.refresh(); }
  });
  events.start();
  ch.postMessage({ hello: true });
  void document.fonts.ready.then(() => revealApp());
}
