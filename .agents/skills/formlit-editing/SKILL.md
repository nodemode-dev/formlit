---
name: formlit-editing
description: Cull, develop and deliver photos in formlit, the local Lightroom alternative, through its MCP server. Use whenever the person wants photos imported, rated, flagged, culled, keyworded, geotagged, developed (exposure, white balance, masks, presets, denoise, HDR or panorama merges) or exported, printed, made into a book, slideshow or web gallery, and the formlit tools (find_photos, get_preview, develop_set, export_photos and the rest) are available or formlit is named. Also use when a formlit tool fails and the next step is unclear. Not for changing formlit's own source code (use formlit-harness) and not for layered compositing (formvis).
---

# Working with photos in formlit

formlit is a photo library and raw developer running on this computer. Its MCP server (named `formlit`) works on the catalog directly, so the tools run whether or not the window is open, and every change is an ordinary undoable step the person sees in Library and Develop. These tools are the hands; this skill is how to use them well.

Work in small verified steps. Ids come from `find_photos`; looks come from `get_preview`. A develop change is only right once the preview shows it.

## Before anything

1. `get_catalog`: folders, collections and keywords with their ids, and the photo count.
2. `find_photos` with a `source` (`{"kind": "folder", "id": 3}`, `{"kind": "previousImport"}`, `{"kind": "collection", "id": 7}`) and a `filter` (`{"rating": 3, "ratingOp": ">="}`, `{"flags": ["pick"]}`, `{"text": "beach"}`).
3. `get_preview` on one or two photos before changing anything.

The server's `culling_workflow` and `develop_strategy` prompts hold the full decision trees; `references/tools.md` lists every tool with its parameters.

## Workflow 1: cull a shoot

1. `import_photos` with absolute folder paths when the photos are not in the catalog yet.
2. `analyze_culling` on the shoot's ids: sharpness, exposure, faces and near-duplicate groups are scored; nothing visible changes.
3. `apply_culling` with `pickBest: true`; add `rejectBlurry` and `rejectDuplicates` only when the person wants rejects marked.
4. Spot-check picks and rejects with `get_preview`; correct with `set_flag`, `set_rating`, `set_label`.
5. `create_collection` with the picks so they are easy to find again. Nothing is ever deleted from here.

## Workflow 2: develop a look

1. `get_photo` for camera, lens and the current settings; `auto_tone` for a starting point when the photo has no edits.
2. Propose with `get_preview` and `values` (for example `{"light.exposure": 0.4, "light.highlights": -40}`): it renders without saving. Commit with `develop_set` when it looks right.
3. Local work: `add_ai_mask` with `kind: "sky"` and `adjust: {"exposure": -0.5, "saturation": 15}`, or `add_gradient_mask` for a graduated sky or a radial spotlight.
4. A whole shoot: develop one photo, then `sync_settings` from it to the others. Without `groups` it copies everything but crop, masks, spots and red eye; `groups: ["whiteBalance", "basicTone", "presence"]` copies only exposure and colour.
5. Presets: `list_presets`, then `apply_preset` with an `amount` (100 is the preset as made).
6. Noise and detail: `denoise` writes an enhanced DNG beside the raw and stacks it; develop that DNG from then on.

Setting ids and ranges are in `get_develop_controls`. The ones used most: `wb.temp`, `wb.tint`, `light.exposure`, `light.contrast`, `light.highlights`, `light.shadows`, `light.whites`, `light.blacks`, `effects.texture`, `effects.clarity`, `effects.dehaze`, `color.vibrance`, `color.saturation`, `detail.sharpenAmount`, `detail.nrLuminance`.

## Workflow 3: deliver

- Files: `export_photos` with a preset (`builtin.web` 2048 px JPEG, `builtin.full`, `builtin.tiff` 16-bit ProPhoto, `builtin.print` 300 ppi Adobe RGB, `builtin.original`, `builtin.dng`) and an absolute `folder`. Settings override any part of a preset.
- Paper: `print_pdf` with `settings` such as `{"rows": 4, "cols": 3, "caption": {"on": true, "field": "fileName"}}` for a contact sheet.
- A book: `make_book` with a title; the PDF lands in the Exports folder unless a `path` is given.
- Motion: `export_slideshow` as MP4 (ffmpeg on the computer) or PDF.
- The web: `export_web_gallery` writes an `index.html` folder.
- `show_in_window` with a module and photo lets the person see the result in the window.

## Things that matter

- Every mutating tool is one undo step; `undo` reverses the last one.
- Paths are absolute on the person's computer; `~` works.
- Long jobs (import, AI, export) wait until done and return the written paths.
- Deleting files and switching catalogs are refused here on purpose: the person does those in the window.
- `run_command` reaches every engine command (`list_commands` shows them) when no curated tool fits.

## When something fails

| What you see | What it means | What to do |
| --- | --- | --- |
| No formlit tools at all | The MCP server is not connected in this client | Ask the person to run `./formlit agents install` in the formlit folder, or approve the project's MCP server, then restart the client |
| "The formlit engine is not running" | The engine could not be started | Ask the person to run `./formlit boot` (or open the formlit app), then retry |
| "needs the ... model" | An AI model is not installed yet | Run `run_command` with `ai.download` and the model id, or ask the person to install it in Preferences |
| "No photo with id" | A stale id | `find_photos` again |
| An export wrote nothing | Every file existed and `existing` was skip | Pass `settings.destination.existing` as `unique` or `overwrite` |

## Setup, for the person

In the formlit folder: `./formlit agents install` registers formlit with Claude Code, Codex and Cursor for their user account. Inside the repository nothing is needed: `.mcp.json`, `.cursor/mcp.json` and `.codex/config.toml` point at `./formlit mcp`, which starts the engine when it is not running.
