import cv2
import numpy as np

from app.develop import colour, curves as cv

FIT_LONG = 192
BIN = 0.25
MIN_BIN = 12
MIN_PIXELS = 400
MAX_ERR = 0.035
MAX_COLOR_ERR = 0.030
MIN_SPAN = 3.0
SMOOTH = 0.25
PRIOR = 0.05
MIN_SLOPE = 0.002
KNOT_V = np.arange(-11.0, 3.01, 0.5)
SRGB_TO_WORK = (colour.from_xyz("rec2020") @ colour.to_xyz("srgb")).astype(np.float32)


def _match_aspect(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ra, rb = a.shape[1] / a.shape[0], b.shape[1] / b.shape[0]
    if abs(ra - rb) <= 0.01 * rb:
        return a, b

    def crop(img: np.ndarray, r: float) -> np.ndarray:
        h, w = img.shape[:2]
        if w / h > r:
            nw = int(round(h * r))
            x0 = (w - nw) // 2
            return img[:, x0:x0 + nw]
        nh = int(round(w / r))
        y0 = (h - nh) // 2
        return img[y0:y0 + nh]
    return (crop(a, rb), b) if ra > rb else (a, crop(b, ra))


def _trim_borders(ref: np.ndarray) -> tuple[slice, slice]:
    dark = ref.max(axis=2) < 6
    rows = np.where(dark.mean(axis=1) < 0.98)[0]
    cols = np.where(dark.mean(axis=0) < 0.98)[0]
    if len(rows) < ref.shape[0] * 0.6 or len(cols) < ref.shape[1] * 0.6:
        return slice(None), slice(None)
    return slice(rows[0], rows[-1] + 1), slice(cols[0], cols[-1] + 1)


def _pairs(sensor: np.ndarray, ref8: np.ndarray):
    ref8 = np.ascontiguousarray(ref8[..., :3])
    ys, xs = _trim_borders(ref8)
    ref8 = ref8[ys, xs]
    s = np.asarray(sensor[..., :3])
    sh, sw = s.shape[:2]
    k0 = min(1.0, 4 * FIT_LONG / max(sh, sw))
    if k0 < 1.0:
        s = cv2.resize(np.ascontiguousarray(s, np.float32), (max(16, int(round(sw * k0))), max(16, int(round(sh * k0)))), interpolation=cv2.INTER_AREA)
    s, r = _match_aspect(np.ascontiguousarray(s, np.float32), ref8)
    h, w = r.shape[:2]
    k = FIT_LONG / max(h, w)
    tw, th = max(16, int(round(w * k))), max(16, int(round(h * k)))
    smax = s.max(axis=2)
    clip = float(np.percentile(smax, 99.95))
    sm = cv2.resize(s, (tw, th), interpolation=cv2.INTER_AREA)
    hot = cv2.resize((smax >= 0.97 * clip).astype(np.float32), (tw, th), interpolation=cv2.INTER_AREA)
    rl = colour.srgb_decode(r.astype(np.float32) / 255.0) @ SRGB_TO_WORK.T
    rm = cv2.resize(np.ascontiguousarray(rl, np.float32), (tw, th), interpolation=cv2.INTER_AREA)
    rmax = cv2.resize((r.max(axis=2) >= 250).astype(np.float32), (tw, th), interpolation=cv2.INTER_AREA)
    ysn = np.maximum(sm @ colour.LUMA_2020, 1e-7)
    yrf = np.maximum(rm @ colour.LUMA_2020, 1e-7)
    ls, lr = np.log2(ysn), np.log2(yrf)
    shift, resp = cv2.phaseCorrelate(cv2.GaussianBlur(ls, (0, 0), 1.0), cv2.GaussianBlur(lr, (0, 0), 1.0))
    if resp > 0.1 and max(abs(shift[0]), abs(shift[1])) <= 3.0:
        m = np.float32([[1, 0, shift[0]], [0, 1, shift[1]]])
        rm = cv2.warpAffine(rm, m, (tw, th), borderMode=cv2.BORDER_REPLICATE)
        rmax = cv2.warpAffine(rmax, m, (tw, th), borderMode=cv2.BORDER_REPLICATE)
        yrf = np.maximum(rm @ colour.LUMA_2020, 1e-7)
        lr = np.log2(yrf)
    gs = np.hypot(cv2.Sobel(ls, cv2.CV_32F, 1, 0), cv2.Sobel(ls, cv2.CV_32F, 0, 1)) / 8.0
    gr = np.hypot(cv2.Sobel(lr, cv2.CV_32F, 1, 0), cv2.Sobel(lr, cv2.CV_32F, 0, 1)) / 8.0
    ok = (gs < 0.35) & (gr < 0.35) & (hot < 0.01) & (rmax < 0.01) & (yrf > 1e-4) & np.all(rm > 0, axis=2)
    yy, xx = np.mgrid[0:th, 0:tw]
    test = ((yy // 8 + xx // 8) % 2) == 1
    return sm, rm, ysn, yrf, ok, test


def _isotonic(y: np.ndarray, w: np.ndarray) -> np.ndarray:
    vals, wts, cnt = [], [], []
    for yi, wi in zip(y, w):
        vals.append(float(yi))
        wts.append(float(wi))
        cnt.append(1)
        while len(vals) > 1 and vals[-2] > vals[-1]:
            wsum = wts[-2] + wts[-1]
            v = (vals[-2] * wts[-2] + vals[-1] * wts[-1]) / wsum
            c = cnt[-2] + cnt[-1]
            vals[-2:], wts[-2:], cnt[-2:] = [v], [wsum], [c]
    return np.repeat(vals, cnt)


def _generic_e(v: np.ndarray) -> np.ndarray:
    g = np.asarray(cv.GENERIC)
    return np.interp(v, g[:, 0], g[:, 1])


def _curve(v: np.ndarray, e: np.ndarray, w: np.ndarray) -> np.ndarray | None:
    edges = np.arange(-12.0, 4.0 + BIN, BIN)
    idx = np.digitize(v, edges) - 1
    bv, be, bw = [], [], []
    for i in range(len(edges) - 1):
        sel = idx == i
        n = int(sel.sum())
        if n < MIN_BIN:
            continue
        bv.append(float(np.median(v[sel])))
        be.append(float(np.median(e[sel])))
        bw.append(float(n))
    if len(bv) < 6:
        return None
    bv, be, bw = np.array(bv), _isotonic(np.array(be), np.array(bw)), np.array(bw)
    if bv[-1] - bv[0] < MIN_SPAN:
        return None
    lo, hi = bv[0], bv[-1]
    g = _generic_e(KNOT_V)
    g_lo, g_hi = float(_generic_e(np.array([lo]))[0]), float(_generic_e(np.array([hi]))[0])
    prior = np.full(len(KNOT_V), np.nan)
    below, above = KNOT_V < lo - 0.25, KNOT_V > hi + 0.25
    prior[below] = be[0] * g[below] / max(g_lo, 1e-6)
    if g_hi < 0.9999:
        prior[above] = 1.0 - (1.0 - be[-1]) * (1.0 - g[above]) / (1.0 - g_hi)
    else:
        prior[above] = be[-1]
    out = _smooth_fit(bv, be, bw, prior)
    return np.clip(out, 0.0, 0.999)


def _smooth_fit(bv: np.ndarray, be: np.ndarray, bw: np.ndarray, prior: np.ndarray) -> np.ndarray:
    n = len(KNOT_V)
    step = KNOT_V[1] - KNOT_V[0]
    pos = np.clip((bv - KNOT_V[0]) / step, 0.0, n - 1.000001)
    i = pos.astype(int)
    f = pos - i
    A = np.zeros((len(bv), n))
    A[np.arange(len(bv)), i] = 1.0 - f
    A[np.arange(len(bv)), i + 1] = f
    D = np.zeros((n - 2, n))
    for k in range(n - 2):
        D[k, k:k + 3] = (1.0, -2.0, 1.0)
    w = bw / bw.sum()
    has = np.isfinite(prior)
    pw = np.where(has, PRIOR, 0.0)
    lhs = A.T @ (A * w[:, None]) + SMOOTH * D.T @ D + np.diag(pw) + 1e-9 * np.eye(n)
    x = np.linalg.solve(lhs, A.T @ (w * be) + pw * np.where(has, prior, 0.0))
    for k in range(1, n):
        x[k] = max(x[k], x[k - 1] + MIN_SLOPE * step)
    return x


def _knots(e: np.ndarray) -> list:
    y = cv.srgb_dec(e)
    keep = np.concatenate([[True], np.diff(y) > 1e-7])
    return [[float(cv.MID * 2.0 ** v), float(min(yy, 0.999))] for v, yy in zip(KNOT_V[keep], y[keep])]


def _predict(e_knots: np.ndarray, v: np.ndarray) -> np.ndarray:
    return np.interp(v, KNOT_V, e_knots)


def _tone(ysn: np.ndarray, yrf: np.ndarray, ok: np.ndarray, test: np.ndarray):
    v = np.log2(ysn / cv.MID)
    e = cv.srgb_enc(np.clip(yrf, 0.0, 1.0))
    tr, te = ok & ~test, ok & test
    if tr.sum() < MIN_PIXELS or te.sum() < MIN_PIXELS // 2:
        return None
    fit = _curve(v[tr], e[tr], np.ones(int(tr.sum())))
    if fit is None:
        return None
    err = float(np.median(np.abs(_predict(fit, v[te]) - e[te])))
    if err > MAX_ERR:
        return None
    full = _curve(v[ok], e[ok], np.ones(int(ok.sum())))
    if full is None:
        return None
    mid = float(_predict(full, np.array([0.0]))[0])
    if not 0.40 <= mid <= 0.97:
        return None
    knots = _knots(full)
    if cv.valid_knots(knots) is None:
        return None
    return knots, full, err


def _basis() -> np.ndarray:
    luma = colour.LUMA_2020.astype(np.float64)
    rows = []
    for i in range(3):
        r = np.zeros(9)
        r[3 * i:3 * i + 3] = 1.0
        rows.append(r)
    for j in range(3):
        r = np.zeros(9)
        r[j::3] = luma
        rows.append(r)
    _, s, vt = np.linalg.svd(np.array(rows))
    rank = int(np.sum(s > 1e-9))
    return vt[rank:]


def _mantiuk(g: np.ndarray) -> np.ndarray:
    from app.develop import finish
    gp = np.power(np.maximum(g, 1e-9), finish.K2)
    return (1.0 + finish.K1) * gp / (1.0 + finish.K1 * gp) * finish.SAT_GAIN


def _lab(rgb: np.ndarray) -> np.ndarray:
    return colour.oklab_from_2020(np.maximum(rgb, 0.0).astype(np.float32))


def _matrix(sm, rm, ysn, yrf, ok, test, knots):
    e_lut, g_lut = cv.tone_lut(knots, True)
    v = np.log2(ysn / cv.MID)
    s = _mantiuk(np.asarray(cv.lut_v(v.astype(np.float32), g_lut), np.float64))
    q = sm / ysn[..., None]
    j = rm / yrf[..., None]
    sel = ok & (v > -5.0) & (v < 1.5) & (s > 0.3)
    tr, te = sel & ~test, sel & test
    if tr.sum() < MIN_PIXELS or te.sum() < MIN_PIXELS // 2:
        return None
    rho = 1.0 + (j - 1.0) / s[..., None]
    B = _basis()

    def solve(mask, w):
        qq, tt = q[mask].astype(np.float64), (rho[mask] - q[mask]).astype(np.float64)
        cols = []
        for b in B:
            d = b.reshape(3, 3)
            cols.append(qq @ d.T)
        A = np.stack([c.reshape(-1) for c in cols], axis=1)
        ww = np.repeat(w, 3)
        coef, *_ = np.linalg.lstsq(A * ww[:, None], tt.reshape(-1) * ww, rcond=None)
        return np.eye(3) + np.tensordot(coef, B, axes=(0, 0)).reshape(3, 3)
    w = np.ones(int(tr.sum()))
    m = np.eye(3)
    for _ in range(4):
        m = solve(tr, w)
        res = np.linalg.norm(q[tr] @ m.T - rho[tr], axis=1)
        scale = max(float(np.median(res)) * 1.5, 1e-4)
        w = 1.0 / np.maximum(1.0, res / scale)
    if not np.all(np.isfinite(m)) or np.abs(m - np.eye(3)).max() > 1.2 or np.linalg.cond(m) > 20:
        return None

    def err(mm):
        r = q[te] @ mm.T
        pred = (1.0 + s[te][:, None] * (r - 1.0)) * cv.srgb_dec(cv.lut_v(v[te].astype(np.float32), e_lut))[:, None]
        tgt = rm[te]
        a, b = _lab(pred), _lab(tgt)
        return float(np.median(np.hypot(a[:, 1] - b[:, 1], a[:, 2] - b[:, 2])))
    e_fit, e_id = err(m), err(np.eye(3))
    if e_fit > MAX_COLOR_ERR or e_fit > e_id:
        return None
    return m, e_fit, e_id


def fit(sensor: np.ndarray, reference_srgb8: np.ndarray) -> dict:
    try:
        if sensor is None or reference_srgb8 is None or sensor.ndim != 3 or reference_srgb8.ndim != 3:
            return {}
        if min(reference_srgb8.shape[:2]) < 32 or min(sensor.shape[:2]) < 32:
            return {}
        sm, rm, ysn, yrf, ok, test = _pairs(sensor, np.asarray(reference_srgb8, np.uint8))
        tone = _tone(ysn, yrf, ok, test)
        if tone is None:
            return {}
        knots = tone[0]
        out: dict = {"tone": knots}
        got = _matrix(sm, rm, ysn, yrf, ok, test, knots)
        if got is not None:
            out["look"] = {"tone": knots, "matrix": [[float(x) for x in row] for row in got[0]]}
        return out
    except (ValueError, FloatingPointError, cv2.error, np.linalg.LinAlgError):
        return {}


__all__ = ["fit"]
