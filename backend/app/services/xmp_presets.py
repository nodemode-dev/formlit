import re
from pathlib import Path

from app.develop import settings as S
from app.services import metadata

SCALAR = {
    "Exposure2012": "light.exposure", "Contrast2012": "light.contrast", "Highlights2012": "light.highlights", "Shadows2012": "light.shadows",
    "Whites2012": "light.whites", "Blacks2012": "light.blacks", "Texture": "effects.texture", "Clarity2012": "effects.clarity", "Dehaze": "effects.dehaze",
    "Vibrance": "color.vibrance", "Saturation": "color.saturation", "ParametricShadows": "curve.shadows", "ParametricDarks": "curve.darks",
    "ParametricLights": "curve.lights", "ParametricHighlights": "curve.highlights", "ParametricShadowSplit": "curve.splitShadows",
    "ParametricMidtoneSplit": "curve.splitMid", "ParametricHighlightSplit": "curve.splitHighlights", "Sharpness": "detail.sharpenAmount",
    "SharpenRadius": "detail.sharpenRadius", "SharpenDetail": "detail.sharpenDetail", "SharpenEdgeMasking": "detail.sharpenMasking",
    "LuminanceSmoothing": "detail.nrLuminance", "LuminanceNoiseReductionDetail": "detail.nrDetail", "LuminanceNoiseReductionContrast": "detail.nrContrast",
    "ColorNoiseReduction": "detail.nrColor", "ColorNoiseReductionDetail": "detail.nrColorDetail", "ColorNoiseReductionSmoothness": "detail.nrColorSmoothness",
    "PostCropVignetteAmount": "vignette.amount", "PostCropVignetteMidpoint": "vignette.midpoint", "PostCropVignetteRoundness": "vignette.roundness",
    "PostCropVignetteFeather": "vignette.feather", "PostCropVignetteHighlightContrast": "vignette.highlights", "GrainAmount": "grain.amount",
    "GrainSize": "grain.size", "GrainFrequency": "grain.roughness", "LensManualDistortionAmount": "optics.distortion", "VignetteAmount": "optics.vignetting",
    "VignetteMidpoint": "optics.vignettingMidpoint", "DefringePurpleAmount": "optics.defringePurple", "DefringePurpleHueLo": "optics.defringePurpleHueLo",
    "DefringePurpleHueHi": "optics.defringePurpleHueHi", "DefringeGreenAmount": "optics.defringeGreen", "DefringeGreenHueLo": "optics.defringeGreenHueLo",
    "DefringeGreenHueHi": "optics.defringeGreenHueHi", "PerspectiveVertical": "geometry.vertical", "PerspectiveHorizontal": "geometry.horizontal",
    "PerspectiveRotate": "geometry.rotate", "PerspectiveAspect": "geometry.aspect", "PerspectiveScale": "geometry.scale", "PerspectiveX": "geometry.offsetX",
    "PerspectiveY": "geometry.offsetY", "ShadowTint": "calibration.shadowsTint", "RedHue": "calibration.redHue", "RedSaturation": "calibration.redSat",
    "GreenHue": "calibration.greenHue", "GreenSaturation": "calibration.greenSat", "BlueHue": "calibration.blueHue", "BlueSaturation": "calibration.blueSat",
    "ColorGradeMidtoneHue": "grading.midtones.hue", "ColorGradeMidtoneSat": "grading.midtones.sat", "ColorGradeMidtoneLum": "grading.midtones.lum",
    "ColorGradeShadowLum": "grading.shadows.lum", "ColorGradeHighlightLum": "grading.highlights.lum", "ColorGradeGlobalHue": "grading.global.hue",
    "ColorGradeGlobalSat": "grading.global.sat", "ColorGradeGlobalLum": "grading.global.lum", "ColorGradeBlending": "grading.blending",
    "SplitToningShadowHue": "grading.shadows.hue", "SplitToningShadowSaturation": "grading.shadows.sat", "SplitToningHighlightHue": "grading.highlights.hue",
    "SplitToningHighlightSaturation": "grading.highlights.sat", "SplitToningBalance": "grading.balance", "Temperature": "wb.temp", "Tint": "wb.tint",
}
BANDS = {"Red": "red", "Orange": "orange", "Yellow": "yellow", "Green": "green", "Aqua": "aqua", "Blue": "blue", "Purple": "purple", "Magenta": "magenta"}


def _num(v: str) -> float | None:
    try:
        return float(str(v).replace("+", ""))
    except ValueError:
        return None


def from_crs(crs: dict) -> dict:
    dev: dict = {}
    for key, cid in SCALAR.items():
        if key in crs and cid in S.controls():
            v = _num(crs[key])
            if v is not None:
                S.put(dev, cid, v)
    for lr, band in BANDS.items():
        for kind, short in (("Hue", "hue"), ("Saturation", "sat"), ("Luminance", "lum")):
            v = _num(crs.get(f"{kind}Adjustment{lr}", ""))
            if v is not None and v != 0:
                S.put(dev, f"mixer.{band}.{short}", v)
        v = _num(crs.get(f"GrayMixer{lr}", ""))
        if v is not None and v != 0:
            S.put(dev, f"bw.{band}", v)
    wb = crs.get("WhiteBalance")
    if wb:
        mode = {"As Shot": "asShot", "Auto": "auto", "Daylight": "daylight", "Cloudy": "cloudy", "Shade": "shade", "Tungsten": "tungsten",
                "Fluorescent": "fluorescent", "Flash": "flash", "Custom": "custom"}.get(wb, "custom")
        dev.setdefault("wb", {})["mode"] = mode
    elif "Temperature" in crs or "Tint" in crs:
        dev.setdefault("wb", {})["mode"] = "custom"
    if str(crs.get("ConvertToGrayscale", "")).lower() == "true":
        dev["treatment"] = "bw"
    for name, key in (("ToneCurvePV2012", "master"), ("ToneCurvePV2012Red", "red"), ("ToneCurvePV2012Green", "green"), ("ToneCurvePV2012Blue", "blue")):
        raw = crs.get(name)
        if not raw:
            continue
        pts = []
        for part in str(raw).split("|"):
            m = re.match(r"\s*(\d+)\s*,\s*(\d+)\s*", part)
            if m:
                pts.append([int(m.group(1)) / 255.0, int(m.group(2)) / 255.0])
        if len(pts) >= 2:
            dev.setdefault("curve", {})[key] = pts
    if str(crs.get("HasCrop", "")).lower() == "true":
        t, l, b, r = (_num(crs.get(k, "")) for k in ("CropTop", "CropLeft", "CropBottom", "CropRight"))
        if None not in (t, l, b, r):
            dev["crop"] = {"rect": [l, t, r, b], "angle": _num(crs.get("CropAngle", "0")) or 0.0}
    return S.prune(dev)


def _lrtemplate(text: str) -> tuple[str, dict]:
    title = re.search(r'title\s*=\s*"([^"]*)"', text)
    settings_block = text[text.find("settings"):] if "settings" in text else text
    crs = {}
    for m in re.finditer(r'(\w+)\s*=\s*(-?[\d.]+|true|false|"[^"]*")', settings_block):
        crs[m.group(1)] = m.group(2).strip('"')
    curve = re.search(r"ToneCurvePV2012\s*=\s*\{([^}]*)\}", settings_block)
    if curve:
        nums = [int(float(x)) for x in re.findall(r"-?[\d.]+", curve.group(1))]
        crs["ToneCurvePV2012"] = "|".join(f"{nums[i]}, {nums[i + 1]}" for i in range(0, len(nums) - 1, 2))
    return (title.group(1) if title else "Imported"), crs


def convert(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if path.suffix.lower() == ".lrtemplate":
        name, crs = _lrtemplate(text)
    else:
        parsed = metadata.parse_xmp(text)
        crs = parsed.get("crs", {})
        m = re.search(r'crs:Name>\s*<rdf:Alt>\s*<rdf:li[^>]*>([^<]*)<', text) or re.search(r'<crs:Name>([^<]*)<', text)
        name = m.group(1).strip() if m else path.stem
    if not crs:
        return None
    group = crs.get("Group") or path.parent.name
    return {"name": name or path.stem, "group": group, "settings": from_crs(crs)}
