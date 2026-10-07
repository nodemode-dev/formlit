# Changelog

All notable changes to formlit. Versions are `v*.*.*`; each release lists what it added, what it fixed and what is not verified yet.

## v0.2.0 · 2026-10-07

Profiles reach Lightroom parity: graded at 57.5 of 58 rows (`docs/PARITY.md`), with reflection removal the one Partial row. Raw sources are decoded once more on first open (source cache version 5).

### Added

- **Profiles as tables.** Every built-in look, B&W looks included, is a 3D colour table; Amount scales it from 0 to 200 without moving any slider, and it looks the same in sRGB, Display P3, Adobe RGB, ProPhoto and Rec.2020 exports.
- **Camera matching per maker.** Canon, Nikon, Sony, Fujifilm, Panasonic, Olympus and OM, Pentax and Ricoh raws list their maker's picture styles and film simulations, built on Camera Look (the fit to the camera's own JPEG) relative to the style the photo was shot in (read from Canon CR2 so far; other raws assume Standard, and the Profile Browser says which).
- **Adobe creative profiles.** `.xmp` profiles with an RGB table import as tables, resampled from their own primaries and gamma, keeping name, group and the grayscale flag.
- **DCPs in camera space.** An imported `.dcp` applies its forward or colour matrices for its own camera, blends both illuminants by white balance, runs the look table after exposure and uses its tone curve; Develop lists a DCP only for its camera.
- **Profile Browser.** Color and B&W filters and a note about the as-shot style; Amount rests when a profile has nothing to scale; new imports appear without changing photos.

### Fixed

- The Profile Browser's first opening shifted every tile when favourites arrived; it now opens with them loaded.
- The Navigator grew when a slow first decode finished and pushed the left panels down; it reserves the picture's shape.
- Grain was reshaped by the profile table; the table now runs before grain.

### Tried and withdrawn

- A classical reflection-removal slider (gradient-threshold layer separation). An independent audit found it moved photos further from the true scene in all 12 test composites, so it was removed before release. A learned model is the way forward (see `docs/PARITY.md`, row 46).

### Not verified yet

- Real Adobe or camera-maker DCPs and creative profiles (verified with synthetic profiles built to the DNG and RGBTable layouts, and with profiles made by an independent MIT-licensed encoder); the as-shot style for raw formats other than CR2; the items still open from v0.1.0.

## v0.1.0 · 2026-10-07

The first release: a Lightroom Classic alternative in the form family, graded at 57 of 58 parity rows (`docs/PARITY.md`). The version reads 0.1.0 in `frontend/package.json`, `frontend/package-lock.json`, `frontend/src/version.ts`, `backend/app/__init__.py`, `src-tauri/Cargo.toml` and `src-tauri/tauri.conf.json`; tag `v0.1.0` builds the desktop bundles.

### Added

- **Engine.** A FastAPI engine whose catalog (SQLite, WAL, one revision counter) records undo for every command; 217 commands dispatched alike by the interface, the CLI and the MCP server; server-sent events for keyed patching; background tasks with progress.
- **Pipeline.** Geometry first, then white balance, spots and red eye, noise reduction, low-frequency planes and one finish stage, in linear Rec.2020, with a numba kernel and a numpy reference; HDR editing with headroom and an SDR rendition.
- **Import and catalog.** Add, copy, move and Copy as DNG with templates, presets, keywords, a second copy and eject; folder synchronize, volumes, changed files, missing files and relink; smart previews; tethering through gphoto2 and digiCamControl with Live View; auto import; Export as Catalog and Import from Another Catalog; XMP sidecars and embedded XMP with full Camera Raw settings.
- **Library.** Grid, Loupe with Navigator, Compare, Survey, a second window, ratings, flags, labels, collections and smart collections, hierarchical keywords with suggestions, sets and the Painter, metadata views and presets, stacks, virtual copies, batch rename, capture time, the filter bar, People, and the Comments panel for published photos.
- **Develop.** Basic, presence, curves with targeted adjustment, colour mixer, Point Color, grading, B&W, profiles with a browser and .cube and .dcp import, calibration, detail, lens corrections from Lensfun and DNG opcodes, Upright, crop with overlays and Straighten, effects, history, snapshots, settable Before, copy, paste, sync and auto sync, presets with amount and hover preview.
- **Masks and retouching.** Brush, gradients, ranges, AI masks (subject, sky, background, objects, each person, people parts, landscape parts) that follow the edit, 17 local sliders with tint, Point Color and a point curve; heal, clone, generative Remove with variations, Detect Objects, Remove People and Find Dust; red eye and pet eye.
- **AI.** Local models on ONNX Runtime, pinned by SHA-256: segmentation, depth, faces, LaMa, Real-ESRGAN, SAM 2.1; denoise, super resolution, raw details, HDR, panorama and HDR panorama merges, lens blur, assisted culling.
- **Output.** Export in nine formats with custom ICC, HDR (Ultra HDR, AVIF, JPEG XL, TIFF) and graded video; Print with driver settings; Books with spreads, wrap covers and Blurb PDFs; Slideshows with up to ten tracks, audio balance, fit to music and video clips; Web galleries with FTP upload; Publish services for folders, FTP, WebDAV and Nextcloud with comments, S3-compatible storage and Python plug-ins; Edit In; the Map module with private locations.
- **Agents.** The MCP server (49 tools plus `run_command`), `./formlit mcp`, `./formlit agents install|sync`, the `formlit-editing` skill and the `formlit-harness` skill pack.
- **Desktop.** The Tauri 2 shell with the frozen engine as a sidecar and a release matrix for macOS, Linux and Windows.

### Fixed during the release series

- Full-size exports with Lens Blur ran out of memory; the blur pyramid now blends two levels at a time.
- A new photo could inherit another photo's cached previews when SQLite reused a removed photo's id.
- Mask rows painted one sync late.

### Not verified yet

- Desktop bundles (the release workflow has not run), real cameras for tethering (only a simulated gphoto2), real printers, and H.264 playback in webviews without the codec.
