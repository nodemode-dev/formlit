import json
import threading
from typing import Callable
from collections import OrderedDict

import numpy as np

from app.develop import colour, dcp, finish as finish_mod, fringe, kernel, layers as layers_mod, lensblur, masks as masks_mod, planes as planes_mod, profiles, retouch, skin as skin_mod
from app.develop.geometry import Frame
from app.develop.output import to_u8, to_u16
from app.develop.settings import doc as controls_doc, sanitize, section_enabled

_auto_wb: "OrderedDict[int, tuple[float, float]]" = OrderedDict()
_auto_lock = threading.Lock()
AUTO_WB_ENTRIES = 256
WB_PRESETS = {p["id"]: (float(p["temp"]), float(p["tint"])) for p in controls_doc()["wbPresets"] if p.get("temp") is not None and p.get("tint") is not None}


def _number(v, fallback: float) -> float:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v) else fallback


def _auto(img: np.ndarray, info: dict, photo_id: int | None) -> tuple[float, float]:
    from app.develop.auto import auto_wb
    if photo_id is not None:
        with _auto_lock:
            hit = _auto_wb.get(photo_id)
            if hit is not None:
                _auto_wb.move_to_end(photo_id)
                return hit
    got = auto_wb(img, info)
    t, tint = float(got[0]), float(got[1])
    if photo_id is None:
        return t, tint
    with _auto_lock:
        _auto_wb[photo_id] = (t, tint)
        _auto_wb.move_to_end(photo_id)
        while len(_auto_wb) > AUTO_WB_ENTRIES:
            _auto_wb.popitem(last=False)
    return t, tint


def effective_wb(img: np.ndarray | None, info: dict, dev: dict, photo_id: int | None = None) -> tuple[float, float]:
    shot = (_number(info.get("asShotTemp"), 6500.0), _number(info.get("asShotTint"), 0.0))
    wb = dev.get("wb") if isinstance(dev, dict) else None
    wb = wb if isinstance(wb, dict) else {}
    mode = wb.get("mode", "asShot")
    if mode == "asShot":
        return shot
    if mode == "auto":
        return shot if img is None else _auto(img, info, photo_id)
    if mode in WB_PRESETS and info.get("raw"):
        return WB_PRESETS[mode]
    return _number(wb.get("temp"), shot[0]), _number(wb.get("tint"), shot[1])


def white_balance(img: np.ndarray, info: dict, dev: dict, photo_id: int | None = None, full: np.ndarray | None = None) -> np.ndarray:
    t, tint = effective_wb(full if full is not None else img, info, dev, photo_id)
    m = colour.wb_matrix(t, tint, _number(info.get("asShotTemp"), 6500.0), _number(info.get("asShotTint"), 0.0))
    if m is None:
        return np.maximum(img, 0.0).astype(np.float32)
    return np.maximum(img @ m.T, 0.0).astype(np.float32)


def effective(dev: dict, info: dict | None = None) -> dict:
    return profiles.effective(sanitize(dev), info)


def plan(src_w: int, src_h: int, dev: dict, max_long: int | None = None, size: tuple[int, int] | None = None, apply_crop: bool = True) -> tuple[Frame, int, int, float]:
    frame = Frame(src_w, src_h, dev, apply_crop)
    w, h = frame.fit(*size) if size is not None else frame.fit_long(max_long)
    return frame, w, h, frame.px_per_long(w)


class Stages:
    def __init__(self) -> None:
        self.geo = ""
        self.sampled: np.ndarray | None = None
        self.lin_key = ""
        self.base: np.ndarray | None = None
        self.look_key = ""
        self.lin: np.ndarray | None = None
        self.planes: dict = {}
        self.mask_key = ""
        self.masks: list = []
        self.lock = threading.Lock()


_stages: "OrderedDict[tuple, Stages]" = OrderedDict()
_stages_lock = threading.Lock()
STAGE_ENTRIES = 6


def _key(*parts) -> str:
    return json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)


def stages_for(slot: tuple) -> Stages:
    with _stages_lock:
        st = _stages.get(slot)
        if st is None:
            st = Stages()
            _stages[slot] = st
        _stages.move_to_end(slot)
        while len(_stages) > STAGE_ENTRIES:
            _stages.popitem(last=False)
        return st


def drop_stages(photo_id: int | None = None) -> None:
    with _stages_lock:
        for k in [k for k in _stages if photo_id is None or k[0] == photo_id]:
            del _stages[k]


def _planes(st: Stages, lin: np.ndarray, eff: dict, ppl: float) -> dict:
    return planes_mod.build(st.planes, lin, eff, ppl)


def stage_render(img: np.ndarray, info: dict, eff: dict, frame: Frame, w: int, h: int, ppl: float, photo_id: int | None, src_long: int | None,
                 slot: tuple | None, region: tuple[int, int] = (0, 0), out_long: int | None = None) -> tuple[np.ndarray, dict, list]:
    st = stages_for(slot) if slot is not None else Stages()
    with st.lock:
        return _stage_render(st, img, info, eff, frame, w, h, ppl, photo_id, src_long, region, out_long or max(w, h))


def _stage_render(st: Stages, img: np.ndarray, info: dict, eff: dict, frame: Frame, w: int, h: int, ppl: float, photo_id: int | None,
                  src_long: int | None, region: tuple[int, int], out_long: int) -> tuple[np.ndarray, dict, list]:
    sh, sw = img.shape[:2]
    geo = _key(id(img), sw, sh, w, h, frame.rect, frame.angle, frame.flip_h, frame.flip_v, frame.turns, eff.get("geometry"), eff.get("optics"),
               eff.get("disabled"), eff.get("spots"), eff.get("redEye"), region)
    if st.geo != geo or st.sampled is None:
        sampled = frame.sample(img, w, h)
        sampled = retouch.apply_spots(sampled, eff.get("spots") or [], frame, ppl)
        st.sampled = retouch.apply_red_eye(sampled, eff.get("redEye") or [], frame, ppl)
        st.geo = geo
        st.lin_key = ""
    wb = effective_wb(img, info, eff, photo_id)
    det = eff.get("detail") or {}
    nr = {k: v for k, v in det.items() if k.startswith("nr")} if section_enabled(eff, "detail") else {}
    long_src = src_long or max(info.get("fullWidth", sw), info.get("fullHeight", sh), sw, sh)
    blur = eff.get("lensBlur") if lensblur.active(eff) else None
    pid = str((eff.get("profile") or {}).get("id", ""))
    camera = dcp.load(pid[4:]) if pid.startswith("dcp:") else None
    lin_key = _key(geo, wb, nr, long_src, out_long, blur, pid if camera else "")
    if st.lin_key != lin_key or st.base is None:
        m = colour.wb_matrix(wb[0], wb[1], float(info.get("asShotTemp", 6500.0)), float(info.get("asShotTint", 0.0)))
        lin = np.maximum(st.sampled, 0.0) if m is None else np.maximum(st.sampled @ m.T, 0.0).astype(np.float32)
        if camera is not None:
            lin = dcp.apply_camera(lin, camera, info, wb).astype(np.float32)
        if nr:
            lin = planes_mod.denoise(lin, eff, long_src, out_long)
        if section_enabled(eff, "optics") and fringe.active(eff.get("optics") or {}):
            lin = fringe.defringe(lin, eff.get("optics") or {}, ppl)
        if blur:
            lin = lensblur.apply(lin, eff, frame, w, h, ppl, photo_id)
        st.base = lin.astype(np.float32)
        st.lin_key = lin_key
        st.look_key = ""
    ev = float((eff.get("light") or {}).get("exposure", 0))
    look = profiles.look_of(eff)
    look_key = _key(lin_key, look[0], ev if dcp.needs_exposure(look[1]) else 0) if look else lin_key
    if st.look_key != look_key or st.lin is None:
        st.lin = st.base if look is None else dcp.apply_look(st.base, look[1], ev).astype(np.float32)
        st.look_key = look_key
        st.planes = {}
        st.mask_key = ""
    planes = _planes(st, st.lin, eff, ppl)
    mask_key = _key(look_key, eff.get("masks"), ev if any(c.get("shape", {}).get("kind") == "luminanceRange" for m in eff.get("masks") or [] for c in m.get("components", [])) else 0)
    if st.mask_key != mask_key:
        st.masks = masks_mod.evaluate(eff, frame, w, h, st.lin, ev, photo_id)
        st.mask_key = mask_key
    return st.lin, planes, st.masks


PROOF_PAPER = {"matte": ((0.93, 0.92, 0.89), 0.12), "glossy": ((0.97, 0.965, 0.95), 0.05), "screen": ((1.0, 1.0, 1.0), 0.0)}


def proof(out: np.ndarray, wide: Callable[[], np.ndarray], opts: dict) -> np.ndarray:
    from app.develop import colour
    dest = str(opts.get("space") or "srgb")
    if dest.startswith("icc:"):
        from app.output import icc
        return icc.soft_proof(out, dest[4:], str(opts.get("intent") or "perceptual"), opts.get("paper") == "simulate", bool(opts.get("gamut")))
    if opts.get("gamut") and dest in colour.SPACES:
        lin = colour.srgb_decode(np.clip(wide(), 0.0, 1.0))
        m = (colour.from_xyz(dest) @ colour.bradford(colour.SPACES["rec2020"][4], colour.SPACES[dest][4]) @ colour.to_xyz("rec2020")).astype(np.float32)
        t = lin @ m.T
        outside = np.any((t < -0.002) | (t > 1.002), axis=-1)
        out = out.copy()
        out[outside] = np.array([1.0, 0.1, 0.55], np.float32)
    paper = opts.get("paper")
    if paper in PROOF_PAPER:
        white, black = PROOF_PAPER[paper]
        w = np.array(white, np.float32)
        out = black + out * (w - black)
    return out


def _skin(out: np.ndarray, eff: dict, ppl: float, space: str) -> np.ndarray:
    if not skin_mod.active(eff) or any(t in str(space).lower() for t in ("linear", "pq", "hlg", "hdr", "scene")):
        return out
    return skin_mod.apply(out, eff, ppl)


def render(img: np.ndarray, info: dict, dev: dict, max_long: int | None = None, size: tuple[int, int] | None = None, space: str = "srgb",
           photo_id: int | None = None, apply_crop: bool = True, overlay: dict | None = None, src_long: int | None = None,
           slot: tuple | None = None) -> np.ndarray:
    eff = effective(dev or {}, info)
    sh, sw = img.shape[:2]
    frame, w, h, ppl = plan(sw, sh, eff, max_long, size, apply_crop)
    lin, planes, evaluated = stage_render(img, info, eff, frame, w, h, ppl, photo_id, src_long, slot)
    fin = lambda e, p: _skin(kernel.best_finish()(lin, p, e, frame, info, w, h, ppl, evaluated, space), e, ppl, space)
    out = layers_mod.composite(fin(eff, planes), fin, lin, planes, eff, ppl, frame, w, h, photo_id)
    if overlay:
        if overlay.get("proof"):
            out = proof(out, lambda: kernel.best_finish()(lin, planes, eff, frame, info, w, h, ppl, evaluated, "rec2020"), overlay["proof"])
        if overlay.get("clipping"):
            out = finish_mod.clipping_overlay(out, overlay.get("shadows", True), overlay.get("highlights", True))
        mid = overlay.get("mask")
        if mid is not None:
            for alpha, _, i in evaluated:
                if i == int(mid):
                    out = finish_mod.mask_overlay(out, alpha, tuple(overlay.get("color", (1.0, 0.23, 0.23))), float(overlay.get("opacity", 0.5)))
        if overlay.get("depth") and (eff.get("lensBlur") or {}).get("depth"):
            out = lensblur.visualize(out, eff, frame, w, h, photo_id)
        if overlay.get("spots") is not None:
            out = finish_mod.spots_overlay(out, float(overlay["spots"]))
    return out


def render_region(img: np.ndarray, info: dict, dev: dict, region: list[float], out_long: int, space: str = "srgb", photo_id: int | None = None,
                  overlay: dict | None = None, src_long: int | None = None, slot: tuple | None = None, margin: int | None = None) -> tuple[np.ndarray, list[int], list[int]]:
    eff = effective(dev or {}, info)
    sh, sw = img.shape[:2]
    full = Frame(sw, sh, eff, True)
    W, H = full.fit_long(out_long)
    if margin is None:
        margin = planes_mod.margin(eff, full.px_per_long(W))
    u0, v0, u1, v1 = (min(1.0, max(0.0, float(v))) for v in region)
    rx0, ry0 = int(np.floor(min(u0, u1) * W)), int(np.floor(min(v0, v1) * H))
    rx1, ry1 = max(rx0 + 1, int(np.ceil(max(u0, u1) * W))), max(ry0 + 1, int(np.ceil(max(v0, v1) * H)))
    px0, py0 = max(0, rx0 - margin), max(0, ry0 - margin)
    px1, py1 = min(W, rx1 + margin), min(H, ry1 + margin)
    fx0, fx1 = (W - px1, W - px0) if full.flip_h else (px0, px1)
    fy0, fy1 = (H - py1, H - py0) if full.flip_v else (py0, py1)
    x0, y0, x1, y1 = full.rect
    sub = [x0 + (x1 - x0) * fx0 / W, y0 + (y1 - y0) * fy0 / H, x0 + (x1 - x0) * fx1 / W, y0 + (y1 - y0) * fy1 / H]
    eff2 = json.loads(json.dumps(eff))
    eff2.setdefault("crop", {})["rect"] = sub
    eff2.setdefault("geometry", {})["constrainCrop"] = False
    frame = Frame(sw, sh, eff2, True)
    w, h = px1 - px0, py1 - py0
    ppl = full.px_per_long(W)
    lin, planes, evaluated = stage_render(img, info, eff2, frame, w, h, ppl, photo_id, src_long, slot, region=(px0, py0), out_long=max(W, H))
    fin = lambda e, p: _skin(kernel.best_finish()(lin, p, e, full, info, W, H, ppl, evaluated, space, region=(px0, py0)), e, ppl, space)
    out = layers_mod.composite(fin(eff2, planes), fin, lin, planes, eff2, ppl, frame, w, h, photo_id)
    if overlay:
        if overlay.get("proof"):
            out = proof(out, lambda: kernel.best_finish()(lin, planes, eff2, full, info, W, H, ppl, evaluated, "rec2020", region=(px0, py0)), overlay["proof"])
        if overlay.get("clipping"):
            out = finish_mod.clipping_overlay(out, overlay.get("shadows", True), overlay.get("highlights", True))
        mid = overlay.get("mask")
        if mid is not None:
            for alpha, _, i in evaluated:
                if i == int(mid):
                    out = finish_mod.mask_overlay(out, alpha, tuple(overlay.get("color", (1.0, 0.23, 0.23))), float(overlay.get("opacity", 0.5)))
        if overlay.get("depth") and (eff2.get("lensBlur") or {}).get("depth"):
            out = lensblur.visualize(out, eff2, frame, w, h, photo_id)
        if overlay.get("spots") is not None:
            out = finish_mod.spots_overlay(out, float(overlay["spots"]))
    crop = out[ry0 - py0: ry1 - py0, rx0 - px0: rx1 - px0]
    return crop, [rx0, ry0, rx1, ry1], [W, H]


def histogram(e: np.ndarray, bins: int = 256) -> dict:
    planes = np.ascontiguousarray(np.asarray(e, np.float32)[..., :3].reshape(-1, 3).T)
    out = {}
    for k, v in zip(("r", "g", "b", "l"), (planes[0], planes[1], planes[2], colour.LUMA_709 @ planes)):
        x = v.astype(np.float64)
        x *= bins - 1
        x += 0.5
        np.fmax(x, 0.0, out=x)
        np.fmin(x, bins - 1, out=x)
        out[k] = np.bincount(x.astype(np.intp), minlength=bins).tolist()
    return out


__all__ = ["render", "to_u8", "to_u16", "histogram", "plan", "effective_wb", "white_balance"]
