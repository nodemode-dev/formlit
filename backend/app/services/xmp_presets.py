import json
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


def from_crs(crs: dict, aspect: float = 1.5) -> dict:
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
    look = re.search(r'Name[^>]*>\s*([^<]+?)\s*<', crs.get("Look") or "") or re.search(r'Name="([^"]+)"', crs.get("Look") or "")
    amount = re.search(r'Amount[^>]*>\s*([\d.]+)\s*<', crs.get("Look") or "") or re.search(r'Amount="([\d.]+)"', crs.get("Look") or "")
    if look:
        from app.develop.profiles import PROFILES
        name = look.group(1)
        pid = {v: k for k, v in LOOKS.items()}.get(name) or next((p["id"] for p in PROFILES if p["name"] == name), None)
        if pid:
            dev["profile"] = {"id": pid, **({"amount": round(float(amount.group(1)) * 100)} if amount and float(amount.group(1)) != 1.0 else {})}
    elif str(crs.get("CameraProfile", "")).startswith("Camera "):
        from app.develop.camera_styles import id_for_name
        dev["profile"] = {"id": id_for_name(str(crs.get("CameraProfile", "")))}
    spots = []
    for item in [s for s in str(crs.get("RetouchInfo") or "").split("|") if "centerX" in s]:
        kv = {k.strip(): v.strip() for k, _, v in (p.partition("=") for p in item.split(","))}
        cx, cy, sx, sy = (_f(kv.get(k)) for k in ("centerX", "centerY", "sourceX", "sourceY"))
        spots.append({"points": [[cx, cy]], "size": _f(kv.get("radius"), 0.02), "source": [sx - cx, sy - cy] if "sourceX" in kv else None,
                      "feather": 50, "opacity": 100, "mode": "clone" if kv.get("spotType") == "clone" else "heal"})
    if spots:
        dev["spots"] = spots
    eyes = []
    for item in [s for s in str(crs.get("RedEyeInfo") or "").split("|") if s.strip()]:
        v = [_f(x) for x in item.split(",")]
        if len(v) >= 7:
            eyes.append({"center": [v[1], v[2]], "rx": v[3], "ry": v[4], "pupilSize": round(v[5] * 100), "darken": round(v[6] * 100)})
    if eyes:
        dev["redEye"] = eyes
    if crs.get("MaskGroupBasedCorrections", "").lstrip().startswith("<"):
        masks = masks_from(crs["MaskGroupBasedCorrections"], aspect)
        if masks:
            dev["masks"] = masks
    return S.prune(dev)


def to_crs(dev: dict) -> dict:
    out: dict[str, str] = {"ProcessVersion": "11.0", "Version": "15.0"}
    for key, cid in SCALAR.items():
        if key.startswith("SplitToning") or cid not in S.controls():
            continue
        v = S.get(dev, cid)
        if v != S.controls()[cid].get("default", 0) or key in ("Exposure2012", "Contrast2012"):
            out[key] = (f"{v:+.2f}" if key == "Exposure2012" else f"{v:+.0f}" if S.controls()[cid].get("min", 0) < 0 else f"{v:.0f}")
    wb = dev.get("wb") or {}
    out["WhiteBalance"] = {"asShot": "As Shot", "auto": "Auto", "daylight": "Daylight", "cloudy": "Cloudy", "shade": "Shade", "tungsten": "Tungsten",
                           "fluorescent": "Fluorescent", "flash": "Flash"}.get(wb.get("mode", "asShot"), "Custom")
    if out["WhiteBalance"] != "Custom":
        out.pop("Temperature", None)
        out.pop("Tint", None)
    for lr, band in BANDS.items():
        for kind, short in (("Hue", "hue"), ("Saturation", "sat"), ("Luminance", "lum")):
            v = S.get(dev, f"mixer.{band}.{short}") if f"mixer.{band}.{short}" in S.controls() else 0
            if v:
                out[f"{kind}Adjustment{lr}"] = f"{v:+.0f}"
        v = S.get(dev, f"bw.{band}") if f"bw.{band}" in S.controls() else 0
        if v:
            out[f"GrayMixer{lr}"] = f"{v:+.0f}"
    out["ConvertToGrayscale"] = "True" if dev.get("treatment") == "bw" else "False"
    crop = dev.get("crop") or {}
    if crop.get("rect"):
        l, t, r, b = crop["rect"]
        out.update(HasCrop="True", CropLeft=f"{l:.6f}", CropTop=f"{t:.6f}", CropRight=f"{r:.6f}", CropBottom=f"{b:.6f}", CropAngle=f"{float(crop.get('angle', 0)):.4f}")
    prof = (dev.get("profile") or {}).get("id", "fl.color")
    if str(prof).startswith("fl.camera"):
        from app.develop.camera_styles import crs_name
        out["CameraProfile"] = crs_name(str(prof))
    else:
        out["CameraProfile"] = "Adobe Standard"
    optics = dev.get("optics") or {}
    lp = optics.get("profile") or {}
    out["LensProfileEnable"] = "1" if lp.get("enabled") else "0"
    if lp.get("enabled"):
        lf = lp.get("lensfun") or {}
        out["LensProfileSetup"] = "Auto" if not lf.get("lens") else "Custom"
        if lf.get("lens"):
            out["LensProfileName"] = str(lf.get("lens"))
        out["LensProfileDistortionScale"] = f"{float(optics.get('profileDistortion', 100)):.0f}"
        out["LensProfileVignettingScale"] = f"{float(optics.get('profileVignetting', 100)):.0f}"
    out["AutoLateralCA"] = "1" if optics.get("autoCaRed") or optics.get("autoCaBlue") else "0"
    out["HasSettings"] = "True"
    if any((dev.get("curve") or {}).get(k) for k in ("master", "red", "green", "blue")):
        out["ToneCurveName2012"] = "Custom"
    return out


LOOKS = {"fl.color": "Adobe Color", "fl.neutral": "Adobe Neutral", "fl.vivid": "Adobe Vivid", "fl.landscape": "Adobe Landscape", "fl.portrait": "Adobe Portrait",
         "fl.monochrome": "Adobe Monochrome"}
LOCAL = {"exposure": ("LocalExposure2012", 4.0), "contrast": ("LocalContrast2012", 100.0), "highlights": ("LocalHighlights2012", 100.0),
         "shadows": ("LocalShadows2012", 100.0), "whites": ("LocalWhites2012", 100.0), "blacks": ("LocalBlacks2012", 100.0), "texture": ("LocalTexture", 100.0),
         "clarity": ("LocalClarity2012", 100.0), "dehaze": ("LocalDehaze", 100.0), "saturation": ("LocalSaturation", 100.0), "sharpness": ("LocalSharpness", 100.0),
         "noise": ("LocalLuminanceNoise", 100.0), "moire": ("LocalMoire", 100.0), "defringe": ("LocalDefringe", 100.0), "temp": ("LocalTemperature", 100.0),
         "tint": ("LocalTint", 100.0), "hue": ("LocalHue", 100.0)}
AI_SUBTYPES = {"subject": "1", "sky": "2", "people": "3", "object": "4", "background": "1", "landscape": "5"}


def _x(v: object) -> str:
    return metadata._esc(str(v))


def _seq(name: str, items: list[str]) -> str:
    return f"<crs:{name}><rdf:Seq>" + "".join(f"<rdf:li>{_x(i)}</rdf:li>" for i in items) + f"</rdf:Seq></crs:{name}>"


def _head(op: str, inverted: bool = False, value: str = "1") -> str:
    blend = {"add": "0", "intersect": "1", "subtract": "1"}.get(op, "0")
    inv = (op == "subtract") != inverted
    return f'crs:MaskActive="true" crs:MaskBlendMode="{blend}" crs:MaskInverted="{"true" if inv else "false"}" crs:MaskValue="{value}"'


def _mask_xml(shape: dict, op: str, aspect: float) -> str:
    kind = shape.get("kind")
    kx, ky = (1.0, aspect) if aspect >= 1 else (1.0 / aspect, 1.0)
    head = _head(op)
    if kind == "linear":
        (sx, sy), (ex, ey) = shape.get("start", [0.5, 0.0]), shape.get("end", [0.5, 1.0])
        return f'<rdf:li><rdf:Description crs:What="Mask/Gradient" {head} crs:FullX="{sx:.6f}" crs:FullY="{sy:.6f}" crs:ZeroX="{ex:.6f}" crs:ZeroY="{ey:.6f}"/></rdf:li>'
    if kind == "radial":
        cx, cy = shape.get("center", [0.5, 0.5])
        rx, ry = float(shape.get("rx", 0.2)) * kx, float(shape.get("ry", 0.2)) * ky
        flip = "false" if shape.get("invert") else "true"
        return (f'<rdf:li><rdf:Description crs:What="Mask/CircularGradient" {head} crs:Top="{cy - ry:.6f}" crs:Left="{cx - rx:.6f}" crs:Bottom="{cy + ry:.6f}" '
                f'crs:Right="{cx + rx:.6f}" crs:Angle="{float(shape.get("angle", 0)):.4f}" crs:Midpoint="50" crs:Roundness="0" crs:Feather="{float(shape.get("feather", 50)):.0f}" crs:Flipped="{flip}"/></rdf:li>')
    if kind == "brush":
        out = []
        for s in shape.get("strokes") or []:
            dabs = [f"d {float(p[0]):.6f} {float(p[1]):.6f}" for p in s.get("points") or []]
            if not dabs:
                continue
            out.append(f'<rdf:li><rdf:Description crs:What="Mask/Paint" {_head(op, value="0" if s.get("erase") else "1")} crs:Radius="{float(s.get("size", 0.03)):.6f}" '
                       f'crs:Flow="{float(s.get("flow", 80)) / 100:.3f}" crs:CenterWeight="{1 - float(s.get("feather", 60)) / 100:.3f}">{_seq("Dabs", dabs)}</rdf:Description></rdf:li>')
        return "".join(out)
    if kind == "luminanceRange":
        lo, hi = float(shape.get("lo", 0)), float(shape.get("hi", 1))
        lf, hf = float(shape.get("loFeather", 0.1)), float(shape.get("hiFeather", 0.1))
        return (f'<rdf:li><rdf:Description crs:What="Mask/RangeMask" {head} crs:MaskSubType="1"><crs:CorrectionRangeMask crs:Version="3" crs:Type="2" '
                f'crs:LumRange="{max(0, lo - lf):.4f} {lo:.4f} {hi:.4f} {min(1, hi + hf):.4f}"/></rdf:Description></rdf:li>')
    if kind == "colorRange":
        samples = " ".join(f"{s[1]:.4f} {s[2]:.4f}" for s in shape.get("samples") or [])
        return (f'<rdf:li><rdf:Description crs:What="Mask/RangeMask" {head} crs:MaskSubType="0"><crs:CorrectionRangeMask crs:Version="3" crs:Type="1" '
                f'crs:ColorAmount="{float(shape.get("refine", 50)) / 100:.3f}" crs:SampleType="0" fl:samples="{_x(samples)}"/></rdf:Description></rdf:li>')
    if kind in AI_SUBTYPES or kind == "depthRange":
        sub = "6" if kind == "depthRange" else AI_SUBTYPES[kind]
        extra = f' crs:MaskName="{_x(shape.get("label") or shape.get("part") or kind)}"'
        if kind == "depthRange":
            extra += f' crs:DepthRange="{float(shape.get("lo", 0)):.4f} {float(shape.get("hi", 1)):.4f}"'
        return f'<rdf:li><rdf:Description crs:What="Mask/Image" {_head(op, inverted=kind == "background")} crs:MaskSubType="{sub}"{extra}/></rdf:li>'
    return ""


def _corrections_xml(masks: list, aspect: float) -> str:
    items = []
    for m in masks:
        adj = m.get("adjust") or {}
        attrs = ['crs:What="Correction"', f'crs:CorrectionAmount="{float(adj.get("amount", 100)) / 100:.3f}"',
                 f'crs:CorrectionActive="{"false" if m.get("visible") is False else "true"}"', f'crs:CorrectionName="{_x(m.get("name", "Mask"))}"']
        for k, (tag, div) in LOCAL.items():
            if adj.get(k):
                attrs.append(f'crs:{tag}="{float(adj[k]) / div:.6f}"')
        comps = "".join(_mask_xml(c.get("shape") or {}, c.get("op", "add"), aspect) for c in m.get("components") or [] if c.get("op") != "refine")
        if not comps:
            continue
        items.append(f'<rdf:li><rdf:Description {" ".join(attrs)}><crs:CorrectionMasks><rdf:Seq>{comps}</rdf:Seq></crs:CorrectionMasks></rdf:Description></rdf:li>')
    return f"<crs:MaskGroupBasedCorrections><rdf:Seq>{''.join(items)}</rdf:Seq></crs:MaskGroupBasedCorrections>" if items else ""


def crs_children(dev: dict, aspect: float = 1.5) -> list[str]:
    out = []
    curve = dev.get("curve") or {}
    for key, name in (("master", "ToneCurvePV2012"), ("red", "ToneCurvePV2012Red"), ("green", "ToneCurvePV2012Green"), ("blue", "ToneCurvePV2012Blue")):
        pts = curve.get(key)
        if pts and len(pts) >= 2:
            out.append(_seq(name, [f"{round(float(x) * 255)}, {round(float(y) * 255)}" for x, y in pts]))
    prof = dev.get("profile") or {}
    look = LOOKS.get(prof.get("id", "")) if prof else None
    if look is None and prof.get("id") is not None and not str(prof.get("id")).startswith("fl.camera"):
        from app.develop.profiles import PROFILES
        look = next((p["name"] for p in PROFILES if p["id"] == prof.get("id")), None)
    if look:
        out.append(f'<crs:Look rdf:parseType="Resource"><crs:Name>{_x(look)}</crs:Name><crs:Amount>{float(prof.get("amount", 100)) / 100:.3f}</crs:Amount></crs:Look>')
    spots = []
    for s in dev.get("spots") or []:
        if not s.get("points"):
            continue
        cx, cy = s["points"][0]
        src = s.get("source") or [0.0, 0.0]
        spots.append(f"centerX = {cx:.6f}, centerY = {cy:.6f}, radius = {float(s.get('size', 0.02)):.6f}, sourceState = sourceSetExplicitly, "
                     f"sourceX = {cx + float(src[0]):.6f}, sourceY = {cy + float(src[1]):.6f}, spotType = {'clone' if s.get('mode') == 'clone' else 'heal'}")
    if spots:
        out.append(_seq("RetouchInfo", spots))
    eyes = [f"1, {e['center'][0]:.6f}, {e['center'][1]:.6f}, {float(e.get('rx', 0.01)):.6f}, {float(e.get('ry', 0.01)):.6f}, {float(e.get('pupilSize', 50)) / 100:.6f}, {float(e.get('darken', 50)) / 100:.6f}"
            for e in dev.get("redEye") or [] if e.get("center")]
    if eyes:
        out.append(_seq("RedEyeInfo", eyes))
    masks = _corrections_xml(dev.get("masks") or [], aspect)
    if masks:
        out.append(masks)
    lb = dev.get("lensBlur") or {}
    if float(lb.get("amount", 0) or 0) > 0:
        f, r = float(lb.get("focalDistance", 50)), float(lb.get("focalRange", 20))
        out.append(f'<crs:LensBlur rdf:parseType="Resource"><crs:Version>1</crs:Version><crs:Active>true</crs:Active><crs:BlurAmount>{float(lb["amount"]):.0f}</crs:BlurAmount>'
                   f'<crs:BokehType>{ {"circle": 0, "bubble": 1, "blade": 2, "ring": 3, "cateye": 4}.get(str(lb.get("shape", "circle")), 0)}</crs:BokehType>'
                   f'<crs:FocalRange>{max(0, f - r / 2):.0f} {f:.0f} {f:.0f} {min(100, f + r / 2):.0f}</crs:FocalRange>'
                   f'<crs:HighlightsBoost>{float(lb.get("bokeh", 0)):.0f}</crs:HighlightsBoost></crs:LensBlur>')
    return out


def _f(v: str | None, default: float = 0.0) -> float:
    n = _num(v) if v is not None else None
    return default if n is None else n


def masks_from(xml: str, aspect: float = 1.5) -> list[dict]:
    import xml.etree.ElementTree as ET
    ns = {"rdf": metadata.NS["rdf"], "crs": metadata.NS["crs"]}
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    C = "{" + ns["crs"] + "}"
    kx, ky = (1.0, aspect) if aspect >= 1 else (1.0 / aspect, 1.0)
    out = []
    for corr in root.findall("./rdf:Seq/rdf:li/rdf:Description", ns):
        a = corr.attrib
        adjust: dict = {}
        for k, (tag, div) in LOCAL.items():
            if C + tag in a and _f(a[C + tag]):
                adjust[k] = round(_f(a[C + tag]) * div, 3)
        if _f(a.get(C + "CorrectionAmount"), 1.0) != 1.0:
            adjust["amount"] = round(_f(a.get(C + "CorrectionAmount"), 1.0) * 100, 1)
        comps = []
        for mk in corr.findall("./crs:CorrectionMasks/rdf:Seq/rdf:li/rdf:Description", ns):
            m = mk.attrib
            what = m.get(C + "What", "")
            op = "subtract" if m.get(C + "MaskInverted") == "true" and m.get(C + "MaskBlendMode") == "1" else "intersect" if m.get(C + "MaskBlendMode") == "1" else "add"
            if what == "Mask/Gradient":
                shape = {"kind": "linear", "start": [_f(m.get(C + "FullX")), _f(m.get(C + "FullY"))], "end": [_f(m.get(C + "ZeroX")), _f(m.get(C + "ZeroY"), 1.0)]}
            elif what == "Mask/CircularGradient":
                t, l, b, r = (_f(m.get(C + k)) for k in ("Top", "Left", "Bottom", "Right"))
                shape = {"kind": "radial", "center": [(l + r) / 2, (t + b) / 2], "rx": abs(r - l) / 2 / kx, "ry": abs(b - t) / 2 / ky,
                         "angle": _f(m.get(C + "Angle")), "feather": _f(m.get(C + "Feather"), 50)}
                if m.get(C + "Flipped") == "false":
                    shape["invert"] = True
            elif what == "Mask/Paint":
                dabs = [d.text or "" for d in mk.findall("./crs:Dabs/rdf:Seq/rdf:li", ns)]
                pts = [[float(p[1]), float(p[2])] for p in (d.split() for d in dabs) if len(p) == 3]
                shape = {"kind": "brush", "strokes": [{"points": pts, "size": _f(m.get(C + "Radius"), 0.03), "flow": _f(m.get(C + "Flow"), 0.8) * 100,
                                                       "feather": (1 - _f(m.get(C + "CenterWeight"), 0.4)) * 100, "density": 100, "erase": m.get(C + "MaskValue") == "0"}]}
            elif what == "Mask/Image" and m.get(C + "MaskSubType") in ("1", "2", "3", "6"):
                sub = m.get(C + "MaskSubType")
                kind = {"1": "subject", "2": "sky", "3": "people", "6": "depthRange"}[sub]
                if kind == "subject" and m.get(C + "MaskInverted") == "true" and m.get(C + "MaskBlendMode") != "1":
                    kind = "background"
                shape = {"kind": kind, "bitmap": f"{kind}-xmp-{len(out) + 1}-{len(comps) + 1}"}
                if kind == "depthRange":
                    lo, _, hi = str(m.get(C + "DepthRange") or "0 1").partition(" ")
                    shape.update(lo=_f(lo), hi=_f(hi, 1.0), feather=0.1)
            else:
                continue
            comps.append({"shape": shape, "op": op if comps else "add"})
        if comps:
            out.append({"id": len(out) + 1, "name": a.get(C + "CorrectionName") or f"Mask {len(out) + 1}", "visible": a.get(C + "CorrectionActive") != "false",
                        "components": comps, "adjust": adjust})
    return out


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
    exact = None
    if path.suffix.lower() != ".lrtemplate" and parsed.get("develop"):
        try:
            exact = json.loads(parsed["develop"])
        except ValueError:
            exact = None
    if not crs and exact is None:
        return None
    group = crs.get("Group") or path.parent.name
    return {"name": name or path.stem, "group": group, "settings": exact if isinstance(exact, dict) else from_crs(crs)}
