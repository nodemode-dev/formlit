import math

import cv2
import numpy as np

from app.develop.geometry import FOCAL, camera, rot_z

DEFAULT_FOCAL = FOCAL
MIN_LENGTH = 0.025
MIN_CONTRAST = 10.0
EDGE_OFFSET = 2.0
EDGE_SAMPLES = 24
EDGE_SHARE = 0.9
MAX_SEGMENTS = 400
BORDER = 3.0
AXIS_WINDOW = 20.0
HIST_STEP = 0.05
HIST_SIGMA = 0.25
PEAK_WINDOW = 0.75
PEAK_SHARE = 0.2
MIN_LEVEL = 0.2
VP_WINDOW = 30.0
INLIER = 1.5
RANSAC_TRIES = 400
MIN_EVIDENCE = 0.5
MIN_LINES = 4
VP_SHARE = 0.35
VP_SPREAD = 0.2
VP_BAND = 0.4
VP_CONC = 0.9
FLAT_RMS = 1.0
INF_RATIO = 1.25
VP_TILT = 25.0
STRONG_EVIDENCE = 1.5
MAX_ANGLE = 40.0
AUTO_MAX = 25.0
AUTO_EXTRA = 15.0
GUIDE_STEPS = 30
EMPTY = np.zeros((0, 4), np.float64)


def _detect(g: np.ndarray) -> np.ndarray:
    try:
        found = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD).detect(g)[0]
        return np.zeros((0, 4)) if found is None else found.reshape(-1, 4).astype(np.float64) + 0.5
    except (AttributeError, cv2.error):
        edges = cv2.Canny(cv2.GaussianBlur(g, (0, 0), 1.0), 40, 120)
        long = max(g.shape)
        found = cv2.HoughLinesP(edges, 1, np.pi / 720, 40, minLineLength=max(8, int(MIN_LENGTH * long)), maxLineGap=3)
        return np.zeros((0, 4)) if found is None else found.reshape(-1, 4).astype(np.float64) + 0.5


def _edge_ok(g: np.ndarray, s: np.ndarray) -> np.ndarray:
    h, w = g.shape
    d = s[:, 2:] - s[:, :2]
    n = np.stack([-d[:, 1], d[:, 0]], 1) / np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-9)[:, None] * EDGE_OFFSET
    t = np.linspace(0.05, 0.95, EDGE_SAMPLES)
    px = s[:, None, 0] - 0.5 + d[:, None, 0] * t[None, :]
    py = s[:, None, 1] - 0.5 + d[:, None, 1] * t[None, :]

    def at(x: np.ndarray, y: np.ndarray) -> np.ndarray:
        return g[np.clip(np.rint(y), 0, h - 1).astype(np.intp), np.clip(np.rint(x), 0, w - 1).astype(np.intp)].astype(np.float64)
    diff = at(px + n[:, None, 0], py + n[:, None, 1]) - at(px - n[:, None, 0], py - n[:, None, 1])
    sign = np.sign(np.median(diff, 1))[:, None]
    along = np.mean(diff * sign >= MIN_CONTRAST / 2.0, 1)
    return (np.abs(np.median(diff, 1)) >= MIN_CONTRAST) & (along >= EDGE_SHARE)


def segments(gray8: np.ndarray) -> np.ndarray:
    g = np.asarray(gray8)
    if g.ndim == 3:
        g = cv2.cvtColor(g[..., :3].astype(np.uint8), cv2.COLOR_RGB2GRAY)
    g = np.ascontiguousarray(g if g.dtype == np.uint8 else np.clip(g, 0, 255).astype(np.uint8))
    h, w = g.shape[:2]
    if h < 8 or w < 8:
        return EMPTY.copy()
    s = _detect(g)
    if not len(s):
        return EMPTY.copy()
    length = np.hypot(s[:, 2] - s[:, 0], s[:, 3] - s[:, 1])
    xs, ys = s[:, [0, 2]], s[:, [1, 3]]
    edge = (np.all(xs < BORDER, 1) | np.all(xs > w - BORDER, 1) | np.all(ys < BORDER, 1) | np.all(ys > h - BORDER, 1))
    keep = (length >= MIN_LENGTH * max(w, h)) & ~edge
    s, length = s[keep], length[keep]
    if len(s):
        keep = _edge_ok(g, s)
        s, length = s[keep], length[keep]
    if not len(s):
        return EMPTY.copy()
    s = s[np.argsort(-length, kind="stable")[:MAX_SEGMENTS]]
    half = max(w, h) / 2.0
    return np.stack([(s[:, 0] - w / 2.0) / half, (s[:, 1] - h / 2.0) / half, (s[:, 2] - w / 2.0) / half, (s[:, 3] - h / 2.0) / half], 1)


def _clean(seg) -> np.ndarray:
    s = np.asarray(seg, np.float64).reshape(-1, 4) if seg is not None and np.size(seg) else EMPTY
    s = s[np.all(np.isfinite(s), 1)]
    return s[np.hypot(s[:, 2] - s[:, 0], s[:, 3] - s[:, 1]) > 1e-9]


def _deviations(s: np.ndarray, kind: str) -> tuple[np.ndarray, np.ndarray]:
    dx, dy = s[:, 2] - s[:, 0], s[:, 3] - s[:, 1]
    t = np.degrees(np.arctan2(dy, dx)) % 180.0
    dev = t - 90.0 if kind == "v" else np.where(t < 90.0, t, t - 180.0)
    return dev, np.hypot(dx, dy)


def straighten_angle(seg) -> float:
    s = _clean(seg)
    if not len(s):
        return 0.0
    devs, wts = [], []
    for kind in ("h", "v"):
        dev, length = _deviations(s, kind)
        near = np.abs(dev) <= AXIS_WINDOW
        devs.append(dev[near])
        wts.append(length[near])
    dev, wt = np.concatenate(devs), np.concatenate(wts)
    if wt.sum() < MIN_LEVEL:
        return 0.0
    bins = int(round(2 * AXIS_WINDOW / HIST_STEP)) + 1
    hist = np.bincount(np.clip(np.round((dev + AXIS_WINDOW) / HIST_STEP).astype(np.intp), 0, bins - 1), wt, bins)
    k = int(math.ceil(4 * HIST_SIGMA / HIST_STEP))
    kern = np.exp(-0.5 * (np.arange(-k, k + 1) * HIST_STEP / HIST_SIGMA) ** 2)
    peak = int(np.argmax(np.convolve(hist, kern, "same"))) * HIST_STEP - AXIS_WINDOW
    near = np.abs(dev - peak) <= PEAK_WINDOW
    if wt[near].sum() < MIN_LEVEL or wt[near].sum() < PEAK_SHARE * wt.sum():
        return 0.0
    return float(np.average(dev[near], weights=wt[near]))


def _rodrigues(axis: np.ndarray, angle: float) -> np.ndarray:
    return cv2.Rodrigues(np.asarray(axis, np.float64).reshape(3, 1) * angle)[0]


def _angle(r: np.ndarray) -> float:
    return float(np.linalg.norm(cv2.Rodrigues(np.asarray(r, np.float64))[0]))


def _scaled(r: np.ndarray, s: float) -> np.ndarray:
    return cv2.Rodrigues(cv2.Rodrigues(np.asarray(r, np.float64))[0] * s)[0]


def _align(d: np.ndarray, target: np.ndarray) -> np.ndarray:
    d = d / np.linalg.norm(d)
    axis = np.cross(d, target)
    s, c = float(np.linalg.norm(axis)), float(np.dot(d, target))
    if s < 1e-12:
        return np.eye(3)
    return _rodrigues(axis / s, math.atan2(s, c))


def _frame(dv: np.ndarray, dh: np.ndarray) -> np.ndarray:
    r2 = dv / np.linalg.norm(dv)
    r1 = dh - np.dot(dh, r2) * r2
    r1 /= np.linalg.norm(r1)
    return np.stack([r1, r2, np.cross(r1, r2)])


def _normals(s: np.ndarray, f: float) -> np.ndarray:
    p1 = np.stack([s[:, 0] / f, s[:, 1] / f, np.ones(len(s))], 1)
    p2 = np.stack([s[:, 2] / f, s[:, 3] / f, np.ones(len(s))], 1)
    n = np.cross(p1, p2)
    return n / np.linalg.norm(n, axis=1, keepdims=True)


def _residual(d: np.ndarray, mid: np.ndarray, dirs: np.ndarray, f: float) -> np.ndarray:
    d = np.atleast_2d(d)
    gx = f * d[:, 0:1] - d[:, 2:3] * mid[None, :, 0]
    gy = f * d[:, 1:2] - d[:, 2:3] * mid[None, :, 1]
    norm = np.hypot(gx, gy)
    res = np.abs(dirs[None, :, 0] * gy - dirs[None, :, 1] * gx) / np.maximum(norm, 1e-12)
    return np.where(norm < 1e-9, 1.0, res)


def _vp(s: np.ndarray, kind: str, f: float) -> tuple[np.ndarray, float] | None:
    dev, length = _deviations(s, kind)
    sel = np.abs(dev) <= VP_WINDOW
    if sel.sum() < MIN_LINES:
        return None
    s, wt = s[sel], length[sel]
    axis = 1 if kind == "v" else 0
    n = _normals(s, f)
    mid = (s[:, :2] + s[:, 2:]) / 2.0
    dirs = (s[:, 2:] - s[:, :2]) / wt[:, None]
    dirs *= np.where(dirs[:, axis] < 0, -1.0, 1.0)[:, None]
    k = len(s)
    rng = np.random.default_rng(0)
    prob = wt / wt.sum()
    i, j = rng.choice(k, RANSAC_TRIES, p=prob), rng.choice(k, RANSAC_TRIES, p=prob)
    cand = np.cross(n[i[i != j]], n[j[i != j]])
    norm = np.linalg.norm(cand, axis=1)
    cand = cand[norm > 1e-9] / norm[norm > 1e-9, None]
    if not len(cand):
        return None
    lim = math.sin(math.radians(INLIER))
    inl = _residual(cand, mid, dirs, f) < lim
    best = int(np.argmax(inl @ wt))
    mask, d, vals = inl[best], cand[best], np.zeros(3)
    for _ in range(3):
        if mask.sum() < 2:
            return None
        vals, vecs = np.linalg.eigh((n[mask] * wt[mask, None]).T @ n[mask])
        d = vecs[:, 0]
        mask = _residual(d, mid, dirs, f)[0] < lim
    weight = float(wt[mask].sum())
    if weight < MIN_EVIDENCE or mask.sum() < MIN_LINES or weight < VP_SHARE * wt.sum():
        return None
    w = wt[mask]
    u = np.average(dirs[mask], axis=0, weights=w)
    flat = np.array([u[0], u[1], 0.0])
    across = mid[mask, 1 - axis]
    spread = math.sqrt(max(float(np.average((across - np.average(across, weights=w)) ** 2, weights=w)), 0.0))
    conc = float(((np.abs(across[:, None] - across[None, :]) <= VP_BAND / 2.0) @ w).max()) / weight

    def rms(v: np.ndarray) -> float:
        return math.degrees(math.sqrt(float(np.average(np.minimum(_residual(v, mid[mask], dirs[mask], f)[0], 1.0) ** 2, weights=w))))
    flat_rms = rms(flat)
    if vals[1] < 1e-4 * weight:
        d = flat
    elif spread < VP_SPREAD or conc > VP_CONC:
        if flat_rms > FLAT_RMS:
            return None
        d = flat
    elif flat_rms <= INF_RATIO * rms(d):
        d = flat
    if math.degrees(math.atan2(abs(d[1 - axis]), abs(d[axis]))) > VP_TILT:
        return None
    return (d if d[axis] > 0 else -d) / np.linalg.norm(d), weight


def _rotation(s: np.ndarray, mode: str, f: float) -> np.ndarray | None:
    ey, ex = np.array([0.0, 1.0, 0.0]), np.array([1.0, 0.0, 0.0])
    vert = _vp(s, "v", f)
    hor = _vp(s, "h", f) if mode in ("full", "auto") else None
    if mode == "auto" and hor is not None and hor[1] < STRONG_EVIDENCE:
        hor = None
    if vert is None and hor is None:
        return None
    if vert is None:
        return _align(hor[0], ex) if mode == "full" else None
    r = _align(vert[0], ey)
    if hor is not None:
        both = _frame(vert[0], hor[0])
        if mode == "full" or _angle(both @ r.T) <= math.radians(AUTO_EXTRA):
            r = both
    limit = math.radians(AUTO_MAX if mode == "auto" else MAX_ANGLE)
    a = _angle(r)
    return _scaled(r, limit / a) if a > limit else r


def _level(s: np.ndarray, strength: float) -> np.ndarray:
    return rot_z(math.radians(-straighten_angle(s) * strength))


def upright(seg, mode: str, focal: float = DEFAULT_FOCAL, strength: float = 1.0) -> np.ndarray:
    s = _clean(seg)
    k = min(max(float(strength), 0.0), 1.0)
    if not len(s) or k == 0.0 or mode not in ("level", "vertical", "full", "auto"):
        return np.eye(3)
    if mode == "level":
        return _level(s, k)
    r = _rotation(s, mode, float(focal))
    if r is None:
        return _level(s, k)
    return camera(_scaled(r, k), float(focal))


def guided(guides) -> np.ndarray:
    g = _clean(guides)[:4]
    if not len(g):
        return np.eye(3)
    dx, dy = g[:, 2] - g[:, 0], g[:, 3] - g[:, 1]
    vertical = np.abs(dy) > np.abs(dx)
    if len(g) == 1:
        dev = _deviations(g, "v" if vertical[0] else "h")[0][0]
        return rot_z(math.radians(-dev))
    f = DEFAULT_FOCAL
    n = _normals(g, f)
    targets = np.where(vertical[:, None], np.array([[0.0, 1.0, 0.0]]), np.array([[1.0, 0.0, 0.0]]))
    r = np.eye(3)
    for _ in range(GUIDE_STEPS):
        m = n @ r.T
        res = np.sum(m * targets, 1)
        if np.max(np.abs(res)) < 1e-12:
            break
        jac = np.cross(m, targets)
        step = np.linalg.lstsq(jac, -res, rcond=None)[0]
        if not np.all(np.isfinite(step)):
            break
        r = cv2.Rodrigues(step.reshape(3, 1))[0] @ r
        if np.linalg.norm(step) < 1e-12:
            break
    return camera(r, f)
