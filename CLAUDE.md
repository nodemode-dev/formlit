# formlit

Photo library and raw developer (a Lightroom Classic alternative) in the form family's Studio Dark design: vanilla TypeScript and Vite frontend, Python and FastAPI engine, Tauri 2 shell.

## Repo layout notes

- The engine owns all state. Every action is a command registered with `@command` in `backend/app/engine/cmd_*.py` (or `presets.py`) and dispatched the same way by the interface (`/api/commands/{id}`), the CLI (`./formlit cli`) and the MCP server (`backend/app/routers/mcp.py`). Catalog changes go through `catalog.change(label)`, which records undo and publishes events; the interface patches what changed.
- `shared/controls.json` is the develop control table read by the engine, the interface and the agent references. Its ids are the develop settings' paths.
- Rendering happens in the engine only: `backend/app/develop/render.py` drives the stages, `kernel.py` is the numba finish and `finish.py` its numpy reference; both must agree.
- `frontend/src/styles/` keeps formvis's vendored Studio Dark sheets (`cv-` classes) beside formlit's own `lit-*.css` (`fl-` classes). Colours are tokens, stacking levels are `--z-*` tokens.
- `assets/` is repo art (the README logo and the desktop icon source), not runtime files.
- `backend/formlit_engine.py` is the PyInstaller entry for the desktop sidecar, not a dev server. The desktop shell starts it on port 8390 (a free port only if 8390 is taken) so the Form plugin's bridge can reach `/mcp`. Use `./formlit backend` or `./formlit boot` for development.
- The terminal dock and Claude Code in formlit: `backend/app/engine/terminal.py` (pseudo-terminal sessions), `cmd_terminal.py`, `claude_code.py` (finds `claude`, builds its MCP config with the per-run `agents.INAPP_TOKEN`), `routers/terminal_socket.py` (WebSocket, local origins only), and `frontend/src/ui/terminal-dock.ts`. The dock's Chat tab is `backend/app/engine/cmd_chat.py` (runs `claude -p` with stream-json output and republishes it as `chat.*` events) and `frontend/src/ui/chat-pane.ts`. `terminal.*`, `claudecode.*` and `chat.*` are window-only: `mcp.py` `WINDOW_ONLY` keeps them out of `run_command`; keep it that way.
- `./build_app` is the one-shot desktop build for macOS and Linux; `./formlit desktop build` runs it.
- Planning documents (DEV_PLAN, BUILD_NOTES, TEST_PLAN, the root HASHOUT_LOG) ship in the planning sidecar zip, not in this tree. The living logs `frontend/HASHOUT_LOG.md` and `backend/HASHOUT_LOG.md` are in the tree: read them before editing.

## Skills

- `formlit-harness` · the Develop skill, for changing formlit's code: the engine, the pipeline, the interface, the MCP server and its consent gate, and releases. Route through its `SKILL.md` to the specialist `SUB-SKILL.md`; the photo specialists there are the depth behind `formlit-driving`.
- `formlit-driving` · the Use skill, for working on photos through formlit's MCP tools. The formlit plugin in the Form marketplace carries it; `references/tools.md` lists every tool.

Route code changes through `.claude/skills/formlit-harness/SKILL.md` first, and photo work through `formlit-driving`.

## Working on photos through formlit

When the person wants photos imported, culled, developed, masked, exported, printed or published, use the `formlit` MCP server's tools with the `formlit-driving` skill, not formlit's source code. For a person that is the formlit plugin with the app open; in this repository `.mcp.json` starts it (`./formlit mcp`, which starts the engine if it is not running). The first call asks the person in formlit's window to allow outside agents (Preferences, AI agents); a refusal means stop and say where to change it. After changing the MCP tools in `backend/app/routers/mcp.py`, run `./formlit agents sync` so the skill's tool reference and its `.agents/skills` mirror follow.

## Laws

Single-region hand edits only (no sed, patch, git apply or scripted edits), zero DOM flash or re-render (verify under 4x CPU and slow network), no emoji, no em dash in markdown, no icon-library dependencies, z-index only through tokens, near-zero comments with rationale in the HASHOUT logs, `v*.*.*` versions, Conventional Commits.

## Trademarks, copyright and licences

- Other vendors' product and feature names appear only to name a file format or compatibility (XMP sidecars and DNG files Lightroom and Camera Raw read, Adobe profile names written into XMP by `services/xmp_presets.py`). Never as a formlit command, panel, preset group, preset name or agent tool name, and never as "like Lightroom" or "Lightroom's" in UI text or READMEs. formlit's names: Intelligent Previews, Adaptable preset groups. The notice in `README.md` and `NOTICE.md` lists every vendor mark named.
- Built-in preset ids never change when a group or name is renamed: make them with `presets.builtin_id` and add the old slug to `LEGACY_SLUGS`.
- Preset values come from formlit's own tuning or from published technique articles, never from another vendor's or creator's preset file; descriptions never say a preset copies one. Never bundle Adobe's presets, profiles (.dcp), lens profiles (.lcp) or templates.
- The DNG notice ("This product includes DNG technology under license by Adobe Systems Incorporated.") stays in the About box (Licences and notices), `NOTICE.md` and the README while formlit reads or writes DNG.
- Never copy vendor help or documentation text, and never import or trace vendor icons.
- Every new dependency, binary, model, font or data file gets a row in `NOTICE.md` before it is used. GPL stays outside the distributed bundle, AGPL nowhere, LGPL dynamically linked and replaceable, MPL files unedited; CC BY credited, CC BY-SA only unmodified, CC NC and ND never.
