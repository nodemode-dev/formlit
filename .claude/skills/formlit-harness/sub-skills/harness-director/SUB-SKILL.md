---
name: harness-director
description: "Entrypoint for formlit work. Classifies a request as using formlit (agent work over MCP), building formlit (code), or both, loads the specialists in order, keeps the ledger and holds the completion gate. Load first for anything broad or multi-step."
---

# Harness Director

## Purpose

Turn a request into an ordered plan across the specialists, keep a ledger of what each step produced, and refuse to call the task done until every step has its evidence. Hands back the ledger and the deliverables.

## Preconditions

None. This is where every unscoped formlit request starts.

## Procedure

1. Classify the request with `references/intake.md`: use (photos change, files are written), build (code changes), or both. A request to "make formlit do X for my photos" when X does not exist is both: build the command first, then use it.
2. For use work, confirm the tools are present: call `get_catalog`. No tools means the MCP server is not connected; follow the setup row in `../catalog-keeper/SUB-SKILL.md` rather than guessing.
3. For build work, read `frontend/HASHOUT_LOG.md`, `backend/HASHOUT_LOG.md` and the planning sidecar (`DEV_PLAN.md`, `BUILD_NOTES.md`) before opening code.
4. Order the specialists. Use work runs catalog-keeper, cull-assistant, develop-artist, output-producer in that order, skipping what the request does not need. Build work runs engine-builder before pipeline-builder and ui-builder, and release-keeper last.
5. Open a ledger row per step: the specialist, what it was asked, what it produced, the evidence. Keep it in the reply for use work and in `BUILD_NOTES.md` for build work.
6. Run `checklists/completion-gate.md` before handing back.

## Gate

Done when every ledger row has evidence (a preview, a written path, a command result, a parity figure or a throttled check) and `checklists/completion-gate.md` passes.

## Hands back

The ledger, the files or photos changed, and for build work the commits and the two zips from release-keeper.

## Owned resources

- `references/intake.md` how to classify a request and what to ask when it is ambiguous
- `checklists/completion-gate.md` the final gate for any formlit task
