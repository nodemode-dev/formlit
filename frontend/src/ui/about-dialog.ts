import { Dialog } from './dialogs';
import { el, q, setText } from './dom';
import { t } from '../i18n';
import { VERSION } from '../version';

export const DNG_NOTICE = 'This product includes DNG technology under license by Adobe Systems Incorporated.';

export class AboutDialog extends Dialog {
  constructor() {
    super(t('About formlit'), 420);
    const intro = el('<div class="fl-about"><p class="fl-about-name"></p><p class="fl-about-line"></p><p class="fl-about-line fl-about-by" translate="no">Copyright 2026 NodeAgentc, Inc.</p><p class="fl-about-line"><a class="fl-about-licence" href="https://github.com/nodemode-dev/formlit/blob/main/LICENSE" target="_blank" rel="noopener" translate="no">Apache License 2.0</a></p><details class="fl-about-notices"><summary></summary><p class="fl-about-notice"></p></details></div>');
    setText(q(intro, '.fl-about-name'), `formlit ${VERSION}`);
    setText(q(intro, '.fl-about-line'), t('Photo library and raw developer in the form family. Apache-2.0.'));
    setText(q(intro, 'summary'), t('Licences and notices'));
    setText(q(intro, '.fl-about-notice'), DNG_NOTICE);
    this.body.appendChild(intro);
    this.button(t('Close'), 'primary', () => this.close());
  }
}

let about: AboutDialog | null = null;

export function openAbout(): void {
  about ??= new AboutDialog();
  about.open();
}
