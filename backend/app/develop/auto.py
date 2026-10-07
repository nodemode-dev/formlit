import math

import cv2
import numpy as np

from app.develop import colour, colorops as co, settings as S

AUTO_LONG = 256
WB_LONG = 256
SOG_P = 6.0
GREY_LIMITS = (0.35, 0.25, 0.16, 0.12, 0.12)
GREY_MIN = 0.01
BRIGHT_PCT = 40.0
WB_PULL = 0.85
WB_MIX = (0.5, 0.25, 0.25)
MID_TARGET = 0.46
EV_PULL = 0.65
EV_MAX = 2.0
WHITE_TARGET = 0.955
BLACK_TARGET = 0.03
WB_RANGE = (-40.0, 40.0)
BK_RANGE = (-40.0, 25.0)
CHROMA_TARGET = 0.065


def _small(img: np.ndarray, long: int) -> np.ndarray:
    a = np.ascontiguousarray(np.asarray(img, np.float32)[..., :3])
    h, w = a.shape[:2]
    k = long / max(h, w)
    if k < 1.0:
        a = cv2.resize(a, (max(8, int(round(w * k))), max(8, int(round(h * k)))), interpolation=cv2.INTER_AREA)
    return np.maximum(a, 0.0)


def _temp_tint(e: np.ndarray, info: dict) -> tuple[float, float]:
    shot = (float(info.get("asShotTemp", 6500.0) or 6500.0), float(info.get("asShotTint", 0.0) or 0.0))
    e = np.asarray(e, np.float64)
    if not np.all(np.isfinite(e)) or np.any(e <= 0):
        return shot
    xy_shot = colour.temp_tint_to_xy(*shot)
    xyz = colour.bradford(colour.D65, xy_shot) @ colour.to_xyz("rec2020") @ e
    s = float(xyz.sum())
    if s <= 0:
        return shot
    t, tint = colour.xy_to_temp_tint(float(xyz[0] / s), float(xyz[1] / s))
    return float(round(min(max(t, 2000.0), 50000.0))), float(round(min(max(tint, -150.0), 150.0)))


def _illuminant(img: np.ndarray) -> np.ndarray | None:
    edge = _grey_edge(img)
    px = img.reshape(-1, 3).astype(np.float64)
    mx = px.max(axis=1)
    if len(px) < 16 or mx.max() <= 0:
        return None
    y = px @ colour.LUMA_2020
    clip = np.percentile(mx, 99.9)
    ok = (mx < 0.95 * clip) & (y > np.percentile(y, 2)) & (y > 1e-5)
    if ok.sum() < 16:
        return None
    p = px[ok]
    sog = np.power(np.mean(np.power(p, SOG_P), axis=0), 1.0 / SOG_P)
    if np.any(sog <= 0):
        return None
    sog = sog / float(sog @ colour.LUMA_2020)
    if edge is None:
        edge = sog
    yw = y[ok]
    bright = yw >= np.percentile(yw, BRIGHT_PCT)
    e = np.ones(3)
    found = False
    for limit in GREY_LIMITS:
        q = p / e
        lr, lb = np.log(np.maximum(q[:, 0], 1e-9) / np.maximum(q[:, 1], 1e-9)), np.log(np.maximum(q[:, 2], 1e-9) / np.maximum(q[:, 1], 1e-9))
        d = np.hypot(lr, lb)
        grey = (d < limit) & bright
        if grey.mean() < GREY_MIN:
            break
        w = yw[grey] * (1.0 - d[grey] / limit)
        g = np.sum(p[grey] * w[:, None], axis=0) / max(float(w.sum()), 1e-12)
        if np.any(g <= 0):
            break
        e = g / float(g @ colour.LUMA_2020)
        found = True
    if not found:
        e = 0.5 * (np.ones(3) + sog)
    e = np.exp(WB_MIX[0] * np.log(np.maximum(e, 1e-6)) + WB_MIX[1] * np.log(sog) + WB_MIX[2] * np.log(edge))
    e = np.power(np.maximum(e, 1e-6), WB_PULL)
    return e / max(float(e @ colour.LUMA_2020), 1e-12)


def _grey_edge(img: np.ndarray) -> np.ndarray | None:
    sm = cv2.GaussianBlur(np.ascontiguousarray(img, np.float32), (0, 0), 1.0)
    gx = cv2.Sobel(sm, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(sm, cv2.CV_32F, 0, 1)
    g = np.sqrt(gx * gx + gy * gy).reshape(-1, 3).astype(np.float64)
    e = np.power(np.mean(np.power(g, SOG_P), axis=0), 1.0 / SOG_P)
    if np.any(e <= 0) or not np.all(np.isfinite(e)):
        return None
    return e / float(e @ colour.LUMA_2020)


def auto_wb(img: np.ndarray, info: dict) -> tuple[float, float]:
    e = _illuminant(_small(img, WB_LONG))
    if e is None:
        return float(info.get("asShotTemp", 6500.0) or 6500.0), float(info.get("asShotTint", 0.0) or 0.0)
    return _temp_tint(e, info)


def pick_wb(img: np.ndarray, info: dict, dev: dict, x: float, y: float, patch) -> tuple[float, float]:
    from app.develop.render import effective_wb
    try:
        px = np.asarray(patch(x, y), np.float64).reshape(-1, 3)
    except (TypeError, ValueError):
        px = np.zeros((0, 3))
    px = px[np.all(np.isfinite(px), axis=1) & np.all(px > 0, axis=1)]
    if len(px) == 0:
        return effective_wb(img, info, dev)
    e = np.median(px, axis=0)
    return _temp_tint(e, info)


def _render(lin: np.ndarray, info: dict, dev: dict, cache: dict) -> np.ndarray:
    from app.develop import kernel, planes
    h, w = lin.shape[:2]
    ppl = float(max(h, w))
    pl = planes.build(cache, lin, dev, ppl)
    return kernel.best_finish()(lin, pl, dev, None, info, w, h, ppl, [], "srgb")


def _luma(e: np.ndarray) -> np.ndarray:
    return e @ np.array([0.2126, 0.7152, 0.0722], np.float32)


def _base_dev(dev: dict) -> dict:
    out = S.merge(dev, {})
    for sec in ("light", "color"):
        out.pop(sec, None)
    out.pop("masks", None)
    out["detail"] = {}
    out.pop("vignette", None)
    out.pop("grain", None)
    return out


def _with(base: dict, vals: dict) -> dict:
    out = S.merge(base, {})
    for cid, v in vals.items():
        S.put(out, cid, v)
    return out


def _solve(fn, lo: float, hi: float, target: float, iters: int = 9) -> float:
    flo, fhi = fn(lo), fn(hi)
    if (flo - target) * (fhi - target) > 0:
        return lo if abs(flo - target) < abs(fhi - target) else hi
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        fm = fn(mid)
        if (fm - target) * (flo - target) <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return 0.5 * (lo + hi)


def _prepared(img: np.ndarray, info: dict, dev: dict) -> np.ndarray:
    from app.develop import render
    small = _small(img, AUTO_LONG)
    return np.ascontiguousarray(render.white_balance(small, info, dev, full=img), np.float32)


def auto_tone(img: np.ndarray, info: dict, dev: dict) -> dict:
    eff_in = dev or {}
    try:
        from app.develop import profiles
        eff_in = profiles.effective(S.sanitize(eff_in), info)
    except (ImportError, KeyError, ValueError):
        pass
    lin = _prepared(img, info, eff_in)
    base = _base_dev(eff_in)
    cache: dict = {}
    vals: dict = {}

    def med(ev: float) -> float:
        return float(np.median(_luma(_render(lin, info, _with(base, {**vals, "light.exposure": ev}), cache))))
    ev = _solve(med, -4.0, 4.0, MID_TARGET, 8) * EV_PULL
    vals["light.exposure"] = round(min(max(ev, -EV_MAX), EV_MAX), 2)
    e0 = _render(lin, info, _with(base, vals), cache)
    l0 = _luma(e0)
    y = np.maximum(lin @ colour.LUMA_2020, 1e-7) * 2.0 ** vals["light.exposure"]
    v = np.log2(y)
    dr = float(np.percentile(v, 99.5) - np.percentile(v, 1.0))
    bright = float(np.mean(l0 > 0.92))
    dark = float(np.mean(l0 < 0.12))
    hl = -min(max(18.0 + 9.0 * (dr - 7.0) + 250.0 * max(bright - 0.01, 0.0), 0.0), 80.0) if bright > 0.002 else 0.0
    sh = min(max(8.0 + 9.0 * (dr - 7.0) + 120.0 * max(dark - 0.08, 0.0), 0.0), 70.0) if dark > 0.01 else 0.0
    vals["light.highlights"] = int(round(hl))
    vals["light.shadows"] = int(round(sh))

    def top(w: float) -> float:
        return float(np.percentile(_luma(_render(lin, info, _with(base, {**vals, "light.whites": w}), cache)), 99.5))
    vals["light.whites"] = int(round(_solve(top, WB_RANGE[0], WB_RANGE[1], WHITE_TARGET, 6)))

    def bottom(b: float) -> float:
        return float(np.percentile(_luma(_render(lin, info, _with(base, {**vals, "light.blacks": b}), cache)), 0.5))
    vals["light.blacks"] = int(round(_solve(bottom, BK_RANGE[0], BK_RANGE[1], BLACK_TARGET, 6)))
    e2 = _render(lin, info, _with(base, vals), cache)
    l2 = _luma(e2)
    spread = float(np.percentile(l2, 75) - np.percentile(l2, 25))
    vals["light.contrast"] = int(round(min(max((0.26 - spread) * 100.0, -10.0), 15.0)))
    lab = co.to_lab(colour.srgb_decode(e2) @ (colour.from_xyz("rec2020") @ colour.to_xyz("srgb")).T.astype(np.float32))
    chroma = float(np.mean(np.hypot(lab[..., 1], lab[..., 2])))
    vib = min(max((CHROMA_TARGET - chroma) / 0.04 * 30.0, 0.0), 30.0)
    vals["color.vibrance"] = int(round(vib))
    vals["color.saturation"] = int(round(min(vib * 0.2, 6.0)))
    out: dict = {}
    for cid, val in vals.items():
        S.put(out, cid, val)
    return out


def auto_bw(img: np.ndarray, info: dict, dev: dict) -> dict:
    lin = _prepared(img, info, dev or {})
    base = _base_dev(dev or {})
    base.pop("treatment", None)
    base.pop("bw", None)
    for k in ("light", "color"):
        if isinstance((dev or {}).get(k), dict):
            base[k] = dict(dev[k])
    e = _render(lin, info, base, {})
    lab = co.to_lab(colour.srgb_decode(e) @ (colour.from_xyz("rec2020") @ colour.to_xyz("srgb")).T.astype(np.float32)).reshape(-1, 3)
    C = np.hypot(lab[:, 1], lab[:, 2])
    wts = co.band_weights(co.atan2f(lab[:, 2], lab[:, 1])) * (C * C / (C * C + co.C0 * co.C0))[:, None]
    total = wts.sum(axis=0)
    share = total / max(float(total.sum()), 1e-9)
    Lb = (wts * lab[:, :1]).sum(axis=0) / np.maximum(total, 1e-9)
    dom = [k for k in range(8) if share[k] >= 0.04]
    mix = {b: 0 for b in S.BANDS}
    if len(dom) >= 1:
        warm = {0: 3, 1: 4, 2: 5, 3: 1, 4: 0, 5: -2, 6: -1, 7: 2}
        order = sorted(dom, key=lambda k: (Lb[k] + 0.01 * warm[k]))
        lo, hi = float(min(Lb[dom])), float(max(Lb[dom]))
        centre = 0.5 * (lo + hi)
        span = max(hi - lo, 0.0) * 1.2 + 0.12 * max(len(dom) - 1, 1)
        for i, k in enumerate(order):
            t = centre + span * ((i / (len(order) - 1) - 0.5) if len(order) > 1 else 0.0)
            if len(order) == 1:
                t = Lb[k] * (1.08 if warm[k] > 2 else 0.92)
            stops = 3.0 * math.log2(max(t, 0.02) / max(float(Lb[k]), 0.02))
            mix[S.BANDS[k]] = int(round(min(max(stops / co.BW_STOPS * 100.0, -70.0), 70.0)))
    return {"bw": mix}
