# formlit demo

The formlit window running entirely in a browser tab. No engine, no network, no CDN, and no account: open `index.html` straight from disk (`file://`) or serve this folder with any static server. Photos you open never leave the page.

## What it does

- Library: grid, loupe and filmstrip, sorting, search, star ratings, pick and reject flags, colour labels, keywords and a metadata panel with the file's EXIF.
- Develop: the global develop controls (white balance, tone, presence, tone curve, colour mixer, black and white, colour grading, detail, transform, vignette, grain, calibration), 12 presets with an amount slider, history, before and after and split views, a clipping overlay, a white balance picker, crop with aspect and straighten, flips and quarter turns, and Auto Tone.
- Utility operations: export one or many photos as JPEG, PNG or WebP at a chosen size and quality (several photos can be bundled as a ZIP), copy, paste and synchronize settings between photos, save and load a settings file, and view photo information.
- A real library: it opens on 25 photographs from Pexels in four collections (Mountain Lakes, Coastlines, City After Dark, Autumn Woods), with ratings, flags, colour labels, keywords, the camera data and capture dates the photo pages publish, and 18 photos that already carry develop settings with a history, so Before and After shows real work. Sources and licences are in `CREDITS.md`.
- Samples: six procedural scenes can still be added from the left panel, and they stand in for the library if its photo packs fail to load.
- Your files: JPEG, PNG, WebP and other formats the browser decodes. For RAW files the demo reads the embedded JPEG preview; it does not demosaic.

## Run it

```
open demo/index.html
```

or

```
cd demo && python3 -m http.server 5396
```

## How it is built

The develop pipeline is a TypeScript port of the engine's global path (`src/engine/`), driven by the same `shared/controls.json` the desktop app reads. The interface is the app's own: its stylesheets, icons, panels, sliders, histogram, tone curve, colour wheel, thumbnail grid, filmstrip, viewer, menus and dialogs are imported from `frontend/src/ui` and `frontend/src/modules/develop`. A small Vite plugin swaps the app's backend modules (`io/api`, `state/library`, `state/catalog`, `state/develop`) for the in-page versions in `src/shims/`.

The photos are JavaScript data packs in `assets/media/` (one per collection, base64 JPEG data URIs) that the page loads by injecting a script tag, because Chrome blocks `fetch` of local files from `file://`. Each photo is first decoded at 512 px for its thumbnail and decoded at full size only when it is opened, exported or previewed.

Chrome does not run `type="module"` scripts from `file://`, so the build is a classic script (IIFE) with the stylesheet and fonts bundled and no `crossorigin` attributes.

Rebuild after changing anything under `demo/src` or the shared interface modules:

```
frontend/node_modules/.bin/tsc -p demo/tsconfig.json
frontend/node_modules/.bin/vite build --config demo/vite.config.mjs
```

The build writes `index.html` and `assets/` into this folder. The dev server (`vite --config demo/vite.config.mjs`) uses port 5395 and the preview server 5396, both bound to localhost only.

## Limits

Masks, local adjustments, noise reduction, HDR and panorama merges, maps, books, printing, web galleries, the catalog on disk, and RAW demosaicing are desktop features and are not in the demo. Images are processed at up to 3000 px on the long edge, and exports are limited to that size.
