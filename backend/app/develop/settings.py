import copy
import json
import math
import numbers
from functools import lru_cache
from typing import Any

from app.core import config

BANDS = ("red", "orange", "yellow", "green", "aqua", "blue", "purple", "magenta")
SECTION_TOGGLES = {"curve", "mixer", "grading", "detail", "optics", "geometry", "effects", "lensBlur", "calibration"}
LISTS = ("masks", "spots", "redEye", "pointColors", "disabled")
CURVE_CHANNELS = ("master", "red", "green", "blue")
GROUPS = {
    "whiteBalance": ("wb",), "basicTone": ("light",), "presence": ("effects", "color"), "toneCurve": ("curve",), "colorMixer": ("mixer",),
    "pointColor": ("pointColors",), "bwMix": ("bw",), "treatment": ("treatment",), "colorGrading": ("grading",), "detail": ("detail",),
    "lensCorrections": ("optics",), "transform": ("geometry",), "effects": ("vignette", "grain"), "calibration": ("calibration",),
    "profile": ("profile",), "crop": ("crop", "orientation"), "masks": ("masks",), "spots": ("spots",), "redEye": ("redEye",),
    "lensBlur": ("lensBlur",), "hdr": ("hdr",),
}
UNPICKED = ("crop", "orientation", "masks", "spots", "redEye")
UNSYNCED_GROUPS = ("crop", "masks", "spots", "redEye")
FULL_FRAME = (0.0, 0.0, 1.0, 1.0)
DEFAULT_EPS = 1e-9
DIAGONAL_EPS = 1e-6


@lru_cache(maxsize=1)
def doc() -> dict:
    return json.loads((config.shared_dir() / "controls.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def controls() -> dict:
    return {c["id"]: c for c in doc()["controls"]}


@lru_cache(maxsize=1)
def local_controls() -> dict:
    return {c["id"]: c for c in doc()["local"]}


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _pairs(v: Any) -> bool:
    return isinstance(v, list) and all(isinstance(p, (list, tuple)) and len(p) >= 2 and _num(p[0]) and _num(p[1]) for p in v)


def _parent(dev: Any, cid: str) -> tuple[dict | None, str]:
    parts = cid.split(".")
    cur = dev
    for p in parts[:-1]:
        cur = cur.get(p) if isinstance(cur, dict) else None
    return (cur if isinstance(cur, dict) else None), parts[-1]


def get(dev: dict, cid: str) -> float:
    spec = controls().get(cid)
    if spec is None:
        return 0.0
    parent, key = _parent(dev, cid)
    v = parent.get(key) if parent is not None else None
    return float(v) if _num(v) else float(spec["default"])


def clamp(cid: str, value: Any) -> float:
    spec = controls()[cid]
    if not isinstance(value, numbers.Real) or isinstance(value, bool) or math.isnan(value):
        return float(spec["default"])
    return float(min(max(float(value), float(spec["min"])), float(spec["max"])))


def put(dev: dict, cid: str, value: Any) -> None:
    spec = controls()[cid]
    v = clamp(cid, value)
    parts = cid.split(".")
    cur = dev
    for p in parts[:-1]:
        if not isinstance(cur.get(p), dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = int(round(v)) if int(spec["decimals"]) == 0 else round(v, 4)


def _clean(d: dict, top: bool = False) -> None:
    for k in list(d):
        v = d[k]
        if v is None:
            del d[k]
        elif isinstance(v, dict):
            _clean(v)
            if not v and not (top and k == "crop"):
                del d[k]


def prune(dev: dict) -> dict:
    out = copy.deepcopy(dev) if isinstance(dev, dict) else {}
    wb = out.get("wb")
    keep_wb = isinstance(wb, dict) and wb.get("mode", "asShot") != "asShot"
    for cid, spec in controls().items():
        if keep_wb and cid.startswith("wb."):
            continue
        parent, key = _parent(out, cid)
        if parent is not None and _num(parent.get(key)) and abs(parent[key] - spec["default"]) <= DEFAULT_EPS:
            del parent[key]
    _clean(out, top=True)
    for key in LISTS:
        if isinstance(out.get(key), list) and not out[key]:
            del out[key]
    curve = out.get("curve")
    if isinstance(curve, dict):
        for ch in CURVE_CHANNELS:
            pts = curve.get(ch)
            if _pairs(pts) and all(abs(p[0] - p[1]) <= DIAGONAL_EPS for p in pts):
                del curve[ch]
        if not curve:
            del out["curve"]
    prof = out.get("profile")
    if isinstance(prof, dict) and prof.get("id") in (None, "fl.color") and "amount" not in prof:
        del out["profile"]
    if out.get("treatment") == "color":
        del out["treatment"]
    if out.get("wb") == {"mode": "asShot"}:
        del out["wb"]
    crop = out.get("crop")
    if isinstance(crop, dict):
        r = crop.get("rect")
        if isinstance(r, list) and len(r) == 4 and all(_num(x) and abs(x - f) <= DEFAULT_EPS for x, f in zip(r, FULL_FRAME)):
            del crop["rect"]
        for k in ("flipH", "flipV"):
            if crop.get(k) is False:
                del crop[k]
        if "aspect" in crop and crop["aspect"] is None:
            del crop["aspect"]
        if not crop:
            del out["crop"]
    if _num(out.get("orientation")) and out["orientation"] == 0:
        del out["orientation"]
    return out


def section_enabled(dev: dict, section: str) -> bool:
    off = dev.get("disabled") if isinstance(dev, dict) else None
    return not (isinstance(off, list) and section in off)


def defaults_for(kind: str) -> dict:
    return copy.deepcopy(doc()["rawDefaults"]) if kind == "raw" else {}


def merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base) if isinstance(base, dict) else {}
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _covered(groups) -> set[str]:
    return {k for g in groups for k in GROUPS.get(g, (g,))}


def pick_groups(dev: dict, groups: list[str] | None = None) -> dict:
    if groups is None:
        return {k: copy.deepcopy(v) for k, v in dev.items() if k not in UNPICKED}
    keys = _covered(groups)
    return {k: copy.deepcopy(v) for k, v in dev.items() if k in keys}


def scale(dev: dict, amount: float) -> dict:
    out = copy.deepcopy(dev)
    for cid, spec in controls().items():
        if cid.startswith("grading.") and cid.endswith(".hue"):
            continue
        parent, key = _parent(out, cid)
        if parent is not None and _num(parent.get(key)):
            d = float(spec["default"])
            parent[key] = clamp(cid, d + (parent[key] - d) * float(amount))
    curve = out.get("curve")
    if isinstance(curve, dict):
        k = max(0.0, min(2.0, float(amount)))
        for ch in CURVE_CHANNELS:
            if _pairs(curve.get(ch)):
                curve[ch] = [[float(p[0]), min(1.0, max(0.0, float(p[0]) + (float(p[1]) - float(p[0])) * k))] for p in curve[ch]]
    return out


def apply_groups(target: dict, source: dict, groups: list[str] | None = None, amount: float = 1.0) -> dict:
    covered = _covered(groups if groups is not None else [g for g in GROUPS if g not in UNSYNCED_GROUPS])
    out = {k: copy.deepcopy(v) for k, v in (target or {}).items() if k not in covered}
    picked = pick_groups(source or {}, groups)
    if float(amount) != 1.0:
        picked = scale(picked, amount)
    return prune(merge(out, picked))


def edited(dev: dict, kind: str) -> bool:
    return prune(dev) != prune(defaults_for(kind))


def sanitize(dev: Any) -> dict:
    out = copy.deepcopy(dev) if isinstance(dev, dict) else {}
    for key in LISTS:
        if key in out and not isinstance(out[key], list):
            del out[key]
    for cid in controls():
        parts = cid.split(".")
        cur = out
        for p in parts[:-1]:
            nxt = cur.get(p)
            if nxt is not None and not isinstance(nxt, dict):
                del cur[p]
                nxt = None
            if nxt is None:
                cur = None
                break
            cur = nxt
        if cur is None or parts[-1] not in cur:
            continue
        if _num(cur[parts[-1]]):
            cur[parts[-1]] = clamp(cid, cur[parts[-1]])
        else:
            del cur[parts[-1]]
    crop = out.get("crop")
    if crop is not None and not isinstance(crop, dict):
        del out["crop"]
    elif isinstance(crop, dict):
        r = crop.get("rect")
        if r is not None and not (isinstance(r, list) and len(r) == 4 and all(_num(x) for x in r) and -0.5 <= r[0] < r[2] <= 1.5 and -0.5 <= r[1] < r[3] <= 1.5):
            crop.pop("rect")
        if "angle" in crop and not _num(crop["angle"]):
            crop.pop("angle")
        for k in ("flipH", "flipV"):
            if k in crop and not isinstance(crop[k], bool):
                crop.pop(k)
    if "orientation" in out and not (_num(out["orientation"]) and float(out["orientation"]).is_integer()):
        del out["orientation"]
    if out.get("treatment") not in (None, "color", "bw"):
        del out["treatment"]
    for key, field in (("wb", "mode"), ("profile", "id")):
        sec = out.get(key)
        if sec is not None and not isinstance(sec, dict):
            del out[key]
        elif isinstance(sec, dict) and field in sec and not isinstance(sec[field], str):
            if key == "profile":
                del out[key]
            else:
                sec.pop(field)
    curve = out.get("curve")
    if isinstance(curve, dict):
        for ch in CURVE_CHANNELS:
            if ch in curve and not _pairs(curve[ch]):
                del curve[ch]
    if "spots" in out:
        out["spots"] = [s for s in out["spots"] if isinstance(s, dict) and _pairs(s.get("points", [])) and (s.get("source") is None or _pairs([s["source"]]))
                        and all(_num(s[k]) for k in ("size", "feather", "opacity") if k in s)]
    if "masks" in out:
        out["masks"] = [m for m in out["masks"] if isinstance(m, dict) and isinstance(m.get("components", []), list)
                        and all(isinstance(c, dict) and isinstance(c.get("shape", {}), dict) for c in m.get("components", []))
                        and isinstance(m.get("adjust", {}), dict)]
    for key in ("redEye", "pointColors"):
        if key in out:
            out[key] = [x for x in out[key] if isinstance(x, dict)]
    if "disabled" in out:
        out["disabled"] = [x for x in out["disabled"] if isinstance(x, str)]
    return out
