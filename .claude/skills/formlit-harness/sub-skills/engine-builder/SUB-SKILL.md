---
name: engine-builder
description: "Owns formlit's FastAPI engine code under backend/app: the command registry, catalog schema and undo, query sources and filters, tasks, SSE events, routers, AI and output services, and the MCP tool list with ./formlit agents sync. Load when adding or changing a command, a table, an endpoint, an MCP tool, or when a command returns the wrong data."
---

# Engine Builder

## Purpose

Change what formlit can do, in the one place every client reaches: a command. Hands back the command (or change), its proof through `./formlit cli`, the MCP tool when agents need it, and the HASHOUT entry.

## Preconditions

`backend/HASHOUT_LOG.md` read. The engine running (`./formlit backend` or `./formlit boot`); uvicorn reloads on save.

## Procedure

1. Find the owner module with `../../references/tool-map.md`: library and photo commands in `cmd_library.py`, develop in `cmd_develop.py`, presets in `presets.py`, models, masks needing nets and culling in `cmd_ai.py`, every output and location command in `cmd_output.py`. A new module is added to `COMMAND_MODULES` in `app/engine/boot.py`.
2. Write the command with `references/adding-a-command.md`: the decorator's params mirror the signature, mutations happen inside `catalog.change(label)`, long work goes through `tasks.start`, errors raise `CommandError` with a sentence that says what to do.
3. Schema changes: add columns in the `SCHEMA` string with `IF NOT EXISTS` semantics or a migration in `Catalog.__init__`; register JSON columns in `JSON_FIELDS`; map new tables to a list name in `Change.touch` so `list.changed` fires.
4. Window reachability: the window calls `ctx.api.cmd(id, params)`; nothing more is needed on the engine side.
5. Agent reachability: a command an agent would plausibly need gets a curated tool in `app/routers/mcp.py` (a `_tool(...)` with a description that says what it does and returns, and a handler calling `_cmd`). Run `./formlit agents sync` to regenerate `.claude/skills/formlit-editing/references/tools.md` and its mirror.
6. Prove it: `./formlit cli [command-id] key=value ...` and read the result; for mutating commands also `./formlit cli edit.undo` and confirm the state returned.
7. Record decisions in `backend/HASHOUT_LOG.md`; no comments in code.
8. Run `checklists/command-gate.md`.

## Gate

Done when the command runs through the CLI with the expected result, undo restores the previous state for mutating commands, `agents sync --check` is in step, and the checklist passes.

## Hands back

The command id, its parameters, the CLI transcript, and the MCP tool name when one was added.

## Owned resources

- `references/adding-a-command.md` the shape of a command, a task, an event and an MCP tool
- `checklists/command-gate.md` what every engine change passes
