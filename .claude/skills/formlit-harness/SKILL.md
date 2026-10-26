---
name: formlit-harness
description: "Changes and ships formlit's own code, the local Lightroom alternative for photos and raws: the FastAPI engine and its commands, the develop pipeline and numba kernel, the MCP tools and the outside-agent consent gate, the Tauri shell and sidecar, the window's Library, Develop, Map, Book, Slideshow, Print and Web modules (a flash or a layout jump), the catalog schema, versioning, desktop builds and the hand-back. Use whenever a task edits formlit's source, docs, logs or skills: backend/app, frontend/src, src-tauri, setup. Trigger on a formlit command, an MCP tool, the sidecar, a release or a bug in the window. Not for using formlit on photos, such as importing, culling, developing or exporting (that is formlit-driving), not for layered compositing or pixel retouching (formvis) and not for video editing (formcut)."
---

# formlit harness

formlit is a photo library and raw developer in the form family: an engine that owns the catalog, the develop pipeline and every output, a window that renders the engine's state, and an MCP server that hands the same commands to agents. This pack is for changing formlit; using it on photos is `formlit-driving`, the skill the formlit plugin carries, and the photo specialists below stay here as the depth behind it. Both kinds of work fail in the same way: they reach past the engine. An agent that edits settings blind, without looking at a preview, ships a photo nobody checked; a developer who puts logic in the window instead of a command ships a feature agents cannot use and undo cannot reverse. Every specialist here holds the line that the engine is the source of truth and every claim is checked against what it renders.

## How this pack is laid out

```
formlit-harness/
  SKILL.md                         this file: premise, routing, laws
  EVALS.json                       evaluations and trigger tests
  references/
    architecture.md                the system map: engine, commands, catalog, events, pipeline, outputs, window, MCP
    tool-map.md                    each MCP tool, the command behind it and the file that implements it
  sub-skills/
    harness-director/              intake: which half (use or build), which specialists, the ledger, the gate
    catalog-keeper/                import, folders, collections, keywords, metadata, people, locations
    cull-assistant/                scoring, grouping, picks and rejects, the review pass
    develop-artist/                develop values, masks, presets, sync, enhance and merges
    output-producer/               export, print, book, slideshow, web gallery, publish, Edit In
    engine-builder/                the FastAPI engine: commands, catalog, tasks, events, MCP tools
    pipeline-builder/              the develop pipeline: numpy reference, numba kernel, stage cache, geometry
    ui-builder/                    the window: modules, panels, forms, output base, design tokens, zero flash
    release-keeper/                versions, commits, desktop builds, parity grading, the two-zip hand-back
```

A path named inside a `SUB-SKILL.md` resolves against that specialist's own folder, so `references/[file].md` is `sub-skills/[specialist]/references/[file].md`. A sibling resolves under `sub-skills/[sibling]/SUB-SKILL.md`. Pack-wide references resolve from the pack root.

## Routing

Start with `sub-skills/harness-director/SUB-SKILL.md` for anything broad. Load a specialist directly only for a narrow question. A plain request to use formlit on photos goes to `formlit-driving`; the photo specialists load here only to change or check the feature behind them.

| The request is about | Load |
| --- | --- |
| Anything unscoped, several steps, or both using and changing formlit | `harness-director` |
| Importing, folders, collections, keywords, IPTC metadata, people, GPS and saved locations | `catalog-keeper` |
| Choosing the keepers from a shoot: picks, rejects, ratings, near-duplicates, sharpness | `cull-assistant` |
| How photos look: white balance, tone, color, detail, masks, presets, sync, denoise, HDR, panorama, upright | `develop-artist` |
| Files and pages out: export presets, print layouts, books, slideshows, web galleries, publish services, Edit In | `output-producer` |
| Engine code: a new or changed command, the catalog schema, tasks, events, routers, the MCP tool list, the outside-agent consent gate, `./formlit agents sync` | `engine-builder` |
| Render code: `backend/app/develop/`, the numba kernel, region renders, camera look, masks evaluation, lens blur | `pipeline-builder` |
| Window code: `frontend/src/`, a module, a panel, a dialog, the form helper, styles, icons, a flash or a layout jump | `ui-builder` |
| Versions, commits, the desktop app, the sidecar, CI, the parity score, the hand-back zips | `release-keeper` |

## Laws for every specialist

1. The engine is the source of truth. State changes go through a command in `backend/app/engine/`; the window and the MCP server only dispatch. A feature that exists only in the window is unfinished.
2. Look before and after. Agents verify a develop or output change with `get_preview` or by opening the written file; developers verify a UI change in a browser under CPU and network throttling.
3. SEDO: existing files change by single-region hand edits. No sed, no patch files, no codemods, no rewrites.
4. Zero DOM flash: mount once, patch in place, reserve space before content arrives.
5. Colours and z-index come from tokens; icons are inline currentColor SVG from `frontend/src/ui/icons-lit.ts`; no icon libraries.
6. No emoji anywhere and no U+2014 em dash in markdown (use the interpunct). Near-zero comments; context goes in `frontend/HASHOUT_LOG.md` or `backend/HASHOUT_LOG.md`.
7. Tests live in `backend/tests/` and run in CI; write only the tests FAMILY_TEST_PLAN (formai_dev sidecar) or its successor names, and list what is covered in the planning sidecar's `TEST_PLAN.md`.
8. Destructive actions stay with the person: deleting files from disk and switching catalogs are refused over MCP.
9. Outside agents are asked once: every MCP tool call passes `agents.require` in `call_tool` against the `outsideAgents` setting (ask, allowed or blocked). Only the handshake, listing tools and prompts, and the window's own REST calls are open. A new tool gets no exemption, and `agents.respond` stays in `BLOCKED` so an agent cannot answer its own prompt.

## Verification bar

A task is finished only with its evidence: for agent work, the preview or the written path; for engine work, the command run through `./formlit cli` and its result; for a change to the MCP tools or the consent gate, a call through `/mcp` or `setup/mcp_stdio.py` with `outsideAgents` allowed, ask and blocked; for pipeline work, the parity numbers; for UI work, the throttled check; for a release, `git status` clean, the version bumped in all six files and both zips built.
