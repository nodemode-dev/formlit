# Interface

`frontend/` is a Vite app in vanilla TypeScript with formvis's Studio Dark design: the shared recipes keep formvis's `cv-` classes (vendored under Apache-2.0), and formlit's own surfaces use `fl-` classes in the `lit-*.css` sheets.

## Shell and modules

`src/ui/shell.ts` mounts the title bar with the module picker, the left and right panel columns, the stage, the filmstrip and the status bar once. Modules register through `src/modules/registry.ts`: Library (`modules/library`), Develop (`modules/develop`), and the output modules Map, Book, Slideshow, Print and Web (`modules/output`, sharing `base.ts` and `page.ts`). Commands shared across modules (photo actions, export, catalog, AI, tethering, the Plug-in Manager) live in `modules/shared`.

## Workspace and panels

`src/ui/panel.ts` gives every panel a header that opens and closes it (Alt-click opens it alone), a right-click menu, and drag to reorder within its column. Hidden panels, the order per module and column, and Solo Mode per side live in the window's local storage (`formlit_panels_hidden`, `formlit_panels_order`, `formlit_panels_solo`) beside the open states (`formlit_panels`). The shell keeps the side widths, the dock height and which areas are hidden (`formlit_layout`), so a layout survives a restart. `src/modules/shared/workspace.ts` adds Window, Workspace: five built-in workspaces, Save and Delete Workspace (stored in the engine's preferences as `workspaces`, so they survive a cleared browser cache), Solo Mode for each side and Reset Panels; it reorders panels as modules mount them, through a MutationObserver on the panel columns.

The filmstrip has its own resize handle (`formlit_filmstrip_h`, saved in workspaces as `stripH`), collapses to its 28 px header and docks at the top or bottom (the `is-filmstrip-collapsed` and `is-filmstrip-top` areas in `formlit_layout`, `stripCollapsed` and `stripTop` in workspaces; the app grid sizes its row from `--fl-strip-row` so the inline height never fights the hidden and collapsed states), and the module picker's right-click menu shows or hides modules (`formlit_modules_hidden`; hidden modules stay in the Window menu). Panel drag follows the pointer on the window rather than capturing it on the header, because moving the panel would release the capture, and it scrolls the column while the pointer rests near its top or bottom.

The Chat tab (`src/ui/chat-pane.ts`) renders Claude's Markdown through `src/ui/markdown.ts`, which builds DOM nodes and never parses HTML; `MarkdownStream` appends each finished block once and keeps only the unfinished tail as plain text. Its bar shows live token use from the engine's `chat.usage` events, and its two bridge buttons hand the conversation to a Claude Code tab (`claudecode.open` with `resume`) or bring one back (`chat.sessions`, `chat.adopt`).

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
