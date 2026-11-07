# formlit demo 2: develop

The Develop module of formlit running in a browser tab, with the parts demo 1 leaves out: masks and local adjustments, presets you make, virtual copies, and a library already edited with a tone curve, colour mixer and colour grading. No engine, no network, no CDN, no account. Open `index.html` straight from disk (`file://`) or serve this folder with any static server. Photos you open never leave the page.

The three demos: [demo 1](../../demo/index.html) (library, develop basics, export), this one, and [share](../share/index.html) (output modules). The status bar of each links to the others.

## What it shows

- Masks. Create Subject, Sky and Background selections, Linear and Radial gradients (drag on the photo, then move the pins), a Brush (size, feather, flow, density, erase with Alt), Color Range (click the photo; Shift-click adds colours) and Luminance Range. Add, Subtract or Intersect components, Invert, Duplicate, hide with the eye, and turn on Show Overlay for the red overlay. Subject, Sky and Background edges have Refine Edge (snaps to the photo), Shift Edge and Feather.
- Local adjustments. Each mask has its own Temp, Tint, Exposure, Contrast, Highlights, Shadows, Whites, Blacks, Texture, Clarity, Dehaze, Saturation, Sharpness, Noise and Amount, effect presets (Burn, Dodge, Darken Sky and others) and your own saved effect presets.
- Presets you make. New Preset in My Presets or the Develop menu opens the app's own New Develop Preset dialog: name, group, which setting groups to include. Presets apply with an Amount slider and are kept in the browser.
- Virtual copies. Create Virtual Copy (Photo menu, or the button in the Virtual Copies panel) makes a copy that shares the photo and keeps its own settings, history and masks. Copies appear in the Virtual Copies catalog.
- Tone curve, Color Mixer, Color Grading wheels, Before and After and Split, history, clipping: the same panels as demo 1, shown on photos that already use them.
- Export: JPEG, PNG or WebP of any photo, with masks baked in.

The nine photographs open in three shoots (Alpine Evening, Coast Walk, Autumn Woods). Seven carry masks. Select Sky and Select Subject work on the six photos that ship a prepared selection (the Sky and Subject buttons are disabled with a reason elsewhere); every other mask works on any photo, including your own.

## Run it

```
open demos/develop/index.html
```

or

```
cd demos/develop && python3 -m http.server 5398
```

## How it is built

`src/` imports demo 1's modules by path (store, library shim, Library view, Develop module and panels, actions, the pipeline port) and the app's own interface code from `frontend/src`. Nothing under `demo/` or `frontend/` is changed. Three things are new: a render module that replaces demo 1's `engine/render` at build time (`src/render-masks.ts`, selected by the Vite plugin in `vite.config.mjs`) so thumbnails, the Develop canvas and exports all show masks; the mask engine (`src/masks/`); and the Masking, My Presets and Virtual Copies panels with the on-photo overlay.

The photographs and selections are JavaScript data packs in `assets/media/` loaded by injecting a script tag, because Chrome blocks `fetch` of local files from `file://`. The build is a classic script (IIFE) with no `crossorigin` attributes.

Rebuild after changing anything under `src/` (run from this folder; node_modules is the app's own, in `frontend/`):

```
../../frontend/node_modules/.bin/tsc -p tsconfig.json
node ../../frontend/node_modules/vite/bin/vite.js build --config ./vite.config.mjs
```

The build writes `index.html` and `assets/` into this folder. The dev server uses port 5397 and the preview server 5398, both bound to localhost only.

## Limits

Masks are computed in the page: they are approximations of the desktop engine's, not bit-identical. Masks follow the crop, straighten and flips but not the Transform panel's keystone. People and landscape parts, depth range, edge range, point colour inside a mask, edge-point editing, brush Auto Mask and Edge Snap, healing, noise reduction, merges, maps, books, printing and RAW demosaicing are desktop features.
