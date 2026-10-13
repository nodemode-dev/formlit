# formlit built-in presets

Generated from formlit's preset list; do not edit by hand. Preview one with `get_preview` or `analyze_photo` and `preset`, apply it with `apply_preset` and an `amount` (100 is the preset as made, 50 half strength: colour-grading hues stay fixed and only their saturation scales, and curves ease toward straight).
`list_presets` with a `query` searches names, groups, descriptions and tags; the person's own presets are listed there too.

167 presets in 29 groups. Adaptive presets add AI masks, which are computed for each photo they reach.

## Contents

- Color (3)
- Film (3)
- Cinematic (11)
- B&W (18)
- Portrait (13)
- Landscape (11)
- Urban (2)
- Style (4)
- Adaptive: Sky (6)
- Adaptive: Subject (7)
- Adaptive: Portrait (6)
- Film-Inspired (10)
- Vintage (5)
- Seasons (5)
- Golden Hour (4)
- Night & Astro (5)
- Travel (5)
- Food (4)
- Urban Architecture (5)
- Concerts (3)
- Lifestyle (4)
- Moody (4)
- Futuristic (3)
- Underwater (2)
- Curves (6)
- Detail (4)
- Effects (5)
- Color Fixes (5)
- Adaptive: Landscape (4)

## Color

| Preset | What it does | Touches |
| --- | --- | --- |
| Clean Punch (`builtin:color/clean-punch`) | All-round lift: more contrast with recovered highlights and opened shadows, plus vibrance. | color, effects, light |
| Soft Bright (`builtin:color/soft-bright`) | Brighter, softer and slightly less saturated, for gentle everyday photos. | color, light |
| Rich Shadows (`builtin:color/rich-shadows`) | Deeper shadows and blacks with more contrast. | color, light |

## Film

| Preset | What it does | Touches |
| --- | --- | --- |
| Golden Negative (`builtin:film/golden-negative`) | Warm colour-negative film: warm fade profile, warm highlights, cool shadows, grain. | grading, grain, profile |
| Faded Print (`builtin:film/faded-print`) | Faded print: raised blacks (matte curve), warm shadows, light vignette. | color, curve, grading, vignette |
| Chrome Slide (`builtin:film/chrome-slide`) | Punchy slide film: vivid profile, contrast, deeper blacks. | grain, light, mixer, profile |

## Cinematic

| Preset | What it does | Touches |
| --- | --- | --- |
| Teal Night (`builtin:cinematic/teal-night`) | Teal-and-orange profile with extra teal in the shadows, darker and vignetted. | grading, light, profile, vignette |
| Warm Glow (`builtin:cinematic/warm-glow`) | Golden profile with softer clarity and recovered highlights. | effects, light, profile |
| Teal and Orange (`builtin:cinematic/teal-and-orange`) | The classic complementary grade: teal shadows (hue near 210) and orange highlights (near 35), matching a real exported Cinematic Teal and Orange preset. | curve, grading, grain, light, mixer, vignette |
| Blockbuster (`builtin:cinematic/blockbuster`) | Stronger teal and orange with calibration shifts (red primary hue up, blue primary hue down) for a saturated movie look. | calibration, grading, light, vignette |
| Night City (`builtin:cinematic/night-city`) | Cool, contrasty urban night grade with teal shadows and preserved warm lights. | effects, grading, light, mixer |
| Desert Heat (`builtin:cinematic/desert-heat`) | Warm, dusty grade: orange midtones, softened greens and blues, gentle fade. | curve, grading, light, mixer |
| Bleach Bypass (`builtin:cinematic/bleach-bypass`) | Low saturation and high contrast with bright highlights, like skipping the bleach in film processing. | color, curve, effects, light |
| Moody Green (`builtin:cinematic/moody-green`) | Pacific Northwest style moody grade: deep greens pushed toward teal, desaturated, lifted blacks, after a real Moody PNW preset. | color, curve, effects, grading, grain, light, mixer |
| Cold Thriller (`builtin:cinematic/cold-thriller`) | Steel-blue overall cast with crushed blacks, for tense, cold scenes. | color, grading, light, vignette |
| Golden Matte (`builtin:cinematic/golden-matte`) | Warm golden highlights over a matte curve, for late-afternoon story frames. | color, curve, grading, light |
| Wide Screen Fade (`builtin:cinematic/wide-screen-fade`) | Low-contrast, slightly cool cinema fade with soft highlights. | color, curve, grading, light |

## B&W

| Preset | What it does | Touches |
| --- | --- | --- |
| Classic Grain (`builtin:b-w/classic-grain`) | Monochrome with classic film grain. | grain, profile |
| Hard Light (`builtin:b-w/hard-light`) | High-contrast black and white with a vignette. | profile, vignette |
| Sepia Tone (`builtin:b-w/sepia-tone`) | Black and white toned brown in shadows and highlights. | grading, treatment |
| Selenium Tone (`builtin:b-w/selenium-tone`) | Black and white with cool purple-brown shadows. | grading, light, treatment |
| Infrared Dream (`builtin:b-w/infrared-dream`) | Infrared-style black and white: bright foliage, dark sky, softer clarity. | bw, effects, grain, light, treatment |
| Tri-X Style (`builtin:b-w/tri-x-style`) | Gritty, high-contrast black and white with heavy grain and darkened blue sky, from a real Kodak Tri-X 400 preset. | bw, grain, light, treatment |
| Silver Fine (`builtin:b-w/silver-fine`) | Smooth, fine-grain black and white with full tonal range. | grain, light, treatment |
| High-Key B&W (`builtin:b-w/high-key-b-w`) | Bright, airy black and white with soft blacks. | curve, light, treatment |
| Low-Key B&W (`builtin:b-w/low-key-b-w`) | Dark black and white after Digital Camera World's low-key portrait settings (exposure -0.45, contrast +47, highlights -100). | grain, light, treatment |
| Dark Sky Filter (`builtin:b-w/dark-sky-filter`) | Darkens blue skies and lightens warm tones like a red filter, a common B&W mix technique. | bw, light, treatment |
| Green Filter (`builtin:b-w/green-filter`) | Lightens foliage and darkens skin and reds, like a green filter. | bw, treatment |
| Portrait Glow B&W (`builtin:b-w/portrait-glow-b-w`) | Soft black and white portrait: bright orange channel for luminous skin, low clarity. | bw, effects, light, treatment |
| Street Grit (`builtin:b-w/street-grit`) | Hard black and white for street: strong clarity and contrast, dark corners. | effects, grain, light, treatment, vignette |
| Matte B&W (`builtin:b-w/matte-b-w`) | Faded black and white with raised blacks. | curve, grain, light, treatment |
| Warm B&W (`builtin:b-w/warm-b-w`) | Black and white with a light warm tone. | grading, treatment |
| Cool B&W (`builtin:b-w/cool-b-w`) | Black and white with a light cool tone. | grading, treatment |
| Split-Tone B&W (`builtin:b-w/split-tone-b-w`) | Classic split toning: cool shadows and warm highlights at blending 100, which Adobe says reproduces the old Split Toning panel. | grading, treatment |
| Architecture B&W (`builtin:b-w/architecture-b-w`) | Crisp black and white for buildings: dark sky, bright walls, clarity. | bw, effects, light, treatment |

## Portrait

| Preset | What it does | Touches |
| --- | --- | --- |
| Soft Skin (`builtin:portrait/soft-skin`) | Lower texture and clarity with brighter orange for smoother skin. | effects, light, mixer |
| Warm Portrait (`builtin:portrait/warm-portrait`) | Portrait profile with warm highlights. | grading, profile |
| Natural Skin (`builtin:portrait/natural-skin`) | Gentle portrait base: softer contrast, slightly brighter and less saturated orange for even skin, a touch of vibrance. | color, effects, light, mixer |
| Warm Skin Glow (`builtin:portrait/warm-skin-glow`) | Warm, glowing skin: orange highlights grade, lifted shadows, low texture. | effects, grading, light, mixer |
| Cool Clean Portrait (`builtin:portrait/cool-clean-portrait`) | Crisp, slightly cool portrait with clean whites, for studio or overcast light. | color, grading, light, mixer |
| Soft Window Light (`builtin:portrait/soft-window-light`) | Low-contrast, airy portrait for window light: lifted shadows, gentle highlight roll-off. | curve, effects, light |
| Editorial Contrast (`builtin:portrait/editorial-contrast`) | Punchy magazine portrait: medium S-curve, deep blacks, controlled saturation. | color, curve, effects, light |
| Edgy Desaturated (`builtin:portrait/edgy-desaturated`) | Gritty, desaturated portrait with texture and clarity, after Adobe's Edgy portrait style. | color, effects, light, vignette |
| Rosy Cheeks (`builtin:portrait/rosy-cheeks`) | Adds a slight pink to skin by shifting orange and red hue toward red, a common skin-tone fix. | mixer |
| Tame Red Skin (`builtin:portrait/tame-red-skin`) | Calms blotchy or sunburnt skin: less red and orange saturation, brighter orange. | mixer |
| Group Bright (`builtin:portrait/group-bright`) | Even, bright exposure for group photos: open shadows, protected highlights, mild clarity. | color, effects, light |
| Low-Key Portrait (`builtin:portrait/low-key-portrait`) | Dark, dramatic portrait after a Digital Camera World low-key recipe (exposure down, strong contrast, crushed highlights), in colour. | color, light, vignette |
| High-Key Portrait (`builtin:portrait/high-key-portrait`) | Bright, white-background portrait: lifted exposure and whites, soft contrast. | color, light |

## Landscape

| Preset | What it does | Touches |
| --- | --- | --- |
| Crisp Landscape (`builtin:landscape/crisp-landscape`) | Landscape profile with dehaze, clarity and highlight and shadow recovery. | effects, light, profile |
| Blue Hour (`builtin:landscape/blue-hour`) | Sets a cool 4600 K white balance and blue shadows (absolute white balance: best on raw files). | grading, light, wb |
| Haze Cut (`builtin:landscape/haze-cut`) | Strong dehaze with deeper blacks and vibrance. | color, effects, light |
| Natural Landscape (`builtin:landscape/natural-landscape`) | Balanced landscape base: recovered highlights, opened shadows, a little dehaze and vibrance. | color, effects, light |
| Rich Greens (`builtin:landscape/rich-greens`) | Deeper, less yellow greens for forests and fields. | color, effects, mixer |
| Deep Blue Water (`builtin:landscape/deep-blue-water`) | Richer blues and aquas for sea, lakes and sky. | effects, mixer |
| Mountain Clarity (`builtin:landscape/mountain-clarity`) | Cuts haze in distant mountains, adds midtone contrast. | color, effects, light |
| Misty Morning (`builtin:landscape/misty-morning`) | Keeps and softens haze: negative dehaze and clarity, cool shadows. | effects, grading, light |
| Desert Tones (`builtin:landscape/desert-tones`) | Warm sand and rock, muted greens, clear sky. | effects, grading, mixer |
| Seascape Cool (`builtin:landscape/seascape-cool`) | Cool blue-teal seascape with smooth contrast. | grading, light, mixer |
| Wide Dynamic (`builtin:landscape/wide-dynamic`) | Strong shadow and highlight recovery for high-contrast scenes, HDR-like but natural. | color, effects, light |

## Urban

| Preset | What it does | Touches |
| --- | --- | --- |
| Concrete (`builtin:urban/concrete`) | Desaturated, crunchy urban look. | color, effects, light |
| Neon (`builtin:urban/neon`) | Saturated blues and magentas with deep blacks. | color, light, mixer |

## Style

| Preset | What it does | Touches |
| --- | --- | --- |
| Matte Fade (`builtin:style/matte-fade`) | Matte look from a real exported preset: raised black point, lower contrast, slight desaturation. | color, curve, effects, light |
| Pastel Day (`builtin:style/pastel-day`) | Pastel grade: violet shadows and peach highlights at low saturation, brighter and softer. | color, curve, grading, light |
| Earth Tones (`builtin:style/earth-tones`) | Earthy palette: muted blues and greens, warm highlights. | color, grading, mixer |
| Vintage Vignette (`builtin:style/vintage-vignette`) | Faded vintage with a strong vignette and grain. | color, curve, grain, vignette |

## Adaptive: Sky

| Preset | What it does | Touches |
| --- | --- | --- |
| Deep Blue Sky (`builtin:adaptive-sky/deep-blue-sky`) | Adaptive sky mask: darker, bluer, more saturated sky. | masks |
| Dramatic Sky (`builtin:adaptive-sky/dramatic-sky`) | Adaptive sky mask: darker sky with contrast, dehaze and clarity. | masks |
| Golden Sky (`builtin:adaptive-sky/golden-sky`) | Adaptive sky mask: warmer, golden sky. | masks |
| Sunset Sky (`builtin:adaptive-sky/sunset-sky`) | Warms and deepens only the sky for sunsets. | masks |
| Soften Sky (`builtin:adaptive-sky/soften-sky`) | Softens a harsh sky: lower contrast and clarity in the sky only. | masks |
| Night Sky (`builtin:adaptive-sky/night-sky`) | Darker, cooler, clearer sky for night scenes. | masks |

## Adaptive: Subject

| Preset | What it does | Touches |
| --- | --- | --- |
| Pop Subject (`builtin:adaptive-subject/pop-subject`) | Adaptive subject mask: brighter and more detailed subject. | masks |
| Darken Background (`builtin:adaptive-subject/darken-background`) | Adaptive background mask: darker, less saturated background. | masks |
| Soft Background (`builtin:adaptive-subject/soft-background`) | Adaptive background mask: softened background detail. | masks |
| Subject Glow (`builtin:adaptive-subject/subject-glow`) | Brightens the subject softly and warms it slightly. | masks |
| Subject Detail (`builtin:adaptive-subject/subject-detail`) | Adds texture and clarity to the subject only. | masks |
| Desaturate Background (`builtin:adaptive-subject/desaturate-background`) | Removes most colour from the background so the subject stands out. | masks |
| Cool Background (`builtin:adaptive-subject/cool-background`) | Cools and darkens the background slightly. | masks |

## Adaptive: Portrait

| Preset | What it does | Touches |
| --- | --- | --- |
| Smooth Skin (`builtin:adaptive-portrait/smooth-skin`) | Adaptive face and body skin masks: lower texture and clarity. | masks |
| Brighten Eyes (`builtin:adaptive-portrait/brighten-eyes`) | Adaptive iris and sclera masks: brighter, clearer eyes. | masks |
| Whiten Teeth (`builtin:adaptive-portrait/whiten-teeth`) | Adaptive teeth mask: brighter, less yellow teeth. | masks |
| Define Brows (`builtin:adaptive-portrait/define-brows`) | Darkens eyebrows a little, as in Adobe's portrait-mask tutorial. | masks |
| Lip Color (`builtin:adaptive-portrait/lip-color`) | Adds saturation and a touch of contrast to lips. | masks |
| Hair Shine (`builtin:adaptive-portrait/hair-shine`) | Adds texture and slight brightness to hair. | masks |

## Film-Inspired

| Preset | What it does | Touches |
| --- | --- | --- |
| Portra Style (`builtin:film-inspired/portra-style`) | Warm, low-contrast colour negative look with soft skin and fine grain, from a real Kodak Portra 400 preset's values. | grading, grain, light, mixer |
| Gold Daylight (`builtin:film-inspired/gold-daylight`) | Saturated, warm consumer-film colour with yellow highlights and punchy blues. | color, grading, grain, light, mixer |
| Cool Negative (`builtin:film-inspired/cool-negative`) | Cool, green-leaning negative film: cyan shadows, muted reds, gentle fade. | curve, grading, grain, mixer |
| Slide Velvia (`builtin:film-inspired/slide-velvia`) | High-saturation slide film: deep blues and greens, rich contrast, dark blacks. | color, light, mixer, profile |
| Expired Film (`builtin:film-inspired/expired-film`) | Faded, shifted colour of old stock: magenta-cast highlights, cyan shadows, raised blacks and heavy grain. | color, curve, grading, grain, vignette |
| Warm Gold (`builtin:film-inspired/warm-gold`) | Warm golden tint across highlights and midtones, after Adobe's Film-Inspired Warm Gold variation. | grading, grain, light |
| Soft Ember (`builtin:film-inspired/soft-ember`) | Soft orange-red warmth with lifted shadows. | color, curve, grading, grain |
| Faded Blue (`builtin:film-inspired/faded-blue`) | Cool faded film with blue shadows and soft highlights. | color, curve, grading, grain |
| Light Sage (`builtin:film-inspired/light-sage`) | Muted green-grey film tone, calm and earthy. | color, curve, grading |
| Instant Print (`builtin:film-inspired/instant-print`) | Instant-camera look: cool shadows, warm creamy highlights, low contrast, faded top end. | curve, grading, grain, light, vignette |

## Vintage

| Preset | What it does | Touches |
| --- | --- | --- |
| Seventies (`builtin:vintage/seventies`) | Warm, yellow-brown cast with faded blacks and soft saturation. | color, curve, grading, grain |
| Retro Pastel (`builtin:vintage/retro-pastel`) | Pastel retro: pink highlights, mint shadows, lifted curve. | color, curve, grading, light |
| Sun-Bleached (`builtin:vintage/sun-bleached`) | Washed-out summer print: low saturation, bright, warm highlights. | color, curve, grading, light |
| Old Postcard (`builtin:vintage/old-postcard`) | Strong warm tint, soft focus feel, deep vignette. | color, effects, grading, grain, vignette |
| Cross Process (`builtin:vintage/cross-process`) | Cross-processed slide film: green-yellow highlights, blue shadows, high contrast. | color, grading, light |

## Seasons

| Preset | What it does | Touches |
| --- | --- | --- |
| Spring Fresh (`builtin:seasons/spring-fresh`) | Fresh greens and soft pinks, bright and gentle. | color, light, mixer |
| Summer Warmth (`builtin:seasons/summer-warmth`) | Warm, saturated summer light with blue skies kept strong. | color, grading, light, mixer |
| Autumn Gold (`builtin:seasons/autumn-gold`) | Pushes greens and yellows toward orange and gold, deepens oranges, for fall foliage. | color, grading, mixer |
| Winter Crisp (`builtin:seasons/winter-crisp`) | Snow and winter: positive exposure (cameras underexpose snow), higher whites without clipping, cool shadows and slightly warm highlights. | color, grading, light |
| Winter Soft (`builtin:seasons/winter-soft`) | Soft, raised-black winter look for snowy scenes. | color, grading, light |

## Golden Hour

| Preset | What it does | Touches |
| --- | --- | --- |
| Golden Hour Glow (`builtin:golden-hour/golden-hour-glow`) | Fine-tunes existing warmth rather than removing it, lowers highlights and lifts shadows to balance sky and foreground, as Adobe advises for golden hour. | color, grading, light |
| Sunset Fire (`builtin:golden-hour/sunset-fire`) | Intense sunset: deeper oranges and reds, darker sky top. | grading, light, mixer |
| Backlit Haze (`builtin:golden-hour/backlit-haze`) | Soft backlit portrait or field: low dehaze, warm highlights, open shadows. | effects, grading, light |
| Pink Dusk (`builtin:golden-hour/pink-dusk`) | Rose and violet dusk tones. | grading, mixer |

## Night & Astro

| Preset | What it does | Touches |
| --- | --- | --- |
| Milky Way (`builtin:night-astro/milky-way`) | Starting point for astro: Texture and Clarity near -5 to -10 and colour noise reduction 10 to 20 with colour detail 60 to 80, after Photography Life's Milky Way guide. | detail, effects, grading, light |
| Blue Hour City (`builtin:night-astro/blue-hour-city`) | Deep blue twilight with warm windows and street lights kept. | grading, light, mixer |
| Neon Nights (`builtin:night-astro/neon-nights`) | Saturated neon magentas and blues with deep blacks. | color, light, mixer |
| Low-Light Clean (`builtin:night-astro/low-light-clean`) | Noise reduction and gentle tone for high-ISO night shots; run Denoise first on raw files when available. | detail, effects, light |
| Moonlight (`builtin:night-astro/moonlight`) | Cool, dim moonlit look. | color, grading, light |

## Travel

| Preset | What it does | Touches |
| --- | --- | --- |
| Travel Vivid (`builtin:travel/travel-vivid`) | Bright, colourful travel look with clean contrast. | color, effects, light |
| Tropical (`builtin:travel/tropical`) | Turquoise water, lush greens, warm skin. | color, grading, mixer |
| Mediterranean (`builtin:travel/mediterranean`) | Warm stone, deep blue sea, sunny highlights. | grading, light, mixer |
| Travel Muted (`builtin:travel/travel-muted`) | Calm, desaturated travel look with a slight fade. | color, curve, grading |
| Market Colors (`builtin:travel/market-colors`) | Pops the many colours of markets and street scenes without blowing skin. | color, effects, light |

## Food

| Preset | What it does | Touches |
| --- | --- | --- |
| Fresh Food (`builtin:food/fresh-food`) | Bright, appetising food: lifted exposure, crisp texture, fresh greens and warm reds. | color, effects, light, mixer |
| Moody Food (`builtin:food/moody-food`) | Dark, rich food styling: low exposure, deep shadows, warm highlights. | color, grading, light, vignette |
| Bakery Warm (`builtin:food/bakery-warm`) | Warm, golden tones for bread, pastry and coffee. | effects, grading, mixer |
| Clean White Plate (`builtin:food/clean-white-plate`) | Neutral, bright whites for light food on white plates. | color, light |

## Urban Architecture

| Preset | What it does | Touches |
| --- | --- | --- |
| Clean Architecture (`builtin:urban-architecture/clean-architecture`) | Neutral, crisp architecture with straight contrast and cool shadows. | effects, grading, light |
| Steel and Glass (`builtin:urban-architecture/steel-and-glass`) | Cool, desaturated modern city look. | color, effects, grading, light |
| Warm Facades (`builtin:urban-architecture/warm-facades`) | Warm stone and brick with deep sky. | effects, grading, mixer |
| Gritty Street (`builtin:urban-architecture/gritty-street`) | Hard urban colour: crunchy clarity, muted colours, dark corners. | color, effects, light, vignette |
| Interior Bright (`builtin:urban-architecture/interior-bright`) | Bright, even interiors: strong shadow lift, controlled windows. | color, light |

## Concerts

| Preset | What it does | Touches |
| --- | --- | --- |
| Stage Lights (`builtin:concerts/stage-lights`) | Concert base: recovers coloured stage highlights, deepens blacks, controls noise. | color, detail, light |
| Concert B&W (`builtin:concerts/concert-b-w`) | High-contrast black and white for stage photos under mixed light. | effects, grain, light, treatment |
| Club Neon (`builtin:concerts/club-neon`) | Saturated club lighting with smooth noise. | color, detail, light, mixer |

## Lifestyle

| Preset | What it does | Touches |
| --- | --- | --- |
| Bright and Airy (`builtin:lifestyle/bright-and-airy`) | Light, airy lifestyle look: brighter exposure, low contrast, open shadows, slightly muted colour. | color, curve, light, mixer |
| Cozy Home (`builtin:lifestyle/cozy-home`) | Warm, soft indoor light. | effects, grading, light |
| Clean Minimal (`builtin:lifestyle/clean-minimal`) | Neutral, bright, low-saturation minimal look. | color, effects, light |
| Wedding Soft (`builtin:lifestyle/wedding-soft`) | Soft, flattering wedding look with protected whites and warm skin. | effects, grading, light, mixer |

## Moody

| Preset | What it does | Touches |
| --- | --- | --- |
| Dark and Moody (`builtin:moody/dark-and-moody`) | Low exposure, crushed highlights, desaturated colour, deep vignette. | color, grading, light, vignette |
| Forest Shadows (`builtin:moody/forest-shadows`) | Dark, green-teal forest mood with soft highlights. | grading, light, mixer |
| Stormy (`builtin:moody/stormy`) | Heavy, dramatic sky and land: dehaze, clarity, cool cast. | color, effects, grading, light |
| Muted Earth (`builtin:moody/muted-earth`) | Brown-olive palette with low saturation and matte curve. | color, curve, grading, mixer |

## Futuristic

| Preset | What it does | Touches |
| --- | --- | --- |
| Cyber Teal (`builtin:futuristic/cyber-teal`) | Synthetic teal and magenta grade with high contrast. | color, grading, light |
| Chrome Future (`builtin:futuristic/chrome-future`) | Cold, metallic, desaturated look with bright whites. | color, effects, grading, light |
| Infrared Color (`builtin:futuristic/infrared-color`) | False-colour infrared feel: foliage shifted to pink and white, sky darkened. | light, mixer |

## Underwater

| Preset | What it does | Touches |
| --- | --- | --- |
| Underwater Restore (`builtin:underwater/underwater-restore`) | Restores colour lost underwater: reds and oranges vanish first, so warm the image and push tint toward magenta (Adobe Learn); purples shifted to blue. | effects, grading, light, mixer |
| Blue Water Clear (`builtin:underwater/blue-water-clear`) | Clearer blue water with reduced haze and controlled noise. | detail, effects, mixer |

## Curves

| Preset | What it does | Touches |
| --- | --- | --- |
| Medium Contrast Curve (`builtin:curves/medium-contrast-curve`) | A medium S-curve point curve: darker shadows and brighter highlights for more contrast and saturation. | curve |
| Strong Contrast Curve (`builtin:curves/strong-contrast-curve`) | A strong S-curve point curve. | curve |
| Matte Curve (`builtin:curves/matte-curve`) | Raised black point and lowered white point, the curve real film and matte presets share (0,20 64,55 128,128 192,196 255,235). | curve |
| Soft Matte Curve (`builtin:curves/soft-matte-curve`) | A lighter matte: slightly raised blacks. | curve |
| Lift Shadows (`builtin:curves/lift-shadows`) | Parametric curve: opens the darks and shadows regions. | curve |
| Tame Highlights (`builtin:curves/tame-highlights`) | Parametric curve: lowers the lights and highlights regions. | curve |

## Detail

| Preset | What it does | Touches |
| --- | --- | --- |
| Sharpen Portrait (`builtin:detail/sharpen-portrait`) | Gentle sharpening with high masking so skin stays smooth and edges get detail. | detail |
| Sharpen Landscape (`builtin:detail/sharpen-landscape`) | Crisp sharpening for landscapes and architecture: radius 1.0, more detail, low masking. | detail |
| Noise ISO 3200 (`builtin:detail/noise-iso-3200`) | Moderate luminance and colour noise reduction for around ISO 3200. | detail |
| Noise ISO 6400+ (`builtin:detail/noise-iso-6400`) | Strong noise reduction for very high ISO; Denoise on the raw is usually better. | detail |

## Effects

| Preset | What it does | Touches |
| --- | --- | --- |
| Soft Vignette (`builtin:effects/soft-vignette`) | A soft, subtle darkening of the corners to hold the eye in the frame. | vignette |
| Strong Vignette (`builtin:effects/strong-vignette`) | Heavy dark corners for drama. | vignette |
| White Vignette (`builtin:effects/white-vignette`) | Light corners for high-key and airy images. | vignette |
| Fine Grain (`builtin:effects/fine-grain`) | Light, fine film grain. | grain |
| Heavy Grain (`builtin:effects/heavy-grain`) | Coarse, rough grain like fast film. | grain |

## Color Fixes

| Preset | What it does | Touches |
| --- | --- | --- |
| Richer Color (Calibration) (`builtin:color-fixes/richer-color-calibration`) | Raises blue primary saturation for richer overall colour; watch the sky, which over-saturates easily. | calibration |
| Remove Green Cast (`builtin:color-fixes/remove-green-cast`) | Counters a green cast in shadows and fluorescent light. | calibration, grading |
| Calm Oversaturation (`builtin:color-fixes/calm-oversaturation`) | Reduces saturation while keeping softer colours with vibrance. | color |
| Muted Palette (`builtin:color-fixes/muted-palette`) | Saturation down and vibrance up, Julieanne Kost's combination for toning down the palette while keeping non-skin colour. | color |
| Blue Sky Boost (`builtin:color-fixes/blue-sky-boost`) | Deeper, darker blue sky through the blue and aqua mixer bands. | mixer |

## Adaptive: Landscape

| Preset | What it does | Touches |
| --- | --- | --- |
| Lush Vegetation (`builtin:adaptive-landscape/lush-vegetation`) | Richer, more detailed foliage only. | masks |
| Clear Water (`builtin:adaptive-landscape/clear-water`) | Clearer, deeper water only. | masks |
| Mountain Detail (`builtin:adaptive-landscape/mountain-detail`) | Cuts haze and adds structure to mountains only. | masks |
| Building Detail (`builtin:adaptive-landscape/building-detail`) | Crisper buildings and architecture only. | masks |
