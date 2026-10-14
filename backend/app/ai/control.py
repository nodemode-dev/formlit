import base64

import cv2
import numpy as np

KINDS = ("edges", "lines", "depth", "subject")


def _lum(rgb8: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(rgb8, cv2.COLOR_RGB2LAB)[..., 0].astype(np.float32) * (100.0 / 255.0)


def edges(rgb8: np.ndarray, detail: float = 50.0) -> np.ndarray:
    from app.develop.masks import edge_strength
    return edge_strength(_lum(rgb8), detail)


def canny(rgb8: np.ndarray) -> np.ndarray:
    g = cv2.GaussianBlur(cv2.cvtColor(rgb8, cv2.COLOR_RGB2GRAY), (0, 0), max(0.8, max(rgb8.shape[:2]) / 1200.0))
    m = float(np.median(g))
    return cv2.Canny(g, int(max(0, 0.66 * m)), int(min(255, 1.33 * m + 20)))


def lines(rgb8: np.ndarray, min_len: float = 0.04) -> np.ndarray:
    g = cv2.cvtColor(rgb8, cv2.COLOR_RGB2GRAY)
    found = cv2.createLineSegmentDetector().detect(g)[0]
    if found is None:
        return np.zeros((0, 4), np.float32)
    seg = found.reshape(-1, 4)
    length = np.hypot(seg[:, 2] - seg[:, 0], seg[:, 3] - seg[:, 1])
    return seg[length >= min_len * max(g.shape)]


def _jpeg(img: np.ndarray) -> str:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def render(rgb8: np.ndarray, kinds: list[str], depth: np.ndarray | None = None, subject: np.ndarray | None = None) -> dict:
    bgr = cv2.cvtColor(rgb8, cv2.COLOR_RGB2BGR)
    dim = (bgr * 0.35).astype(np.uint8)
    out: dict = {}
    if "edges" in kinds:
        e = edges(rgb8)
        out["edges"] = _jpeg((np.clip(e, 0, 1) * 255).astype(np.uint8))
    if "lines" in kinds:
        segs = lines(rgb8)
        canvas = dim.copy()
        for x0, y0, x1, y1 in segs:
            cv2.line(canvas, (int(x0), int(y0)), (int(x1), int(y1)), (0, 200, 255), max(1, round(max(rgb8.shape[:2]) / 600)), cv2.LINE_AA)
        out["lines"] = _jpeg(canvas)
        out["lineCount"] = int(len(segs))
    if "depth" in kinds and depth is not None:
        out["depth"] = _jpeg(cv2.applyColorMap((np.clip(depth, 0, 1) * 255).astype(np.uint8), cv2.COLORMAP_VIRIDIS))
    if "subject" in kinds and subject is not None:
        tint = dim.copy()
        a = np.clip(subject, 0, 1)[..., None]
        tint = (tint * (1 - a) + (bgr * 0.5 + np.array([0, 0, 255]) * 0.5) * a).astype(np.uint8)
        out["subject"] = _jpeg(tint)
    return out
