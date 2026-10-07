# HASHOUT_LOG · frontend · formlit

Living log of all comment content, explainers, rationale, TODOs and removed code for the interface. Source files stay comment-free (vendored formvis files keep their upstream headers); everything else they would have said lives here, indexed. Read this first, then edit code surgically.

Current build version: v0.3.0
Last updated: 2026-10-07 · the Navigator keeps one 3:2 box and maps its rectangle onto the letterboxed picture, the dev server drops font preloads

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
    │   ├── shell.ts               the frame, mounted once
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
    │   ├── preferences.ts         Preferences dialog
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
        └── lit-modules.css        output modules, pages, publish, comments, plug-ins
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
- [src/styles/lit-tokens.css](#styles-lit-tokens)
- [vite.config.ts](#vite-config)
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

---

## src/modules/develop/left.ts {#develop-left}

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

---

## Files with no entries {#no-entries}

No logged content at v0.1.0 for the remaining files in the map, including `app.ts`, `main.ts`, `second.ts`, `second-modes.ts`, `io/*`, `state/*`, the rest of `modules/library`, `modules/develop`, `modules/output` and `modules/shared`, the rest of `ui/`, and the remaining `lit-*.css` sheets.
