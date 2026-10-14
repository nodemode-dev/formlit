import cv2
import numpy as np

from app.ai import merge

LW = np.array([0.2126, 0.7152, 0.0722], np.float32)


def _lum(img: np.ndarray) -> np.ndarray:
    return np.maximum(img @ LW, 1e-6)


def _align(ref: np.ndarray, img: np.ndarray) -> np.ndarray:
    a = cv2.cvtColor(merge._proxy8(ref, 1600, 1.0 / max(1e-6, float(np.percentile(ref, 99)))), cv2.COLOR_RGB2GRAY)
    b = cv2.cvtColor(merge._proxy8(img, 1600, 1.0 / max(1e-6, float(np.percentile(img, 99)))), cv2.COLOR_RGB2GRAY)
    dx, dy = cv2.createAlignMTB().calculateShift(a, b)
    s = ref.shape[1] / a.shape[1]
    return merge._shift(img, -dx * s, -dy * s)


def windows(radiance: np.ndarray, room: float, stops: float = 2.0) -> np.ndarray:
    h, w = radiance.shape[:2]
    y = _lum(radiance)
    bright = (np.log2(y / room) > stops).astype(np.uint8)
    k = max(3, round(max(h, w) / 160)) | 1
    closed = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    keep = np.zeros((h, w), np.uint8)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= 0.002 * h * w:
            keep[lab == i] = 1
    filled = keep.copy()
    contours, _ = cv2.findContours(keep, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(filled, contours, -1, 1, -1)
    soft = cv2.GaussianBlur(cv2.dilate(filled, np.ones((k, k), np.uint8)).astype(np.float32), (0, 0), k / 2)
    core = cv2.GaussianBlur(cv2.erode(filled, np.ones((2 * k + 1, 2 * k + 1), np.uint8)).astype(np.float32), (0, 0), k / 2)
    return np.stack([np.clip(soft, 0.0, 1.0), np.clip(core, 0.0, 1.0)])


def blend(ambients: list[np.ndarray], factors: list[float | None], flash: np.ndarray | None, flash_amount: float = 50.0, color_amount: float = 100.0,
          window_ev: float = 1.5, pull: bool = True, progress=None) -> tuple[np.ndarray, dict]:
    say = progress or (lambda a, b, label: None)
    amb = merge.hdr(ambients, factors, "off", None, True) if len(ambients) > 1 else ambients[0].astype(np.float32)
    say(1, 4, "Merging the ambient frames")
    ya = _lum(amb)
    room_mask = ya < np.percentile(ya, 80)
    room = float(np.median(ya[room_mask]))
    win, core = windows(amb, room) if pull else np.zeros((2,) + ya.shape, np.float32)
    report = {"windows": round(float((win > 0.5).mean()), 4), "flash": flash is not None}
    out = amb
    if flash is not None:
        fl = _align(amb, flash.astype(np.float32))
        say(2, 4, "Aligning the flash frame")
        inside = (win < 0.05) & (fl.max(axis=2) < 0.92) & (ya > room * 0.05)
        k = float(np.median(ya[inside] / _lum(fl)[inside])) if inside.any() else 1.0
        fl = fl * k
        yf = _lum(fl)
        f, c = min(max(flash_amount, 0.0), 100.0) / 100.0, min(max(color_amount, 0.0), 100.0) / 100.0
        y = (1.0 - f) * ya + f * yf
        chroma = (1.0 - c) * (amb / ya[..., None]) + c * (fl / yf[..., None])
        out = chroma * y[..., None]
        report["flashScale"] = round(k, 4)
    if pull and report["windows"] > 0:
        sel = win > 0.5
        y_win, y_top = float(np.median(ya[sel])), float(np.percentile(ya[sel], 97))
        g = min(room * 2.0 ** window_ev / max(y_win, 1e-6), room * 4.5 / max(y_top, 1e-6), 1.0)
        p = amb * g
        glow = np.clip(np.log2(ya / room) - 1.5, 0.0, 1.0)
        m = np.maximum(core, win * glow)[..., None]
        out = out * (1.0 - m) + np.minimum(out, p) * m
        report["windowGain"] = round(float(np.log2(max(g, 1e-9))), 2)
    say(4, 4, "Blending")
    return np.maximum(out, 0.0).astype(np.float32), report
