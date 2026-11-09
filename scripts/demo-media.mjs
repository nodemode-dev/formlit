#!/usr/bin/env node
// Copies the three browser demos' media into the app build and writes each demo's demo.json, so Help > Demos and the
// empty library's Demos cards open them inside the app (engine command demo.open). Run from anywhere:
//   node scripts/demo-media.mjs
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const front = join(root, 'frontend');
const out = join(front, 'public', 'demos');
const { rolldown } = await import(pathToFileURL(createRequire(join(front, 'package.json')).resolve('rolldown')).href);

function unpack(file) {
  const text = readFileSync(join(root, file), 'utf8');
  const found = new Map();
  for (const m of text.matchAll(/"([^"]+)":\s*"data:[^;]+;base64,([A-Za-z0-9+/=]+)"/g)) found.set(m[1], Buffer.from(m[2], 'base64'));
  if (!found.size) throw new Error(`${file}: no data in the pack`);
  return found;
}
const packs = (dir, names) => new Map(names.flatMap((n) => [...unpack(`${dir}/${n}.js`)]));
const sha = (b) => createHash('sha256').update(b).digest('hex');

const tmp = join(tmpdir(), `formlit-demo-specs-${process.pid}.mjs`);
const bundle = await rolldown({ input: join(front, 'src', 'demos', 'specs.ts'), platform: 'node' });
await bundle.write({ file: tmp, format: 'esm' });
const { SPECS } = await import(pathToFileURL(tmp).href);
rmSync(tmp, { force: true });

const media = {
  library: packs('demo/assets/media', ['lakes', 'coast', 'city', 'autumn']),
  develop: packs('demos/develop/assets/media', ['develop']),
  share: packs('demos/share/assets/media', ['alps', 'world', 'more']),
};
const bitmaps = unpack('demos/develop/assets/media/masks.js');
const music = unpack('demos/share/assets/media/music.js');

rmSync(out, { recursive: true, force: true });
let bytes = 0;
const put = (rel, data) => { const p = join(out, rel); mkdirSync(dirname(p), { recursive: true }); writeFileSync(p, data); bytes += data.length; };
const library = new Map([...media.library].map(([n, b]) => [sha(b), n]));
for (const spec of SPECS) {
  const files = {};
  for (const p of spec.photos) {
    const data = media[spec.id].get(p.file);
    if (!data) throw new Error(`${spec.id}: ${p.file} is not in the demo's packs`);
    const same = spec.id !== 'library' ? library.get(sha(data)) : undefined;
    if (same) files[p.file] = `library/${same}`;
    else { put(`${spec.id}/${p.file}`, data); files[p.file] = `${spec.id}/${p.file}`; }
  }
  const extra = {};
  if (spec.bitmaps) {
    extra.bitmaps = {};
    for (const key of spec.bitmaps) {
      const data = bitmaps.get(key);
      if (!data) throw new Error(`develop: no selection bitmap ${key}`);
      put(`${spec.id}/masks/${key}.png`, data);
      extra.bitmaps[key] = `${spec.id}/masks/${key}.png`;
    }
  }
  if (spec.music) { put(`${spec.id}/${spec.music}`, music.get(spec.music)); extra.music = `${spec.id}/${spec.music}`; }
  writeFileSync(join(out, spec.id, 'demo.json'), JSON.stringify({ ...spec, bitmaps: undefined, music: undefined, files, ...extra }));
}
console.log(`frontend/public/demos: ${(bytes / 1048576).toFixed(1)} MB of media for ${SPECS.length} demos`);
