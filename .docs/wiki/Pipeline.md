# Pipeline

The develop pipeline lives in `backend/app/develop/` and renders everything formlit shows or writes: the Develop view, 1:1 regions, thumbnails, previews and exports all come from it, so what you see is what you export.

## Order

1. **Geometry.** `geometry.py` builds a `Frame` from crop, angle, orientation, lens profile, Upright and transform, and samples the source through it at the output size.
2. **Repairs.** Spots (heal, clone, remove fills) and red eye in `retouch.py`, on the sampled image.
3. **White balance** as a Bradford adaptation from the as-shot illuminant in linear Rec.2020, then noise reduction (`planes.py`), defringe (`fringe.py`) and Lens Blur (`lensblur.py`).
4. **Planes.** Log luminance, a guided-filter base, clarity, texture, dark channel and chroma planes, computed on a proxy with radii relative to the long edge so a region, a fit view and a full export match.
5. **Masks.** `masks.py` evaluates every visible mask into an alpha and its terms (local sliders, tint, Point Color, curve).
6. **Finish.** One per-pixel stage: dehaze, exposure, local terms, the tone LUT, calibration, colour operations in OkLCh (mixer, Point Color, vibrance, saturation, B&W), grading, vignette, gamut mapping, encoding, the point curves, grain and the profile LUT. Local mask curves apply after it through each mask's alpha.

## Two renderers

`kernel.py` is the numba finish used whenever its compiled kernel is ready; `finish.py` is the numpy reference it must match. Change both together and compare them on the demo photos.

## Settings

`shared/controls.json` declares every control (id, label, section, range, default) and the local mask sliders; `settings.py` reads it, clamps values and groups them for copy and sync. Profiles (`profiles.py`) apply as offsets beneath the sliders, or as LUTs for imported .cube and .dcp looks. `render.effective` merges the profile and the treatment before rendering.

## HDR

`backend/app/output/gainmap.py` makes HDR from an SDR rendition and an under-exposed render: the ratio becomes a gain map, used for Ultra HDR JPEG, and the HDR image for AVIF, JPEG XL and float TIFF in PQ with SDR white at 203 nits.
