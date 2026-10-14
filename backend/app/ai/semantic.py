import json
import math
import re
import sqlite3
import string
import threading
import unicodedata
from collections import OrderedDict

import cv2
import numpy as np

from app.ai import models
from app.core import config

MODEL = "search"
SIG = "siglip-b16-int8"
DIM = 768
SCALE = 117.33077
BIAS = -12.932437
SEQ = 64
MATCH = 0.0003
STRICT = 0.01
_vocab: dict[str, tuple[int, float]] | None = None
_longest = 0
_lock = threading.RLock()
_texts: OrderedDict[str, np.ndarray] = OrderedDict()
_matrix: tuple[np.ndarray, np.ndarray] | None = None
_last: tuple[tuple, list[tuple[int, float]]] | None = None
_PUNCT = str.maketrans("", "", string.punctuation)


def _load_vocab() -> dict[str, tuple[int, float]]:
    global _vocab, _longest
    if _vocab is None:
        data = json.loads(models.path("siglip-base/tokenizer.json").read_text(encoding="utf-8"))["model"]["vocab"]
        _vocab = {piece: (i, float(score)) for i, (piece, score) in enumerate(data)}
        _longest = max(len(p) for p in _vocab)
    return _vocab


def tokens(text: str) -> list[int]:
    vocab = _load_vocab()
    t = unicodedata.normalize("NFKC", text).lower().translate(_PUNCT)
    t = "▁" + re.sub(r"\s+", " ", t).strip().replace(" ", "▁")
    n = len(t)
    score = [-math.inf] * (n + 1)
    back = [(-1, -1)] * (n + 1)
    score[0] = 0.0
    for e in range(1, n + 1):
        for s in range(max(0, e - _longest), e):
            if score[s] == -math.inf:
                continue
            got = vocab.get(t[s:e])
            if got is not None and score[s] + got[1] > score[e]:
                score[e] = score[s] + got[1]
                back[e] = (s, got[0])
        if back[e][0] < 0:
            score[e] = score[e - 1] - 10.0
            back[e] = (e - 1, 2)
    out: list[int] = []
    e = n
    while e > 0:
        s, tid = back[e]
        out.append(tid)
        e = s
    out = out[::-1][:SEQ - 1] + [1]
    return out + [1] * (SEQ - len(out))


def _unit(v: np.ndarray) -> np.ndarray:
    return (v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)).astype(np.float32)


def embed_images(rgb8s: list[np.ndarray]) -> np.ndarray:
    models.require(MODEL)
    from app.ai.nets import _run_lock
    s = models.session("search-vision", "siglip-base/vision_model_quantized.onnx")
    batch = []
    for im in rgb8s:
        interp = cv2.INTER_AREA if min(im.shape[:2]) > 224 else cv2.INTER_CUBIC
        x = cv2.resize(im[..., :3], (224, 224), interpolation=interp).astype(np.float32) / 255.0
        batch.append(((x - 0.5) / 0.5).transpose(2, 0, 1))
    with _run_lock:
        out = s.run(None, {"pixel_values": np.stack(batch).astype(np.float32)})[1]
    return _unit(np.asarray(out, np.float32))


def embed_text(text: str) -> np.ndarray:
    key = text.strip().lower()
    with _lock:
        if key in _texts:
            _texts.move_to_end(key)
            return _texts[key]
    models.require(MODEL)
    from app.ai.nets import _run_lock
    s = models.session("search-text", "siglip-base/text_model_quantized.onnx")
    ids = np.asarray([tokens(text)], np.int64)
    with _run_lock:
        out = s.run(None, {"input_ids": ids})[1][0]
    v = _unit(np.asarray(out, np.float32))
    with _lock:
        _texts[key] = v
        while len(_texts) > 64:
            _texts.popitem(last=False)
    return v


def probability(cos: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-(SCALE * cos + BIAS)))


def _db() -> sqlite3.Connection:
    db = sqlite3.connect(str(config.catalog_path().parent / "search.sqlite"), timeout=30)
    db.execute("CREATE TABLE IF NOT EXISTS vectors (photo_id INTEGER PRIMARY KEY, model TEXT NOT NULL, sig TEXT NOT NULL, v BLOB NOT NULL)")
    return db


def stored() -> dict[int, str]:
    with _lock, _db() as db:
        return {int(pid): sig for pid, sig in db.execute("SELECT photo_id, sig FROM vectors WHERE model=?", (SIG,))}


def save(rows: list[tuple[int, str, np.ndarray]]) -> None:
    global _matrix, _last
    with _lock, _db() as db:
        db.executemany("INSERT OR REPLACE INTO vectors (photo_id, model, sig, v) VALUES (?, ?, ?, ?)",
                       [(pid, SIG, sig, v.astype(np.float16).tobytes()) for pid, sig, v in rows])
        _matrix, _last = None, None


def forget(ids: list[int]) -> None:
    global _matrix, _last
    with _lock, _db() as db:
        db.executemany("DELETE FROM vectors WHERE photo_id=?", [(int(i),) for i in ids])
        _matrix, _last = None, None


def matrix() -> tuple[np.ndarray, np.ndarray]:
    global _matrix
    with _lock:
        if _matrix is None:
            with _db() as db:
                rows = db.execute("SELECT photo_id, v FROM vectors WHERE model=? ORDER BY photo_id", (SIG,)).fetchall()
            ids = np.asarray([r[0] for r in rows], np.int64)
            vecs = np.frombuffer(b"".join(r[1] for r in rows), np.float16).reshape(-1, DIM) if rows else np.zeros((0, DIM), np.float16)
            _matrix = (ids, vecs)
        return _matrix


def rank(query: np.ndarray, within: set[int] | None = None, floor: float = -2.0) -> list[tuple[int, float]]:
    ids, vecs = matrix()
    if not len(ids):
        return []
    cos = np.concatenate([vecs[k:k + 8192].astype(np.float32) @ query for k in range(0, len(vecs), 8192)])
    keep = cos >= floor
    if within is not None:
        keep &= np.isin(ids, np.fromiter(within, np.int64, len(within)))
    idx = np.nonzero(keep)[0]
    idx = idx[np.argsort(-cos[idx], kind="stable")]
    return list(zip(ids[idx].tolist(), cos[idx].tolist()))


def matches(text: str, within: set[int] | None = None, min_probability: float = MATCH) -> list[tuple[int, float]]:
    global _last
    floor = (math.log(min_probability / (1.0 - min_probability)) - BIAS) / SCALE
    if within is not None:
        return rank(embed_text(text), within, floor)
    key = (text.strip().lower(), floor)
    if _last is not None and _last[0] == key:
        return _last[1]
    out = rank(embed_text(text), None, floor)
    _last = (key, out)
    return out
