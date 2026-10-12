# Engine

The engine in `backend/` owns every piece of state. The interface, the CLI and the MCP server are clients of the same command registry, so an agent can cull, develop and export with the window closed, and Undo covers agent actions too.

## Commands

A command is a function decorated with `@command("group.name", "Label", params, mutates)` in one of the modules `backend/app/engine/boot.py` loads: `cmd_library.py` (catalog, folders, collections, keywords, stacks, metadata), `cmd_develop.py` (settings, history, snapshots, copy and sync, Before), `presets.py` (develop presets), `cmd_ai.py` (models, AI masks, remove, merges, enhance, faces, culling) and `cmd_output.py` (export, print, book, slideshow, web, publish, map, Edit In, video, tethering). `dispatch` rejects unknown parameters, so a misspelt key fails loudly.

- REST: `GET /api/commands` lists them, `POST /api/commands/{id}` runs one, `POST /api/batch` runs several.
- CLI: `./formlit cli <id> key=value` (values are parsed as JSON when they can be).
- MCP: 50 curated tools in `backend/app/routers/mcp.py`, and `run_command` for any command. Each tool call first passes the AI agents setting (`backend/app/engine/agents.py`, preference `outsideAgents`: ask, allowed or blocked). Deleting photos or folders and opening or creating catalogs are blocked for agents unless `FORMLIT_MCP_ALLOW_DELETE=1`.

## The catalog

`backend/app/engine/catalog.py` wraps SQLite in WAL mode. Every change goes through `with catalog.change(label) as ch:` and `ch.insert`, `ch.update`, `ch.delete` or `ch.set_meta`. The change records its operations for undo and redo, bumps the revision, and publishes `photos.added`, `photos.removed`, `photos.changed` (ids with the fields that changed) and `list.changed` events when it commits. Inserting a photo row clears any cached previews left under that id.

## Events and tasks

`/api/events` streams server-sent events; the interface patches keyed rows from them rather than reloading lists. Long work (imports, exports, merges, publishing) runs through `tasks.start(kind, label, job)`, which reports progress as events and can be cancelled; commands take `wait: true` to block until the result.

## Previews

`backend/app/services/previews.py` keeps thumbnails and previews per photo and develop revision, decoded float16 sources for editing, embedded previews for fast first display, and 2560 px smart previews that stand in for offline originals. Files that change on disk are detected by `library.checkFiles` and their caches dropped.

## Output

`backend/app/output/` writes everything: `export.py` and `encode.py` (formats, ICC, metadata, HDR, video), `layout.py` and `pages.py` (print and book pages, PDF, printers), `slideshow.py`, `web.py`, and `publish.py` with `publish_sdk.py` and the built-in service plug-ins in `services/`.
