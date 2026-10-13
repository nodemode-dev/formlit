# HASHOUT_LOG · backend · formlit

Living log of all comment content, explainers, rationale, TODOs and removed code for the engine. Source files stay comment-free; everything they would have said lives here, indexed. Read this first, then edit code surgically.

Current build version: v0.9.1
Last updated: 2026-10-13 · v0.9.1 face-part model requirement, empty masks refused, model pins verified; v0.9.0 match_look, reports on writes, set analysis, save_preset, part masks, a forgiving run_command, 66 more presets; v0.8.0 photo analysis, 134 researched presets, preset previews and search, broken built-in profiles, scaled hues and curves; v0.7.0 the terminal, Claude Code in formlit, the in-app consent token, modern list fields; v0.6.0 outside-agent consent, MCP sessions, the sidecar port; v0.3.4 the preview deadlock, keyword and stack integrity, value ranges; v0.3.3 previews read before answering, search operators; v0.3.2 originals protected, undo moves files, typed parameters, sanitized settings; v0.3.0 look tables, maker notes, DCP baselines, the frozen engine

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
    │   └── prefs.py               JSON preferences in the data folder, including outsideAgents
    ├── engine/
    │   ├── agents.py              outside-agent consent: the gate, status and respond, the in-app token
    │   ├── terminal.py            pseudo-terminal sessions: spawn, scrollback, subscribers, restart
    │   ├── cmd_terminal.py        terminal.* commands for the dock
    │   ├── claude_code.py         finds the claude CLI, builds its MCP config, claudecode.* commands
    │   ├── boot.py                loads command modules, warms the numba kernel
    │   ├── catalog.py             SQLite catalog, Change (undo, events), schema
    │   ├── commands.py            @command registry, dispatch, resolve_ids
    │   ├── events.py              server-sent event bus
    │   ├── tasks.py               background tasks with progress and cancel
    │   ├── query.py               photo queries, smart rules, text filter, facets
    │   ├── records.py             row decoding, summaries and details
    │   ├── presets.py             develop presets, adaptive presets, search, blended previews, import and export
    │   ├── preset_library.py      the 200 researched built-ins with descriptions and tags
    │   ├── cmd_analyze.py         develop.analyze and develop.match: measurement, findings, reference matching
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
    │   ├── camera_styles.py       camera-matching styles per maker and their names
    │   ├── makernotes.py          as-shot picture style from each maker's raw maker notes
    │   ├── dcp_kernel.py          numba evaluation of DCP and look hue/saturation/value tables
    │   ├── pool.py                the one lock around every parallel numba kernel call
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
        └── mcp.py                 MCP server: tools, prompts, sessions, consent gate, window bridge
```

---

## Table of contents

- [formlit_engine.py](#formlit-engine)
- [app/core/config.py](#core-config)
- [app/core/prefs.py](#core-prefs)
- [app/engine/agents.py](#engine-agents)
- [app/engine/terminal.py, cmd_terminal.py, routers/terminal_socket.py](#engine-terminal)
- [app/engine/claude_code.py](#engine-claude-code)
- [app/engine/boot.py](#engine-boot)
- [app/engine/catalog.py](#engine-catalog)
- [app/engine/commands.py](#engine-commands)
- [app/engine/cmd_library.py](#engine-cmd-library)
- [app/engine/cmd_develop.py](#engine-cmd-develop)
- [app/engine/cmd_ai.py](#engine-cmd-ai)
- [app/engine/cmd_output.py](#engine-cmd-output)
- [app/engine/presets.py, preset_library.py](#engine-presets)
- [app/engine/cmd_analyze.py](#engine-analyze)
- [app/develop/settings.py](#develop-settings)
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

### formlit_engine.py · usable_port
- refers-to: formlit_engine.py :: usable_port, main; src-tauri/src/main.rs :: ENGINE_PORT
- kind: rationale
- logged: v0.6.0 · 2026-10-12

The desktop shell used to start the sidecar with `FORMLIT_PORT=0`, a random port that the Form plugin's bridge could never find. It now asks for 8390, formlit's registry port. When something already listens there (a second formlit, a dev engine, another program) the sidecar must still start, so `usable_port` returns 0 and the OS picks a free port, which the shell still reads from the startup line. The probe connects to the port instead of binding it: a bind check reports the port busy while Linux holds it in TIME_WAIT after a quick relaunch, and a relaunch is exactly when 8390 has to be reusable. The plugin cannot reach a fallback engine; the window still can.

### formlit_engine.py · selfcheck
- refers-to: formlit_engine.py :: selfcheck; setup/freeze_backend(.bat) hidden imports
- kind: warning-context
- logged: v0.3.0 · 2026-10-07

The first local Linux build (v0.3.0 work) produced an engine that exited at startup: `app.engine.cmd_output` was missing from the frozen archive. `boot.load_commands` and `publish_sdk` import modules by name, and `--collect-submodules app` collected nothing, because the spec's collection step runs before the backend folder is on PyInstaller's search path (passing `--paths` did not change that). The freeze scripts now name each dynamically imported module with `--hidden-import`, and `--selfcheck` imports every command module and the built-in publish services and exits 1 if any is missing. The freeze scripts run the selfcheck on the fresh binary in `dist-engine` before copying it to `src-tauri/binaries`, and stop if it fails, so a broken engine never replaces a working one there (`desktop_dev` skips freezing when that binary exists). A new command module or publish service must be added to both lists.

### formlit_engine.py · free_port
- refers-to: formlit_engine.py :: free_port, main; app/core/config.py :: engine_port, engine_url
- kind: rationale
- logged: v0.7.0 · 2026-10-12

When 8390 is taken the sidecar used to pass port 0 to uvicorn, so only the shell (reading the startup line) ever learned the real port. The terminal's `FORMLIT_ENGINE_URL` and the Claude Code MCP config need it inside the engine, so `free_port` binds port 0 once, reads the number, and the engine starts on that concrete port and writes it back to `FORMLIT_PORT`. The startup line still carries it, so the shell is unchanged.

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

## app/core/prefs.py {#core-prefs}

### app/core/prefs.py · outsideAgents, CHOICES
- refers-to: app/core/prefs.py :: DEFAULTS, CHOICES, update; app/engine/agents.py :: setting
- kind: rationale
- logged: v0.6.0 · 2026-10-12

Whether outside agents may use formlit is a preference like the others, kept in `preferences.json` in the data folder, so it survives restarts and belongs to the person, not to a catalog. The default is `ask`. `CHOICES` lists the values a text preference may take and `update` refuses anything else, so the file cannot hold a value the gate does not understand; `agents.setting` also reads an unknown stored value as `ask`, the safe reading of a damaged file.

---

## app/engine/agents.py {#engine-agents}

### app/engine/agents.py · require
- refers-to: app/engine/agents.py :: require, WAIT_SECONDS, POLL_SECONDS; app/routers/mcp.py :: call_tool
- kind: rationale
- logged: v0.6.0 · 2026-10-12

Every MCP tool call passes `require` before it runs. `allowed` returns at once and `blocked` raises a refusal that names Preferences, AI agents. `ask` publishes `agents.consent` so the window can show its prompt, then polls the preference every quarter second for up to two minutes; polling is what lets a click in the window, a change in Preferences or `prefs.set` from the CLI all release the call without a separate wake-up channel. The wait is an `await` on `asyncio.sleep`, so the engine keeps serving the window and its other requests; a thread-blocking wait would freeze the very window the person has to answer in. After two minutes the call is refused with a sentence that tells the agent to ask the person to open formlit and not to retry in a loop.

### app/engine/agents.py · _later, Not now
- refers-to: app/engine/agents.py :: respond, _later, require
- kind: rationale
- logged: v0.6.0 · 2026-10-12

Not now must refuse the calls that are waiting without changing the setting, and must not poison calls that arrive afterwards. A counter does that: each waiting call remembers its value when it started, `respond("later")` bumps it, and only calls that started before the bump are refused. The agent's next call asks again, which is what Not now means.

### app/engine/agents.py · one setting for every client, _seen
- refers-to: app/engine/agents.py :: note, status, MAX_SEEN; app/routers/mcp.py :: _caller
- kind: rationale
- logged: v0.6.0 · 2026-10-12

The setting is global, not per client. Names come from the client itself (`clientInfo`, or `x-formlit-agent` from `./formlit mcp`), so they label the prompt and the Seen list and are never an identity to trust or to allow on their own. `_seen` keeps at most 40 names and drops the least recent, so a client that invents a new name for every call cannot grow it.

### app/engine/agents.py · pending, a window that connects late
- refers-to: app/engine/agents.py :: status (pending), _waiting; frontend/src/modules/shared/agent-consent.ts
- kind: explainer
- logged: v0.6.0 · 2026-10-12

The plugin's bridge opens the desktop app when its first call finds no engine, so the window can connect after `agents.consent` was published and the event is gone. `status` therefore lists the calls still waiting, and the window reads it when its event stream says hello or resyncs and shows the prompt for any call that is pending.

### app/engine/agents.py · scope, respond
- refers-to: app/engine/agents.py :: respond; app/routers/mcp.py :: BLOCKED; setup/freeze_backend(.bat) hidden imports
- kind: warning-context
- logged: v0.6.0 · 2026-10-12

The gate covers the MCP surface, which is what the plugin and `./formlit mcp` use. The window, the CLI and the REST commands on the loopback address are the person's own and are not gated, so a program the person runs on the same computer can call them, as the window does. `agents.respond` is the answer to the prompt, so it is in the MCP `BLOCKED` set: an agent that could call it through `run_command` would approve itself. The module is imported by name from `boot.COMMAND_MODULES`, so it is also a `--hidden-import` in both freeze scripts.

---

### app/engine/agents.py · INAPP_TOKEN, the inapp channel
- refers-to: app/engine/agents.py :: INAPP_TOKEN, INAPP_CLIENT, require; app/routers/mcp.py :: _caller; app/engine/claude_code.py :: mcp_config
- kind: rationale
- logged: v0.7.0 · 2026-10-12

Claude Code started from the dock is the person's own action in the window, so asking them again whether "an outside agent" may use formlit would be noise. The engine makes a random token per run and puts it only in the MCP config it hands to the Claude Code it spawns; `_caller` maps a request carrying it in `x-formlit-inapp` to the `inapp` channel and the name Claude Code in formlit. `require` lets `inapp` through under Ask but still refuses it under Block, because Block is the person's standing answer. The token never leaves the engine and its children, and a new one is made at every start, so a leaked config stops working on restart.

---

## app/engine/terminal.py, cmd_terminal.py, routers/terminal_socket.py {#engine-terminal}

### app/engine/terminal.py · Session, _pump, gen
- refers-to: app/engine/terminal.py :: Session, _pump, _spawn, restart, close
- kind: explainer
- logged: v0.7.0 · 2026-10-12

Ported from Format's terminal. Each session owns a pseudo-terminal process (ptyprocess on macOS and Linux, pywinpty on Windows) read by one daemon thread, keeps the last 256 KB as scrollback for a window that attaches late, and fans output to WebSocket subscribers through the event loop with `call_soon_threadsafe`. `gen` counts restarts: a pump thread belonging to an older process returns without touching the session, so the old shell's last bytes and its exit never reach a restarted tab. A session keeps its argv and env, so Restart on a Claude Code tab starts Claude Code again rather than a shell. `start` and `stop` are routers' startup and shutdown hooks; `stop` ends every shell with the engine.

### app/engine/terminal.py · base_env
- refers-to: app/engine/terminal.py :: base_env
- kind: rationale
- logged: v0.7.0 · 2026-10-12

Shells get `FORMLIT_ENGINE_URL` and `FORMLIT_MCP_URL` (the second is what `setup/mcp_stdio.py` reads), so `./formlit mcp` and `./formlit cli` reach this engine even on a fallback port. The repo folder goes on the PATH only in a source checkout; a frozen engine has no repo folder.

### app/engine/cmd_terminal.py · mutates False
- refers-to: app/engine/cmd_terminal.py
- kind: rationale
- logged: v0.7.0 · 2026-10-12

Terminal commands change nothing in the catalog, so they are not mutating; that keeps them out of undo and the revision counter.

### app/routers/terminal_socket.py · origin check
- refers-to: app/routers/terminal_socket.py :: _local, attach
- kind: warning-context
- logged: v0.7.0 · 2026-10-12

Browsers apply no CORS to WebSockets, so any web page could otherwise open `ws://127.0.0.1:8390/api/terminal/{id}` and type into a shell. The socket refuses an Origin that is not loopback or Tauri (close code 4403); clients that send no Origin are local programs. Session ids are 48 random bits and are only listed through `terminal.list`, which outside agents cannot call.

---

## app/engine/claude_code.py {#engine-claude-code}

### app/engine/claude_code.py · cli, _from_login_shell
- refers-to: app/engine/claude_code.py :: cli, CANDIDATES, SYSTEM_PATHS, _from_login_shell
- kind: rationale
- logged: v0.7.0 · 2026-10-12

A desktop app opened from the Finder or a launcher gets a minimal PATH, so `shutil.which` alone misses most Claude Code installs. The search goes `FORMLIT_CLAUDE_BIN`, the PATH, the installer folders Format checks, then asks the person's login shell (`command -v claude`), which sees whatever their profile adds (nvm, volta, brew).

### app/engine/claude_code.py · argv, child_env
- refers-to: app/engine/claude_code.py :: argv, child_env, mcp_config, NOTE
- kind: rationale
- logged: v0.7.0 · 2026-10-12

Claude Code runs interactively in a dock tab, the way the person would run it in a terminal, with `--mcp-config` adding formlit over HTTP (the person's own MCP servers stay), `--allowedTools mcp__formlit` so formlit's tools do not ask per call, and `--append-system-prompt` telling it where it is. On macOS and Linux it is started through the login shell (`shell -l -c "exec claude ..."`) so an npm-installed `claude` finds its node. `CLAUDE*` variables are dropped from its environment except the sign-in ones, as Format does, so a formlit started from inside another Claude Code session does not make the child think it is nested. A prompt from the Ask line becomes the first message when Claude Code starts, or is typed into the running tab followed by Enter.

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

### app/engine/catalog.py · Change.moved, the move operation
- refers-to: app/engine/catalog.py :: Change.moved, Catalog._apply, undo, redo, keyword_id; cmd_library.py :: rename_photos, folder_update, _remove, delete
- kind: rationale
- logged: v0.3.2 · 2026-10-08

Undo used to restore only the catalog: undoing Rename Photos or Rename Folder left the files under their new names, so the photos went missing. A command that moves a file or folder now records `ch.moved(src, dst)` in its change; `_apply` checks every move first (the source must exist and the target must be free), then renames on disk in replay order, so undo and redo move the files with the rows. If a check fails, nothing is applied and the entry goes back on its stack, so the user can fix the clash and try again. Delete from Disk is not undoable (the files are in the system trash, which formlit cannot reach on every platform), so its catalog removal is recorded with `undoable=False` and the confirmation says so. `keyword_id` refuses an empty or non-text keyword, which had created keyword 0 and stray one-letter keywords.

---

## app/engine/commands.py {#engine-commands}

### app/engine/commands.py · dispatch
- refers-to: app/engine/commands.py :: dispatch
- kind: warning-context
- logged: v0.1.0 · 2026-10-07

Unknown parameters are rejected, so a renamed parameter breaks callers loudly. The CLI parses every `key=value` as JSON when it can, so numbers arrive as ints: commands that need strings convert explicitly (`tether.set` calls `str()` on its key and value for this reason).

### app/engine/commands.py · _typed
- refers-to: app/engine/commands.py :: _typed, dispatch
- kind: rationale
- logged: v0.3.2 · 2026-10-08

An engine sweep of 3,100 calls found 90 that ended in a 500 (AttributeError, IndexError, OverflowError and similar) because a parameter of the wrong type reached the command. `dispatch` now checks every declared parameter against its schema type before the call: integers and numbers (numeric strings are converted, NaN and infinity refused, `minimum` and `maximum` enforced), booleans (0 and 1 accepted), strings (numbers converted), objects and arrays (`ids` may also be one id, "selection" or "active"), and `enum`. `None` always passes through, because several commands give it a meaning (a `null` parent is the top level for keywords and collections). The parameters must be an object. After this, the same sweep ends in three 500s, all fixed in their commands.

---

## app/engine/cmd_library.py {#engine-cmd-library}

### app/engine/cmd_library.py · remove
- refers-to: app/engine/cmd_library.py :: photo remove
- kind: rationale
- logged: v0.1.0 · 2026-10-07

Removing the top photo of a stack left the others hidden behind a missing top. Remove now renumbers the stack, or dissolves it when one photo is left.

### app/engine/cmd_library.py · keyword and stack integrity, folder prefixes
- refers-to: app/engine/cmd_library.py :: keyword_update, keyword_merge, _keyword_tree, keyword_delete, stack_group, folder queries; query.py :: like_under, _folder_ids, collection_descendants; tasks.py :: start
- kind: rationale
- logged: v0.3.4 · 2026-10-08

From the command sweep: a keyword could be renamed to blank or to a sibling's name (an IntegrityError), moved under a keyword that does not exist or under itself or a child (which made the recursive queries loop while holding the catalog lock), and merged into a keyword that does not exist or into its own child. All are now refused with a sentence, and every recursive keyword and collection query uses `UNION` rather than `UNION ALL`, so a cycle already in a catalog ends instead of looping. Stacking photos that were already stacked left one-photo stacks behind and accepted duplicates and missing ids; `stack.group` now de-duplicates, keeps only existing photos and tidies the stacks they left. Folder subtree queries matched `_` and `%` in folder names as wildcards (removing a folder `a_b` also removed `aXb`); `like_under` escapes them. A cancelled task now ends as `cancelled`, not `done`, and the interface treats both as finished.

### app/engine/cmd_library.py · collection rules and parents, photo.readMetadata
- refers-to: app/engine/cmd_library.py :: collection_create, collection_update, _collection_descendants; query.py :: validate_rules, compile_rules, RULE_OPS
- kind: rationale
- logged: v0.3.2 · 2026-10-08

One smart collection saved with malformed rules (`{"rules": "zzz"}`) made `library.tree` fail with a 500 until it was deleted, and a rule with an unknown field matched every photo. Rules are now validated when a smart collection is created or edited (known field, known operator, a single value except for between, nesting at most 8 deep), and `compile_rules` skips anything malformed already in a catalog (a broken rule matches nothing rather than everything, and its arguments are discarded so the others stay aligned). A collection cannot be moved into itself or one of its own children, which would loop in the recursive queries, and a new collection's parent and photos must exist.

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

### app/engine/presets.py · user_file
- refers-to: app/engine/presets.py :: user_file, delete, update; output/export.py :: delete_preset
- kind: warning-context
- logged: v0.3.2 · 2026-10-08

A user preset id is `user:` plus a path under the Develop presets folder. `preset.delete` and `preset.update` joined that path without checking it, so `user:/any/file` or `user:../../x` deleted or overwrote any file the engine could reach, including over MCP. `user_file` resolves the id, requires a `.flpreset` inside the presets folder that exists, and answers 404 otherwise. Export presets are deleted only when their id is one `list_presets` returns.

### app/engine/presets.py · merge_masks, adaptive built-ins
- refers-to: app/engine/presets.py :: merge_masks
- kind: explainer
- logged: v0.1.0 · 2026-10-07

Applying a preset with masks merges them into the photo's masks (scaled by the preset amount) rather than replacing them; the nine adaptive built-ins (sky, subject, portrait) carry AI mask shapes that `adapt` computes per photo.

### app/engine/presets.py · profile ids that did not exist
- refers-to: app/engine/presets.py :: BUILTIN (Golden Negative, Faded Print, Chrome Slide, Teal Night, Warm Glow, Sepia Tone, Selenium Tone, Infrared Dream, Matte Fade, Pastel Day, Earth Tones, Vintage Vignette); app/develop/profiles.py :: BY_ID
- kind: warning-context
- logged: v0.8.0 · 2026-10-13

Twelve of the original built-ins named profiles (`fl.film.warm`, `fl.film.faded`, `fl.film.slide`, `fl.film.matte`, `fl.cine.teal`, `fl.cine.golden`, `fl.bw.sepia`, `fl.bw.selenium`, `fl.bw.ir`, `fl.muted.pastel`, `fl.muted.earth`) that `profiles.py` never defined, and an unknown profile id is ignored, so Sepia Tone and Selenium Tone changed nothing at all and the others did only their extra sliders. They are now explicit settings (treatment, B&W mix, grading, the matte curve) or point at profiles that exist. Every built-in is checked against `profiles.BY_ID`, the control ranges and the sanitizer before a change ships.

### app/engine/preset_library.py · where the values come from
- refers-to: app/engine/preset_library.py :: LIBRARY, MATTE, NOTES; .claude/skills/formlit-driving/references/editing-guide.md
- kind: rationale
- logged: v0.8.0 · 2026-10-13

134 presets in Adobe's preset categories (Portrait, Cinematic, Film-Inspired, Vintage, B&W, Seasons, Landscape, Golden Hour, Night and Astro, Travel, Food, Urban Architecture, Concerts, Lifestyle, Moody, Futuristic, Underwater, Curves, Detail, Effects, Color Fixes, and adaptive sky, subject, portrait and landscape). Magnitudes follow the sourced research in the driving skill's editing guide: grading saturation about 7 to 20, the matte curve 0,20 64,55 128,128 192,196 255,235 and the Cinematic Teal and Orange, Moody PNW, Portra and Tri-X values from real exported .xmp files, the low-key portrait recipe, the winter and underwater white-balance advice. They avoid `wb` (an absolute temperature) so they behave the same on raws and JPEGs; warmth comes from grading. `description` and `tags` feed `preset.list` search and the generated `references/presets.md`; `NOTES` describes the original built-ins without editing each entry.

### app/engine/presets.py · blended, preset previews
- refers-to: app/engine/presets.py :: blended, apply, list_presets; app/routers/mcp.py :: _preview; app/engine/cmd_analyze.py :: _settings
- kind: explainer
- logged: v0.8.0 · 2026-10-13

`blended` is the one way a preset meets a photo's settings, shared by `preset.apply`, `get_preview` and `develop.analyze`, so a preview is exactly what applying would store. Adaptive presets preview without their masks until `adapt` has computed the bitmaps for that photo.

---

## app/engine/cmd_analyze.py {#engine-analyze}

### app/engine/cmd_analyze.py · what it measures
- refers-to: app/engine/cmd_analyze.py :: measure, findings, analyze, ZONES, BANDS
- kind: rationale
- logged: v0.8.0 · 2026-10-13

Agents judged exposure from a 1024 px JPEG and guessed. `develop.analyze` renders the photo at 640 px through the same pipeline as previews (with proposed values or a preset when given, unsaved) and returns numbers: Rec.709 luminance on the 8-bit output, its percentiles and spread, the share in Adobe's tonal bands (blacks 0 to 10, shadows 10 to 30, midtones 30 to 70, highlights 70 to 90, whites 90 to 100, from Adobe's Tone Control Adjustment page), clipping per channel and in all channels, saturation, and each colour-mixer band's share, saturation and luminance (hue ranges chosen to match the mixer's eight bands). The cast is measured only on near-neutral midtone pixels, and its finding says what share of the photo that was, because a sunset or a night scene is warm or cool on purpose. Findings are suggestions with control ids and starting values, not edits.

### app/engine/cmd_analyze.py · match, the engine iterates instead of the agent
- refers-to: app/engine/cmd_analyze.py :: match, _step, _distance, _look, LIMITS, MATCH_ROUNDS
- kind: rationale
- logged: v0.9.0 · 2026-10-13

An agent matching a look by hand needed a dozen preview, guess and commit rounds, each a tool call and an image. `develop.match` does the loop in the engine at 384 px: measure the reference once, then up to six rounds of nudging exposure, contrast, highlights, shadows, whites, blacks, saturation, temperature, tint and each shared mixer band toward the reference's statistics, keeping the best round and stopping when a round gets 15 percent worse. Every control is held within `LIMITS` of where the photo started so a strange reference cannot wreck it. White balance starts from `seed_wb`, the photo's effective values, so raws and JPEGs shift the same way. Tint moves with the reference's green-magenta balance (positive is magenta, as in Lightroom; the first version had the sign reversed and pushed a violet reference green). Grading, masks and selective colour are left alone: statistics cannot tell a deliberate selective grade from a global one, so the result says to add those after.

### app/engine/cmd_analyze.py · quick and summary
- refers-to: app/engine/cmd_analyze.py :: quick, summary, analyze (ids); app/routers/mcp.py :: _report, _preview (analyze)
- kind: rationale
- logged: v0.9.0 · 2026-10-13

`quick` is the compact measurement (median, end points, contrast, clipping, saturation, cast, issue names) that writes return with `report` and previews return with `analyze`, so an edit and its check are one call. `get_preview` measures the very render it returns instead of rendering again.

---

## app/develop/settings.py {#develop-settings}

### app/develop/settings.py · scale keeps grading hues, eases curves
- refers-to: app/develop/settings.py :: scale; app/engine/presets.py :: blended
- kind: warning-context
- logged: v0.8.0 · 2026-10-13

A preset applied at an amount scales every number toward its default. Grading hues (`grading.*.hue`) default to 0, so at 50 percent an orange highlight tint (hue 40) became hue 20, a different colour; hues now stay and only saturation, luminance, blending and balance scale, which is what weaker means for a tint. Point curves were copied at full strength whatever the amount; each point now moves toward the diagonal by the amount, so a matte curve at 50 percent lifts the blacks half as far.

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

### app/develop/render.py · the look step
- refers-to: app/develop/render.py :: Stages (base, look_key), _stage_render; profiles.py :: look_of; dcp.py :: apply_camera, apply_look
- kind: rationale
- logged: v0.3.0 · 2026-10-07

The linear stage is cached in two steps. `st.base` holds white balance, a DCP's matrices and hue/saturation map (`dcp.apply_camera`), noise reduction, defringe and lens blur, keyed without Exposure. `st.lin` adds the look step (`dcp.apply_look`): a DCP's look table or an imported Adobe look table with its Amount, keyed by the look and, only when the table depends on value, by Exposure. Dragging Exposure with such a table re-runs only the look step and the planes (0.64 s at 1600 px instead of 2.7 s). Without a look `st.lin` is `st.base`, so nothing is copied. Planes and masks key on the look key, since they read `st.lin`. The look now runs after noise reduction, defringe and lens blur rather than before them; all three are close to colour-neutral, and Camera Raw also denoises before its look.

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

### app/develop/pool.py · LOCK
- refers-to: app/develop/pool.py :: LOCK; kernel.py :: finish, warm; dcp.py :: lookup
- kind: warning-context
- logged: v0.3.0 · 2026-10-07

FastAPI runs each render request on its own worker thread, and the interface sends several at once (the view, the zoomed region, Before, thumbnails). numba's default threading layer on macOS and on Linux without TBB or OpenMP is `workqueue`, which is not thread-safe: when two threads launch `parallel=True` kernels at the same moment it prints "Numba workqueue threading layer is terminating: Concurrent access has been detected" and aborts the whole engine process, which the interface sees as a 502 and every later request fails. Reported from v0.2.0 on macOS. Every call into a parallel kernel (`kernel.run`, `dcp_kernel.table`) now holds `pool.LOCK`. Each kernel already uses every core, so serializing them costs no throughput; decoding, planes and encoding still run concurrently. Checked with 24 overlapping renders (CR2, CR3, DNG and a 10401 px TIFF, view and region sizes): all 200, the engine stays up. A new parallel kernel must take the same lock. `warm` now also compiles the DCP kernel at boot, so its first compile does not hold the lock during a user's first render.

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

Because Camera Look already contains the as-shot style, the other styles are built relative to it: `as_shot` reads the style from the raw through `makernotes.picture_style` (see below), the decoder stores it as `cameraStyle`, and `_delta` subtracts that style's deltas, so choosing the as-shot style gives exactly Camera Look and no style is applied twice. Colour grading hues are absolute angles and are copied, every other key (mixer hues included) is subtracted. A black and white as-shot style is ignored (its JPEG holds no colour to build from). Raws that do not record a style (DNGs from phones, some older cameras) assume Standard, and the Profile Browser says so. `catalogue(keep=...)` keeps a photo's current camera style in the list even when it belongs to another maker's set. `xmp_presets` maps Camera Raw's `CameraProfile` names (including the renamed ones) to these ids and back.

### app/develop/makernotes.py · picture_style
- refers-to: app/develop/makernotes.py :: Tiff, picture_style, _from_tiff, _cr3, _raf, _embedded, _fuji, CANON, NIKON, SONY, FUJI_FILM, FUJI_MONO, PANASONIC, OLYMPUS, PENTAX
- kind: explainer
- logged: v0.3.0 · 2026-10-07

Reads only the first 4 MB. Canon CR2: maker note IFD at the note, offsets from the TIFF header, ProcessingInfo (0x00A0) element 10 (0x81 Standard to 0x88 Fine Detail; 0x87 Auto counts as Standard). Canon CR3: the `CMT3` box is a TIFF of the maker note, offsets from the box data. Nikon: "Nikon\0" plus a TIFF header 10 bytes in; Picture Control Data (0x0023) holds the version in 4 bytes, then name and base, 20 bytes each, at 4 and 24 for versions 01xx and 02xx and at 8 and 28 for 03xx; the base is used, so custom controls map to what they were built from. Sony: Creative Style (0xB020) string, offsets from the file's TIFF header, with or without a "SONY DSC" header. Fujifilm: the RAF's embedded JPEG (offset and length big-endian at 84) holds Exif; the "FUJIFILM" maker note is little-endian with offsets from the note; Film Mode (0x1401), else the monochrome modes in Saturation (0x1003). Panasonic RW2: Exif sits in the embedded JPEG (tag 0x002E); Photo Style (0x0089). Olympus and OM System: "OLYMPUS\0II" or "OM SYSTEM\0\0\0II" headers, offsets from the note, the Camera Settings sub-IFD (0x2020, type IFD) holds Picture Mode (0x0520). Pentax: "PENTAX \0II" (offsets from the note) or "AOC\0" (offsets from the file), Image Tone (0x004F). The make (0x010F) chooses between Canon and Sony, whose notes have no header. Checked against exiftool on 13 raws.

### app/develop/makernotes.py · container_exif
- refers-to: app/develop/makernotes.py :: container_exif, _box; services/metadata.py :: read_exif; engine/cmd_library.py :: photo.readMetadata
- kind: rationale
- logged: v0.3.0 · 2026-10-07

exifread reads no Exif from CR3 (an ISO media container) or RAF, so before v0.3.0 those photos imported with no camera, lens, exposure or capture time (the file date stood in). `read_exif` now falls back to `container_exif` when exifread returns nothing: for a RAF it runs exifread on the embedded JPEG; for a CR3 it runs exifread on each of the `CMT1` (IFD0, keys renamed `Image`), `CMT2` (Exif, keys renamed `EXIF`) and `CMT4` (GPS, keys renamed `GPS` with their GPS tag names) boxes, so `read_exif` sees the same key names it sees from a TIFF raw. Checked against exiftool on R5, R10, X-T3 and X100V files. Photos imported before v0.3.0 are filled in by `photo.readMetadata` (Metadata > Read Metadata from File): when a photo's stored camera is empty it re-reads Exif and sets the camera, lens, exposure and the Exif record; it fills a GPS column only when that column is still empty (anything there was set by hand, since the import read no GPS), and replaces the capture time only when it is still the import's stand-in (the file's modification time as stored in `file_mtime`), so a re-timed or geotagged photo keeps its edits. Photos that already have a camera are left alone.

### app/develop/adobe_profile.py · format
- refers-to: app/develop/adobe_profile.py :: _base85, read, to_srgb
- kind: explainer
- logged: v0.2.0 · 2026-10-07

An Adobe creative profile is an XMP with `crs:RGBTable` naming a `crs:Table_[md5]` attribute. The attribute is Adobe's base85 (alphabet in `ALPHABET`, little-endian 32-bit groups, least significant digit first) over a 4-byte little-endian length and a zlib stream. The stream holds a header (type 1, version 1, dimensions 3, divisions), then uint16 samples stored as deltas from the identity lattice, red outermost and blue innermost, then the primaries, gamma and gamut enums and the amount range as two doubles. Enums follow the DNG SDK: primaries 0 sRGB, 1 Adobe RGB, 2 ProPhoto, 3 Display P3, 4 Rec.2020; gamma 0 linear, 1 sRGB, 2 1.8, 3 2.2, 4 Rec.2020; gamut 0 clip, 1 extend. Layout checked against the MIT-licensed CUBE-to-XMP converter (round trip max error 7.6e-6); no code was copied from either source. Tables in other spaces are resampled into an sRGB lattice through XYZ with Bradford adaptation, then saved as a `.cube` with a JSON sidecar for the name, group and the grayscale flag.

### app/develop/adobe_profile.py · look_table_only
- refers-to: app/develop/adobe_profile.py :: look_table_only (removed v0.3.0)
- kind: todo (resolved v0.3.0)
- logged: v0.2.0 · 2026-10-07

v0.2.0 refused Adobe profiles that hold an HSV look table. Resolved in v0.3.0 by `_look` below.

### app/develop/adobe_profile.py · _block, _look, LOOK_TABLE
- refers-to: app/develop/adobe_profile.py :: _block, _look, read, stem_of; profiles.py :: import_profile_xmp, _look_data, look_of, catalogue
- kind: rationale
- logged: v0.3.0 · 2026-10-07

`crs:LookTable` names a `crs:Table_[md5]` attribute encoded like the RGB table (Adobe base85 over a length and a zlib stream). The stream is read as the DNG SDK's look table: type 0 (the RGB table is type 1), version 1 or 2, hue, saturation and value divisions, then hue shift, saturation scale and value scale as float32 triples with value outermost and saturation innermost (the DCP order), the encoding (0 linear, 1 sRGB) and, in version 2, the minimum and maximum amount as doubles. The layout comes from the SDK's structure as recalled for this build, not from a reference file, so the reader checks the block's exact length against the divisions and refuses anything that does not match, rather than reading a misaligned table. The look is stored in the profile's JSON sidecar (rounded to six decimals); a look-only profile has no `.cube` and is listed from its sidecar. `look_of` scales the deltas by Amount (hue shift times a, saturation and value scales moved from 1 by a) and hands them to the render's look step with the DCP's machinery.

Only a top-level `rdf:Description` whose `crs:PresetType` is `Look` (or absent) counts as a profile (`_profile_desc`, used by `is_profile` and `read`). A Lightroom preset that references a creative profile nests the profile's tables inside `crs:Look/crs:Parameters`; matching any description in the file had imported such a preset as a bare profile and dropped its settings, so it now goes to the preset converter. The compressed block's stated size must lie between 16 bytes and 32 MB and is decompressed with that bound, a look block shorter than its 20-byte header is refused, and malformed XML becomes a ValueError, so every bad file reaches the user as a message from `preset.import`.

### app/develop/profiles.py · _owner, _stem_for, _changed, _meta
- refers-to: app/develop/profiles.py :: _owner, _stem_for, _changed, _meta, _meta_at, import_cube, import_profile_xmp, import_dcp; render.py :: drop_stages
- kind: rationale
- logged: v0.3.0 · 2026-10-07

Imported profiles share one folder and one name space: a plain `.cube`, an Adobe profile (a `.json` sidecar, with a `.cube` when it has an RGB table) and a DCP (a `.dcp` with a `.json` naming it) are told apart by `_owner`. An import replaces only a profile of its own kind with the same name; a name held by another kind gets a numbered stem (`Name_2`), so importing an Adobe look never deletes a user's LUT and a new LUT never inherits an old look. `_changed` runs after every import: it clears the cube, look and DCP caches and drops every cached render stage, because the stage keys name a profile by id, so re-importing a profile under the same name would otherwise keep rendering the old one. `_meta` reads a sidecar through a cache keyed by path and modification time: sidecars can now hold a look table (1.6 MB as JSON for a 90 by 30 by 24 table), and `effective` reads the sidecar on every render.

### app/develop/dcp.py · lookup, dcp_kernel.table
- refers-to: app/develop/dcp.py :: lookup, _apply_table; dcp_kernel.py :: table
- kind: rationale
- logged: v0.3.0 · 2026-10-07

`_apply_table` stays as the numpy reference; `lookup` runs the same arithmetic per pixel in a parallel numba kernel (cached to the data folder like the finish kernel) and falls back to the reference if numba cannot be imported. The two agree within 5e-15 on random tables of every shape (2.5D and 3D, linear and sRGB encoding, any value scale). Both wrap a hue that rounds to exactly 6.0 after the modulo (a tiny negative shift on a red) back to 0; without that the kernel fell through to the magenta sector and the reference raised.

### app/develop/dcp.py · baseline_gain
- refers-to: app/develop/dcp.py :: baseline_gain, tone_knots, MID_GREY; finish.py :: camera_tone
- kind: rationale
- logged: v0.3.0 · 2026-10-07

Camera Raw puts a per-camera BaselineExposure in front of a DCP's tone curve. DNG files carry it; proprietary raws do not (it lives in Adobe's camera tables), so a DCP tone curve on a CR2, NEF, ARW or RAF came out 1.2 to 1.5 EV darker than the camera's JPEG on the test files. When the raw has no baseline of its own, `tone_knots` scales the curve's input so the DCP maps middle grey (0.18) where the fitted camera tone does, within two stops either way. Whether a raw has its own baseline is the decoder's `ownBaseline` flag: true only for a DNG that carries tag 50730. formlit's own linear DNGs (denoise, HDR, panorama, DNG export) write a BaselineExposure that only undoes their storage scale, so `write_linear_dng` carries the source's flag in its private tag and the decoder restores it; a derived DNG then renders a DCP exactly as its source raw does (checked: tone at 0.18 is 0.5649 on a 5D Mark IV CR2 and on its DNG). An earlier test of `sensorGain` against 2^0.35 treated those DNGs, and any DNG with a baseline of exactly 0, the wrong way round. The two-stop clamp is deliberate: the camera tone fit also holds per-photo in-camera brightening (Canon Auto Lighting Optimizer or Highlight Tone Priority, Sony DRO), which is not a camera baseline. On the 5D Mark IV test file the match wanted 2.98 EV, the clamp gave 2 EV and the render sits 0.67 EV under the JPEG; Sony A7 III, Fujifilm X-T3 and Nikon D750 wanted 1.2 to 1.5 EV and land within 0.2 EV. Checked with RawTherapee's camera DCPs (used locally only) on matching raws.

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

### app/output/export.py · is_original, place
- refers-to: app/output/export.py :: is_original, place; publish.py :: _names, _delete; engine/cmd_output.py :: _out_path
- kind: warning-context
- logged: v0.3.2 · 2026-10-08

Export to the photo's own folder with "overwrite" replaced the original with the rendered copy (with its edits baked in, which the catalog then applied a second time). A folder publish collection named `..` wrote its exports over originals one level up, and unpublishing then deleted them. `is_original` asks the catalog whether a path is a photo's original or one of its sidecars (`samefile`, so a case-insensitive file system cannot slip past it); `place` never returns such a path, falling back to a numbered name (or skipping when the setting is skip). Publish names go through `rename.safe`, so `..` becomes a plain folder name, and a local unpublish never deletes an original. Book, slideshow, print and web outputs refuse an explicit output path that is an original.

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

### app/output/slideshow.py and layout.py · value ranges
- refers-to: app/output/slideshow.py :: merged; layout.py :: print_pages grid; core/prefs.py :: update; engine/cmd_library.py :: set_capture_time; query.py :: query limit
- kind: rationale
- logged: v0.3.4 · 2026-10-08

Out-of-range values that produced nonsense are clamped or refused where they enter: slide duration 0.5 to 600 s, fade 0 to 30 s, pan and zoom 0 to 1; print grids 1 to 15 rows and columns with gaps that leave every cell a positive size; preferences that have a default must keep its type (a string for Edit In settings broke Edit In); capture times must parse and shifts stay within 200 years. Schema ranges were added where the meaning is fixed (white balance picker 0 to 1, location latitude, longitude and radius, generative remove 1 to 3 variants, cull threshold 0 to 100), which `dispatch` enforces. `library.query` applies `limit` after collapsing stacks, so it returns as many photos as asked.

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

### app/services/previews.py · _once deadlock
- refers-to: app/services/previews.py :: _once
- kind: warning-context
- logged: v0.3.4 · 2026-10-08

`_once` added its clean-up callback to the future while still holding `_inflight_lock`. When the preview job had already finished by then (a build that fails at once, such as a missing original), `add_done_callback` runs the callback on the spot, in the same thread, and the callback waited for the lock that thread was holding. That thread hung for good and every later preview, thumbnail and develop write that requested a preview queued behind the lock, so the interface stopped getting new previews until the engine restarted. Found with a stack dump of an engine that stalled during the command sweep. The callback is now added after the lock is released.

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

### app/routers/photos.py · _file
- refers-to: app/routers/photos.py :: _file, thumb, preview, full
- kind: warning-context
- logged: v0.3.3 · 2026-10-08

`best_thumb` and `best_preview` may pick an older preview file while the background builder is replacing it; `FileResponse` opened the file only when sending, so a file deleted in between raised "File at path ... does not exist" as a 500 (2 of 73 thumbnail requests during a fast slider drag). `_file` now reads the bytes before answering and returns None if the file is gone, and the endpoints ask for the best file again, up to three times.

### app/engine/query.py · parse_text operators
- refers-to: app/engine/query.py :: parse_text; frontend modules/library/filterbar.ts placeholder
- kind: rationale
- logged: v0.3.3 · 2026-10-08

The search box suggests `rating>=3`, but the parser only accepted `field:` followed by an operator (`rating:>=3`). A field name followed directly by `<`, `>`, `=` or `!` is now read as a rule too; words that are not field names stay free text.

### app/engine/cmd_develop.py · whiteBalancePreset on rendered files
- refers-to: app/engine/cmd_develop.py :: wb_preset; render.py :: WB_PRESETS, effective_wb
- kind: rationale
- logged: v0.3.3 · 2026-10-08

Daylight, Cloudy, Shade, Tungsten, Fluorescent and Flash describe light falling on a sensor and only make sense for raws; the render already ignored them for rendered files, but Quick Develop stored the mode on a JPEG, which Develop then showed as a hidden menu entry. The command now skips rendered files for those presets and reports them as `skipped`, and refuses unknown modes.

### app/routers/photos.py · _bad_render, settings.sanitize, main._unhandled
- refers-to: app/routers/photos.py :: _bad_render, render; develop/settings.py :: sanitize; develop/render.py :: effective; develop/masks.py :: evaluate; engine/cmd_develop.py :: current, store; main.py :: _unhandled
- kind: rationale
- logged: v0.3.2 · 2026-10-08

`develop.update` accepted any patch, so `{"light": {"exposure": "abc"}}`, `{"masks": "nope"}` or a non-list of spot points was stored and every later render of that photo failed with a plain-text 500. `settings.sanitize` now cleans a develop record against the control table and the known structures: numeric controls must be finite numbers and are clamped, sections must be objects, crop rect, angle and flips, orientation, treatment, white balance mode, profile id, curve points, spots, masks, red eye, point colours and the disabled list must have their shapes, and anything else is dropped. It runs when settings are stored, when they are read for editing, and at the start of every render (`render.effective`), so records saved before this release render too. A mask that still fails to evaluate is skipped with a warning instead of failing the render. The render endpoint checks its own body (`long`, `size`, `region`, `quality`, `settings`, `overlay` and the string options) and answers 400 with a sentence. Any other unhandled error now returns JSON with the error instead of a bare 500.

### app/routers/photos.py · render hdr modes
- refers-to: app/routers/photos.py :: render
- kind: explainer
- logged: v0.1.0 · 2026-10-07

`hdr: "display"` returns an AVIF in PQ with `X-HDR-Hist` and `X-HDR-Stops` headers for the HDR histogram; `"sdr"` renders the SDR rendition; `"visualize"` paints the areas above SDR white.

---

## app/routers/mcp.py {#routers-mcp}

### app/routers/mcp.py · _straighten, malformed requests
- refers-to: app/routers/mcp.py :: _straighten, mcp
- kind: rationale
- logged: v0.3.2 · 2026-10-08

The `auto_straighten` tool passed `ids` to `develop.autoStraighten`, which takes one `id` and only measures the angle, so the tool always failed. It now measures each photo, then sets the crop angle and the largest crop of the photo's shape that fits the rotation (`geometry.crop_fit_angle`), as the Crop tool's Auto button does. A request body that is not a JSON-RPC object, `params` that are not an object, and a tool or prompt name that is not text now get JSON-RPC errors instead of a 500.

### app/routers/mcp.py · BLOCKED
- refers-to: app/routers/mcp.py :: BLOCKED, ALLOW_DELETE
- kind: rationale
- logged: v0.1.0 · 2026-10-07

Deleting photos and folders and opening or creating catalogs stay with the person in the window unless `FORMLIT_MCP_ALLOW_DELETE=1`; everything else an agent does is undoable. After changing the tools, run `./formlit agents sync`.

### app/routers/mcp.py · call_tool, the consent gate
- refers-to: app/routers/mcp.py :: call_tool, TOOLS; app/engine/agents.py :: require
- kind: rationale
- logged: v0.6.0 · 2026-10-12

`call_tool` is the one place every `tools/call` goes through, so the gate lives there and a new tool inherits it. A refusal comes back as an ordinary tool result with `isError` set, not as a JSON-RPC error, so the agent reads the sentence and passes it on to the person. `initialize`, `tools/list`, prompts and `ping` stay open so a client can connect and list its tools before the person has decided. `get_agent_access` goes through the gate like every other tool, which keeps the rule free of exceptions.

### app/routers/mcp.py · SESSIONS, _caller
- refers-to: app/routers/mcp.py :: SESSIONS, _open_session, _client_name, _caller; setup/mcp_stdio.py :: forward
- kind: rationale
- logged: v0.6.0 · 2026-10-12

The endpoint stays stateless: no header is needed to call it and a client that sends no `Mcp-Session-Id` works. `initialize` issues one only so later calls can be named in the prompt; `SESSIONS` maps it to the client's name and keeps the newest 64. A call is named from, in order, the `x-formlit-agent` header (sent by `./formlit mcp`, plain ASCII because header values must be), the `_meta` client info of protocol 2026-07-28, then the session. A call with none of them is "an outside agent".

### app/routers/mcp.py · WINDOW_ONLY
- refers-to: app/routers/mcp.py :: WINDOW_ONLY, _run_command
- kind: warning-context
- logged: v0.7.0 · 2026-10-12

`run_command` reaches every engine command, and `terminal.write` is a shell. Every `terminal.*` and `claudecode.*` command is refused there whatever the consent setting or `FORMLIT_MCP_ALLOW_DELETE` say, so allowing an agent to develop photos never also hands it a shell on the person's computer. The window and `./formlit cli` still reach them through `/api/commands`.

### app/routers/mcp.py · _params, a forgiving run_command
- refers-to: app/routers/mcp.py :: _params, _run_command; app/ai/models.py :: ModelMissing
- kind: rationale
- logged: v0.9.0 · 2026-10-13

A real Claude Code run spent four calls on `ai.download` because each try shaped the arguments differently (`args` as a JSON string, flat `model`, `id` for the command). `_params` takes `params` or `args`, an object or a JSON string, plus any extra top-level keys, and `id` names the command when `command` is missing, so the first reasonable shape works. The missing-model refusal names the exact call and tells the agent to fall back to the mixer or a gradient if the install fails, which is what stopped the retry loop.

### app/engine/cmd_ai.py · FACE_PARTS need the face model; coverage on every mask
- refers-to: app/engine/cmd_ai.py :: FACE_PARTS, ai_parts, ai_mask; app/routers/mcp.py :: _add_mask; app/ai/parts.py :: people_parts
- kind: warning-context
- logged: v0.9.1 · 2026-10-13

`people_parts` places face skin, hair, eyebrows, eyes, lips and teeth from face boxes. With the people model installed but not YuNet, `_people` returned no faces and those parts came back with zero coverage; the tool still added the empty mask and reported success, so an agent believed it had masked the hair. `ai_parts` now requires the `faces` model for those parts. `ai_mask` reports coverage like `ai_parts`, and `_add_mask` refuses shapes under 0.2 percent, naming them, and returns each mask's coverage. People parts are rules on top of the person mask and face boxes, not a learned face parser; that is stated in the skill so agents check them with a preview.

### app/ai/models.py · pins and their verification
- refers-to: app/ai/models.py :: MODELS
- kind: rationale
- logged: v0.9.1 · 2026-10-13

Every file is pinned to a revision and a SHA-256, and the downloader discards a file whose hash differs. At v0.9.1 all 15 files were checked: two by downloading through `ai.download`, the rest against the SHA-256 Hugging Face shows at the pinned revision. Real-ESRGAN pointed at `main` and is now pinned to 107475e. Its file is a third-party ONNX conversion (skillsafe-ai) of xinntao's RealESRGAN_x4plus under BSD-3-Clause; the sky model is a mirror (JianyuanWang/skyseg) of xiongzhu666's MIT model. Both are protected by the pinned hash, so a changed upload fails closed instead of loading.

### app/routers/mcp.py · add_ai_mask parts
- refers-to: app/routers/mcp.py :: _add_mask; app/engine/cmd_ai.py :: ai_parts
- kind: explainer
- logged: v0.9.0 · 2026-10-13

The engine could mask people and landscape parts (the adaptive presets used them) but the tool could not ask for them, so agents reached for an object box. `parts` with kind people or landscape goes through `develop.aiParts` and puts every requested part in one mask as added components.

### app/routers/mcp.py · LIST_CACHE, ttlMs and cacheScope
- refers-to: app/routers/mcp.py :: LIST_CACHE, mcp (tools/list, prompts/list)
- kind: warning-context
- logged: v0.7.0 · 2026-10-12

On protocol 2026-07-28 a list result must carry `ttlMs` (a number) and `cacheScope` (public or private). Without them Claude Code 2.1 rejects `tools/list` and `prompts/list`, retries, and keeps the server connected with no tools, which looked like formlit not connecting at all. 60 seconds and private: the list only changes with a new engine build, and it belongs to this computer. The 2025-11-25 replies stay as they were.

---

## Files with no entries {#no-entries}

No logged content at v0.1.0 for: `app/__init__.py`, `app/main.py`, `app/engine/events.py`, `app/engine/tasks.py`, `app/engine/query.py`, `app/engine/records.py`, `app/develop/settings.py`, `app/develop/geometry.py`, `app/develop/planes.py`, `app/develop/retouch.py`, `app/develop/colorops.py`, `app/develop/colour.py`, `app/develop/curves.py`, `app/develop/auto.py`, `app/develop/camera_look.py`, `app/develop/lensprofile.py`, `app/develop/fringe.py`, `app/develop/output.py`, `app/ai/models.py`, `app/ai/nets.py`, `app/ai/parts.py`, `app/ai/cull.py`, `app/ai/upright.py`, `app/ai/dng.py`, `app/output/icc.py`, `app/output/web.py`, `app/services/importer.py`, `app/services/metadata.py`, `app/services/xmp_presets.py`, `app/services/xmpwrite.py`, `app/services/xmpembed.py`, `app/services/rename.py`, `app/services/lensdb.py`, `app/services/watch.py`, `app/services/catalog_io.py`, and the remaining routers.
