# Changelog

All notable changes to formlit. Versions are `v*.*.*`; each release lists what it added, what it fixed and what is not verified yet.

## v0.1.0 · 2026-10-07

The first release: a Lightroom Classic alternative in the form family, graded at 57 of 58 parity rows (`docs/PARITY.md`).

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
