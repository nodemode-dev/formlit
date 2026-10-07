import json
import logging
import math
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from numba import njit

from app.core import config
from app.develop import colour
from app.develop.geometry import Frame

log = logging.getLogger("formlit.retouch")

SPOT = {"size": 0.02, "feather": 50.0, "opacity": 100.0}
HEAL_EPS = 0.02
HEAL_EPS_MIN = 1e-5
HEAL_BLUR = 0.08
HEAL_BLUR_RANGE = (0.6, 2.0)
SOR_OMEGA = 1.6
SOR_ITERS = 24
SOR_COARSE_ITERS = 200
COARSEST = 6
PATCH_ENTRIES = 8
SOURCE_RES = 6.0
SOURCE_REACH = 5.0
SOURCE_WIDEN = (1.0, 2.0, 4.0)
SOURCE_LEVEL_SAMPLES = 4096
SOURCE_GAP = 2.2
SOURCE_RING = (1.1, 1.9)
SOURCE_INTERIOR = 1.0
SOURCE_DISTANCE = 0.03
RED_STOPS = (0.9, 2.0)
GLOW_STOPS = (0.8, 1.8)
GLINT_STOPS = (1.0, 2.5)
EYE_PRIOR = 0.35
PUPIL_SCALE = (0.6, 1.5)
PUPIL_EDGE = 0.25
PUPIL_SPREAD = 0.12
DARKEN_MAX = 0.85
PET_LEVEL = 0.35
CATCHLIGHT_OFFSET = 0.3
CATCHLIGHT_SIZE = 0.14
CATCHLIGHT_LEVEL = 1.0
CATCHLIGHT_OPACITY = 0.9


def _smooth(t: np.ndarray) -> np.ndarray:
    t = np.clip(t, 0.0, 1.0)
    return (t * t * (3.0 - 2.0 * t)).astype(np.float32)


def _points(raw, to_out: np.ndarray) -> np.ndarray | None:
    pts = np.asarray(raw if raw is not None else [], np.float64)
    if pts.size == 0:
        return None
    if pts.ndim != 2 or pts.shape[1] < 2 or not np.isfinite(pts[:, :2]).all():
        raise ValueError("points must be [x, y] pairs")
    return pts[:, :2] @ to_out[:2, :2].T + to_out[:2, 2] - 0.5


def _box(lo, hi, pad: float, w: int, h: int) -> tuple[int, int, int, int] | None:
    x0, y0 = max(0, math.floor(lo[0] - pad)), max(0, math.floor(lo[1] - pad))
    x1, y1 = min(w, math.ceil(hi[0] + pad) + 1), min(h, math.ceil(hi[1] + pad) + 1)
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


@njit(cache=True)
def _sweep(dist, ox, oy, px, py, reach):
    bh, bw = dist.shape
    n = px.shape[0]
    for k in range(max(n - 1, 1)):
        ax, ay = px[k], py[k]
        j = min(k + 1, n - 1)
        bx, by = px[j], py[j]
        vx, vy = bx - ax, by - ay
        vv = vx * vx + vy * vy
        x0 = max(int(np.floor(min(ax, bx) - reach)) - ox, 0)
        x1 = min(int(np.ceil(max(ax, bx) + reach)) - ox + 1, bw)
        y0 = max(int(np.floor(min(ay, by) - reach)) - oy, 0)
        y1 = min(int(np.ceil(max(ay, by) + reach)) - oy + 1, bh)
        for y in range(y0, y1):
            wy = y + oy - ay
            for x in range(x0, x1):
                wx = x + ox - ax
                t = (wx * vx + wy * vy) / vv if vv > 0.0 else 0.0
                t = min(max(t, 0.0), 1.0)
                ex, ey = wx - t * vx, wy - t * vy
                d = np.sqrt(ex * ex + ey * ey)
                if d < dist[y, x]:
                    dist[y, x] = d


def _shape(pts: np.ndarray, r: float, feather: float, box: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = box
    dist = np.full((y1 - y0, x1 - x0), np.inf, np.float32)
    _sweep(dist, x0, y0, np.ascontiguousarray(pts[:, 0]), np.ascontiguousarray(pts[:, 1]), r + 1.0)
    lo, hi = r * (1.0 - feather), r
    if hi - lo < 1.0:
        lo, hi = r - 0.5, r + 0.5
    return _smooth((hi - dist) / (hi - lo))


def _reflect(i: np.ndarray, n: int) -> np.ndarray:
    if n == 1:
        return np.zeros_like(i)
    i = np.mod(i, 2 * (n - 1))
    return np.where(i >= n, 2 * (n - 1) - i, i)


def _shifted(img: np.ndarray, box: tuple[int, int, int, int], dx: float, dy: float) -> np.ndarray:
    h, w = img.shape[:2]
    x0, y0, x1, y1 = box
    dx = float(round(dx)) if abs(dx - round(dx)) < 1e-6 else dx
    dy = float(round(dy)) if abs(dy - round(dy)) < 1e-6 else dy
    ix, iy = math.floor(dx), math.floor(dy)
    fx, fy = np.float32(dx - ix), np.float32(dy - iy)
    xs, ys = np.arange(x0, x1) + ix, np.arange(y0, y1) + iy

    def row(yi: np.ndarray) -> np.ndarray:
        rows = img[_reflect(yi, h)]
        out = rows[:, _reflect(xs, w)]
        return out if fx == 0 else out * (1 - fx) + rows[:, _reflect(xs + 1, w)] * fx

    top = row(ys)
    return top if fy == 0 else top * (1 - fy) + row(ys + 1) * fy


@njit(cache=True)
def _relax(m, known, iters, omega):
    h, w, c = m.shape
    acc = np.zeros(c)
    for _ in range(iters):
        for parity in range(2):
            for y in range(h):
                for x in range((y + parity) & 1, w, 2):
                    if known[y, x]:
                        continue
                    n = 0
                    acc[:] = 0.0
                    if y > 0:
                        n += 1
                        for ch in range(c):
                            acc[ch] += m[y - 1, x, ch]
                    if y < h - 1:
                        n += 1
                        for ch in range(c):
                            acc[ch] += m[y + 1, x, ch]
                    if x > 0:
                        n += 1
                        for ch in range(c):
                            acc[ch] += m[y, x - 1, ch]
                    if x < w - 1:
                        n += 1
                        for ch in range(c):
                            acc[ch] += m[y, x + 1, ch]
                    if n == 0:
                        continue
                    for ch in range(c):
                        m[y, x, ch] += omega * (acc[ch] / n - m[y, x, ch])


def _down(m: np.ndarray, known: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    h, w, c = m.shape
    ph, pw = h + h % 2, w + w % 2
    vals = np.zeros((ph, pw, c), np.float32)
    cnt = np.zeros((ph, pw), np.float32)
    vals[:h, :w] = m * known[..., None]
    cnt[:h, :w] = known
    s = vals.reshape(ph // 2, 2, pw // 2, 2, c).sum(axis=(1, 3))
    n = cnt.reshape(ph // 2, 2, pw // 2, 2).sum(axis=(1, 3))
    return (s / np.maximum(n, 1.0)[..., None]).astype(np.float32), n > 0


def _membrane(d: np.ndarray, known: np.ndarray) -> np.ndarray:
    levels = [(np.array(d, np.float32), known)]
    while max(levels[-1][1].shape) > COARSEST and not levels[-1][1].all():
        levels.append(_down(*levels[-1]))
    m, k = levels[-1]
    if not k.any():
        return np.zeros_like(levels[0][0])
    m = m.copy()
    m[~k] = m[k].mean(axis=0)
    _relax(m, k, SOR_COARSE_ITERS, SOR_OMEGA)
    for fm, fk in reversed(levels[:-1]):
        h, w = fk.shape
        up = cv2.resize(m, (w + w % 2, h + h % 2), interpolation=cv2.INTER_LINEAR)[:h, :w].reshape(h, w, -1)
        fm = fm.copy()
        fm[~fk] = up[~fk]
        _relax(fm, fk, SOR_ITERS, SOR_OMEGA)
        m = fm
    return m


def _heal(tgt: np.ndarray, src: np.ndarray, inside: np.ndarray, r: float) -> np.ndarray:
    known = ~inside
    if not known.any():
        return src
    t, s = np.maximum(tgt, 0.0), np.maximum(src, 0.0)
    sigma = min(max(HEAL_BLUR * r, HEAL_BLUR_RANGE[0]), HEAL_BLUR_RANGE[1])
    kf = known.astype(np.float32)
    norm = np.maximum(cv2.GaussianBlur(kf, (0, 0), sigma), 1e-6)[..., None]
    tb = cv2.GaussianBlur(t * kf[..., None], (0, 0), sigma) / norm
    sb = cv2.GaussianBlur(s * kf[..., None], (0, 0), sigma) / norm
    ring = known & (cv2.dilate(inside.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0)
    eps = max(HEAL_EPS_MIN, HEAL_EPS * float(tb[ring].mean())) if ring.any() else HEAL_EPS_MIN
    diff = np.log(tb + eps) - np.log(sb + eps)
    diff[inside] = 0.0
    return np.maximum((s + eps) * np.exp(_membrane(diff, known)) - eps, 0.0).astype(np.float32)


@lru_cache(maxsize=PATCH_ENTRIES)
def _read_patch(path: str, mtime: int, meta: str, meta_mtime: int) -> tuple[np.ndarray, tuple] | None:
    try:
        arr = np.load(path, allow_pickle=False)
        rect = [float(v) for v in json.loads(Path(meta).read_text(encoding="utf-8"))["rect"]]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.warning("remove patch %s unreadable: %s", path, exc)
        return None
    arr = np.asarray(arr, np.float32)
    if arr.ndim != 3 or arr.shape[2] not in (3, 4) or min(arr.shape[:2]) < 1:
        return None
    if len(rect) != 4 or not all(math.isfinite(v) for v in rect) or rect[2] <= rect[0] or rect[3] <= rect[1]:
        return None
    arr = np.ascontiguousarray(np.nan_to_num(arr))
    arr.setflags(write=False)
    return arr, tuple(rect)


def _patch(key) -> tuple[np.ndarray, tuple] | None:
    if not isinstance(key, str) or not key or ".." in Path(key).parts or Path(key).is_absolute():
        return None
    p = config.masks_dir() / f"{key}.npy"
    meta = p.with_suffix(".json")
    try:
        st, sm = p.stat(), meta.stat()
    except OSError:
        return None
    return _read_patch(str(p), st.st_mtime_ns, str(meta), sm.st_mtime_ns)


def _remove(out: np.ndarray, s: dict, pts: np.ndarray, r: float, feather: float, opacity: float, to_out: np.ndarray) -> None:
    got = _patch(s.get("patch"))
    if got is None:
        return
    arr, (nx0, ny0, nx1, ny1) = got
    h, w = out.shape[:2]
    ph, pw = arr.shape[:2]
    corners = (to_out @ np.array([[nx0, nx1, nx0, nx1], [ny0, ny0, ny1, ny1], [1.0, 1.0, 1.0, 1.0]]))[:2] - 0.5
    detect = bool(s.get("detect")) and arr.shape[2] == 4
    lo, hi = corners.min(axis=1), corners.max(axis=1)
    if not detect:
        lo, hi = np.maximum(lo, pts.min(axis=0) - r - 1.0), np.minimum(hi, pts.max(axis=0) + r + 1.0)
    box = _box(lo, hi, 1.0, w, h)
    if box is None:
        return
    x0, y0, x1, y1 = box
    to_patch = np.array([[pw / (nx1 - nx0), 0.0, -nx0 * pw / (nx1 - nx0) - 0.5], [0.0, ph / (ny1 - ny0), -ny0 * ph / (ny1 - ny0) - 0.5], [0.0, 0.0, 1.0]])
    m = (to_patch @ np.linalg.inv(to_out) @ np.array([[1.0, 0.0, x0 + 0.5], [0.0, 1.0, y0 + 0.5], [0.0, 0.0, 1.0]]))[:2]
    size = (x1 - x0, y1 - y0)
    fill = cv2.warpAffine(arr, m, size, flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE).reshape(y1 - y0, x1 - x0, -1)
    cover = cv2.warpAffine(np.ones((ph, pw), np.float32), m, size, flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_CONSTANT, borderValue=0.0)
    a = np.clip(fill[..., 3], 0.0, 1.0) * cover if detect else _shape(pts, r, feather, box) * cover
    tgt = out[y0:y1, x0:x1]
    out[y0:y1, x0:x1] = tgt + (fill[..., :3] - tgt) * (a * np.float32(opacity))[..., None]


def _source(s: dict, out: np.ndarray, pts: np.ndarray, r: float, to_out: np.ndarray) -> tuple[float, float]:
    src = s.get("source")
    if isinstance(src, (list, tuple)) and len(src) >= 2 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in src[:2]):
        d = to_out[:2, :2] @ np.array([float(src[0]), float(src[1])])
        return float(d[0]), float(d[1])
    return _find_source(out, pts, r)


def _spot(out: np.ndarray, s: dict, to_out: np.ndarray, ppl: float) -> None:
    pts = _points(s.get("points"), to_out)
    if pts is None:
        return
    h, w = out.shape[:2]
    r = max(0.5, float(s.get("size", SPOT["size"])) * ppl)
    feather = min(max(float(s.get("feather", SPOT["feather"])), 0.0), 100.0) / 100.0
    opacity = min(max(float(s.get("opacity", SPOT["opacity"])), 0.0), 100.0) / 100.0
    if opacity <= 0.0:
        return
    mode = s.get("mode", "heal")
    if mode == "remove":
        _remove(out, s, pts, r, feather, opacity, to_out)
        return
    sigma = min(max(HEAL_BLUR * r, HEAL_BLUR_RANGE[0]), HEAL_BLUR_RANGE[1])
    box = _box(pts.min(axis=0), pts.max(axis=0), r + 3.0 + math.ceil(3.0 * sigma), w, h)
    if box is None:
        return
    x0, y0, x1, y1 = box
    alpha = _shape(pts, r, feather, box)
    inside = alpha > 0.0
    if not inside.any():
        return
    dx, dy = _source(s, out, pts, r, to_out)
    src = _shifted(out, box, dx, dy)
    tgt = out[y0:y1, x0:x1]
    fill = src if mode == "clone" else _heal(tgt, src, inside, r)
    out[y0:y1, x0:x1] = tgt + (fill - tgt) * (alpha * np.float32(opacity))[..., None]


def apply_spots(img: np.ndarray, spots: list, frame: Frame, ppl: float) -> np.ndarray:
    out = np.array(img, np.float32, copy=True)
    if not isinstance(spots, list) or not spots:
        return out
    h, w = out.shape[:2]
    to_out = np.asarray(frame.norm_to_out(w, h), np.float64)
    for s in spots:
        if not isinstance(s, dict) or s.get("hidden"):
            continue
        try:
            _spot(out, s, to_out, float(ppl))
        except Exception as exc:
            log.warning("spot skipped: %s", exc)
    return out


def _search(img: np.ndarray, pts: np.ndarray, r: float, reach: float) -> tuple[float, float] | None:
    h, w = img.shape[:2]
    step = max(1.0, r / SOURCE_RES)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    pad = reach + SOURCE_RING[1] * r + 2.0 * step
    x0, y0 = max(0, math.floor(lo[0] - pad)), max(0, math.floor(lo[1] - pad))
    x1, y1 = min(w, math.ceil(hi[0] + pad) + 1), min(h, math.ceil(hi[1] + pad) + 1)
    if x1 - x0 < 3 or y1 - y0 < 3:
        return None
    win = np.maximum(np.asarray(img[y0:y1, x0:x1, :3], np.float32), 0.0)
    every = max(1, round(math.sqrt(win.shape[0] * win.shape[1] / SOURCE_LEVEL_SAMPLES)))
    enc = np.sqrt(np.minimum(win / max(1e-6, float(np.percentile(win[::every, ::every], 99.5))), 1.0)).astype(np.float32)
    sw, sh = max(3, round((x1 - x0) / step)), max(3, round((y1 - y0) / step))
    small = cv2.resize(enc, (sw, sh), interpolation=cv2.INTER_AREA) if (sw, sh) != (x1 - x0, y1 - y0) else enc
    fx, fy = (x1 - x0) / sw, (y1 - y0) / sh
    sp = np.column_stack([(pts[:, 0] - x0 + 0.5) / fx - 0.5, (pts[:, 1] - y0 + 0.5) / fy - 0.5])
    rs = r / fx
    m = math.ceil(SOURCE_RING[1] * rs) + 1
    tx0, ty0 = math.floor(sp[:, 0].min()) - m, math.floor(sp[:, 1].min()) - m
    tx1, ty1 = math.ceil(sp[:, 0].max()) + m + 1, math.ceil(sp[:, 1].max()) + m + 1
    dist = np.full((ty1 - ty0, tx1 - tx0), np.inf, np.float32)
    _sweep(dist, tx0, ty0, np.ascontiguousarray(sp[:, 0]), np.ascontiguousarray(sp[:, 1]), float(m + 1))
    foot = (dist <= rs).astype(np.float32)
    ring = ((dist >= SOURCE_RING[0] * rs) & (dist <= SOURCE_RING[1] * rs)).astype(np.float32)
    gap = (dist < 0.5 * SOURCE_GAP * rs).astype(np.float32)
    if ring.sum() < 3 or foot.sum() < 1:
        return None
    reach_s = math.ceil(reach / min(fx, fy))
    q = reach_s + m + 2
    padded = cv2.copyMakeBorder(small, q, q, q, q, cv2.BORDER_REFLECT_101)
    tmpl = np.ascontiguousarray(padded[ty0 + q:ty1 + q, tx0 + q:tx1 + q])
    area = np.ascontiguousarray(padded[ty0 + q - reach_s:ty1 + q + reach_s, tx0 + q - reach_s:tx1 + q + reach_s])
    cost = np.maximum(cv2.matchTemplate(area, tmpl, cv2.TM_SQDIFF, mask=ring), 0.0) / (3.0 * ring.sum())
    mu = (tmpl * ring[..., None]).sum(axis=(0, 1)) / ring.sum()
    var = float((((tmpl - mu) ** 2) * ring[..., None]).sum() / (3.0 * ring.sum()))
    flat = np.ascontiguousarray(np.broadcast_to(mu.astype(np.float32), tmpl.shape))
    cost += SOURCE_INTERIOR * np.maximum(np.maximum(cv2.matchTemplate(area, flat, cv2.TM_SQDIFF, mask=foot), 0.0) / (3.0 * foot.sum()) - var, 0.0)
    canvas = np.zeros(area.shape[:2], np.float32)
    canvas[reach_s:reach_s + gap.shape[0], reach_s:reach_s + gap.shape[1]] = gap
    overlap = cv2.matchTemplate(canvas, gap, cv2.TM_CCORR)
    oy, ox = np.mgrid[-reach_s:reach_s + 1, -reach_s:reach_s + 1].astype(np.float64)
    off = np.hypot(ox * fx, oy * fy)
    ok = (overlap < 0.5) & (off <= reach)
    fy0, fx0 = np.nonzero(foot)
    within = ok & (ox + tx0 + fx0.min() >= 0) & (ox + tx0 + fx0.max() < sw) & (oy + ty0 + fy0.min() >= 0) & (oy + ty0 + fy0.max() < sh)
    valid = within if within.any() else ok
    if not valid.any():
        return None
    score = np.where(valid, cost * (1.0 + SOURCE_DISTANCE * np.maximum(off / r - SOURCE_GAP, 0.0)), np.inf)
    j, i = np.unravel_index(int(np.argmin(score)), score.shape)
    return float(round(ox[j, i] * fx)), float(round(oy[j, i] * fy))


def _find_source(img: np.ndarray, pts: np.ndarray, r: float) -> tuple[float, float]:
    r = max(1.0, float(r))
    for widen in SOURCE_WIDEN:
        got = _search(img, pts, r, SOURCE_REACH * r * widen)
        if got is not None:
            return got
    return (SOURCE_GAP * r if float(pts[:, 0].mean()) < img.shape[1] / 2 else -SOURCE_GAP * r), 0.0


def auto_source(img: np.ndarray, target, r: float) -> tuple[float, float]:
    return _find_source(img, np.array([[float(target[0]) - 0.5, float(target[1]) - 0.5]]), r)


def _eye(out: np.ndarray, e: dict, frame: Frame, to_out: np.ndarray, ppl: float) -> None:
    h, w = out.shape[:2]
    ow, oh = float(frame.ow), float(frame.oh)
    long = max(ow, oh)
    cx, cy = float(e["center"][0]), float(e["center"][1])
    rx, ry = max(float(e.get("rx", 0.01)), 1e-5), max(float(e.get("ry", 0.008)), 1e-5)
    m = np.linalg.inv(to_out)[:2].copy()
    m[:, 2] += 0.5 * (m[:, 0] + m[:, 1]) - np.array([cx, cy])
    m[0] *= ow / long / rx
    m[1] *= oh / long / ry
    inv = np.linalg.inv(m[:, :2])
    centre = -inv @ m[:, 2]
    ext = np.sqrt((inv * inv).sum(axis=1)) + 2.0
    box = _box(centre - ext, centre + ext, 0.0, w, h)
    if box is None:
        return
    x0, y0, x1, y1 = box
    gx = np.arange(x0, x1, dtype=np.float32)[None, :]
    gy = np.arange(y0, y1, dtype=np.float32)[:, None]
    u = m[0, 0] * gx + m[0, 1] * gy + np.float32(m[0, 2])
    v = m[1, 0] * gx + m[1, 1] * gy + np.float32(m[1, 2])
    q = np.sqrt(u * u + v * v)
    inside = q < 1.0
    if inside.sum() < 4:
        return
    patch = out[y0:y1, x0:x1]
    rgb = np.maximum(patch, 0.0)
    lum = rgb @ colour.LUMA_2020
    eps = 0.01 * float(np.median(lum[inside])) + 1e-6
    red = _smooth((np.log2((rgb[..., 0] + eps) / (np.maximum(rgb[..., 1], rgb[..., 2]) + eps)) - RED_STOPS[0]) / (RED_STOPS[1] - RED_STOPS[0]))
    pet = bool(e.get("pet"))
    ring = inside & (q > 0.75)
    outer = lum[ring] if ring.sum() >= 4 else lum[inside]
    if pet:
        glow = _smooth((np.log2((lum + eps) / (float(np.median(outer)) + eps)) - GLOW_STOPS[0]) / (GLOW_STOPS[1] - GLOW_STOPS[0]))
        found = np.maximum(red, glow)
    else:
        found = red
    weight = found * _smooth((1.0 - q) / EYE_PRIOR)
    area = float(weight.sum())
    if area < 1.0:
        return
    mx, my = float((weight * gx).sum() / area), float((weight * gy).sum() / area)
    rp = min(math.sqrt(area / math.pi), max(rx, ry) * ppl)
    k = min(max(float(e.get("pupilSize", 50.0)), 0.0), 100.0) / 100.0
    rsel = max(0.75, rp * (PUPIL_SCALE[0] + (PUPIL_SCALE[1] - PUPIL_SCALE[0]) * k))
    dist = np.hypot(gx - mx, gy - my)
    region = _smooth((rsel * (1.0 + PUPIL_EDGE) - dist) / (2.0 * PUPIL_EDGE * rsel)) * _smooth((1.0 - q) / 0.1)
    seen = float((weight * lum).sum() / area)
    glint = _smooth((np.log2((lum + eps) / (seen + eps)) - GLINT_STOPS[0]) / (GLINT_STOPS[1] - GLINT_STOPS[0]))
    spread = np.maximum(found, cv2.GaussianBlur(found, (0, 0), max(0.5, PUPIL_SPREAD * rsel)) * (1.0 - glint))
    corr = (region * spread)[..., None]
    darken = min(max(float(e.get("darken", 50.0)), 0.0), 100.0) / 100.0
    keep = np.float32(1.0 - DARKEN_MAX * darken)
    if pet:
        dark = np.float32(PET_LEVEL * float(np.percentile(outer, 25)))
        fix = np.broadcast_to(dark * keep, rgb.shape)
    else:
        fix = np.repeat((0.5 * (rgb[..., 1] + rgb[..., 2]) * keep)[..., None], 3, axis=2)
    res = patch + (fix - patch) * corr
    light = e.get("catchlight")
    if pet and light:
        if isinstance(light, (list, tuple)) and len(light) >= 2:
            lx, ly = float(light[0]), float(light[1])
        else:
            lx, ly = cx - CATCHLIGHT_OFFSET * rx * long / ow, cy - CATCHLIGHT_OFFSET * ry * long / oh
        lp = to_out @ np.array([lx, ly, 1.0]) - 0.5
        rc = max(0.8, CATCHLIGHT_SIZE * rsel)
        spot = _smooth((1.3 * rc - np.hypot(gx - lp[0], gy - lp[1])) / (0.6 * rc))[..., None] * np.float32(CATCHLIGHT_OPACITY)
        res = res + (np.float32(CATCHLIGHT_LEVEL) - res) * spot
    out[y0:y1, x0:x1] = res


def apply_red_eye(img: np.ndarray, eyes: list, frame: Frame, ppl: float) -> np.ndarray:
    out = np.array(img, np.float32, copy=True)
    if not isinstance(eyes, list) or not eyes:
        return out
    h, w = out.shape[:2]
    to_out = np.asarray(frame.norm_to_out(w, h), np.float64)
    for e in eyes:
        if not isinstance(e, dict):
            continue
        try:
            _eye(out, e, frame, to_out, float(ppl))
        except Exception as exc:
            log.warning("red eye skipped: %s", exc)
    return out


__all__ = ["apply_spots", "auto_source", "apply_red_eye"]
