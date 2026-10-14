import cv2
import numpy as np


def dhash(gray: np.ndarray) -> int:
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    bits = (small[:, 1:] > small[:, :-1]).reshape(-1)
    return int(sum(1 << i for i, b in enumerate(bits) if b))


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def eye_open(gray: np.ndarray, face: dict) -> float | None:
    lm = face.get("landmarks") or []
    if len(lm) < 2:
        return None
    h, w = gray.shape
    x0, y0, x1, y1 = face["box"]
    fw = (x1 - x0) * w
    if fw < 40:
        return None
    vals = []
    for ex, ey in lm[:2]:
        cx, cy = ex * w, ey * h
        rx, ry = fw * 0.13, fw * 0.08
        a, b = int(max(0, cy - ry)), int(min(h, cy + ry))
        c, d = int(max(0, cx - rx)), int(min(w, cx + rx))
        if b - a < 6 or d - c < 8:
            continue
        p = cv2.resize(gray[a:b, c:d], (40, 24), interpolation=cv2.INTER_AREA).astype(np.float32)
        lo, hi = float(np.percentile(p, 5)), float(np.percentile(p, 95))
        if hi - lo < 12:
            vals.append(0.2)
            continue
        dark = (p < lo + 0.38 * (hi - lo)).astype(np.uint8)
        n, lab, stats, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
        if n <= 1:
            vals.append(0.2)
            continue
        k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        bw, bh = stats[k, cv2.CC_STAT_WIDTH], stats[k, cv2.CC_STAT_HEIGHT]
        ratio = bh / max(1.0, bw)
        contrast = min(1.0, (hi - lo) / 90.0)
        vals.append(float(np.clip((ratio - 0.22) / 0.33, 0.0, 1.0)) * (0.6 + 0.4 * contrast))
    return round(100.0 * float(np.mean(vals)), 1) if vals else None


def scores(rgb8: np.ndarray, faces: list[dict] | None = None) -> dict:
    gray = cv2.cvtColor(rgb8, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    lap = cv2.Laplacian(gray.astype(np.float32) / 255.0, cv2.CV_32F, ksize=3)
    tiles = []
    th, tw = max(1, h // 6), max(1, w // 6)
    for y in range(0, h - th + 1, th):
        for x in range(0, w - tw + 1, tw):
            tiles.append(float(lap[y:y + th, x:x + tw].var()))
    focus = float(np.percentile(tiles, 90)) if tiles else float(lap.var())
    face_sharp = None
    eyes: list[float] = []
    face_list: list[dict] = []
    if faces:
        fv = []
        for f in faces:
            x0, y0, x1, y1 = f["box"]
            a, b = int(max(0, y0 * h)), int(min(h, y1 * h))
            c, d = int(max(0, x0 * w)), int(min(w, x1 * w))
            fs = None
            if b - a > 8 and d - c > 8:
                v = float(lap[a:b, c:d].var())
                fv.append(v)
                fs = round(float(np.clip(100.0 * (np.log10(max(v, 1e-7)) + 5.0) / 3.2, 0.0, 100.0)), 1)
            e = eye_open(gray, f)
            if e is not None:
                eyes.append(e)
            face_list.append({"box": [round(float(max(0.0, x0)), 4), round(float(max(0.0, y0)), 4), round(float(min(1.0, x1)), 4), round(float(min(1.0, y1)), 4)], "sharpness": fs, "eyesOpen": e})
        face_list = sorted(face_list, key=lambda r: (r["box"][2] - r["box"][0]) * (r["box"][3] - r["box"][1]), reverse=True)[:6]
        if fv:
            focus = max(focus * 0.4, max(fv))
            face_sharp = round(float(np.clip(100.0 * (np.log10(max(max(fv), 1e-7)) + 5.0) / 3.2, 0.0, 100.0)), 1)
    sharp = float(np.clip(100.0 * (np.log10(max(focus, 1e-7)) + 5.0) / 3.2, 0.0, 100.0))
    judged = gray
    if face_list:
        x0, y0, x1, y1 = face_list[0]["box"]
        part = gray[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
        judged = part if part.size > 256 else gray
    clip_hi = float(np.mean(judged >= 250))
    clip_lo = float(np.mean(judged <= 4))
    mean = float(judged.mean() / 255.0)
    exposure = float(np.clip(100.0 - 400.0 * max(clip_hi - 0.01, 0.0) - 300.0 * max(clip_lo - 0.02, 0.0) - 120.0 * abs(mean - 0.45), 0.0, 100.0))
    return {"sharpness": round(sharp, 1), "exposure": round(exposure, 1), "hash": dhash(gray), "faces": len(faces or []), "faceSharpness": face_sharp,
            "eyesOpen": min(eyes) if eyes else None, "faceList": face_list}


def quality(c: dict) -> float:
    q = 0.6 * float(c.get("sharpness", 0)) + 0.25 * float(c.get("exposure", 0))
    eyes = c.get("eyesOpen")
    return q + (0.15 * float(eyes) if eyes is not None else 0.15 * float(c.get("sharpness", 0)))


def groups(items: list[dict], seconds: float = 3.0, distance: int = 12) -> list[list[int]]:
    out: list[list[int]] = []
    current: list[dict] = []
    for it in sorted(items, key=lambda r: (r.get("time") or "", r["id"])):
        if current:
            last = current[-1]
            near_time = abs(_secs(it.get("time")) - _secs(last.get("time"))) <= seconds if it.get("time") and last.get("time") else False
            similar = hamming(it["hash"], last["hash"]) <= distance
            if near_time and similar or (similar and hamming(it["hash"], last["hash"]) <= distance // 2):
                current.append(it)
                continue
            out.append([c["id"] for c in current])
        current = [it]
    if current:
        out.append([c["id"] for c in current])
    return out


def _secs(t: str | None) -> float:
    if not t:
        return 0.0
    from datetime import datetime
    try:
        return datetime.fromisoformat(t[:19]).timestamp()
    except ValueError:
        return 0.0
