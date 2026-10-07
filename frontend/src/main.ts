import './ui/icons-lit';
import './modules';
import { App } from './app';

const host = document.getElementById('app');
if (host) {
  const app = new App(host);
  app.start();
}
