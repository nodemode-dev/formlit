---
name: develop-artist
description: "Owns how photos look in formlit over MCP: white balance, tone, presence, colour mixer and grading, detail, lens corrections, geometry, AI and gradient masks, presets, sync across a shoot, and the computational tools (denoise, super resolution, HDR and panorama merges, upright). Load for any request to edit, fix, grade, brighten, warm, match or batch-develop photos."
---

# Develop Artist

## Purpose

Make photos look the way the person asked, proposing every change with a preview before committing it, and keeping a shoot consistent. Hands back the settings applied per photo and the previews that confirm them.

## Preconditions

Photo ids from catalog-keeper (or cull-assistant's picks). The photo has been looked at once with `get_preview`.

## Procedure

1. Read the photo: `get_photo` for camera, ISO, lens and existing settings. Raws open with the Camera Look profile (`fl.camera`), matched to the camera's own JPEG, so start from there rather than fighting it.
2. Translate the request into ids with `references/develop-ids.md` and the recipes in `references/look-recipes.md`. Words map to settings: "too dark" is `light.exposure` plus `light.shadows`; "washed out" is `light.blacks` down and `light.contrast` up; "too orange" is `wb.temp` down.
3. Propose: `get_preview` with `values` and `max_size` 1024. Compare with the current look (`get_preview` without values) and, for big changes, the original (`before: true`).
4. Commit with `develop_set`. Use `delta: true` for nudges so existing values are respected.
5. Local work: `add_ai_mask` for sky, subject, background, people or depth with an `adjust` object; `add_gradient_mask` linear for skies and foregrounds, radial for spotlights and vignettes (`invert: true` adjusts outside the ellipse). Masks are additive; read `get_develop` to see them.
6. Colour grading, mixer bands and parametric curve regions are plain ids for `develop_set` (`grading.shadows.hue`, `grading.shadows.sat`, `mixer.blue.sat`, `curve.highlights`). Structured settings go through `develop_patch`: `{"treatment": "bw"}` for black and white, `{"crop": {"rect": [0.05, 0.0, 0.95, 1.0], "angle": 1.5}}` in normalized coordinates, masks and curve points.
7. Consistency across a shoot: develop the hero frame, then `sync_settings` from it. Without `groups` it copies everything except crop, masks, spots and red eye; with groups it copies only those (`["whiteBalance", "basicTone", "presence"]` for exposure and colour only). Group names are in `references/develop-ids.md`.
8. Computational: `denoise` (high ISO raws, 50 is a safe amount), `super_resolution` (small crops for print), `merge_hdr` (bracket ids, deghost `medium` when anything moved), `merge_panorama` (overlapping frames), `auto_straighten` and `upright` for architecture. Each writes a DNG stacked with its sources; develop the DNG afterwards.
9. Run `checklists/before-after.md`.

## Gate

Done when every changed photo has an after preview that was looked at, and the checklist holds.

## Hands back

Per photo: the values set, masks added, presets applied, and new DNG ids from computational tools.

## Owned resources

- `references/develop-ids.md` every setting id with range and default, local adjust keys, white balance presets and crop aspects
- `references/look-recipes.md` starting values for common requests
- `checklists/before-after.md` the checks before calling a look done
