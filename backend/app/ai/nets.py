import threading

import cv2
import numpy as np

from app.ai import models

MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
_run_lock = threading.Lock()


def _resize(img: np.ndarray, w: int, h: int, interp=cv2.INTER_AREA) -> np.ndarray:
    return cv2.resize(img, (w, h), interpolation=interp)


def _norm01(a: np.ndarray) -> np.ndarray:
    lo, hi = float(a.min()), float(a.max())
    return (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)


def u2net(rgb8: np.ndarray, model: str = "subject") -> np.ndarray:
    file = "u2net.onnx" if model == "subject" else "u2net_human_seg.onnx"
    models.require(model)
    s = models.session(model, file)
    h, w = rgb8.shape[:2]
    im = _resize(rgb8, 320, 320, cv2.INTER_LANCZOS4).astype(np.float32)
    im = im / max(float(im.max()), 1e-6)
    x = ((im - MEAN) / STD).transpose(2, 0, 1)[None].astype(np.float32)
    with _run_lock:
        pred = s.run(None, {s.get_inputs()[0].name: x})[0][0, 0]
    return np.clip(_resize(_norm01(pred.astype(np.float32)), w, h, cv2.INTER_LINEAR), 0.0, 1.0)


def sky(rgb8: np.ndarray) -> np.ndarray:
    models.require("sky")
    s = models.session("sky", "skyseg/skyseg.onnx")
    h, w = rgb8.shape[:2]
    x = _resize(rgb8, 320, 320, cv2.INTER_LINEAR).astype(np.float32) / 255.0
    x = ((x - MEAN) / STD).transpose(2, 0, 1)[None].astype(np.float32)
    with _run_lock:
        r = s.run(None, {s.get_inputs()[0].name: x})[0]
    r = np.asarray(r, np.float32).squeeze()
    return np.clip(_resize(_norm01(r), w, h, cv2.INTER_LINEAR), 0.0, 1.0)


def depth(rgb8: np.ndarray) -> np.ndarray:
    models.require("depth")
    s = models.session("depth", "depth-anything-v2-small/model.onnx")
    h, w = rgb8.shape[:2]
    x = _resize(rgb8, 518, 518, cv2.INTER_CUBIC).astype(np.float32) / 255.0
    x = ((x - MEAN) / STD).transpose(2, 0, 1)[None].astype(np.float32)
    with _run_lock:
        out = s.run(None, {s.get_inputs()[0].name: x})[0]
    d = np.asarray(out, np.float32).reshape(518, 518)
    return np.clip(_resize(_norm01(d), w, h, cv2.INTER_CUBIC), 0.0, 1.0)


def sam_box(rgb8: np.ndarray, box: list[float], points: list[list[float]] | None = None) -> np.ndarray:
    models.require("objects")
    enc = models.session("sam-enc", "sam2.1-hiera-tiny/vision_encoder.onnx")
    dec = models.session("sam-dec", "sam2.1-hiera-tiny/prompt_encoder_mask_decoder.onnx")
    h, w = rgb8.shape[:2]
    im = _resize(rgb8, 1024, 1024, cv2.INTER_LINEAR).astype(np.float32) / 255.0
    im = ((im - MEAN) / STD).transpose(2, 0, 1)[None].astype(np.float32)
    with _run_lock:
        outs = enc.run(None, {"pixel_values": im})
        emb = {f"image_embeddings.{i}": outs[i] for i in range(3)}
        sx, sy = 1024.0 / w, 1024.0 / h
        pts = [[p[0] * w * sx, p[1] * h * sy] for p in (points or [])] or [[0.0, 0.0]]
        labels = [1] * len(points or []) or [-1]
        b = np.array([[[box[0] * w * sx, box[1] * h * sy, box[2] * w * sx, box[3] * h * sy]]], np.float32)
        iou, masks, _ = dec.run(None, {"input_points": np.array([[pts]], np.float32), "input_labels": np.array([[labels]], np.int64), "input_boxes": b, **emb})
    best = masks[0, 0, int(np.argmax(iou[0, 0]))].astype(np.float32)
    m = _resize(best, w, h, cv2.INTER_LINEAR)
    return (1.0 / (1.0 + np.exp(-m))).astype(np.float32)


def lama(rgb8: np.ndarray, hole: np.ndarray) -> np.ndarray:
    models.require("remove")
    s = models.session("lama", "lama_fp32.onnx")
    h, w = rgb8.shape[:2]
    grow = max(3, round(max(w, h) / 512 * 4)) | 1
    hole8 = cv2.dilate((hole > 0.5).astype(np.uint8) * 255, np.ones((grow, grow), np.uint8))
    side = max(w, h)
    pix = np.pad(rgb8, ((0, side - h), (0, side - w), (0, 0)), mode="edge")
    holes = np.pad(hole8, ((0, side - h), (0, side - w)), mode="constant")
    small = _resize(pix, 512, 512, cv2.INTER_AREA).astype(np.float32) / 255.0
    small_hole = (_resize(holes, 512, 512, cv2.INTER_NEAREST) > 127).astype(np.float32)
    with _run_lock:
        out = s.run(None, {"image": small.transpose(2, 0, 1)[None], "mask": small_hole[None, None]})[0][0].transpose(1, 2, 0)
    filled = _resize(np.clip(out, 0, 255).astype(np.uint8), side, side, cv2.INTER_LANCZOS4)[:h, :w]
    a = (hole8 > 127)[..., None]
    return np.where(a, filled, rgb8)


def esrgan(rgb8: np.ndarray, progress=None, tile: int = 192, margin: int = 16) -> np.ndarray:
    models.require("upscale")
    s = models.session("esrgan", "realesrgan-x4plus.onnx")
    h, w = rgb8.shape[:2]
    out = np.zeros((h * 4, w * 4, 3), np.uint8)
    src = rgb8.astype(np.float32) / 255.0
    tiles = ((h + tile - 1) // tile) * ((w + tile - 1) // tile)
    done = 0
    for top in range(0, h, tile):
        for left in range(0, w, tile):
            if progress is not None and getattr(progress, "cancelled", False):
                raise InterruptedError("Cancelled")
            bottom, right = min(h, top + tile), min(w, left + tile)
            y0, x0, y1, x1 = max(0, top - margin), max(0, left - margin), min(h, bottom + margin), min(w, right + margin)
            batch = np.ascontiguousarray(src[y0:y1, x0:x1].transpose(2, 0, 1)[None])
            with _run_lock:
                r = s.run(None, {s.get_inputs()[0].name: batch})[0][0].transpose(1, 2, 0)
            keep = r[(top - y0) * 4:(bottom - y0) * 4, (left - x0) * 4:(right - x0) * 4]
            out[top * 4:bottom * 4, left * 4:right * 4] = (np.clip(keep, 0, 1) * 255 + 0.5).astype(np.uint8)
            done += 1
            if progress is not None:
                progress(done, tiles, "Super Resolution")
    return out


def faces(rgb8: np.ndarray, threshold: float = 0.8) -> list[dict]:
    models.require("faces")
    h, w = rgb8.shape[:2]
    det = cv2.FaceDetectorYN.create(str(models.path("yunet-face/face_detection_yunet_2023mar.onnx")), "", (w, h), threshold, 0.3, 5000)
    bgr = cv2.cvtColor(rgb8, cv2.COLOR_RGB2BGR)
    _, found = det.detect(bgr)
    out = []
    if found is None:
        return out
    rec = cv2.FaceRecognizerSF.create(str(models.path("sface/face_recognition_sface_2021dec.onnx")), "")
    for f in found:
        aligned = rec.alignCrop(bgr, f)
        feat = rec.feature(aligned).reshape(-1).astype(np.float32)
        feat = feat / max(1e-9, float(np.linalg.norm(feat)))
        x, y, bw, bh = (float(v) for v in f[:4])
        out.append({"box": [x / w, y / h, (x + bw) / w, (y + bh) / h], "score": float(f[14]), "landmarks": [[float(f[4 + 2 * i]) / w, float(f[5 + 2 * i]) / h] for i in range(5)],
                    "embedding": feat.tolist()})
    return out
