import cv2
import numpy as np


def _box(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def attached(rgb8: np.ndarray, obj: np.ndarray, reflections: bool = True) -> tuple[np.ndarray, dict]:
    h, w = obj.shape
    m = (obj > 0).astype(np.uint8)
    box = _box(m)
    report = {"shadow": 0, "reflection": False}
    if box is None:
        return np.zeros((h, w), np.uint8), report
    x0, y0, x1, y1 = box
    s = max(x1 - x0, y1 - y0)
    sx0, sy0 = max(0, x0 - int(4 * s)), max(0, y0 - int(1.5 * s))
    sx1, sy1 = min(w, x1 + int(4 * s)), min(h, y1 + 2 * s)
    crop = rgb8[sy0:sy1, sx0:sx1]
    cm = m[sy0:sy1, sx0:sx1]
    lin = (crop.astype(np.float32) / 255.0) ** 2.2 @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    scale = min(1.0, 256.0 / max(crop.shape[:2]))
    small = lambda a, interp=cv2.INTER_AREA: cv2.resize(a, (max(1, round(a.shape[1] * scale)), max(1, round(a.shape[0] * scale))), interpolation=interp)
    hole = small(cv2.dilate(cm, np.ones((3, 3), np.uint8), iterations=max(1, s // 40)), cv2.INTER_NEAREST)
    big = lambda a: cv2.resize(a, (crop.shape[1], crop.shape[0]), interpolation=cv2.INTER_LINEAR)
    enc = np.clip(np.sqrt(small(lin)) * 255, 0, 255).astype(np.uint8)
    filled = (cv2.inpaint(enc, hole, 5, cv2.INPAINT_TELEA).astype(np.float32) / 255.0) ** 2
    filled = cv2.GaussianBlur(filled, (0, 0), max(0.8, 0.03 * s * scale))
    rgb_s = small((crop.astype(np.float32) / 255.0) ** 2.2)
    chrom = (rgb_s[..., :2] / np.maximum(rgb_s.sum(-1, keepdims=True), 1e-4)).reshape(-1, 2).astype(np.float32)
    _, labels, _ = cv2.kmeans(chrom, 4, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1e-3), 2, cv2.KMEANS_PP_CENTERS)
    labels = labels.reshape(filled.shape)
    ks = (2 * max(2, round(0.6 * s * scale)) + 1,) * 2
    bg_small = np.zeros_like(filled)
    for c in range(4):
        mc = ((labels == c) & (hole == 0)).astype(np.float32)
        n = np.maximum(cv2.boxFilter(mc, -1, ks, normalize=False), 1.0)
        mu = cv2.boxFilter(filled * mc, -1, ks, normalize=False) / n
        sd = np.sqrt(np.maximum(cv2.boxFilter(filled * filled * mc, -1, ks, normalize=False) / n - mu * mu, 0.0))
        bg_small = np.where(labels == c, mu + 0.7 * sd, bg_small)
    bg_l = big(cv2.GaussianBlur(bg_small, (0, 0), max(1.0, 0.05 * s * scale)))
    lin = cv2.GaussianBlur(lin, (0, 0), max(0.8, 0.03 * s))
    plain = chrom.reshape(filled.shape + (2,))
    bg_rg = [cv2.GaussianBlur(big(cv2.inpaint(np.clip(plain[..., c] * 255, 0, 255).astype(np.uint8), hole, 5, cv2.INPAINT_TELEA).astype(np.float32) / 255.0), (0, 0), max(1.0, 0.04 * s)) for c in (0, 1)]
    full_rgb = (crop.astype(np.float32) / 255.0) ** 2.2
    rg = full_rgb[..., :2] / np.maximum(full_rgb.sum(-1, keepdims=True), 1e-4)
    ratio = lin / np.maximum(bg_l, 1e-5)
    chroma = np.hypot(cv2.GaussianBlur(rg[..., 0], (0, 0), 1.0) - bg_rg[0], cv2.GaussianBlur(rg[..., 1], (0, 0), 1.0) - bg_rg[1])
    cand = ((ratio < 0.72) & (chroma < 0.06) & (cm == 0)).astype(np.uint8)
    k = max(3, (s // 30) | 1)
    cand = cv2.morphologyEx(cand, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    rows = np.nonzero(cm.any(axis=1))[0]
    foot = cm.copy()
    if len(rows):
        foot[: rows[0] + int(0.7 * (rows[-1] - rows[0] + 1))] = 0
    near = cv2.dilate(foot, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * int(0.12 * s) + 1,) * 2))
    n, lab_img = cv2.connectedComponents(cand, connectivity=8)
    shadow = np.zeros_like(cand)
    edge = np.zeros_like(cand, bool)
    if sx0 > 0:
        edge[:, 0] = True
    if sx1 < w:
        edge[:, -1] = True
    if sy1 < h:
        edge[-1, :] = True
    if sy0 > 0:
        edge[0, :] = True
    around = cv2.dilate(cm, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * int(0.06 * s) + 1,) * 2))
    fy = int(rows[-1]) if len(rows) else 0
    fx = np.nonzero(cm[max(0, fy - int(0.1 * s)):fy + 1].any(axis=0))[0]
    for i in range(1, n):
        comp = lab_img == i
        if (comp & edge).any():
            continue
        if (comp & (near > 0)).any():
            shadow |= comp.astype(np.uint8)
            continue
        if not len(fx) or not (comp & (around > 0)).any():
            continue
        ys, xs = np.nonzero(comp)
        if len(xs) < 20 or ys.mean() >= fy:
            continue
        ev, vec = np.linalg.eigh(np.cov(np.vstack([xs, ys]).astype(np.float64)))
        if ev[1] < 9.0 * max(ev[0], 1e-6) or abs(vec[1, 1]) < 1e-3:
            continue
        x_at_foot = xs.mean() + (fy - ys.mean()) * vec[0, 1] / vec[1, 1]
        if fx.min() - 0.15 * s <= x_at_foot <= fx.max() + 0.15 * s:
            shadow |= comp.astype(np.uint8)
    shadow = cv2.morphologyEx(shadow, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    if shadow.sum() > 6 * m.sum():
        shadow[:] = 0
    out = np.zeros((h, w), np.uint8)
    out[sy0:sy1, sx0:sx1] = shadow
    report["shadow"] = int(shadow.sum())
    if reflections and y1 + (y1 - y0) // 2 < h:
        bh = y1 - y0
        below = rgb8[y1:min(h, y1 + bh), x0:x1]
        above = rgb8[y0:y1, x0:x1][::-1][:below.shape[0]]
        if below.shape[0] >= 8 and below.shape[1] >= 8:
            g = lambda a: cv2.Sobel(cv2.cvtColor(a, cv2.COLOR_RGB2GRAY).astype(np.float32), cv2.CV_32F, 1, 0)
            a, b = g(above), g(below)
            fm = m[y0:y1, x0:x1][::-1][:below.shape[0]] > 0
            if fm.sum() > 30:
                va, vb = a[fm] - a[fm].mean(), b[fm] - b[fm].mean()
                ncc = float((va * vb).sum() / (np.sqrt((va ** 2).sum() * (vb ** 2).sum()) + 1e-6))
                report["reflectionMatch"] = round(ncc, 3)
                if ncc > 0.35:
                    mirror = np.zeros((h, w), np.uint8)
                    mirror[y1:y1 + below.shape[0], x0:x1] = fm.astype(np.uint8)
                    out |= cv2.dilate(mirror, np.ones((3, 3), np.uint8), iterations=max(1, s // 60))
                    report["reflection"] = True
    return out, report
