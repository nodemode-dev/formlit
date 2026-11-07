# Changelog

All notable changes to formlit. Versions are `v*.*.*`; each release lists what it added, what it fixed and what is not verified yet.

## v0.49.2 · 2026-11-07

- The desktop splash now matches the rest of the Form family: the same rounded card with the app icon, "Starting formlit" and the family-gradient progress bar, rounded corners on macOS with nothing square behind the card, and the same reveal. The main window stays unseen on a dark background until the page has drawn its first content and at least 2.6 s have passed since launch, then appears whole as the splash closes; there is no white frame.
- The window page tells the shell when it is ready (`app_ready`), which needs the shell's capability to list the engine's loopback address. A page that never reports is shown after 20 s.
- Not verified: the Rust shell was not compiled and the desktop build was not run here; the splash page was checked in headless Chrome.

## v0.49.1 · 2026-11-07

- The offline demo now opens on a real photo library: 25 Pexels photographs in four collections (Mountain Lakes, Coastlines, City After Dark, Autumn Woods) with star ratings, pick and reject flags, colour labels, keywords, the camera data and capture dates the Pexels photo pages publish, and 18 photos that already carry develop settings and a history, so Before and After shows real work. The Catalog panel lists the collections with counts, and the Metadata panel shows capture date and focal length.
- The library appears in one step: fixed-size placeholder cells fill the grid from first paint, the empty-library card never shows while loading, the Metadata panel keeps its eight rows at their final height, and the photos and counts arrive together with no layout shift. Grid cells widen to fill the grid width. Photos load from JavaScript data packs, decoded small for thumbnails and full size only when opened, previewed or exported, and the loupe swaps its thumbnail for the full preview when it is ready. The procedural scenes moved to a collapsed Generated Samples panel and remain as an offline fallback.
- Sources, photographers and licences are in `demo/CREDITS.md`, with a row in `NOTICE.md`. Nothing in `frontend/src` or `backend/` changed.
- Not verified: the demo was checked in headless Chrome over `file://` only; the desktop build was not run here.

## v0.49.0 · 2026-11-07

- New: an offline demo in `demo/`. Open `demo/index.html` from disk or from any static server and the formlit window runs in the browser with no engine, no network and no install. It has the Library (grid, loupe, filmstrip, ratings, flags, labels, keywords, EXIF), Develop (the global develop controls, 12 presets, history, before and after, clipping, white balance picker, crop and straighten, Auto Tone), and export to JPEG, PNG or WebP with a ZIP for several photos, copy, paste and synchronize settings, and settings files. It runs on six built-in procedural samples or on your own photos, which never leave the page.
- The demo's develop pipeline is a TypeScript port of the engine's global path, and its interface is the app's own modules and stylesheets. Nothing in `frontend/src` or `backend/` changed.
- The version is 0.49.0 because the last number runs 0 to 9.
- Not verified: the demo was checked in headless Chrome over `file://` only; RAW files open through their embedded JPEG preview and were not tried against a real RAW file; the desktop build was not run here.

## v0.48.0 · 2026-11-05

- The Intel Mac build of FormLit still stopped while installing its Python libraries, with "No matching distribution found for rawpy==0.25.1". 0.47.9 taught setup to use Python 3.13 or 3.12 on Intel Macs, but the engine installer (`backend/oc_install`, which `./formlit install` runs) picked its Python on its own and still made the engine's environment with Python 3.14, for which those library versions do not exist.
- Now the installer uses the same choice as the rest of setup, and if an Intel Mac already has an environment made with Python 3.14 it is made again with 3.13 or 3.12. Apple Silicon Macs, Linux and Windows are unchanged.
- The version is 0.48.0 because the last number runs 0 to 9.
- Not verified: the full desktop build on formcompiler's Intel Mac machine; the install was run here under Rosetta.

## v0.47.9 · 2026-11-05

- FormLit installs again on Windows and on Intel Macs. The Windows install picked the newest Python on the machine (3.15 on the build service), and onnxruntime, which runs the local AI tools, has no version for Python 3.15 yet, so the install stopped. On an Intel Mac, onnxruntime, rawpy (camera RAW files), numba, pikepdf (PDF export) and cryptography have stopped publishing Intel Mac versions, and the last ones exist only up to Python 3.13.
- Now the install uses Python 3.14, 3.13 or 3.12 (3.13 or 3.12 on an Intel Mac), and an Intel Mac installs the last version of each of those five libraries that still supports it: onnxruntime 1.23.2, rawpy 0.25.1, numba 0.62.1, pikepdf 10.13.0.post1 and cryptography 48.0.1. Apple Silicon Macs and Linux are unchanged; Windows only changes which Python it uses.
- Not verified: the Windows install and the desktop builds were not run here; the Intel Mac libraries were installed and tested under Rosetta.

## v0.47.8 · 2026-11-04

- The folder-removal test in `test_originals_untouched.py` passes on macOS. The catalog stores each folder by its resolved path, and macOS's temp folder `/var/folders/...` resolves to `/private/var/folders/...`, so the test looked up the unresolved path and never found the folder. It now looks up `folder.resolve()`. No app change: removing a folder from the catalog only drops its catalog rows and leaves the files on disk, as before.
- Not verified: the desktop build was not run here.

## v0.47.7 · 2026-11-04

- README in the Form family template (Mackin's #6), merged with main.
- Not verified: the desktop build was not run here.

## v0.47.6 · 2026-11-03

- The README follows the Form family layout, with screenshots of the Library, Develop and Export in `docs/images/`.
- The title bar and splash screen show the unified app icon (`favicon.png`) instead of the old inline SVG art.
- Not verified: the desktop build was not run here.

## v0.47.5 · 2026-11-03

- The app icon is the unified family icon in the desktop bundle, the web favicon and the README; the old SVG favicon is gone.
- The compiled app is named FormLit: product name, window titles and page titles.
- The repo has a CODEOWNERS file: `* @nodemode-ai @gbarnai`.
- The About box and the installers name NodeAgentc, Inc. as the publisher, with the licence (Apache-2.0) and a link to the LICENSE file. The bundle sets `publisher`, `copyright`, `license` and `licenseFile`, so the macOS About panel, the Windows file properties and installer, and the Linux packages say the same.
- The updater reads its feed from the download store, `https://dl.formai.studio/formlit/updates/latest.json`, instead of formcompiler's private release page; the release notes in `.docs` and the release-keeper skill name the current flow (formcompiler at `nodemode-dev`, the draft `vX.Y.Z` on formlit's own Releases page).
- Not verified: the desktop build was not run here.

## v0.47.4 · 2026-10-31

- The Windows desktop app no longer opens to a blank window on PCs where an installer set the `.js` file type to `text/plain` in the registry: the engine now serves scripts and stylesheets with their real types.
- Video thumbnails, video export and slideshow video no longer need ffmpeg installed: when none is found, the desktop app downloads its own LGPL ffmpeg on first run, checks every file against its pinned SHA-256, and uses it. An installed ffmpeg is still used first.
- On Linux, the .deb and .rpm recommend GStreamer's plugins and the AppImage carries the base and good ones, so the video player and slideshows play on a fresh install.
- Not verified: the desktop build was not run here; the ffmpeg download was run against the real release on Linux.

## v0.47.3 · 2026-10-30

- Windows desktop builds take `--config`: `formlit.bat desktop build --config FILE` passes it to `tauri build`, so formcompiler's Windows release can carry updater files.
- macOS installs pin opencv-python-headless to 5.0.0.93, the version Linux and Windows use, so the from-source OpenCV build is the same on every run.
- A .gitattributes keeps text files LF and checks batch files out with CRLF.
- Not verified: the desktop build was not run here.

## v0.47.2 · 2026-10-26

- A window smoke test in frontend/tests/window loads the built window and its splash page under a slowed CPU and network and fails on any layout shift, console error, failed request or request the local guard refuses. CI runs it as the window job (F7).
- Fixed (FB-110): the splash page's caption no longer moves the mark when it parses.
- Fixed (FB-111): the Catalog, Folders and Collections panels reserve their empty-state and fixed rows before the library tree answers, so the panels below no longer jump on a slow start.
- Not verified: the desktop build was not run here.

## v0.47.1 · 2026-10-26

- The engine has a test suite in backend/tests that runs in CI: the local guard, outside-agent consent, the MCP server, the version sites, the engine boot, that originals are never modified, the develop math, catalog migration and the files export writes. No behaviour changed.
- CI audits the frontend lockfile with npm audit.
- Not verified: the desktop build was not run here.

## v0.47.0 · 2026-10-26

- The desktop release build keeps its symbols, since macOS builds fail on a stripped binary. A minor number only because a patch number never reaches two digits.
- Not verified: the desktop build was not run here.

## v0.46.9 · 2026-10-25

- A web page can no longer reach the engine through an image or a link.
- Not verified: the desktop build was not run here.

## v0.46.8 · 2026-10-25

- The engine answers only this computer's own window and agents.
- Not verified: the desktop build was not run here.

## v0.46.7 · 2026-10-25

- The frontend's vite dev dependency moves from 8.3.0 to 8.3.5, which clears two command-injection advisories in the dev server's launch-editor; `npm audit` reports 0 vulnerabilities. Dev dependency only, nothing in the shipped bundle changed.
- Not verified: the desktop build was not run here.

## v0.46.6 · 2026-10-24

- The copyright holder in LICENSE, NOTICE.md and the README is NodeAgentc, Inc.
- The About box carries the credit "by nodemode.ai".
- Not verified: the About box was not opened in a window here.

## v0.46.5 · 2026-10-23

- NOTICE.md lists five more downloaded models, the Python packages frozen into the engine, the desktop shell's crates under other licences, and how the lens profile database is fetched; the installers carry LICENSE and NOTICE.md.
- The macOS build stops if OpenCV's GPL codec libraries are installed; macOS releases build OpenCV without them.
- Not verified: a macOS build.

## v0.46.4 · 2026-10-23

- Changed: smart collections are Intelligent Collections (and Intelligent Published Collections) in every menu, dialog, message, agent tool and document, translated in all 25 languages. Saved catalogs, ids and agent calls are unchanged.
- Not verified yet: the renamed menus and dialogs were not seen in the window.

## v0.46.3 · 2026-10-23

- Changed: built-in print, filename and smart collection templates that shared their names with another photo library's built-in sets have formlit's own names (Gallery Mat, Full Page, Proof Sheet 20 per Page, Print Set, Name - Sequence, Red Label, Top Rated and the rest); every id is unchanged. The new names are translated in all 25 languages.
- Not verified yet: the renamed templates were not seen in the window.

## v0.46.2 · 2026-10-23

- Added: About formlit opens a dialog with the version and a closed "Licences and notices" section carrying Adobe's required DNG notice; the notice is also in NOTICE.md and the README.
- Changed: Smart Previews are Intelligent Previews and the Adaptive preset groups are Adaptable groups; every built-in preset id is unchanged. Five presets (Teal and Orange, Moody Green, Portra Style, Tri-X Style, Matte Fade) were retuned with formlit's own values. A trademark notice is in the README and NOTICE.md, and the README no longer describes formlit as a copy of Lightroom.
- Not verified yet: the About dialog and the retuned presets were not seen in the window; the translated values of the renamed strings still use the old words.

## v0.46.1 · 2026-10-22

### Changed

- Releases are built by formcompiler (`nodemode-ai/formcompiler`), the release pipeline for every form* app, and published on its release page as `formlit-vX.Y.Z`. formlit's own GitHub Actions now only run the checks, on main, on pull requests and on `compile_vX.Y.Z` branches. A release starts when a `compile_vX.Y.Z` branch is pushed; the steps are on the wiki's Releasing page.
- The updater looks for new versions in formcompiler's `formlit-updates` feed.
- No change to the app itself.

### Not verified

- No formcompiler build of formlit has run yet.

## v0.46.0 · 2026-10-20

### Added

- **A new app icon: a lens with an iris and bokeh.** The flat aperture with a white dot is redrawn as a lens in the Form family style: a gunmetal barrel, a seven-blade iris in the family colours lit from the top left, a deep violet opening, a glass reflection, and soft out-of-focus light discs around it. The same design is used everywhere: the Dock and taskbar icons, the mark inside the window, the browser tab icon and the startup splash. `assets/icon_src/` regenerates every size.

### Not verified yet

- The new icon has not been seen in a built desktop app on macOS, Windows or Linux; the files were checked against the design source only.

## v0.45.3 · 2026-10-15

### Note

- **Remove keeps LaMa after trying better models.** Two more models were built and measured in Remove on real photos where the true background is known. LCM DreamShaper (a faster diffusion model) made smooth blobs. MI-GAN (a texture model) was mixed: alone it gave colour blotches, and combined with LaMa's tone it was better in one of four cases, worse in one and even in two. MAT was ruled out by its non-commercial licence. Structure stays covered by Keep Lines, Same Surface and Same Depth.

## v0.45.2 · 2026-10-15

### Note

- **The generative Detail pass for Remove was built, measured and left out.** It uses the Stable Diffusion 1.5 inpainting model, checked against the original weights, refining LaMa's fill. On foliage with the true background known, every setting gave a softer fill than LaMa: texture 7.9 to 8.8 against LaMa's 8.8 in one test and 11.9 in the other, with the real photo at 13.9. It took about 2 minutes per fill instead of 4 to 21 seconds and needed a 4.3 GB download. Remove stays as it was.

## v0.45.1 · 2026-10-15

### Note

- **No generative fill for Remove, by decision.** A Stable Diffusion inpainting model steered by edge or depth maps (ControlNet) was researched. Its licence would allow it, but on a 2-core computer a fill takes about a minute even in fast mode, about 15 times LaMa, and it needs a 2.5 to 4 GB download. For removal it could only refine LaMa's fill: maps taken from the original photo still contain the object and would draw it back. Keep Lines and the Same Surface and Same Depth sample areas already cover the structure cases it was meant for. An opt-in Detail pass is written up for later.
- Models with non-commercial or revenue-capped licences (FLUX.1 Fill dev, Stable Diffusion 3.5) were ruled out.

## v0.45.0 · 2026-10-15

### Added

- **Pick a distance for a Depth Range mask by clicking the photo:** Near and Far are set around the depth where you click; Shift-click widens the range to take in another distance. The sliders stay for fine tuning.
- The new hint, the message shown when there is no depth map yet and the command name are in all 25 languages.

### Fixed

- **Same Surface and Same Depth fills could pull in colour from the wrong place:** they copied from a box around the whole sampled area, which on a wall beside a window took in the bright window (a lighter disc on the wall, window colour smeared onto the sill). They now copy only from the sampled surface nearest the spot, matched to the tone around it.
  - On a real wall with an object pasted onto it, Same Surface and Same Depth left cleaner texture than the plain fill (detail error 1.37 and 1.14 against 1.46; the plain fill leaves a visible smudge). Their overall tone is very slightly further off (3.8 and 3.6 against 2.3 on a 0 to 255 scale), which cannot be seen.

### Note

- Object masks that stop at edges were dropped from the plan: the object model's masks already follow edges, and Refine Edge, Shift Edge and edge points handle the cases where they do not.
- This changelog now covers every version from v0.26.1 on; it had stopped at v0.26.0.

## v0.44.0 · 2026-10-15

### Added

- **Keep Lines for Remove:** when an object you remove crosses a straight line (a window frame, a sill, a horizon edge) that continues on the far side, the line is rebuilt through the fill instead of breaking.
  - It is a check box in the Sample from row of the Remove tool.
  - On a tiled test with a known background it came closer to the truth than the plain fill (error 9.5 against 10.5). On a real window sill the frame corner stays sharp and a diffuser's reed is not carried across.
- **Edge Snap for the mask brush:** the soft edge of a brush stroke stops at the nearest strong edge in the photo. It sits beside Auto Mask. On a flat photo it paints exactly like the plain brush.
- **For agents:** `remove_object` takes `keep_lines`.
- Both new labels are in all 25 languages.

### Fixed

- **Sample from appeared in Heal and Clone**, where it does nothing. It now shows only in Remove.

### Note

- Same Surface was checked on a real wall in v0.45.0, and Select by Depth arrived there as a click on the Depth Range mask.

## v0.43.0 · 2026-10-14

### Added

- **Show Control Maps (View menu):** shows four views of how formlit reads the photo: edges, straight lines, depth and subject. Useful for seeing why a mask or a Remove fill behaves as it does.
- **Remove can sample from the same surface:** Sample from now offers Same Surface, which finds the wall, floor, sky or water around the spot and fills from that surface only.
- **For agents:** `get_control_maps` returns the four maps as images, and `remove_object` takes `sample_same_surface`.
- **Translations complete:** everything added since v0.42.0 (678 preset names and descriptions, 42 groups, all new labels) is now in all 25 languages. Checked in the window in Czech, Thai, Danish, Hungarian, Finnish, Norwegian and Japanese.

### Note

- Translations have not been reviewed by native speakers.
- Keep Lines for Remove and an edge-snapping brush were next on the list for this stage (both arrive in v0.44.0).

## v0.42.2 · 2026-10-14

### Added

- **Second translation pass for the new presets:** the new preset names, groups and labels are in all 25 languages. The nine languages whose names had been assembled word by word in the previous pass (Czech, Danish, Finnish, Hungarian, Norwegian, Polish, Russian, Swedish, Ukrainian) were translated again phrase by phrase.
- **Preset descriptions** are now in 19 languages.

### Note

- Preset descriptions still show in English in Czech, Danish, Norwegian, Finnish, Hungarian and Thai (finished in v0.43.0).
- Checked in the window in Russian, Swedish, Polish, Hungarian, Finnish and Spanish; all 25 languages load.

## v0.42.1 · 2026-10-14

### Added

- **First translation pass for the new presets:** names, groups and new labels in 16 languages, and descriptions in 7 (German, Japanese, Korean, both Chinese scripts, Turkish and Indonesian). Checked in German, Japanese and French.

### Note

- The names for Czech, Danish, Finnish, Hungarian, Norwegian, Polish, Russian, Swedish and Ukrainian were not shipped: they had been built from a word list in English word order and would read worse than English. They show in English until v0.42.2.
- The remaining descriptions were still to do.

## v0.42.0 · 2026-10-14

### Added

- **678 new built-in presets** (now 978, in 49 new groups): exposure steps, white balance by light source, black and white filters, toning, sharpening by subject and output, noise by sensor and ISO, grain, vignettes, lens fixes and looks for product, food, real estate and more. They come from three research passes over 83 distinct sources.
  - **Checked:** every preset's settings are valid, and each was run on five test photos (portrait, two daylight, high contrast, night) without errors.
- **Preset packs:** Import now takes zip packs (how most presets are sold and shared), and Export Group (in the preset context menu) saves a whole group as Lightroom-compatible XMP files in one zip. A group of 26 presets exported and imported back intact.
- **Edge Range mask (in the mask Range menu):** selects by how strong the edges are, with Edge Threshold, Feather, Fine Detail and Invert (for flat areas). Use it to sharpen or add clarity only on edges, or to smooth only flat areas. Edge-only adjustments changed edges 24 times more than flat areas.
- **Remove from the same depth:** Sample from now offers Same Depth, so a fill behind a person draws from the wall at that distance, not the floor in front.

### Note

- The new preset names, descriptions and labels showed in English in other languages until v0.42.1 to v0.43.0.
- Some presets clip above 2 percent by design or on the wrong kind of photo (brightening steps and white-background product presets on a bright frame, astro presets on daylight frames, a noir preset that crushes shadows). Detail-only presets (sharpening, grain, defringe) leave tone unchanged on purpose.

## v0.41.1 · 2026-10-14

### Fixed

- **Thumbnails grew when their picture arrived:** a portrait thumbnail started at 12 pixels and grew every cold load, nudging the layout. Thumbnails now take their final size before loading; two cold loads under a slow computer and slow network show no movement.

### Note

- This was a health pass with nothing else left open: code checks, the engine self-check, the agent tool reference, and all 25 languages loading were run.

## v0.41.0 · 2026-10-14

### Added

- **Apply My Style now tunes itself to you:** for each control it picks the method that suits how you edit (match the most similar photos, match them and adjust for brightness, or use your average edit). It switches on from 24 edited photos up, since with fewer the choice was noise.
  - On three synthetic photographers (30 photos), exposure error was 0.20, 0.24 and 0.10 stops, against 0.20, 1.09 and 1.15 before.
- **Check My Style** now reports the method chosen per control and both errors.

### Note

- Not yet run on a real photographer's catalog, and native-speaker review of the translations is still open. A printer's own preflight of book files is also still to do.

## v0.40.0 · 2026-10-14

### Added

- **Book files pass an independent preflight:** book PDFs are now PDF/X-1a:2001 and pass an open-source checker for IngramSpark, Lulu and KDP, interior and cover. A plain CMYK file fails it, as expected. Run it yourself with `./formlit preflight FILE...`.
- **Check My Style (Photo menu):** measures how well Apply My Style would have predicted your own edits, against the average edit and against no edit. For agents: `check_my_style`.
- **Language review round trip:** `./formlit i18n export` writes a sheet of every string a language shows, and `./formlit i18n import` loads a native speaker's corrections, which win over the built-in text. The 25 review sheets are ready.

### Note

- A certified Acrobat or callas run is still the printer-grade proof.
- A public set of expert edits was considered for testing the learned style and not used because its licence is research only.

## v0.39.0 · 2026-10-14

### Added

- **PDF/X-1a book files:** the Book module has a PDF/X-1a check box once a CMYK profile is chosen. Fonts are embedded (bundled Liberation fonts), the file carries the CMYK output intent, trim and bleed boxes, and passes its own self-check. IngramSpark and Lulu exports pass it.
- **Develop terminology fixes:** 104 corrections across 22 languages, for example Hue and Tint no longer swapped or merged, Lens Blur's focus range and distance no longer called focal length, and Ukrainian Develop now reads обробка.

### Fixed

- **Shadows that pass behind the subject** and show above its head are now found as part of the object's shadow when you remove it (test overlap 0.00 to 0.45). A pole above the head is not taken.
- **A small layout nudge at the end of Enhance** came from a thumbnail resizing when the list changed. It resized twice; it now resizes once, by a fraction of the size.

### Note

- A certified preflight, native-speaker review and a real photographer's catalog for the learned style are still open.

## v0.38.0 · 2026-10-14

### Added

- **Each window gets its own exposure** in Flash and Window Blend. With a sunlit and a shaded window, one shared gain left the dim one 1.5 stops too dark; now both land where you want them.
- **Send by SFTP after export** (alongside FTP): choose the protocol, port, a private key file, and Trust this server the first time. An unknown server is refused unless you trust it; a wrong password is refused.
- **Sample from (Remove tool):** choose Anywhere, Above, Below, Left or Right, so a fill borrows texture from the side you point to.
- **Book PDFs through a CMYK profile:** pick a CMYK profile in the Book module's Colour setting; images are converted and text uses the profile's colours, with pure black as black only. All 24 images of a test book came out CMYK.
- **Low-sun shadows:** shadows cast by an object are found much better when long or cast away from the camera (test overlap 0.00 to 0.77 and 0.19 to 0.71), and a dark object beside the subject is no longer taken.
- **Terminology fixes** for the 178 most visible strings (menus, panel titles) in 12 languages.

### Fixed

- **The packaged engine would have failed its self-check:** its build list had fallen behind and left out seven command modules. The build scripts now collect the whole app.

### Note

- The packaged engine was not built here.
- Still open: PDF/X, native-speaker review, the learned style on a real catalog, and the end of Enhance on a large photo (Denoise did not finish within 7 minutes on the 2-core test machine).

## v0.37.0 · 2026-10-14

### Added

- **Amazon KDP inside margin by page count** in the book printer checks, so text too close to the binding is flagged for your page count.
- **Pick limit for proofing galleries:** the client gallery shows "N of LIMIT picked" and refuses another pick at the limit, so the client unpicks first.
- **Send by FTP after export** (Post-Processing): server, user, password, remote folder and TLS. The password is never stored. Checked against a local FTP server.
- **Plural forms by count in 25 languages** (for example Swedish 1 foto, 3 foton; Polish and Russian forms checked).

### Fixed

- **The People list shifted** when its faces arrived after the panel opened. It now loads at startup, and no shift was measured.
- **Action toasts pushed the others up:** a finishing task's toast now goes on top without moving the rest.

### Note

- SFTP, a fresh full Enhance run, per-window flash exposure, Remove sample-from area, low-sun shadows and CMYK or PDF/X were not done in this version (several arrive in v0.38.0 to v0.40.0).

## v0.36.0 · 2026-10-14

### Added

- **Apply My Style (Photo menu):** gives each photo the tone and presence settings of your edited photos most like it, with a choice of amount and which photos to learn from. One undo step. On a synthetic consistent photographer it was off by 0.25 stops of exposure, against 1.41 for no edit and 1.46 for the average edit.
- **Smart collections can use "looks like":** the new Shows rule matches photos that look like (or do not look like) a description.
- **Retouch Skin: Largest spot**, a limit on the size of blemish it will heal (as a percent of the face).
- **For agents:** `apply_my_style`.

### Fixed

- **Filters now find photos inside collapsed stacks.**
- **New toasts no longer push the earlier ones up the screen;** they stack on top.

### Note

- In Czech, Danish, Norwegian, Polish and Swedish a count still reads with the singular noun; a native check is open.
- The new strings are in 25 languages; German was checked in the window.

## v0.35.1 · 2026-10-14

### Fixed

- **Imports now start search indexing** for the photos they add, when the search model is installed. A new portrait was indexed within 15 seconds and came first for its description.

## v0.35.0 · 2026-10-14

### Added

- **formlit speaks 26 languages,** English by default. Pick one under Language in Preferences. Menus are translated from the first paint, dates follow the chosen language, and the result was checked in German, Japanese, Thai and Finnish with no overflowing label in the set checked.
- **Book PDFs for Lulu, Amazon KDP and IngramSpark** (Book module printer list): each printer's bleed and binding side, even page counts, IngramSpark's blank last page, and notes for too few pages or text near the trim. A 10 x 8 inch book becomes 10.25 x 8.25 for Lulu and 10.125 x 8.25 for KDP and IngramSpark.
- **For agents:** `make_book` takes a printer.

### Note

- Names you type stay as typed, and some words inside sentences (book, slideshow, print, web) stay in English.
- Languages with several plural forms use the singular in this version (fixed in v0.37.0).
- Not covered yet: KDP's inside margin by page count, CMYK and PDF/X-1a, and each printer's spine formula.

## v0.34.1 · 2026-10-14

### Added

- **Translation catalogs for 25 languages:** 2,726 strings written (Spanish, Mexican Spanish, Brazilian Portuguese, French, Canadian French, German, Italian, Dutch, Danish, Finnish, Norwegian, Swedish, Russian, Polish, Czech, Hungarian, Ukrainian, Turkish, both Chinese scripts, Japanese, Korean, Indonesian, Thai and Vietnamese). Exposure reads Belichtung, Exposition, 露光量 and 曝光度.

### Note

- The window still showed English only: switching language arrived in v0.35.0.
- One term needed fixing (Russian Develop).

## v0.34.0 · 2026-10-14

### Added

- **Shadows and Reflections option for Remove:** takes out the shadow an object casts and its reflection along with it. On test scenes the leftover error in the shadow area fell from about 0.5 to about 0.05 to 0.09. On a real photo the ball goes cleanly and the boot and sock stay.
- **Detect Objects** keeps only the parts of the object your mark touched.
- **For agents:** `remove_object`.

### Fixed

- **Refresh gave the same three fills every time.** It now really gives new ones.
- **The Variations row pushed the drawer down** when a fill arrived. It no longer moves anything.

### Note

- Under a slow computer and network there was no layout shift and no page errors.

## v0.33.0 · 2026-10-14

### Added

- **Flash and Window Blend (Photo menu):** for interiors, so windows are not cut out and pasted in. Ambient frames are merged, the room's brightness comes from them and its colour from the flash frame, and the windows are pulled in so the view outside stays natural.
  - On two test brackets the interior colour error fell from 0.38 to 0.06 and 0.35 to 0.07, window detail correlation rose from 0.74 to 0.95 and 0.76 to 0.97 with nothing clipped, and the wall beside the window showed no halo.
- **For agents:** `merge_flash_blend`.

### Note

- Not yet run on a real flash bracket (the tests used synthetic brackets made from real interior photos).

## v0.32.0 · 2026-10-14

### Added

- **Retouch Skin (Photo menu):** smooths and cleans skin across a session in one step, with smooth, shine, heal blemishes, sensitivity and keep freckles and moles.
  - Blemishes are found by how dark and red they are against the surrounding skin; eyes, nose and mouth are kept out; freckles and moles are kept.
  - It makes a skin mask plus a heal spot for each blemish, as one undo step, and a rerun replaces its own edits.
  - On six portraits, red spots fell from 35 to 5 on an acne portrait and 26 to 9 on a clear-skinned one. Freckles stayed on all three freckled faces. Fine texture dropped only 5 to 10 percent at smooth 40. About 5 seconds a photo.
- **For agents:** `retouch_skin`.

### Note

- Marks larger than 3 percent of the face width are left alone, and faces that cannot be found are skipped.

## v0.31.0 · 2026-10-14

### Added

- **Find photos by description:** a Describe tab in the Library Filter (Edit, Find by Description, Alt+Ctrl or Cmd+F) with indexing status and Install Model or Index Now. Results sort by Relevance, which sits in the sort list.
  - It uses the Google SigLIP model (Apache-2.0). OpenAI CLIP was dropped because its model card puts deployed use out of scope.
  - 50 photos indexed in 10.5 seconds, and 50,000 are searched in about 85 milliseconds.
- **Find Similar Photos (Edit menu).**
- **For agents:** `search_photos_by_description` and `find_similar_photos`.

### Note

- The model is a 213 MB download you install once.
- On twelve test queries the compressed model ranked the same as the full one on 11 of 12; the twelfth was a tie between two right photos.

## v0.30.2 · 2026-10-14

### Fixed

- **A bumpy ridge in a stacked time-lapse:** two faults were found. The sky line stepped by up to 12 pixels, and a moving camera (up to 7 pixels, with parallax) doubled the landscape's edges. The sky edge is now refined at full size, and the landscape is aligned to the middle frame with optical flow when it moved at least half a pixel.
  - On a real time-lapse, pixels differing from the middle frame fell from 0.83 to 0.17 percent over the landscape, 13.5 to 0.3 percent on a slatted building, and 4.9 to 1.7 percent along the sky line. The ridge is straight, and star widths are unchanged.

### Note

- The dish's reflections (averaged as landscape) and one spot on its upper rim still differ.

## v0.30.1 · 2026-10-14

### Fixed

- **Astro Stack on wide lenses:** stars at the edges of a wide frame did not line up, so they smeared. Stars are now picked across the whole frame, matched in six tiles, and corrected with a smooth warp. The sky is cut to regions that touch the top edge (a dish's reflection had been aligned as sky), and the ground area grows with the frame size (a dome edge had left a ghost).
  - On a real 4K time-lapse, stars were found in every third of the frame (236 to 316 per frame) and are sharper stacked than single in each (for example 6.02 to 5.89 bottom left). The ten frames stacked in 67 seconds with the dish and dome sharp.

### Note

- Noise fell 1.82 times, not the theoretical 3.16, because video compression noise is shared between frames.

## v0.30.0 · 2026-10-14

### Added

- **Client proofing without accounts (File, Export Proofing Gallery):** makes a self-contained gallery folder your client opens in any browser, from a file or any web host. They pick, reject, rate and comment, and send you a selections file with their name.
- **Import Client Selections (File menu):** sets the flags, ratings and comments, and makes a collection of the picks. A wrong file is refused. Client comments appear in the Comments panel as threads without a reply box.
- **For agents:** `proofing_gallery` and `import_client_selections`.
- Checked in Chromium on a slow computer: picks, rejects, ratings and comments survived a reload, and it fits in two columns at phone width.

### Fixed

- **A finished toast pushed earlier toasts up** during the export and import. It no longer does (the same problem elsewhere was fixed in v0.36.0).

### Note

- Astro Stack was also checked on a real night-sky photo: alignment within 0.023 pixels on about 380 stars, sky noise halved, ground about 3 times cleaner and a satellite trail removed. The sky model is used both to make and to stack the test frames, so the horizon result flatters it.

## v0.29.0 · 2026-10-14

### Added

- **Astro Stack (Photo menu, through the merge dialog):** stacks night-sky frames into a linear DNG.
  - Stars are aligned frame to frame while hot pixels and satellite trails are ignored, and the sky and landscape are stacked separately so stars stay sharp and the ground does not smear. Frames are kept on disk so memory stays flat.
  - On eight test frames, alignment was within 0.016 pixels, and sky error fell from 0.00392 (one frame) to 0.00126 stacked; a plain average reached only 0.00450. The satellite trail was removed.
- **For agents:** `merge_astro_stack`.

### Note

- Not verified on real night-sky raws: no public sequence was reachable. The test set models star motion, noise, hot pixels and a trail, but not lens distortion, which grows toward the corners of wide lenses (addressed in v0.30.1).
- Time: 46 seconds for 8 frames of 3.8 megapixels.

## v0.28.0 · 2026-10-14

### Added

- **Sessions with tethering (Session panel above Catalog, plus File and Library menu commands):** a session is a folder with Capture, Selects, Trash and Output. Tethered shots go into the open session's Capture, exports default to its Output, and edits and ratings are saved into the folder within seconds, so a second computer can open it and get them back. Move to Selects is Alt+Shift+J, and Move Back to Capture undoes it.
- **For agents:** `session` and `session_move`.

### Fixed

- **Re-importing an export applied the edits twice:** rendered exports used to carry the edit recipe. They no longer do.

### Note

- Not verified: a real tethered camera into a session, sessions on Windows paths, and very large sessions (the folder is scanned every 5 seconds).

## v0.27.0 · 2026-10-14

### Added

- **A learned noise reducer in Enhance:** uses the SCUNet real-world model (77 MB, an optional download). Amount keeps a share of the removed noise as grain, and the old noise reducer remains when the model is not installed. The Enhance note names the one in use.
  - On real smartphone noise at ISO 3200 to 10000 it scored 29.99 dB against the old denoiser's 26.80 (default) and 27.81 (full). A denoised DNG of an ISO 10000 crop keeps its brightness and crisp text, and tiles join seamlessly.

### Note

- It is slow: about 17 minutes for 16 megapixels on the 2-core test machine, as a background task with progress and Cancel. Faster on real machines and with CoreML, DirectML or CUDA.
- Not verified on high-ISO raws from interchangeable-lens cameras (the raws available were ISO 80 to 400).
- Two tiny layout shifts remain: the People list filling in and the new photo becoming active when Enhance finishes (both fixed in v0.37.0).

## v0.26.3 · 2026-10-14

### Added

- **Edge points on AI masks:** each segment of an AI mask now has dots along its edge so a wrong edge can be fixed by hand. Under a mask component's edge sliders, choose Edit Edge Points, then drag a dot, click the outline to add one, or Alt-click a dot to remove it. Reset Edge puts the original back.
  - Where dots are moved out the mask grows, where they are moved in it is cut, and where the outline is untouched the model's fine edge is kept. Holes stay holes.
  - On a portrait's Subject mask there were 56 dots; a drag saved, adding made 57, removing made 56, and Reset worked.

### Fixed

- **The mask panel jumped when a model finished:** a placeholder entry now holds the panel's layout while an AI mask is being made.
- **Develop showed the previous photo** for a moment after you opened a new one. It now switches at once and shows the new photo's thumbnail until the render arrives.

### Note

- Edge points are not a tool for agents yet (agents can still write an `outline` through `develop_set` masks).
- Opening the People list still adds rows after detection, a very small shift below the fold.
- The learned noise reducer was not started in this version (it arrives in v0.27.0).

## v0.26.2 · 2026-10-14

### Added

- **Better hair, skin and clothes masks:** a new optional model labels hair, face skin, body skin and clothes. Hair now covers long hair on both sides, hair under a hood (not the hood), and short crops.
- **Better people detection:** a second optional model finds each person, with a second pass on a crop around each one. It found 4 of 4 in a sunset group (the backlit person included), 8 of 8 on a bench, and nobody extra on a single portrait.
- **Remove People uses the same people** as Detect People, so a person removed from a group takes the arm and leg with them. Removing one man from a group took head, both legs, arm and towel.

### Fixed

- **Generative Remove squeezed the whole photo** to 512 pixels on large photos. It now fills a crop around the hole, so detail is kept on photos over 768 pixels.

### Note

- A soft smear can remain beside a neighbour where the fill invents what was behind them. Ball removal is still clean.
- The two models are downloads of 16 MB and 186 MB. Detect People takes about 15 seconds for four people and 30 seconds for eight on the 2-core test machine.
- The two layout shifts logged in v0.26.1 were not fixed in this version (see v0.26.3).

## v0.26.1 · 2026-10-14

### Fixed

- **Objects mask clicks selected the wrong thing:** a click was paired with an invented centre box, so a click outside the centre picked the wrong object. A click now selects the object under it (it used to need a drag).
- **Detect People missed people facing away** and merged linked groups. It now finds 7 of 8 and 3 of 4, and keeps legs with their person.
- **Culling scored a low-key portrait's exposure as 0.** It is now judged on the face (93.4).
- **Enhanced DNGs from non-raw sources came out far too bright** (average brightness 100 to 161). They now match the source (100.6 and 99.9 against 100.4). The Focus Stack of a TIFF bracket from v0.25.0 had the same fault.

### Note

- This is the first time the model features were run on their real models (all eight installed and loaded). Working: sky on clear skies, people, subject, face skin, hair, lips, teeth, depth range, face detection (4 of 4), face recognition, generative remove of a ball, super resolution (sharper than bicubic) and object selection by box.
- Correction to v0.26.0: the learned noise reducer was deferred for a reason that turned out to be wrong, as downloads were never blocked.
- Known limits: the sky model counts a fog-filled valley as sky on one photo, landscape water covers only breaking waves, removing one person from an interlocked group leaves a hand and a leg, a laughing face can read as eyes closed, and super resolution takes 56 seconds for 0.19 megapixels on the 2-core test machine.
- Two small layout shifts were measured and not yet fixed: an AI mask result growing the panel seconds after the click, and Develop correcting the image size shortly after load.

## v0.26.0 · 2026-10-14

### Added

- **Skin Tone in the Color Mixer:** evens out blotchy, uneven skin without flattening it, as Capture One's skin-tone tools do.
  - **Pick** a patch of skin, or set Skin Hue and Skin Range by hand.
  - **Hue, Saturation and Lightness Uniformity** pull redness, patchy colour and uneven brightness toward the surrounding skin. The face's light and shadow stay, and nothing outside the skin range changes.
  - It works in layers and with Sync, presets and Claude (`develop_set` with `skin.*`).

### Fixed

- **The panels jumped after using the White Balance selector:** the tool closed when the result came back and the panels below moved up. It now closes as you click.
- **Slider thumbs counted as layout movement** whenever a value changed from outside (Auto, presets, undo). They now move without touching the layout.

### Note

- The learned noise reducer planned for this version needs a model downloaded and verified, which was not possible from the build machine. It moves to a later version.

## v0.25.0 · 2026-10-14

### Added

- **Focus Stack (Photo, Focus Stack, Alt+Ctrl or Cmd+M):** merges photos of one scene focused at different distances into one photo sharp from front to back, for macro, product and near-to-far landscapes.
  - **How it works:** frames are aligned to the middle one, correcting the slight size change as focus moves. The sharpest frame is kept at each point with seamless blending, and the result is cropped to the area every frame covers.
  - **Output:** a DNG beside the middle frame with its settings, stacked with the frames if you like. A preview shows the result before you merge.
- **For agents:** `merge_focus_stack`.

## v0.24.0 · 2026-10-14

### Added

- **Adjustment layers (Develop, Layers panel under the Histogram):** the feature reviewers most often say Lightroom lacks. A layer is its own copy of the photo's colour and tone settings, blended in through a mask at an opacity.
  - **Full toolset:** select a layer and every slider, the tone curve, the colour mixer, colour grading, detail and effects change that layer only. Masks reach 17 local sliders; layers reach everything.
  - **Masks:** the whole photo, Subject, Sky, Background, People, or any mask built in the Masking tool, so brushes, gradients, ranges and the new edge controls all work. Invert flips it.
  - **Layer controls:** opacity, show and hide, rename, duplicate and delete, all with undo, up to eight layers per photo.
  - **What stays with the photo:** white balance, crop, geometry, lens corrections, noise reduction, the profile and treatment. A banner and an accent edge on the right column show when you are editing a layer.
- **For agents:** `add_layer` and `set_layer`, for example "make the sky's saturation +40 in a layer at 70 percent".

### Note

- Layers are formlit's own. They are not copied by Sync or Paste unless chosen, and they are not written to the XMP that Lightroom reads.

## v0.23.0 · 2026-10-14

### Added

- **Edge controls on AI masks:** Subject, Sky, Background, People, Objects and Landscape masks each get three sliders:
  - **Refine Edge** snaps the mask to the edges in the photo, for hair and soft outlines.
  - **Shift Edge** grows or shrinks the mask, up to 2 percent of the photo's long side, to clear a halo or take in a missed rim.
  - **Feather** softens the edge, up to 3 percent of the long side.
  - All three look the same in the preview, at 1:1 and in a full-size export.
- **Refine Edge Brush:** paint over hair, fur or a fuzzy edge and the mask follows the photo's edges only where you paint. It is in the mask's Add row, and any brush component can be switched to Refine.
- **For agents:** `add_ai_mask` takes `refine`, `shift` and `feather`.

### Note

- The edge settings and the Refine Edge Brush are formlit's own. Lightroom has no equivalent fields, so they are left out of the XMP written for it.

## v0.22.0 · 2026-10-14

### Added

- **Code replacements for captions,** for news and sports work (Metadata, Code Replacements):
  - Keep a set of short codes and their text, such as a team roster with one line per player.
  - Type a code between marks in any metadata field (`=23=`) and it becomes the full text when saved, from the Metadata panel, presets, templates or Claude.
  - Codes not in the set stay as typed and a message names them.
  - Sets can be imported from a tab or comma separated text file, switched and deleted. The marks can be `=`, `\`, `#`, `~` or `|`.
- **Caption variables:** `{date}`, `{time}`, `{camera}`, `{lens}`, `{filename}`, `{city}`, `{event}` and more fill from each photo when metadata is saved, so one caption written for a whole set comes out right on every photo.
- **Required fields (Metadata, Required Fields):** choose the fields every photo must have before delivery. Export warns about photos missing them and says which fields, or refuses them if you turn that on. Check Required Fields counts them at any time.
- **For agents:** `set_code_replacements` and `check_required_metadata`. `set_metadata` expands codes and variables too.

### Fixed

- **The Metadata panel showed the text as typed after an edit** instead of what was saved. It now shows the saved text.

## v0.21.0 · 2026-10-14

### Added

- **Cull view (K, or the new button beside Survey):** a full-screen pass built for speed, the first item of the plan drawn from the 2026-10-13 research into what professionals want from Lightroom.
  - Photos come in burst order: each group of near-duplicates is shown together, with the best frame starred.
  - **P** picks, **X** rejects and **1** to **5** rate the frame on screen, then move to the next. **U** unflags.
  - **Shift+P** keeps the frame on screen, rejects the rest of its burst and jumps to the next burst.
  - **Left** and **Right** step frames; **Up** and **Down** jump bursts and land on each burst's best frame.
  - The top bar shows where you are, the sharpness, exposure and eyes-open scores (low ones in red) and how many are picked, rejected and left. **Analyze** scores the photos not yet analyzed.
  - The face column shows each face at full size with its own eyes-open and sharpness scores, when the faces model is installed.
  - The next five and the previous two frames are loaded in the background, so moving between frames does not wait.
- **For agents:** `get_cull_groups` returns the same bursts, best frames and per-face scores.

### Fixed

- **The Keywording panel jumped when you moved between photos:** its suggestions wrapped onto more rows and pushed the panels below it down. The suggestions now have a fixed space.

## v0.20.0 · 2026-10-13

### Added

- **The filmstrip (the All Photographs strip) collapses and moves:**
  - **Collapse** to just its header bar with the arrow button at its right end, a double-click on the header, Alt+F6, or View, Collapse Filmstrip. Expanding returns it to the height you dragged it to.
  - **Move** it above the photo area with the button beside the arrow or View, Filmstrip at Top; the same button moves it back. Its resize edge follows it.
  - Right-click the header for Collapse, Top and Show. Both settings are kept between sessions and saved with workspaces; Default puts it back at the bottom, open, and Working with Claude collapses it to give the Chat more room.

### Fixed

- **Hiding the filmstrip (F6) after resizing it left an empty band** where it had been. The row now closes whatever height it was dragged to.

## v0.19.0 · 2026-10-13

### Added

- **The Chat tab as a real bridge to Claude Code, for people who never open a terminal:**
  - **Formatting:** answers are formatted as they arrive: paragraphs, **bold**, bulleted and numbered lists, headings, small tables and code. Finished paragraphs are rendered once, and only the line still being written shows as plain text. The renderer builds page elements, never raw HTML, and links cannot navigate the window away.
  - **Previews:** the photos Claude looks at (`get_preview`) appear in the chat under the step that fetched them.
  - **Live token tracking** in the Chat bar, with a plain-language tooltip:
    - how much of Claude's working memory the conversation uses, against the model's window (for example "Memory 19.8k of 1M"; it turns the accent colour above 80 percent);
    - the reply's tokens as they are written;
    - the whole chat's tokens and cost.
    - Each answer ends with its time, steps, tokens and cost.
  - **Open in Claude Code** continues the same conversation in a Claude Code terminal tab (`claude --resume`). **From Claude Code...** lists the Claude Code conversations started in formlit and brings one into the Chat, with its messages, tool calls and photo strips.
  - **Context:** every message now also tells Claude the current module and the active photo, along with the selection.
- **More customization:**
  - The filmstrip's height can be dragged (72 to 320 px). It is kept between sessions and saved with workspaces.
  - Right-click the module picker to show or hide modules. Hidden ones stay in the Window menu and keep their shortcuts.
  - While you drag a panel near the top or bottom of its column, the column scrolls, so Develop's long column can be reordered end to end.

### Fixed

- **Dragging a panel stopped after its first move in Develop, and the new order was not saved.** The v0.18.0 rewrite of `panel.ts` captured the pointer on the panel header, and moving the panel releases that capture. Dragging now follows the pointer on the window, saves the order and survives a reload. Every panel in all seven modules was re-checked: open, close, Alt-click solo, on/off switches and drag.

## v0.18.0 · 2026-10-13

### Added

- **Workspace customization:**
  - **Hide or show panels:** right-click any panel header for a list of that column's panels with checkmarks, plus Solo Mode and Reset Panels.
  - **Reorder panels:** drag a panel header up or down its column. The order is kept per module and side.
  - **Solo Mode:** set per side (Window, Workspace, Solo Mode). Opening a panel closes the others in that column, and Alt-click still does this once.
  - **Workspaces:** Window, Workspace switches between five built-in layouts: Default; Culling: Big Grid; Editing: Wide Panels, One at a Time; Working with Claude (left panels hidden, the dock open on Chat); and Photo Only.
  - **Your own workspaces:** Save Workspace keeps the side widths, what is shown, panel order and Solo Mode. Delete Workspace removes one. They are stored in formlit's preferences.
  - **Reset Panels** shows every panel again in its original order.
- **Hidden areas survive a restart:** which areas you hid (left panels, right panels, filmstrip, toolbar) is now kept between sessions, like the widths already were.

### Changed

- **New AI icons:** the three-star sparkle is gone.
  - Claude Code and the Ask line use a small robot head.
  - Chat uses a speech bubble with the same eyes.
  - Features run by local AI models (Denoise, Build Depth) use a processor chip.

## v0.17.0 · 2026-10-13

### Added

- **Photo strips in the Chat tab.**
  - When Claude uses a tool on photos (rating, flagging, developing, matching, a preview), the tool's chip is followed by small thumbnails of those photos: up to eight, then a count.
  - Clicking the strip selects those photos in the window.
  - The engine's `chat.tool` events carry the photo ids, read from the tool's `id`, `ids`, `reference`, `from` and `photo` arguments.

### Still not in formlit

- Instagram 4:5 and Stories 9:16 presets: Meta's help pages still refuse automated reading, so their sizes remain unverified and are not built in.

## v0.16.0 · 2026-10-13

### Added

- **`build_app.bat`: the one-shot desktop build on Windows, the twin of `./build_app`.**
  - It checks Python, Node 22 and Rust, then installs the engine and the window (`--lite` passes through).
  - It installs the desktop packages, builds the window, freezes the engine and runs the Tauri build.
  - It stops at the first failing step with a sentence saying so, and `--open` opens the folder with the installers.
  - `./build_app` on Windows now points to it.

### Changed

- **Chat messages show only what you typed, with a short note such as "with 7 selected photos".** The selected photo ids still go to Claude with the message, as before.

### Verified

- **Stop in the Chat tab** ends a long answer within about half a second, marks it Stopped and leaves no Claude Code process behind. The next message works normally.

## v0.15.0 · 2026-10-13

### Added

- **A Chat tab in the dock:** the chat button, Window or Help, Chat with Claude, or Alt+Cmd or Ctrl+J.
  - Type in the Ask line and Claude answers as a plain conversation. It runs through `claude -p` with formlit's tools only, the way Format's chat does.
  - Each tool call appears as a small chip with its arguments as it happens, and the answer streams in word by word.
  - It shows the time and number of steps when done, and offers Stop and New Chat.
  - The conversation continues across messages (`--resume`) and is restored when the window reloads.
  - The current selection is passed along, as it already was for the Claude Code tab.
  - Engine side: `chat.send`, `chat.state`, `chat.cancel` and `chat.reset`. They are window-only: outside agents are refused, like the terminal and Claude Code commands.

## v0.14.0 · 2026-10-13

### Added

- **Preferences, AI agents, Claude Code in formlit:**
  - A status line shows the Claude Code version, where it was found and the folder it starts in.
  - Starts in folder replaces `FORMLIT_AGENT_DIR`.
  - Claude Code program replaces `FORMLIT_CLAUDE_BIN`.
  - Start with message gives every new Claude Code tab a first message.
  - The environment variables still work; a setting in Preferences comes first.
  - A program path that cannot run is reported, and the one found on the computer is used instead.
  - A folder that cannot be created is refused with a message naming it.

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
