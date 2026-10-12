# formlit architecture

## The shape

```
window (frontend/src, vanilla TS + Vite, port 5390)      agents (MCP over HTTP /mcp or ./formlit mcp stdio)
        |  POST /api/commands/{id}, GET /api/photos/*              |  tools/call -> curated tool -> dispatch(id, params)
        v                                                         v
engine (backend/app, FastAPI, port 8390) ---------------- command registry (app/engine/commands.py)
        |                                                         |
        |-- catalog: SQLite WAL, undo and redo (app/engine/catalog.py)
        |-- events: SSE /api/events (photos.added, photos.changed, list.changed, task, render, agent.*)
        |-- tasks: background jobs with progress and cancel (app/engine/tasks.py)
        |-- previews: thumbnails, previews, 1:1 and source caches (app/services/previews.py)
        |-- develop pipeline: decode -> geometry -> linear -> planes -> masks -> finish (app/develop/)
        |-- AI: ONNX models pinned by SHA-256, masks, remove, denoise, merges, faces, culling (app/ai/)
        `-- output: export, layouts, PDF pages, slideshow video, web gallery, publish (app/output/)
desktop (src-tauri, Tauri 2) runs the frozen engine as the sidecar formlit-engine and serves the built window
```

## Commands

Every state change is a command registered with `@command(id, label, params, mutates)` in a module listed in `app/engine/boot.py` `COMMAND_MODULES`: `cmd_library`, `cmd_develop`, `presets`, `cmd_ai`, `cmd_output`. `dispatch(id, params)` validates the parameter names against the function signature, so a parameter missing from the signature is refused, not ignored. A mutating command opens `catalog.change(label)`; every write inside is one undo step and is announced as events after commit. Long work goes through `tasks.start(kind, label, job)` and returns `{"task": id}`; `wait: true` blocks until done.

## The catalog

`photos` holds one row per photo or virtual copy (`master_id`), with `develop` as JSON, `develop_rev` bumped on every develop change, and `meta` as JSON (IPTC fields and `cull` scores). Collections carry a `kind`: `collection`, `set`, `smart`, `quick`, and saved creations `book`, `print`, `slideshow`, `web`, `published` with their `settings` JSON. Faces, people, keywords, locations, publish services and published rows have their own tables. `Change.touch` maps a table to the list name that `list.changed` announces.

## The develop pipeline

Sources decode to linear Rec. 2020 float (`app/services/decode.py`); raws use LibRaw with the camera matrix and a fitted Camera Look tone from the embedded preview. Coordinates for masks, spots and red eye are normalized to the oriented, uncropped frame ("norm"); sizes are fractions of the long side. `render.stage_render` caches geometry, the linear image, low-frequency planes and mask alphas per view slot; `kernel.best_finish` runs the numba kernel when warm, else the numpy reference, and the two agree within 1/255. Region renders for 1:1 add a margin of 16 plus three times the largest plane sigma.

## Outputs

`app/output/export.py` renders at the output size (from the preview source when that is enough, the full source otherwise), sharpens for screen, matte or glossy, watermarks, then `encode.py` writes JPEG, PNG and TIFF at 8 or 16 bits, WebP, AVIF, HEIC with ICC, EXIF and XMP. `layout.py` computes print and book pages in inches; `pages.py` writes them as PDF (reportlab) or JPEG; `slideshow.py` pipes frames to ffmpeg; `web.py` writes a gallery folder; `publish.py` syncs a published collection to a folder or FTP.

## The window

`app.ts` mounts every module once (Library, Develop, Map, Book, Slideshow, Print, Web), registers commands with key combos written `Alt+Shift+Mod+Key`, and builds the menus from command ids. State stores (`state/library.ts`, `state/develop.ts`, `state/catalog.ts`) listen to SSE and patch keyed rows. Output modules share `modules/output/base.ts` (template browser, saved creations, Use selector, form panels); pages render through `modules/output/page.ts` from layouts the engine computes, so the preview and the PDF come from one layout.

## Agents

`app/routers/mcp.py` serves MCP over stateless JSON at `/mcp` (protocol 2026-07-28 and 2025-11-25), checks the Origin is local, and lists curated tools that call `dispatch`. Every `tools/call` first passes `agents.require` (`app/engine/agents.py`) against the `outsideAgents` preference: allowed runs, blocked refuses, ask publishes `agents.consent` for the window's prompt and waits up to 120 seconds. `initialize`, `tools/list` and the window's own REST calls are never gated, and `initialize` issues an `Mcp-Session-Id` that only maps later calls to the client's name. `get_preview` returns a JPEG image content block. `show_in_window` and every tool call publish `agent.show` and `agent.activity` events so the window follows. `setup/mcp_stdio.py` bridges stdio clients (naming the client in `x-formlit-agent`) and starts the engine when needed; `setup/agents.py` registers the server with Claude Code, Codex and Cursor and regenerates `formlit-driving/references/tools.md`. The Form marketplace plugin carries a Node bridge that posts to `http://127.0.0.1:8390/mcp`, so the desktop app starts its sidecar on 8390 and takes a free port only when that one is in use.
