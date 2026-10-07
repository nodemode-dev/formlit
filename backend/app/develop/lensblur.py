import cv2
import numpy as np

from app.develop.geometry import Frame
from app.develop.masks import load_bitmap
from app.develop.settings import section_enabled

LEVELS = 6


def active(dev: dict) -> bool:
    lb = dev.get("lensBlur") or {}
    return bool(lb.get("depth")) and float(lb.get("amount", 0)) > 0 and section_enabled(dev, "lensBlur")


SHAPES = ("circle", "bubble", "blade5", "ring", "cateye")


def _kernel(r: float, bokeh: float, shape: str, angle: float = 0.0) -> np.ndarray:
    k = int(max(3, round(r * 2) | 1))
    yy, xx = np.mgrid[-(k // 2):k // 2 + 1, -(k // 2):k // 2 + 1].astype(np.float32)
    d = np.sqrt(xx * xx + yy * yy)
    if shape == "blade5":
        th = np.arctan2(yy, xx) + np.pi / 2
        sector = np.pi * 2 / 5
        a = np.mod(th, sector) - sector / 2
        edge = r * np.cos(sector / 2) / np.maximum(np.cos(a), 1e-3)
        disk = np.clip(edge + 0.5 - d, 0.0, 1.0)
    elif shape == "cateye":
        off = r * 0.55
        dx, dy = xx - off * np.cos(angle), yy - off * np.sin(angle)
        disk = np.clip(r + 0.5 - d, 0.0, 1.0) * np.clip(r * 1.05 + 0.5 - np.sqrt(dx * dx + dy * dy), 0.0, 1.0)
    else:
        disk = np.clip(r + 0.5 - d, 0.0, 1.0)
    if shape == "ring":
        disk = disk * np.clip(d - r * 0.45 + 0.5, 0.0, 1.0)
    edge_boost = bokeh * (2.5 if shape == "bubble" else 1.0)
    ring = 1.0 + edge_boost * np.clip(1.0 - np.abs(d - r * 0.85) / max(1.0, r * 0.25), 0.0, 1.0)
    kern = disk * ring
    return (kern / max(1e-9, float(kern.sum()))).astype(np.float32)


def _disk(img: np.ndarray, r: float, bokeh: float, shape: str = "circle", angle: float = 0.0) -> np.ndarray:
    if r < 0.6:
        return img
    k = int(max(3, round(r * 2) | 1))
    if k > 41:
        s = k / 41.0
        small = cv2.resize(img, (max(1, round(img.shape[1] / s)), max(1, round(img.shape[0] / s))), interpolation=cv2.INTER_AREA)
        return cv2.resize(_disk(small, r / s, bokeh, shape, angle), (img.shape[1], img.shape[0]), interpolation=cv2.INTER_LINEAR)
    return cv2.filter2D(img, -1, _kernel(r, bokeh, shape, angle), borderType=cv2.BORDER_REFLECT)


def _shaped(img: np.ndarray, r: float, bokeh: float, shape: str) -> np.ndarray:
    if shape != "cateye" or r < 1.5:
        return _disk(img, r, bokeh, "circle" if shape == "cateye" else shape)
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    th = np.arctan2(yy - h / 2, xx - w / 2)
    rad = np.clip(np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)) / 1.2, 0.0, 1.0)[..., None]
    out = np.zeros_like(img)
    wsum = np.zeros((h, w, 1), np.float32)
    for a in np.linspace(0, np.pi, 4, endpoint=False):
        wt = (np.cos(th - a) ** 2)[..., None]
        out += _disk(img, r, bokeh, "cateye", float(a + np.pi / 2)) * wt
        wsum += wt
    centre = _disk(img, r, bokeh, "circle")
    return (centre * (1.0 - rad) + (out / np.maximum(wsum, 1e-6)) * rad).astype(np.float32)


def coc_map(dev: dict, frame: Frame, w: int, h: int, photo_id: int | None, lin: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    lb = dev.get("lensBlur") or {}
    depth = load_bitmap(photo_id, lb.get("depth"), frame, w, h)
    far = 1.0 - depth
    focus = float(lb.get("focalDistance", 50)) / 100.0
    rng = float(lb.get("focalRange", 20)) / 100.0 * 0.5
    coc = np.clip((np.abs(far - focus) - rng) / 0.4, 0.0, 1.0)
    strokes = lb.get("refine") or []
    if strokes:
        from app.develop.masks import rasterize_brush
        base = lin if lin is not None else np.zeros((h, w, 3), np.float32)
        zeros = np.zeros((h, w), np.float32)
        for mode in ("focus", "blur"):
            mine = [dict(s, auto=False, autoMask=False, erase=False) for s in strokes if s.get("mode", "blur") == mode]
            if not mine:
                continue
            a = rasterize_brush(mine, frame, w, h, base, zeros)
            coc = coc * (1.0 - a) if mode == "focus" else np.maximum(coc, a)
    return coc.astype(np.float32), far.astype(np.float32)


def visualize(out: np.ndarray, dev: dict, frame: Frame, w: int, h: int, photo_id: int | None, opacity: float = 0.8) -> np.ndarray:
    coc, far = coc_map(dev, frame, w, h, photo_id)
    near = np.array([1.0, 0.78, 0.25], np.float32)
    distant = np.array([0.25, 0.35, 0.95], np.float32)
    heat = near * (1.0 - far[..., None]) + distant * far[..., None]
    sharp = (coc < 0.02)[..., None]
    heat = np.where(sharp, np.array([0.95, 0.95, 0.95], np.float32), heat)
    return (out * (1.0 - opacity) + heat * opacity).astype(np.float32)


def apply(lin: np.ndarray, dev: dict, frame: Frame, w: int, h: int, ppl: float, photo_id: int | None) -> np.ndarray:
    lb = dev.get("lensBlur") or {}
    amount = float(lb.get("amount", 0)) / 100.0
    bokeh = float(lb.get("bokeh", 0)) / 100.0
    shape = str(lb.get("shape", "circle"))
    shape = shape if shape in SHAPES else "circle"
    max_r = amount * 0.012 * ppl
    coc, _ = coc_map(dev, frame, w, h, photo_id, lin)
    coc = coc * (LEVELS - 1)
    coc = cv2.GaussianBlur(coc.astype(np.float32), (0, 0), max(1.0, max_r * 0.25))
    src = np.maximum(lin, 0.0)
    src *= 1.0 + bokeh * 3.0 * np.clip((src.max(axis=2, keepdims=True) - 1.0), 0.0, 4.0)
    i0 = np.clip(np.floor(coc).astype(np.int32), 0, LEVELS - 2)
    t = (coc - i0).astype(np.float32)
    del coc
    out = np.zeros_like(lin)
    prev = src
    for k in range(LEVELS - 1):
        nxt = _shaped(src, max_r * (k + 1) / (LEVELS - 1), bokeh, shape)
        m = i0 == k
        if m.any():
            tk = t[m][:, None]
            out[m] = prev[m] * (1 - tk) + nxt[m] * tk
        prev = nxt
    out = out / np.maximum(1.0 + bokeh * 3.0 * np.clip(out.max(axis=2, keepdims=True) - 1.0, 0.0, 4.0), 1.0)
    return out.astype(np.float32)
