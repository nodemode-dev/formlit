# HASHOUT_LOG · demos/develop · formlit

Rationale and decisions for demo 2 (develop). Source files stay comment-free.

Current build version: v0.49.3 (the version of the app this demo was built against).

## What this demo adds to demo 1

Demo 1 ports the global develop path and lists masks, local adjustments, presets of your own and virtual copies as not done. This demo is those four, plus a library already edited with a tone curve, colour mixer and colour grading so Develop opens looking like finished work. The focus table names "masks and local adjustments, tone curve, HSL, colour grading, presets you make and apply, virtual copies, before and after". Tone curve, colour mixer, colour grading wheels and Before and After already exist in demo 1's panels and are reused as they are; building them a second time would only fork code.

Features checked against the repo before use: masks (`backend/app/develop/masks.py`, `frontend/src/modules/develop/masks.ts`), the New Develop Preset dialog (`preset-dialog.ts`), `photo.virtualCopy` (`cmd_library.py`). Dropped as not feasible offline: people and landscape parts, depth range (they need the desktop models), point colour in a mask, edge-point editing, brush Auto Mask and Edge Snap.

## Why a render swap instead of forking demo 1

Every consumer of demo 1's pipeline (Develop canvas, thumbnails, loupe preview, export, the Before pane) imports `engine/render`. The Vite plugin in `vite.config.mjs` resolves that one import, when it comes from a `demo/src` file, to `src/render-masks.ts`, whose `Renderer` extends the original. Masks therefore appear everywhere with no change under `demo/`. Imports from `src/` itself still reach the original, which the subclass needs.

## How a mask renders

The global render runs first. For each visible mask that has any adjustment, the mask's local sliders are added to a copy of the settings (`adjustedDev`: exposure to `light.exposure`, Temp as a mired shift of the white balance, Texture and Clarity to `effects`, and so on, scaled by the mask's Amount) and rendered by a second, separate `Renderer` so the first one's caches survive. The result is blended by the mask alpha onto the global render: `out += alpha * (adjusted - global)`, so several masks accumulate. This is an approximation of the desktop engine, which applies local stages inside the pipeline; it is cheap, uses the demo's own finish code, and shows the same visible result for exposure, tone, colour and detail sliders. The adjusted render is cached per mask settings, so moving a pin or painting recomputes only the alpha, not the image.

Dragging uses the same low resolution pass as demo 1's sliders.

## Mask shapes

Coordinates are normalised to the oriented photo, as in the engine. Gradients and brush sizes are in "iso" units (fractions of the long edge) so a circle stays a circle on a portrait or landscape frame. Mapping from output pixel to photo uses one affine transform built from the same crop rect, angle and flips as `Frame.sample`, so masks follow crop and straighten; the keystone matrix of the Transform panel is not applied to masks.

- Linear and radial: smoothstep falloffs as in `masks.py`.
- Brush: dabs along each stroke with spacing 0.14 of the radius, per-dab flow, per-stroke density, erase. The stroke being painted is kept apart from the strokes already stored so a drag does not append a stroke per move.
- Luminance range: smooth band on the luma of the global render.
- Color Range: Oklab distance with the engine's tolerance formula and refine mapping; picks sample the displayed render.
- Subject, Sky and Background: alpha bitmaps. The desktop app runs a model; a page cannot. Six bitmaps were made offline (OpenCV GrabCut seeded from colour and position, then a guided filter) for the photos that use them, and the buttons are disabled with a reason on other photos. Background is the inverse of Subject. Edge controls are real: Refine Edge is a guided filter on luma, Shift Edge a grey-scale dilate or erode, Feather a Gaussian.

## Edge refine tuning

The first Refine Edge used the engine's tiny regularisation (4e-3 down to 2e-4) and mixed in at twice the slider. On a sky with strong cloud edges that let the mask leak along the clouds. The demo's regularisation is larger (6e-2 down to 3e-4) and the mix is the slider value, so 30 to 40 reads as a gentle snap.

## Overlay and pins

A canvas above the photo draws the red overlay (alpha of the selected mask at 640 px, cached until settings change), the gradient lines, the radial ellipse with its feather ring and the brush cursor. Pointer events are taken in the capture phase only while the Masking panel is open, no tool is active and the view is not in Before mode, so Crop, White Balance and the Split handle keep working. The overlay renders its own global pass at 640 px, cached by settings other than masks, so pin drags do not re-render the photo for it.

Show Overlay starts off: with it on, the first screen is a red wash that hides the grade the demo exists to show.

## Presets you make

The app's own `PresetDialog` is reused. A preset keeps only the keys of the ticked groups; applying removes the same keys from the photo and merges the preset's, scaled by Amount for numbers except hue, temperature and tint. Presets live in `localStorage` when it is available and in memory when it is not. Two are seeded from the demo's own edits through the same `pick` function, so "Alpine Pink Sky" and "Soft Film Mist" are what the dialog would have made.

## Virtual copies

A copy is a new store item that spreads the master and redefines `src`, `small`, `full`, `blob` and `used` as accessors on the master, so one decoded photo serves both and a later upgrade to full size reaches the copy without decoding twice. Its settings and history are its own. It sits in the Virtual Copies collection. The copy name carries a suffix so the grid shows two different names.

## Loading without a flash

The app starts in Develop. Until the first render, `.is-booting` hides the "No photo selected" card and draws a quiet placeholder where the photo will be, so the empty message never shows; the class is removed in the first histogram callback, after the canvas has its pixels. The built-in Presets panel is closed on boot so My Presets and Virtual Copies are visible without scrolling.

## Files shipped

The nine photographs are demo 1's, repacked as `develop.js` with their EXIF; nothing is downloaded. The link row names the three demos in the status bar and links by relative path.

## Not done

Healing, people and landscape parts, depth and edge range, point colour, brush Auto Mask and Edge Snap, mask tone curve, Transform keystone inside masks, true engine-identical mask maths.
