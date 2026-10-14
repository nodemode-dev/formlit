import cv2
import numpy as np


def _heads(comp: np.ndarray, x0: int, y0: int, bw: int, bh: int) -> tuple[list[tuple[int, int]], float]:
    sub = comp[y0:y0 + bh, x0:x0 + bw]
    top = np.where(sub.any(axis=0), sub.argmax(axis=0), bh).astype(np.float32)
    top = cv2.blur(top[None], (max(3, int(bh * 0.06)) | 1, 1))[0]
    head = bh * 0.14
    taken = np.zeros(bw, bool)
    out = []
    for x in np.argsort(top):
        if top[x] >= bh * 0.6:
            break
        if taken[x]:
            continue
        lo, hi = max(0, int(x - head)), min(bw, int(x + head) + 1)
        a, b = max(0, int(x - 2.5 * head)), min(bw, int(x + 2.5 * head) + 1)
        sides = [top[a:lo].max() if lo > a else top[x], top[hi:b].max() if b > hi else top[x]]
        if min(sides) - top[x] >= head * 0.35 or ((lo == 0 or hi == bw) and max(sides) - top[x] >= head * 0.35):
            out.append((x0 + int(x), y0 + int(top[x])))
        taken[max(0, int(x - 1.4 * head)):min(bw, int(x + 1.4 * head) + 1)] = True
    return sorted(out), head


def persons(rgb8: np.ndarray, people: np.ndarray, faces: list[dict], min_area: float = 0.004, components: bool = False) -> list[dict]:
    h, w = people.shape[:2]
    solid = (people > 0.5).astype(np.uint8)
    seeds = []
    for f in faces:
        x0, y0, x1, y1 = f["box"]
        cx, cy = (x0 + x1) / 2 * w, (y0 + y1) / 2 * h
        if 0 <= int(cy) < h and 0 <= int(cx) < w and people[int(cy), int(cx)] > 0.3:
            seeds.append((cx, cy, (x1 - x0) * w, (y1 - y0) * h, f["box"]))
    if components:
        n, lab, stats, _ = cv2.connectedComponentsWithStats(solid, 8)
        seeded = {int(lab[min(h - 1, int(s[1])), min(w - 1, int(s[0]))]) for s in seeds}
        for i in range(1, n):
            if i not in seeded and stats[i, cv2.CC_STAT_AREA] >= min_area * h * w:
                x, y, bw, bh = (int(v) for v in stats[i, :4])
                tops, head = _heads(lab == i, x, y, bw, bh)
                if len(tops) < 2:
                    seeds.append((x + bw / 2, y + bh * 0.2, bw * 0.3, bh * 0.1, [x / w, y / h, (x + bw) / w, (y + bh) / h]))
                for tx, ty in (tops if len(tops) >= 2 else []):
                    seeds.append((tx, ty + head * 0.6, head, max(head, (y + bh - ty - head * 0.6) / 2.5), [max(0, tx - head * 1.2) / w, ty / h, min(w, tx + head * 1.2) / w, (y + bh) / h]))
    seeds.sort(key=lambda s: s[0])
    if not seeds:
        return []
    if len(seeds) == 1:
        return [{"alpha": people.astype(np.float32), "box": seeds[0][4]}]
    markers = np.zeros((h, w), np.int32)
    for i, (cx, cy, bw, bh, _) in enumerate(seeds):
        rx, ry = max(2, int(bw * 0.3)), max(2, int(bh * 0.3))
        cv2.ellipse(markers, (int(cx), int(cy)), (rx, ry), 0, 0, 360, i + 1, -1)
        cv2.line(markers, (int(cx), int(cy)), (int(cx), min(h - 1, int(cy + bh * 2.5))), i + 1, max(2, rx // 2))
    markers[(people < 0.15)] = len(seeds) + 1
    labels = cv2.watershed(cv2.cvtColor(rgb8, cv2.COLOR_RGB2BGR), markers.copy())
    out = []
    for i, s in enumerate(seeds):
        own = (labels == i + 1).astype(np.float32)
        own = cv2.GaussianBlur(cv2.dilate(own, np.ones((3, 3), np.uint8)), (0, 0), 1.5)
        alpha = np.clip(people * own, 0.0, 1.0).astype(np.float32)
        if alpha.mean() >= min_area * 0.25:
            out.append({"alpha": alpha, "box": s[4]})
    return out
