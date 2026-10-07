import math

import cv2
import numpy as np

from app.develop import colour, settings as S

EPS_L = 2.0 ** -11
EPS_S = 0.004
HS_SIGMAS = (0.010, 0.032)
HS_EPS = (0.30, 0.45)
CLARITY_SIGMA = 0.0075
CLARITY_EPS = 0.06
TEXTURE_SIGMAS = (0.0003, 0.0022)
SOFT_SIGMA = 0.0025
HAZE_LONG = 320.0
HAZE_PATCH = 0.010
HAZE_GUIDE = 0.025
HAZE_EPS = 0.002
NR_LOCAL_SIGMA = 0.0015
RATIO_SIGMA = 0.004
MARGIN_CAP = 384
GAUSS_DIRECT = 5.0
ATROUS_NOISE = (0.889, 0.200, 0.086, 0.041, 0.020, 0.010)
NR_SIGMA = 0.05
NR_BETA = 0.002
CHROMA_SIGMA = (1.5, 9.0, 14.0)


def luminance(img: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(img[..., 0] * colour.LUMA_2020[0] + img[..., 1] * colour.LUMA_2020[1] + img[..., 2] * colour.LUMA_2020[2], dtype=np.float32)


def gauss(img: np.ndarray, sigma: float) -> np.ndarray:
    img = np.ascontiguousarray(img, np.float32)
    if sigma <= 0.05:
        return img.copy()
    if sigma <= GAUSS_DIRECT:
        return cv2.GaussianBlur(img, (0, 0), sigma, borderType=cv2.BORDER_REFLECT)
    h, w = img.shape[:2]
    f = 2 ** max(1, int(math.floor(math.log2(sigma / 2.5))))
    lw, lh = max(1, -(-w // f)), max(1, -(-h // f))
    pw, ph = lw * f, lh * f
    src = img if (pw, ph) == (w, h) else cv2.copyMakeBorder(img, 0, ph - h, 0, pw - w, cv2.BORDER_REFLECT)
    lo = cv2.resize(src, (lw, lh), interpolation=cv2.INTER_AREA)
    s2 = max(sigma * sigma - (f * f - 1) / 12.0, 0.25) ** 0.5 / f
    lo = cv2.GaussianBlur(lo, (0, 0), s2, borderType=cv2.BORDER_REFLECT)
    up = cv2.resize(lo, (pw, ph), interpolation=cv2.INTER_LINEAR)
    return np.ascontiguousarray(up[:h, :w])


def _gf_coeffs(I: np.ndarray, p: np.ndarray, sigma: float, eps: float) -> tuple[np.ndarray, np.ndarray]:
    mI, mp = gauss(I, sigma), gauss(p, sigma)
    cov = gauss(I * p, sigma) - mI * mp
    var = gauss(I * I, sigma) - mI * mI
    a = cov / (np.maximum(var, 0.0) + eps)
    return gauss(a, sigma), gauss(mp - a * mI, sigma)


def guided(I: np.ndarray, p: np.ndarray, sigma: float, eps: float) -> np.ndarray:
    h, w = I.shape[:2]
    f = max(1, int(sigma / 3.0))
    if f <= 1:
        a, b = _gf_coeffs(I, p, sigma, eps)
        return a * I + b
    lw, lh = max(2, int(round(w / f))), max(2, int(round(h / f)))
    Il = cv2.resize(I, (lw, lh), interpolation=cv2.INTER_AREA)
    pl = Il if p is I else cv2.resize(p, (lw, lh), interpolation=cv2.INTER_AREA)
    a, b = _gf_coeffs(Il, pl, sigma * lw / w, eps)
    a = cv2.resize(a, (w, h), interpolation=cv2.INTER_LINEAR)
    b = cv2.resize(b, (w, h), interpolation=cv2.INTER_LINEAR)
    return a * I + b


def _active(dev: dict) -> set:
    need = set()
    get = S.get
    if get(dev, "light.highlights") or get(dev, "light.shadows"):
        need.add("hs")
    if get(dev, "effects.clarity"):
        need.add("dc")
    if get(dev, "effects.texture"):
        need.add("dt")
    if get(dev, "effects.dehaze"):
        need.add("hd")
    for m in dev.get("masks") or []:
        adj = m.get("adjust") if isinstance(m, dict) else None
        if not isinstance(adj, dict):
            continue
        for key, plane in (("highlights", "hs"), ("shadows", "hs"), ("clarity", "dc"), ("texture", "dt"), ("dehaze", "hd")):
            v = adj.get(key)
            if isinstance(v, (int, float)) and v:
                need.add(plane)
    return need


def margin(dev: dict, ppl: float) -> int:
    need = _active(dev)
    r = 0.0
    if "hs" in need:
        r = max(r, 4.3 * HS_SIGMAS[1] * ppl)
    if "dc" in need:
        r = max(r, 4.3 * CLARITY_SIGMA * ppl)
    if "dt" in need:
        r = max(r, 3.0 * TEXTURE_SIGMAS[1] * ppl)
    if "hd" in need:
        r = max(r, 4.3 * HAZE_GUIDE * ppl + HAZE_PATCH * ppl)
    det = dev.get("detail") or {}
    if S.section_enabled(dev, "detail") and (det.get("nrColor") or det.get("nrLuminance")):
        r = max(r, 4.0 * CHROMA_SIGMA[2] + 3.0 * 16)
    r = max(r, 3.0 * max(SOFT_SIGMA, RATIO_SIGMA) * ppl, 12.0)
    return int(min(MARGIN_CAP, math.ceil(16 + r)))


def log_lum(lin: np.ndarray, eps: float = EPS_L) -> np.ndarray:
    return np.log2(luminance(lin) + np.float32(eps))


def _get(cache: dict, key: tuple, fn):
    hit = cache.get(key)
    if hit is None:
        hit = fn()
        cache[key] = hit
    return hit


def _hs(l0: np.ndarray, ppl: float) -> np.ndarray:
    b1 = guided(l0, l0, max(HS_SIGMAS[0] * ppl, 1.0), HS_EPS[0])
    b2 = guided(l0, l0, max(HS_SIGMAS[1] * ppl, 1.0), HS_EPS[1])
    return (0.5 * (b1 + b2)).astype(np.float32)


def _clarity(l0: np.ndarray, ppl: float) -> np.ndarray:
    base = guided(l0, l0, max(CLARITY_SIGMA * ppl, 0.8), CLARITY_EPS)
    d = l0 - base
    return (1.6 * np.tanh(d / 1.6)).astype(np.float32)


def _texture(l0: np.ndarray, ppl: float) -> np.ndarray:
    fine = gauss(l0, TEXTURE_SIGMAS[0] * ppl)
    return (fine - gauss(l0, max(TEXTURE_SIGMAS[1] * ppl, 0.7))).astype(np.float32)


def _haze(lin: np.ndarray, ppl: float) -> np.ndarray:
    h, w = lin.shape[:2]
    f = max(1.0, ppl / HAZE_LONG)
    lw, lh = max(4, int(round(w / f))), max(4, int(round(h / f)))
    small = cv2.resize(np.ascontiguousarray(lin, np.float32), (lw, lh), interpolation=cv2.INTER_AREA)
    dark = np.min(small, axis=2)
    r = max(1, int(round(HAZE_PATCH * ppl / f)))
    dark = cv2.erode(dark, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)), borderType=cv2.BORDER_REPLICATE)
    guide_lo = np.sqrt(np.maximum(luminance(small), 0.0))
    sig = max(HAZE_GUIDE * ppl / f, 1.0)
    a, b = _gf_coeffs(guide_lo, np.sqrt(np.maximum(dark, 0.0)), sig, HAZE_EPS)
    a = cv2.resize(a, (w, h), interpolation=cv2.INTER_LINEAR)
    b = cv2.resize(b, (w, h), interpolation=cv2.INTER_LINEAR)
    q = a * np.sqrt(np.maximum(luminance(lin), 0.0)) + b
    return np.square(np.maximum(q, 0.0)).astype(np.float32)


def build(cache: dict, lin: np.ndarray, dev: dict, ppl: float) -> dict:
    need = _active(dev)
    ppl = float(ppl)
    cache["ppl"] = ppl
    if not need:
        return cache
    l0 = _get(cache, ("l0",), lambda: log_lum(lin))
    if "hs" in need:
        cache["hs"] = _get(cache, ("hs", ppl), lambda: _hs(l0, ppl))
    if "dc" in need:
        cache["dc"] = _get(cache, ("dc", ppl), lambda: _clarity(l0, ppl))
    if "dt" in need:
        cache["dt"] = _get(cache, ("dt", ppl), lambda: _texture(l0, ppl))
    if "hd" in need:
        cache["hd"] = _get(cache, ("hd", ppl), lambda: _haze(lin, ppl))
    return cache


def sharp_detail(cache: dict, lin: np.ndarray, sigma: float) -> tuple[np.ndarray, np.ndarray]:
    key = ("ds", round(float(sigma), 4))
    hit = cache.get(key)
    if hit is None:
        ls = _get(cache, ("ls",), lambda: log_lum(lin, EPS_S))
        d = (ls - gauss(ls, sigma)).astype(np.float32)
        sm = gauss(ls, max(sigma, 0.7))
        gx = cv2.Sobel(sm, cv2.CV_32F, 1, 0, ksize=3, borderType=cv2.BORDER_REFLECT) * np.float32(0.125)
        gy = cv2.Sobel(sm, cv2.CV_32F, 0, 1, ksize=3, borderType=cv2.BORDER_REFLECT) * np.float32(0.125)
        hit = (d, np.sqrt(gx * gx + gy * gy).astype(np.float32))
        cache[key] = hit
    return hit


def soft_detail(cache: dict, lin: np.ndarray, ppl: float) -> np.ndarray:
    def make():
        l0 = _get(cache, ("l0",), lambda: log_lum(lin))
        return (gauss(l0, max(SOFT_SIGMA * ppl, 0.6)) - l0).astype(np.float32)
    return _get(cache, ("soft", float(ppl)), make)


def noise_detail(cache: dict, lin: np.ndarray, ppl: float) -> np.ndarray:
    def make():
        l0 = _get(cache, ("l0",), lambda: log_lum(lin))
        return (guided(l0, l0, max(NR_LOCAL_SIGMA * ppl, 0.8), 0.02) - l0).astype(np.float32)
    return _get(cache, ("nrd", float(ppl)), make)


def ratio_plane(cache: dict, lin: np.ndarray, ppl: float) -> np.ndarray:
    def make():
        y = luminance(lin)
        sig = max(RATIO_SIGMA * ppl, 1.0)
        num = gauss(np.ascontiguousarray(lin, np.float32), sig)
        den = gauss(y, sig)
        return (num / np.maximum(den, 1e-6)[..., None]).astype(np.float32)
    return _get(cache, ("ratio", float(ppl)), make)


def _atrous(img: np.ndarray, level: int) -> np.ndarray:
    step = 1 << level
    k = np.zeros(4 * step + 1, np.float32)
    k[::step] = np.array([1, 4, 6, 4, 1], np.float32) / 16.0
    return cv2.sepFilter2D(img, -1, k, k, borderType=cv2.BORDER_REFLECT)


def _shrink(d: np.ndarray, tau: float) -> np.ndarray:
    if tau <= 0:
        return d
    d2 = d * d
    return d * (d2 / (d2 + np.float32(tau * tau)))


def denoise(lin: np.ndarray, dev: dict, src_long: float | None, out_long: float | None) -> np.ndarray:
    if not S.section_enabled(dev, "detail"):
        return lin
    lum = S.get(dev, "detail.nrLuminance") / 100.0
    col = S.get(dev, "detail.nrColor") / 100.0
    if lum <= 0 and col <= 0:
        return lin
    r = 1.0
    if src_long and out_long:
        r = min(1.0, max(float(out_long) / float(src_long), 1e-3))
    img = np.maximum(np.ascontiguousarray(lin, np.float32), 0.0)
    u = 2.0 * np.sqrt(img + np.float32(NR_BETA))
    luma = colour.LUMA_2020
    U = (u @ luma).astype(np.float32)
    c1, c2 = u[..., 0] - u[..., 1], u[..., 2] - u[..., 1]
    if lum > 0:
        det = S.get(dev, "detail.nrDetail") / 100.0
        con = S.get(dev, "detail.nrContrast") / 100.0
        sig = NR_SIGMA * lum * r
        kappa = 2.8 - 1.9 * det
        cur, acc = U, np.zeros_like(U)
        for j in range(5):
            nxt = _atrous(cur, j)
            tau = kappa * sig * ATROUS_NOISE[j] * (1.0 - 0.8 * con * min(1.0, j / 3.0))
            acc += _shrink(cur - nxt, tau)
            cur = nxt
        U = cur + acc
    if col > 0:
        cdet = S.get(dev, "detail.nrColorDetail") / 100.0
        smooth = S.get(dev, "detail.nrColorSmoothness") / 100.0
        sig = (CHROMA_SIGMA[0] + CHROMA_SIGMA[1] * col + CHROMA_SIGMA[2] * smooth * col) * max(r, 0.15)
        eps = (0.06 * (1.08 - cdet)) ** 2
        g = U / np.float32(4.0)
        f1 = guided(g, c1 / np.float32(4.0), sig, eps) * np.float32(4.0)
        f2 = guided(g, c2 / np.float32(4.0), sig, eps) * np.float32(4.0)
        k = np.float32(min(1.0, 0.35 + 1.3 * col))
        c1 = c1 + (f1 - c1) * k
        c2 = c2 + (f2 - c2) * k
    ug = U - np.float32(luma[0]) * c1 - np.float32(luma[2]) * c2
    out = np.stack([ug + c1, ug, ug + c2], axis=-1)
    out = np.square(np.maximum(out, 0.0) * np.float32(0.5)) - np.float32(NR_BETA)
    return np.maximum(out, 0.0).astype(np.float32)
