import cv2
import numpy as np


def persons(rgb8: np.ndarray, people: np.ndarray, faces: list[dict], min_area: float = 0.004, components: bool = False) -> list[dict]:
    h, w = people.shape[:2]
    solid = (people > 0.5).astype(np.uint8)
    seeds = []
    for f in faces:
        x0, y0, x1, y1 = f["box"]
        cx, cy = (x0 + x1) / 2 * w, (y0 + y1) / 2 * h
        if 0 <= int(cy) < h and 0 <= int(cx) < w and people[int(cy), int(cx)] > 0.3:
            seeds.append((cx, cy, (x1 - x0) * w, (y1 - y0) * h, f["box"]))
    if not seeds and components:
        n, _lab, stats, _ = cv2.connectedComponentsWithStats(solid, 8)
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] >= min_area * h * w:
                x, y, bw, bh = stats[i, :4]
                seeds.append((x + bw / 2, y + bh * 0.2, bw * 0.3, bh * 0.1, [x / w, y / h, (x + bw) / w, (y + bh) / h]))
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
