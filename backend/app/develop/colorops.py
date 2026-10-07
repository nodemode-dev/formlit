import math
from functools import lru_cache

import numpy as np

from app.develop import colour, settings as S

C0 = 0.02
HUE_SHIFT = 0.5
LUM_STOPS = 1.25
BW_STOPS = 1.5
SKIN_HUE = math.radians(58.0)
SKIN_WIDTH = math.radians(24.0)
VIB_CHROMA = 0.16
CAL_HUE = math.radians(18.0)
CAL_SAT = 0.6
SHADOW_TINT = 0.35
LOCAL_MIRED = 90.0
LOCAL_TINT = 50.0
LOCAL_REF = 5000.0
GRADE_TINT = 0.075
GRADE_LUM = 0.12
GRADE_EDGE = 0.18
TINT_LOCAL = 0.09
ATAN = (0.99997726, -0.33262347, 0.19354346, -0.11643287, 0.05265332, -0.01172120)


def fast_cbrt(x: np.ndarray) -> np.ndarray:
    a = np.abs(x)
    r = np.exp2(np.log2(np.maximum(a, 1e-30)) * (1.0 / 3.0))
    return np.where(a < 1e-30, 0.0, np.copysign(r, x)).astype(np.result_type(x, np.float32))


@lru_cache(maxsize=1)
def lab_mats() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    to_lms, from_lms, to_lab, from_lab = colour.oklab_mats()
    return (np.ascontiguousarray(to_lms, np.float32), np.ascontiguousarray(from_lms, np.float32), np.ascontiguousarray(to_lab, np.float32),
            np.ascontiguousarray(from_lab, np.float32))


def to_lab(rgb: np.ndarray) -> np.ndarray:
    m1, _, m2, _ = lab_mats()
    return fast_cbrt(rgb @ m1.T) @ m2.T


def from_lab(lab: np.ndarray, out: np.ndarray | None = None) -> np.ndarray:
    _, i1, _, i2 = lab_mats()
    lms = lab @ i2.T
    return (lms * lms * lms) @ i1.T


def atan2f(y: np.ndarray, x: np.ndarray) -> np.ndarray:
    ax, ay = np.abs(x), np.abs(y)
    big = np.maximum(ax, ay)
    a = np.minimum(ax, ay) / np.maximum(big, 1e-30)
    s = a * a
    r = a * (ATAN[0] + s * (ATAN[1] + s * (ATAN[2] + s * (ATAN[3] + s * (ATAN[4] + s * ATAN[5])))))
    r = np.where(ay > ax, np.pi / 2 - r, r)
    r = np.where(x < 0, np.pi - r, r)
    return np.where(y < 0, -r, r).astype(np.result_type(x, y, np.float32))


@lru_cache(maxsize=1)
def band_centres() -> np.ndarray:
    hues = [float(b["hue"]) for b in S.doc()["mixerBands"]]
    c = np.array([colour.hsv_hue_to_oklch(h) for h in hues], np.float64) % (2 * np.pi)
    return c


@lru_cache(maxsize=1)
def band_table() -> tuple[np.ndarray, np.ndarray]:
    c = band_centres()
    order = np.argsort(c)
    return c[order].astype(np.float64), order.astype(np.int64)


def _segment(h: np.ndarray):
    cs, order = band_table()
    n = len(cs)
    hh = np.mod(h, 2 * np.pi)
    k = np.searchsorted(cs, hh, side="right") - 1
    lo = np.where(k < 0, cs[-1] - 2 * np.pi, cs[np.maximum(k, 0)])
    hi = np.where(k < 0, cs[0], np.where(k + 1 < n, cs[np.minimum(k + 1, n - 1)], cs[0] + 2 * np.pi))
    i0 = order[np.mod(k, n)]
    i1 = order[np.mod(k + 1, n)]
    t = np.clip((hh - lo) / np.maximum(hi - lo, 1e-9), 0.0, 1.0)
    w1 = t * t * (3.0 - 2.0 * t)
    return i0, i1, (1.0 - w1).astype(np.float32), w1.astype(np.float32)


def band_weights(h) -> np.ndarray:
    h = np.asarray(h, np.float64)
    i0, i1, w0, w1 = _segment(h)
    out = np.zeros(h.shape + (8,), np.float32)
    np.put_along_axis(out, i0[..., None], w0[..., None], axis=-1)
    prev = np.take_along_axis(out, i1[..., None], axis=-1)
    np.put_along_axis(out, i1[..., None], prev + w1[..., None], axis=-1)
    return out


def band_shifts() -> np.ndarray:
    c = band_centres()
    n = len(c)
    out = np.zeros((n, 2))
    for k in range(n):
        d = (c - c[k] + np.pi) % (2 * np.pi) - np.pi
        out[k, 0] = np.min(d[d > 1e-6]) if np.any(d > 1e-6) else 0.5
        out[k, 1] = -np.max(d[d < -1e-6]) if np.any(d < -1e-6) else 0.5
    return out


def mixer_table(dev: dict) -> np.ndarray | None:
    if not S.section_enabled(dev, "mixer"):
        return None
    sh = band_shifts()
    tab = np.zeros((8, 3), np.float64)
    for k, band in enumerate(S.BANDS):
        hv = S.get(dev, f"mixer.{band}.hue") / 100.0
        tab[k, 0] = hv * HUE_SHIFT * (sh[k, 0] if hv > 0 else sh[k, 1])
        tab[k, 1] = S.get(dev, f"mixer.{band}.sat") / 100.0
        tab[k, 2] = S.get(dev, f"mixer.{band}.lum") / 100.0 * LUM_STOPS / 3.0
    return tab if np.any(tab) else None


def bw_table(dev: dict) -> np.ndarray:
    tab = np.zeros(8, np.float64)
    if S.section_enabled(dev, "mixer"):
        for k, band in enumerate(S.BANDS):
            tab[k] = S.get(dev, f"bw.{band}") / 100.0 * BW_STOPS / 3.0
    return tab


def _rodrigues(theta: float) -> np.ndarray:
    u = np.ones(3) / np.sqrt(3.0)
    k = np.array([[0, -u[2], u[1]], [u[2], 0, -u[0]], [-u[1], u[0], 0]])
    return np.eye(3) + math.sin(theta) * k + (1 - math.cos(theta)) * (k @ k)


def calibration(dev: dict) -> np.ndarray | None:
    if not S.section_enabled(dev, "calibration"):
        return None
    vals = [(S.get(dev, f"calibration.{p}Hue") / 100.0, S.get(dev, f"calibration.{p}Sat") / 100.0) for p in ("red", "green", "blue")]
    if not any(h or s for h, s in vals):
        return None
    luma = colour.LUMA_2020.astype(np.float64)
    cols = []
    for i, (h, s) in enumerate(vals):
        p = np.eye(3)[i]
        n = np.full(3, luma[i])
        cols.append(n + (1.0 + s * CAL_SAT) * (_rodrigues(h * CAL_HUE) @ (p - n)))
    m = np.stack(cols, axis=1)
    m = m + np.outer(1.0 - m.sum(axis=1), luma)
    return m


def shadow_tint(dev: dict) -> float:
    if not S.section_enabled(dev, "calibration"):
        return 0.0
    return S.get(dev, "calibration.shadowsTint") / 100.0 * SHADOW_TINT


def local_wb(temp: float, tint: float) -> np.ndarray | None:
    if abs(temp) < 1e-6 and abs(tint) < 1e-6:
        return None
    mired = 1e6 / LOCAL_REF - temp * LOCAL_MIRED
    t1 = 1e6 / max(mired, 20.0)
    m = colour.wb_matrix(t1, tint * LOCAL_TINT, LOCAL_REF, 0.0)
    return np.eye(3) if m is None else m.astype(np.float64)


def wheel_dir(deg: float) -> tuple[float, float]:
    h = colour.hsv_hue_to_oklch(float(deg))
    return math.cos(h), math.sin(h)


def grading_table(dev: dict) -> np.ndarray | None:
    if not S.section_enabled(dev, "grading"):
        return None
    tab = np.zeros((4, 3), np.float64)
    for i, r in enumerate(("shadows", "midtones", "highlights", "global")):
        sat = S.get(dev, f"grading.{r}.sat") / 100.0
        ca, sa = wheel_dir(S.get(dev, f"grading.{r}.hue"))
        tab[i] = (sat * GRADE_TINT * ca, sat * GRADE_TINT * sa, S.get(dev, f"grading.{r}.lum") / 100.0 * GRADE_LUM)
    if not np.any(tab):
        return None
    return tab


def grading_shape(dev: dict) -> tuple[float, float, float]:
    blend = S.get(dev, "grading.blending") / 100.0
    bal = S.get(dev, "grading.balance") / 100.0
    width = 0.05 + 0.32 * blend
    return 0.36 - 0.22 * bal, 0.70 - 0.22 * bal, width


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def grading_weights(L: np.ndarray, shape: tuple[float, float, float]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ts, th, wd = shape
    ws = 1.0 - smoothstep(ts - wd, ts + wd, L)
    wh = smoothstep(th - wd, th + wd, L)
    wm = np.maximum(1.0 - ws - wh, 0.0)
    return ws, wm, wh


def tint_envelope(L: np.ndarray) -> np.ndarray:
    return np.clip(L / GRADE_EDGE, 0.0, 1.0) * np.clip((1.0 - L) / GRADE_EDGE, 0.0, 1.0)


def point_table(entries) -> np.ndarray | None:
    rows = []
    for p in entries or []:
        if not isinstance(p, dict):
            continue
        try:
            hue = math.radians(float(p.get("hue", 0.0)))
            chroma, lum = float(p.get("chroma", 0.0)), float(p.get("lum", 0.5))
            hs, ss, ls = (float(p.get(k, 0.0)) / 100.0 for k in ("hueShift", "satShift", "lumShift"))
            var, rng = float(p.get("variance", 0.0)) / 100.0, float(p.get("range", 50.0)) / 100.0
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(v) for v in (hue, chroma, lum, hs, ss, ls, var, rng)):
            continue
        if not (hs or ss or ls or var):
            continue
        rng = min(max(rng, 0.0), 1.0)
        sh = math.radians(8.0 + 40.0 * rng)
        sc = max(0.015, max(chroma, 0.02) * (0.3 + 0.9 * rng))
        sl = 0.06 + 0.30 * rng
        rows.append([hue, max(chroma, 0.0), lum, hs * math.radians(30.0), ss, ls * 1.25 / 3.0, var, sh, sc, sl])
        if len(rows) == 8:
            break
    return np.asarray(rows, np.float64) if rows else None
