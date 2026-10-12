import { defineConfig } from 'vite';

const FRONTEND_PORT = 5390;
const BACKEND_PORT = 8390;
const engine = { target: `http://127.0.0.1:${BACKEND_PORT}`, changeOrigin: true, ws: true };

const devFontPreloads = {
  name: 'formlit-dev-font-preloads',
  apply: 'serve' as const,
  transformIndexHtml: (html: string) => html.replace(/\s*<link rel="preload" href="[^"]+\.woff2" as="font"[^>]*>/g, ''),
};

export default defineConfig({
  root: '.',
  publicDir: 'public',
  plugins: [devFontPreloads],
  server: {
    fs: { allow: ['..'] },
    port: FRONTEND_PORT,
    host: false,
    strictPort: true,
    proxy: { '/api': engine, '/mcp': engine },
  },
  preview: {
    port: FRONTEND_PORT + 1,
    host: false,
    strictPort: true,
    proxy: { '/api': engine, '/mcp': engine },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    target: 'es2022',
    chunkSizeWarningLimit: 1600,
  },
});
