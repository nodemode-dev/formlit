import copy
from typing import Any

import numpy as np

from app.ai import models, semantic
from app.develop import settings as S
from app.engine import catalog as catalog_mod
from app.engine.cmd_develop import after, current, store
from app.engine.commands import CommandError, command, resolve_ids
from app.services import previews

CONTROLS = ("light.exposure", "light.contrast", "light.highlights", "light.shadows", "light.whites", "light.blacks",
            "color.vibrance", "color.saturation", "effects.texture", "effects.clarity", "effects.dehaze")


def _level(pid: int) -> float:
    img, _ = previews.source(pid)
    y = np.asarray(img, np.float32)[::4, ::4] @ np.array([0.2627, 0.678, 0.0593], np.float32)
    return float(np.log2(max(float(np.median(y)), 1e-5)))


def examples(exclude: set[int] | None = None) -> list[dict]:
    cat = catalog_mod.get()
    rows = cat.rows("SELECT id FROM photos WHERE edited=1 AND kind != 'video'")
    ids, vecs = semantic.matrix()
    index = {int(p): i for i, p in enumerate(ids.tolist())}
    out = []
    for r in rows:
        pid = int(r["id"])
        if (exclude and pid in exclude) or pid not in index:
            continue
        dev, _ = current(pid)
        vals = [float(S.get(dev, c)) for c in CONTROLS]
        if not any(abs(v) > 1e-6 for v in vals):
            continue
        out.append({"id": pid, "vec": vecs[index[pid]].astype(np.float32), "values": vals})
    return out


DEFAULT = ["match"] + ["knn"] * (len(CONTROLS) - 1)
MIN_CALIBRATE = 24


def _levels(pool: list[dict]) -> np.ndarray:
    for e in pool:
        if e.get("level") is None:
            e["level"] = _level(e["id"])
    return np.array([e["level"] for e in pool], np.float64)


def _weights(sims: np.ndarray, k: int) -> np.ndarray:
    k = max(1, min(int(k), sims.shape[1]))
    idx = np.argpartition(-sims, k - 1, axis=1)[:, :k]
    s = np.take_along_axis(sims, idx, 1)
    top = np.max(np.where(np.isfinite(s), s, -1e9), axis=1, keepdims=True)
    w = np.where(np.isfinite(s), np.exp(np.clip((s - top) * 20.0, -60.0, 0.0)), 0.0)
    w /= np.maximum(w.sum(1, keepdims=True), 1e-12)
    out = np.zeros(sims.shape, np.float64)
    np.put_along_axis(out, idx, w, 1)
    return out


def _loo(V: np.ndarray, Y: np.ndarray, L: np.ndarray, k: int, drop: int | None = None) -> dict[str, np.ndarray]:
    sims = (V @ V.T).astype(np.float64)
    np.fill_diagonal(sims, -np.inf)
    keep = np.ones(len(Y), bool)
    if drop is not None:
        sims[:, drop] = -np.inf
        keep[drop] = False
    W = _weights(sims, k)
    knn = W @ Y
    match = knn.copy()
    match[:, 0] += W @ L - L
    n = max(int(keep.sum()) - 1, 1)
    average = (Y[keep].sum(0)[None, :] - Y * keep[:, None]) / n
    return {"knn": knn, "match": match, "average": average}


def calibrate(V: np.ndarray, Y: np.ndarray, L: np.ndarray, k: int, drop: int | None = None) -> list[str]:
    rows = np.arange(len(Y)) != (-1 if drop is None else drop)
    if rows.sum() < MIN_CALIBRATE:
        return list(DEFAULT)
    preds = _loo(V, Y, L, k, drop)
    out = []
    for c, base in enumerate(DEFAULT):
        opts = ("match", "knn", "average") if c == 0 else ("knn", "average")
        errs = {m: float(np.mean(np.abs(preds[m][rows, c] - Y[rows, c]))) for m in opts}
        best = min(opts, key=lambda m: errs[m])
        out.append(best if errs[best] < 0.85 * errs[base] else base)
    return out


def predict(pid: int, pool: list[dict], k: int = 5, choice: list[str] | None = None) -> tuple[list[float], list[tuple[int, float]]]:
    ids, vecs = semantic.matrix()
    where = np.nonzero(ids == pid)[0]
    if not len(where):
        raise CommandError(f"Photo {pid} is not indexed for search yet; run search.index first")
    me = vecs[int(where[0])].astype(np.float32)
    V = np.stack([e["vec"] for e in pool])
    Y = np.array([e["values"] for e in pool], np.float64)
    sims = (V @ me).astype(np.float64)[None, :]
    w = _weights(sims, k)[0]
    knn = w @ Y
    match = knn.copy()
    match[0] += float(w @ _levels(pool)) - _level(pid)
    preds = {"knn": knn, "match": match, "average": Y.mean(0)}
    vals = [float(preds[m][c]) for c, m in enumerate(choice or DEFAULT)]
    order = np.argsort(-sims[0])[:max(1, k)]
    return vals, [(pool[i]["id"], round(float(sims[0, i]), 3)) for i in order]


@command("develop.styleCheck", "Check My Style", {"k": {"type": "integer"}}, mutates=False,
         description="Measures how well Apply My Style would work on this catalog: each edited photo is predicted from the others (leave one out) and compared with your own edit, beside two baselines, the average of your edits and no edit. Exposure in stops, the other controls in slider points. Changes nothing.")
def style_check(k: int = 5) -> dict:
    models.require(semantic.MODEL)
    pool = examples()
    if len(pool) < 6:
        raise CommandError(f"Edit at least six photos first; {len(pool)} edited photos are indexed for search")
    k = int(k or 5)
    V = np.stack([e["vec"] for e in pool])
    Y = np.array([e["values"] for e in pool], np.float64)
    L = _levels(pool)
    preds = _loo(V, Y, L, k)
    style = np.array([[preds[m][i, c] for c, m in enumerate(calibrate(V, Y, L, k, drop=i))] for i in range(len(Y))])
    guesses = {"style": style, "fixed": np.stack([preds[m][:, c] for c, m in enumerate(DEFAULT)], 1),
               "average": preds["average"], "none": np.zeros_like(Y)}
    out = {}
    for name, g in guesses.items():
        a = np.abs(g - Y)
        out[name] = {"exposure": round(float(np.mean(a[:, 0])), 2), "others": round(float(np.mean(a[:, 1:])), 1), "othersMedian": round(float(np.median(a[:, 1:])), 1)}
    best = min(out, key=lambda n: out[n]["exposure"] + out[n]["others"] / 20.0)
    return {"photos": len(pool), "k": k, "errors": out, "better": best == "style",
            "methods": dict(zip(CONTROLS, calibrate(V, Y, L, k))), "controls": list(CONTROLS)}


@command("develop.applyStyle", "Apply My Style", {"ids": {"type": "array"}, "amount": {"type": "number", "description": "0 to 100"}, "k": {"type": "integer"}},
         description="Learns your style from the photos you have edited: for each photo, finds the edited photos most like it (by content, through the search model) and gives it their tone and presence settings, weighted by likeness, with exposure moved by the difference in brightness. Needs some edited photos and the search model.")
def apply_style(ids: Any = None, amount: float = 100.0, k: int = 5) -> dict:
    models.require(semantic.MODEL)
    pids = resolve_ids(ids)
    pool = examples(set(pids))
    if len(pool) < 3:
        raise CommandError("Edit at least three photos first: the style is learned from your edited photos")
    a = min(max(float(amount), 0.0), 100.0) / 100.0
    choice = calibrate(np.stack([e["vec"] for e in pool]), np.array([e["values"] for e in pool], np.float64), _levels(pool), int(k or 5)) if len(pool) >= 6 else DEFAULT
    report = []
    with catalog_mod.get().change("Apply My Style") as ch:
        for pid in pids:
            vals, near = predict(pid, pool, int(k or 5), choice)
            dev, _ = current(pid)
            new = copy.deepcopy(dev)
            for cid, v in zip(CONTROLS, vals):
                spec = S.controls()[cid]
                S.put(new, cid, round(min(max(float(S.get(dev, cid)) * (1 - a) + v * a, spec["min"]), spec["max"]), 2))
            store(ch, pid, new, "Apply My Style")
            report.append({"id": pid, "like": near, "values": {c: round(v, 2) for c, v in zip(CONTROLS, vals)}})
    after(pids)
    return {"ids": pids, "learnedFrom": len(pool), "methods": dict(zip(CONTROLS, choice)), "photos": report}
