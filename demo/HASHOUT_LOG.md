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

## Why real photographs (media pass, v0.49.1)

The first demo opened on procedural scenes and read as a tech test. It now opens on 25 Pexels photographs in four collections, chosen so the grid looks like a working photographer's library: mountain lakes, coastlines, city at night, autumn woods. Each photo page was read and stated "Free" under the Pexels License; sources are in CREDITS.md. Procedural scenes remain as an offline fallback and as optional extras in the left panel.

Pexels strips camera metadata from the files it serves, but its photo pages publish camera model, focal length, aperture, ISO, shutter and capture date for most photos. Those published values were written back into each file as EXIF, so the app's own EXIF reader supplies the Metadata panel. The pages give a date without a time of day, so the time is 00:00:00. Photos whose page published no camera data were not used.

Ratings, flags, labels, keywords and 18 develop histories are demo catalogue data written for the demo. Edits are composed from the app's own presets plus hand patches and committed through the same history call as the Develop module, one entry per step.

## Why data packs and two decode sizes

Reading pixels needs a decode, and Chrome on `file://` blocks `fetch` of local files and taints a canvas that draws a file image. So the photos ship as JS data packs of base64 data URIs, loaded by injecting a script tag. A 1600 px source decoded to a linear float image with its mip pyramid is about 27 MB, so 25 of them would not fit comfortably. Every photo is therefore decoded once at 512 px (about 2 MB) for thumbnails, and the full size is decoded when a photo is opened in Develop, previewed in the loupe or exported. At most six full sources are kept; the least recently used one drops back to its small source. Sources have unique ids so the renderers' per-source caches never mix sizes. The pack strings are released after the blobs are made.

The loupe preview is rendered from the full source, and the loupe now refreshes when the preview is ready; before, it showed the thumbnail until something else redrew it.

## Interleaved order

Photos are added round-robin across the four collections so the first rows of the grid show every kind of scene. Collections are still one click away in the Catalog panel, with counts.

## Why no procedural-only opening

The brief for this pass is that the first screen is real media. Failure to load a pack shows a toast and falls back to the six procedural scenes.

## Responsiveness

Dragging a slider renders a low-resolution frame and scales it into place; the full-resolution frame is drawn on release. The sampled, linear and plane stages are cached per photo and recomputed only when their inputs change. The canvas, histogram and panels are patched in place, so there is no clear-and-refill.

## RAW

RAW files are opened by extracting the largest embedded JPEG. This was not tested against a real RAW file in this build; it is covered by the format reader only.

## Dev server ports

5395 for the dev server and 5396 for preview, `host: false`, strict port.

## Not done

Masks, local tools, noise reduction, merges, map, book, print, web, catalog on disk, true RAW decoding, and undo across photos.
