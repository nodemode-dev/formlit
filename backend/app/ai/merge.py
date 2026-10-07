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


def hdr(images: list[np.ndarray], factors: list[float | None], deghost: str = "off", progress=None) -> np.ndarray:
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
        if i == ref_i:
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
            wt = wt * (diff < thr)
        acc += norm * wt[..., None]
        wsum += wt
        if progress is not None:
            progress(n + 1, n + 2, "Merging")
    out = np.where((wsum > 1e-6)[..., None], acc / np.maximum(wsum, 1e-6)[..., None], darkest)
    return np.maximum(out, 0.0).astype(np.float32)


def pano(images: list[np.ndarray], projection: str = "spherical", progress=None, max_pixels: float = 80e6) -> np.ndarray:
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
    rows = np.where(covered.mean(axis=1) > 0.98)[0]
    cols = np.where(covered.mean(axis=0) > 0.98)[0]
    if len(rows) > 16 and len(cols) > 16:
        sub = covered[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
        if sub.mean() > 0.995:
            out = out[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    return np.maximum(out, 0.0).astype(np.float32)
