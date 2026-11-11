import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const front = resolve(here, '../../frontend').replace(/\\/g, '/');
const shims = {
  'src/io/api': 'shims/api',
  'src/io/events': 'shims/events',
  'src/modules/shared/tasks': 'shims/tasks',
  'src/modules/shared/captions': 'shims/captions',
  'src/ui/folder-picker': 'shims/folderpicker',
};

const swapBackend = {
  name: 'formlit-share-shims',
  enforce: 'pre',
  async resolveId(source, importer, options) {
    if (!importer || !source.startsWith('.') || !importer.startsWith(`${front}/src/`)) return null;
    const hit = await this.resolve(source, importer, { ...options, skipSelf: true });
    if (!hit) return null;
    const rel = hit.id.slice(front.length + 1).replace(/\.ts$/, '');
    return shims[rel] ? resolve(here, 'src', `${shims[rel]}.ts`) : null;
  },
};

const offlineTiles = {
  name: 'formlit-share-offline-tiles',
  enforce: 'pre',
  transform(code, id) {
    if (!id.endsWith('/frontend/src/modules/output/map.ts')) return null;
    const from = code.indexOf('const OSM =');
    const to = code.indexOf('const VIEW_KEY');
    if (from < 0 || to < from) throw new Error('formlit-share: the tile table in map.ts moved; update the offline tile plugin');
    const table = 'const STYLES: Record<string, { label: string; url: (z: number, x: number, y: number) => string; attr: string; max: number; overlay?: (z: number, x: number, y: number) => string; cls?: string }> = OFFLINE_STYLES;\n';
    const head = `import { OFFLINE_STYLES } from ${JSON.stringify(resolve(here, 'src/map-styles.ts'))};\n`;
    return { code: head + code.slice(0, from) + table + code.slice(to), map: null };
  },
};

const fileSafe = {
  name: 'formlit-share-file-safe',
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
  name: 'formlit-share-theme-boot',
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
  plugins: [swapBackend, offlineTiles, themeBoot, fileSafe],
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
    chunkSizeWarningLimit: 4000,
    rollupOptions: { output: { format: 'iife', inlineDynamicImports: true, entryFileNames: 'assets/formlit-share.js', assetFileNames: 'assets/formlit-share[extname]' } },
  },
};
