import cv2
import numpy as np


def _encode(lin: np.ndarray, peak: float) -> np.ndarray:
    return (np.sqrt(np.clip(lin / peak, 0.0, 1.0)) * 255 + 0.5).astype(np.uint8)


def crossing(orig: np.ndarray, hole: np.ndarray, r: float, limit: int = 12) -> list[tuple[np.ndarray, np.ndarray, float]]:
    peak = max(1e-6, float(np.percentile(orig, 99.5)))
    g = cv2.cvtColor(_encode(orig, peak), cv2.COLOR_RGB2GRAY)
    found = cv2.createLineSegmentDetector().detect(g)[0]
    if found is None:
        return []
    near = cv2.dilate(hole.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=2) > 0
    reach = cv2.dilate(hole.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=max(4, int(r * 1.5))) > 0
    h, w = hole.shape
    ys, xs = np.nonzero(hole)
    diag = float(np.hypot(xs.max() - xs.min(), ys.max() - ys.min())) + 2.0
    out = []
    for x0, y0, x1, y1 in found.reshape(-1, 4):
        length = float(np.hypot(x1 - x0, y1 - y0))
        if length < max(10.0, 0.6 * r):
            continue
        a, b = np.array([x0, y0]), np.array([x1, y1])
        ia, ib = (int(round(a[1])), int(round(a[0]))), (int(round(b[1])), int(round(b[0])))
        if not (0 <= ia[0] < h and 0 <= ia[1] < w and 0 <= ib[0] < h and 0 <= ib[1] < w) or near[ia] or near[ib]:
            continue
        end = a if reach[ia] and not reach[ib] else b if reach[ib] and not reach[ia] else (a if np.hypot(*(a - [xs.mean(), ys.mean()])) < np.hypot(*(b - [xs.mean(), ys.mean()])) else b)
        if not reach[int(round(end[1])), int(round(end[0]))]:
            continue
        d = (b - a) / length
        if np.dot(d, [xs.mean(), ys.mean()] - end) < 0:
            d = -d
        t = np.arange(0.0, diag + 2 * r, 0.5)
        pts = end[None, :] + t[:, None] * d[None, :]
        inside = (pts[:, 0] >= 0) & (pts[:, 0] < w) & (pts[:, 1] >= 0) & (pts[:, 1] < h)
        pts = pts[inside]
        if not len(pts):
            continue
        hit = hole[pts[:, 1].astype(int), pts[:, 0].astype(int)] > 0
        if not hit.any():
            continue
        span = float(((np.stack([xs, ys], 1) - end) @ d).max())
        n = np.array([-d[1], d[0]])
        far = None
        for q in found.reshape(-1, 4):
            qa, qb = q[:2] - end, q[2:] - end
            ql = float(np.hypot(*(qb - qa)))
            if ql < 6.0 or abs(float(d[0] * (qb - qa)[1] - d[1] * (qb - qa)[0])) / ql > 0.07 or max(abs(qa @ n), abs(qb @ n)) > max(2.5, 0.05 * r):
                continue
            if min(qa @ d, qb @ d) > 0.5 * span:
                far = min(far if far is not None else 1e9, float(min(qa @ d, qb @ d)))
        if far is None:
            continue
        out.append((end, d, length, far))
    out.sort(key=lambda s: -s[2])
    return out[:limit]


def carry(orig: np.ndarray, fill: np.ndarray, hole: np.ndarray, r: float) -> tuple[np.ndarray, int]:
    segs = crossing(orig, hole, r)
    if not segs:
        return fill, 0
    h, w = hole.shape
    half = max(2.0, min(6.0, r * 0.12))
    over = np.zeros_like(fill)
    weight = np.zeros(hole.shape, np.float32)
    grow = cv2.dilate(hole.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=2) > 0
    for end, d, length, far in segs:
        n = np.array([-d[1], d[0]])
        back = end - d * 3.0
        offs = np.arange(-half, half + 0.5, 0.5)
        steps = np.linspace(3.0, max(3.0, min(length - 2.0, 3.0 + 8.0 * half)), 7)
        src = end[None, None, :] - steps[:, None, None] * d[None, None, :] + offs[None, :, None] * n[None, None, :]
        mx, my = src[..., 0].astype(np.float32), src[..., 1].astype(np.float32)
        prof = np.median(cv2.remap(orig.astype(np.float32), mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT), 0)
        bx, by, k = int(round(back[0])), int(round(back[1])), int(half * 4)
        win = orig[max(0, by - k):by + k + 1, max(0, bx - k):bx + k + 1].reshape(-1, orig.shape[2])
        if not len(win):
            continue
        dl = (prof - np.median(win, 0)).mean(1)
        sig = np.clip((np.abs(dl) / (np.abs(dl).max() + 1e-6) - 0.25) / 0.35, 0.0, 1.0)
        if np.abs(dl).max() < 0.02 * float(np.percentile(win, 99.5)) + 1e-6:
            continue
        ys, xs = np.nonzero(grow)
        rel = np.stack([xs - end[0], ys - end[1]], 1).astype(np.float32)
        along, across = rel @ d, rel @ n
        sel = (along > 0) & (along <= far + 2.0) & (np.abs(across) <= half)
        if not sel.any():
            continue
        idx = np.clip(np.round((across[sel] + half) / 0.5).astype(int), 0, len(offs) - 1)
        fade = np.clip(1.0 - along[sel] / (along[sel].max() + 1e-6) * 0.35, 0.0, 1.0) * sig[idx]
        yy, xx = ys[sel], xs[sel]
        better = fade > weight[yy, xx]
        over[yy[better], xx[better]] = prof[idx[better]]
        weight[yy[better], xx[better]] = fade[better]
    weight = cv2.GaussianBlur(weight, (0, 0), 0.8) * (grow > 0)
    out = fill * (1.0 - weight[..., None]) + over * weight[..., None]
    return out.astype(fill.dtype), len(segs)
