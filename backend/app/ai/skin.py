import cv2
import numpy as np


def _masked_blur(v: np.ndarray, m: np.ndarray, sigma: float) -> np.ndarray:
    num = cv2.GaussianBlur(v * m, (0, 0), sigma)
    den = cv2.GaussianBlur(m, (0, 0), sigma)
    return num / np.maximum(den, 1e-4)


def _robust(v: np.ndarray) -> float:
    if v.size < 16:
        return 1.0
    med = float(np.median(v))
    return 1.4826 * float(np.median(np.abs(v - med))) + 1e-6


def protect(shape: tuple[int, int], faces: list[dict]) -> np.ndarray:
    h, w = shape
    keep = np.zeros((h, w), np.uint8)
    for f in faces:
        x0, y0, x1, y1 = f["box"]
        fw = (x1 - x0) * w
        lm = [(p[0] * w, p[1] * h) for p in f.get("landmarks") or []]
        if len(lm) < 5:
            continue
        for (px, py), (rx, ry) in zip(lm, [(0.17, 0.11), (0.17, 0.11), (0.1, 0.09), (0.0, 0.0), (0.0, 0.0)]):
            if rx:
                cv2.ellipse(keep, (round(px), round(py)), (max(1, round(rx * fw)), max(1, round(ry * fw))), 0, 0, 360, 1, -1)
        (lx, ly), (rx_, ry_) = lm[3], lm[4]
        cx, cy = (lx + rx_) / 2, (ly + ry_) / 2
        half = max(4.0, abs(rx_ - lx) / 2 + 0.05 * fw)
        cv2.ellipse(keep, (round(cx), round(cy)), (round(half), max(2, round(0.08 * fw))), float(np.degrees(np.arctan2(ry_ - ly, rx_ - lx))), 0, 360, 1, -1)
    return keep > 0


def blemishes(rgb8: np.ndarray, skin: np.ndarray, faces: list[dict], sensitivity: float = 50.0, keep_freckles: bool = True, limit: int = 80) -> list[tuple[float, float, float, float]]:
    h, w = rgb8.shape[:2]
    if not faces:
        return []
    fw = float(np.median([(f["box"][2] - f["box"][0]) * w for f in faces]))
    if fw < 60:
        return []
    rmin, rmax = max(1.2, fw * 0.004), fw * 0.03
    lab = cv2.cvtColor(rgb8, cv2.COLOR_RGB2LAB).astype(np.float32)
    L, A = lab[..., 0] * (100.0 / 255.0), lab[..., 1] - 128.0
    m = (skin > 0.5).astype(np.uint8)
    m = cv2.erode(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * round(rmax) + 1,) * 2))
    m &= ~protect((h, w), faces)
    if m.sum() < 400:
        return []
    mf = m.astype(np.float32)
    bg_l = _masked_blur(L, mf, rmax * 1.5)
    bg_a = _masked_blur(A, mf, rmax * 1.5)
    fine_l = cv2.GaussianBlur(L, (0, 0), max(0.6, rmin * 0.5))
    fine_a = cv2.GaussianBlur(A, (0, 0), max(0.6, rmin * 0.5))
    dark, red = bg_l - fine_l, fine_a - bg_a
    inside = m > 0
    sd_l, sd_a = _robust(dark[inside]), _robust(red[inside])
    score = np.maximum(dark / sd_l, 0) + 0.8 * np.maximum(red / sd_a, 0)
    thr = 7.0 - 4.0 * min(max(sensitivity, 0.0), 100.0) / 100.0
    cand = ((score > thr) & inside).astype(np.uint8)
    n, lab_img, stats, cents = cv2.connectedComponentsWithStats(cand, connectivity=8)
    found = []
    for k in range(1, n):
        area = stats[k, cv2.CC_STAT_AREA]
        r = float(np.sqrt(area / np.pi))
        if r < rmin * 0.6 or r > rmax:
            continue
        x0, y0, bw, bh = stats[k, 0], stats[k, 1], stats[k, 2], stats[k, 3]
        sel = lab_img[y0:y0 + bh, x0:x0 + bw] == k
        ys, xs = np.nonzero(sel)
        if len(xs) >= 5:
            cov = np.cov(np.vstack([xs, ys]).astype(np.float64))
            ev = np.linalg.eigvalsh(cov)
            if ev[1] > 6.0 * max(ev[0], 0.25):
                continue
        s = score[y0:y0 + bh, x0:x0 + bw][sel]
        da = float(red[y0:y0 + bh, x0:x0 + bw][sel].max())
        dl = float(dark[y0:y0 + bh, x0:x0 + bw][sel].max())
        if max(da, dl) < 3.0:
            continue
        found.append((float(cents[k][0]), float(cents[k][1]), r, float(s.max()), da >= 3.0 and da >= 0.8 * dl))
    if keep_freckles:
        found = [f for f in found if f[4]]
    found.sort(key=lambda f: -f[3])
    return [(x, y, max(r * 1.8 + 1.0, rmin * 2.0), s) for x, y, r, s, _ in found[:limit]]
