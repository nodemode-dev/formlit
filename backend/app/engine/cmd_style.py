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


def predict(pid: int, pool: list[dict], k: int = 5) -> tuple[list[float], list[tuple[int, float]]]:
    ids, vecs = semantic.matrix()
    where = np.nonzero(ids == pid)[0]
    if not len(where):
        raise CommandError(f"Photo {pid} is not indexed for search yet; run search.index first")
    me = vecs[int(where[0])].astype(np.float32)
    sims = np.array([float(e["vec"] @ me) for e in pool])
    order = np.argsort(-sims)[:max(1, k)]
    w = np.exp((sims[order] - sims[order].max()) * 20.0)
    w /= w.sum()
    vals = np.sum([w[j] * np.array(pool[i]["values"]) for j, i in enumerate(order)], axis=0)
    level = _level(pid)
    shift = float(np.sum([w[j] * (_level(pool[i]["id"]) - level) for j, i in enumerate(order)]))
    vals[0] += shift
    return [float(v) for v in vals], [(pool[i]["id"], round(float(sims[i]), 3)) for i in order]


@command("develop.styleCheck", "Check My Style", {"k": {"type": "integer"}}, mutates=False,
         description="Measures how well Apply My Style would work on this catalog: each edited photo is predicted from the others (leave one out) and compared with your own edit, beside two baselines, the average of your edits and no edit. Exposure in stops, the other controls in slider points. Changes nothing.")
def style_check(k: int = 5) -> dict:
    models.require(semantic.MODEL)
    pool = examples()
    if len(pool) < 6:
        raise CommandError(f"Edit at least six photos first; {len(pool)} edited photos are indexed for search")
    errs = {"style": [], "average": [], "none": []}
    for i, e in enumerate(pool):
        rest = pool[:i] + pool[i + 1:]
        truth = np.array(e["values"])
        pred = np.array(predict(e["id"], rest, int(k or 5))[0])
        mean = np.mean([r["values"] for r in rest], axis=0)
        for name, guess in (("style", pred), ("average", mean), ("none", np.zeros_like(truth))):
            errs[name].append(np.abs(guess - truth))
    out = {}
    for name, rows in errs.items():
        a = np.array(rows)
        out[name] = {"exposure": round(float(np.mean(a[:, 0])), 2), "others": round(float(np.mean(a[:, 1:])), 1), "othersMedian": round(float(np.median(a[:, 1:])), 1)}
    best = min(out, key=lambda n: out[n]["exposure"] + out[n]["others"] / 20.0)
    return {"photos": len(pool), "k": int(k or 5), "errors": out, "better": best == "style",
            "controls": list(CONTROLS)}


@command("develop.applyStyle", "Apply My Style", {"ids": {"type": "array"}, "amount": {"type": "number", "description": "0 to 100"}, "k": {"type": "integer"}},
         description="Learns your style from the photos you have edited: for each photo, finds the edited photos most like it (by content, through the search model) and gives it their tone and presence settings, weighted by likeness, with exposure moved by the difference in brightness. Needs some edited photos and the search model.")
def apply_style(ids: Any = None, amount: float = 100.0, k: int = 5) -> dict:
    models.require(semantic.MODEL)
    pids = resolve_ids(ids)
    pool = examples(set(pids))
    if len(pool) < 3:
        raise CommandError("Edit at least three photos first: the style is learned from your edited photos")
    a = min(max(float(amount), 0.0), 100.0) / 100.0
    report = []
    with catalog_mod.get().change("Apply My Style") as ch:
        for pid in pids:
            vals, near = predict(pid, pool, int(k or 5))
            dev, _ = current(pid)
            new = copy.deepcopy(dev)
            for cid, v in zip(CONTROLS, vals):
                spec = S.controls()[cid]
                S.put(new, cid, round(min(max(float(S.get(dev, cid)) * (1 - a) + v * a, spec["min"]), spec["max"]), 2))
            store(ch, pid, new, "Apply My Style")
            report.append({"id": pid, "like": near, "values": {c: round(v, 2) for c, v in zip(CONTROLS, vals)}})
    after(pids)
    return {"ids": pids, "learnedFrom": len(pool), "photos": report}
