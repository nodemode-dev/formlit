# Releasing formlit

## Commits

```
feat(develop): point colour with range and smoothness (0.2.0)

What changed and why, in a few lines a reviewer can check against the diff.
```

Every commit has one author and committer, `nodemode-ai <mackin@nodemode.ai>`, and no `Co-Authored-By:` or session lines (owner's rule, 2026-10-22).

Types: feat, fix, perf, refactor, docs, build, ci, chore. Scopes: engine, library, develop, ai, output, map, book, slideshow, print, web, mcp, agents, desktop, ui, docs, release. The version bump is its own last commit: `chore(release): v0.2.0 (0.2.0)`.

A turn on an attached `.git` lands as real commits on the checked-out branch. The zip ships the `.git` connected: `origin` is `git@github.com:nodemode-ai/formlit.git`, the branch tracks `origin/main`, and `origin/main` points at the commit the turn started from, so `git status -sb` shows the branch ahead by the turn's commits. On the repository's first turn there is no remote commit yet; set the remote only.

## Versions

| File | Field |
| --- | --- |
| `frontend/package.json` | `version` |
| `frontend/package-lock.json` | top-level `version` and `packages[""].version` |
| `frontend/src/version.ts` | `export const VERSION` |
| `backend/app/__init__.py` | `__version__` |
| `src-tauri/tauri.conf.json` | `version` |
| `src-tauri/Cargo.toml` | `[package] version` |
| `src-tauri/Cargo.lock` | the `formlit` package's `version` (committed since v0.3.0) |
| `README.md` | the version badge |

Every one by hand. Filenames and tags read `v0.2.0`, never `v0_2_0`.

## Desktop builds

| Step | Command | Output |
| --- | --- | --- |
| Engine sidecar | `./formlit freeze` (PyInstaller, collects llvmlite, numba, onnxruntime, rawpy, cv2) | `src-tauri/binaries/formlit-engine-[target triple]` |
| Frontend | `./formlit build` | `frontend/dist` |
| Bundle | `./formlit desktop build` | `.dmg` and `.app` (macOS), `.msi` and `.exe` (Windows), `.AppImage`, `.deb` (Linux) |
| Release | push a `compile_v0.2.0` branch from the bump commit | formcompiler (`nodemode-ai/formcompiler`) builds all three on their own runners and attaches the bundles to a draft release `formlit-v0.2.0` on its release page; this repository's CI only runs the checks |

The desktop app starts the sidecar with `FORMLIT_DESKTOP=1` and `FORMLIT_PORT=8390` (`ENGINE_PORT` in `src-tauri/src/main.rs`); the engine serves `frontend/dist` and the window talks to `http://127.0.0.1:8390`, the address the Form plugin's bridge uses. When 8390 is already in use the sidecar takes a free port and the window still finds it from the startup line, but the plugin cannot.

## The zips

- `formlit_vX.Y.Z.zip`: the repository root folder `formlit/` with `.git`, without `node_modules`, `backend/venv`, `frontend/dist`, `src-tauri/target`, `__pycache__`, `.DS_Store`.
- `formlit_planning_docs_sidecar_vX.Y.Z.zip`: `DEV_PLAN.md`, `BUILD_NOTES.md`, `TEST_PLAN.md`, `HASHOUT_LOG.md` (the root log).
