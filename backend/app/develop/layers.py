import copy
from typing import Callable

import numpy as np

from app.develop import masks as masks_mod
from app.develop import planes as planes_mod
from app.develop.settings import merge

PHOTO_ONLY = ("crop", "orientation", "geometry", "optics", "spots", "redEye", "lensBlur", "masks", "layers", "wb", "profile", "disabled", "hdr")
MAX_LAYERS = 8


def layerable(top: str, key: str = "") -> bool:
    return top not in PHOTO_ONLY and not (top == "detail" and key.startswith("nr"))


def active(eff: dict) -> list[dict]:
    ls = eff.get("layers") if isinstance(eff, dict) else None
    if not isinstance(ls, list):
        return []
    out = []
    for layer in ls[:MAX_LAYERS]:
        if not isinstance(layer, dict) or not layer.get("visible", True):
            continue
        if _opacity(layer) <= 0.0 or not isinstance(layer.get("settings"), dict) or not layer["settings"]:
            continue
        out.append(layer)
    return out


def _opacity(layer: dict) -> float:
    try:
        return min(max(float(layer.get("opacity", 100)), 0.0), 100.0) / 100.0
    except (TypeError, ValueError):
        return 0.0


def merged(eff: dict, layer: dict) -> dict:
    out = {k: v for k, v in eff.items() if k != "layers"}
    for k, v in layer["settings"].items():
        if not layerable(k):
            continue
        if k == "detail" and isinstance(v, dict):
            d = dict(out.get("detail") or {})
            d.update({kk: vv for kk, vv in v.items() if layerable(k, kk)})
            out["detail"] = d
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def alpha(layer: dict, frame, w: int, h: int, lin: np.ndarray, ev: float, photo_id: int | None) -> np.ndarray | float:
    m = layer.get("mask") if isinstance(layer.get("mask"), dict) else {}
    comps = m.get("components") if isinstance(m.get("components"), list) else []
    op = _opacity(layer)
    if not comps:
        return 0.0 if m.get("invert") else op
    got = masks_mod.evaluate({"masks": [{"id": 0, "visible": True, "components": comps, "invert": bool(m.get("invert")), "refine": m.get("refine", 0)}]},
                             frame, w, h, lin, ev, photo_id)
    if not got:
        return 0.0
    return got[0][0] * np.float32(op)


def composite(out: np.ndarray, finish: Callable[[dict, dict], np.ndarray], lin: np.ndarray, planes: dict, eff: dict, ppl: float,
              mask_frame, mw: int, mh: int, photo_id: int | None) -> np.ndarray:
    ls = active(eff)
    if not ls:
        return out
    ev = float((eff.get("light") or {}).get("exposure", 0) or 0)
    for layer in ls:
        a = alpha(layer, mask_frame, mw, mh, lin, ev, photo_id)
        if isinstance(a, float):
            if a <= 0.0:
                continue
        elif not np.any(a > 1e-4):
            continue
        eff_l = merged(eff, layer)
        top = finish(eff_l, planes_mod.build(dict(planes), lin, eff_l, ppl))
        if top.shape[:2] != out.shape[:2]:
            continue
        if isinstance(a, float):
            out = out + (top - out) * np.float32(a)
        else:
            k = a[..., None] if out.ndim == 3 else a
            out = out + (top - out) * k
    return out.astype(np.float32, copy=False)
