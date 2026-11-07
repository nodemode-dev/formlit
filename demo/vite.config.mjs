import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const front = resolve(here, '../frontend');
const shims = {
  'src/io/api': 'shims/api',
  'src/state/catalog': 'shims/catalog',
  'src/state/library': 'shims/library',
  'src/state/develop': 'shims/develop',
};

const swapBackend = {
  name: 'formlit-demo-shims',
  enforce: 'pre',
  async resolveId(source, importer, options) {
    if (!importer || !source.startsWith('.') || !importer.startsWith(`${front}/src/`)) return null;
    const hit = await this.resolve(source, importer, { ...options, skipSelf: true });
    if (!hit) return null;
    const rel = hit.id.slice(front.length + 1).replace(/\.ts$/, '');
    return shims[rel] ? resolve(here, 'src', `${shims[rel]}.ts`) : null;
  },
};

const fileSafe = {
  name: 'formlit-demo-file-safe',
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
  name: 'formlit-demo-theme-boot',
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
  server: { port: 5395, host: false, strictPort: true, fs: { allow: ['..'] } },
  preview: { port: 5396, host: false, strictPort: true },
  build: {
    outDir: here,
    emptyOutDir: false,
    target: 'es2020',
    sourcemap: false,
    cssCodeSplit: false,
    assetsInlineLimit: 400000,
    modulePreload: false,
    chunkSizeWarningLimit: 2000,
    rollupOptions: { output: { format: 'iife', inlineDynamicImports: true, entryFileNames: 'assets/formlit-demo.js', assetFileNames: 'assets/formlit-demo[extname]' } },
  },
};
