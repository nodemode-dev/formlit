import cv2
import numpy as np

from app.ai import nets
from app.develop.masks import guided_cross

LW = np.array([0.2627, 0.6780, 0.0593], np.float32)


def _encode(lin: np.ndarray) -> tuple[np.ndarray, float]:
    peak = max(1e-6, float(np.percentile(lin, 99.98)))
    return np.sqrt(np.clip(lin / peak, 0.0, 1.0)).astype(np.float32), peak


def _decode(enc: np.ndarray, peak: float, lin: np.ndarray) -> np.ndarray:
    out = (np.clip(enc, 0.0, 1.0) ** 2) * peak
    over = lin > peak
    return np.where(over, lin, out).astype(np.float32)


def noise_sigma(y: np.ndarray) -> float:
    small = y if max(y.shape) <= 2048 else cv2.resize(y, (y.shape[1] // 2, y.shape[0] // 2), interpolation=cv2.INTER_AREA)
    hp = np.abs(small - cv2.GaussianBlur(small, (0, 0), 1.0))
    blocks = cv2.resize(hp, (max(1, hp.shape[1] // 16), max(1, hp.shape[0] // 16)), interpolation=cv2.INTER_AREA)
    return float(np.percentile(blocks, 10) * 1.4826 * 1.25)


def denoise(lin: np.ndarray, amount: float = 50.0, progress=None) -> np.ndarray:
    enc, peak = _encode(lin)
    y = enc @ LW
    chroma = enc - y[..., None]
    sigma = noise_sigma(y)
    k = max(0.05, amount / 50.0)
    h16 = float(np.clip(sigma * 65535.0 * 1.05 * k, 120.0, 20000.0))
    if progress is not None:
        progress(1, 4, "Denoise: luminance")
    y16 = np.clip(y * 65535.0 + 0.5, 0, 65535).astype(np.uint16)
    yd = cv2.fastNlMeansDenoising(y16, h=[h16], templateWindowSize=7, searchWindowSize=15, normType=cv2.NORM_L1).astype(np.float32) / 65535.0
    if progress is not None:
        progress(2, 4, "Denoise: color")
    radius = max(1.5, 2.0 * k * (sigma / 0.004) ** 0.5)
    cd = np.stack([guided_cross(yd, chroma[..., i] + 0.5, radius, 1e-4) - 0.5 for i in range(3)], axis=-1)
    detail = 0.35 * (1.0 - min(1.0, k / 2.0))
    yd = yd + detail * (y - yd)
    out = np.clip(yd[..., None] + cd, 0.0, 1.0)
    if progress is not None:
        progress(3, 4, "Denoise: finishing")
    return _decode(out, peak, lin)


def superres(lin: np.ndarray, progress=None) -> np.ndarray:
    enc, peak = _encode(lin)
    rgb8 = (enc * 255 + 0.5).astype(np.uint8)
    up8 = nets.esrgan(rgb8, progress)
    h, w = lin.shape[:2]
    up = cv2.resize(up8, (w * 2, h * 2), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    base = cv2.resize(enc, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
    lo = cv2.GaussianBlur(up, (0, 0), 1.2)
    merged = cv2.GaussianBlur(base, (0, 0), 1.2) + (up - lo)
    return _decode(np.clip(merged, 0.0, 1.0), peak, cv2.resize(lin, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC))


def raw_details(path, progress=None) -> tuple[np.ndarray, dict]:
    from app.services.decode import _raw_linear
    if progress is not None:
        progress(1, 3, "Raw Details: demosaicing")
    lin, info = _raw_linear(path, None, True, "DCB")
    enc, peak = _encode(lin)
    y = enc @ LW
    if progress is not None:
        progress(2, 3, "Raw Details: edges")
    fine = y - cv2.GaussianBlur(y, (0, 0), 0.8)
    sigma = noise_sigma(y)
    gate = np.clip((np.abs(fine) - 1.5 * sigma) / max(2.0 * sigma, 1e-4), 0.0, 1.0)
    out = np.clip(enc + (0.45 * fine * gate)[..., None], 0.0, 1.0)
    return _decode(out, peak, lin), info
