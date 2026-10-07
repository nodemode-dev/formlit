# formlit

Photo library and raw developer (a Lightroom Classic alternative) in the form family's Studio Dark design: vanilla TypeScript and Vite frontend, Python and FastAPI engine, Tauri 2 shell.

## Repo layout notes

- The engine owns all state. Every action is a command registered with `@command` in `backend/app/engine/cmd_*.py` (or `presets.py`) and dispatched the same way by the interface (`/api/commands/{id}`), the CLI (`./formlit cli`) and the MCP server (`backend/app/routers/mcp.py`). Catalog changes go through `catalog.change(label)`, which records undo and publishes events; the interface patches what changed.
- `shared/controls.json` is the develop control table read by the engine, the interface and the agent references. Its ids are the develop settings' paths.
- Rendering happens in the engine only: `backend/app/develop/render.py` drives the stages, `kernel.py` is the numba finish and `finish.py` its numpy reference; both must agree.
- `frontend/src/styles/` keeps formvis's vendored Studio Dark sheets (`cv-` classes) beside formlit's own `lit-*.css` (`fl-` classes). Colours are tokens, stacking levels are `--z-*` tokens.
- `assets/` is repo art (the README logo and the desktop icon source), not runtime files.
- `backend/formlit_engine.py` is the PyInstaller entry for the desktop sidecar, not a dev server. Use `./formlit backend` or `./formlit boot` for development.
- Planning documents (DEV_PLAN, BUILD_NOTES, TEST_PLAN, the root HASHOUT_LOG) ship in the planning sidecar zip, not in this tree. The living logs `frontend/HASHOUT_LOG.md` and `backend/HASHOUT_LOG.md` are in the tree: read them before editing.

## Skills

- `formlit-harness` · the orchestrator for all formlit work, for agents driving formlit and agents developing it: catalog and culling, develop, output, the engine, the pipeline, the interface and releases. Route through its `SKILL.md` to the specialist `SUB-SKILL.md`.
- `formlit-editing` · how to drive formlit through its MCP tools; `references/tools.md` lists every tool.

Always route work through `.claude/skills/formlit-harness/SKILL.md` first.

## Working on photos through formlit

When the person wants photos imported, culled, developed, masked, exported, printed or published, use the `formlit` MCP server's tools with the `formlit-editing` skill, not formlit's source code. `.mcp.json` starts it (`./formlit mcp`, which starts the engine if it is not running). After changing the MCP tools in `backend/app/routers/mcp.py`, run `./formlit agents sync` so the skill's tool reference and its `.agents/skills` mirror follow.

## Laws

Single-region hand edits only (no sed, patch, git apply or scripted edits), zero DOM flash or re-render (verify under 4x CPU and slow network), no emoji, no em dash in markdown, no icon-library dependencies, z-index only through tokens, near-zero comments with rationale in the HASHOUT logs, `v*.*.*` versions, Conventional Commits.
