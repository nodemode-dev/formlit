import hashlib
import json
import logging
import math
import threading
import weakref
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from numba import njit

from app.core import config
from app.develop import colour
from app.develop.geometry import Frame

log = logging.getLogger("formlit.masks")

BITMAP_KINDS = ("subject", "sky", "background", "object", "people", "landscape")
BITMAP_ENTRIES = 16
RANGE_L_WEIGHT = 0.5
RANGE_TOL = 0.04
RANGE_TOL_OCTAVES = 2.0
RANGE_CORE = 0.35
REFINE_SIGMA = 0.05
REFINE_EPS = (4e-3, 2e-4)
REFINE_PASSES = 2
EDGE_SHIFT_MAX = 0.02
EDGE_FEATHER_MAX = 0.03
EDGE_WORK_RADIUS = 16
DAB_SPACING = 0.12
DAB_MIN_SPACING = 0.3
DAB_TURN = math.radians(10.0)
DAB_LIMIT = 200_000
AUTO_TOL = (0.05, 0.10)
AUTO_L_WEIGHT = 1.0
AUTO_SMOOTH = 0.08
AUTO_EPS = 2e-3
GUIDED_DETAIL = 8.0
GUIDED_FAST_DETAIL = 3.0
GAUSS_TRUNCATE = 4.0
STROKE = {"size": 0.03, "feather": 50.0, "flow": 100.0, "density": 100.0}
MEMO_ENTRIES = 6

_memo: "OrderedDict[str, tuple]" = OrderedDict()
_memo_lock = threading.Lock()


def _memo_key(*parts) -> str:
    return hashlib.sha1(json.dumps(parts, separators=(",", ":"), default=str).encode()).hexdigest()


def _memo_get(key: str, lin: np.ndarray | None) -> np.ndarray | None:
    with _memo_lock:
        hit = _memo.get(key)
        if hit is None or (hit[0] is not None and hit[0]() is not lin):
            return None
        _memo.move_to_end(key)
        return hit[1]


def _memo_put(key: str, lin: np.ndarray | None, arr: np.ndarray) -> np.ndarray:
    arr.setflags(write=False)
    with _memo_lock:
        _memo[key] = (weakref.ref(lin) if lin is not None else None, arr)
        _memo.move_to_end(key)
        while len(_memo) > MEMO_ENTRIES:
            _memo.popitem(last=False)
    return arr


def tonemap_for_select(c: np.ndarray) -> np.ndarray:
    t = np.asarray(np.maximum(np.asarray(c, np.float32), np.float32(0.0)))
    np.negative(t, out=t)
    np.exp(t, out=t)
    np.subtract(np.float32(1.0), t, out=t)
    return t


def bitmap_path(photo_id: int, key: str) -> Path:
    return config.masks_dir() / str(photo_id) / f"{key}.png"


@lru_cache(maxsize=BITMAP_ENTRIES)
def _read_bitmap(path: str, mtime: int, size: int) -> np.ndarray | None:
    raw = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if raw is None or raw.size == 0:
        return None
    if raw.ndim == 3:
        raw = raw[..., 2] if raw.shape[2] >= 3 else raw[..., 0]
    if raw.dtype == np.uint8:
        v = raw.astype(np.float32) / 255.0
    elif raw.dtype == np.uint16:
        v = raw.astype(np.float32) / 65535.0
    else:
        v = np.nan_to_num(raw.astype(np.float32))
    v = np.ascontiguousarray(v)
    v.setflags(write=False)
    return v


def _plane(c, x0: int, y0: int, bw: int, bh: int) -> np.ndarray:
    xs = np.arange(x0, x0 + bw, dtype=np.float32) * np.float32(c[0])
    ys = np.arange(y0, y0 + bh, dtype=np.float32) * np.float32(c[1])
    return ys[:, None] + (xs + np.float32(c[2]))[None, :]


def outline_fill(polys, bw: int, bh: int) -> np.ndarray:
    out = np.zeros((bh * 2, bw * 2), np.uint8)
    pts = [np.round(np.asarray(p, np.float64)[:, :2] * [bw * 2, bh * 2] - 0.5).astype(np.int32) for p in polys or [] if len(p) >= 3]
    if pts:
        cv2.fillPoly(out, pts, 255, cv2.LINE_AA)
    return cv2.resize(out, (bw, bh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0


def _outlined(bm: np.ndarray, outline: dict) -> np.ndarray:
    bh, bw = bm.shape
    edit, orig = outline_fill(outline.get("edit"), bw, bh), outline_fill(outline.get("orig"), bw, bh)
    return np.maximum(bm * (1.0 - np.maximum(orig - edit, 0.0)), np.maximum(edit - orig, 0.0)).astype(np.float32)


def _bitmap(photo_id: int | None, key, frame: Frame, w: int, h: int, outline: dict | None = None) -> np.ndarray | None:
    if photo_id is None or not key or not isinstance(key, str):
        return None
    try:
        p = bitmap_path(photo_id, key)
        st = p.stat()
    except (OSError, ValueError):
        return None
    bm = _read_bitmap(str(p), st.st_mtime_ns, st.st_size)
    if bm is None:
        return None
    if isinstance(outline, dict) and outline.get("sig") == st.st_size:
        bm = _outlined(bm, outline)
    bh, bw = bm.shape
    m = np.asarray(frame.out_to_norm(w, h), np.float64)
    to_bm = np.array([[bw, 0.0, -0.5], [0.0, bh, -0.5], [0.0, 0.0, 1.0]]) @ m @ np.array([[1.0, 0.0, 0.5], [0.0, 1.0, 0.5], [0.0, 0.0, 1.0]])
    out = cv2.warpAffine(bm, to_bm[:2], (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
    corners = m @ np.array([[0.0, w, 0.0, w], [0.0, 0.0, h, h], [1.0, 1.0, 1.0, 1.0]])
    if corners[:2].min() < 0.0 or corners[:2].max() > 1.0:
        c = m.copy()
        c[:2, 2] += 0.5 * (c[:2, 0] + c[:2, 1])
        nx, ny = _plane(c[0], 0, 0, w, h), _plane(c[1], 0, 0, w, h)
        out = np.where((nx >= 0.0) & (nx <= 1.0) & (ny >= 0.0) & (ny <= 1.0), out, np.float32(0.0))
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def load_bitmap(photo_id: int | None, key, frame: Frame, w: int, h: int, outline: dict | None = None) -> np.ndarray:
    got = _bitmap(photo_id, key, frame, w, h, outline)
    return got if got is not None else np.zeros((h, w), np.float32)


def guided_cross(guide: np.ndarray, p: np.ndarray, sigma: float, eps: float) -> np.ndarray:
    return _guided(guide, p, sigma, eps, GUIDED_DETAIL)


def _guided(guide: np.ndarray, p: np.ndarray, sigma: float, eps: float, detail: float) -> np.ndarray:
    i_full = np.asarray(guide, np.float32)
    p = np.asarray(p, np.float32)
    sigma = float(sigma)
    if sigma <= 0.0:
        return np.clip(p, 0.0, 1.0)
    h, w = i_full.shape[:2]
    step = math.floor(sigma / detail)
    if step > 1:
        sw, sh = max(1, round(w / step)), max(1, round(h / step))
        i_low = cv2.resize(i_full, (sw, sh), interpolation=cv2.INTER_AREA)
        p = cv2.resize(p, (sw, sh), interpolation=cv2.INTER_AREA)
        sigma *= sw / w
    else:
        i_low = i_full

    k = 2 * math.ceil(GAUSS_TRUNCATE * sigma) + 1

    def blur(x: np.ndarray) -> np.ndarray:
        return cv2.GaussianBlur(x, (k, k), sigma, borderType=cv2.BORDER_REFLECT)

    mi, mp = blur(i_low), blur(p)
    t = np.multiply(i_low, i_low)
    var = blur(t)
    np.multiply(i_low, p, out=t)
    cov = blur(t)
    np.multiply(mi, mi, out=t)
    var -= t
    np.multiply(mi, mp, out=t)
    cov -= t
    np.maximum(var, 0.0, out=var)
    var += np.float32(eps)
    cov /= var
    np.multiply(cov, mi, out=t)
    mp -= t
    ma, mb = blur(cov), blur(mp)
    if step > 1:
        ma = cv2.resize(ma, (w, h), interpolation=cv2.INTER_LINEAR)
        mb = cv2.resize(mb, (w, h), interpolation=cv2.INTER_LINEAR)
    ma *= i_full
    ma += mb
    return np.clip(ma, 0.0, 1.0, out=ma)


def _smooth(t: np.ndarray) -> np.ndarray:
    t = np.clip(t, 0.0, 1.0)
    return (t * t * (3.0 - 2.0 * t)).astype(np.float32)


def _iso(frame: Frame, w: int, h: int) -> np.ndarray:
    m = np.asarray(frame.out_to_norm(w, h), np.float64)[:2].copy()
    long = max(float(frame.ow), float(frame.oh))
    m[0] *= float(frame.ow) / long
    m[1] *= float(frame.oh) / long
    m[:, 2] += 0.5 * (m[:, 0] + m[:, 1])
    return m


def _iso_point(frame: Frame, p) -> np.ndarray:
    long = max(float(frame.ow), float(frame.oh))
    return np.array([float(p[0]) * float(frame.ow) / long, float(p[1]) * float(frame.oh) / long])


def _box(centre: np.ndarray, ext: np.ndarray, w: int, h: int) -> tuple[int, int, int, int] | None:
    x0, y0 = max(0, math.floor(centre[0] - ext[0])), max(0, math.floor(centre[1] - ext[1]))
    x1, y1 = min(w, math.ceil(centre[0] + ext[0]) + 1), min(h, math.ceil(centre[1] + ext[1]) + 1)
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


class _Ctx:
    def __init__(self, frame: Frame, w: int, h: int, lin: np.ndarray, ev: float, photo_id: int | None) -> None:
        self.frame, self.w, self.h, self.lin, self.ev, self.photo_id = frame, w, h, lin, ev, photo_id
        self.iso = _iso(frame, w, h)
        self.sig = [np.asarray(frame.out_to_norm(w, h), np.float64).tolist(), float(frame.ow), float(frame.oh), w, h]
        self._lab: np.ndarray | None = None

    def zeros(self) -> np.ndarray:
        return np.zeros((self.h, self.w), np.float32)

    def lab(self) -> np.ndarray:
        if self._lab is None:
            key = _memo_key("lab", self.ev, self.lin.shape)
            self._lab = _memo_get(key, self.lin)
            if self._lab is None:
                self._lab = _memo_put(key, self.lin, colour.oklab_from_2020(tonemap_for_select(self.lin * np.float32(2.0 ** self.ev))))
        return self._lab


def _linear(s: dict, ctx: _Ctx) -> np.ndarray:
    a, b = _iso_point(ctx.frame, s["start"]), _iso_point(ctx.frame, s["end"])
    d = b - a
    n2 = float(d @ d)
    if n2 < 1e-14:
        return ctx.zeros()
    c = (d @ ctx.iso) / n2
    c[2] -= float(a @ d) / n2
    return 1.0 - _smooth(_plane(c, 0, 0, ctx.w, ctx.h))


def _radial(s: dict, ctx: _Ctx) -> np.ndarray:
    centre = _iso_point(ctx.frame, s["center"])
    rx, ry = max(float(s["rx"]), 1e-6), max(float(s["ry"]), 1e-6)
    t = math.radians(float(s.get("angle", 0.0) or 0.0))
    rot = np.array([[math.cos(t), math.sin(t)], [-math.sin(t), math.cos(t)]])
    m = rot @ ctx.iso
    m[:, 2] -= rot @ centre
    m[0] /= rx
    m[1] /= ry
    feather = min(max(float(s.get("feather", 50.0)), 0.0), 100.0) / 100.0
    aa = max(math.hypot(m[0, 0], m[1, 0]), math.hypot(m[0, 1], m[1, 1]))
    lo, hi = 1.0 - feather, 1.0
    if hi - lo < aa:
        lo, hi = 1.0 - 0.5 * aa, 1.0 + 0.5 * aa
    inv = np.linalg.inv(m[:, :2])
    out = ctx.zeros()
    box = _box(-inv @ m[:, 2], np.sqrt((inv * inv).sum(axis=1)) * hi + 1.0, ctx.w, ctx.h)
    if box is not None:
        x0, y0, x1, y1 = box
        u, v = _plane(m[0], x0, y0, x1 - x0, y1 - y0), _plane(m[1], x0, y0, x1 - x0, y1 - y0)
        out[y0:y1, x0:x1] = _smooth((hi - np.sqrt(u * u + v * v)) / (hi - lo))
    return 1.0 - out if s.get("invert") else out


def _edge(x: np.ndarray, feather: float) -> np.ndarray:
    return _smooth(x / feather + 1.0) if feather > 1e-6 else (x >= 0.0).astype(np.float32)


def _band(v: np.ndarray, lo: float, hi: float, lo_feather: float, hi_feather: float) -> np.ndarray:
    return np.minimum(_edge(v - lo, max(lo_feather, 0.0)), _edge(hi - v, max(hi_feather, 0.0)))


def _luminance_range(s: dict, ctx: _Ctx) -> np.ndarray:
    lo, hi = sorted((float(s.get("lo", 0.0)), float(s.get("hi", 1.0))))
    return _band(ctx.lab()[..., 0], lo, hi, float(s.get("loFeather", 0.0)), float(s.get("hiFeather", 0.0)))


def edge_strength(lum: np.ndarray, detail: float = 50.0) -> np.ndarray:
    import cv2
    scale = max(lum.shape) / 1000.0
    sigma = max(0.5, (2.5 - 2.0 * min(max(detail, 0.0), 100.0) / 100.0) * scale)
    y = cv2.GaussianBlur(lum.astype(np.float32), (0, 0), sigma)
    mag = np.hypot(cv2.Sobel(y, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(y, cv2.CV_32F, 0, 1, ksize=3))
    ref = float(np.percentile(mag, 99.0))
    e = np.clip(mag / max(ref, 1e-6), 0.0, 1.0)
    return cv2.GaussianBlur(e, (0, 0), max(0.6, sigma)).astype(np.float32)


def _edge_range(s: dict, ctx: _Ctx) -> np.ndarray:
    lo, hi = sorted((float(s.get("lo", 0.35)), float(s.get("hi", 1.0))))
    e = edge_strength(ctx.lab()[..., 0], float(s.get("detail", 0.5)) * 100.0)
    out = _band(e, lo, hi, float(s.get("loFeather", 0.1)), float(s.get("hiFeather", 0.0)))
    return 1.0 - out if s.get("invert") else out


def _color_range(s: dict, ctx: _Ctx) -> np.ndarray:
    samples = np.asarray(s.get("samples") or [], np.float64)
    if samples.size == 0:
        return ctx.zeros()
    if samples.ndim != 2 or samples.shape[1] < 3 or not np.isfinite(samples).all():
        raise ValueError("colour range samples must be [L, a, b] triples")
    refine = min(max(float(s.get("refine", 50.0)), 0.0), 100.0)
    tol = RANGE_TOL * 2.0 ** (RANGE_TOL_OCTAVES * (refine - 50.0) / 50.0)
    lab = ctx.lab()
    best = None
    for l0, a0, b0 in samples[:, :3]:
        dl = (lab[..., 0] - np.float32(l0)) * np.float32(RANGE_L_WEIGHT)
        da, db = lab[..., 1] - np.float32(a0), lab[..., 2] - np.float32(b0)
        d2 = dl * dl + da * da + db * db
        best = d2 if best is None else np.minimum(best, d2)
    inner = RANGE_CORE * tol
    return 1.0 - _smooth((np.sqrt(best) - inner) / (tol - inner))


def _depth_range(s: dict, ctx: _Ctx) -> np.ndarray:
    depth = _bitmap(ctx.photo_id, s.get("bitmap") or "depth", ctx.frame, ctx.w, ctx.h)
    if depth is None:
        return ctx.zeros()
    lo, hi = sorted((float(s.get("lo", 0.0)), float(s.get("hi", 1.0))))
    f = float(s.get("feather", 0.0))
    return _band(depth, lo, hi, f, f)


def _scaled(cov: np.ndarray, radius: float, op) -> np.ndarray:
    h, w = cov.shape
    f = max(1.0, radius / EDGE_WORK_RADIUS)
    if f <= 1.0:
        return op(np.ascontiguousarray(cov, np.float32), radius)
    sw, sh = max(1, round(w / f)), max(1, round(h / f))
    small = cv2.resize(cov, (sw, sh), interpolation=cv2.INTER_AREA)
    return cv2.resize(op(small, radius / f), (w, h), interpolation=cv2.INTER_LINEAR)


def _edges(cov: np.ndarray, s: dict, ctx: _Ctx) -> np.ndarray:
    refine = min(max(float(s.get("refine", 0) or 0), 0.0), 100.0)
    shift = min(max(float(s.get("shift", 0) or 0), -100.0), 100.0)
    feather = min(max(float(s.get("feather", 0) or 0), 0.0), 100.0)
    if refine <= 0 and abs(shift) < 0.5 and feather < 0.5:
        return cov
    if refine > 0:
        cov = _refine(cov, refine, ctx)
    px = float(ctx.frame.px_per_long(ctx.w))
    r = abs(shift) / 100.0 * EDGE_SHIFT_MAX * px
    if r >= 0.75:
        def morph(a: np.ndarray, rad: float) -> np.ndarray:
            k = max(1, int(round(rad)))
            el = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1))
            return (cv2.dilate if shift > 0 else cv2.erode)(a, el)
        cov = _scaled(cov, r, morph)
    sigma = feather / 100.0 * EDGE_FEATHER_MAX * px
    if sigma >= 0.3:
        def blur(a: np.ndarray, sg: float) -> np.ndarray:
            k = 2 * math.ceil(GAUSS_TRUNCATE * sg) + 1
            return cv2.GaussianBlur(a, (k, k), sg, borderType=cv2.BORDER_REFLECT)
        cov = _scaled(cov, sigma, blur)
    return np.clip(cov, 0.0, 1.0).astype(np.float32)


def _coverage(s: dict, ctx: _Ctx) -> np.ndarray:
    kind = s.get("kind")
    if kind == "linear":
        return _linear(s, ctx)
    if kind == "radial":
        return _radial(s, ctx)
    if kind == "brush":
        return _brush_cached(s.get("strokes") or [], ctx)
    if kind == "luminanceRange":
        return _luminance_range(s, ctx)
    if kind == "colorRange":
        return _color_range(s, ctx)
    if kind == "depthRange":
        return _depth_range(s, ctx)
    if kind == "edgeRange":
        return _edge_range(s, ctx)
    if kind in BITMAP_KINDS:
        return _edges(load_bitmap(ctx.photo_id, s.get("bitmap"), ctx.frame, ctx.w, ctx.h, s.get("outline")), s, ctx)
    return ctx.zeros()


def _refine(alpha: np.ndarray, refine: float, ctx: _Ctx) -> np.ndarray:
    k = min(max(refine / 100.0, 0.0), 1.0)
    if k <= 0.0:
        return alpha
    sigma = max(1.0, REFINE_SIGMA * k * float(ctx.frame.px_per_long(ctx.w)))
    eps = REFINE_EPS[0] * (REFINE_EPS[1] / REFINE_EPS[0]) ** k
    snapped = alpha
    for _ in range(REFINE_PASSES):
        snapped = _guided(ctx.lab()[..., 0], snapped, sigma, eps, GUIDED_FAST_DETAIL)
    return alpha + (snapped - alpha) * np.float32(min(1.0, 2.0 * k))


def _alpha(m: dict, comps: list, ctx: _Ctx) -> np.ndarray:
    alpha = None
    for c in comps:
        if not isinstance(c, dict) or not isinstance(c.get("shape"), dict):
            raise ValueError("component without a shape")
        cov = _coverage(c["shape"], ctx)
        if c.get("invert"):
            cov = 1.0 - cov
        op = c.get("op", "add")
        if op == "refine":
            if alpha is not None:
                alpha = alpha + (_refine(alpha, 100.0, ctx) - alpha) * cov
            continue
        if alpha is None:
            alpha = np.array(cov, np.float32)
        elif op == "subtract":
            alpha *= 1.0 - cov
        elif op == "intersect":
            alpha *= cov
        else:
            np.maximum(alpha, cov, out=alpha)
    refine = float(m.get("refine", 0) or 0)
    if refine > 0:
        alpha = _refine(alpha, refine, ctx)
    if m.get("invert"):
        alpha = 1.0 - alpha
    return np.ascontiguousarray(np.clip(alpha, 0.0, 1.0), np.float32)


def evaluate(dev: dict, frame: Frame, w: int, h: int, lin: np.ndarray, ev: float, photo_id: int | None) -> list:
    masks = dev.get("masks") if isinstance(dev, dict) else None
    if not isinstance(masks, list):
        return []
    ctx = _Ctx(frame, w, h, lin, float(ev or 0.0), photo_id)
    out = []
    for m in masks:
        if not isinstance(m, dict) or not m.get("visible", True):
            continue
        comps = m.get("components")
        if not isinstance(comps, list) or not comps:
            continue
        try:
            mid = int(m.get("id", 0) or 0)
            alpha = _alpha(m, comps, ctx)
        except Exception as exc:
            log.warning("mask %r skipped: %s", m.get("id"), exc)
            continue
        out.append((alpha, m, mid))
    return out


@njit(cache=True)
def _paint(buf, foot, ox, oy, cx, cy, g11, g12, g22, hy, r, core, aa, a, lab, auto, tol0, tol1, lw):
    bh, bw = buf.shape
    if r - core < aa:
        lo, hi = r - 0.5 * aa, r + 0.5 * aa
    else:
        lo, hi = core, r
    inv = 1.0 / (hi - lo)
    lo2, hi2 = lo * lo, hi * hi
    for k in range(cx.shape[0]):
        y0 = max(int(np.floor(cy[k] - hy)) - oy, 0)
        y1 = min(int(np.ceil(cy[k] + hy)) - oy + 1, bh)
        ak = a[k]
        l0 = 0.0
        a0 = 0.0
        b0 = 0.0
        if auto:
            ix = min(max(int(np.floor(cx[k] + 0.5)) - ox, 0), bw - 1)
            iy = min(max(int(np.floor(cy[k] + 0.5)) - oy, 0), bh - 1)
            l0, a0, b0 = lab[iy, ix, 0], lab[iy, ix, 1], lab[iy, ix, 2]
        for y in range(y0, y1):
            dy = y + oy - cy[k]
            disc = g12 * g12 * dy * dy - g11 * (g22 * dy * dy - hi2)
            if disc <= 0.0:
                continue
            sq = np.sqrt(disc)
            x0 = max(int(np.ceil(cx[k] + (-g12 * dy - sq) / g11)) - ox, 0)
            x1 = min(int(np.floor(cx[k] + (-g12 * dy + sq) / g11)) - ox + 1, bw)
            cyy = g22 * dy * dy
            cxy = 2.0 * g12 * dy
            for x in range(x0, x1):
                dx = x + ox - cx[k]
                d2 = g11 * dx * dx + cxy * dx + cyy
                if d2 <= lo2:
                    p = 1.0
                elif d2 >= hi2:
                    continue
                else:
                    t = (hi - np.sqrt(d2)) * inv
                    p = t * t * (3.0 - 2.0 * t)
                if auto:
                    if p > foot[y, x]:
                        foot[y, x] = p
                    el = (lab[y, x, 0] - l0) * lw
                    ea = lab[y, x, 1] - a0
                    eb = lab[y, x, 2] - b0
                    e = np.sqrt(el * el + ea * ea + eb * eb)
                    if e >= tol1:
                        continue
                    if e > tol0:
                        t = (tol1 - e) / (tol1 - tol0)
                        p *= t * t * (3.0 - 2.0 * t)
                cur = buf[y, x]
                if p > cur:
                    buf[y, x] = cur + (p - cur) * ak


def _stroke(st, frame: Frame) -> tuple | None:
    if not isinstance(st, dict):
        raise ValueError("stroke is not an object")
    pts = np.asarray(st.get("points") or [], np.float64)
    if pts.size == 0:
        return None
    if pts.ndim != 2 or pts.shape[1] < 2 or not np.isfinite(pts[:, :2]).all():
        raise ValueError("stroke points must be [x, y] pairs")
    long = max(float(frame.ow), float(frame.oh))
    pts = pts[:, :2] * np.array([float(frame.ow) / long, float(frame.oh) / long])
    r = max(float(st.get("size", STROKE["size"])), 1e-6)
    feather = min(max(float(st.get("feather", STROKE["feather"])), 0.0), 100.0) / 100.0
    flow = min(max(float(st.get("flow", STROKE["flow"])), 1.0), 100.0) / 100.0
    density = min(max(float(st.get("density", STROKE["density"])), 0.0), 100.0) / 100.0
    return pts, r, r * (1.0 - feather), flow, density, bool(st.get("erase")), bool(st.get("auto") or st.get("autoMask")), bool(st.get("snap"))


def _snap(buf: np.ndarray, rgb: np.ndarray, band: int) -> np.ndarray:
    seeds = np.zeros(buf.shape, np.int32)
    seeds[buf <= 0.02] = 1
    seeds[buf >= 0.9 * float(buf.max())] = 2
    if not (seeds == 1).any() or not (seeds == 2).any():
        return buf
    cv2.watershed(np.ascontiguousarray((np.clip(rgb, 0.0, 1.0) * 255.0).astype(np.uint8)[..., ::-1]), seeds)
    hard = (seeds == 2).astype(np.float32)
    hard = np.minimum(cv2.GaussianBlur(hard, (0, 0), 0.8) * float(buf.max()), (buf > 0.0).astype(np.float32))
    k = 2 * max(1, band) + 1
    y = cv2.GaussianBlur(np.ascontiguousarray(rgb.mean(axis=2), np.float32), (0, 0), 1.0)
    mag = np.hypot(cv2.Sobel(y, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(y, cv2.CV_32F, 0, 1, ksize=3)) / 8.0
    near = np.clip((cv2.dilate(mag, np.ones((k, k), np.uint8)) - 0.01) / 0.03, 0.0, 1.0)
    return (buf * (1.0 - near) + hard * near).astype(np.float32)


def _dabs(pts: np.ndarray, r: float, flow: float, aa: float) -> tuple[np.ndarray, np.ndarray]:
    seg = np.hypot(*np.diff(pts, axis=0).T) if len(pts) > 1 else np.zeros(0)
    keep = np.concatenate([[True], seg > 1e-12])
    pts, seg = pts[keep], seg[seg > 1e-12]
    total = float(seg.sum())
    if total <= 0.0:
        return pts[:1], np.array([flow])
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    n = min(DAB_LIMIT, math.ceil(total / max(DAB_SPACING * r, DAB_MIN_SPACING * aa)) + 1)
    heading = np.arctan2(*np.diff(pts, axis=0).T[::-1])
    turn = np.abs((np.diff(heading) + math.pi) % (2.0 * math.pi) - math.pi)
    at = np.union1d(np.linspace(0.0, total, n), cum[1:-1][turn > DAB_TURN][:DAB_LIMIT])
    at = at[np.concatenate([[True], np.diff(at) > 1e-12])]
    centres = np.stack([np.interp(at, cum, pts[:, 0]), np.interp(at, cum, pts[:, 1])], axis=1)
    gaps = np.diff(at)
    share = 0.5 * (np.concatenate([[0.0], gaps]) + np.concatenate([gaps, [0.0]]))
    alpha = 1.0 - (1.0 - flow) ** (share / (2.0 * r))
    alpha[0] = max(alpha[0], flow)
    return centres, alpha


def _brush(strokes, frame: Frame, w: int, h: int, img: np.ndarray | None, gain: float, strict: bool, start: np.ndarray | None = None) -> np.ndarray:
    if not isinstance(strokes, list):
        raise ValueError("strokes must be a list")
    out = np.array(start, np.float32) if start is not None else np.zeros((h, w), np.float32)
    if not strokes:
        return out
    iso = _iso(frame, w, h)
    inv = np.linalg.inv(iso[:, :2])
    g = iso[:, :2].T @ iso[:, :2]
    ext = np.sqrt((inv * inv).sum(axis=1))
    aa = math.sqrt(abs(float(np.linalg.det(iso[:, :2]))))
    none = np.zeros((1, 1, 3), np.float32)
    for st in strokes:
        try:
            parsed = _stroke(st, frame)
        except (TypeError, ValueError) as exc:
            if strict:
                raise
            log.warning("brush stroke skipped: %s", exc)
            continue
        if parsed is None:
            continue
        pts, r, core, flow, density, erase, auto, snap = parsed
        centres, a = _dabs(pts, r, flow, aa)
        px = (centres - iso[:, 2]) @ inv.T
        reach = ext * (r + aa) + 1.0
        lo, hi = px.min(axis=0), px.max(axis=0)
        box = _box(0.5 * (lo + hi), 0.5 * (hi - lo) + reach, w, h)
        if box is None:
            continue
        x0, y0, x1, y1 = box
        auto = auto and img is not None
        lab = np.ascontiguousarray(colour.oklab_from_2020(tonemap_for_select(img[y0:y1, x0:x1] * np.float32(gain)))) if auto else none
        buf = np.zeros((y1 - y0, x1 - x0), np.float32)
        foot = np.zeros_like(buf)
        _paint(buf, foot, x0, y0, np.ascontiguousarray(px[:, 0]), np.ascontiguousarray(px[:, 1]), float(g[0, 0]), float(g[0, 1]), float(g[1, 1]),
               float(reach[1]), r, core, aa, a, lab, auto, AUTO_TOL[0], AUTO_TOL[1], AUTO_L_WEIGHT)
        if auto:
            buf = np.minimum(_guided(lab[..., 0], buf, max(1.0, AUTO_SMOOTH * r / aa), AUTO_EPS, GUIDED_FAST_DETAIL), foot)
        if snap and img is not None:
            buf = _snap(buf, tonemap_for_select(img[y0:y1, x0:x1] * np.float32(gain)), int((r - core) / aa))
        view = out[y0:y1, x0:x1]
        if erase:
            view *= 1.0 - np.float32(density) * buf
        else:
            view += (1.0 - view) * (np.float32(density) * buf)
    return out


def _brush_key(strokes: list, ctx: _Ctx) -> tuple[str, np.ndarray | None]:
    auto = any(isinstance(st, dict) and (st.get("auto") or st.get("autoMask") or st.get("snap")) for st in strokes)
    return _memo_key("brush", strokes, ctx.sig, ctx.ev if auto else 0.0), ctx.lin if auto else None


def _brush_cached(strokes, ctx: _Ctx) -> np.ndarray:
    if not isinstance(strokes, list):
        raise ValueError("strokes must be a list")
    key, lin = _brush_key(strokes, ctx)
    hit = _memo_get(key, lin)
    if hit is not None:
        return hit
    base = _memo_get(*_brush_key(strokes[:-1], ctx)) if len(strokes) > 1 else None
    todo = strokes if base is None else strokes[-1:]
    return _memo_put(key, lin, _brush(todo, ctx.frame, ctx.w, ctx.h, ctx.lin, 2.0 ** ctx.ev, True, base))


def rasterize_brush(strokes, frame: Frame, w: int, h: int, img: np.ndarray | None, *_) -> np.ndarray:
    return _brush(strokes if isinstance(strokes, list) else [], frame, w, h, img, 1.0, False)


__all__ = ["evaluate", "tonemap_for_select", "bitmap_path", "load_bitmap", "rasterize_brush", "guided_cross"]
