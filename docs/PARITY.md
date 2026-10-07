# formlit parity with Lightroom Classic 15

How close formlit v0.3.0 comes to Adobe Lightroom Classic 15, row by row. The method follows the formvis comparison page: every cell is traced in code (the setting or data model, the engine command, the interface that reaches it, and the render or export path that makes it real). README claims are not counted.

- **Full** (1): the Lightroom capability is implemented and wired from the interface through to rendering or export.
- **Partial** (0.5): it exists, but a meaningful part of Lightroom's version is missing or it cannot be reached from the interface.
- **None** (0): absent.
- Platform rows are listed but not scored.

## Score

**57.5 of 58 (99.1%)**: 57 rows Full, 1 row Partial, 0 None.

| Audit | Score | Notes |
| --- | --- | --- |
| First independent audit (v0.1.0) | 48.5 / 58 (83.6%) | 39 Full, 19 Partial |
| Second independent audit, whole table (v0.1.0) | 55.5 / 58 (95.7%) | 53 Full, 5 Partial (16, 29, 42, 46, 54) |
| Focused re-audit of rows 16, 42 and 54 after their fixes (v0.1.0) | 57 / 58 (98.3%) | all three Full |
| Focused audit of rows 29 and 46 (v0.2.0 work in progress) | 57 / 58 | both Partial: four profile gaps and two defects; the classical reflection filter made photos worse and was withdrawn |
| Focused re-audit of row 29 after its fixes (v0.2.0) | 57.5 / 58 (99.1%) | row 29 Full |
| Independent audit of the v0.3.0 changes | 57.5 / 58 (99.1%) | no row changed grade; 11 defects found in the new code (one high: presets with an embedded look imported as profiles) and fixed before release |

Each audit was made by a separate agent that had not seen the work being produced, reading the code only. Paths below are relative to the repo root: **B** is `backend/app`, **F** is `frontend/src`.

## Import and catalog

| # | Row | Grade | Trace | Missing |
| --- | --- | --- | --- | --- |
| 1 | Import dialog (add, copy, move, rename, presets, keywords) | Full | B/services/importer.py `import_files` (add, copy, move, Copy as DNG, second copy, folder and rename templates); B/engine/cmd_library.py `library.import`, `library.scan`; F/modules/library/importer.ts (import presets, develop and metadata presets, keywords, collection, eject) | |
| 2 | Raw coverage | Full | B/services/decode.py `RAW_EXTS`, `_raw_linear` (rawpy on LibRaw, linear Rec.2020); B/develop/camera_look.py; B/ai/dng.py `read_private` | |
| 3 | Other formats | Full | B/services/decode.py `IMAGE_EXTS` (JPEG, TIFF, PNG, PSD, HEIC, AVIF, JPEG XL, WebP), ICC-aware `_pil_linear`, `_tiff16_linear`, `_psd_linear`, `_jxl_linear`; video through `video.trim`, `video.captureFrame`; F/modules/library/video-player.ts | |
| 4 | Folders panel, synchronize, missing files | Full | B/engine/cmd_library.py `folder.synchronize` (import new, remove missing, scan metadata, dry run), `folder.relocate`, `folder.showParent`, `library.findMissing`, `library.checkFiles`, `photo.relink`; F/modules/library/folder-sync.ts, sources.ts (volume headers) | |
| 5 | Previews and smart previews | Full | B/services/previews.py `source` (2560 px float16 smart preview used when the original is offline), `rendered`; `library.buildPreviews`, `library.buildSmartPreviews`, `library.discardSmartPreviews` | |
| 6 | Duplicates, auto import, tethering | Full | B/services/importer.py `quick_hash`, `scan` (suspected duplicates); B/services/watch.py with `autoImport.set`; B/services/tether.py (gphoto2, digiCamControl on Windows) with `tether.start`, `tether.liveView`, `tether.set`, `tether.develop`; F/modules/shared/tether.ts | |
| 7 | XMP sidecars | Full | B/services/xmpwrite.py `write`, `check` (conflicts), automatic writing; B/services/metadata.py `build_xmp`, `parse_xmp`; B/services/xmp_presets.py `to_crs`, `from_crs` (full Camera Raw settings with masks); B/services/xmpembed.py | |

## Library and organizing

| # | Row | Grade | Trace | Missing |
| --- | --- | --- | --- | --- |
| 8 | Ratings, flags, labels | Full | B/engine/cmd_library.py `photo.rate`, `photo.flag`, `photo.label`, `library.labelNames`; F/modules/shared/actions.ts (auto advance) | |
| 9 | Collections, sets, smart collections | Full | `collection.create` (collection, set, smart), `collection.reorder`, `collection.setTarget`, `quick.toggle`; B/engine/query.py `compile_rules` (all, any, none, nested); F/modules/library/smart.ts | |
| 10 | Hierarchical keywords, suggestions, sets, painter | Full | `keyword.create` (hierarchy, synonyms, person), `keyword.merge`, `keyword.purge`, `keyword.suggest`; F/modules/library/keyword-list.ts, keyword-sets.ts, painter.ts; B/output/export.py keyword export with synonyms | |
| 11 | Metadata panel and presets | Full | F/modules/library/inspect.ts `META_VIEWS`; F/modules/library/metadata-presets.ts; `photo.setMeta`, `library.syncMetadata` | |
| 12 | Stacks and virtual copies | Full | `stack.group`, `stack.toggle`, `stack.setTop`, `stack.auto`, `photo.virtualCopy`, `photo.setMasterCopy`; F/modules/shared/actions.ts | |
| 13 | Filter bar | Full | F/modules/library/filterbar.ts (Text, Attribute, Metadata columns, lock, presets); B/engine/query.py `parse_text`, `FACETS` | |
| 14 | Batch rename and capture time | Full | B/services/rename.py `TOKENS`, `expand`; `photo.rename`, `photo.setCaptureTime`; F/modules/shared/photo-dialogs.ts | |
| 15 | People | Full | B/ai/nets.py (YuNet, SFace); `ai.findFaces`, `people.list`, `people.name`, `people.confirm`, `faces.add`; F/modules/library/people.ts, face-regions.ts | |
| 16 | Map module | Full | F/modules/output/map.ts (styles, search, drag to tag, GPX track log, saved locations with Private); `location.save`; B/output/export.py `in_private_location` feeding `export_one`, which Publish also uses | |

## Culling and views

| # | Row | Grade | Trace | Missing |
| --- | --- | --- | --- | --- |
| 17 | Grid | Full | F/ui/grid.ts `ThumbGrid`; F/ui/thumbs.ts badges; B/engine/query.py `SORTS` | |
| 18 | Loupe and navigator | Full | F/ui/viewer.ts; F/modules/library/navigator.ts (Fit, Fill, 1:1, 2:1); B/develop/render.py `render_region` | |
| 19 | Compare and survey | Full | F/modules/library/index.ts compare (linked focus, swap, Make Select) and survey | |
| 20 | Before and after | Full | F/modules/develop/view.ts `Compare`; `develop.before`, `develop.setBefore`, `develop.beforeToAfter` | |
| 21 | Filmstrip, second window, impromptu slideshow | Full | F/ui/filmstrip.ts; F/second.ts, second-modes.ts; `library.impromptuSlideshow` | |
| 22 | Histogram, clipping, soft proofing | Full | B/develop/render.py `histogram`, `proof`; B/develop/finish.py `clipping_overlay`; B/output/icc.py `soft_proof`; `develop.proofCopy` | |

## Develop tone and colour

| # | Row | Grade | Trace | Missing |
| --- | --- | --- | --- | --- |
| 23 | Basic and auto | Full | F/modules/develop/panels.ts; `develop.auto`, `develop.whiteBalancePick`; B/develop/auto.py | |
| 24 | Presence | Full | B/develop/finish.py (texture, clarity, dehaze); B/develop/colorops.py vibrance with skin protection | |
| 25 | Tone curve with targeted adjustment | Full | B/develop/curves.py `curve_luts`, `refine_saturation`; F/modules/develop/curve.ts; tools.ts `TatTool` | |
| 26 | Colour mixer and point colour | Full | B/develop/colorops.py `ColorOps.apply`, `point_k`, `point_weight`; F/modules/develop/tools.ts point colour picker | |
| 27 | Colour grading | Full | B/develop/colorops.py `wheel`, grading with blending and balance; F/modules/develop/wheel.ts | |
| 28 | B&W | Full | colorops.py B&W mix; finish.py `is_bw`; `develop.autoBw` | |
| 29 | Profiles and browser | Full | B/develop/profiles.py `table_of` (looks and B&W looks as 3D tables with Amount 0 to 200), `in_space`, `effective`, `catalogue`, `import_profile_xmp`, `import_dcp`; B/develop/camera_styles.py (camera-matching styles per maker, relative to the as-shot style); B/develop/adobe_profile.py (RGBTable .xmp); B/develop/dcp.py `apply_linear`, `to_prophoto`, `tone_knots` (matrices, both illuminants, look after exposure, tone curve); B/develop/camera_look.py; F/modules/develop/profile-browser.ts (groups, Color and B&W filters, thumbnails, favourites), panels.ts | The camera styles are formlit's approximations on a per-photo fit, since Adobe's camera DCPs cannot be shipped (real DCPs import and apply in full); the as-shot style is read from Canon CR2 only so far, other raws assume Standard and the browser says so; look-table-only .xmp profiles are refused. |
| 30 | Calibration | Full | colorops.py `calibration_matrix`, `calibrate` | |
| 31 | Presets | Full | B/engine/presets.py `preset.apply` (amount, adaptive mask presets), `preset.import` (.xmp, .lrtemplate, .cube, .dcp), `preset.export`; F/modules/develop/left.ts hover preview | |
| 32 | History, snapshots, reset | Full | `develop.history`, `develop.historyRestore`, `snapshot.*`, `develop.reset`; F/modules/develop/left.ts | |
| 33 | Copy, paste, sync, auto sync | Full | `develop.copy`, `develop.paste`, `develop.sync`, `develop.pastePrevious`, `develop.matchExposure`; F/state/develop.ts auto sync | |

## Detail, optics, geometry

| # | Row | Grade | Trace | Missing |
| --- | --- | --- | --- | --- |
| 34 | Sharpening | Full | finish.py sharpen (amount, radius, detail, masking); export output sharpening | |
| 35 | Noise reduction | Full | B/develop/planes.py `denoise` (luminance detail and contrast, colour detail and smoothness) | |
| 36 | Lens corrections | Full | B/develop/geometry.py; B/services/lensdb.py (Lensfun); B/develop/fringe.py; `develop.lensProfile`, `develop.autoCa` | |
| 37 | Upright and transform | Full | B/ai/upright.py; `develop.upright`, `develop.uprightGuides` | |
| 38 | Crop and straighten | Full | F/modules/develop/tools.ts `CropTool` (aspects, seven overlays, Straighten tool); `develop.autoStraighten` | |
| 39 | Vignette and grain | Full | finish.py `vignette_params` (three styles), `grain_noise` | |

## Local and retouching

| # | Row | Grade | Trace | Missing |
| --- | --- | --- | --- | --- |
| 40 | Brush, linear, radial, combine | Full | B/develop/masks.py `shape_alpha`, `rasterize_brush`, `evaluate_one` (add, subtract, intersect, invert); F/modules/develop/masks.ts | |
| 41 | Range masks | Full | masks.py luminance, colour and depth ranges | |
| 42 | Local sliders | Full | shared/controls.json `local`; masks.py `terms`, `apply_curves` (local point curve with R, G, B); render.py `render`, `render_region`; F/modules/develop/masks.ts with `CurveEditor` in local mode | |
| 43 | Spot removal, heal, clone | Full | B/develop/retouch.py `apply_spots`, `auto_source`; tools.ts `SpotTool` with Visualize Spots | |
| 44 | Red eye and pet eye | Full | retouch.py `apply_red_eye`; tools.ts `RedEyeTool` | |

## AI and computational

| # | Row | Grade | Trace | Missing |
| --- | --- | --- | --- | --- |
| 45 | AI masks | Full | B/engine/cmd_ai.py `develop.aiMask`, `develop.aiParts`, `develop.aiPeople`, `adapt`, `ensure_masks`; B/ai/nets.py, parts.py, people.py | |
| 46 | Generative and content-aware remove | Partial | `develop.removeFill` (LaMa, variations, Detect Objects), `develop.removePeople`, `develop.findDust`; retouch.py remove patches | Distraction Removal for reflections is missing; People and Dust exist. A classical reflection filter was built in v0.2.0, measured worse than doing nothing on real composites, and withdrawn before release. |
| 47 | Denoise and super resolution | Full | B/ai/enhance.py; `ai.denoise`, `ai.superResolution`, `ai.rawDetails` | |
| 48 | HDR and panorama merge | Full | B/ai/merge.py `hdr`, `pano`, boundary warp, fill edges; `ai.hdrMerge`, `ai.panoMerge`, `ai.hdrPanoMerge`, Create Stack | |
| 49 | Lens blur | Full | B/develop/lensblur.py; `ai.depth`, `develop.lensBlurFocus`; F/modules/develop/lensblur-tool.ts | |
| 50 | Assisted culling | Full | B/ai/cull.py `scores`, `groups`; `cull.analyze`, `cull.apply` | |

## Output

| # | Row | Grade | Trace | Missing |
| --- | --- | --- | --- | --- |
| 51 | Export | Full | B/output/export.py `export_one`; B/output/encode.py `FORMATS` (JPEG, PNG, TIFF, PSD, JPEG XL, WebP, AVIF, HEIC, DNG), custom ICC; `export.run`, `export.previous` | |
| 52 | Print | Full | B/output/pages.py `write_pdf`, `send_to_printer`, `printer_options`, `printer_dialog`; F/modules/output/print.ts | |
| 53 | Book | Full | B/output/layout.py spreads, wrap covers, spine; `book.export` (PDF, JPEG, Blurb), `book.saveTemplate`; F/modules/output/book.ts | |
| 54 | Slideshow | Full | B/output/slideshow.py `tracks`, `gains`, `still_seconds`, `clips`, `write_video`; `slideshow.layout`, `slideshow.musicIn`; F/modules/output/slideshow.ts `Player` (music, clips, fit) | |
| 55 | Web | Full | B/output/web.py `write_site`, `upload` (FTP, FTPS); F/modules/output/web.ts | |
| 56 | Publish services | Full | B/output/publish.py `run`, `status`, `mark`, `comments`; B/output/publish_sdk.py (plug-ins); B/output/services/webdav.py, s3.py; F/modules/library/publish.ts, comments.ts; F/modules/shared/plugin-manager.ts | |
| 57 | Edit in another app | Full | `photo.editIn` (copy with edits, copy, original, layered PSD), `editIn.addApp`; B/output/encode.py `psd_layers` | |
| 58 | HDR and video output | Full | B/output/gainmap.py; encode.py `encode_hdr` (AVIF, JPEG XL, TIFF); F/modules/develop/hdr.ts; export.py `_video_graded` | |

## Platform (not scored)

| Row | formlit |
| --- | --- |
| Desktop app | Tauri 2 shell with the frozen engine as a sidecar, built for macOS (arm64 and x64), Windows (x64) and Linux (x64) by `.github/workflows/desktop.yml` |
| Web app | The same interface in any modern browser against the local engine (`./formlit boot`) |
| Tablet and phone | Not built |
| Cloud sync | Not built; formlit is local-first by design |

## What the Partial row would need

- **Row 46.** A learned reflection separation model. Single-image gradient methods cannot tell a soft reflection from a soft background: the v0.2.0 attempt (Arvanitopoulos et al., CVPR 2017) moved the result further from the true scene in all 12 audit composites. A permissively licensed learned model exists (DSRNet, ICCV 2023, Apache-2.0), but its weights are published only on Google Drive as PyTorch files; using it means fetching them once, converting to ONNX and hosting the ONNX where formlit's model downloader can pin it. The engine plumbing for it (a whole-frame layer on a 1536 px proxy, warped into every render region) is recorded in the backend HASHOUT log.
