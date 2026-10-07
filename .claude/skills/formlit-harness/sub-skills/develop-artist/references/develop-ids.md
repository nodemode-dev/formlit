# Develop setting ids

Every id `develop_set` and `get_preview` values accept, with its range and default. Regenerate after an engine change with `./formlit cli develop.controls` and rewrite this table from its `controls` list.

## Contents

Profile · White balance and color · Light · Tone curve (parametric) · Color mixer (HSL) · Black and white mix · Color grading · Presence · Post-crop vignette · Grain · Detail · Lens corrections · Transform · Calibration · Crop · Lens blur · Local adjustments (mask adjust keys) · White balance presets · Sync and copy groups · Crop aspects

## Profile

| id | label | min | max | default |
| --- | --- | --- | --- | --- |
| `profile.amount` | Amount | 0 | 200 | 100 |

## White balance and color

| id | label | min | max | default |
| --- | --- | --- | --- | --- |
| `wb.temp` | Temp | 2000 | 50000 | 6500 |
| `wb.tint` | Tint | -150 | 150 | 0 |
| `color.vibrance` | Vibrance | -100 | 100 | 0 |
| `color.saturation` | Saturation | -100 | 100 | 0 |

## Light

| id | label | min | max | default |
| --- | --- | --- | --- | --- |
| `light.exposure` | Exposure | -5 | 5 | 0 |
| `light.contrast` | Contrast | -100 | 100 | 0 |
| `light.highlights` | Highlights | -100 | 100 | 0 |
| `light.shadows` | Shadows | -100 | 100 | 0 |
| `light.whites` | Whites | -100 | 100 | 0 |
| `light.blacks` | Blacks | -100 | 100 | 0 |

## Tone curve (parametric)

| id | label | min | max | default |
| --- | --- | --- | --- | --- |
| `curve.highlights` | Highlights | -100 | 100 | 0 |
| `curve.lights` | Lights | -100 | 100 | 0 |
| `curve.darks` | Darks | -100 | 100 | 0 |
| `curve.shadows` | Shadows | -100 | 100 | 0 |
| `curve.splitShadows` | Shadows split | 10 | 70 | 25 |
| `curve.splitMid` | Midtones split | 20 | 80 | 50 |
| `curve.splitHighlights` | Highlights split | 30 | 90 | 75 |
| `curve.refineSaturation` | Refine Saturation | 0 | 100 | 100 |

## Color mixer (HSL)

| id | label | min | max | default |
| --- | --- | --- | --- | --- |
| `mixer.red.hue` | Red Hue | -100 | 100 | 0 |
| `mixer.red.sat` | Red Saturation | -100 | 100 | 0 |
| `mixer.red.lum` | Red Luminance | -100 | 100 | 0 |
| `mixer.orange.hue` | Orange Hue | -100 | 100 | 0 |
| `mixer.orange.sat` | Orange Saturation | -100 | 100 | 0 |
| `mixer.orange.lum` | Orange Luminance | -100 | 100 | 0 |
| `mixer.yellow.hue` | Yellow Hue | -100 | 100 | 0 |
| `mixer.yellow.sat` | Yellow Saturation | -100 | 100 | 0 |
| `mixer.yellow.lum` | Yellow Luminance | -100 | 100 | 0 |
| `mixer.green.hue` | Green Hue | -100 | 100 | 0 |
| `mixer.green.sat` | Green Saturation | -100 | 100 | 0 |
| `mixer.green.lum` | Green Luminance | -100 | 100 | 0 |
| `mixer.aqua.hue` | Aqua Hue | -100 | 100 | 0 |
| `mixer.aqua.sat` | Aqua Saturation | -100 | 100 | 0 |
| `mixer.aqua.lum` | Aqua Luminance | -100 | 100 | 0 |
| `mixer.blue.hue` | Blue Hue | -100 | 100 | 0 |
| `mixer.blue.sat` | Blue Saturation | -100 | 100 | 0 |
| `mixer.blue.lum` | Blue Luminance | -100 | 100 | 0 |
| `mixer.purple.hue` | Purple Hue | -100 | 100 | 0 |
| `mixer.purple.sat` | Purple Saturation | -100 | 100 | 0 |
| `mixer.purple.lum` | Purple Luminance | -100 | 100 | 0 |
| `mixer.magenta.hue` | Magenta Hue | -100 | 100 | 0 |
| `mixer.magenta.sat` | Magenta Saturation | -100 | 100 | 0 |
| `mixer.magenta.lum` | Magenta Luminance | -100 | 100 | 0 |

## Black and white mix

| id | label | min | max | default |
| --- | --- | --- | --- | --- |
| `bw.red` | Red | -100 | 100 | 0 |
| `bw.orange` | Orange | -100 | 100 | 0 |
| `bw.yellow` | Yellow | -100 | 100 | 0 |
| `bw.green` | Green | -100 | 100 | 0 |
| `bw.aqua` | Aqua | -100 | 100 | 0 |
| `bw.blue` | Blue | -100 | 100 | 0 |
| `bw.purple` | Purple | -100 | 100 | 0 |
| `bw.magenta` | Magenta | -100 | 100 | 0 |

## Color grading

| id | label | min | max | default |
| --- | --- | --- | --- | --- |
| `grading.shadows.hue` | Shadows Hue | 0 | 360 | 0 |
| `grading.shadows.sat` | Shadows Saturation | 0 | 100 | 0 |
| `grading.shadows.lum` | Shadows Luminance | -100 | 100 | 0 |
| `grading.midtones.hue` | Midtones Hue | 0 | 360 | 0 |
| `grading.midtones.sat` | Midtones Saturation | 0 | 100 | 0 |
| `grading.midtones.lum` | Midtones Luminance | -100 | 100 | 0 |
| `grading.highlights.hue` | Highlights Hue | 0 | 360 | 0 |
| `grading.highlights.sat` | Highlights Saturation | 0 | 100 | 0 |
| `grading.highlights.lum` | Highlights Luminance | -100 | 100 | 0 |
| `grading.global.hue` | Global Hue | 0 | 360 | 0 |
| `grading.global.sat` | Global Saturation | 0 | 100 | 0 |
| `grading.global.lum` | Global Luminance | -100 | 100 | 0 |
| `grading.blending` | Blending | 0 | 100 | 50 |
| `grading.balance` | Balance | -100 | 100 | 0 |

## Presence

| id | label | min | max | default |
| --- | --- | --- | --- | --- |
| `effects.texture` | Texture | -100 | 100 | 0 |
| `effects.clarity` | Clarity | -100 | 100 | 0 |
| `effects.dehaze` | Dehaze | -100 | 100 | 0 |

## Post-crop vignette

| id | label | min | max | default |
| --- | --- | --- | --- | --- |
| `vignette.amount` | Vignette | -100 | 100 | 0 |
| `vignette.midpoint` | Midpoint | 0 | 100 | 50 |
| `vignette.roundness` | Roundness | -100 | 100 | 0 |
| `vignette.feather` | Feather | 0 | 100 | 50 |
| `vignette.highlights` | Highlights | 0 | 100 | 0 |

## Grain

| id | label | min | max | default |
| --- | --- | --- | --- | --- |
| `grain.amount` | Grain | 0 | 100 | 0 |
| `grain.size` | Size | 0 | 100 | 25 |
| `grain.roughness` | Roughness | 0 | 100 | 50 |

## Detail

| id | label | min | max | default |
| --- | --- | --- | --- | --- |
| `detail.sharpenAmount` | Sharpening | 0 | 150 | 0 |
| `detail.sharpenRadius` | Radius | 0.5 | 3 | 1 |
| `detail.sharpenDetail` | Detail | 0 | 100 | 25 |
| `detail.sharpenMasking` | Masking | 0 | 100 | 0 |
| `detail.nrLuminance` | Noise Reduction | 0 | 100 | 0 |
| `detail.nrDetail` | Detail | 0 | 100 | 50 |
| `detail.nrContrast` | Contrast | 0 | 100 | 0 |
| `detail.nrColor` | Color Noise Reduction | 0 | 100 | 0 |
| `detail.nrColorDetail` | Detail | 0 | 100 | 50 |
| `detail.nrColorSmoothness` | Smoothness | 0 | 100 | 50 |

## Lens corrections

| id | label | min | max | default |
| --- | --- | --- | --- | --- |
| `optics.distortion` | Distortion | -100 | 100 | 0 |
| `optics.vignetting` | Vignetting | -100 | 100 | 0 |
| `optics.vignettingMidpoint` | Midpoint | 0 | 100 | 50 |
| `optics.profileDistortion` | Profile Distortion | 0 | 200 | 100 |
| `optics.profileVignetting` | Profile Vignetting | 0 | 200 | 100 |
| `optics.defringePurple` | Purple Amount | 0 | 20 | 0 |
| `optics.defringePurpleHueLo` | Purple Hue Low | 0 | 90 | 30 |
| `optics.defringePurpleHueHi` | Purple Hue High | 10 | 100 | 70 |
| `optics.defringeGreen` | Green Amount | 0 | 20 | 0 |
| `optics.defringeGreenHueLo` | Green Hue Low | 0 | 90 | 40 |
| `optics.defringeGreenHueHi` | Green Hue High | 10 | 100 | 60 |
| `optics.caRed` | Red/Cyan Fringe | -100 | 100 | 0 |
| `optics.caBlue` | Blue/Yellow Fringe | -100 | 100 | 0 |

## Transform

| id | label | min | max | default |
| --- | --- | --- | --- | --- |
| `geometry.vertical` | Vertical | -100 | 100 | 0 |
| `geometry.horizontal` | Horizontal | -100 | 100 | 0 |
| `geometry.rotate` | Rotate | -10 | 10 | 0 |
| `geometry.aspect` | Aspect | -100 | 100 | 0 |
| `geometry.scale` | Scale | 50 | 150 | 100 |
| `geometry.offsetX` | Offset X | -100 | 100 | 0 |
| `geometry.offsetY` | Offset Y | -100 | 100 | 0 |

## Calibration

| id | label | min | max | default |
| --- | --- | --- | --- | --- |
| `calibration.shadowsTint` | Shadows Tint | -100 | 100 | 0 |
| `calibration.redHue` | Red Hue | -100 | 100 | 0 |
| `calibration.redSat` | Red Saturation | -100 | 100 | 0 |
| `calibration.greenHue` | Green Hue | -100 | 100 | 0 |
| `calibration.greenSat` | Green Saturation | -100 | 100 | 0 |
| `calibration.blueHue` | Blue Hue | -100 | 100 | 0 |
| `calibration.blueSat` | Blue Saturation | -100 | 100 | 0 |

## Crop

| id | label | min | max | default |
| --- | --- | --- | --- | --- |
| `crop.angle` | Straighten | -45 | 45 | 0 |

## Lens blur

| id | label | min | max | default |
| --- | --- | --- | --- | --- |
| `lensBlur.amount` | Blur Amount | 0 | 100 | 0 |
| `lensBlur.focalDistance` | Focal Distance | 0 | 100 | 50 |
| `lensBlur.focalRange` | Focal Range | 0 | 100 | 20 |
| `lensBlur.bokeh` | Bokeh Boost | 0 | 100 | 30 |

## Local adjustments (mask adjust keys)

These keys go in the `adjust` object of `add_ai_mask` and `add_gradient_mask`. `amount` scales the whole mask, 0 to 100.

| key | label | min | max |
| --- | --- | --- | --- |
| `temp` | Temp | -100 | 100 |
| `tint` | Tint | -100 | 100 |
| `exposure` | Exposure | -4 | 4 |
| `contrast` | Contrast | -100 | 100 |
| `highlights` | Highlights | -100 | 100 |
| `shadows` | Shadows | -100 | 100 |
| `whites` | Whites | -100 | 100 |
| `blacks` | Blacks | -100 | 100 |
| `texture` | Texture | -100 | 100 |
| `clarity` | Clarity | -100 | 100 |
| `dehaze` | Dehaze | -100 | 100 |
| `hue` | Hue | -100 | 100 |
| `saturation` | Saturation | -100 | 100 |
| `sharpness` | Sharpness | -100 | 100 |
| `noise` | Noise | -100 | 100 |
| `moire` | Moire | -100 | 100 |
| `defringe` | Defringe | -100 | 100 |
| `amount` | Amount | 0 | 200 |

More keys sit beside the sliders: `colorHue` and `colorSat` tint the masked area, `pointColors` takes up to eight local point colours shaped like the global ones, and `curve` takes a point curve `{"master": [[x, y], ...], "red": [...], "green": [...], "blue": [...]}` with x and y from 0 to 1, applied through the mask after the global tone.

## White balance presets

`run_command` with `develop.whiteBalancePreset` and params `{"ids": [...], "mode": "daylight"}`; the modes are `asShot`, `auto`, `daylight`, `cloudy`, `shade`, `tungsten`, `fluorescent`, `flash`, `custom`.

## Sync and copy groups

`sync_settings` and `develop.copy` take these group names: `whiteBalance` (wb), `basicTone` (light), `presence` (effects, color), `toneCurve` (curve), `colorMixer` (mixer), `pointColor`, `bwMix` (bw), `treatment`, `colorGrading` (grading), `detail`, `lensCorrections` (optics), `transform` (geometry), `effects` (vignette, grain), `calibration`, `profile`, `crop` (crop, orientation), `masks`, `spots`, `redEye`, `lensBlur`. With no groups, everything except crop, masks, spots and red eye is copied.

## Crop aspects

`original` (Original), `asShot` (As Shot), `1x1` (1 x 1), `4x5` (4 x 5 / 8 x 10), `8.5x11` (8.5 x 11), `5x7` (5 x 7), `2x3` (2 x 3 / 4 x 6), `4x3` (4 x 3), `16x9` (16 x 9), `16x10` (16 x 10), `custom` (Custom).
