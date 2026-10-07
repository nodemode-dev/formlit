# Look recipes

Starting points, not answers. Propose with `get_preview` values, adjust by eye, then commit.

Presets (`list_presets`, ids like `builtin:color/clean-punch`) are applied with `apply_preset`. Profiles (`fl.color`, `fl.camera`, `fl.monochrome`, `fl.film.warm`, `fl.cine.teal`, `fl.bw.punch` and the rest from `develop.info`) are set with `develop_patch` `{"profile": {"id": "...", "amount": 100}}`.

| Request | Values | Notes |
| --- | --- | --- |
| Brighter, airy | `light.exposure` +0.4, `light.highlights` -30, `light.shadows` +40, `light.blacks` +10, `color.vibrance` +10 | keep whites under clipping: watch the preview's brightest areas |
| Moody, darker | `light.exposure` -0.4, `light.contrast` +20, `light.highlights` -20, `light.blacks` -20, `color.saturation` -10, `effects.clarity` +10 | a radial mask with `invert: true`, `adjust: {"exposure": -0.4}` deepens the edges |
| Warmer | `wb.temp` +600 to +1200 (from its current value), `wb.tint` +5 | raws: temperature is in kelvin; JPEGs follow the same scale relative to as shot (6500). The interface shows non-raw photos as -100 to +100, 0.75 mired per step, but the settings and tools always take kelvin |
| Cooler | `wb.temp` -600 to -1200 | |
| Fix a dull sky | `add_ai_mask` kind `sky`, adjust `{"exposure": -0.5, "highlights": -30, "saturation": 15, "dehaze": 10}` | add a linear mask if the horizon is flat and the AI sky misses haze |
| Make the subject pop | `add_ai_mask` kind `subject`, adjust `{"exposure": 0.3, "clarity": 10, "texture": 10}` | |
| Soften skin | `add_ai_mask` kind `people`, adjust `{"texture": -30, "clarity": -10}` | never on the whole photo |
| Black and white | `develop_patch` `{"treatment": "bw"}`, then `light.contrast` +20, `effects.clarity` +15 | B and W mix bands are `bw.*` ids (`bw.blue` -30 darkens skies); the profile `develop_patch` `{"profile": {"id": "fl.bw.punch"}}` is a fast start |
| High ISO cleanup | `detail.nrLuminance` 30 to 50, `detail.nrColor` 25, `detail.sharpenAmount` 40, `detail.sharpenMasking` 40; or `denoise` amount 50 for a DNG | the AI denoise result beats the sliders above ISO 3200 |
| Hazy landscape | `effects.dehaze` +20, `light.blacks` -10, `color.vibrance` +15 | dehaze over 40 shifts colour; check the preview |
| Product on white | `light.whites` +30, `light.exposure` until the background reads 250, `color.saturation` 0 | square crop with `develop_patch` `{"crop": {"rect": [x0, y0, x1, y1]}}` sized to the frame's aspect |
| Teal and orange | `grading.shadows.hue` 190, `grading.shadows.sat` 30, `grading.highlights.hue` 35, `grading.highlights.sat` 25, `mixer.green.sat` -15 | the profile `{"profile": {"id": "fl.cine.teal", "amount": 100}}` does the same, with `profile.amount` to scale it |
| Match a set | develop one, `sync_settings` with `groups: ["whiteBalance", "basicTone", "presence"]` | re-check exposure per frame afterwards with `delta` |
| Match the camera's picture style | `{"profile": {"id": "fl.camera.vivid"}}`, or a maker style from `develop.info` such as `fl.camera.canon.faithful` or `fl.camera.fujifilm.classicchrome` | raws only; Camera Look (`fl.camera`) is the photo as shot, the styles are built relative to it |
