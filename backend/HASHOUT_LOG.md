# HASHOUT_LOG · backend · formlit

Living log of all comment content, explainers, rationale, TODOs and removed code for the engine. Source files stay comment-free; everything they would have said lives here, indexed. Read this first, then edit code surgically.

Current build version: v0.2.0
Last updated: 2026-10-07 · colour-table profiles, Adobe profile import, DCPs in camera space, the classical reflection filter tried and withdrawn

---

## Org-navi-map

```
backend/
├── formlit_engine.py              PyInstaller entry for the desktop sidecar
├── boot_backend(.bat)             dev boot with uvicorn --reload on 8390
├── oc_install(.bat)               venv and requirements install
├── requirements*.txt              pinned deps; _ml adds the AI extra, _desktop adds PyInstaller
└── app/
    ├── __init__.py                __version__
    ├── main.py                    FastAPI app, routers, startup and shutdown
    ├── core/
    │   ├── config.py              ports, data folders, workers, env loading
    │   └── prefs.py               JSON preferences in the data folder
    ├── engine/
    │   ├── boot.py                loads command modules, warms the numba kernel
    │   ├── catalog.py             SQLite catalog, Change (undo, events), schema
    │   ├── commands.py            @command registry, dispatch, resolve_ids
    │   ├── events.py              server-sent event bus
    │   ├── tasks.py               background tasks with progress and cancel
    │   ├── query.py               photo queries, smart rules, text filter, facets
    │   ├── records.py             row decoding, summaries and details
    │   ├── presets.py             develop presets, adaptive presets, import and export
    │   ├── cmd_library.py         catalog, import, folders, collections, keywords, stacks, metadata
    │   ├── cmd_develop.py         settings, history, snapshots, copy and sync, Before
    │   ├── cmd_ai.py              models, AI masks, remove, merges, enhance, faces, culling
    │   └── cmd_output.py          export, print, book, slideshow, web, publish, map, Edit In, video, tether
    ├── develop/
    │   ├── settings.py            control table, defaults, groups, clamping
    │   ├── render.py              stage orchestration, caching, render and render_region
    │   ├── geometry.py            Frame: crop, rotation, lens warp, Upright, sampling
    │   ├── planes.py              denoise, low-frequency planes, blurs
    │   ├── finish.py              numpy reference finish, overlays, output transfer
    │   ├── kernel.py              numba finish (the fast path)
    │   ├── masks.py               mask shapes, ranges, evaluation, local terms and curves
    │   ├── retouch.py             spots (heal, clone, remove) and red eye
    │   ├── colorops.py            OkLCh colour operations, mixer, Point Color, grading
    │   ├── colour.py              colour spaces, Bradford, OkLab, encodings
    │   ├── curves.py              tone LUTs, monotone point curves
    │   ├── auto.py                Auto tone, Auto white balance, Auto B&W
    │   ├── profiles.py            built-in looks baked to colour tables, .cube LUTs, profile import
    │   ├── adobe_profile.py       Adobe creative profile (.xmp RGBTable) reader and resampler
    │   ├── camera_styles.py       camera-matching styles per maker, as-shot style from the raw
    │   ├── dcp.py                 DNG camera profiles applied in camera space
    │   ├── camera_look.py         fitted Camera Look from the embedded JPEG
    │   ├── lensprofile.py         DNG opcode lens profiles
    │   ├── fringe.py              defringe
    │   ├── lensblur.py            depth-driven lens blur
    │   └── output.py              ICC profile writing, 8-bit conversion
    ├── ai/
    │   ├── models.py              model catalogue, SHA-pinned downloads
    │   ├── nets.py                ONNX sessions: U2-Net, sky, depth, SAM
    │   ├── parts.py               people and landscape parts
    │   ├── people.py              per-person masks from faces
    │   ├── cull.py                sharpness, exposure, eyes, groups
    │   ├── merge.py               HDR and panorama merge
    │   ├── enhance.py             denoise, super resolution, raw details
    │   ├── upright.py             line segments, vanishing points, straighten
    │   └── dng.py                 linear and CFA DNG writer and reader
    ├── output/
    │   ├── export.py              export settings, render_photo, export_one, video, DNG
    │   ├── encode.py              formats, metadata filtering, EXIF and XMP, HDR encode
    │   ├── gainmap.py             HDR gain maps, SDR rendition, Ultra HDR
    │   ├── icc.py                 ICC profiles, soft proof, conversions
    │   ├── layout.py              print and book page layouts, templates
    │   ├── pages.py               PDF, JPEG pages, printers
    │   ├── slideshow.py           slideshow layout and video
    │   ├── web.py                 web galleries and FTP upload
    │   ├── publish.py             publish services, status, run, comments
    │   ├── publish_sdk.py         plug-in loader and session
    │   └── services/
    │       ├── webdav.py          WebDAV and Nextcloud plug-in
    │       └── s3.py              S3-compatible plug-in (SigV4)
    ├── services/
    │   ├── decode.py              raw and image decoding to linear Rec.2020
    │   ├── importer.py            scan, import, duplicates, transfer
    │   ├── previews.py            thumbnails, previews, sources, smart previews
    │   ├── metadata.py            EXIF, IPTC, XMP read and write
    │   ├── xmp_presets.py         Camera Raw settings to and from formlit
    │   ├── xmpwrite.py            automatic sidecar writing, conflict check
    │   ├── xmpembed.py            XMP inside JPEG, TIFF and DNG
    │   ├── rename.py              rename templates
    │   ├── lensdb.py              Lensfun database
    │   ├── tether.py              gphoto2 and digiCamControl sessions
    │   ├── watch.py               auto import folder watcher
    │   └── catalog_io.py          Export as Catalog, Import from Another Catalog
    └── routers/
        ├── __init__.py            router list
        ├── commands.py            /api/commands and /api/batch
        ├── events.py              /api/events
        ├── photos.py              thumbs, previews, originals, render, masks
        ├── files.py               file browser, uploads
        ├── faces.py               face crops
        ├── output.py              exported files, slideshow audio
        ├── system.py              health, version, capabilities
        └── mcp.py                 MCP server: tools, prompts, window bridge
```

---

## Table of contents

- [formlit_engine.py](#formlit-engine)
- [app/core/config.py](#core-config)
- [app/engine/boot.py](#engine-boot)
- [app/engine/catalog.py](#engine-catalog)
- [app/engine/commands.py](#engine-commands)
- [app/engine/cmd_library.py](#engine-cmd-library)
- [app/engine/cmd_develop.py](#engine-cmd-develop)
- [app/engine/cmd_ai.py](#engine-cmd-ai)
- [app/engine/cmd_output.py](#engine-cmd-output)
- [app/engine/presets.py](#engine-presets)
- [app/develop/render.py](#develop-render)
- [app/develop/finish.py and kernel.py](#develop-finish-kernel)
- [app/develop/masks.py](#develop-masks)
- [app/develop/lensblur.py](#develop-lensblur)
- [app/develop/profiles.py, adobe_profile.py and dcp.py](#develop-profiles)
- [app/develop/reflections.py (removed in v0.2.0)](#develop-reflections)
- [app/ai/people.py](#ai-people)
- [app/ai/merge.py and enhance.py](#ai-merge-enhance)
- [app/output/export.py](#output-export)
- [app/output/encode.py](#output-encode)
- [app/output/gainmap.py](#output-gainmap)
- [app/output/layout.py and pages.py](#output-layout-pages)
- [app/output/slideshow.py](#output-slideshow)
- [app/output/publish.py and publish_sdk.py](#output-publish)
- [app/output/services/s3.py](#output-services-s3)
- [app/output/services/webdav.py](#output-services-webdav)
- [app/services/decode.py](#services-decode)
- [app/services/previews.py](#services-previews)
- [app/services/tether.py](#services-tether)
- [app/routers/output.py](#routers-output)
- [app/routers/photos.py](#routers-photos)
- [app/routers/mcp.py](#routers-mcp)
- [Files with no entries](#no-entries)

---

## formlit_engine.py {#formlit-engine}

### formlit_engine.py · main
- refers-to: formlit_engine.py :: main (startup)
- kind: explainer
- logged: v0.1.0 · 2026-10-07

The frozen entry sets `FORMLIT_DESKTOP=1` and `FORMLIT_DIST` to the bundled frontend with `setdefault`, then binds `FORMLIT_PORT` (0 picks a free port) and prints the port on its startup line; the Tauri shell reads that line. Development never runs this file.

---

## app/core/config.py {#core-config}

### app/core/config.py · NUMBA_CACHE_DIR
- refers-to: app/core/config.py :: module bottom
- kind: warning-context
- logged: v0.1.0 · 2026-10-07

`NUMBA_CACHE_DIR` is set at import, before anything imports numba, so the compiled kernel is cached in the data folder and later warms in about 0.3 s instead of recompiling. Moving it below a numba import silently disables the cache.

### app/core/config.py · previews_dir, masks_dir, faces_dir
- refers-to: app/core/config.py :: previews_dir
- kind: rationale
- logged: v0.1.0 · 2026-10-07

Caches sit beside the catalog file, not in the data root, so two catalogs never share previews or masks keyed by the same photo id.

---

## app/engine/boot.py {#engine-boot}

### app/engine/boot.py · _warm
- refers-to: app/engine/boot.py :: _warm
- kind: warning-context
- logged: v0.1.0 · 2026-10-07

Until the numba kernel is warm, `kernel.best_finish` falls back to the numpy reference finish, which holds several full-size float arrays (band weights alone are 8 floats a pixel). A full-size export of a 24 MP raw in that window peaks far higher than with the kernel. The warm thread starts at boot; with the cache in place it finishes in well under a second.

---

## app/engine/catalog.py {#engine-catalog}

### app/engine/catalog.py · Change.insert
- refers-to: app/engine/catalog.py :: Change.insert (photos branch)
- kind: rationale
- logged: v0.1.0 · 2026-10-07

SQLite reuses the highest rowid once the last rows are deleted (undoing an import does exactly that), and preview files are named `{pid}-{rev}-{size}`. A new photo with a reused id and develop_rev 0 used to show the removed photo's thumbnail. Inserting a photos row now calls `previews.drop_source` and `previews.clear` for the id. Undo and redo re-insert through `_apply`, not `insert`, so a redo keeps its own valid cache.

### app/engine/catalog.py · Change and undo
- refers-to: app/engine/catalog.py :: Catalog._apply, undo
- kind: explainer
- logged: v0.1.0 · 2026-10-07

Each change keeps its operations (insert, update with before and after, delete, meta). Undo replays them reversed; events are published after commit with the photo ids added, removed and changed (with the changed fields), and the lists touched.

---

## app/engine/commands.py {#engine-commands}

### app/engine/commands.py · dispatch
- refers-to: app/engine/commands.py :: dispatch
- kind: warning-context
- logged: v0.1.0 · 2026-10-07

Unknown parameters are rejected, so a renamed parameter breaks callers loudly. The CLI parses every `key=value` as JSON when it can, so numbers arrive as ints: commands that need strings convert explicitly (`tether.set` calls `str()` on its key and value for this reason).

---

## app/engine/cmd_library.py {#engine-cmd-library}

### app/engine/cmd_library.py · remove
- refers-to: app/engine/cmd_library.py :: photo remove
- kind: rationale
- logged: v0.1.0 · 2026-10-07

Removing the top photo of a stack left the others hidden behind a missing top. Remove now renumbers the stack, or dissolves it when one photo is left.

### app/engine/cmd_library.py · WATCH, changed_files, folder.synchronize
- refers-to: app/engine/cmd_library.py :: changed_files, folder_synchronize
- kind: explainer
- logged: v0.1.0 · 2026-10-07

Files edited elsewhere (Edit In, other apps) are found by size and modification time; their previews and decoded source are dropped and `develop_rev` bumped so every view re-renders. Synchronize is scoped to the folder and its subfolders; a dry run returns what would change, and Remove Missing only touches that folder.

---

## app/engine/cmd_develop.py {#engine-cmd-develop}

### app/engine/cmd_develop.py · before_of
- refers-to: app/engine/cmd_develop.py :: before_of, develop.setBefore
- kind: explainer
- logged: v0.1.0 · 2026-10-07

The Before state is stored in catalog meta under `before:{pid}`; without it Before is the defaults. It can be set from the After, the defaults, a history step or a snapshot, and swapped with the After.

---

## app/engine/cmd_ai.py {#engine-cmd-ai}

### app/engine/cmd_ai.py · adapt, ensure_masks
- refers-to: app/engine/cmd_ai.py :: adapt, ensure_masks, missing_bitmaps
- kind: rationale
- logged: v0.1.0 · 2026-10-07

AI mask bitmaps live per photo at `Masks/{pid}/{key}.png`, so a mask that reaches another photo (sync, paste, preset, virtual copy, import with a preset) has no bitmap there. `adapt(pids)` recomputes the missing ones in the background after those commands; `ensure_masks` recomputes synchronously inside export so a file never ships with an empty mask.

### app/engine/cmd_ai.py · _people
- refers-to: app/engine/cmd_ai.py :: _people, ai/people.py persons
- kind: rationale
- logged: v0.1.0 · 2026-10-07

Connected components seed people only when the face model is not installed; with faces available, components produced false people in photos without anyone in them.

### app/engine/cmd_ai.py · develop.findDust
- refers-to: app/engine/cmd_ai.py :: find_dust
- kind: rationale
- logged: v0.1.0 · 2026-10-07

A plain threshold found about 200 false spots on textured photos. The criterion is a signal-to-noise test: the dip must exceed `max(k, (12 - 6 * sensitivity) * ring)` where `ring` is the local noise around it.

### app/engine/cmd_ai.py · _fill_hole alpha mode
- refers-to: app/engine/cmd_ai.py :: _fill_hole
- kind: rationale
- logged: v0.1.0 · 2026-10-07

Remove People fills showed ghost outlines; the alpha patches take their grain from outside the hole and feather into it.

---

## app/engine/cmd_output.py {#engine-cmd-output}

### app/engine/cmd_output.py · slideshow.layout
- refers-to: app/engine/cmd_output.py :: slideshow_layout
- kind: explainer
- logged: v0.1.0 · 2026-10-07

With Fit to Music on, every still slide gets `seconds` from `slideshow.still_seconds`, so the in-app player and the running time match the exported video. Clip slides carry their own `seconds` and `clip`.

### app/engine/cmd_output.py · publish.createService
- refers-to: app/engine/cmd_output.py :: publish_create_service
- kind: rationale
- logged: v0.1.0 · 2026-10-07

The kind is not an enum in the schema because plug-in kinds load at run time; the command checks folder, ftp and the loaded plug-ins instead.

---

## app/engine/presets.py {#engine-presets}

### app/engine/presets.py · merge_masks, adaptive built-ins
- refers-to: app/engine/presets.py :: merge_masks
- kind: explainer
- logged: v0.1.0 · 2026-10-07

Applying a preset with masks merges them into the photo's masks (scaled by the preset amount) rather than replacing them; the nine adaptive built-ins (sky, subject, portrait) carry AI mask shapes that `adapt` computes per photo.

---

## app/develop/render.py {#develop-render}

### app/develop/render.py · stage cache keys
- refers-to: app/develop/render.py :: _stage_render
- kind: explainer
- logged: v0.1.0 · 2026-10-07

Three cached layers per slot: geometry (sampled image, spots, red eye), linear (white balance, noise reduction, defringe, lens blur) and masks. Each key includes everything its layer reads, so a slider in the finish stage never re-samples. Mask evaluation re-runs when masks change or when a luminance range depends on exposure.

### app/develop/render.py · apply_curves placement
- refers-to: app/develop/render.py :: render, render_region
- kind: alternative
- logged: v0.1.0 · 2026-10-07

Local mask curves are applied after the finish, through each mask's alpha, instead of inside both finish implementations. The output is decoded to the sRGB-encoded values the global curve sees, curved, and re-encoded, so the curve behaves the same in every output space. Moving them into the kernel would put them before grain and the profile LUT.

### app/develop/render.py · camera profile in the linear stage
- refers-to: app/develop/render.py :: _stage_render (dcp.apply_linear)
- kind: rationale
- logged: v0.2.0 · 2026-10-07

A DCP is applied right after white balance, in linear ProPhoto, which is where Camera Raw applies a profile's hue and saturation map and look table, so exposure and the tone sliders work on the profile's colours instead of under them. The profile id joins the linear key only when it is a DCP, so switching between built-in looks never re-runs the linear stage.

---

## app/develop/finish.py and kernel.py {#develop-finish-kernel}

### app/develop/finish.py · decode_trc
- refers-to: app/develop/finish.py :: decode_trc, encode_trc
- kind: explainer
- logged: v0.1.0 · 2026-10-07

`encode_trc` turns the sRGB-encoded finish result into the output space's transfer (linear, gamma 1.8 or 2.2); `decode_trc` is its inverse for passes that work on the encoded values after the finish.

### app/develop/kernel.py · parity with finish.py
- refers-to: app/develop/kernel.py :: finish
- kind: warning-context
- logged: v0.1.0 · 2026-10-07

The numba kernel and the numpy reference must give the same picture. Any change to one is made to the other in the same turn and compared on the demo photos.

---

## app/develop/masks.py {#develop-masks}

### app/develop/masks.py · terms
- refers-to: app/develop/masks.py :: terms
- kind: explainer
- logged: v0.1.0 · 2026-10-07

Besides the slider terms, a mask's adjust can hold `colorHue` and `colorSat` (tint), `pointColors` (applied on linear light by `apply_points`) and `curve` (built with `curves.curve_luts`, applied by `apply_curves`). Both kernels ignore keys they do not know, so new structured terms stay out of the hot loop.

---

## app/develop/lensblur.py {#develop-lensblur}

### app/develop/lensblur.py · apply
- refers-to: app/develop/lensblur.py :: apply (blend loop)
- kind: removed-code
- logged: v0.1.0 · 2026-10-07

```python
levels = [src] + [_shaped(src, max_r * k / (LEVELS - 1), bokeh, shape) for k in range(1, LEVELS)]
out = np.zeros_like(lin)
for k in range(LEVELS - 1):
    m = (i0 == k)[..., None]
    out = np.where(m, levels[k] * (1 - t) + levels[k + 1] * t, out)
```

Held all six full-size blur levels plus three full-size temporaries per step; a 24 MP raw with Lens Blur exhausted memory and the engine was killed. Replaced by generating levels one after another and blending only the pixels of each band (max difference 2.4e-7, peak 2.9 GB for the same export).

---

## app/develop/profiles.py, adobe_profile.py and dcp.py {#develop-profiles}

### app/develop/profiles.py · PROFILES
- refers-to: app/develop/profiles.py :: PROFILES, effective
- kind: todo (resolved v0.2.0)
- logged: v0.1.0 · 2026-10-07

Built-in looks were setting offsets applied beneath the sliders. Resolved in v0.2.0: colour looks are baked to 3D tables, Adobe creative profiles import, and DCPs apply in camera space. See the entries below.

### app/develop/profiles.py · table_of, is_table, SPATIAL
- refers-to: app/develop/profiles.py :: table_of, is_table, effective, lut_of
- kind: rationale
- logged: v0.2.0 · 2026-10-07

A look is baked once into a 33-point sRGB table by running the numpy finish over a lattice with the look's per-pixel deltas, then applied through the same LUT hook as an imported `.cube`, so Amount scales it from 0 to 200 percent and the sliders stay at their own values instead of carrying the look's offsets. Two kinds of key stay as offsets (`offset_key`): Clarity, Texture and Dehaze (`SPATIAL`), which are neighbourhood operations a per-pixel table cannot hold, and the `bw.*` mix of black and white looks, which is a colour filter that has to act before the conversion to grey. A black and white look is the treatment switch plus those mix offsets plus a table holding its tone and toning; the table is baked on colour input but at render time it receives the already-grey picture, so it adds contrast and toning without touching the user's own B&W mix. The lattice uses `log_l` equal to `base` so local contrast terms see no detail; `info.raw` is False so no camera tone is applied twice. The table runs before grain (both finish implementations) so a look never reshapes the grain.

### app/develop/profiles.py · in_space, lut_of(dev, space)
- refers-to: app/develop/profiles.py :: in_space, SPACE_N, _SPACE_TABLES; finish.py and kernel.py call sites
- kind: rationale
- logged: v0.2.0 · 2026-10-07

Tables are authored in sRGB, but the finish hands them values encoded in the export's own primaries, so a ProPhoto or Adobe RGB export used to get a different look. `in_space` re-expresses a table for a space once (49 points, cached against the table object): each lattice point is converted to sRGB, looked up, and the change is carried back as a linear delta, so in-gamut colours match the sRGB result exactly and wide-gamut colours keep their gamut instead of being clipped to sRGB.

### app/develop/camera_styles.py and profiles.py · camera-matching sets
- refers-to: app/develop/camera_styles.py :: STYLES, SETS, RENAME, MAKES, as_shot, id_for_name, crs_name; profiles.py :: _delta, style_of, effective(dev, info), catalogue(camera, keep); finish.py :: camera_matrix_look
- kind: rationale
- logged: v0.2.0 · 2026-10-07

Lightroom's camera-matching profiles are Adobe-made DCPs per camera model, which cannot be shipped. formlit's equivalent has two parts. Camera Look is fitted per photo to the camera's own embedded JPEG (tone curve and colour matrix), so it reproduces whatever picture style the photo was shot in. Each maker's named styles (`SETS`, with maker wording in `RENAME`, chosen from the first word of the catalog's camera name through `MAKES`) are tables built on top of Camera Look (any id beginning `fl.camera` turns it on in `camera_matrix_look`). The deltas describe each style relative to the maker's standard rendering, from the makers' published descriptions, and are approximations.

Because Camera Look already contains the as-shot style, the other styles are built relative to it: `as_shot` reads the style from the raw (Canon CR2 maker note 0x00A0, ProcessingInfo index 10; Auto is treated as Standard), the decoder stores it as `cameraStyle`, and `_delta` subtracts that style's deltas, so choosing the as-shot style gives exactly Camera Look and no style is applied twice. Colour grading hues are absolute angles and are copied, every other key (mixer hues included) is subtracted. A black and white as-shot style is ignored (its JPEG holds no colour to build from). Other raw formats do not report the style yet, so the styles assume Standard, and the Profile Browser says so. `catalogue(keep=...)` keeps a photo's current camera style in the list even when it belongs to another maker's set. `xmp_presets` maps Camera Raw's `CameraProfile` names (including the renamed ones) to these ids and back.

### app/develop/adobe_profile.py · format
- refers-to: app/develop/adobe_profile.py :: _base85, read, to_srgb
- kind: explainer
- logged: v0.2.0 · 2026-10-07

An Adobe creative profile is an XMP with `crs:RGBTable` naming a `crs:Table_[md5]` attribute. The attribute is Adobe's base85 (alphabet in `ALPHABET`, little-endian 32-bit groups, least significant digit first) over a 4-byte little-endian length and a zlib stream. The stream holds a header (type 1, version 1, dimensions 3, divisions), then uint16 samples stored as deltas from the identity lattice, red outermost and blue innermost, then the primaries, gamma and gamut enums and the amount range as two doubles. Enums follow the DNG SDK: primaries 0 sRGB, 1 Adobe RGB, 2 ProPhoto, 3 Display P3, 4 Rec.2020; gamma 0 linear, 1 sRGB, 2 1.8, 3 2.2, 4 Rec.2020; gamut 0 clip, 1 extend. Layout checked against the MIT-licensed CUBE-to-XMP converter (round trip max error 7.6e-6); no code was copied from either source. Tables in other spaces are resampled into an sRGB lattice through XYZ with Bradford adaptation, then saved as a `.cube` with a JSON sidecar for the name, group and the grayscale flag.

### app/develop/adobe_profile.py · look_table_only
- refers-to: app/develop/adobe_profile.py :: look_table_only; engine/presets.py :: preset.import
- kind: todo
- logged: v0.2.0 · 2026-10-07

Some Adobe profiles carry their look as an HSV look table (`crs:LookTable`, the DCP-style hue, saturation and value map) instead of, or beside, an RGB table. The binary layout of that table inside the XMP is not documented in any source available to this build, so such a file is refused with a message rather than imported as a plain preset that silently loses its look. Profiles that hold an RGB table (the large majority, including every profile made with Camera Raw's profile tools from a LUT) import. Supporting the look-table form needs the layout of the DNG SDK's look table stream.

### app/develop/dcp.py · apply_linear, to_prophoto, weight1, tone_knots
- refers-to: app/develop/dcp.py :: load, fits_camera, weight1, _pick, to_prophoto, needs_exposure, apply_linear, tone_knots, _apply_table, LIGHT_K, SENSOR_EV
- kind: rationale
- logged: v0.2.0 · 2026-10-07

The order follows the DNG reference. `to_prophoto`: when the DCP names the photo's camera (`fits_camera` on UniqueCameraModel against the catalog camera) and the decoder recorded LibRaw's camera to Rec.2020 matrix, the image is taken back to white-balanced camera RGB and converted with the DCP's ForwardMatrix to XYZ D50, or, without one, with its ColorMatrix and the neutral of the current white balance, then Bradford to D50. Otherwise the plain Rec.2020 to ProPhoto conversion is used, since matrices only fit their own camera. Both matrices and hue/saturation maps are blended between the two calibration illuminants by 1/T of the white balance temperature (`weight1`; illuminant temperatures in `LIGHT_K` are the DNG SDK's). The hue/saturation map sees sensor-relative values (divided by `sensorGain`), then BaselineExposureOffset is applied, then the look table sees post-exposure values (scaled by 2^(Exposure − 0.35), the 0.35 EV formlit adds at decode); a look table with value divisions or sRGB encoding therefore depends on Exposure, so only then does Exposure join the linear stage's cache key (`needs_exposure`). For sRGB-encoded tables the value scale multiplies the encoded value, as `RefBaselineHueSatMap` does. A ProfileToneCurve becomes the base tone (`tone_knots` resamples it into the 32 knots `camera_look` uses, mapping formlit's scene scale to the DNG one by 2^-0.35); `finish.camera_tone` picks it up for both kernels. Work is done in 256-row chunks to bound memory. Validated with synthetic profiles: a ForwardMatrix equal to LibRaw's conversion reproduces the plain render; grey 0.18 with an sRGB-encoded value scale of 1.25 gives 0.292 as in the reference. Known cost: with a 3D look table, Exposure drags re-run the numpy DCP stage (about 2.7 s at 1600 px).

### app/develop/dcp.py · bake, to_cube
- refers-to: app/develop/dcp.py :: bake, to_cube (removed v0.2.0)
- kind: removed-code
- logged: v0.2.0 · 2026-10-07

```python
def bake(prof: dict, size: int = 33) -> np.ndarray:
    ...
    pp = lin @ SRGB_TO_PP.T
    # hue and saturation map, then look table
    out = np.clip(pp @ PP_TO_SRGB.T, 0.0, 1.0)
    return srgb_encode(out)

def to_cube(src: Path, dst_dir: Path) -> tuple[Path, str]:
    # validate, bake, write a 33-point .cube named after the profile
```

v0.1.0 baked a DCP into a display-referred sRGB table, applied after the tone curve, so the profile's maps saw clipped, tone-mapped values. Replaced by `profiles.import_dcp` (copies the DCP and a JSON name sidecar) and `apply_linear` in the render's linear stage. The module's own Bradford and ProPhoto constants went with it; `colour.py` provides both.

---

## app/develop/reflections.py (removed in v0.2.0) {#develop-reflections}

### app/develop/reflections.py · suppress, layer, global_layer, apply
- refers-to: app/develop/reflections.py (deleted), render.py :: _stage_render, render_region; controls.json `reflections.amount`; settings.py GROUPS `reflections`; F/modules/develop/tools.ts SpotTool sRefl
- kind: removed-code
- logged: v0.2.0 · 2026-10-07

```python
def suppress(e, threshold, lam=1e-7):
    keep = smoothstep(0.7 * threshold, 1.3 * threshold, |grad(luma(e))|)
    kappa = 2cos(pi*i/h) + 2cos(pi*j/w) - 4          # DCT eigenvalues of the Laplacian
    for each channel a:
        div = divergence(keep * grad(a))
        out = idct((kappa * dct(div) + lam * dct(a)) / (kappa**2 + lam))

def global_layer(img, frame, wb_m, strength, key):   # cached per photo, strength, geometry
    small = frame.sample(img, *frame.fit_long(1536)) @ wb_m.T
    return srgb-encoded small minus suppress(small, 0.01 + 0.05 * strength), back to linear

def apply(lin, dev, glob, region, size):             # warp the layer into any size or region
    r = warpAffine(glob, pixel-centre map of region within size)
    return lin - r if amount > 0 else blend toward r + 0.5 * mean
```

A first Reflections slider (-100 to 100, in the Healing tool's remove row, its own sync group) used single-image reflection suppression after Arvanitopoulos, Achanta and Süsstrunk (CVPR 2017): keep strong gradients, drop weak ones, solve the screened Poisson equation in the DCT domain. The plumbing worked (a global layer on a 1536 px proxy, warped into every size and region, agreed with full renders to 1.2e-5), but the method itself did not: an independent audit composited real photos with blurred real reflections and found the slider moved the result further from the true scene in all 12 cases, and on a clean photo Amount 80 changed the picture by a mean of 0.075 (soft backgrounds blotched, skies greyed). A benchmark over four transmissions, three reflections each, two strengths and two blurs gave an error ratio of 2.0 (0.17 of cases improved); high-passing the layer to protect low frequencies cut the damage on clean photos to 0.013 but no case improved. Withdrawn before release rather than shipped as a control that makes photos worse. The plumbing above is the shape to reuse with a learned separation model (for example DSRNet, Apache-2.0), which replaces `suppress` and `layer` with one ONNX pass on the proxy.

---

## app/ai/people.py {#ai-people}

### app/ai/people.py · persons
- refers-to: app/ai/people.py :: persons
- kind: explainer
- logged: v0.1.0 · 2026-10-07

Splits the people segmentation into persons with a watershed seeded from detected faces, sorted left to right, so People masks can target one person.

---

## app/ai/merge.py and enhance.py {#ai-merge-enhance}

### app/ai/merge.py · hdr
- refers-to: app/ai/merge.py :: hdr
- kind: todo
- logged: v0.1.0 · 2026-10-07

Brackets are aligned by translation only; handheld brackets with rotation rely on deghosting.

### app/ai/enhance.py · denoise
- refers-to: app/ai/enhance.py :: denoise
- kind: alternative
- logged: v0.1.0 · 2026-10-07

Denoise is non-local means. A permissively licensed learned model (NAFNet MIT, SCUNet Apache) pinned by hash would replace it; none was adopted for v0.1.0.

---

## app/output/export.py {#output-export}

### app/output/export.py · in_private_location
- refers-to: app/output/export.py :: in_private_location, export_one
- kind: explainer
- logged: v0.1.0 · 2026-10-07

Saved locations store a radius in kilometres. A photo whose GPS falls within the great-circle radius of any location marked Private is exported with location removed, as if Remove Location were on. Publish goes through `export_one`, so it is covered too.

### app/output/export.py · DNG export
- refers-to: app/output/export.py :: export_one (dng branch)
- kind: explainer
- logged: v0.1.0 · 2026-10-07

A DNG original is copied with fresh XMP; other raws are written as a CFA DNG with `dng.write_cfa_dng` (uncompressed), falling back to a linear DNG when the mosaic cannot be read.

---

## app/output/encode.py {#output-encode}

### app/output/encode.py · _jxl
- refers-to: app/output/encode.py :: _jxl, encode_hdr
- kind: rationale
- logged: v0.1.0 · 2026-10-07

JPEG XL and 10-bit AVIF use imagecodecs (BSD-3). pillow-jxl-plugin was rejected because it is GPL-3, which cannot ship in a distributed build. HDR files are PQ in Rec.2020 with SDR white at 203 nits.

---

## app/output/gainmap.py {#output-gainmap}

### app/output/gainmap.py · render_pair
- refers-to: app/output/gainmap.py :: render_pair, gain_from
- kind: explainer
- logged: v0.1.0 · 2026-10-07

HDR is the SDR rendition times two to the gain, where the gain comes from an under-exposed render at minus the headroom in stops. The Ultra HDR boost was checked against libultrahdr's decoder and agrees within 5 to 8 percent.

---

## app/output/layout.py and pages.py {#output-layout-pages}

### app/output/layout.py · spine_width, BLEED
- refers-to: app/output/layout.py :: spine_width
- kind: warning-context
- logged: v0.1.0 · 2026-10-07

Spine width is estimated as 0.0025 in a page plus 0.25 in for the boards, and bleed is 0.125 in. Blurb publishes exact spine widths per paper and page count; check theirs before ordering.

### app/output/layout.py · book_pages spreads
- refers-to: app/output/layout.py :: book_pages
- kind: explainer
- logged: v0.1.0 · 2026-10-07

A spread template on a left page lays its cells across two page widths, then splits them into a left page and the following `spread-cont` page on output. Wrap covers are one page of back, spine and front with the spine text rotated 90 degrees.

---

## app/output/slideshow.py {#output-slideshow}

### app/output/slideshow.py · write_video timeline
- refers-to: app/output/slideshow.py :: write_video
- kind: explainer
- logged: v0.1.0 · 2026-10-07

Each slide has its own length in frames; the crossfade between slides i and i+1 is the smaller of the fade and half of either slide. Slide i starts at the sum of the earlier lengths minus their crossfades, which is also the delay applied to that slide's clip audio. Music tracks are concatenated, clip sound is delayed into place, both are mixed with `amix normalize=0` (ffmpeg 5.1 or newer), padded and trimmed to the video and faded out over the last two seconds.

### app/output/slideshow.py · Clip
- refers-to: app/output/slideshow.py :: Clip.frame
- kind: explainer
- logged: v0.1.0 · 2026-10-07

Clips are decoded by ffmpeg already scaled to the slide's image size and at the slideshow's frame rate, then graded with the photo's develop settings (minus video, masks, spots, red eye and lens blur, as in video export). Frames are read in order; asking past the end keeps the last frame.

---

## app/output/publish.py and publish_sdk.py {#output-publish}

### app/output/publish_sdk.py · load
- refers-to: app/output/publish_sdk.py :: load, _entries
- kind: explainer
- logged: v0.1.0 · 2026-10-07

Built-in plug-ins import as `app.output.services.*` (so the PyInstaller `--collect-submodules app` picks them up); user plug-ins load from `Plugins/` as files or packages, each failure recorded rather than raised. Kinds `folder` and `ftp` are reserved; a duplicate kind is an error. Settings keys in `SECRET` never leave the engine, and `keep_secrets` keeps a stored secret when an edit leaves it blank.

### app/output/publish.py · comments
- refers-to: app/output/publish.py :: comments, add_comment
- kind: explainer
- logged: v0.1.0 · 2026-10-07

Comments are read live from each comment-capable service the photo is published to; a failing service yields a thread with its error instead of failing the request.

---

## app/output/services/s3.py {#output-services-s3}

### app/output/services/s3.py · _send
- refers-to: app/output/services/s3.py :: Client._send
- kind: explainer
- logged: v0.1.0 · 2026-10-07

AWS Signature Version 4 by hand with hmac and hashlib, so no SDK is bundled. Path-style and virtual-hosted addressing both produce signatures identical to botocore's for the same request (checked with keys and paths containing spaces and tildes).

---

## app/output/services/webdav.py {#output-services-webdav}

### app/output/services/webdav.py · comments
- refers-to: app/output/services/webdav.py :: Client.comments, comment, _thread
- kind: explainer
- logged: v0.1.0 · 2026-10-07

Nextcloud and ownCloud comments: PROPFIND the file for `oc:fileid`, REPORT `oc:filter-comments` on `/remote.php/dav/comments/files/{id}` to read, POST JSON to it to write. Servers without `/remote.php/dav/` in the path are plain WebDAV and report no comments. Exercised against a local stand-in that follows Nextcloud's documented responses, not against a live Nextcloud.

---

## app/services/decode.py {#services-decode}

### app/services/decode.py · ICC handling
- refers-to: app/services/decode.py :: icc_matrix, icc_linear, is_srgb
- kind: explainer
- logged: v0.1.0 · 2026-10-07

Matrix and TRC ICC profiles (the usual case for ProPhoto, Adobe RGB and Display P3) are parsed directly: TRCs decoded per channel, the D50 matrix adapted to D65 with Bradford, then mapped into Rec.2020. LUT-based profiles fall back to sRGB.

### app/services/decode.py · _psd_linear
- refers-to: app/services/decode.py :: psd_header, _psd_linear
- kind: rationale
- logged: v0.1.0 · 2026-10-07

Pillow reads only 8-bit PSD, so 16 and 32-bit composites are read from the image data section directly, using Pillow's packbits decoder for compressed rows.

### app/services/decode.py · _cam_to_2020, sensorGain, cameraStyle
- refers-to: app/services/decode.py :: _cam_to_2020, XYZ_FROM_SRGB, _raw_linear, SOURCE_VERSION; previews.py :: source (camera)
- kind: explainer
- logged: v0.2.0 · 2026-10-07

Raw sources now record what DCPs and camera styles need: `camToRec2020`, LibRaw's own path from white-balanced camera RGB to Rec.2020 (its rgb_xyz matrix times dcraw's sRGB matrix, rows normalised, inverted, then sRGB to Rec.2020), `sensorGain` (the 2^(BaselineExposure + 0.35) applied at decode), and `cameraStyle` from `camera_styles.as_shot`. `previews.source` adds the catalog's camera name. SOURCE_VERSION went to 5 so cached sources are decoded again once.

---

## app/services/previews.py {#services-previews}

### app/services/previews.py · clear
- refers-to: app/services/previews.py :: clear, drop_source
- kind: explainer
- logged: v0.1.0 · 2026-10-07

`clear(pid, keep_rev)` deletes cached renders for a photo, keeping the embedded preview and decoded source when a revision is given; `drop_source` evicts the in-memory decoded source.

---

## app/services/tether.py {#services-tether}

### app/services/tether.py · DigiCamSession
- refers-to: app/services/tether.py :: DigiCamSession
- kind: todo
- logged: v0.1.0 · 2026-10-07

The gphoto2 session was exercised with a simulated gphoto2 (capture, preview, settings and choices). The digiCamControl adapter for Windows follows its command-line documentation and has not been run against the program or a camera.

---

## app/routers/output.py {#routers-output}

### app/routers/output.py · audio
- refers-to: app/routers/output.py :: audio
- kind: warning-context
- logged: v0.1.0 · 2026-10-07

Serves slideshow music from anywhere on disk, so it is limited to audio extensions; the engine listens on loopback only.

---

## app/routers/photos.py {#routers-photos}

### app/routers/photos.py · render hdr modes
- refers-to: app/routers/photos.py :: render
- kind: explainer
- logged: v0.1.0 · 2026-10-07

`hdr: "display"` returns an AVIF in PQ with `X-HDR-Hist` and `X-HDR-Stops` headers for the HDR histogram; `"sdr"` renders the SDR rendition; `"visualize"` paints the areas above SDR white.

---

## app/routers/mcp.py {#routers-mcp}

### app/routers/mcp.py · BLOCKED
- refers-to: app/routers/mcp.py :: BLOCKED, ALLOW_DELETE
- kind: rationale
- logged: v0.1.0 · 2026-10-07

Deleting photos and folders and opening or creating catalogs stay with the person in the window unless `FORMLIT_MCP_ALLOW_DELETE=1`; everything else an agent does is undoable. After changing the tools, run `./formlit agents sync`.

---

## Files with no entries {#no-entries}

No logged content at v0.1.0 for: `app/__init__.py`, `app/main.py`, `app/core/prefs.py`, `app/engine/events.py`, `app/engine/tasks.py`, `app/engine/query.py`, `app/engine/records.py`, `app/develop/settings.py`, `app/develop/geometry.py`, `app/develop/planes.py`, `app/develop/retouch.py`, `app/develop/colorops.py`, `app/develop/colour.py`, `app/develop/curves.py`, `app/develop/auto.py`, `app/develop/camera_look.py`, `app/develop/lensprofile.py`, `app/develop/fringe.py`, `app/develop/output.py`, `app/ai/models.py`, `app/ai/nets.py`, `app/ai/parts.py`, `app/ai/cull.py`, `app/ai/upright.py`, `app/ai/dng.py`, `app/output/icc.py`, `app/output/web.py`, `app/services/importer.py`, `app/services/metadata.py`, `app/services/xmp_presets.py`, `app/services/xmpwrite.py`, `app/services/xmpembed.py`, `app/services/rename.py`, `app/services/lensdb.py`, `app/services/watch.py`, `app/services/catalog_io.py`, and the remaining routers.
