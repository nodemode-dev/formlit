---
name: release-keeper
description: "Owns how formlit changes ship: version numbers in six files, Conventional Commits as nodemode-ai, the planning sidecar, desktop builds for macOS, Windows and Linux through the Tauri shell and the PyInstaller sidecar, CI, the Lightroom parity score, and the two-zip hand-back. Load when versioning, committing, building the desktop app, grading parity or handing a turn back."
---

# Release Keeper

## Purpose

Turn finished work into a reviewable release: commits on a connected `.git`, a bumped version, a desktop build that runs, an honest parity score, and the two zips. Hands back the zips, the commit list and the ledger.

## Preconditions

The work itself passed its specialist's gate.

## Procedure

1. Commits: one per coherent change, Conventional Commits `type(scope): summary (x.y.z)` with a body, authored with `git -c user.name=nodemode-ai -c user.email=mackin@nodemode.ai commit`, with no `Co-Authored-By:` or session trailers: one author, nodemode-ai (owner's rule, 2026-10-22). See `references/release.md`.
2. Version: bump `frontend/package.json`, both version fields of the root package in `frontend/package-lock.json`, `frontend/src/version.ts`, `backend/app/__init__.py`, `src-tauri/tauri.conf.json` and `src-tauri/Cargo.toml` with hand edits, together, as the last commit of the series. Patch for fixes, minor for features, major for milestones; always `v` then digits and dots.
3. Desktop: `./formlit freeze` builds the engine sidecar (`formlit-engine`) with PyInstaller into `src-tauri/binaries/` with the target triple suffix; `./formlit desktop build` bundles. Releases are built by formcompiler (`nodemode-dev/formcompiler`): macOS (arm64 and x64), Windows and Linux from a `compile_v*.*.*` branch, drafted as `v*.*.*` on formlit's own Releases page. CI in `.github/workflows/` only runs the checks.
4. Parity: grade `docs/PARITY.md` with `references/parity-rubric.md`; every Full names the file where the trace ends.
5. Hand-back: run `checklists/hand-back.md`, then build `formlit_vX.Y.Z.zip` (the repo with its `.git`, `origin` set to `git@github.com:nodemode-ai/formlit.git`, no `node_modules`, `venv`, `dist` or caches) and `formlit_planning_docs_sidecar_vX.Y.Z.zip` (DEV_PLAN, BUILD_NOTES, TEST_PLAN, the root HASHOUT_LOG).

## Gate

Done when `git status` is clean, the version reads the same in every file, both zips exist with the same version, and the hand-back checklist holds.

## Hands back

The two zip paths, `git log --oneline` for the series, the parity score, and the turn ledger.

## Owned resources

- `references/release.md` commits, versions, desktop builds and the zips
- `references/parity-rubric.md` how the Lightroom parity score is counted
- `checklists/hand-back.md` the last checks before handing a turn back
