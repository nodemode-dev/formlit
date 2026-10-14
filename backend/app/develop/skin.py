import math

import cv2
import numpy as np

from app.develop.settings import section_enabled

KR, KB = 0.299, 0.114
KG = 1.0 - KR - KB
DEFAULT_HUE = 131.0
DEFAULT_RANGE = 30.0
COLOR_SIGMA = 0.010
LUM_SIGMA = 0.005


def _params(eff: dict) -> tuple[float, float, float, float, float] | None:
    s = eff.get("skin") if isinstance(eff, dict) else None
    if not isinstance(s, dict) or not section_enabled(eff, "mixer"):
        return None
    u = [min(max(float(s.get(k, 0) or 0), 0.0), 100.0) / 100.0 for k in ("hueUniformity", "satUniformity", "lumUniformity")]
    if not any(u):
        return None
    return float(s.get("hue", DEFAULT_HUE)), max(2.0, float(s.get("range", DEFAULT_RANGE))), u[0], u[1], u[2]


def active(eff: dict) -> bool:
    return _params(eff) is not None


def to_ycc(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    y = KR * r + KG * g + KB * b
    return y, (b - y) / (2.0 * (1.0 - KB)), (r - y) / (2.0 * (1.0 - KR))


def from_ycc(y: np.ndarray, cb: np.ndarray, cr: np.ndarray) -> np.ndarray:
    r = y + 2.0 * (1.0 - KR) * cr
    b = y + 2.0 * (1.0 - KB) * cb
    g = (y - KR * r - KB * b) / KG
    return np.stack([r, g, b], axis=-1)


def hue_of(rgb: np.ndarray) -> tuple[float, float]:
    y, cb, cr = to_ycc(np.asarray(rgb, np.float64).reshape(-1, 3).mean(axis=0))
    return (math.degrees(math.atan2(float(cr), float(cb))) % 360.0), float(math.hypot(float(cb), float(cr)))


def weight(y: np.ndarray, cb: np.ndarray, cr: np.ndarray, hue: float, width: float) -> np.ndarray:
    ang = np.arctan2(cr, cb)
    d = np.abs((ang - math.radians(hue) + math.pi) % (2.0 * math.pi) - math.pi)
    w0 = math.radians(width)
    wh = np.clip((1.5 * w0 - d) / (0.5 * w0), 0.0, 1.0)
    wh = wh * wh * (3.0 - 2.0 * wh)
    mag = np.hypot(cb, cr)
    wc = np.clip((mag - 0.012) / 0.03, 0.0, 1.0)
    wy = np.clip((y - 0.04) / 0.08, 0.0, 1.0) * np.clip((0.985 - y) / 0.08, 0.0, 1.0)
    return (wh * wc * wy).astype(np.float32)


def apply(out: np.ndarray, eff: dict, ppl: float) -> np.ndarray:
    p = _params(eff)
    if p is None or out.ndim != 3 or out.shape[2] < 3:
        return out
    hue, width, uh, us, ul = p
    rgb = np.ascontiguousarray(out[..., :3], np.float32)
    y, cb, cr = to_ycc(rgb)
    w = weight(y, cb, cr, hue, width)
    if not np.any(w > 1e-3):
        return out
    sc = max(1.0, COLOR_SIGMA * float(ppl))
    sl = max(1.0, LUM_SIGMA * float(ppl))

    def blur(a: np.ndarray, s: float) -> np.ndarray:
        return cv2.GaussianBlur(a, (0, 0), s, borderType=cv2.BORDER_REFLECT)

    ww = blur(w, sc) + 1e-6
    mcb, mcr = blur(cb * w, sc) / ww, blur(cr * w, sc) / ww
    mag = np.hypot(cb, cr)
    ang = np.arctan2(cr, cb)
    mean_ang = np.arctan2(mcr, mcb)
    mean_mag = blur(mag * w, sc) / ww
    d = (mean_ang - ang + np.pi) % (2.0 * np.pi) - np.pi
    ang2 = ang + d * (uh * w)
    mag2 = mag + (mean_mag - mag) * (us * w)
    y2 = y + (blur(y, sl) - y) * (ul * w)
    res = from_ycc(y2, mag2 * np.cos(ang2), mag2 * np.sin(ang2)).astype(np.float32)
    top = max(1.0, float(rgb.max()))
    result = out.copy()
    result[..., :3] = np.clip(res, 0.0, top)
    return result
