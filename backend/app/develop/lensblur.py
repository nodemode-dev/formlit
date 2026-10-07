import cv2
import numpy as np

from app.develop.geometry import Frame
from app.develop.masks import load_bitmap
from app.develop.settings import section_enabled

LEVELS = 6


def active(dev: dict) -> bool:
    lb = dev.get("lensBlur") or {}
    return bool(lb.get("depth")) and float(lb.get("amount", 0)) > 0 and section_enabled(dev, "lensBlur")


def _disk(img: np.ndarray, r: float, bokeh: float) -> np.ndarray:
    if r < 0.6:
        return img
    k = int(max(3, round(r * 2) | 1))
    yy, xx = np.mgrid[-(k // 2):k // 2 + 1, -(k // 2):k // 2 + 1].astype(np.float32)
    d = np.sqrt(xx * xx + yy * yy)
    disk = np.clip(r + 0.5 - d, 0.0, 1.0)
    ring = 1.0 + bokeh * np.clip(1.0 - np.abs(d - r * 0.85) / max(1.0, r * 0.25), 0.0, 1.0)
    kern = disk * ring
    kern /= max(1e-9, float(kern.sum()))
    if k > 41:
        s = k / 41.0
        small = cv2.resize(img, (max(1, round(img.shape[1] / s)), max(1, round(img.shape[0] / s))), interpolation=cv2.INTER_AREA)
        return cv2.resize(_disk(small, r / s, bokeh), (img.shape[1], img.shape[0]), interpolation=cv2.INTER_LINEAR)
    return cv2.filter2D(img, -1, kern, borderType=cv2.BORDER_REFLECT)


def apply(lin: np.ndarray, dev: dict, frame: Frame, w: int, h: int, ppl: float, photo_id: int | None) -> np.ndarray:
    lb = dev.get("lensBlur") or {}
    depth = load_bitmap(photo_id, lb.get("depth"), frame, w, h)
    far = 1.0 - depth
    focus = float(lb.get("focalDistance", 50)) / 100.0
    rng = float(lb.get("focalRange", 20)) / 100.0 * 0.5
    amount = float(lb.get("amount", 0)) / 100.0
    bokeh = float(lb.get("bokeh", 0)) / 100.0
    max_r = amount * 0.012 * ppl
    coc = np.clip((np.abs(far - focus) - rng) / 0.4, 0.0, 1.0) * (LEVELS - 1)
    coc = cv2.GaussianBlur(coc.astype(np.float32), (0, 0), max(1.0, max_r * 0.25))
    hl = np.maximum(lin, 0.0)
    boost = 1.0 + bokeh * 3.0 * np.clip((hl.max(axis=2, keepdims=True) - 1.0), 0.0, 4.0)
    src = hl * boost
    levels = [src] + [_disk(src, max_r * k / (LEVELS - 1), bokeh) for k in range(1, LEVELS)]
    i0 = np.clip(np.floor(coc).astype(np.int32), 0, LEVELS - 2)
    t = (coc - i0)[..., None]
    out = np.zeros_like(lin)
    for k in range(LEVELS - 1):
        m = (i0 == k)[..., None]
        out = np.where(m, levels[k] * (1 - t) + levels[k + 1] * t, out)
    out = out / np.maximum(1.0 + bokeh * 3.0 * np.clip(out.max(axis=2, keepdims=True) - 1.0, 0.0, 4.0), 1.0)
    return out.astype(np.float32)
