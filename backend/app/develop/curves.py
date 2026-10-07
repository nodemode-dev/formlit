from functools import lru_cache

import numpy as np

MID = 0.18
LOG_MID = float(np.log2(MID))
VMIN, VMAX, NV = -20.0, 12.0, 4096
NE = 4096
NP = 1024
PIVOT = 0.4636
GENERIC = ((-11.0, 0.0012), (-9.0, 0.0050), (-8.0, 0.0105), (-7.0, 0.0215), (-6.0, 0.0470), (-5.0, 0.0960), (-4.0, 0.1700),
           (-3.0, 0.2800), (-2.0, 0.4500), (-1.0, 0.6250), (0.0, 0.7650), (1.0, 0.8750), (2.0, 0.9560), (2.9, 0.9930))
SPACE_GAMMA = {"adobergb": 563.0 / 256.0, "prophoto": 1.8}
REGION_GAIN = (0.10, 0.14, 0.14, 0.10)
REGION_MIN = 0.12
SAT_SLOPE = (0.5, 2.5)


def monotone_slopes(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    x = np.asarray(x, np.float64)
    y = np.asarray(y, np.float64)
    n = len(x)
    if n < 2:
        return np.zeros(n)
    d = np.diff(y) / np.maximum(np.diff(x), 1e-12)
    m = np.empty(n)
    m[0], m[-1] = d[0], d[-1]
    m[1:-1] = (d[:-1] + d[1:]) / 2.0
    m[1:-1][d[:-1] * d[1:] <= 0.0] = 0.0
    for k in range(n - 1):
        if d[k] == 0.0:
            m[k] = m[k + 1] = 0.0
            continue
        a, b = m[k] / d[k], m[k + 1] / d[k]
        s = a * a + b * b
        if s > 9.0:
            t = 3.0 / np.sqrt(s)
            m[k], m[k + 1] = t * a * d[k], t * b * d[k]
    return m


def hermite(x: np.ndarray, y: np.ndarray, m: np.ndarray, t: np.ndarray) -> np.ndarray:
    x = np.asarray(x, np.float64)
    t = np.clip(np.asarray(t, np.float64), x[0], x[-1])
    k = np.clip(np.searchsorted(x, t, side="right") - 1, 0, len(x) - 2)
    h = np.maximum(x[k + 1] - x[k], 1e-12)
    s = (t - x[k]) / h
    s2, s3 = s * s, s * s * s
    return (2 * s3 - 3 * s2 + 1) * y[k] + (s3 - 2 * s2 + s) * h * m[k] + (-2 * s3 + 3 * s2) * y[k + 1] + (s3 - s2) * h * m[k + 1]


def clean_points(points) -> np.ndarray | None:
    try:
        p = np.asarray(points, np.float64)[:, :2]
    except (TypeError, ValueError, IndexError):
        return None
    if p.ndim != 2 or len(p) < 2 or not np.all(np.isfinite(p)):
        return None
    p = np.clip(p[np.argsort(p[:, 0], kind="stable")], 0.0, 1.0)
    keep = np.concatenate([[True], np.diff(p[:, 0]) > 1e-6])
    p = p[keep]
    return p if len(p) >= 2 else None


def is_identity(points) -> bool:
    p = clean_points(points)
    return p is None or bool(np.all(np.abs(p[:, 0] - p[:, 1]) <= 1e-6))


def point_lut(points, n: int = NE) -> np.ndarray | None:
    p = clean_points(points)
    if p is None or np.all(np.abs(p[:, 0] - p[:, 1]) <= 1e-6):
        return None
    t = np.linspace(0.0, 1.0, n)
    return np.clip(hermite(p[:, 0], p[:, 1], monotone_slopes(p[:, 0], p[:, 1]), t), 0.0, 1.0).astype(np.float32)


def parametric_points(vals) -> np.ndarray:
    sh, dk, lt, hl, s1, s2, s3 = vals
    xs = [0.0, s1 / 2.0, (s1 + s2) / 2.0, (s2 + s3) / 2.0, (s3 + 1.0) / 2.0, 1.0]
    ys = [0.0] + [x + a * g for x, a, g in zip(xs[1:5], (sh, dk, lt, hl), REGION_GAIN)] + [1.0]
    for k in range(1, 5):
        ys[k] = min(max(ys[k], ys[k - 1] + REGION_MIN * (xs[k] - xs[k - 1])), 1.0 - REGION_MIN * (1.0 - xs[k]))
    return np.array([xs, ys], np.float64).T


def parametric_values(c: dict) -> tuple[float, float, float, float, float, float, float]:
    def num(k, d):
        v = c.get(k, d)
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v) else d
    s1 = min(max(num("splitShadows", 25.0), 10.0), 70.0) / 100.0
    s2 = min(max(num("splitMid", 50.0), 20.0), 80.0) / 100.0
    s3 = min(max(num("splitHighlights", 75.0), 30.0), 90.0) / 100.0
    s2 = max(s2, s1 + 0.02)
    s3 = max(s3, s2 + 0.02)
    return (num("shadows", 0.0) / 100.0, num("darks", 0.0) / 100.0, num("lights", 0.0) / 100.0, num("highlights", 0.0) / 100.0, s1, s2, min(s3, 0.98))


def parametric_curve(e: np.ndarray, vals) -> np.ndarray:
    pts = parametric_points(vals)
    return hermite(pts[:, 0], pts[:, 1], monotone_slopes(pts[:, 0], pts[:, 1]), e)


@lru_cache(maxsize=32)
def _parametric(vals: tuple) -> tuple[np.ndarray, np.ndarray]:
    t = np.linspace(0.0, 1.0, NP + 1)
    y = np.clip(parametric_curve(t, vals), 0.0, 1.0)
    d = np.gradient(y, t)
    return y.astype(np.float32), np.maximum(d, 0.0).astype(np.float32)


def parametric_lut(curve: dict) -> tuple[np.ndarray, np.ndarray] | None:
    vals = parametric_values(curve or {})
    if not any(vals[:4]):
        return None
    return _parametric(vals)


def srgb_enc(y: np.ndarray) -> np.ndarray:
    y = np.clip(np.asarray(y, np.float64), 0.0, 1.0)
    return np.where(y <= 0.0031308, y * 12.92, 1.055 * np.power(y, 1.0 / 2.4) - 0.055)


def srgb_dec(e: np.ndarray) -> np.ndarray:
    e = np.clip(np.asarray(e, np.float64), 0.0, 1.0)
    return np.where(e <= 0.04045, e / 12.92, np.power((e + 0.055) / 1.055, 2.4))


def trc_enc(y: np.ndarray, space: str) -> np.ndarray:
    if space == "linear":
        return np.clip(np.asarray(y, np.float64), 0.0, 1.0)
    if space in SPACE_GAMMA:
        return np.power(np.clip(np.asarray(y, np.float64), 0.0, 1.0), 1.0 / SPACE_GAMMA[space])
    return srgb_enc(y)


def trc_dec(e: np.ndarray, space: str) -> np.ndarray:
    if space == "linear":
        return np.clip(np.asarray(e, np.float64), 0.0, 1.0)
    if space in SPACE_GAMMA:
        return np.power(np.clip(np.asarray(e, np.float64), 0.0, 1.0), SPACE_GAMMA[space])
    return srgb_dec(e)


@lru_cache(maxsize=8)
def enc_lut(space: str = "srgb") -> np.ndarray:
    u = np.linspace(0.0, 1.0, NE)
    return trc_enc(u ** 4, space).astype(np.float32)


@lru_cache(maxsize=8)
def dec_lut(space: str = "srgb") -> np.ndarray:
    return trc_dec(np.linspace(0.0, 1.0, NE), space).astype(np.float32)


def lut1(t: np.ndarray, lut: np.ndarray) -> np.ndarray:
    n = lut.shape[0] - 1
    f = np.clip(t, 0.0, 1.0) * np.float32(n)
    i = np.minimum(f.astype(np.int32), n - 1)
    f -= i
    lo = lut[i]
    return lo + (lut[i + 1] - lo) * f


def enc(y: np.ndarray, space: str = "srgb") -> np.ndarray:
    return lut1(np.sqrt(np.sqrt(np.maximum(y, 0.0))), enc_lut(space))


def dec(e: np.ndarray, space: str = "srgb") -> np.ndarray:
    return lut1(e, dec_lut(space))


def valid_knots(k) -> np.ndarray | None:
    try:
        a = np.asarray(k, np.float64)
    except (TypeError, ValueError):
        return None
    if a.ndim != 2 or a.shape[1] != 2 or len(a) < 4 or not np.all(np.isfinite(a)):
        return None
    if np.any(np.diff(a[:, 0]) <= 0) or np.any(np.diff(a[:, 1]) < -1e-9) or a[0, 0] <= 0 or a[0, 1] < 0 or a[-1, 1] > 1.0001:
        return None
    if not a[0, 1] < MID < a[-1, 1] or a[-1, 1] - a[0, 1] < 0.3:
        return None
    return a


def generic_knots() -> list:
    return [[float(MID * 2.0 ** v), float(srgb_dec(e))] for v, e in GENERIC]


def _from_knots(a: np.ndarray, v: np.ndarray) -> np.ndarray:
    kv = np.log2(a[:, 0] / MID)
    ke = srgb_enc(np.clip(a[:, 1], 0.0, 1.0))
    ke = np.maximum.accumulate(ke)
    m = monotone_slopes(kv, ke)
    out = hermite(kv, ke, m, v)
    y0 = max(float(a[0, 1]), 1e-9)
    below = v < kv[0]
    out[below] = srgb_enc(y0 * np.exp2(v[below] - kv[0]))
    above = v > kv[-1]
    if np.any(above):
        yn = float(srgb_dec(ke[-1]))
        if yn < 0.9999:
            dy = max(float(m[-1]), 1e-6) * _dy_de(float(ke[-1]))
            k = max(dy / ((1.0 - yn) * np.log(2.0)), 0.25)
            out[above] = srgb_enc(1.0 - (1.0 - yn) * np.exp2(-(v[above] - kv[-1]) * k))
        else:
            out[above] = ke[-1]
    return np.clip(out, 0.0, 1.0)


def _dy_de(e: float) -> float:
    return 1.0 / 12.92 if e <= 0.04045 else 2.4 / 1.055 * ((e + 0.055) / 1.055) ** 1.4


@lru_cache(maxsize=32)
def _tone(key: tuple, raw: bool) -> tuple[np.ndarray, np.ndarray]:
    v = np.linspace(VMIN, VMAX, NV)
    if raw:
        e = _from_knots(np.asarray(key, np.float64).reshape(-1, 2), v)
    else:
        e = srgb_enc(MID * np.exp2(v))
    y = srgb_dec(e)
    ly = np.log2(np.maximum(y, 1e-12))
    g = np.gradient(ly, v)
    g[y <= 1e-9] = 1.0
    if not raw:
        g = np.where(MID * np.exp2(v) < 1.0, 1.0, 0.0)
    return e.astype(np.float32), np.clip(g, 0.0, 4.0).astype(np.float32)


def tone_lut(knots, raw: bool) -> tuple[np.ndarray, np.ndarray]:
    if not raw:
        return _tone((), False)
    a = valid_knots(knots)
    if a is None:
        a = np.asarray(generic_knots(), np.float64)
    return _tone(tuple(float(x) for x in a.ravel()), True)


def lut_v(v: np.ndarray, lut: np.ndarray) -> np.ndarray:
    return lut1((v - np.float32(VMIN)) * np.float32(1.0 / (VMAX - VMIN)), lut)


def contrast(e: np.ndarray, a: np.ndarray | float, p: float = PIVOT) -> tuple[np.ndarray, np.ndarray]:
    lo = e < p
    u = np.where(lo, e / p, (e - p) / (1.0 - p))
    w = np.where(lo, p, 1.0 - p) / np.pi
    s = np.sin(np.pi * np.clip(u, 0.0, 1.0))
    c = np.cos(np.pi * np.clip(u, 0.0, 1.0))
    out = np.where(lo, e - a * w * s, e + a * w * s)
    d = np.where(lo, 1.0 - a * c, 1.0 + a * c)
    inside = (e >= 0.0) & (e <= 1.0)
    return np.where(inside, out, e), np.where(inside, d, 1.0)
