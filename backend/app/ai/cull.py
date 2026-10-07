import cv2
import numpy as np


def dhash(gray: np.ndarray) -> int:
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    bits = (small[:, 1:] > small[:, :-1]).reshape(-1)
    return int(sum(1 << i for i, b in enumerate(bits) if b))


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


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
    if faces:
        fv = []
        for f in faces:
            x0, y0, x1, y1 = f["box"]
            a, b = int(max(0, y0 * h)), int(min(h, y1 * h))
            c, d = int(max(0, x0 * w)), int(min(w, x1 * w))
            if b - a > 8 and d - c > 8:
                fv.append(float(lap[a:b, c:d].var()))
        if fv:
            focus = max(focus * 0.4, max(fv))
    sharp = float(np.clip(100.0 * (np.log10(max(focus, 1e-7)) + 5.0) / 3.2, 0.0, 100.0))
    clip_hi = float(np.mean(gray >= 250))
    clip_lo = float(np.mean(gray <= 4))
    mean = float(gray.mean() / 255.0)
    exposure = float(np.clip(100.0 - 400.0 * max(clip_hi - 0.01, 0.0) - 300.0 * max(clip_lo - 0.02, 0.0) - 120.0 * abs(mean - 0.45), 0.0, 100.0))
    return {"sharpness": round(sharp, 1), "exposure": round(exposure, 1), "hash": dhash(gray), "faces": len(faces or [])}


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
