import math

import cv2
import numpy as np

from app.develop import colour

PURPLE_BASE, GREEN_BASE, HUE_SPAN = 230.0, 80.0, 1.2


def hue_range(kind: str, lo: float, hi: float) -> tuple[float, float]:
    base = PURPLE_BASE if kind == "purple" else GREEN_BASE
    return base + float(lo) * HUE_SPAN, base + float(hi) * HUE_SPAN


def slider_for_hue(kind: str, deg: float) -> float:
    base = PURPLE_BASE if kind == "purple" else GREEN_BASE
    return float(np.clip(((deg - base) % 360.0) / HUE_SPAN, 0.0, 100.0))


def active(opt: dict) -> bool:
    return float(opt.get("defringePurple", 0) or 0) > 0 or float(opt.get("defringeGreen", 0) or 0) > 0


def _window(h: np.ndarray, lo: float, hi: float, soft: float = 8.0) -> np.ndarray:
    span = (hi - lo) % 360.0 or 360.0
    d = (h - lo) % 360.0
    inside = np.clip(d / soft, 0.0, 1.0) * np.clip((span - d) / soft, 0.0, 1.0)
    return np.where(d <= span, inside, 0.0).astype(np.float32)


def defringe(lin: np.ndarray, opt: dict, ppl: float) -> np.ndarray:
    amounts = {"purple": float(opt.get("defringePurple", 0) or 0) / 20.0, "green": float(opt.get("defringeGreen", 0) or 0) / 20.0}
    if max(amounts.values()) <= 0:
        return lin
    y = np.maximum(lin @ np.array([0.2627, 0.6780, 0.0593], np.float32), 1e-5)
    logl = np.log2(y).astype(np.float32)
    r = max(1, int(round(0.0016 * ppl)))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    spread = cv2.dilate(logl, k) - cv2.erode(logl, k)
    edge = np.clip((spread - 0.6) / 1.6, 0.0, 1.0)
    lab = colour.oklab_from_2020(np.clip(lin, 0.0, None) / max(1e-6, float(np.percentile(y, 99.5))))
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    hue = (np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) + 360.0) % 360.0
    weight = np.zeros(y.shape, np.float32)
    for kind, amt in amounts.items():
        if amt <= 0:
            continue
        lo, hi = hue_range(kind, opt.get(f"defringe{kind.title()}HueLo", 30 if kind == "purple" else 40), opt.get(f"defringe{kind.title()}HueHi", 70 if kind == "purple" else 60))
        weight = np.maximum(weight, amt * _window(hue, lo % 360.0, hi % 360.0))
    weight *= edge * np.clip((chroma - 0.015) / 0.05, 0.0, 1.0)
    weight = np.clip(weight, 0.0, 1.0)[..., None]
    grey = y[..., None]
    return (lin + (grey - lin) * weight).astype(np.float32)


def _radial(ch: np.ndarray, k: float) -> np.ndarray:
    h, w = ch.shape
    m = np.array([[1.0 + k, 0.0, -k * w / 2.0], [0.0, 1.0 + k, -k * h / 2.0]], np.float32)
    return cv2.warpAffine(ch, m, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT)


def estimate_ca(img: np.ndarray, long: int = 2000) -> tuple[float, float]:
    h, w = img.shape[:2]
    s = min(1.0, long / max(h, w))
    small = cv2.resize(img, (max(8, int(w * s)), max(8, int(h * s))), interpolation=cv2.INTER_AREA) if s < 1.0 else img
    lg = np.log2(np.maximum(small, 1e-4)).astype(np.float32)
    gx = cv2.Sobel(lg[..., 1], cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(lg[..., 1], cv2.CV_32F, 0, 1, ksize=3)
    mag = np.hypot(gx, gy)
    hh, ww = mag.shape
    yy, xx = np.mgrid[0:hh, 0:ww]
    rad = np.hypot((xx - ww / 2) / (ww / 2), (yy - hh / 2) / (hh / 2))
    mask = (mag > np.percentile(mag, 97)) & (rad > 0.35)
    if mask.sum() < 200:
        return 0.0, 0.0
    target = lg[..., 1][mask]
    out = []
    for c in (0, 2):
        ch = lg[..., c]
        offset = float(np.median(ch[mask] - target))

        def err(k: float) -> float:
            return float(np.mean((_radial(ch, k)[mask] - offset - target) ** 2))
        best = min((err(k), k) for k in np.arange(-0.004, 0.00401, 0.0005))[1]
        best = min((err(k), k) for k in np.arange(best - 0.0005, best + 0.00051, 0.0001))[1]
        out.append(round(float(best), 5) if abs(best) > 0.00005 else 0.0)
    return out[0], out[1]


def degrees(lab: list[float]) -> float:
    return (math.degrees(math.atan2(lab[2], lab[1])) + 360.0) % 360.0
