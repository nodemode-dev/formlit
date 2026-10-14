import tempfile

import cv2
import numpy as np

from app.ai.merge import largest_rect

LW = np.array([0.2627, 0.6780, 0.0593], np.float32)
KAPPA = 2.5


def stars(lin: np.ndarray, limit: int = 400, mask: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    h, w = lin.shape[:2]
    s = min(1.0, 2000.0 / max(h, w))
    y = lin @ LW if lin.ndim == 3 else lin
    y = cv2.medianBlur(np.ascontiguousarray(y, np.float32), 3)
    y = cv2.resize(y, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else y
    bg = cv2.GaussianBlur(cv2.medianBlur(np.clip(y, 0, None).astype(np.float32), 5), (0, 0), 12)
    d = cv2.GaussianBlur(y - bg, (0, 0), 0.8)
    sigma = 1.4826 * float(np.median(np.abs(d - np.median(d)))) + 1e-9
    peak = (d == cv2.dilate(d, np.ones((5, 5), np.uint8))) & (d > 6 * sigma)
    if mask is not None:
        m = cv2.resize(mask.astype(np.float32), (d.shape[1], d.shape[0]), interpolation=cv2.INTER_AREA) > 0.5
        peak &= m
    ys, xs = np.nonzero(peak)
    if not len(ys):
        return np.zeros((0, 2), np.float32), np.zeros(0, np.float32)
    order = np.argsort(-d[ys, xs])
    ys, xs = ys[order], xs[order]
    cell = (ys * 5 // d.shape[0]) * 8 + xs * 8 // d.shape[1]
    by = np.argsort(cell, kind="stable")
    rank = np.empty(len(ys), np.int64)
    rank[by] = np.arange(len(ys)) - np.searchsorted(cell[by], cell[by])
    pick = np.lexsort((np.arange(len(ys)), rank))[:limit * 3]
    ys, xs = ys[pick], xs[pick]
    pts, flux = [], []
    for yy, xx in zip(ys, xs):
        y0, y1, x0, x1 = max(0, yy - 3), min(d.shape[0], yy + 4), max(0, xx - 3), min(d.shape[1], xx + 4)
        win = np.clip(d[y0:y1, x0:x1], 0, None)
        tot = float(win.sum())
        if tot <= 0:
            continue
        gy, gx = np.mgrid[y0:y1, x0:x1]
        cx, cy = float((gx * win).sum()) / tot, float((gy * win).sum()) / tot
        cxx, cyy, cxy = float((win * (gx - cx) ** 2).sum()) / tot, float((win * (gy - cy) ** 2).sum()) / tot, float((win * (gx - cx) * (gy - cy)).sum()) / tot
        root = np.sqrt(((cxx - cyy) / 2) ** 2 + cxy ** 2)
        if (cxx + cyy) / 2 + root > 3.0 * max(1e-6, (cxx + cyy) / 2 - root):
            continue
        pts.append(((cx + 0.5) / s - 0.5, (cy + 0.5) / s - 0.5))
        flux.append(tot)
        if len(pts) >= limit:
            break
    return np.asarray(pts, np.float32), np.asarray(flux, np.float32)


def cosmetic(img: np.ndarray) -> np.ndarray:
    out = np.ascontiguousarray(img, np.float32).copy()
    for c in range(out.shape[2]):
        ch = out[..., c]
        med = cv2.medianBlur(ch, 3)
        diff = ch - med
        noise = 1.4826 * float(np.median(np.abs(diff - np.median(diff)))) + 1e-9
        hot = (diff > 8 * noise) & (diff > 0.5 * np.abs(ch))
        ch[hot] = med[hot]
    return out


def _render(pts: np.ndarray, flux: np.ndarray, h: int, w: int, scale: float) -> np.ndarray:
    img = np.zeros((max(1, round(h * scale)), max(1, round(w * scale))), np.float32)
    for (x, y), f in zip(pts, flux):
        xi, yi = int(x * scale), int(y * scale)
        if 0 <= yi < img.shape[0] and 0 <= xi < img.shape[1]:
            img[yi, xi] += np.sqrt(f)
    return cv2.GaussianBlur(img, (0, 0), 2.0)


def match(ref: tuple[np.ndarray, np.ndarray], cur: tuple[np.ndarray, np.ndarray], h: int, w: int) -> tuple[np.ndarray | None, int, float]:
    rp, rf = ref
    cp, cf = cur
    if len(rp) < 6 or len(cp) < 6:
        return None, 0, 0.0
    a, b = cp[:80], rp[:80]
    diff = (b[None, :, :] - a[:, None, :]).reshape(-1, 2)
    lim = max(h, w) * 0.25
    diff = diff[(np.abs(diff) < lim).all(1)]
    if not len(diff):
        return None, 0, 0.0
    bins = int(2 * lim / 6) + 1
    hist, ex, ey = np.histogram2d(diff[:, 0], diff[:, 1], bins=bins, range=[[-lim, lim], [-lim, lim]])
    hist = cv2.GaussianBlur(hist.astype(np.float32), (0, 0), 1.0)
    ix, iy = np.unravel_index(int(np.argmax(hist)), hist.shape)
    dx, dy = (ex[ix] + ex[ix + 1]) / 2, (ey[iy] + ey[iy + 1]) / 2
    m = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]])
    inliers, rms = 0, 0.0
    for radius in (max(h, w) * 0.01 + 6, 4.0):
        moved = cp @ m[:, :2].T + m[:, 2]
        dist = np.sqrt(((moved[:, None, :] - rp[None, :, :]) ** 2).sum(-1))
        j = dist.argmin(1)
        ok = dist[np.arange(len(cp)), j] < radius
        if ok.sum() < 6:
            return None, int(ok.sum()), 0.0
        est, keep = cv2.estimateAffinePartial2D(cp[ok], rp[j[ok]], method=cv2.RANSAC, ransacReprojThreshold=1.5, maxIters=4000, confidence=0.999)
        if est is None:
            return None, 0, 0.0
        m = est.astype(np.float64)
        keep = keep.ravel().astype(bool)
        res = cp[ok][keep] @ m[:, :2].T + m[:, 2] - rp[j[ok]][keep]
        inliers, rms = int(keep.sum()), float(np.sqrt((res ** 2).sum(-1).mean())) if keep.any() else 0.0
    hm = np.vstack([m, [0.0, 0.0, 1.0]])
    for radius in (6.0, 3.0, 1.5):
        moved = cv2.perspectiveTransform(cp[None].astype(np.float64), hm)[0]
        dist = np.sqrt(((moved[:, None, :] - rp[None, :, :]) ** 2).sum(-1))
        j = dist.argmin(1)
        ok = dist[np.arange(len(cp)), j] < radius
        if ok.sum() < 12:
            break
        est, keep = cv2.findHomography(cp[ok].astype(np.float64), rp[j[ok]].astype(np.float64), cv2.RANSAC, 1.0, maxIters=4000, confidence=0.999)
        if est is None:
            break
        keep = keep.ravel().astype(bool)
        res = cv2.perspectiveTransform(cp[ok][keep][None].astype(np.float64), est)[0] - rp[j[ok]][keep]
        hm, inliers, rms = est, int(keep.sum()), float(np.sqrt((res ** 2).sum(-1).mean()))
    return hm, inliers, rms


def _terms(p: np.ndarray, h: int, w: int, full: bool = True) -> np.ndarray:
    s = max(h, w) / 2.0
    u, v = (p[:, 0] - w / 2.0) / s, (p[:, 1] - h / 2.0) / s
    cols = [np.ones_like(u), u, v] + ([u * u, u * v, v * v, u ** 3, u * u * v, u * v * v, v ** 3] if full else [])
    return np.stack(cols, 1)


def _fit(pr: np.ndarray, pc: np.ndarray, h: int, w: int) -> tuple[np.ndarray | None, np.ndarray]:
    keep = np.ones(len(pr), bool)
    coef = None
    for _ in range(5):
        if keep.sum() < 6:
            return None, keep
        full = keep.sum() >= 30
        a = _terms(pr[keep], h, w, full)
        coef = np.linalg.lstsq(a, pc[keep], rcond=None)[0]
        if not full:
            coef = np.vstack([coef, np.zeros((7, 2))])
        res = np.sqrt(((_terms(pr, h, w) @ coef - pc) ** 2).sum(1))
        keep = res < max(1.0, 3.0 * float(np.sqrt((res[keep] ** 2).mean())))
    return coef, keep


def model(ref: tuple[np.ndarray, np.ndarray], cur: tuple[np.ndarray, np.ndarray], h: int, w: int, guide: np.ndarray | None = None) -> tuple[np.ndarray | None, np.ndarray, np.ndarray, float]:
    rp, rf = ref
    cp, cf = cur
    none = (None, np.zeros((0, 2)), np.zeros((0, 2)), 0.0)
    if len(rp) < 6 or len(cp) < 6:
        return none
    seen = cv2.perspectiveTransform(cp[None].astype(np.float64), np.linalg.inv(guide))[0] if guide is not None else cp.astype(np.float64)
    margin = max(h, w) * (0.08 if guide is not None else 0.3)
    pr, pc, used = [], [], set()
    for ty in range(2):
        for tx in range(3):
            x0, x1, y0, y1 = w * tx / 3, w * (tx + 1) / 3, h * ty / 2, h * (ty + 1) / 2
            rs = (rp[:, 0] >= x0) & (rp[:, 0] < x1) & (rp[:, 1] >= y0) & (rp[:, 1] < y1)
            cs = (seen[:, 0] >= x0 - margin) & (seen[:, 0] < x1 + margin) & (seen[:, 1] >= y0 - margin) & (seen[:, 1] < y1 + margin)
            if rs.sum() < 6 or cs.sum() < 6:
                continue
            hm, _, _ = match((rp[rs], rf[rs]), (cp[cs], cf[cs]), h, w)
            if hm is None:
                continue
            ci = np.nonzero(cs)[0]
            moved = cv2.perspectiveTransform(cp[ci][None].astype(np.float64), hm)[0]
            dist = np.sqrt(((moved[:, None, :] - rp[rs][None, :, :]) ** 2).sum(-1))
            j = dist.argmin(1)
            for k in np.nonzero(dist[np.arange(len(ci)), j] < 1.5)[0]:
                if ci[k] not in used:
                    used.add(ci[k])
                    pr.append(rp[rs][j[k]])
                    pc.append(cp[ci[k]])
    if len(pr) < 6:
        return none
    pr, pc = np.asarray(pr, np.float64), np.asarray(pc, np.float64)
    coef, keep = _fit(pr, pc, h, w)
    if coef is None:
        return none
    for radius in (3.0, 1.5):
        guess = _terms(rp.astype(np.float64), h, w) @ coef
        dist = np.sqrt(((guess[:, None, :] - cp[None, :, :]) ** 2).sum(-1))
        j = dist.argmin(1)
        ok = dist[np.arange(len(rp)), j] < radius
        if ok.sum() < 6:
            break
        pr, pc = rp[ok].astype(np.float64), cp[j[ok]].astype(np.float64)
        coef, keep = _fit(pr, pc, h, w)
        if coef is None:
            return none
    res = _terms(pr[keep], h, w) @ coef - pc[keep]
    return coef, pr[keep], pc[keep], float(np.sqrt((res ** 2).sum(1).mean()))


def maps(coef: np.ndarray, pr: np.ndarray, pc: np.ndarray, h: int, w: int) -> tuple[np.ndarray, np.ndarray]:
    gw, gh = max(2, -(-w // 16)), max(2, -(-h // 16))
    gx = (np.arange(gw) + 0.5) * w / gw - 0.5
    gy = (np.arange(gh) + 0.5) * h / gh - 0.5
    grid = np.stack(np.meshgrid(gx, gy), -1).reshape(-1, 2)
    disp = _terms(grid, h, w) @ coef - grid
    if len(pr) >= 20:
        r = pc - _terms(pr, h, w) @ coef
        sigma = max(h, w) / 10.0
        for k in range(0, len(grid), 4096):
            g = grid[k:k + 4096]
            wgt = np.exp(-((g[:, None, 0] - pr[None, :, 0]) ** 2 + (g[:, None, 1] - pr[None, :, 1]) ** 2) / (2 * sigma * sigma))
            disp[k:k + 4096] += (wgt @ r) / (wgt.sum(1)[:, None] + 1.0)
    full = cv2.resize(disp.reshape(gh, gw, 2).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    py, px = np.mgrid[0:h, 0:w].astype(np.float32)
    return px + full[..., 0], py + full[..., 1]


def _combine(block: np.ndarray, reject: str) -> np.ndarray:
    if reject == "mean" or block.shape[0] < 3:
        return np.nanmean(block, axis=0)
    med = np.nanmedian(block, axis=0)
    if reject == "median":
        return med
    mad = np.nanmedian(np.abs(block - med[None]), axis=0) * 1.4826 + 1e-7
    keep = np.abs(block - med[None]) <= KAPPA * mad[None]
    with np.errstate(invalid="ignore"):
        out = np.nansum(np.where(keep, block, 0.0), axis=0) / np.maximum(1, np.sum(keep & ~np.isnan(block), axis=0))
    return np.where(np.sum(keep, axis=0) > 0, out, med)


def stack(load, n: int, progress=None, align: bool = True, reject: str = "sigma", sky: np.ndarray | None = None, crop: bool = True) -> tuple[np.ndarray, dict]:
    say = progress or (lambda a, b, label: None)
    ref_i = n // 2
    ref = cosmetic(load(ref_i))
    h, w = ref.shape[:2]
    sky_full = cv2.resize(sky.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR) if sky is not None else None
    if sky_full is not None:
        solid = (sky_full > 0.5).astype(np.uint8)
        _, lab = cv2.connectedComponents(solid, connectivity=4)
        top = [int(v) for v in np.unique(lab[0][solid[0] > 0]) if v]
        if top:
            sky_full = (sky_full * np.isin(lab, top)).astype(np.float32)
    ref_stars = stars(ref, mask=None if sky_full is None else sky_full > 0.5)
    grow = max(2, round(max(h, w) / 320 * 0.75))
    ground_mask = None if sky_full is None else cv2.dilate((sky_full < 0.5).astype(np.float32), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow + 1, 2 * grow + 1)))
    tmp = tempfile.TemporaryDirectory(prefix="formlit-astro-")
    aligned = np.memmap(f"{tmp.name}/a.f16", np.float16, "w+", shape=(n, h, w, 3))
    fixed = np.memmap(f"{tmp.name}/f.f16", np.float16, "w+", shape=(n, h, w, 3)) if sky_full is not None else None
    report = {"frames": n, "aligned": 0, "rms": [], "inliers": []}
    covered = np.ones((h, w), bool)
    for i in range(n):
        img = ref if i == ref_i else cosmetic(load(i))
        if img.shape[:2] != (h, w):
            raise ValueError("The photos are not all the same size")
        if fixed is not None:
            fixed[i] = img.astype(np.float16)
        if align and i != ref_i:
            cur_stars = stars(img, mask=None if sky_full is None else sky_full > 0.5)
            m, _, _ = match(ref_stars, cur_stars, h, w)
            coef, pr, pc, rms = model(ref_stars, cur_stars, h, w, m)
            if coef is None:
                raise ValueError(f"Could not find the same stars in frame {i + 1}; try fewer frames, a longer focal length is fine but the sky must show stars")
            inl = len(pr)
            mx, my = maps(coef, pr, pc, h, w)
            warped = cv2.remap(img, mx, my, cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT, borderValue=(np.nan, np.nan, np.nan))
            covered &= ~np.isnan(warped[..., 0])
            if ground_mask is not None:
                warped[cv2.remap(ground_mask, mx, my, cv2.INTER_LINEAR) > 0.2] = np.nan
            del mx, my
            aligned[i] = warped.astype(np.float16)
            report["aligned"] += 1
            report["rms"].append(round(rms, 3))
            report["inliers"].append(inl)
        else:
            aligned[i] = img.astype(np.float16)
        say(i + 1, 2 * n, f"Aligning frame {i + 1} of {n}")
    out = np.zeros((h, w, 3), np.float32)
    rows = max(16, int(2_000_000 // max(1, w * n)))
    for y0 in range(0, h, rows):
        y1 = min(h, y0 + rows)
        part = _combine(np.asarray(aligned[:, y0:y1], np.float32), reject)
        if fixed is not None:
            ground = _combine(np.asarray(fixed[:, y0:y1], np.float32), reject)
            a = sky_full[y0:y1, :, None]
            part = np.where(np.isnan(part), ground, part) * a + ground * (1.0 - a)
        out[y0:y1] = np.nan_to_num(part, nan=0.0)
        say(n + int(n * y1 / h), 2 * n, "Stacking")
    del aligned, fixed
    tmp.cleanup()
    if crop and align and sky_full is None and not covered.all():
        x0, y0, x1, y1 = largest_rect(covered)
        out = out[y0:y1, x0:x1]
        report["crop"] = [x0, y0, x1, y1]
    return np.clip(out, 0.0, None).astype(np.float32), report
