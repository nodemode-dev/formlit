import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const front = resolve(here, '../../frontend').replace(/\\/g, '/');
const demo = resolve(here, '../../demo/src').replace(/\\/g, '/');
const shims = {
  'src/io/api': 'shims/api',
  'src/state/catalog': 'shims/catalog',
  'src/state/library': 'shims/library',
  'src/state/develop': 'shims/develop',
};

const swapBackend = {
  name: 'formlit-develop-shims',
  enforce: 'pre',
  async resolveId(source, importer, options) {
    if (!importer || !source.startsWith('.')) return null;
    const hit = await this.resolve(source, importer, { ...options, skipSelf: true });
    if (!hit) return null;
    if (importer.startsWith(`${front}/src/`)) {
      const rel = hit.id.slice(front.length + 1).replace(/\.ts$/, '');
      return shims[rel] ? resolve(demo, `${shims[rel]}.ts`) : null;
    }
    if (importer.startsWith(`${demo}/`) && hit.id === `${demo}/engine/render.ts`) return resolve(here, 'src/render-masks.ts');
    return null;
  },
};

const fileSafe = {
  name: 'formlit-develop-file-safe',
  transformIndexHtml: {
    order: 'post',
    handler(html) {
      const scripts = [];
      let out = html.replace(/<script type="module"[^>]*src="([^"]+)"[^>]*><\/script>\s*/g, (_m, src) => {
        scripts.push(src);
        return '';
      });
      out = out.replace(/ crossorigin(="[^"]*")?/g, '');
      const tags = scripts.map((s) => `<script src="${s}"></script>`).join('\n');
      return out.replace('</body>', `${tags}\n</body>`);
    },
  },
};

const themeBoot = {
  name: 'formlit-develop-theme-boot',
  transformIndexHtml: {
    order: 'pre',
    handler(html) {
      const src = readFileSync(resolve(front, 'index.html'), 'utf8');
      const m = /<script>([\s\S]*?)<\/script>/.exec(src);
      return html.replace('<!--theme-boot-->', m ? `<script>${m[1]}</script>` : '');
    },
  },
};

export default {
  root: resolve(here, 'site'),
  base: './',
  publicDir: false,
  plugins: [swapBackend, themeBoot, fileSafe],
  server: { port: 5397, host: false, strictPort: true, fs: { allow: ['../..'] } },
  preview: { port: 5398, host: false, strictPort: true },
  build: {
    outDir: here,
    emptyOutDir: false,
    target: 'es2020',
    sourcemap: false,
    cssCodeSplit: false,
    assetsInlineLimit: 400000,
    modulePreload: false,
    chunkSizeWarningLimit: 2000,
    rollupOptions: { output: { format: 'iife', inlineDynamicImports: true, entryFileNames: 'assets/formlit-develop.js', assetFileNames: 'assets/formlit-develop[extname]' } },
  },
};
