# Releasing formlit

## Commits

```
feat(develop): point colour with range and smoothness (0.2.0)

What changed and why, in a few lines a reviewer can check against the diff.

Co-Authored-By: [as the session states]
Claude-Session: [as the session states]
```

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

Every one by hand. Filenames and tags read `v0.2.0`, never `v0_2_0`.

## Desktop builds

| Step | Command | Output |
| --- | --- | --- |
| Engine sidecar | `./formlit freeze` (PyInstaller, collects llvmlite, numba, onnxruntime, rawpy, cv2) | `src-tauri/binaries/formlit-engine-[target triple]` |
| Frontend | `./formlit build` | `frontend/dist` |
| Bundle | `./formlit desktop build` | `.dmg` and `.app` (macOS), `.msi` and `.exe` (Windows), `.AppImage`, `.deb` (Linux) |
| CI | tag `v0.2.0` and push | `.github/workflows/desktop.yml` builds all three on their own runners and attaches the bundles to a draft release |

The desktop app starts the sidecar with `FORMLIT_DESKTOP=1`; the engine serves `frontend/dist` and the window talks to `http://127.0.0.1:8390`.

## The zips

- `formlit_vX.Y.Z.zip`: the repository root folder `formlit/` with `.git`, without `node_modules`, `backend/venv`, `frontend/dist`, `src-tauri/target`, `__pycache__`, `.DS_Store`.
- `formlit_planning_docs_sidecar_vX.Y.Z.zip`: `DEV_PLAN.md`, `BUILD_NOTES.md`, `TEST_PLAN.md`, `HASHOUT_LOG.md` (the root log).
