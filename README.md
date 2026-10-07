<p align="center"><img src="assets/formlit_folder_icon.png" width="112" alt="formlit"></p>
<h1 align="center">formlit</h1>
<p align="center"><b>A photo library and raw developer for the web and the desktop, in the form family's Studio Dark design.</b></p>
<p align="center">
<img src="https://img.shields.io/badge/version-0.2.0-f97316" alt="version 0.2.0">
<img src="https://img.shields.io/badge/node-22-339933" alt="node 22">
<img src="https://img.shields.io/badge/python-3.12-3776AB" alt="python 3.12">
<img src="https://img.shields.io/badge/tauri-2-24C8DB" alt="tauri 2">
<img src="https://img.shields.io/badge/lightroom%20parity-57.5%2F58-f97316" alt="Lightroom parity 57.5 of 58">
<img src="https://img.shields.io/badge/license-Apache--2.0-lightgrey" alt="Apache 2.0 license">
</p>

## What it is

formlit is the form family's alternative to Adobe Lightroom Classic: a catalog of your photos, a non-destructive raw developer, and the Library, Develop, Map, Book, Slideshow, Print and Web modules, local-first, with the same agent harness as formvis so Claude Code, Codex and Cursor can cull, develop and export through tools. It runs in a browser against its local engine, or as a desktop app for macOS, Windows and Linux.

**Stack.** Vanilla TypeScript 7 and Vite 8 · Python 3.12 and FastAPI · Tauri 2. Code size, in lines: about 13,400 of TypeScript, 2,100 of CSS, 15,900 of Python, 130 of Rust (product code, tests excluded; `./formlit counts` prints this, and `./formlit counts --check` verifies it).

**Parity.** 57.5 of 58 Lightroom Classic 15 feature rows (57 Full, 1 Partial: reflection removal), traced in code and graded by independent audits: see [docs/PARITY.md](docs/PARITY.md).

## Highlights

- **Catalog.** SQLite in WAL mode with one revision counter and undo for every change, people and agents alike. Import adds in place, copies, moves or copies as DNG, with rename and folder templates, develop and metadata presets, keywords, a second copy, duplicate detection and eject. Folders show their volumes, synchronize (new, missing, changed on disk, metadata), relocate and find missing files. Smart previews keep offline photos editable. Export as Catalog and Import from Another Catalog move work between catalogs.
- **Formats.** Raw from over a thousand cameras through LibRaw, decoded to linear Rec.2020 with the camera's white balance; JPEG, TIFF (8, 16 and float, ICC aware), PNG, PSD (8 and 16-bit), HEIC, AVIF, WebP and JPEG XL; video with playback, trim and Capture Frame.
- **Library.** Grid, Loupe with a Navigator, Compare with linked zoom, Survey, and a second window (Grid, Loupe normal, live or locked, Compare, Survey, Slideshow). Ratings, flags and colour labels with auto advance; collections, sets, smart collections with nested rules; hierarchical keywords with synonyms, suggestions, keyword sets and the Painter; metadata views and presets; stacks, virtual copies, batch rename and capture time; the filter bar with Text, Attribute and Metadata columns; faces found, clustered and named in People.
- **Develop.** One pipeline rendered by the engine (numba kernel, numpy reference) for the screen, 1:1 regions and exports alike: white balance, Basic with Auto, presence, parametric and point curves with targeted adjustment, colour mixer and Point Color, colour grading, B&W mix, profiles with a browser (looks and B&W looks as 3D tables with Amount, camera-matching styles per maker, Adobe creative profile .xmp, .cube and .dcp import, DCPs applied in camera space), calibration, sharpening, noise reduction, lens profiles from Lensfun and DNG opcodes, chromatic aberration and defringe, Upright with guides, crop with seven overlays and a Straighten tool, vignette and grain, history, snapshots, a settable Before, copy, paste, sync and auto sync, presets with amount, hover preview and import of .xmp and .lrtemplate.
- **Masks and retouching.** Brush, linear and radial gradients, colour, luminance and depth ranges, combined with add, subtract and intersect; AI masks for subject, sky, background, objects, people (each person on their own), people parts and landscape parts, recomputed for every photo a mask reaches by sync, paste, preset or virtual copy; 17 local sliders, a local tint, local Point Color and a local point curve with R, G and B. Heal, clone and generative Remove (LaMa) with variations and Detect Objects, Remove People, Find Dust and Visualize Spots; red eye and pet eye.
- **AI and merges.** Denoise, Super Resolution and Raw Details; HDR, panorama and HDR panorama merges with deghosting, boundary warp, fill edges and Create Stack; Lens Blur from a depth map with five bokeh shapes; assisted culling by sharpness, exposure, eyes open and face focus. Every model runs locally on ONNX Runtime, downloads on first use, and is pinned to a SHA-256.
- **HDR.** An HDR editing mode with headroom, Visualize HDR, an SDR rendition and an HDR histogram, previewed as PQ on HDR displays; Ultra HDR JPEG with a gain map, HDR AVIF, JPEG XL and float TIFF on export.
- **Tethering.** gphoto2 on macOS and Linux, digiCamControl on Windows: Live View, camera settings, a develop setting applied as photos arrive (including Same as Previous), and auto import from a watched folder.
- **Output.** Export to JPEG, PNG, TIFF, PSD (layered with Open as Layers), JPEG XL, WebP, AVIF, HEIC or DNG (the original raw for DNG sources), with sizing, output sharpening, custom ICC profiles, metadata choices (private map locations stay private), watermarks, naming, presets and post-processing. Print with grid, picture package and custom layouts, printer profiles, driver Page Setup and Printer Settings. Books with spreads, wrap covers with a spine, custom pages and Blurb-ready PDFs. Slideshows with music (up to ten tracks), audio balance, fit to music and video clips, exported as H.264. Web galleries with FTP upload. Publish services for folders, FTP, WebDAV and Nextcloud (with comments), S3-compatible storage and Python plug-ins (File > Plug-in Manager). Edit In any application.
- **Map.** OpenStreetMap tiles with Hybrid, Satellite, Light and Dark styles, search, drag to geotag, GPX track logs, saved and private locations, reverse geocoding.
- **XMP.** Sidecars and embedded XMP carry the full Camera Raw settings (curves, profiles, lens profiles, masks, spots, red eye), written automatically and checked for changes made by other applications.
- **Agents.** The MCP server gives Claude Code, Codex and Cursor 49 curated tools over the engine's 217 commands (and `run_command` for the rest); `./formlit agents install` sets them up, and the `formlit-editing` skill teaches them the workflow. The `formlit-harness` skill pack guides agents that develop formlit's own code.
- **Zero-flash interface.** The shell mounts once and every list is patched by key; each interface change is verified in a browser throttled to 4x CPU and a slow network.

## Quick Start

Requirements: Node 20.19 or newer (22 recommended), Python 3.12 or newer, git. ffmpeg on the PATH for video export, slideshows and graded video. The desktop build also needs Rust stable and the Tauri 2 system packages for your OS.

### macOS and Linux

```bash
git clone https://github.com/nodemode-ai/formlit.git
cd formlit
./formlit install
./formlit boot
```

### Windows

```bat
git clone https://github.com/nodemode-ai/formlit.git
cd formlit
formlit.bat install
formlit.bat boot
```

`./formlit install` installs the engine with ONNX Runtime and the frontend; `--lite` skips the AI extra. `./formlit install-desktop`, then `./formlit desktop dev` or `./formlit desktop build`, for the desktop app. `./formlit help` lists every command, and `./formlit doctor` checks the toolchain and ports.

| Service | URL | Notes |
| --- | --- | --- |
| Frontend (dev) | http://localhost:5390 | Vite, bound to localhost only, strict port |
| Engine | http://127.0.0.1:8390 | FastAPI; API under `/api`, MCP at `/mcp`; serves the built app in `./formlit serve` |
| Preview | http://localhost:5391 | `vite preview` of the production build |
| Desktop engine | random loopback port | picked by the OS, read by the Tauri shell from the startup line |

## Configuration

The engine reads `backend/.env`, which is never committed; `backend/.env.example` is the template.

| Variable | Purpose |
| --- | --- |
| `FORMLIT_HOST`, `FORMLIT_PORT` | Engine bind address and port; port `0` picks a free one (desktop) |
| `FORMLIT_DATA_DIR` | Data root (default `~/Formlit`): catalog, presets, profiles, plug-ins, models, exports |
| `FORMLIT_LIBRARY_DIR` | The folder browser's starting folder, and where photos uploaded from a browser are saved (default `~/Pictures/formlit`) |
| `FORMLIT_CATALOG` | Catalog file to open instead of the last one used |
| `FORMLIT_CORS_ORIGINS` | Allowed browser origins for the dev frontend |
| `FORMLIT_DIST` | Built frontend folder the engine serves |
| `FORMLIT_WORKERS` | Preview and export worker threads |
| `FORMLIT_MODELS_DIR` | Where local AI models are kept |
| `FORMLIT_GPHOTO2`, `FORMLIT_DIGICAM` | Paths to the tethering programs when they are not on the PATH |
| `FORMLIT_MCP_ALLOW_DELETE` | `1` lets agents delete photos and folders and open or create catalogs, which otherwise only a person can do in the window |

## Architecture

```text
formlit/
├── formlit, formlit.bat            root dispatcher: install, boot, build, serve, desktop, mcp, agents, cli, doctor, counts
├── formlit_oc_install(.bat)        one-command install
├── setup/                          one script per task, each with a .bat twin; lib.sh holds shared helpers
├── shared/controls.json            the develop control table read by the engine, the interface and the agents
├── backend/                        FastAPI engine
│   ├── app/engine/                 catalog, command registry, events, tasks, queries, cmd_library, cmd_develop, cmd_ai, cmd_output
│   ├── app/develop/                the pipeline: geometry, planes, finish, numba kernel, masks, retouch, profiles, lens blur
│   ├── app/ai/                     local models: segmentation, depth, faces, cull, merge, enhance, upright
│   ├── app/output/                 export, encode, print and book pages, slideshow, web, publish and its plug-ins
│   ├── app/services/               decode, import, previews, metadata and XMP, tether, watch, catalog import and export
│   ├── app/routers/                REST, events, photos, files, output and the MCP endpoint
│   └── formlit_engine.py           PyInstaller entry for the desktop sidecar
├── frontend/                       Vite app, vanilla TypeScript
│   ├── src/modules/                library, develop, output (map, book, slideshow, print, web), shared commands and dialogs
│   ├── src/state/                  catalog, library selection and develop session state
│   ├── src/ui/                     shell, grid, viewer, panels, menus, dialogs, icons, themes, DOM helpers
│   └── src/styles/                 formvis Studio Dark tokens and sheets, plus formlit's lit- sheets
├── src-tauri/                      Tauri 2 shell: splash, sidecar spawn, port handshake, updater
├── docs/                           PARITY.md and the publish plug-in example
├── .docs/                          BRANCHING.md and the wiki source
├── .github/workflows/              ci, wiki publish, desktop release matrix
├── .claude/skills/                 formlit-harness (developing formlit) and formlit-editing (driving it)
└── .agents/, .codex/, .cursor/     the same MCP server and editing skill for Codex and Cursor
```

## Agents

`.mcp.json`, `.codex/config.toml` and `.cursor/mcp.json` run `./formlit mcp`, which starts the engine when it is not running. From any other folder, `./formlit agents install` registers formlit with Claude Code, Codex and Cursor for your user account. After changing the tools in `backend/app/routers/mcp.py`, run `./formlit agents sync` so the editing skill's tool reference and its mirror follow.

## Development

Branch model: `main` plus short-lived work branches, see `.docs/BRANCHING.md`. Docs live in `.docs/wiki/` and publish to the GitHub wiki on merge. Contributions follow the dev-rules laws: single-region hand edits, zero DOM flash or re-render, no emoji, no em dash, no icon-library dependencies, `v*.*.*` versions, Conventional Commits. Start at `.claude/skills/formlit-harness/SKILL.md`, and read `frontend/HASHOUT_LOG.md` and `backend/HASHOUT_LOG.md` before editing.

## Status

Release history: `CHANGELOG.md`. What is not verified yet:

- **Desktop app.** The Tauri shell follows formvis's sidecar template; the desktop workflow has not run, so treat desktop bundles as untested until the first `desktop.yml` run passes.
- **Hardware.** Tethering was exercised against a simulated gphoto2; the digiCamControl adapter on Windows and real cameras are untested. Printing to a real printer and its driver dialogs are untested.
- **Video in the browser.** Playback of H.264 clips depends on the webview; the open-source Chromium used for testing plays WebM but not H.264.
- **Approximations.** Denoise is non-local means, people and landscape parts and eye detection are heuristic, Blurb's spine width is estimated from the page count, and DNG export of non-DNG raws writes uncompressed data. Camera-matching styles are formlit's own approximations built on a per-photo fit to the camera's JPEG; the style a raw was shot in is read from Canon CR2 only so far.
- **Profiles.** DCP and Adobe creative profile support was verified with synthetic profiles built to the published layouts, not yet with Adobe-made or camera-maker files; Adobe profiles that hold only an HSV look table are refused.
- **Reflections.** Distraction Removal has People and Dust; reflection removal waits for a learned model (`docs/PARITY.md`, row 46).

## Contributors

- **nodemode-ai** · owner and build

## Licensing

Apache License 2.0. Copyright 2026 nodemode-ai. See `LICENSE`, and `NOTICE.md` for the open-source code, models and data formlit uses and their licenses.
