# Changelog

All notable changes to formlit. Versions are `v*.*.*`; each release lists what it added, what it fixed and what is not verified yet.

## v0.13.0 · 2026-10-13

### Added

- **Preferences, Metadata: Creator, Email and Website.** These are the details the metadata templates, New Shoot from Template and agents fill into copyright and licence text. Until now they were only remembered from the first use.
- **`formlit.bat claude` on Windows:** Claude Code in the terminal with formlit's tools attached, the twin of `./formlit claude`. It goes through a new `setup/claude_launch.py`, which works on every platform.

### Fixed

- **The reference updates as soon as it is edited.** In Reference View it used to refresh only when the photo being edited re-rendered. It now re-renders when its own settings change from anywhere: an agent, Sync, undo, or another window.

## v0.12.0 · 2026-10-13

This release closes the two gaps v0.11.0 left open: Reference View, and the import and rename dialogs' template lists.

### Added

- **Reference View in Develop** (Shift+R, Reference in the compare buttons, Develop, Reference View). A fixed reference photo sits on the left and the photo you are editing on the right, as in Lightroom Classic. Set as Reference Photo fixes the active photo. Match Look to Reference fits the selected photos to the reference with the engine's match and reports how close they got. The reference pane shows only once the right image has loaded, so it never flashes an old Before image or the previous reference.
- **`show_in_window` takes `reference`**, so an agent can open Reference View with a match result and its reference side by side.
- **Full template lists in the window:**
  - The import dialog's file naming offers all 17 filename templates and its Organize list all 8 folder templates. The lists are in place before the dialog first appears.
  - Rename Photos offers the same 17 filename templates.

## v0.11.0 · 2026-10-13

This release turns professional workflows into templates you can run. Lightroom's template families are now built in: filename templates, metadata presets, keyword sets, smart collections and export presets. Shoot recipes tie one of each to a genre and set up a whole job in one step, in the window or for an agent. File facts in the templates come from a verified-sourcing pass on primary sources: creativecommons.org, Adobe Stock and Shutterstock contributor pages, Canopy and Unlock MLS, Mpix, Bay Photo and WHCC, and Instagram's help. Single-source claims are recorded as such.

### Added

- **Shoot recipes:** wedding, portrait, headshots, event, news and sports, landscape, real estate, product, concert, stock, family and night sky.
  - Library, New Shoot from Template (Alt+Shift+Mod+N), or the `setup_shoot` tool / `workflow.setupShoot` command, makes a collection set named for the shoot. It holds All Photos and five stage smart collections limited to it: Picks, To Edit, Edited, Portfolio and Rejects.
  - All of it is one undo step.
  - Given card paths, it also imports with the recipe's folder and file naming, metadata template, keyword set and previews, then applies noise reduction by ISO when the recipe calls for it.
  - It returns the recipe's export presets and workflow prompt.
- **Templates (`template.list`, `list_templates`, `apply_template`):**
  - 17 filename templates.
  - 8 folder templates.
  - 16 metadata templates: all rights reserved, the six Creative Commons 4.0 licences and CC0 with their deed links, editorial, wedding client, commercial, real estate, event, portfolio, stock, and clear rights. Placeholders are filled from remembered creator, email and website details. A template whose copyright would be half written is refused.
  - 15 keyword sets.
  - 23 smart collection templates, including Lightroom's Colored Red, Five Stars, Past Month, Recently Modified and Without Keywords.
  - In the window: Metadata, Apply Metadata Template and Apply Keyword Set; Library, New Smart Collection from Template. The Keywording panel's keyword set picker now offers all 15 sets.
- **Noise reduction by ISO** (`develop.noiseByIso`, the `noise_by_iso` tool, and Develop, Noise Reduction by ISO), in place of Lightroom's ISO adaptive presets.
  - Each photo gets the Noise by ISO preset for its own ISO, touching only Detail.
  - Photos under ISO 800, or with no ISO recorded, are counted and left alone.
- **10 more export presets, 18 in all, grouped in the Export dialog:**
  - Client Gallery (2048 px, small signature) and Proofs (1200 px, centred PROOF watermark).
  - Print Lab (sRGB JPEG, 300 ppi) and Archive Master (16-bit TIFF, Adobe RGB).
  - Stock Agency and News Filing.
  - Real Estate MLS (3000 px, under 6 MB), Instagram (1080 px wide), Blog and 4K Display.
- **Seven more workflow prompts, 17 in all:** `job_from_template`, `concert_workflow`, `stock_workflow`, `astro_workflow`, `wildlife_workflow`, `social_batch` and `catalog_maintenance`. `client_delivery` now names the new export presets.
- **The driving skill:**
  - A "Start a job from a template" section.
  - A generated `references/templates.md` listing every recipe, preset and template.
  - Two evaluations (14 and 15).
- **Counts:** 61 tools and 238 commands.

### Fixed

- **"Shoot Name - Filename" at import:** the window's naming option uses `{shoot}`, which was never filled at import, so files were named `-IMG_0001`. The custom text now fills both `{custom}` and `{shoot}`.

### Not yet in formlit

- Reference View (a fixed reference photo beside the one being edited); `match_look` does the matching. Added in v0.12.0.
- The import dialog's naming and folder lists still show their original short lists, and so does Rename Photos; the full filename and folder template lists are available to agents through `list_templates` and `apply_template`. Fixed in v0.12.0.
- Meta's own feed and Story sizes could not be read from Meta's pages, so there are no 4:5 or 9:16 export presets yet.

## v0.10.0 · 2026-10-13

This release covers how professionals work in Lightroom and how formlit does the same. A verified-sourcing pass covered the end-to-end workflow, genre workflows, and batch consistency and output, using Adobe documentation, Julieanne Kost, Lightroom Killer Tips, Lightroom Queen, working pros in Fstoppers, PetaPixel, DPReview, Digital Camera World, SLR Lounge and PPA, and the AP and NPPA ethics codes. It also brings the built-in presets to 300.

### Added

- **Ten workflow prompts on the MCP server**, each mapped to formlit's tools and citing its sources:
  - The new ones: `pro_ingest_and_cull`, `wedding_event_workflow`, `portrait_session_workflow`, `landscape_workflow`, `news_sports_workflow` (with the AP and NPPA editing limits), `real_estate_workflow`, `product_workflow` and `client_delivery`.
  - The existing ones: `culling_workflow` and `develop_strategy`.
- **Professional ingest through `import_photos`:** Copy as DNG, folder and rename templates, a copyright metadata preset, a develop preset, keywords, a collection, a second copy, duplicate skipping and preview building. The engine could already do all of this; the tool now exposes it.
- **`refine_photos`** and the window's Library, Refine Photos (Alt+Mod+R), backed by a new `library.refine` command. As in Lightroom, unflagged photos become rejects and picks become unflagged, for the next culling pass.
- **New tools for existing engine features:** `match_exposures` (Match Total Exposures), `virtual_copy` and `snapshot`. `find_photos` documents its field operators (`iso>=3200`, `camera:`, `lens:`). That makes 57 tools and 231 commands.
- **67 more presets, 300 in 54 groups.**
  - Wedding Signature Base with Indoor and Night variants: pros keep one look plus lighting variants.
  - Noise by ISO steps: pros fix one frame per ISO level and sync noise only.
  - Documentary News Neutral presets that stay within news ethics.
  - New groups: Headshot, Real Estate, Event, Fashion, Fine Art, Street, Automotive, Family and Interiors.
  - The Warm Vibrant Landscape grade (after Christian Mohrle), and more film, toning, cinematic, portrait and adaptive presets.
- **The driving skill gains `references/pro-workflows.md`:** a Lightroom-to-formlit mapping and genre steps with a source on each claim, single-source claims flagged and gaps listed. Two new evaluations: news ethics and a professional ingest and cull.

### Fixed

- **Match Total Exposures used the window's active photo as its reference even when it was not one of the given photos.** It now uses the first given photo unless the active one is among them, and its error names what is missing.

### Not yet in formlit

- Reference View (a fixed reference beside the photo being edited); `match_look` does the matching.
- ISO adaptive presets.

## v0.9.1 · 2026-10-13

This release checks that subject isolation with separate grading is formlit's own capability: local models, formlit's engine and formlit's renderer. It also checks the local models themselves.

### Verified

- **Subject isolation and separate grading run entirely in formlit.** Driven only through the engine's HTTP API, with no agent involved:
  - `develop.match` set the overall moody look.
  - U2-Net isolated the subject in 1.2 s (28.6 percent of the frame).
  - A subject mask with a warm local grade and a background mask with a cool one were stored as develop settings and rendered by formlit's pipeline.
  - A real Claude Code session did the same through formlit's tools in 5 calls and 15 s, and the masks it asked for are in the catalog.
- **Every pinned model file matches its source.** That is 15 files across 9 models. `subject` and `people` were downloaded through formlit's installer and their SHA-256 matched the pins. The other 13 files match the SHA-256 that Hugging Face publishes at the pinned revisions. Licences were checked on the model cards: U2-Net Apache-2.0, sky segmenter MIT, Depth Anything V2 Small Apache-2.0, SAM 2.1 Apache-2.0, LaMa Apache-2.0, Real-ESRGAN BSD-3-Clause, YuNet MIT, SFace Apache-2.0.

### Fixed

- **People-part masks came back empty without a word when the face model was missing.** Hair, face skin, eyebrows, eyes, lips and teeth are placed from face boxes; without YuNet they returned 0 percent coverage and the mask was still added. Those parts now require the `faces` model and say how to install it.
- **Empty masks are refused.** Every AI mask result reports its coverage, and a mask that covers nothing is not added.
- **The mask tool did not mention its local colour grade.** `add_ai_mask` now documents `colorHue`, `colorSat`, a local `curve`, and which model each kind runs. The driving skill has a recipe for isolating and grading a subject, and a table of the local models and what needs them.
- **Real-ESRGAN was fetched from a moving `main` branch.** It is now pinned to revision 107475e.

### Not verified yet

- The people-part masks with the face model installed: the test machine cannot reach the face model's download hosts.

## v0.9.0 · 2026-10-13

Agents now finish a look in a handful of calls. They can copy a reference photo's look in one call, and there are 66 more presets, 233 in all.

### Added

- **`match_look`** (MCP) and `develop.match`: fits each target to a reference photo as developed, in about a second. It renders and measures over several internal rounds, adjusting exposure, contrast, highlights, shadows, whites, blacks, saturation, white balance and colour-mixer saturation and luminance. It returns the changes and a distance before and after, takes `strength`, `tone`, `color` and `apply: false` for a proposal, and needs no AI model. On the example pair (a vivid painting and its overcast grade) the distance fell from 95 to 12.
- **One call instead of two.**
  - `develop_set`, `develop_patch`, `apply_preset`, `sync_settings` and `match_look` take `report: true` and return a compact measurement of each changed photo.
  - `get_preview` takes `analyze: true` and measures the same render.
  - `analyze_photo` takes `ids` for one line per photo plus the spread across a set.
  - `get_preview` defaults to 768 px and the skill uses 512 for checks.
- **`save_preset`** stores a photo's look as a user preset.
- **`add_ai_mask`** takes `parts`: people (face skin, body skin, eyebrows, sclera, iris, lips, teeth, hair, clothes, one person by index) and landscape (sky, water, vegetation, mountains, architecture, natural and artificial ground), several in one mask.
- **66 more presets, 233 in 43 groups.**
  - New groups: Weather (including Overcast Calm, measured from the example pair), Illustration for digital art, Toning (cyanotype, platinum, gold, duotones), Aerial, Macro and Flowers, Wildlife, Pets, Sports, Product, Wedding, Newborn, Social, HDR and Utility (clear grading, curve, mixer or effects).
  - New film looks: Ektar, Kodachrome, Tungsten Night, HP5 and Superia styles.
  - More cinematic, portrait and adaptive presets.
- The driving skill has a Work efficiently section: batch values, `report` on writes, `match_look` for references, numbers before pictures, set checks with `ids`, and stop when done. It also covers selective colour through the mixer without any AI model, and gains two evaluations.

### Fixed

- **`run_command` accepted only `params` as an object.** An agent that sent `args`, a JSON string or flat keys got four failures in a row. It now accepts all of those, and `id` when `command` is missing.
- **Missing-model refusals now name the exact install call** and tell the agent to fall back to the mixer or a gradient instead of retrying.
- In a real Claude Code run of "make photo 2 look like photo 1 and keep the hair richer", formlit calls fell from 13 to 4 and the time from 28 s to 11 s.

### Not verified yet

- `match_look` statistics copy tone and colour balance, not selective grades: a reference that keeps one colour saturated while greying the rest is approximated.
- People-part masks need the people model, which could not be downloaded on the test machine. Landscape parts were exercised.

## v0.8.0 · 2026-10-13

Agents can now measure a photo, find and preview the right preset, and edit with a sourced understanding of every develop control. There are five times as many built-in presets.

### Added

- **`analyze_photo`** (MCP) and `develop.analyze`: measures the photo as developed, or with proposed values or a preset without saving. It reports luminance percentiles and spread, the share in Adobe's five tonal bands, clipping per channel, saturation, the cast of near-neutral pixels and each colour-mixer band. Findings suggest control ids and starting values (clipped highlights, crushed or missing blacks, under- or overexposure, low or very high contrast, casts, near-clipped colour, high ISO). 51 MCP tools, 229 commands.
- **Preset previews and search.** `get_preview` takes `preset` and `amount`; `list_presets` takes `query` and `group` and returns a description and tags for every preset.
- **134 new built-in presets, 167 in all, in 29 groups**, after Adobe's preset categories:
  - Portrait, Cinematic, Film-Inspired, Vintage, B&W, Seasons, Landscape and Golden Hour.
  - Night and Astro, Travel, Food, Urban Architecture, Concerts, Lifestyle, Moody, Futuristic and Underwater.
  - Curves, Detail, Effects and Color Fixes.
  - Adaptive sky, subject, portrait (eyebrows, lips, hair) and landscape (vegetation, water, mountains, architecture).
  Their values follow the researched editing practice and real exported presets.
- **The driving skill now teaches editing.** `formlit-driving` has a measure, propose, check and commit loop. Its new `references/editing-guide.md` covers tone, presence, curves, white balance, colour mixer, colour grading, calibration, black and white, detail, effects, profiles and masks, mapped to formlit's ids. Every claim cites Adobe documentation or a photography publication, and single-source numbers are flagged. `references/presets.md` lists every built-in and is generated by `./formlit agents sync`. Two new evaluations cover a measured fix and a preset previewed before it is applied.

### Fixed

- **Twelve original built-in presets pointed at profiles that do not exist** (`fl.film.*`, `fl.cine.*`, `fl.bw.sepia`, `fl.bw.selenium`, `fl.bw.ir`, `fl.muted.*`). Unknown profiles are ignored, so Sepia Tone and Selenium Tone did nothing and the rest only applied their extra sliders. They now carry explicit settings.
- **A preset at less than 100 percent changed colour-grading hues.** At 50 percent, an orange tint at hue 40 became hue 20. Hues now stay fixed and only the strength scales. Point curves now ease toward straight with the amount instead of applying at full strength.
- The develop-artist recipes in `formlit-harness` named the missing profiles and used wheel saturation 30 for teal and orange; they now use profiles that exist and the sourced 15 to 20.

### Not verified yet

- Adaptive presets preview without their masks until the AI bitmaps for that photo exist.
- The analysis thresholds were tuned on synthetic test images, not a library of real photos.

## v0.7.1 · 2026-10-12

### Fixed

- **`./build_app` stopped on macOS with `error[E0463]: can't find crate for phf_macros`, twice.** The release profile's `strip = true` also applied to proc macros and build scripts, so cargo built `phf_macros` with `-C strip=symbols`; on macOS that strips the symbol rustc looks for when it loads a proc macro, and `phf` then cannot find the crate it just built. `[profile.release.build-override]` now sets `strip = false` and `debug = false`, as Format's shell does; the app binary is still stripped.

### Not verified yet

- The full macOS build after the fix: confirmed only that cargo no longer passes a strip flag to `phf_macros`.

## v0.7.0 · 2026-10-12

formlit now has a live terminal inside the window, and Claude Code runs in it already connected to formlit, the way Format runs it. One command builds the desktop app.

### Added

- **Terminal dock.** Window, Show Terminal (Ctrl or Cmd+J) opens a dock under the filmstrip with tabs of real login shells over a pseudo-terminal (ptyprocess, pywinpty on Windows) streamed to xterm.js through a WebSocket at `/api/terminal/{id}`. New Terminal, Restart and Hide are in the dock header, the height is draggable and remembered, and the shells keep running while the dock is hidden. Shells get `FORMLIT_ENGINE_URL` and `FORMLIT_MCP_URL`, and `./formlit` on the PATH in a source checkout.
- **Claude Code in formlit.** The sparkle in the title bar, Help or Window, Claude Code (Ctrl or Cmd+Shift+J), starts the person's own Claude Code sign-in in a dock tab, in `~/Formlit/Agent`, with formlit's MCP server attached over HTTP and `mcp__formlit` allowed. The Ask line under the dock sends a request with the selected photo ids, starting Claude Code or typing into the running session.
- Commands `terminal.open`, `terminal.list`, `terminal.write`, `terminal.read`, `terminal.resize`, `terminal.restart`, `terminal.close`, `claudecode.status` and `claudecode.open` (228 commands in all).
- `./build_app`: one shebang script that builds the desktop app from a fresh clone on macOS and Linux (tool checks, Rust through rustup when missing, install, window, frozen sidecar, bundle, a disk image and a copy in Applications on macOS, a .deb on Linux), logged to `build_app.log`. `./formlit desktop build` runs it.
- `./formlit claude` starts Claude Code in the person's own terminal with formlit attached over stdio.

### Fixed

- **Claude Code saw no formlit tools.** On the 2026-07-28 protocol, `tools/list` and `prompts/list` lacked the `ttlMs` and `cacheScope` fields that protocol requires, so Claude Code 2.1 rejected both lists and the formlit server connected with nothing in it. Both lists now carry them; 2025-11-25 replies are unchanged.
- The desktop sidecar binds a concrete free port when 8390 is taken instead of port 0, so the engine knows its own address for the terminal and the Claude Code config.

### Security

- A Claude Code session started from the window carries a per-run token in the `x-formlit-inapp` header; the engine treats it as the person's consent (it skips Ask but still honours Block) and lists it as Claude Code in formlit.
- `run_command` refuses every `terminal.*` and `claudecode.*` command for outside agents, even with `FORMLIT_MCP_ALLOW_DELETE`, and the terminal WebSocket refuses non-local origins.

### Not verified yet

- The interactive Claude Code tab started and drew its screen, but its first-run sign-in could not reach Anthropic from the test machine; the same MCP config was verified with `claude -p`.
- Windows terminals (pywinpty), the terminal inside a frozen desktop build, and a full `./build_app` run were not exercised.

## v0.6.0 · 2026-10-12

formlit now follows the Form Agent Standard: Claude can use it through the formlit plugin from the Form marketplace, and the person decides whether outside agents may.

### Added

- **AI agents setting.** Preferences has an AI agents section with Agent access (Ask me, Allowed or Blocked) and the agents seen since formlit started. The first MCP tool call from an agent asks in the window ("wants to use formlit") with Allow, Not now and Block, waits up to two minutes, and is refused with a message naming where to change it when the person blocks, declines or does not answer.
- `get_agent_access` (the 50th tool) and the `agents.status` and `agents.respond` commands report and answer the setting; `agents.respond` cannot be reached from `run_command`.
- The MCP endpoint issues an `Mcp-Session-Id` on `initialize` so calls carry the client's name, and `./formlit mcp` sends the name as `x-formlit-agent`.

### Changed

- The `formlit-editing` skill is now `formlit-driving`, with a Before the first call section for the plugin and no repository setup steps; the pack `formlit-harness` now covers changing formlit. Both carry an `EVALS.json`.
- The desktop shell asks its sidecar for port 8390 instead of a random port so the plugin's bridge finds `/mcp`; the sidecar takes a free port only when 8390 is already in use.
- The Help menu entry Agents and MCP is now AI Agents, and Preferences leads its agent notes with the plugin and keeps the developer setup second.

### Not verified yet

- The Rust change in `src-tauri/src/main.rs` was not compiled, and no desktop bundle was built or run.
- Opening the macOS app from the plugin's bridge by bundle id `ai.nodemode.formlit` was not exercised.

## v0.5.0 · 2026-10-08

### Changed

- The tone curve editor draws the same monotone spline and parametric regions the engine renders, so the drawn curve and the picture agree.
- Colour Mixer slider tracks take their band colours from the engine's control table.
- NOTICE lists only the works this tree includes.

## v0.4.0 · 2026-10-08

A test build of the rewritten develop engine. The engine's colour, geometry, tone, detail, colour-mixing, finish, kernel, mask and retouching modules are new code written from published standards, papers and Lightroom Classic's documented controls.

### Changed

- **Tint** runs the Lightroom way: positive values turn the photo magenta, negative green. Temperatures and tints are computed with Robertson's method and the DNG tint scale, so as-shot values read closer to Lightroom's. Photos edited in earlier versions keep their numbers, which now mean the opposite tint direction.
- **Every develop slider** has a new implementation (tone mapping, Highlights and Shadows, Clarity, Texture, Dehaze, the colour mixer, B&W, Point Color, Color Grading, Calibration, sharpening, noise reduction, post-crop vignetting, grain, built-in looks, Auto). Strengths differ from v0.3.4; existing edits render somewhat differently.
- Masks, brush strokes, spot heal and clone, Generative Remove compositing and red eye are reimplemented; heal now blends in the gradient domain.
- The Transform sliders, lens corrections and Upright are reimplemented; Upright refuses to correct photos with no reliable lines instead of tilting them.

### Fixed

- **Auto Straighten** rotated the wrong way.
- Output ICC profiles now carry sampled sRGB curves, valid for every ICC v2 reader.

### Not verified yet

- Side-by-side comparison with Lightroom for slider strengths.
- The interface's curve editor and slider tracks are unchanged in this build.
- The engine's design notes (`backend/HASHOUT_LOG.md`, the wiki's Pipeline page and the harness pipeline reference) still describe v0.3.4.
- The first start after installing compiles the new kernel, which takes about a minute.

## v0.3.4 · 2026-10-08

### Fixed

- **Previews could stop for good.** When a preview job finished before the engine had finished registering it (for example a photo whose original is missing), the thread waiting on it deadlocked, and every later thumbnail, preview and develop change queued behind it until the engine was restarted. The registration no longer holds the lock that the finished job needs.
- **Keywords.** Renaming a keyword to nothing or to a sibling's name, moving it under itself, a child or a keyword that does not exist, and merging into a missing keyword or a child are refused with a message; a loop already in a catalog no longer hangs keyword and collection queries.
- **Stacks.** Stacking photos that were already in stacks left one-photo stacks behind; duplicates and missing photos made empty or single stacks. Stacking now tidies the stacks it takes photos from.
- **Folders.** Removing or checking a folder whose name contains `_` or `%` also affected folders that only looked similar.
- **Out-of-range values** are now clamped or refused: slide duration and fade, print grid rows, columns and gaps, white balance picker position, saved location coordinates, generative remove variants, the cull threshold, capture times that do not parse, and preferences of the wrong type (which broke Edit In).
- Find Photos with a limit returned fewer photos than asked when stacks were collapsed; a cancelled task reported itself as done.

## v0.3.3 · 2026-10-08

Interface fixes from a full pass through every module, menu and dialog.

### Fixed

- **Buttons stayed disabled until a shortcut was pressed.** After selecting a photo with the mouse, the toolbar's flag, star, label and rotate buttons and Export stayed disabled (clicking 3 stars did nothing), Develop's Reset, Copy, Paste and Auto stayed disabled while editing, and a menu choice left the wrong view highlighted. Buttons now follow the selection, edits, undo and menus.
- **Ctrl+N** created a snapshot everywhere. It now creates a collection in the Library and a snapshot in Develop, as in Lightroom.
- The Presets +, Snapshots + and History × buttons collapsed their own panel; the Folders + (Import) did nothing. All now just do their job.
- Toolbars no longer run under the side panels: at 1440 px every Library control, the Thumbnails slider included, fits, and at 1024 px the toolbars drop their least-used controls in order instead of cutting them off. Upright's Vertical and Full fit the Transform panel.
- Renaming a snapshot, or the collection or folder you are viewing, shows the new name at once.
- The search box's own example, `rating>=3`, now works (as does `rating:>=3`).
- Thumbnails occasionally failed with a server error while previews were being rebuilt during a slider drag.
- The Develop toolbar's zoom readout was blank and its Fit, Fill, 1:1 and 2:1 never highlighted.
- Auto Settings, Auto B&W, Reset, Copy and Paste Settings work from the Library on the selection; Profile Browser from the Library opens Develop on the selected photo.
- Quick Develop's Daylight, Shade and the other light-source presets are skipped for JPEG, PNG, TIFF and WebP photos (they only apply to raws).
- The Book module's text colour swatches ran past the window edge.

## v0.3.2 · 2026-10-08

A safety release from an engine test sweep of 3,100 command calls. Nothing here changes how photos look.

### Fixed

- **Files outside the catalog could be deleted or overwritten.** A user preset or export preset id containing a path (`user:/any/file`, `../`) let Delete Preset and Update Preset delete or overwrite any file the engine could reach, including over MCP. Preset ids now resolve only inside the presets folder.
- **Originals could be overwritten.** Export to the same folder with "overwrite" replaced the original photo with the rendered copy; a folder publish collection named `..` overwrote originals one level up and deleted them on unpublish. formlit now never writes over or deletes a catalog original or its sidecar: such an export gets a numbered name, and book, slideshow, print and web outputs refuse an original as their file.
- **Undo left files behind.** Undoing Rename Photos or Rename Folder restored the catalog but not the files, so photos went missing. Undo and redo now move the files too, and refuse with a message if something is in the way. Delete from Disk is no longer offered as undoable (its files are in the system trash) and its confirmation says so.
- **One bad smart collection broke the Library.** A smart collection with malformed rules made the folder and collection tree fail until it was deleted, and an unknown rule field matched every photo. Rules are now checked when saved, and malformed ones already in a catalog match nothing. A collection cannot be moved into itself.
- **A malformed setting made a photo unrenderable.** Develop changes with values of the wrong type (from scripts, agents or old sidecars) were stored and every later render of that photo failed. Settings are now cleaned against the control table when stored and again before every render, so affected photos render again.
- **Wrong-type parameters crashed commands.** 90 calls ended in a server error; command parameters are now checked against their declared types and ranges and answered with a sentence (3 left after the change, all fixed). The render endpoint checks its sizes and options the same way, MCP answers malformed requests with protocol errors, and any remaining error returns JSON with its message.
- MCP `auto_straighten` always failed; it now levels each photo and crops to fit, like the Crop tool's Auto button. `develop.sync` rejected nothing it did not understand (a typo in `from` synced from the wrong photo); it now refuses unknown parameters.

## v0.3.1 · 2026-10-07

### Fixed

- **White balance on JPEG, PNG, TIFF and WebP.** Temp and Tint showed kelvin (6500 as shot, up to 50000) for rendered files, as if they were raws. They now read -100 to +100 around as shot, as in Lightroom, the WB menu offers As Shot, Auto and Custom only, history steps read "Temp +25", and the histogram line no longer claims "As shot 6500 K". Raws are unchanged. Settings, presets and agents still store kelvin, so nothing already saved changes.

## v0.3.0 · 2026-10-07

A reliability release. The engine no longer dies when renders overlap, profiles gain Adobe look tables and the as-shot style for seven makers, and the desktop sidecar is built and checked. Parity stays at 57.5 of 58 (`docs/PARITY.md`).

### Fixed

- **The engine aborted under overlapping renders** ("Numba workqueue threading layer is terminating: Concurrent access has been detected", then 502 on every request). The view, the zoomed region and Before render at the same time, and numba's default thread pool on macOS cannot run two parallel kernels at once. Every parallel kernel call now holds one lock; 24 overlapping renders on CR2, CR3, DNG and a 10401 px TIFF all succeed. Warm slider renders at 1400 px take 85 to 220 ms on a 2-core machine.
- Switching photos in Develop stretched the old picture into the new photo's shape (and rescaled it at 1:1) until the new render arrived; the new pixels and the new geometry now appear in the same frame.
- The Navigator keeps one 3:2 box for every photo, so the panels below it never move, and its view rectangle sits on the letterboxed picture and follows it when the photo changes while zoomed.
- CR3 and RAF photos imported with no camera, lens, exposure or capture time; they now read their Exif. For photos already in a catalog, select them and choose Metadata > Read Metadata from File (a hand-edited capture time or location is kept).
- A DCP's tone curve rendered proprietary raws 1.2 to 1.5 EV darker than the camera's JPEG; it now starts from the camera's own brightness, and formlit's derived DNGs (denoise, HDR, panorama) render a DCP like their source raw.
- Importing a profile whose name matched another kind of profile overwrote it; names are now kept apart, and a profile re-imported under the same name renders at once.
- A Lightroom preset that references a creative profile was imported as a bare profile and lost its settings.
- The desktop engine exited at startup because PyInstaller left out the command modules; the freeze now names them and refuses to copy an engine that fails its selfcheck. `@tauri-apps/api` and `cli` move to 2.12.1 to match the Rust crate, which `tauri build` requires.
- Dev server console: the three font preload warnings are gone (dev only; the build keeps the preloads).

### Added

- **Adobe look-table profiles.** Creative profiles holding an HSV look table import, alone or beside an RGB table, and scale with Amount.
- **As-shot picture style** read from the maker notes of Canon (CR2, CR3), Nikon, Sony, Fujifilm, Panasonic, Olympus and OM System, and Pentax raws, so the camera-matching styles start from the style the photo was shot in.
- **Faster look tables.** A DCP or Adobe look table that follows Exposure re-runs only its own step while you drag (0.64 s instead of 2.7 s at 1600 px), through a compiled kernel.

### Not verified yet

- Adobe-made creative profiles and DCPs (checked with RawTherapee's camera DCPs and with profiles built to the published layouts). The look-table layout follows the DNG SDK's structure; a file that does not match it exactly is refused with a message.
- macOS and Windows desktop bundles (the Linux bundle is built and started here); the items still open from earlier releases.

## v0.2.0 · 2026-10-07

Profiles reach Lightroom parity: graded at 57.5 of 58 rows (`docs/PARITY.md`), with reflection removal the one Partial row. Raw sources are decoded once more on first open (source cache version 5).

### Added

- **Profiles as tables.** Every built-in look, B&W looks included, is a 3D colour table; Amount scales it from 0 to 200 without moving any slider, and it looks the same in sRGB, Display P3, Adobe RGB, ProPhoto and Rec.2020 exports.
- **Camera matching per maker.** Canon, Nikon, Sony, Fujifilm, Panasonic, Olympus and OM, Pentax and Ricoh raws list their maker's picture styles and film simulations, built on Camera Look (the fit to the camera's own JPEG) relative to the style the photo was shot in (read from Canon CR2 so far; other raws assume Standard, and the Profile Browser says which).
- **Adobe creative profiles.** `.xmp` profiles with an RGB table import as tables, resampled from their own primaries and gamma, keeping name, group and the grayscale flag.
- **DCPs in camera space.** An imported `.dcp` applies its forward or colour matrices for its own camera, blends both illuminants by white balance, runs the look table after exposure and uses its tone curve; Develop lists a DCP only for its camera.
- **Profile Browser.** Color and B&W filters and a note about the as-shot style; Amount rests when a profile has nothing to scale; new imports appear without changing photos.

### Fixed

- The Profile Browser's first opening shifted every tile when favourites arrived; it now opens with them loaded.
- The Navigator grew when a slow first decode finished and pushed the left panels down; it reserves the picture's shape.
- Grain was reshaped by the profile table; the table now runs before grain.

### Tried and withdrawn

- A classical reflection-removal slider (gradient-threshold layer separation). An independent audit found it moved photos further from the true scene in all 12 test composites, so it was removed before release. A learned model is the way forward (see `docs/PARITY.md`, row 46).

### Not verified yet

- Real Adobe or camera-maker DCPs and creative profiles (verified with synthetic profiles built to the DNG and RGBTable layouts, and with profiles made by an independent MIT-licensed encoder); the as-shot style for raw formats other than CR2; the items still open from v0.1.0.

## v0.1.0 · 2026-10-07

The first release: a Lightroom Classic alternative in the form family, graded at 57 of 58 parity rows (`docs/PARITY.md`). The version reads 0.1.0 in `frontend/package.json`, `frontend/package-lock.json`, `frontend/src/version.ts`, `backend/app/__init__.py`, `src-tauri/Cargo.toml` and `src-tauri/tauri.conf.json`; tag `v0.1.0` builds the desktop bundles.

### Added

- **Engine.** A FastAPI engine whose catalog (SQLite, WAL, one revision counter) records undo for every command; 217 commands dispatched alike by the interface, the CLI and the MCP server; server-sent events for keyed patching; background tasks with progress.
- **Pipeline.** Geometry first, then white balance, spots and red eye, noise reduction, low-frequency planes and one finish stage, in linear Rec.2020, with a numba kernel and a numpy reference; HDR editing with headroom and an SDR rendition.
- **Import and catalog.** Add, copy, move and Copy as DNG with templates, presets, keywords, a second copy and eject; folder synchronize, volumes, changed files, missing files and relink; smart previews; tethering through gphoto2 and digiCamControl with Live View; auto import; Export as Catalog and Import from Another Catalog; XMP sidecars and embedded XMP with full Camera Raw settings.
- **Library.** Grid, Loupe with Navigator, Compare, Survey, a second window, ratings, flags, labels, collections and smart collections, hierarchical keywords with suggestions, sets and the Painter, metadata views and presets, stacks, virtual copies, batch rename, capture time, the filter bar, People, and the Comments panel for published photos.
- **Develop.** Basic, presence, curves with targeted adjustment, colour mixer, Point Color, grading, B&W, profiles with a browser and .cube and .dcp import, calibration, detail, lens corrections from Lensfun and DNG opcodes, Upright, crop with overlays and Straighten, effects, history, snapshots, settable Before, copy, paste, sync and auto sync, presets with amount and hover preview.
- **Masks and retouching.** Brush, gradients, ranges, AI masks (subject, sky, background, objects, each person, people parts, landscape parts) that follow the edit, 17 local sliders with tint, Point Color and a point curve; heal, clone, generative Remove with variations, Detect Objects, Remove People and Find Dust; red eye and pet eye.
- **AI.** Local models on ONNX Runtime, pinned by SHA-256: segmentation, depth, faces, LaMa, Real-ESRGAN, SAM 2.1; denoise, super resolution, raw details, HDR, panorama and HDR panorama merges, lens blur, assisted culling.
- **Output.** Export in nine formats with custom ICC, HDR (Ultra HDR, AVIF, JPEG XL, TIFF) and graded video; Print with driver settings; Books with spreads, wrap covers and Blurb PDFs; Slideshows with up to ten tracks, audio balance, fit to music and video clips; Web galleries with FTP upload; Publish services for folders, FTP, WebDAV and Nextcloud with comments, S3-compatible storage and Python plug-ins; Edit In; the Map module with private locations.
- **Agents.** The MCP server (49 tools plus `run_command`), `./formlit mcp`, `./formlit agents install|sync`, the `formlit-editing` skill and the `formlit-harness` skill pack.
- **Desktop.** The Tauri 2 shell with the frozen engine as a sidecar and a release matrix for macOS, Linux and Windows.

### Fixed during the release series

- Full-size exports with Lens Blur ran out of memory; the blur pyramid now blends two levels at a time.
- A new photo could inherit another photo's cached previews when SQLite reused a removed photo's id.
- Mask rows painted one sync late.

### Not verified yet

- Desktop bundles (the release workflow has not run), real cameras for tethering (only a simulated gphoto2), real printers, and H.264 playback in webviews without the codec.
