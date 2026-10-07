---
name: ui-builder
description: "Owns formlit's window under frontend/src: modules (Library, Develop, Map, Book, Slideshow, Print, Web), panels, the form helper, dialogs, commands and shortcuts, menus, stores and SSE, the output module base, styles, tokens and icons, and the zero-flash rule with throttled verification. Load for any UI change, a flash or layout jump, a new panel or module, or a broken shortcut."
---

# UI Builder

## Purpose

Change the window so it renders engine state faithfully and never flashes. Hands back the change, the typecheck, and the throttled verification result.

## Preconditions

`frontend/HASHOUT_LOG.md` read. The command the UI needs already exists in the engine (engine-builder first when it does not).

## Procedure

1. Find the home: a module under `src/modules/[module]/`, shared commands and dialogs in `src/modules/shared/`, reusable pieces in `src/ui/`. Output modules extend `OutputModule` in `src/modules/output/base.ts`; recipe in `references/module-recipe.md`.
2. State the three-line pre-write for every DOM change (`references/zero-flash.md`): the node and property written, what stays untouched, and what space is reserved.
3. Lists: `patchList` with keys; create builds the node, update paints it, and when create does not call update, paint after the call. Never `innerHTML` a live container; small blocks keyed by structure (a `dataset.key` guard) are the exception.
4. Forms: `Form` in `src/ui/form.ts` with `FieldSpec` rows bound to settings paths; `show` receives a getter for conditional rows. One-off questions use `askForm` from `src/ui/askform.ts`.
5. Commands: register with `ctx.commands.add({ id, label, keys, run, enabled, checked })`; keys are written `Alt+Shift+Mod+Key` in that order; menus list ids in `app.ts` `buildMenus`.
6. Engine calls go through `ctx.api.cmd(id, params)`; long jobs return a task, awaited with `whenDone` or `runOutput` from `src/modules/shared/tasks.ts`, which also shows the Open and Show in Folder toast.
7. Style with tokens only: colours `var(--...)` from `src/styles/tokens.css` or formlit's block at the top of `lit-shell.css`; z-index only `var(--z-*)`; icons from `src/ui/icons-lit.ts` as inline currentColor SVG. formvis classes (`cv-`) are vendored; formlit's own are `fl-`.
8. `npx tsc --noEmit` in `frontend/`, then run `checklists/ui-gate.md`.

## Gate

Done when the typecheck is clean and the UI gate holds, including the throttled run, or the hand-back says plainly that it was not run.

## Hands back

The files changed, the typecheck result, the throttled verification line for the turn ledger, and a screenshot when the person can see one.

## Owned resources

- `references/module-recipe.md` how a module, a panel and an output module are put together
- `references/zero-flash.md` the rules and the patterns that satisfy them
- `checklists/ui-gate.md` the checks before any UI hand-back
