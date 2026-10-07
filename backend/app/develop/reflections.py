import threading

import cv2
import numpy as np

from app.develop import colour
from app.develop.settings import section_enabled

PROXY = 1536
LAMBDA = 1e-7
LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


def amount(dev: dict) -> float:
    if not section_enabled(dev, "reflections"):
        return 0.0
    return max(-1.0, min(1.0, float((dev.get("reflections") or {}).get("amount", 0)) / 100.0))


def active(dev: dict) -> bool:
    return amount(dev) != 0.0


def _grads(a: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    gx = np.zeros_like(a)
    gy = np.zeros_like(a)
    gx[:, :-1] = a[:, 1:] - a[:, :-1]
    gy[:-1] = a[1:] - a[:-1]
    return gx, gy


def suppress(e: np.ndarray, threshold: float, lam: float = LAMBDA) -> np.ndarray:
    h0, w0 = e.shape[:2]
    if h0 % 2 or w0 % 2:
        e = cv2.copyMakeBorder(e, 0, h0 % 2, 0, w0 % 2, cv2.BORDER_REPLICATE)
    h, w = e.shape[:2]
    lx, ly = _grads(e @ LUMA)
    t = np.clip((np.sqrt(lx * lx + ly * ly) - 0.7 * threshold) / (0.6 * threshold), 0.0, 1.0).astype(np.float64)
    keep = t * t * (3.0 - 2.0 * t)
    kappa = 2 * np.cos(np.pi * np.arange(h)[:, None] / h) + 2 * np.cos(np.pi * np.arange(w)[None, :] / w) - 4
    denom = kappa * kappa + lam
    out = np.empty(e.shape, np.float32)
    for ch in range(e.shape[2]):
        a = e[..., ch].astype(np.float64)
        gx, gy = _grads(a)
        gx *= keep
        gy *= keep
        div = np.zeros_like(a)
        div[:, 0] = gx[:, 0]
        div[:, 1:] = gx[:, 1:] - gx[:, :-1]
        div[0] += gy[0]
        div[1:] += gy[1:] - gy[:-1]
        out[..., ch] = cv2.idct((kappa * cv2.dct(div) + lam * cv2.dct(a)) / denom)
    return out[:h0, :w0]


def layer(lin: np.ndarray, strength: float, out_long: int) -> np.ndarray:
    h, w = lin.shape[:2]
    s = min(1.0, PROXY / max(1, out_long))
    small = cv2.resize(lin, (max(8, round(w * s)), max(8, round(h * s))), interpolation=cv2.INTER_AREA) if s < 1.0 else lin
    e = colour.srgb_encode(np.clip(small, 0.0, 1.0))
    t = colour.srgb_decode(np.clip(suppress(e, 0.01 + 0.05 * strength), 0.0, 1.0))
    r = np.clip(small, 0.0, 1.0) - t
    return cv2.resize(r, (w, h), interpolation=cv2.INTER_LINEAR) if s < 1.0 else r


_cache: dict = {}
_lock = threading.Lock()


def global_layer(img: np.ndarray, frame, wb_m: np.ndarray | None, strength: float, key: tuple) -> tuple[np.ndarray, float]:
    pw, ph = (max(8, v) for v in frame.fit_long(PROXY))
    k = (id(img), strength, key)
    with _lock:
        hit = _cache.get(k)
    if hit is not None:
        return hit
    small = frame.sample(img, pw, ph)
    small = np.maximum(small if wb_m is None else small @ wb_m.T, 0.0).astype(np.float32)
    out = (layer(small, strength, max(pw, ph)), float(np.mean(np.clip(small, 0.0, 1.0))))
    with _lock:
        if len(_cache) > 6:
            _cache.clear()
        _cache[k] = out
    return out


def apply(lin: np.ndarray, dev: dict, glob: tuple[np.ndarray, float], region: tuple[int, int], size: tuple[int, int]) -> np.ndarray:
    a = amount(dev)
    if a == 0.0:
        return lin
    r_small, mean = glob
    h, w = lin.shape[:2]
    sx, sy = r_small.shape[1] / size[0], r_small.shape[0] / size[1]
    m = np.float32([[sx, 0.0, (region[0] + 0.5) * sx - 0.5], [0.0, sy, (region[1] + 0.5) * sy - 0.5]])
    r = cv2.warpAffine(r_small, m, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
    if a > 0:
        return np.maximum(lin - r, 0.0).astype(np.float32)
    shown = np.maximum(r, 0.0) + 0.5 * mean
    return np.maximum(lin + (shown - lin) * (-a), 0.0).astype(np.float32)
