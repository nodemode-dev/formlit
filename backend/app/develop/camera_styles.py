GROUP = "Camera Matching"

STYLES: list[dict] = [
    {"id": "fl.camera", "name": "Camera Look", "delta": {}},
    {"id": "fl.camera.standard", "name": "Camera Standard", "delta": {}},
    {"id": "fl.camera.neutral", "name": "Camera Neutral", "delta": {"light.contrast": -16, "color.saturation": -10, "curve.highlights": -6, "curve.shadows": 8}},
    {"id": "fl.camera.vivid", "name": "Camera Vivid", "delta": {"light.contrast": 10, "color.vibrance": 22, "color.saturation": 10}},
    {"id": "fl.camera.portrait", "name": "Camera Portrait", "delta": {"light.contrast": -6, "mixer.orange.sat": -10, "mixer.orange.lum": 6, "mixer.red.sat": -8, "curve.highlights": -4}},
    {"id": "fl.camera.landscape", "name": "Camera Landscape", "delta": {"light.contrast": 8, "color.vibrance": 12, "mixer.green.sat": 14, "mixer.blue.sat": 12, "mixer.blue.lum": -6}},
    {"id": "fl.camera.monochrome", "name": "Camera Monochrome", "treatment": "bw", "delta": {"light.contrast": 6}},
    {"id": "fl.camera.sepia", "name": "Camera Sepia", "treatment": "bw", "delta": {"grading.global.hue": 40, "grading.global.sat": 22, "light.contrast": 4}},
    {"id": "fl.camera.canon.faithful", "make": "canon", "name": "Camera Faithful", "delta": {"light.contrast": -18, "color.saturation": -16, "color.vibrance": -4, "curve.shadows": 6}},
    {"id": "fl.camera.canon.finedetail", "make": "canon", "name": "Camera Fine Detail", "delta": {"light.contrast": -2, "color.saturation": -4, "effects.texture": 18}},
    {"id": "fl.camera.nikon.flat", "make": "nikon", "name": "Camera Flat", "delta": {"light.contrast": -34, "color.saturation": -24, "light.highlights": -10, "curve.shadows": 14, "curve.highlights": -10}},
    {"id": "fl.camera.sony.clear", "make": "sony", "name": "Camera Clear", "delta": {"light.contrast": 6, "color.saturation": 4, "curve.lights": 6, "curve.highlights": 4}},
    {"id": "fl.camera.sony.deep", "make": "sony", "name": "Camera Deep", "delta": {"light.contrast": 8, "color.saturation": 8, "curve.lights": -8, "curve.darks": -8}},
    {"id": "fl.camera.sony.light", "make": "sony", "name": "Camera Light", "delta": {"light.contrast": -12, "color.saturation": -6, "curve.lights": 10, "curve.darks": 8}},
    {"id": "fl.camera.sony.sunset", "make": "sony", "name": "Camera Sunset", "delta": {"color.saturation": 12, "mixer.red.sat": 12, "mixer.orange.sat": 10, "grading.global.hue": 30, "grading.global.sat": 14}},
    {"id": "fl.camera.sony.night", "make": "sony", "name": "Camera Night Scene", "delta": {"light.contrast": 6, "color.saturation": -10, "curve.shadows": -10, "grading.shadows.hue": 220, "grading.shadows.sat": 8}},
    {"id": "fl.camera.sony.autumn", "make": "sony", "name": "Camera Autumn Leaves", "delta": {"color.saturation": 6, "mixer.red.sat": 16, "mixer.orange.sat": 18, "mixer.yellow.sat": 12, "mixer.yellow.hue": -6}},
    {"id": "fl.camera.fujifilm.velvia", "make": "fujifilm", "name": "Camera Velvia/Vivid", "delta": {"light.contrast": 14, "light.blacks": -6, "color.saturation": 18, "color.vibrance": 10, "mixer.red.sat": 6, "mixer.green.sat": 10, "mixer.blue.sat": 8}},
    {"id": "fl.camera.fujifilm.astia", "make": "fujifilm", "name": "Camera ASTIA/Soft", "delta": {"light.contrast": -8, "color.saturation": 4, "curve.shadows": 6, "mixer.orange.sat": -4, "mixer.green.sat": 4, "mixer.blue.sat": 6}},
    {"id": "fl.camera.fujifilm.classicchrome", "make": "fujifilm", "name": "Camera CLASSIC CHROME", "delta": {"light.contrast": 6, "color.saturation": -22, "curve.shadows": -4, "mixer.blue.hue": -8, "mixer.blue.sat": -12, "mixer.red.sat": -10, "mixer.green.hue": -10, "grading.shadows.hue": 200, "grading.shadows.sat": 6}},
    {"id": "fl.camera.fujifilm.proneghi", "make": "fujifilm", "name": "Camera PRO Neg. Hi", "delta": {"light.contrast": 6, "color.saturation": -10, "mixer.orange.sat": -6, "mixer.orange.lum": 4}},
    {"id": "fl.camera.fujifilm.pronegstd", "make": "fujifilm", "name": "Camera PRO Neg. Std", "delta": {"light.contrast": -12, "color.saturation": -14, "curve.shadows": 4, "mixer.orange.lum": 5}},
    {"id": "fl.camera.fujifilm.classicneg", "make": "fujifilm", "name": "Camera CLASSIC Neg.", "delta": {"light.contrast": 10, "color.saturation": -12, "curve.highlights": -6, "mixer.red.hue": 6, "mixer.green.hue": -12, "mixer.green.sat": -10, "grading.shadows.hue": 190, "grading.shadows.sat": 10, "grading.highlights.hue": 50, "grading.highlights.sat": 10}},
    {"id": "fl.camera.fujifilm.eterna", "make": "fujifilm", "name": "Camera ETERNA/Cinema", "delta": {"light.contrast": -24, "color.saturation": -28, "curve.shadows": 10, "mixer.orange.sat": -6, "grading.shadows.hue": 195, "grading.shadows.sat": 6}},
    {"id": "fl.camera.fujifilm.bleachbypass", "make": "fujifilm", "name": "Camera ETERNA BLEACH BYPASS", "delta": {"light.contrast": 26, "light.blacks": -10, "color.saturation": -50, "curve.highlights": 4}},
    {"id": "fl.camera.fujifilm.nostalgicneg", "make": "fujifilm", "name": "Camera NOSTALGIC Neg.", "delta": {"light.contrast": -4, "color.saturation": 4, "curve.shadows": 4, "grading.highlights.hue": 45, "grading.highlights.sat": 14, "grading.shadows.hue": 30, "grading.shadows.sat": 6}},
    {"id": "fl.camera.fujifilm.realaace", "make": "fujifilm", "name": "Camera REALA ACE", "delta": {"light.contrast": 4, "color.saturation": -2, "mixer.orange.sat": -2}},
    {"id": "fl.camera.fujifilm.acros", "make": "fujifilm", "name": "Camera ACROS", "treatment": "bw", "delta": {"light.contrast": 14, "light.blacks": -4, "curve.shadows": -4}},
    {"id": "fl.camera.fujifilm.acrosye", "make": "fujifilm", "name": "Camera ACROS+Ye FILTER", "treatment": "bw", "delta": {"light.contrast": 14, "bw.blue": -30, "bw.yellow": 15}},
    {"id": "fl.camera.fujifilm.acrosr", "make": "fujifilm", "name": "Camera ACROS+R FILTER", "treatment": "bw", "delta": {"light.contrast": 16, "bw.red": 35, "bw.orange": 20, "bw.blue": -45, "bw.aqua": -25}},
    {"id": "fl.camera.fujifilm.acrosg", "make": "fujifilm", "name": "Camera ACROS+G FILTER", "treatment": "bw", "delta": {"light.contrast": 12, "bw.green": 30, "bw.yellow": 15, "bw.red": -15}},
    {"id": "fl.camera.panasonic.natural", "make": "panasonic", "name": "Camera Natural", "delta": {"light.contrast": -8, "color.saturation": -6}},
    {"id": "fl.camera.panasonic.flat", "make": "panasonic", "name": "Camera Flat", "delta": {"light.contrast": -30, "color.saturation": -22, "curve.shadows": 12, "curve.highlights": -8}},
    {"id": "fl.camera.panasonic.cinelikev", "make": "panasonic", "name": "Camera Cinelike V", "delta": {"light.contrast": 12, "color.saturation": 6, "curve.darks": -6}},
    {"id": "fl.camera.panasonic.cineliked", "make": "panasonic", "name": "Camera Cinelike D", "delta": {"light.contrast": -26, "light.highlights": -10, "color.saturation": -12, "curve.shadows": 12, "curve.highlights": -12}},
    {"id": "fl.camera.panasonic.lmonochrome", "make": "panasonic", "name": "Camera L.Monochrome", "treatment": "bw", "delta": {"light.contrast": 12, "curve.shadows": -6, "bw.red": 10, "bw.blue": -10}},
    {"id": "fl.camera.olympus.natural", "make": "olympus", "name": "Camera Natural", "delta": {"light.contrast": -6, "color.saturation": -6}},
    {"id": "fl.camera.olympus.muted", "make": "olympus", "name": "Camera Muted", "delta": {"light.contrast": -16, "color.saturation": -18, "curve.shadows": 6}},
    {"id": "fl.camera.olympus.ienhance", "make": "olympus", "name": "Camera i-Enhance", "delta": {"light.contrast": 8, "color.vibrance": 18, "color.saturation": 6}},
    {"id": "fl.camera.olympus.flat", "make": "olympus", "name": "Camera Flat", "delta": {"light.contrast": -30, "color.saturation": -20, "curve.shadows": 12}},
    {"id": "fl.camera.pentax.bright", "make": "pentax", "name": "Camera Bright", "delta": {"light.contrast": 10, "color.saturation": 12, "color.vibrance": 8}},
    {"id": "fl.camera.pentax.natural", "make": "pentax", "name": "Camera Natural", "delta": {"light.contrast": -6, "color.saturation": -6}},
    {"id": "fl.camera.pentax.vibrant", "make": "pentax", "name": "Camera Vibrant", "delta": {"light.contrast": 6, "color.saturation": 22, "mixer.blue.sat": 8}},
    {"id": "fl.camera.pentax.radiant", "make": "pentax", "name": "Camera Radiant", "delta": {"light.contrast": 12, "color.saturation": 14, "mixer.red.sat": 6, "mixer.orange.lum": 4}},
    {"id": "fl.camera.pentax.muted", "make": "pentax", "name": "Camera Muted", "delta": {"light.contrast": -12, "color.saturation": -24}},
    {"id": "fl.camera.pentax.flat", "make": "pentax", "name": "Camera Flat", "delta": {"light.contrast": -30, "color.saturation": -20, "curve.shadows": 12}},
    {"id": "fl.camera.pentax.bleachbypass", "make": "pentax", "name": "Camera Bleach Bypass", "delta": {"light.contrast": 24, "light.blacks": -8, "color.saturation": -45}},
    {"id": "fl.camera.pentax.reversal", "make": "pentax", "name": "Camera Reversal Film", "delta": {"light.contrast": 20, "light.blacks": -10, "color.saturation": 14, "mixer.blue.lum": -8}},
    {"id": "fl.camera.pentax.cross", "make": "pentax", "name": "Camera Cross Processing", "delta": {"light.contrast": 14, "color.saturation": 10, "grading.shadows.hue": 160, "grading.shadows.sat": 18, "grading.highlights.hue": 60, "grading.highlights.sat": 16}},
]

GENERIC = ["fl.camera", "fl.camera.standard", "fl.camera.neutral", "fl.camera.vivid", "fl.camera.portrait", "fl.camera.landscape", "fl.camera.monochrome"]
SETS = {
    "canon": ["fl.camera", "fl.camera.standard", "fl.camera.portrait", "fl.camera.landscape", "fl.camera.neutral", "fl.camera.canon.faithful",
              "fl.camera.canon.finedetail", "fl.camera.monochrome"],
    "nikon": ["fl.camera", "fl.camera.standard", "fl.camera.neutral", "fl.camera.vivid", "fl.camera.portrait", "fl.camera.landscape", "fl.camera.nikon.flat",
              "fl.camera.monochrome"],
    "sony": ["fl.camera", "fl.camera.standard", "fl.camera.vivid", "fl.camera.neutral", "fl.camera.sony.clear", "fl.camera.sony.deep", "fl.camera.sony.light",
             "fl.camera.portrait", "fl.camera.landscape", "fl.camera.sony.sunset", "fl.camera.sony.night", "fl.camera.sony.autumn", "fl.camera.monochrome",
             "fl.camera.sepia"],
    "fujifilm": ["fl.camera", "fl.camera.standard", "fl.camera.fujifilm.velvia", "fl.camera.fujifilm.astia", "fl.camera.fujifilm.classicchrome",
                 "fl.camera.fujifilm.proneghi", "fl.camera.fujifilm.pronegstd", "fl.camera.fujifilm.classicneg", "fl.camera.fujifilm.eterna",
                 "fl.camera.fujifilm.bleachbypass", "fl.camera.fujifilm.nostalgicneg", "fl.camera.fujifilm.realaace", "fl.camera.monochrome",
                 "fl.camera.fujifilm.acros", "fl.camera.fujifilm.acrosye", "fl.camera.fujifilm.acrosr", "fl.camera.fujifilm.acrosg", "fl.camera.sepia"],
    "panasonic": ["fl.camera", "fl.camera.standard", "fl.camera.vivid", "fl.camera.panasonic.natural", "fl.camera.panasonic.flat", "fl.camera.landscape",
                  "fl.camera.portrait", "fl.camera.monochrome", "fl.camera.panasonic.lmonochrome", "fl.camera.panasonic.cinelikev",
                  "fl.camera.panasonic.cineliked"],
    "olympus": ["fl.camera", "fl.camera.olympus.ienhance", "fl.camera.vivid", "fl.camera.olympus.natural", "fl.camera.olympus.muted", "fl.camera.portrait",
                "fl.camera.monochrome", "fl.camera.olympus.flat"],
    "pentax": ["fl.camera", "fl.camera.pentax.bright", "fl.camera.pentax.natural", "fl.camera.portrait", "fl.camera.landscape", "fl.camera.pentax.vibrant",
               "fl.camera.pentax.radiant", "fl.camera.pentax.muted", "fl.camera.pentax.flat", "fl.camera.pentax.bleachbypass", "fl.camera.pentax.reversal",
               "fl.camera.monochrome", "fl.camera.pentax.cross"],
}
RENAME = {
    "fujifilm": {"fl.camera.standard": "Camera PROVIA/Standard", "fl.camera.monochrome": "Camera MONOCHROME", "fl.camera.sepia": "Camera SEPIA"},
    "sony": {"fl.camera.monochrome": "Camera B/W"},
    "panasonic": {"fl.camera.landscape": "Camera Scenery"},
    "olympus": {"fl.camera.monochrome": "Camera Monotone"},
}
MAKES = {"canon": "canon", "nikon": "nikon", "sony": "sony", "fujifilm": "fujifilm", "fuji": "fujifilm", "panasonic": "panasonic", "lumix": "panasonic",
         "olympus": "olympus", "om": "olympus", "pentax": "pentax", "ricoh": "pentax"}


def make_of(camera: str) -> str:
    words = str(camera or "").replace("-", " ").split()
    return MAKES.get(words[0].lower(), "") if words else ""


def listed(camera: str) -> list[str]:
    return SETS.get(make_of(camera), GENERIC)


def name_for(pid: str, camera: str, default: str) -> str:
    return RENAME.get(make_of(camera), {}).get(pid, default)


def id_for_name(name: str) -> str:
    key = str(name or "").strip().lower()
    names = {s["name"].lower(): s["id"] for s in STYLES if s["id"] != "fl.camera"}
    names.update({n.lower(): pid for table in RENAME.values() for pid, n in table.items()})
    return names.get(key, "fl.camera")


def crs_name(pid: str) -> str:
    style = next((s for s in STYLES if s["id"] == pid), None)
    return "Camera Standard" if style is None or pid == "fl.camera" else style["name"]


def as_shot(path) -> str | None:
    from app.develop.makernotes import picture_style
    return picture_style(path)
