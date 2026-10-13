# Interface

`frontend/` is a Vite app in vanilla TypeScript with formvis's Studio Dark design: the shared recipes keep formvis's `cv-` classes (vendored under Apache-2.0), and formlit's own surfaces use `fl-` classes in the `lit-*.css` sheets.

## Shell and modules

`src/ui/shell.ts` mounts the title bar with the module picker, the left and right panel columns, the stage, the filmstrip and the status bar once. Modules register through `src/modules/registry.ts`: Library (`modules/library`), Develop (`modules/develop`), and the output modules Map, Book, Slideshow, Print and Web (`modules/output`, sharing `base.ts` and `page.ts`). Commands shared across modules (photo actions, export, catalog, AI, tethering, the Plug-in Manager) live in `modules/shared`.

## Workspace and panels

`src/ui/panel.ts` gives every panel a header that opens and closes it (Alt-click opens it alone), a right-click menu, and drag to reorder within its column. Hidden panels, the order per module and column, and Solo Mode per side live in the window's local storage (`formlit_panels_hidden`, `formlit_panels_order`, `formlit_panels_solo`) beside the open states (`formlit_panels`). The shell keeps the side widths, the dock height and which areas are hidden (`formlit_layout`), so a layout survives a restart. `src/modules/shared/workspace.ts` adds Window, Workspace: five built-in workspaces, Save and Delete Workspace (stored in the engine's preferences as `workspaces`, so they survive a cleared browser cache), Solo Mode for each side and Reset Panels; it reorders panels as modules mount them, through a MutationObserver on the panel columns.

The AI icons: `agent` (a small robot head) marks Claude Code and the Ask line, `agentChat` (a speech bubble with the same eyes) marks Chat, and `aiChip` (a processor) marks features run by local models such as Denoise and Build Depth.

## State

`src/state/catalog.ts` holds folders, collections and keywords; `state/library.ts` the source, the query result and the selection; `state/develop.ts` the open photo's settings with debounced writes to the engine. Each listens to engine events and tells its subscribers what changed.

## Zero flash

- The shell and every panel mount once; lists are reconciled by key with `patchList` and never cleared and refilled.
- Text and attributes are written only when they change (`setText`, `setClass`, `setStyleVar`).
- Images swap only after the new one has decoded; the old frame stays until then.
- Space for asynchronous content is reserved before it arrives; the theme boot runs before any stylesheet.
- Every stacking level comes from a `--z-*` token; overlays render into the overlay root.

## Icons and themes

Icons are inline `currentColor` SVG in `src/ui/icons.ts` and `icons-lit.ts`; there is no icon library. `src/ui/themes.ts` carries the 14 appearance profiles with the accent and its intensity.
