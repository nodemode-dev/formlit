# HASHOUT_LOG · frontend · formlit

Living log of all comment content, explainers, rationale, TODOs and removed code for the interface. Source files stay comment-free (vendored formvis files keep their upstream headers); everything else they would have said lives here, indexed. Read this first, then edit code surgically.

Current build version: v0.26.0
Last updated: 2026-10-14 · v0.26.0 Skin Tone and picker, picker drawer and slider thumb shifts fixed; v0.25.0 Focus Stack in the Photo menu; v0.24.0 the Layers panel and the layer editing target; v0.23.0 mask edge sliders, the Refine Edge Brush; v0.22.0 Code Replacements and Required Fields, the Metadata panel refresh fixed; v0.21.0 the Cull view, the Keywording suggestion shift fixed; v0.20.0 filmstrip collapse and top or bottom, hidden-row fix; v0.19.0 panel drag fix, chat Markdown, token meter and bridge, filmstrip resize, module show and hide; v0.18.0 workspaces, panel hide, reorder and solo, AI icons; v0.17.0 chat photo strips; v0.16.0 chat selection notes; v0.15.0 the Chat tab in the dock; v0.14.0 Claude Code in formlit section in Preferences; v0.13.0 the reference follows its edits, identity in Preferences; v0.12.0 Reference View, template lists in the import and rename dialogs; v0.11.0 template commands, keyword sets from the engine, export preset groups; v0.10.0 Refine Photos in the Library menu; v0.7.0 the terminal dock, Claude Code and the Ask line; v0.6.0 the AI agent access prompt and the Preferences AI agents section; v0.3.3 buttons follow state, shared shortcuts by module, panel header tools, toolbars that fit; v0.3.1 relative white balance; v0.3.0 view geometry, Navigator, dev font preloads

---

## Org-navi-map

```
frontend/
├── index.html                     theme boot before any stylesheet, then main.ts
├── vite.config.ts                 host false, port 5390 strict, preview 5391
├── package.json                   TypeScript, Vite, fonts, Tauri api
├── boot_frontend(.bat)            dev server
├── oc_install(.bat)               npm install
└── src/
    ├── main.ts                    entry: second window or the app
    ├── app.ts                     App: shell, modules, menus, command registration
    ├── version.ts                 VERSION
    ├── second.ts                  second window entry
    ├── second-modes.ts            second window Grid, Loupe, Compare, Survey, Slideshow
    ├── io/
    │   ├── api.ts                 engine client, command calls, errors
    │   └── events.ts              server-sent events subscription
    ├── state/
    │   ├── catalog.ts             folders, volumes, collections, keywords
    │   ├── library.ts             source, query result, selection
    │   └── develop.ts             develop session, patches, auto sync
    ├── modules/
    │   ├── index.ts               imports every module
    │   ├── registry.ts            registerModule, module order and keys
    │   ├── library/
    │   │   ├── index.ts           Library module: grid, loupe, compare, survey, toolbar
    │   │   ├── sources.ts         Catalog, Folders, Collections panels
    │   │   ├── folder-sync.ts     Synchronize Folder dialog
    │   │   ├── navigator.ts       Library Navigator panel
    │   │   ├── inspect.ts         Histogram, Quick Develop, Keywording, Keyword List, Metadata
    │   │   ├── keyword-list.ts    keyword context menu and editing
    │   │   ├── keyword-sets.ts    keyword sets and recent keywords
    │   │   ├── metadata-presets.ts metadata presets
    │   │   ├── painter.ts         the Painter
    │   │   ├── filterbar.ts       Text, Attribute and Metadata filters
    │   │   ├── smart.ts           smart collection rule editor
    │   │   ├── people.ts          People panel and view
    │   │   ├── face-regions.ts    face regions in the Loupe
    │   │   ├── importer.ts        Import dialog
    │   │   ├── publish.ts         Publish Services panel and service dialog
    │   │   ├── comments.ts        Comments panel for published photos
    │   │   └── video-player.ts    video playback and trim
    │   ├── develop/
    │   │   ├── index.ts           Develop module, commands, tool switching
    │   │   ├── view.ts            Develop view: renders, zoom, compare, overlays
    │   │   ├── panels.ts          right panels built from the control table
    │   │   ├── left.ts            Navigator, Presets, Snapshots, History
    │   │   ├── tools.ts           crop, spot, red eye, white balance, targeted adjustment, Upright
    │   │   ├── masks.ts           Masking drawer: masks, components, adjustments, Point Color, curve
    │   │   ├── curve.ts           point and parametric curve editor
    │   │   ├── wheel.ts           colour grading wheels
    │   │   ├── hdr.ts             HDR section in Basic
    │   │   ├── lensblur-tool.ts   focus picker and refine brushes
    │   │   ├── profile-browser.ts Profile Browser
    │   │   ├── preset-dialog.ts   New Develop Preset
    │   │   └── groups.ts          settings group names
    │   ├── output/
    │   │   ├── base.ts            OutputModule: templates, saved creations, forms
    │   │   ├── page.ts            PageView for print, book and slideshow pages
    │   │   ├── map.ts             Map module and tile map
    │   │   ├── book.ts            Book module
    │   │   ├── slideshow.ts       Slideshow module and Player
    │   │   ├── print.ts           Print module
    │   │   └── web.ts             Web module
    │   └── shared/
    │       ├── agent-consent.ts   AI agent access prompt: Allow, Not now, Block
    │       ├── terminal.ts        terminal dock and Claude Code commands, selection context
    │       ├── actions.ts         rating, flag, label, stack, rotate commands
    │       ├── catalog-commands.ts catalogs, previews, second window, shortcuts
    │       ├── export.ts          Export dialog
    │       ├── ai.ts              AI commands: enhance, merges, culling
    │       ├── merge-dialog.ts    merge and enhance dialogs
    │       ├── photo-dialogs.ts   rename, capture time, Edit In
    │       ├── tether.ts          tether bar and Live View
    │       ├── plugin-manager.ts  Plug-in Manager dialog
    │       └── tasks.ts           task completion helpers and output toasts
    ├── ui/
    │   ├── shell.ts               the frame, mounted once, with the dock row
    │   ├── terminal-dock.ts       xterm.js tabs over the engine's terminal WebSocket, Claude Code, Ask line
    │   ├── grid.ts                virtualized thumbnail grid
    │   ├── viewer.ts              loupe viewer with zoom
    │   ├── filmstrip.ts           filmstrip
    │   ├── thumbs.ts              thumbnail URLs and badges
    │   ├── histogram.ts           histogram with HDR zone
    │   ├── panel.ts               collapsible panel
    │   ├── tree.ts                keyed tree for folders, collections, keywords
    │   ├── slider.ts              slider control
    │   ├── form.ts                declarative form fields
    │   ├── askform.ts             form dialog
    │   ├── dialogs.ts             Dialog, confirm, prompt (vendored)
    │   ├── folder-picker.ts       engine-side folder browser
    │   ├── preferences.ts         Preferences dialog, with the AI agents section
    │   ├── menu.ts                menu bar and popup menus (vendored)
    │   ├── dropdown.ts            styled selects (vendored)
    │   ├── commands.ts            command registry and shortcuts
    │   ├── dom.ts                 zero-flash DOM helpers (vendored)
    │   ├── themes.ts              14 appearance profiles (vendored)
    │   ├── icons.ts, icons-lit.ts inline currentColor SVG icons
    │   ├── brand.ts               brand mark
    │   └── toast.ts               toasts (vendored)
    └── styles/
        ├── tokens.css, shell.css, panels.css, dialogs.css, light-mode.css, scrollbars.css, fonts.css   formvis Studio Dark (vendored)
        ├── lit-tokens.css         formlit's own colour and size tokens
        ├── lit-shell.css          title bar, module picker, filmstrip, status
        ├── lit-library.css        Library surfaces
        ├── lit-develop.css        Develop surfaces
        ├── lit-modules.css        output modules, pages, publish, comments, plug-ins
        └── lit-dock.css           the terminal dock
```

---

## Table of contents

- [src/ui/dom.ts, themes.ts, dropdown.ts, dialogs.ts, menu.ts, toast.ts (vendored)](#ui-vendored)
- [src/ui/commands.ts](#ui-commands)
- [src/ui/histogram.ts](#ui-histogram)
- [src/modules/library/inspect.ts](#library-inspect)
- [src/modules/library/publish.ts](#library-publish)
- [src/modules/library/comments.ts](#library-comments)
- [src/modules/develop/curve.ts](#develop-curve)
- [src/modules/develop/masks.ts](#develop-masks)
- [src/modules/develop/view.ts](#develop-view)
- [src/modules/develop/tools.ts](#develop-tools)
- [src/modules/develop/profile-browser.ts](#develop-profile-browser)
- [src/modules/develop/panels.ts](#develop-panels)
- [src/modules/develop/left.ts](#develop-left)
- [src/modules/output/book.ts](#output-book)
- [src/modules/output/slideshow.ts](#output-slideshow)
- [src/modules/shared/plugin-manager.ts](#shared-plugin-manager)
- [src/modules/shared/agent-consent.ts](#shared-agent-consent)
- [src/ui/preferences.ts](#ui-preferences)
- [src/styles/lit-tokens.css](#styles-lit-tokens)
- [vite.config.ts](#vite-config)
- [src/ui/terminal-dock.ts, src/modules/shared/terminal.ts](#ui-terminal-dock)
- [Files with no entries](#no-entries)

---

## src/ui/dom.ts, themes.ts, dropdown.ts, dialogs.ts, menu.ts, toast.ts (vendored) {#ui-vendored}

### src/ui/dom.ts · file header
- refers-to: src/ui/dom.ts :: top of file; also themes.ts, dropdown.ts and Dialog.close in dialogs.ts
- kind: explainer
- logged: v0.1.0 · 2026-10-07

These files are vendored from formvis (Apache-2.0, the owner's) and keep their upstream comments verbatim, so a diff against formvis stays clean. The five DOM primitives are `delayedIndicator`, `patchList`, `swapMedia`, `setText` and `reserve`, plus `revealApp`. Note that `patchList` calls `update` only for existing nodes: `create` must paint its own node (see masks.ts below).

---

## src/ui/commands.ts {#ui-commands}

### src/ui/commands.ts · CODE_KEYS Comma
- refers-to: src/ui/commands.ts :: CODE_KEYS
- kind: rationale
- logged: v0.1.0 · 2026-10-07

Shortcuts are matched on `KeyboardEvent.code` where a mapping exists. Without `Comma`, Shift+comma arrived as `<`, so Alt+Shift+Mod+, (Plug-in Manager) never matched. Only Preferences and the Plug-in Manager use the comma.

### src/ui/commands.ts · forCombo
- refers-to: src/ui/commands.ts :: forCombo; modules/develop/left.ts :: develop.snapshot; modules/library/sources.ts :: lib.colNew
- kind: rationale
- logged: v0.3.3 · 2026-10-08

Two commands may share a shortcut when they belong to different modules, as in Lightroom: Mod+N is Create Collection in the Library and New Snapshot in Develop. The key map kept only the last command registered, so Mod+N always meant New Snapshot. `forCombo` now looks at every command with the combo and picks, in order, one that declares `enabled()` and is enabled, then one with no `enabled()` (a command that always applies), then the key map's owner. A module-specific command therefore declares `enabled()` with its module test (`develop.snapshot` is enabled only in Develop with a photo).

### src/app.ts · scheduled syncButtons
- refers-to: src/app.ts :: start (sync), syncButtons
- kind: rationale
- logged: v0.3.3 · 2026-10-08

Every `[data-cmd]` button takes its disabled, checked and title state from its command, but `syncButtons` ran only after a shortcut, a click on an enabled button or a module switch. Selecting a photo with the mouse therefore left the toolbar's flag, star, label, rotate and Export buttons disabled, Develop's Reset, Copy, Paste and Auto stayed disabled while editing, and a menu choice left the wrong view button highlighted. `start` now schedules `syncButtons` (one per animation frame at most) on selection, list and photo changes, catalog changes, develop changes other than drags, undo and redo, and after any pointer or key release. The setters write only what changed, so nothing repaints when the state is the same.

---

## src/ui/histogram.ts {#ui-histogram}

### src/ui/histogram.ts · setHdr
- refers-to: src/ui/histogram.ts :: setHdr
- kind: explainer
- logged: v0.1.0 · 2026-10-07

In HDR mode the SDR range takes the left 72 percent of the width and the stops above SDR white the rest, with the HDR bins from the render's `X-HDR-Hist` header.

---

## src/modules/library/inspect.ts {#library-inspect}

### src/modules/library/inspect.ts · keyword suggestions
- refers-to: src/modules/library/inspect.ts :: fetch
- kind: rationale
- logged: v0.1.0 · 2026-10-07

`keyword.suggest` returns `{id, path}` objects; the panel maps them to paths before escaping. Treating them as strings threw inside `escapeHtml` and the error was swallowed, so suggestions never showed.

---

## src/modules/library/publish.ts {#library-publish}

### src/modules/library/publish.ts · setup plug-in fields
- refers-to: src/modules/library/publish.ts :: setup
- kind: explainer
- logged: v0.1.0 · 2026-10-07

Each plug-in's fields are added to the service dialog under `opt.{kind}.{field}` so two plug-ins can share a field name; only the chosen kind's values are saved, flat, into the service settings. A blank password field on edit keeps the stored secret.

---

## src/modules/library/comments.ts {#library-comments}

### src/modules/library/comments.ts · soon
- refers-to: src/modules/library/comments.ts :: soon, fetch
- kind: rationale
- logged: v0.1.0 · 2026-10-07

Comments are fetched only while the panel is open and only when the active photo changes (or Refresh is pressed), because each fetch can call online services.

---

## src/modules/develop/curve.ts {#develop-curve}

### src/modules/develop/curve.ts · CurveSource
- refers-to: src/modules/develop/curve.ts :: CurveEditor constructor
- kind: explainer
- logged: v0.1.0 · 2026-10-07

The editor reads and writes through a `CurveSource`. The default is the global `curve` setting; the Masking drawer passes one bound to the selected mask's `adjust.curve` and hides the Region tab, since local curves are point curves.

---

## src/modules/develop/masks.ts {#develop-masks}

### src/modules/develop/masks.ts · sync patchList
- refers-to: src/modules/develop/masks.ts :: sync (mask rows)
- kind: removed-code
- logged: v0.1.0 · 2026-10-07

```ts
create: () => el('<div class="fl-mask-row"></div>'),
```

Created an empty row that was filled only on the next sync, a blank row for a frame. `create` now paints the row with the same `update` function.

---

## src/modules/develop/view.ts {#develop-view}

### src/modules/develop/view.ts · shown, place
- refers-to: src/modules/develop/view.ts :: shown, place, setPhoto, run
- kind: rationale
- logged: v0.3.0 · 2026-10-07

`setPhoto` switches the view's geometry to the new photo at once (aspect from the library record, centre reset), but the picture on screen is still the old photo until the new render arrives. The image fills its box (`object-fit: fill`), so moving the box first stretched the old photo into the new photo's shape, and at 1:1 rescaled it, for as long as the render took (about half a second at 4x CPU). `shown` records which photo the box's pixels belong to; `place` only moves the box when they belong to the current photo (or nothing is loaded yet), and `run` sets `shown` right after the new image is swapped in and before calling `place`, so the new pixels and the new geometry appear in the same frame.

### src/modules/develop/view.ts · hdr
- refers-to: src/modules/develop/view.ts :: body, hdr fields
- kind: explainer
- logged: v0.1.0 · 2026-10-07

With HDR on, renders are requested in `display` mode (PQ AVIF) on HDR-capable screens, `visualize` when Visualize HDR is on, and `sdr` when previewing the SDR rendition.

---

## src/modules/develop/tools.ts {#develop-tools}

### src/modules/develop/tools.ts · CropTool overlays
- refers-to: src/modules/develop/tools.ts :: CropTool, spiralUV
- kind: explainer
- logged: v0.1.0 · 2026-10-07

O cycles grid, thirds, diagonal, triangle, golden ratio, golden spiral and aspect ratios; Shift+O flips the orientation of the triangle and spiral. The Straighten tool (or Ctrl-drag) sets the angle to the negative of the drawn line's tilt.

### src/modules/develop/tools.ts · SpotTool reflections slider
- refers-to: src/modules/develop/tools.ts :: SpotTool (remove row); groups.ts `reflections`
- kind: removed-code
- logged: v0.2.0 · 2026-10-07

```ts
this.sRefl = slider('reflections.amount', 'Reflections', -100, 100, 0, this.reflection(), (v, phase) => {
  this.host.view.setDragging(phase === 'drag');
  develop.patch('reflections', v ? { amount: v } : null, phase, 'Remove Reflections');
});
this.removeRow.appendChild(this.sRefl.root);
develop.listen((why) => { if (why !== 'drag') this.sRefl.set(this.reflection()); });
```

The slider sat in the Healing tool's remove row and wrote the whole-photo `reflections.amount` setting (zero writes `null`, which prunes the key), with its own `reflections` sync group. Withdrawn with the engine's classical filter before release (see the backend log, `app/develop/reflections.py`); this is the wiring to restore when a learned model backs it.

---

## src/modules/develop/profile-browser.ts {#develop-profile-browser}

### src/modules/develop/profile-browser.ts · ready
- refers-to: src/modules/develop/profile-browser.ts :: ProfileBrowser.ready, show
- kind: rationale
- logged: v0.2.0 · 2026-10-07

The browser opens only after the favourites preference has loaded. In v0.1.0 the first opening painted the grid, then the preference arrived and inserted the Favorites row above it, shifting every tile (layout shift 0.035 under 4x CPU throttling). Waiting for one small request keeps the first paint final. After an import, `left.ts` calls `develop.refreshInfo` so new profiles appear in the menu and the browser without changing photos.

### src/modules/develop/profile-browser.ts · filter types and the note
- refers-to: src/modules/develop/profile-browser.ts :: fillFilter, rows, writeNote, note
- kind: explainer
- logged: v0.2.0 · 2026-10-07

The filter's values are `All`, `Favorites`, `type:color`, `type:bw` and the group names; the `type:` values keep their own prefix because a group is also called B&W. The note under the filter is written before the dialog opens (never after), from `develop.info.cameraStyle`: it names the picture style the raw was shot in, or says the camera styles assume the standard style when the raw does not record it.

---

## src/modules/develop/panels.ts {#develop-panels}

### src/modules/develop/panels.ts · Amount at rest
- refers-to: src/modules/develop/panels.ts :: DevelopPanels.sync (profile.amount)
- kind: explainer
- logged: v0.2.0 · 2026-10-07

Profiles without a table (Color, Camera Look, DCPs) have nothing for Amount to scale, so the slider is made `inert` and dimmed (`.fl-sl.is-inert`) instead of hidden, which would move every slider under it. Both are written only when the state changes.

### src/modules/develop/panels.ts · relative white balance
- refers-to: src/modules/develop/panels.ts :: toRelativeWb, fromRelativeWb, SliderSet.makeRelativeWb, SliderSet.sync, RAW_ONLY_WB, DevelopPanels.sync; index.ts :: histogram info
- kind: rationale
- logged: v0.3.1 · 2026-10-07

Lightroom shows Temp and Tint for JPEG, PNG, TIFF and other rendered files as -100 to +100 around as shot, and offers only As Shot, Auto and Custom, because a rendered file has no sensor white point to put a kelvin on. formlit showed kelvin (6500 as shot, 2000 to 50000) for them, which reads as a raw control and invites values like 15900. The engine is unchanged: `wb.temp` and `wb.tint` stay in kelvin and tint units, so history, presets, sync, XMP and agents keep one model. For photos the engine marks `relativeWb`, the panel swaps in a second pair of sliders of the same height (no layout movement) that map one step to 0.75 mired around as shot (+100 is about 12,700 K, -100 about 4,400 K) and tint one to one, label their history steps in those units, and hides the six raw-only presets. The histogram line drops "As shot 6500 K" for them. A photo edited in kelvin before this reads back clamped to the ends of the scale.

---

## src/modules/develop/left.ts {#develop-left}

### src/ui/panel.ts and left.ts · header tools, snapshot labels, onZoom
- refers-to: src/ui/panel.ts :: Panel (head click, tools); modules/develop/left.ts :: loadSnaps, onZoom; modules/develop/index.ts :: toolbar onZoom, commands (anyPhoto, profileBrowser); state/library.ts :: relabel; modules/library/sources.ts :: lib.colRename, lib.folderRename
- kind: rationale
- logged: v0.3.3 · 2026-10-08

A panel header is one button, so a click on a tool inside it (Presets +, Snapshots +, History ×) also toggled the panel and hid the dialog's result. Tools passed in the constructor stopped propagation instead, which kept their `data-cmd` from reaching the app's delegated handler, so the Folders + did nothing. The header now ignores clicks that start inside `.fl-panel-tools` and no tool stops propagation. The snapshot list updates each row's name in place, so a rename shows at once; renaming the collection or folder being viewed relabels the filmstrip source through `library.relabel`. The left panels used to replace the view's `onZoom` and so blanked the toolbar's zoom readout; both now chain it, and the readout is set when the toolbar is built. Auto, Auto B&W, Reset, Copy and Paste work from the Library on the selection, and the Profile Browser opens Develop first.

### src/styles/lit-library.css · toolbar container queries
- refers-to: src/styles/lit-shell.css :: .fl-toolbar-page (container fl-toolbar); lit-library.css :: @container fl-toolbar; lit-develop.css :: .fl-upright
- kind: rationale
- logged: v0.3.3 · 2026-10-08

The Library toolbar was 955 px of content in an 838 px bar at 1440 px with both panels open, so the Thumbnails slider sat under the right panel, and at 1024 px a dozen controls were cut off, with Develop's 1:1 and 2:1 too. The toolbar page is now a size container and its contents step down as it narrows: text labels go first (960), then the stars tighten and the Top/Bottom and Split compare modes go (820; the View menu still has them), rotate (700), colour labels and a narrower sort (620), Develop's zoom buttons, separators and the Painter (560; the Navigator has the zooms) and finally the stars and sort direction (480; keys 0 to 5 rate). Every remaining control is fully inside the bar at 1024 and 1440 px. Upright's six modes sit in a 3 by 2 grid so Vertical and Full stay in the column.

### src/modules/develop/left.ts · Navigator box
- refers-to: src/modules/develop/left.ts :: nav, navSync, the navImg load listener; src/styles/lit-develop.css :: .fl-nav-fit
- kind: rationale
- logged: v0.2.0 · 2026-10-07 · revised v0.3.0

v0.2.0 sized the box to each photo's aspect ratio (`--fl-nav-ar`, capped at 180 px). That still moved the panels below it whenever a landscape photo followed a portrait one, and a tall photo overflowed the cap. Since v0.3.0 the box is one fixed 3:2 shape for every photo (`aspect-ratio: 3 / 2`, a single 100% grid cell, the image limited to the cell's height), so nothing below it ever moves, and the picture is letterboxed inside it. `navSync` places the view rectangle against the picture's own rectangle (its offset and size within the box, read with `getBoundingClientRect`), not against the box, so it lines up on portrait and landscape photos alike. The picture's `load` event re-runs `navSync`, so after switching photos while zoomed, or after a preset preview, the rectangle follows the new picture's shape as soon as it is shown.

---

## src/modules/output/book.ts {#output-book}

### src/modules/output/book.ts · setTemplate spreads
- refers-to: src/modules/output/book.ts :: setTemplate
- kind: rationale
- logged: v0.1.0 · 2026-10-07

Spreads begin on a left-hand page. Choosing a spread on a right page applies it to the page on its left and says so; the right page becomes `spread-cont` and its photos are released.

---

## src/modules/output/slideshow.ts {#output-slideshow}

### src/modules/output/slideshow.ts · Player
- refers-to: src/modules/output/slideshow.ts :: Player.clipFor, startMusic, seconds
- kind: explainer
- logged: v0.1.0 · 2026-10-07

Music plays from an `Audio` element outside the DOM, track after track, looping with Repeat. A video slide gets a `video` element layered over the poster image in the same cell, hidden until it is playing so the poster never blinks; its volume follows Audio balance and it is paused after the crossfade away. Slide length comes from the layout's `seconds` (clip length, or the fitted length with Fit to Music).

### src/modules/output/slideshow.ts · H.264 in the test browser
- refers-to: src/modules/output/slideshow.ts :: clipFor
- kind: warning-context
- logged: v0.1.0 · 2026-10-07

Open-source Chromium (as used by Playwright here) plays WebM but not H.264, so MP4 clips stay on their poster in that browser. Tauri's webviews on macOS and Windows play H.264.

---

## src/modules/shared/plugin-manager.ts {#shared-plugin-manager}

### src/modules/shared/plugin-manager.ts · paint
- refers-to: src/modules/shared/plugin-manager.ts :: PluginManager.paint
- kind: explainer
- logged: v0.1.0 · 2026-10-07

Lists loaded plug-ins (keyed by kind) and the files that failed with their reasons; Reload calls `publish.reloadPlugins`, which also refreshes the Publish Services panel through a `list.changed` event.

---

## src/modules/shared/agent-consent.ts {#shared-agent-consent}

### src/modules/shared/agent-consent.ts · one dialog, built once
- refers-to: src/modules/shared/agent-consent.ts :: AgentConsent, ask, dismiss
- kind: rationale
- logged: v0.6.0 · 2026-10-12

The prompt is one dialog built the first time an agent asks and reused after that. A later request only patches the client name (a `<strong>` node, `setText`) and reopens the same dialog; nothing is created or removed while the person is looking, and it opens into the existing overlay root, so the page behind it does not move. Not now takes the initial focus because it refuses one call and changes nothing, the safest button for a reflex press. Closing with Esc, the close button or the scrim sends the same answer. Allow and Block each toast where the choice can be changed again.

### src/modules/shared/agent-consent.ts · events, and a window that connects late
- refers-to: src/modules/shared/agent-consent.ts :: registerAgentConsent; backend/app/engine/agents.py :: status
- kind: explainer
- logged: v0.6.0 · 2026-10-12

`agents.consent` opens the prompt. `agents.changed` closes it when the setting is no longer ask or the answer was Not now, so a choice made in Preferences, in a second window or from the CLI takes down a prompt that is still up. A window that connects after the event (the plugin's bridge launches the desktop app) asks `agents.status` on the stream's `hello` and `resync` and shows the prompt for the first call still pending. The handlers are registered before the event stream starts, in `app.ts`, next to the Plug-in Manager.

---

## src/ui/preferences.ts {#ui-preferences}

### src/ui/preferences.ts · the AI agents section
- refers-to: src/ui/preferences.ts :: Preferences (access, seen, agents), show; src/styles/lit-library.css :: .fl-agents-seen
- kind: rationale
- logged: v0.6.0 · 2026-10-12

The old Agents (MCP) block was a note and the endpoint JSON. The section now leads with the plugin and keeps the developer setup second, and holds the Agent access select (Ask me, Allowed, Blocked) and a Seen row. It sits above Engine and AI Models because those two fill their rows with `innerHTML` after the dialog opens; a section placed below them would be pushed down when they arrive. The endpoint JSON is set before `open()` for the same reason, and the select and the Seen row only have their text patched afterwards (`setValue`, `setText`, `setTitle`). Seen is one line with an ellipsis and its full text in the title, so a long list never changes the row's height. The select also listens for `agents.changed`, so answering the prompt updates an open Preferences.

---

## src/styles/lit-tokens.css {#styles-lit-tokens}

### src/styles/lit-tokens.css · app-owned colours
- refers-to: src/styles/lit-tokens.css :: :root
- kind: rationale
- logged: v0.1.0 · 2026-10-07

Colours only formlit needs (label colours, clipping, the map and page surfaces) are declared here as tokens, so component sheets never hold raw colours and formvis's vendored tokens stay untouched.

---

## vite.config.ts {#vite-config}

### vite.config.ts · devFontPreloads
- refers-to: vite.config.ts :: devFontPreloads, plugins
- kind: rationale
- logged: v0.3.0 · 2026-10-07

`index.html` preloads three Inter woff2 files so the built app paints its first frame in the right font; in the build they resolve to the hashed font files the stylesheet uses. The dev server loads stylesheets through modules after the load event, so Chromium reported those preloads as unused a few seconds in (3 console warnings). The plugin applies only to `serve` and removes the woff2 preload links from the served HTML; the production build keeps them.

### vite.config.ts · ws on the engine proxy
- refers-to: vite.config.ts :: engine; src/ui/terminal-dock.ts :: connect
- kind: rationale
- logged: v0.7.0 · 2026-10-12

The terminal dock streams through a WebSocket at `/api/terminal/{id}` on the page's own host. The built app and the desktop window are served by the engine, so that host is the engine; on the dev server the `/api` proxy needs `ws: true` to pass the upgrade through.

---

## src/modules/shared/actions.ts · library.refine {#shared-refine}

### src/modules/shared/actions.ts · Refine Photos
- refers-to: src/modules/shared/actions.ts :: library.refine; src/app.ts :: buildMenus (Library); backend/app/engine/cmd_workflow.py :: refine
- kind: explainer
- logged: v0.10.0 · 2026-10-13

Library, Refine Photos (Alt+Mod+R) runs the engine's `library.refine` on every photo in view after a confirmation, because it changes flags across the whole source. Only menu and toast change; the grid follows through the engine's flag events, with no rebuild.

## src/ui/panel.ts, shell.ts, modules/shared/workspace.ts · workspace {#workspace}

### src/ui/panel.ts · panels the person arranges
- refers-to: src/ui/panel.ts :: PANELS, arrange, restoreOrder, setPanelVisible, isSolo, setSolo, panelState, applyPanelState, Panel.dragging
- kind: rationale
- logged: v0.18.0 · 2026-10-13

Every Panel registers in `PANELS` so the workspace can show, hide, open and order panels it did not create. Drag reorders with pointer events, not HTML drag and drop, because Tauri's webview takes native drag events for file drops; the panel moves in place while dragging, so there is no ghost element, and the click that follows a drag is swallowed so a drag never toggles the panel. Order is kept per module and side (`orderKey`); `arrange` only moves nodes when the saved order differs, and records the natural order the first time it sees a container so Reset Panels can restore it. Solo Mode per side turns a normal open into Alt-click's open-alone. The right-click menu is a CustomEvent (`fl-panel-menu`) so the panel does not need the command registry. Rewritten in one pass at v0.18.0 rather than in single-region edits, an exception to the edit rule noted in BUILD_NOTES.

### src/ui/panel.ts · drag follows the window, and auto-scrolls (v0.19.0 fix)
- refers-to: src/ui/panel.ts :: Panel.dragging (place, edge, move, up)
- kind: warning-context
- logged: v0.19.0 · 2026-10-13

v0.18.0 captured the pointer on the panel header; `insertBefore` on the panel releases that capture, so a drag stopped after its first move and nothing was saved whenever the header left the pointer (always in Develop's long column). Listeners now sit on `window` for the drag; the click after a drag is swallowed through a flag cleared on the next task, because the click may land on another element after the panel moved. A rAF loop scrolls the column (`.fl-col-page`, the element that scrolls) while the pointer rests within 36 px of its edge and re-places the panel as it scrolls. Re-checked: 61 panels in 7 modules open, close, solo and switch; a Develop drag from the bottom to near the top saved and survived a reload. These fixes were single-region edits.

### src/ui/markdown.ts, chat-pane.ts · formatted chat, previews, token meter, bridge
- refers-to: src/ui/markdown.ts :: renderMarkdown, MarkdownStream; src/ui/chat-pane.ts :: delta, endText, images, showUsage, handoff, adopt; src/ui/terminal-dock.ts :: claude(resume), showChat; src/modules/shared/terminal.ts :: context
- kind: rationale
- logged: v0.19.0 · 2026-10-13

Claude writes Markdown; showing raw asterisks to people who never use a terminal was the main complaint. The renderer covers what Claude actually writes (paragraphs, bold, italic, inline code, lists, headings, tables, fences, rules), builds elements with `textContent` only, and turns links into underlined text with the URL as a tooltip, because a click must not navigate the desktop window. Streaming: a block is rendered once when a blank line closes it (fences are kept whole), so the only replacement is the live tail paragraph becoming its formatted self; verified under 4x CPU (only `fl-md-live` nodes removed). Preview images come back from the engine as saved files and load through `/api/files/thumb`. The meter reads `chat.usage`: memory is the prompt size of the latest step (input plus cache read and write), which is what fills the context window; "Chat" totals everything sent and written, which is large because each step re-reads the conversation from cache, and the tooltip says so in plain words. The handoff passes the Chat's session id to `claudecode.open` as `resume`; From Claude Code lists sessions from Claude Code's own project folder for formlit's agent folder.

### src/ui/shell.ts · filmstrip height and module picker (v0.19.0)
- refers-to: src/ui/shell.ts :: stripResizer, hiddenModules, setModuleShown, ShellLayout.stripH; src/modules/shared/workspace.ts :: module picker menu
- kind: explainer
- logged: v0.19.0 · 2026-10-13

The filmstrip's handle is absolutely positioned inside the filmstrip, so the filmstrip's grid keeps its two rows; heights are clamped to 72 to 320 px and go through `--fl-filmstrip-h`, the variable the app grid already used. Hidden modules only lose their picker button; their commands, shortcuts and Window menu items stay, and the last visible module cannot be hidden.

### Skin Tone in the Color Mixer, the picker, and slider thumbs off the layout path (v0.26.0)
- refers-to: src/modules/develop/panels.ts :: Color Mixer skin block; src/modules/develop/skin-tool.ts :: SkinPickerTool; src/modules/develop/index.ts :: develop.tool.skin; src/modules/develop/tools.ts :: WbPickerTool.down; src/styles/lit-develop.css :: .fl-sl-track container-type, .fl-sl-thumb translate
- kind: rationale, removed-bug
- logged: v0.26.0 · 2026-10-14

Skin Tone sits under Point Color: Pick, Skin Hue, Skin Range, and Hue, Saturation and Lightness Uniformity. Pick sets the hue from a click on the photo, and if all three uniformities are at 0 it starts Hue Uniformity at 50 so the pick visibly does something. The result goes in a toast, or stays in the drawer with Shift-click to keep picking.

Two layout shifts found while measuring, both fixed. (1) The White Balance selector, and the new skin selector built on it, closed the tool drawer when the engine replied, well after the click, so every panel below jumped up 113 px. The tool now closes within the click itself. (2) Slider thumbs were placed with `left`, so every value set from outside (a pick, Auto, a preset, undo) counted as a layout shift. The thumb now moves with the `translate` property in container units (`100cqw` of the track, which is now an inline-size container), so it never touches layout; hover scaling still composes. Checked: thumbs sit exactly at their fraction (Exposure -0.40 at 46.0 percent, Contrast -5 at 47.5, Highlights -50 at 25.0). After both fixes, a pick, a Lightness Uniformity change and the panel updates showed no layout shift and no page errors under 4x CPU and slow network.

### src/modules/shared/merge-dialog.ts and ai.ts · Focus Stack (v0.25.0)
- refers-to: src/modules/shared/merge-dialog.ts :: Kind focus, FOCUS_OPTS, ask; src/modules/shared/ai.ts :: photo.focusStack (Alt+Mod+M); src/app.ts :: Photo menu
- kind: rationale
- logged: v0.25.0 · 2026-10-14

Photo, Focus Stack reuses the merge dialog: Auto Align, Auto Crop and Create Stack (on by default, since the frames are rarely wanted beside the result), a shooting note, and the engine's 900 px preview. Verified under 4x CPU and slow network with a three-frame 16-bit TIFF bracket: the dialog opened with the three options ticked, the preview arrived sharp across the frame, Merge produced the 1519 x 1016 DNG stacked with its frames, the grid showed it, no page errors. Seen on the way: while the frames are still grouped in a stack the grid shows only the top frame and Focus Stack stays disabled with one photo selected, as it should.

### src/state/develop.ts and src/modules/develop/layers.ts · editing layers (v0.24.0)
- refers-to: src/state/develop.ts :: PHOTO_ONLY, Layer, layer, layers, layerable, target, read, selectLayer, editingName, value, set, patch; src/modules/develop/curve.ts :: get; src/modules/develop/layers.ts :: LayersPanel; src/modules/develop/index.ts :: panel placement; src/styles/lit-develop.css :: .fl-layer-*, .is-layer-editing
- kind: rationale
- logged: v0.24.0 · 2026-10-14

The develop session has an editing target, as in Capture One. With a layer selected, `value`, `set`, `patch` and `read` work on that layer's settings for layerable paths, falling back to the photo's value where the layer holds none (the engine's deep merge). Photo-only paths (white balance, crop, geometry, lens, noise reduction, profile, treatment, masks, layers) still edit the photo. So all the existing sliders, the curve (its getter now uses `read`) and the panels work on a layer without changes of their own. History labels start with the layer name. The Layers panel sits under the Histogram: a Photo row, one row per layer (eye, name, opacity), and for the selected layer Opacity, Mask (whole photo, Subject, Sky, Background, People, or any mask from the Masking tool, so brushes and gradients reach layers through it), Invert, Rename, Duplicate and Delete. New Layer goes through `develop.addLayer` after a flush, so the engine copies the settings; opacity, visibility, copied masks and deletion are `develop.patch('layers', ...)` writes, so they debounce and undo like any slider. While a layer is selected, a banner names it and the right column gets an accent edge, because the sliders look the same either way. Verified under 4x CPU and slow network on photo 5: New Layer selected itself with the banner and edge; typing +1.25 in Exposure changed the layer only, the photo staying at -0.40; Mask Subject and opacity 55 reached the engine; Back to Photo showed -0.40 again; a base Contrast of 15 left the layer's -5 alone; reselecting the layer showed +1.25; the preview lit the subject only; no layout shift, no page errors. Test layers and settings were removed afterwards.

### src/modules/develop/masks.ts · edge sliders and the Refine Edge brush (v0.23.0)
- refers-to: src/modules/develop/masks.ts :: Op, BITMAP_KINDS, sync (opList, add row), shapeControls (edge sliders), wireShapeControls (data-int); src/styles/lit-develop.css :: .fl-mask-comp .cv-seg; src/ui/icons-lit.ts :: maskRefine
- kind: rationale
- logged: v0.23.0 · 2026-10-14

An AI component shows Refine Edge (0 to 100), Shift Edge (-100 to 100) and Feather (0 to 100). They are written as whole numbers (`data-int`) under the history label "Mask Edge". The add row gains a Refine Edge Brush button that adds a brush component with op `refine` to the selected mask. A brush component after the first offers a fourth mode, Refine, and its hint says what painting does. With four modes the segment overflowed the 311 px column ("Refine" was clipped), so the modes now sit on their own row under a Component sub-heading, and the buttons may shrink with an ellipsis as a last resort. Verified under 4x CPU and slow network on photo 5: a Subject mask showed the three sliders; dragging Shift through 20, 40 and 60 kept the same slider element, with no nodes removed from the options; the engine stored refine 50, shift 60 and feather 35; Refine Edge Brush added "Refine Edge: Brush" with Refine selected, and one painted stroke reached the engine as a refine component with one stroke; the segment fit with no truncated label; no layout shift, no page errors. The test's masks were removed afterwards.

### src/modules/shared/captions.ts · code replacements and required fields in the window (v0.22.0)
- refers-to: src/modules/shared/captions.ts :: registerCaptions, warnMissing, fieldLabel; src/modules/shared/export.ts :: exportWith, library.exportPrevious; src/modules/library/inspect.ts :: run, DetailCache.forget; src/app.ts :: Metadata menu
- kind: rationale, removed-bug
- logged: v0.22.0 · 2026-10-14

Five Metadata menu commands over the engine's `codes.*`: Code Replacements (edit or create the active set, the delimiter, on or off), Choose Code Set (switch or delete), Import Code Replacements (a file path, since the window cannot read local files by itself), Required Fields (checkboxes for the 16 fields agencies ask for most, plus Refuse Export), and Check Required Fields. All use `askForm`, so no new dialog code. Export from the dialog or with Previous first asks the engine which photos miss required fields; with Refuse Export off it asks "Export them anyway?", with it on the engine refuses and its message is shown. The Metadata panel toasts `unknownCodes` after a save.

Found while testing: after a metadata edit the panel kept showing the text as typed, because `DetailCache` is keyed by the library revision and the panel re-read before the revision moved. That was invisible while the stored text always equalled the typed text; with codes the stored text differs. `run` now forgets the edited photos' cached details and reloads, so the panel shows the expanded caption. Verified under 4x CPU and slow network: the dialog listed the saved set (4 lines) and saved it; typing `=23= scores on the =bos= at =crypto= on {date} =zzz=` in Caption showed the full roster text and date in the panel, with a toast naming `zzz`; Required Fields saved Caption, Headline and City; Export with Previous on all 7 photos asked "7 of 7 photos are missing Headline (7), City (7), Caption (6). Export them anyway?"; no page errors.

### src/modules/library/cull-view.ts · the Cull view (v0.21.0)
- refers-to: src/modules/library/cull-view.ts :: CullView; src/modules/library/index.ts :: View 'cull', view.cull (K), setView, selectionChanged, onKey; src/styles/lit-library.css :: .fl-lib-cull, .fl-kw-chips; src/ui/icons-lit.ts :: viewCull
- kind: rationale, removed-bug
- logged: v0.21.0 · 2026-10-14

Phase 1 item 2 of the research plan: culling was the most-cited chore (S14, S16, S17, S19, S43) and pros named speed between frames and per-face eye and focus checks as why they pay for outside cullers (S32). The view walks the photos in burst order from `cull.groups`, not grid order, so each burst is reviewed together; Up and Down land on a burst's best frame. P, X and the ratings flag only the frame on screen (`photo.flag` with that one id, never the selection) and always advance, unlike the global auto-advance setting, because a cull pass is one decision per frame. Shift+P keeps the frame on screen as a pick, rejects the rest of its burst and jumps to the next burst. Speed comes from preloading: the previews two behind and five ahead are decoded off-screen through `Image.decode()`, and the Viewer swaps only decoded images, so the old frame stays until the new one is ready. Face tiles are CSS background crops of the same preview at 1.6 times the face box, so they cost no request. Every region has a fixed size (34 px head, 148 px face column, 84 px strip, 26 px key row, the best badge reserved with `visibility`), so moving between photos with and without faces changes nothing outside the view.

Verified under 4x CPU and a 150 ms, 200 KB/s network on the 7-photo test catalog. Bursts and best frames matched the engine. Frame to frame took 61 to 136 ms including the test's 10 ms polling. P picked and advanced; Shift+P picked one frame, rejected the other and moved on; the engine's flags matched the window. Escape returned to the grid. No page errors and no layout shift without input. The one slow step (about 1 s) came when keys were pressed every 80 ms faster than the emulated 200 KB/s link could deliver a 2560 px preview. Face tiles were checked with a synthetic face list written into one test photo, because the faces model download was refused in the test sandbox; the fixture was replaced by a real analysis afterwards.

Found while measuring: the Keywording panel's suggestion chips wrapped from one row to three as the active photo changed, pushing the Keyword Set and the next panel down by 52 px (a layout shift without input, in Loupe too). `.fl-kw-chips` is now a fixed three-row box (74 px), as Lightroom's 3 by 3 suggestion grid is.

### src/ui/shell.ts · filmstrip collapse, top or bottom, and the hidden-row fix (v0.20.0)
- refers-to: src/ui/shell.ts :: AREAS, ShellArea, ShellLayout.stripCollapsed, stripTop, stripResizer; src/styles/lit-shell.css :: --fl-strip-row, is-filmstrip-collapsed, is-filmstrip-top; src/ui/filmstrip.ts :: head buttons; src/app.ts :: view.filmstripCollapse, view.filmstripTop; src/modules/shared/workspace.ts :: filmstrip head menu
- kind: rationale, removed-bug
- logged: v0.20.0 · 2026-10-13

Bug found while adding this: the v0.19.0 handle writes `--fl-filmstrip-h` inline on `.fl-app`, and an inline custom property beats the `.is-filmstrip-hidden` rule that set it to 0, so after any resize F6 hid the filmstrip but left its row empty. The app grid now sizes the row from `--fl-strip-row`, which defaults to `--fl-filmstrip-h` and is overridden by the classes (28 px collapsed, 0 hidden); the inline height stays untouched, so expanding or showing again returns to the dragged height.

Collapse keeps the strip laid out at its full height inside a clipped 28 px box (`visibility: hidden`), so expanding never rebuilds or re-measures thumbnails: verified 0 nodes removed from the strip across collapse, reload and expand. Top or bottom is pure grid placement (explicit `grid-row` on the five shell children with the rows reordered), no DOM move, so the grid, its scroll and listeners survive the switch; the handle moves to the bottom edge and the drag direction flips. Both are areas in `formlit_layout` and fields in workspaces; Default resets them, Working with Claude collapses the filmstrip to give the dock room. Verified under 4x CPU and slow network: collapse button, reload, double-click on the header, move to top, resize from the top, right-click menu ticks, F6 with no empty row, Alt+F6, Default, no page errors.

### src/ui/shell.ts · layout in and out
- refers-to: src/ui/shell.ts :: ShellLayout, layout, applyLayout, saveAreas, LAYOUT_KEY
- kind: explainer
- logged: v0.18.0 · 2026-10-13

`layout()` reads the inline width and dock-height variables (null means the stylesheet default) and the hidden-area classes; `applyLayout` sets any subset, clamps widths to the resizers' 200 to 520 px, and writes the same keys the resizers write, so a workspace and a drag agree. Hidden areas are now persisted (`formlit_layout`) and restored in the constructor before first paint, so a restart opens the same layout with no jump.

### src/modules/shared/workspace.ts · workspaces
- refers-to: src/modules/shared/workspace.ts :: BUILTIN, registerWorkspace, workspaceMenu; src/app.ts :: Window menu
- kind: rationale
- logged: v0.18.0 · 2026-10-13

Built-in workspaces change only the layout (and Solo Mode where it is the point, as in Editing), never which panels are hidden or their order, so trying one never loses an arrangement; saved workspaces carry everything. Saved ones live in the engine's preferences so they survive a cleared browser and are shared by every window; each gets a command (`workspace.user.<slug>`) added when it is saved or loaded and removed when deleted, so the Window menu's Workspace submenu is plain command ids. Opening the dock goes through the existing commands (`agent.chat`, `view.terminal`) so the dock mounts its tabs as usual. A MutationObserver on the panel columns applies the saved order when a module mounts its panels, including Develop's, which mount after an await. Verified under 4x CPU and slow network: hiding, dragging, Solo Mode, all built-ins, save, apply, reload and reset, with no layout shifts and no errors.

### src/ui/icons-lit.ts · the AI icons
- refers-to: src/ui/icons-lit.ts :: agent, agentChat, aiChip; src/ui/shell.ts, src/ui/terminal-dock.ts, src/modules/develop/panels.ts
- kind: rationale
- logged: v0.18.0 · 2026-10-13

The owner asked for a better AI icon than the three-star sparkle. Candidates were drawn and compared at 14, 16, 24 and 48 px in the accent and text colours: a robot head, an orbit, a framing reticle and a node graph. The aperture was ruled out because Develop already uses one. The head and a matching speech bubble read clearly at 14 px and say "assistant" without sparkle clichés; Claude Code gets the head, Chat the bubble. Local-model features (Denoise, Build Depth) are not the agent, so they get a processor chip that says "runs on this computer". The vendored `sparkle` in `icons.ts` stays defined but unused.

## src/modules/shared/templates.ts, keyword-sets.ts, export.ts · templates {#shared-templates}

### src/modules/shared/templates.ts · template commands
- refers-to: src/modules/shared/templates.ts :: registerTemplateActions; src/app.ts :: buildMenus (Library, Metadata, Develop); backend/app/engine/cmd_templates.py
- kind: explainer
- logged: v0.11.0 · 2026-10-13

Library, New Shoot from Template (Alt+Shift+Mod+N) and New Smart Collection from Template; Metadata, Apply Metadata Template and Apply Keyword Set; Develop, Noise Reduction by ISO. Each fetches `template.list` for its kind before opening the shared form dialog, so the dialog opens complete, and the form's preview line shows the chosen template's description (or a keyword set's words). Results come back as one toast; collections and keywords appear through the engine's change events.

### src/modules/library/keyword-sets.ts · built-in sets from the engine
- refers-to: src/modules/library/keyword-sets.ts :: KeywordSets.render, loaded
- kind: rationale
- logged: v0.11.0 · 2026-10-13

The built-in keyword sets now come from the engine (one list for the window and agents). Until they arrive, a remembered set that is not loaded yet is kept as the select's only extra option instead of falling back to Recent Keywords, so the visible choice never swaps; checked under 4x CPU and a slow network, the selected text stayed the same throughout.

### src/modules/shared/export.ts · preset groups
- refers-to: src/modules/shared/export.ts :: syncAll
- kind: explainer
- logged: v0.11.0 · 2026-10-13

Each export preset row shows its group (General, Client Delivery, Print, Licensing, Web and Social, or User) and carries its description as the tooltip.

### src/modules/library/importer.ts, shared/photo-dialogs.ts · template lists before paint
- refers-to: src/modules/library/importer.ts :: fillTemplates, show; src/modules/shared/photo-dialogs.ts :: library.rename; src/modules/shared/templates.ts :: patternOptions
- kind: rationale
- logged: v0.12.0 · 2026-10-13

The import dialog's naming and folder selects and the Rename Photos template list come from `template.list` (cached per session by `patternOptions`). The import dialog awaits them before its first `open`, so the selects never change while visible; the old short lists remain as a fallback when the engine call fails, and an old entry is kept only when neither its pattern nor its label is in the engine list (so "Shoot Name - Filename" appears once). Filename (unchanged) maps the engine's `{name}` to the dialog's empty pattern, which stored import preferences use.

## src/modules/develop/view.ts, index.ts · Reference View {#develop-reference}

### src/modules/develop/view.ts · the reference pane
- refers-to: src/modules/develop/view.ts :: Compare 'ref', setReference, refRect, renderReference, referenceChanged; src/styles/lit-develop.css :: .fl-dv-before.is-empty
- kind: rationale
- logged: v0.12.0 · 2026-10-13

Reference View reuses the Before pane: the active photo takes the right half exactly as in Left/Right, and the left half fits the reference photo by its own aspect, rendered with its stored settings at the pane's size. Whenever the pane's content changes source (into or out of Reference View, or a new reference) it is marked `is-empty`, which hides its image until the right render has decoded; so neither a stale Before image nor the previous reference is ever shown, and the pane is resized only after the new image is in (checked under 4x CPU: the pane became visible only with the new image). The tags read Reference and Active. The reference re-renders when its revision changes and the active photo renders.

### src/modules/develop/index.ts · commands and the agent hook
- refers-to: src/modules/develop/index.ts :: develop.referenceView, develop.setReference, develop.matchReference, showReference; src/app.ts :: agent.show
- kind: explainer
- logged: v0.12.0 · 2026-10-13

Reference View (Shift+R, and Reference in the compare segment) uses the active photo as the reference when none is set and says so; Set as Reference Photo fixes the active photo; Match Look to Reference runs the engine's `develop.match` from the reference to the selected photos (not the reference itself) and reports the distance before and after. `show_in_window` with `reference` reaches `showReference` through the `agent.show` event so an agent can put a match and its reference side by side.

### src/modules/develop/index.ts · the reference follows its edits
- refers-to: src/modules/develop/index.ts :: mount (photos.changed); src/modules/develop/view.ts :: referenceChanged
- kind: rationale
- logged: v0.13.0 · 2026-10-13

When the engine reports `develop` or `edited` changing on the reference photo (an agent, Sync, undo, or the person editing it in another window), the reference pane re-renders at once instead of waiting for the active photo's next render. It swaps in place without hiding the pane, so an update never blanks it (checked under 4x CPU: hidden 0 times).

### src/ui/preferences.ts · identity
- refers-to: src/ui/preferences.ts :: identity; backend/app/engine/cmd_templates.py :: identity, keep_identity
- kind: explainer
- logged: v0.13.0 · 2026-10-13

### src/ui/chat-pane.ts, terminal-dock.ts · the Chat tab
- refers-to: src/ui/chat-pane.ts :: ChatPane; src/ui/terminal-dock.ts :: showChat, closeChat, select, send, syncAsk; src/modules/shared/terminal.ts :: agent.chat; src/styles/lit-dock.css :: .fl-chat*
- kind: rationale
- logged: v0.15.0 · 2026-10-13

The Chat tab is a dock tab without a terminal: `select('chat')` hides the terminals and shows the pane, and the Ask line sends to the chat when the Chat tab is on (to the Claude Code tab otherwise). The pane only ever appends: a user bubble on `chat.start`, text appended to the current text node on each `chat.delta`, a chip per `chat.tool` whose class changes on `chat.toolDone`, and a meta line on `chat.done`; nothing already shown is rebuilt (checked under 4x CPU: no nodes removed from the log while an answer streamed, no layout shifts). It scrolls only when the reader is already near the bottom. New Chat is the one place the log is cleared. A user bubble holds the typed words and, when photos are selected, a muted note ("with 7 selected photos") from the dock's `note()`; the ids themselves go only to Claude through `context` (v0.16.0). A tool chip with `photos` is followed by a strip of up to eight thumbnails (`thumbUrl`, so they share the grid's cache) and a +N count; ids the window does not hold are skipped. One delegated click handler on the log selects the strip's photos (`library.select` only, then add) and makes the first active (v0.17.0). `chat.state` restores the transcript once, when the tab first opens after a reload.

Preferences, AI agents also holds Claude Code in formlit (v0.14.0): a status line from `claudecode.status` and three fields (Starts in folder, Claude Code program, Start with message) saved on change, each save refreshing the status line so a bad path is reported at once.

Preferences, Metadata holds Creator, Email and Website: the `identity` preference the metadata templates, New Shoot from Template and agents use for {creator}, {email} and {url}. Saved on change as one object (an emptied field clears it); a field being typed in is not overwritten when the stored values arrive.

---

## src/ui/terminal-dock.ts, src/modules/shared/terminal.ts {#ui-terminal-dock}

### src/ui/terminal-dock.ts · ported from Format
- refers-to: src/ui/terminal-dock.ts :: TerminalDock; Format frontend/src/ui/terminal-dock.ts
- kind: explainer
- logged: v0.7.0 · 2026-10-12

One xterm.js terminal per tab, each mounted once into its own host and shown or hidden with `hidden`, never rebuilt; tabs and hosts are appended and removed one node at a time. The dock adds Format's pieces formlit lacked: a Claude Code button, an Ask line, a resize handle, and an empty note when every tab is closed. Colours come from the theme tokens at mount time. `ensure` adopts tabs the engine already has (a reload keeps its shells), and the socket replays the scrollback first.

### src/ui/terminal-dock.ts · keys inside a terminal
- refers-to: src/ui/terminal-dock.ts :: isToggle, constructor (stage keydown), mount (attachCustomKeyEventHandler); src/app.ts :: onKey
- kind: warning-context
- logged: v0.7.0 · 2026-10-12

xterm types through a textarea, and `App.onKey` still runs shortcuts that include Mod while focus is in a text field, so Ctrl+C, Ctrl+A or Ctrl+Z in a shell on Linux and Windows would have run formlit's Copy Settings, Select All or Undo. The stage stops keydown from bubbling to the document for every key except Mod+J, and xterm is told to ignore Mod+J, so the shell owns its keys and the one dock shortcut still hides it.

### src/ui/terminal-dock.ts · Ask line
- refers-to: src/ui/terminal-dock.ts :: send, claude; src/modules/shared/terminal.ts :: context
- kind: rationale
- logged: v0.7.0 · 2026-10-12

The Ask line goes to `claudecode.open` with the text as `prompt`: the engine starts Claude Code with it as the first message, or types it into the running tab followed by Enter. The selected photo ids are appended on the same line in parentheses (up to 200), because a line break typed into Claude Code's input would not reliably stay part of one message.

### src/ui/shell.ts · the dock row
- refers-to: src/ui/shell.ts :: SHELL (.fl-dock), setDock, dockResizer; src/styles/lit-dock.css; src/styles/lit-tokens.css :: --fl-dock-h, --fl-dock-open-h
- kind: rationale
- logged: v0.7.0 · 2026-10-12

The dock is a fixed row of the app grid between the filmstrip and the status bar, sized by `--fl-dock-h`: 0 while hidden, `--fl-dock-open-h` (280 px by default, dragged and remembered in `formlit_dock_h`) while open. Opening it shrinks the main area in one step at the person's request and nothing else moves; the dock's own rows (head, stage, Ask line) are fixed heights so the terminal never jumps when tabs come and go. Verified under 4x CPU throttling and a 150 ms, 200 KB/s network: no layout shift without input and no node removed from the dock while opening, typing, hiding and starting Claude Code.

---

## Files with no entries {#no-entries}

No logged content at v0.1.0 for the remaining files in the map, including `app.ts`, `main.ts`, `second.ts`, `second-modes.ts`, `io/*`, `state/*`, the rest of `modules/library`, `modules/develop`, `modules/output` and `modules/shared`, the rest of `ui/`, and the remaining `lit-*.css` sheets.
