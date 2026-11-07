# HASHOUT_LOG · demo · formlit

Rationale, decisions and removed or never-written comments for the offline demo. Source files stay comment-free.

Current build version: v0.49.0

## Why a TypeScript port of the pipeline

The engine is Python with numba kernels, so a page cannot call it. The demo ports the global (non-mask) stages to TypeScript: Rec.2020 linear working space, Bradford white balance with Robertson temperature and tint, the exposure-domain tone LUTs, highlights, shadows, whites and blacks softplus curves, the contrast sine pivot, monotone Hermite curves, the Oklab mixer, black and white, vibrance, saturation, grading wheels, gamut mapping, clarity, texture, dehaze and sharpening planes, vignette, grain, geometry and calibration. The control table is `shared/controls.json`, imported directly, so ids, ranges and defaults cannot drift from the app.

The port is faithful in structure but not bit-identical: the numba kernel and this code round differently and the demo uses an area-averaged mip pyramid for previews. The demo is for trying the look, not for matching exports.

## Why shims and a resolve plugin

Reusing the app's real modules keeps the demo visually identical and honest. Those modules import `io/api`, `state/library`, `state/catalog` and `state/develop`, which talk to the engine. The Vite plugin in `vite.config.mjs` resolves exactly those four modules to in-page versions with the same surface, so no app file is edited or forked.

## Why a classic script build

Chrome refuses `type="module"` scripts and `crossorigin` stylesheets from `file://`. The build uses an IIFE bundle, moves the script to the end of the body, and strips `type` and `crossorigin`. Fonts are inlined as data URIs (the same Inter and JetBrains Mono files already listed in NOTICE.md), so the page makes no requests at all. The theme boot script is copied from `frontend/index.html` at build time so the first paint matches the app.

## Why procedural samples

No photo is bundled, so nothing needs a licence and the folder stays small. Six scenes are drawn into canvases at start and carry fake EXIF so the metadata panel has content. Canvases are never tainted because no image is loaded from another origin.

## Responsiveness

Dragging a slider renders a low-resolution frame and scales it into place; the full-resolution frame is drawn on release. The sampled, linear and plane stages are cached per photo and recomputed only when their inputs change. The canvas, histogram and panels are patched in place, so there is no clear-and-refill.

## RAW

RAW files are opened by extracting the largest embedded JPEG. This was not tested against a real RAW file in this build; it is covered by the format reader only.

## Dev server ports

5395 for the dev server and 5396 for preview, `host: false`, strict port.

## Not done

Masks, local tools, noise reduction, merges, map, book, print, web, catalog on disk, true RAW decoding, and undo across photos.
