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


def person_classes(rgb8: np.ndarray) -> np.ndarray:
    models.require("parts")
    s = models.session("parts", "selfie-multiclass/model.onnx")
    h, w = rgb8.shape[:2]
    x = (_resize(rgb8, 256, 256, cv2.INTER_AREA).astype(np.float32) / 255.0)[None]
    with _run_lock:
        lg = s.run(None, {s.get_inputs()[0].name: x})[0][0]
    e = np.exp(lg - lg.max(-1, keepdims=True))
    return _resize((e / e.sum(-1, keepdims=True)).astype(np.float32), w, h, cv2.INTER_LINEAR)


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


def sam_box(rgb8: np.ndarray, box: list[float] | None, points: list[list[float]] | None = None) -> np.ndarray:
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
        b = np.array([[[box[0] * w * sx, box[1] * h * sy, box[2] * w * sx, box[3] * h * sy]]], np.float32) if box else np.zeros((1, 0, 4), np.float32)
        iou, masks, _ = dec.run(None, {"input_points": np.array([[pts]], np.float32), "input_labels": np.array([[labels]], np.int64), "input_boxes": b, **emb})
    best = masks[0, 0, int(np.argmax(iou[0, 0]))].astype(np.float32)
    m = _resize(best, w, h, cv2.INTER_LINEAR)
    return (1.0 / (1.0 + np.exp(-m))).astype(np.float32)


def instances(rgb8: np.ndarray, label: int = 1, min_score: float = 0.5) -> list[dict]:
    models.require("instances")
    s = models.session("instances", "maskrcnn-v2/model.onnx")
    h, w = rgb8.shape[:2]
    x = (_resize(rgb8, 224, 224, cv2.INTER_AREA).astype(np.float32) / 255.0).transpose(2, 0, 1)[None]
    with _run_lock:
        boxes, labels, scores, masks = s.run(None, {s.get_inputs()[0].name: x})
    found = [{"score": float(scores[i]), "box": [float(v) / 224.0 for v in boxes[i]], "mask": _resize(masks[i, 0].astype(np.float32), w, h, cv2.INTER_LINEAR)}
             for i in range(len(labels)) if int(labels[i]) == label and float(scores[i]) >= min_score]
    for d in found:
        bx0, by0, bx1, by1 = d["box"]
        mx, my = (bx1 - bx0) * 0.25, (by1 - by0) * 0.1
        x0, y0, x1, y1 = int(max(0.0, bx0 - mx) * w), int(max(0.0, by0 - my) * h), int(min(1.0, bx1 + mx) * w), int(min(1.0, by1 + my) * h)
        if x1 - x0 < 16 or y1 - y0 < 16 or (x1 - x0) * (y1 - y0) > 0.6 * w * h:
            continue
        crop = rgb8[y0:y1, x0:x1]
        cx = (_resize(crop, 224, 224, cv2.INTER_AREA).astype(np.float32) / 255.0).transpose(2, 0, 1)[None]
        with _run_lock:
            cb, cl, cs, cm = s.run(None, {s.get_inputs()[0].name: cx})
        want = [(bx0 * w - x0) / (x1 - x0) * 224, (by0 * h - y0) / (y1 - y0) * 224, (bx1 * w - x0) / (x1 - x0) * 224, (by1 * h - y0) / (y1 - y0) * 224]
        iou = [_iou(want, cb[k]) if int(cl[k]) == label else 0.0 for k in range(len(cl))]
        if not iou or max(iou) < 0.5:
            continue
        fine = d["mask"].copy()
        fine[y0:y1, x0:x1] = _resize(cm[int(np.argmax(iou)), 0].astype(np.float32), x1 - x0, y1 - y0, cv2.INTER_LINEAR)
        d["mask"] = fine
    return found


def _iou(a, b) -> float:
    ix, iy = max(0.0, min(a[2], b[2]) - max(a[0], b[0])), max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
    return float(ix * iy / u) if u > 0 else 0.0


def sam_prompts(rgb8: np.ndarray, prompts: list[tuple[list[list[float]], list[int], list[float] | None]]) -> list[np.ndarray]:
    models.require("objects")
    enc = models.session("sam-enc", "sam2.1-hiera-tiny/vision_encoder.onnx")
    dec = models.session("sam-dec", "sam2.1-hiera-tiny/prompt_encoder_mask_decoder.onnx")
    h, w = rgb8.shape[:2]
    im = _resize(rgb8, 1024, 1024, cv2.INTER_LINEAR).astype(np.float32) / 255.0
    im = ((im - MEAN) / STD).transpose(2, 0, 1)[None].astype(np.float32)
    out = []
    with _run_lock:
        outs = enc.run(None, {"pixel_values": im})
        emb = {f"image_embeddings.{i}": outs[i] for i in range(3)}
        for pts, labels, box in prompts:
            b = np.array([[[box[0] * 1024, box[1] * 1024, box[2] * 1024, box[3] * 1024]]], np.float32) if box else np.zeros((1, 0, 4), np.float32)
            iou, masks, _ = dec.run(None, {"input_points": np.array([[[[p[0] * 1024, p[1] * 1024] for p in pts]]], np.float32),
                                           "input_labels": np.array([[labels]], np.int64), "input_boxes": b, **emb})
            out.append(_resize(masks[0, 0, int(np.argmax(iou[0, 0]))].astype(np.float32), w, h, cv2.INTER_LINEAR))
    return out


def lama(rgb8: np.ndarray, hole: np.ndarray, whole: bool = False) -> np.ndarray:
    models.require("remove")
    s = models.session("lama", "lama_fp32.onnx")
    h, w = rgb8.shape[:2]
    grow = max(3, round(max(w, h) / 512 * 4)) | 1
    hole8 = cv2.dilate((hole > 0.5).astype(np.uint8) * 255, np.ones((grow, grow), np.uint8))
    ys, xs = np.nonzero(hole8 > 127)
    if len(ys) and max(w, h) > 768 and not whole:
        side = int(min(max(w, h), max(512, 2.2 * max(xs.max() - xs.min(), ys.max() - ys.min()))))
        x0 = int(min(max(0, (xs.min() + xs.max()) / 2 - side / 2), max(0, w - side)))
        y0 = int(min(max(0, (ys.min() + ys.max()) / 2 - side / 2), max(0, h - side)))
        part = rgb8.copy()
        part[y0:y0 + side, x0:x0 + side] = lama(rgb8[y0:y0 + side, x0:x0 + side], hole[y0:y0 + side, x0:x0 + side], True)
        return part
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
