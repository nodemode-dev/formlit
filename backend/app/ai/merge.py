import math

import cv2
import numpy as np


def _proxy8(lin: np.ndarray, long: int, gain: float = 1.0) -> np.ndarray:
    h, w = lin.shape[:2]
    s = min(1.0, long / max(h, w))
    small = cv2.resize(lin, (max(1, round(w * s)), max(1, round(h * s))), interpolation=cv2.INTER_AREA) if s < 1 else lin
    enc = np.sqrt(np.clip(small * gain, 0.0, 1.0))
    return (enc * 255 + 0.5).astype(np.uint8)


def exposure_factor(row: dict) -> float | None:
    t, n, iso = row.get("shutter"), row.get("aperture"), row.get("iso")
    if not t or not n:
        return None
    return float(t) * float(iso or 100) / (float(n) ** 2)


def _shift(img: np.ndarray, dx: float, dy: float) -> np.ndarray:
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return img
    m = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(img, m, (img.shape[1], img.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def hdr(images: list[np.ndarray], factors: list[float | None], deghost: str = "off", progress=None, align: bool = True, ghosts: list | None = None) -> np.ndarray:
    n = len(images)
    if n < 2:
        raise ValueError("HDR merge needs two or more photos")
    h, w = images[0].shape[:2]
    for im in images:
        if im.shape[:2] != (h, w):
            raise ValueError("HDR merge needs photos of the same size and orientation")
    known = [f for f in factors if f]
    ks: list[float] = []
    ref_i = int(np.argsort([float(np.median(im)) for im in images])[n // 2])
    for i, im in enumerate(images):
        if factors[i] and factors[ref_i] and len(known) == n:
            ks.append(float(factors[i]) / float(factors[ref_i]))
        else:
            a, b = images[ref_i], im
            m = (a.max(axis=2) < 0.8) & (b.max(axis=2) < 0.8) & (a.max(axis=2) > 0.01) & (b.max(axis=2) > 0.01)
            ks.append(float(np.median(b.mean(axis=2)[m] / np.maximum(a.mean(axis=2)[m], 1e-6))) if np.any(m) else 1.0)
    ref8 = cv2.cvtColor(_proxy8(images[ref_i], 1600, 1.0 / max(1e-6, float(np.percentile(images[ref_i], 99)))), cv2.COLOR_RGB2GRAY)
    scale = images[0].shape[1] / ref8.shape[1]
    mtb = cv2.createAlignMTB()
    aligned = []
    for i, im in enumerate(images):
        if i == ref_i or not align:
            aligned.append(im)
            continue
        g = cv2.cvtColor(_proxy8(im, 1600, 1.0 / max(1e-6, float(np.percentile(im, 99)))), cv2.COLOR_RGB2GRAY)
        dx, dy = mtb.calculateShift(ref8, g)
        aligned.append(_shift(im, -dx * scale, -dy * scale))
        if progress is not None:
            progress(i + 1, n + 2, "Aligning")
    acc = np.zeros((h, w, 3), np.float32)
    wsum = np.zeros((h, w), np.float32)
    ref_norm = aligned[ref_i] / ks[ref_i]
    order = np.argsort(ks)
    darkest = aligned[int(order[0])] / ks[int(order[0])]
    for i in range(n):
        im = aligned[i]
        mx = im.max(axis=2)
        wt = np.clip((0.92 - mx) / 0.12, 0.0, 1.0) * np.clip((mx - 0.0015) / 0.01, 0.0, 1.0) * math.sqrt(ks[i])
        norm = im / ks[i]
        if deghost != "off" and i != ref_i:
            thr = {"low": 1.2, "medium": 0.8, "high": 0.5}.get(deghost, 0.8)
            diff = np.abs(np.log2(np.maximum(norm.mean(axis=2), 1e-5)) - np.log2(np.maximum(ref_norm.mean(axis=2), 1e-5)))
            if ghosts is not None:
                ghosts.append((diff >= thr) & (wt > 0))
            wt = wt * (diff < thr)
        acc += norm * wt[..., None]
        wsum += wt
        if progress is not None:
            progress(n + 1, n + 2, "Merging")
    out = np.where((wsum > 1e-6)[..., None], acc / np.maximum(wsum, 1e-6)[..., None], darkest)
    return np.maximum(out, 0.0).astype(np.float32)


def pano(images: list[np.ndarray], projection: str = "spherical", progress=None, max_pixels: float = 80e6, boundary: float = 0.0, fill: bool = False,
         crop: bool = True) -> np.ndarray:
    if len(images) < 2:
        raise ValueError("Panorama merge needs two or more photos")
    gain = 1.0 / max(1e-6, float(np.median([np.percentile(im, 99) for im in images])))
    proxies = [cv2.cvtColor(_proxy8(im, 1600, gain), cv2.COLOR_RGB2BGR) for im in images]
    st = cv2.Stitcher_create(cv2.Stitcher_PANORAMA)
    status = st.estimateTransform(proxies)
    if status != 0:
        raise ValueError("These photos do not overlap enough to merge into a panorama")
    cams = st.cameras()
    comp = st.component()
    idx = [int(i) for i in (comp if comp is not None else range(len(images)))]
    if len(idx) < 2:
        raise ValueError("Only one photo could be placed in the panorama")
    total = sum(images[i].shape[0] * images[i].shape[1] for i in idx)
    down = min(1.0, math.sqrt(max_pixels / max(1.0, total * 1.6)))
    work = st.workScale()
    focals = []
    sets = []
    for c, i in zip(cams, idx):
        im = images[i]
        if down < 1.0:
            im = cv2.resize(im, (max(1, round(im.shape[1] * down)), max(1, round(im.shape[0] * down))), interpolation=cv2.INTER_AREA)
        s = im.shape[1] / (proxies[i].shape[1] * work)
        k = c.K().astype(np.float32)
        k[0, 0] *= s
        k[1, 1] *= s
        k[0, 2] *= s
        k[1, 2] *= s
        focals.append(float(k[0, 0]))
        sets.append((im, k, c.R.astype(np.float32)))
    warper = cv2.PyRotationWarper(projection if projection in ("spherical", "cylindrical", "plane") else "spherical", float(np.median(focals)))
    tiles = []
    for n, (im, k, r) in enumerate(sets):
        corner, warped = warper.warp(np.ascontiguousarray(im, np.float32), k, r, cv2.INTER_LINEAR, cv2.BORDER_CONSTANT)
        _, mask = warper.warp(np.full(im.shape[:2], 255, np.uint8), k, r, cv2.INTER_NEAREST, cv2.BORDER_CONSTANT)
        wt = cv2.distanceTransform((mask > 127).astype(np.uint8), cv2.DIST_L2, 3).astype(np.float32)
        wt = np.minimum(wt / max(1.0, float(wt.max()) * 0.25), 1.0) ** 2
        tiles.append((corner, warped, wt))
        if progress is not None:
            progress(n + 1, len(sets) + 1, "Warping")
    x0 = min(t[0][0] for t in tiles)
    y0 = min(t[0][1] for t in tiles)
    x1 = max(t[0][0] + t[1].shape[1] for t in tiles)
    y1 = max(t[0][1] + t[1].shape[0] for t in tiles)
    acc = np.zeros((y1 - y0, x1 - x0, 3), np.float32)
    wsum = np.zeros((y1 - y0, x1 - x0), np.float32)
    for (cx, cy), warped, wt in tiles:
        ys, xs = cy - y0, cx - x0
        hh, ww = warped.shape[:2]
        acc[ys:ys + hh, xs:xs + ww] += warped * wt[..., None]
        wsum[ys:ys + hh, xs:xs + ww] += wt
    covered = wsum > 1e-6
    out = np.where(covered[..., None], acc / np.maximum(wsum, 1e-6)[..., None], 0.0)
    return finish_pano(np.maximum(out, 0.0).astype(np.float32), covered, boundary, fill, crop)


def _edges(covered: np.ndarray, axis: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    m = covered if axis == 0 else covered.T
    n = m.shape[0]
    has = m.any(axis=0)
    lo = np.where(has, m.argmax(axis=0), 0).astype(np.float32)
    hi = np.where(has, n - 1 - m[::-1].argmax(axis=0), n - 1).astype(np.float32)
    k = max(3, (m.shape[1] // 60) | 1)
    lo = cv2.GaussianBlur(lo.reshape(1, -1), (k, 1), 0).ravel()
    hi = cv2.GaussianBlur(hi.reshape(1, -1), (k, 1), 0).ravel()
    return lo, hi, has


def boundary_warp(img: np.ndarray, covered: np.ndarray, amount: float) -> tuple[np.ndarray, np.ndarray]:
    a = max(0.0, min(1.0, amount / 100.0))
    if a <= 0:
        return img, covered
    for axis in (0, 1):
        h, w = covered.shape
        lo, hi, has = _edges(covered, axis)
        n = h if axis == 0 else w
        t = np.linspace(0.0, 1.0, n, dtype=np.float32)
        span = np.where(has, hi - lo, n - 1)
        src = lo[None, :] + t[:, None] * span[None, :]
        pos = np.arange(n, dtype=np.float32)[:, None]
        src = pos * (1.0 - a) + src * a
        if axis == 0:
            map_y = src
            map_x = np.broadcast_to(np.arange(w, dtype=np.float32)[None, :], (h, w)).copy()
        else:
            map_x = src.T.copy()
            map_y = np.broadcast_to(np.arange(h, dtype=np.float32)[:, None], (h, w)).copy()
        img = cv2.remap(img, map_x.astype(np.float32), map_y.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        covered = cv2.remap(covered.astype(np.uint8) * 255, map_x.astype(np.float32), map_y.astype(np.float32), cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT) > 127
    return img, covered


def fill_edges(img: np.ndarray, covered: np.ndarray) -> np.ndarray:
    hole = ~covered
    if not hole.any():
        return img
    h, w = covered.shape
    s = min(1.0, 1200.0 / max(h, w))
    sw, sh = max(1, round(w * s)), max(1, round(h * s))
    small = cv2.resize(img, (sw, sh), interpolation=cv2.INTER_AREA)
    small_hole = (cv2.resize(hole.astype(np.uint8) * 255, (sw, sh), interpolation=cv2.INTER_NEAREST) > 0).astype(np.uint8)
    small_hole = cv2.dilate(small_hole, np.ones((3, 3), np.uint8))
    enc = np.log2(np.maximum(small, 1e-5)).astype(np.float32)
    filled = np.stack([cv2.inpaint(np.ascontiguousarray(enc[..., c]), small_hole, 6, cv2.INPAINT_TELEA) for c in range(3)], axis=-1)
    big = np.exp2(cv2.resize(filled, (w, h), interpolation=cv2.INTER_CUBIC)).astype(np.float32)
    soft = cv2.GaussianBlur(hole.astype(np.float32), (0, 0), max(1.0, 2.0 / s))
    soft = np.maximum(soft, hole.astype(np.float32))[..., None]
    return (img * (1.0 - soft) + big * soft).astype(np.float32)


def largest_rect(covered: np.ndarray) -> tuple[int, int, int, int]:
    h, w = covered.shape
    s = min(1.0, 600.0 / max(h, w))
    m = cv2.resize(covered.astype(np.uint8), (max(1, round(w * s)), max(1, round(h * s))), interpolation=cv2.INTER_NEAREST) > 0
    m = cv2.erode(m.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    mh, mw = m.shape
    heights = np.zeros(mw, np.int32)
    best = (0, 0, 0, mw, mh)
    for y in range(mh):
        heights = np.where(m[y], heights + 1, 0)
        stack: list[int] = []
        for x in range(mw + 1):
            cur = heights[x] if x < mw else 0
            while stack and heights[stack[-1]] >= cur:
                top = stack.pop()
                left = stack[-1] + 1 if stack else 0
                area = int(heights[top]) * (x - left)
                if area > best[0]:
                    best = (area, left, y - int(heights[top]) + 1, x, y + 1)
            stack.append(x)
    _, x0, y0, x1, y1 = best
    return int(np.ceil(x0 / s)), int(np.ceil(y0 / s)), int(np.floor(x1 / s)), int(np.floor(y1 / s))


def finish_pano(out: np.ndarray, covered: np.ndarray, boundary: float = 0.0, fill: bool = False, crop: bool = True) -> np.ndarray:
    out, covered = boundary_warp(out, covered, boundary)
    if fill:
        out = fill_edges(out, covered)
        covered = np.ones_like(covered)
    if crop and not covered.all():
        x0, y0, x1, y1 = largest_rect(covered)
        if x1 - x0 > 16 and y1 - y0 > 16:
            out = out[y0:y1, x0:x1]
    return np.maximum(out, 0.0).astype(np.float32)
