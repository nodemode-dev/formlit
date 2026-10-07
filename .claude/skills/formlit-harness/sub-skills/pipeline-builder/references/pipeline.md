# The develop pipeline

## Stages

| Stage | Where | Input to output | Cache key holds |
| --- | --- | --- | --- |
| Decode | `app/services/decode.py` | file to linear Rec. 2020 float, `info` (camera, as-shot white balance, Camera Look tone, full size) | `SOURCE_VERSION` |
| Geometry | `app/develop/geometry.py` `Frame` | orientation, crop rect and angle, flips, lens distortion, upright homography; output size | crop, orientation, geometry, optics geometry |
| Linear | `render._stage_render` | white balance (Bradford from the as-shot illuminant), a DCP camera profile (`dcp.apply_linear`), noise reduction, defringe, lens blur | the geometry key, wb, nr settings, sizes, lens blur, the profile id when it is a DCP |
| Planes | `app/develop/planes.py` | low-frequency planes for clarity, texture, dehaze and shadows, computed on a proxy and upsampled with guided-filter coefficients | the sigmas in use |
| Masks | `app/develop/masks.py` | alpha per mask from linear, radial, brush, AI bitmaps, colour and luminance ranges | masks and the output frame |
| Finish | `finish.py` (reference), `kernel.py` (numba) | tone, curves, mixer, grading, detail, vignette, grain, local adjustments, output space | not cached |

`render.render` and `render.render_region` run the stages; `kernel.best_finish()` picks the kernel once `kernel.warm()` has compiled it, else the reference.

## Coordinate frames

- Source pixels: the decoded image, before orientation.
- Norm: the oriented, uncropped frame, 0 to 1 on both axes. Masks, spots, red eye and AI bitmaps live here, so crops never move them.
- Output: the cropped, straightened frame at the render size. `Frame.out_to_norm(w, h)` maps output pixels to norm.
- Sizes (brush radius, radial extent, feather) are fractions of the long side, so they render the same at every size.
- The `X-Geometry` render header carries the 3 x 3 output-to-norm matrix for the window's tools.

## Region renders

1:1 views render a region `[u0, v0, u1, v1]` of the output with a margin of `16 + 3 x` the largest plane sigma in pixels, then crop it away, so planes see the same neighbourhood as a full render. Region and full agree within 1/255.

## The kernel contract

- Same inputs as the reference: the linear image, planes, evaluated masks, the effective settings, frame, size and pixels per long side.
- Scalars travel in a float64 `params` array and on/off states in an int64 `flags` array; hue-based tables (mixer, B and W) are precomputed lookup tables with 4096 entries.
- Per-pixel temporaries are allocated per row, not per pixel.
- `NUMBA_CACHE_DIR` is set under the data folder so compiled kernels survive restarts; the PyInstaller build collects llvmlite and numba submodules.

## Camera Look

For raws, `camera_look.fit` fits a 32-knot tone curve (and, for the Camera Look profile, a colour matrix) from the camera's embedded JPEG preview, so the default render matches the camera's own rendering. `GENERIC` is the fallback curve when no preview exists.

## Profiles

- One hook: `profiles.lut_of(dev)` returns the 3D table and amount that both finish implementations apply at the end. Tables are `[b][g][r]` arrays, the `.cube` order.
- Built-in looks are baked by `profiles.table_of(pid, base)` (a 33-point lattice run through the numpy finish with the look's per-pixel deltas). Clarity, Texture and Dehaze deltas and a B&W look's `bw.*` mix stay offsets (`offset_key`); a B&W look is the treatment, those offsets and a table for its tone and toning.
- The table runs after the tone curve and before grain, in the output space's terms: `lut_of(dev, space)` returns `in_space(table, space)`, re-expressed for P3, Adobe RGB, ProPhoto or Rec.2020.
- Any id starting `fl.camera` turns on the fitted Camera Look (`finish.camera_matrix_look`). Maker sets live in `camera_styles.py`; `render.effective(dev, info)` adds the as-shot style (`info.cameraStyle`) as `profile.base`, and `_delta` builds each style relative to it.
- Adobe creative profiles (`.xmp` with `crs:RGBTable`) are read by `adobe_profile.read`, resampled to sRGB and stored as `lut:[name]` with a JSON sidecar (name, group, grayscale). Look-table-only profiles are refused.
- DCPs are stored as files and applied in the linear stage (`dcp.apply_linear` with the source `info`, the white balance and, for 3D look tables, Exposure), never baked; their tone curve replaces the camera tone in `finish.camera_tone`. The decoder records `camToRec2020`, `sensorGain` and `cameraStyle`; `previews.source` adds `camera`.
- Changing the finish means `table_of`'s cache (`lru_cache`) holds stale tables until the engine restarts; uvicorn's reload does that in development.
