import './ui/icons-lit';
import './modules';
import { App } from './app';
import { mountSecondWindow } from './second';
import { initLanguage } from './i18n';

const host = document.getElementById('app');
void initLanguage().catch(() => undefined).then(() => {
  if (host && new URLSearchParams(window.location.search).has('second')) {
    mountSecondWindow(host);
  } else if (host) {
    const app = new App(host);
    app.start();
  }
});
