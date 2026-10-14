import threading
from typing import Any

import cv2
import numpy as np

from app.ai import models, semantic
from app.engine import catalog as catalog_mod
from app.engine import events, tasks
from app.engine.commands import CommandError, command, resolve_ids
from app.services import previews

_state = {"task": None}
_guard = threading.Lock()


def _signatures(ids: list[int] | None = None) -> dict[int, str]:
    cat = catalog_mod.get()
    sql = "SELECT id, content_hash, file_size, file_mtime FROM photos WHERE kind != 'video'"
    rows = cat.rows(sql) if ids is None else [r for chunk in range(0, len(ids), 500)
                                             for r in cat.rows(f"{sql} AND id IN ({','.join('?' * len(ids[chunk:chunk + 500]))})", tuple(ids[chunk:chunk + 500]))]
    return {int(r["id"]): (r["content_hash"] or f"{r['file_size']}:{r['file_mtime']}") for r in rows}


def _pending(ids: list[int] | None = None) -> dict[int, str]:
    have = semantic.stored()
    return {pid: sig for pid, sig in _signatures(ids).items() if have.get(pid) != sig}


def _running() -> int | None:
    tid = _state["task"]
    if tid is None:
        return None
    t = tasks.get(tid)
    return tid if t and t["state"] == "running" else None


def _start(ids: list[int] | None = None) -> int | None:
    with _guard:
        tid = _running()
        if tid is not None:
            return tid
        if ids is None:
            gone = set(semantic.stored()) - set(_signatures())
            if gone:
                semantic.forget(sorted(gone))
        todo = _pending(ids)
        if not todo:
            return None

        def job(progress) -> dict:
            items = list(todo.items())
            done, failed = 0, 0
            for k in range(0, len(items), 4):
                if progress.cancelled:
                    break
                part, imgs = [], []
                for pid, sig in items[k:k + 4]:
                    try:
                        im = cv2.imread(str(previews.rendered(pid, "t")), cv2.IMREAD_COLOR)
                        if im is None:
                            raise OSError("unreadable preview")
                        imgs.append(cv2.cvtColor(im, cv2.COLOR_BGR2RGB))
                        part.append((pid, sig))
                    except Exception:
                        failed += 1
                if imgs:
                    vecs = semantic.embed_images(imgs)
                    semantic.save([(pid, sig, v) for (pid, sig), v in zip(part, vecs)])
                done = min(len(items), k + 4)
                progress(done, len(items), f"Indexing photos for search, {done} of {len(items)}")
            events.publish("search", state="indexed", count=done - failed)
            return {"indexed": done - failed, "failed": failed}
        tid = tasks.start("search", "Indexing photos for search", job)
        _state["task"] = tid
        return tid


def _status() -> dict:
    sigs = _signatures()
    have = semantic.stored()
    indexed = sum(1 for pid, sig in sigs.items() if have.get(pid) == sig)
    return {"ready": models.ready(semantic.MODEL), "indexed": indexed, "total": len(sigs), "missing": len(sigs) - indexed, "indexing": _running()}


@command("search.status", "Search Index Status", {"start": {"type": "boolean", "description": "start indexing the photos not indexed yet"}}, mutates=False,
         description="How many photos are ready for searching by description, and whether indexing is running. start begins indexing the rest in the background (needs the search model).")
def search_status(start: bool = False) -> dict:
    out = _status()
    if start and out["ready"] and out["missing"]:
        out["indexing"] = _start()
    return out


@command("search.index", "Index Photos for Search", {"ids": {"type": "array"}, "wait": {"type": "boolean"}}, mutates=False,
         description="Reads each photo once with the search model so it can be found by description; only new or changed photos are read. All photos when ids is left out.")
def search_index(ids: Any = None, wait: bool = False) -> dict:
    models.require(semantic.MODEL)
    tid = _start(None if ids is None else resolve_ids(ids))
    if tid is None:
        return {"indexed": 0, **_status()}
    if not wait:
        return {"task": tid}
    t = tasks.wait(tid, 3600)
    if t and t["state"] == "failed":
        raise CommandError(t["error"] or "Indexing failed")
    return {"task": tid, **((t or {}).get("result") or {}), **_status()}


def _scope(ids: Any) -> set[int] | None:
    return None if ids is None else set(resolve_ids(ids))


@command("search.describe", "Search by Description", {"text": {"type": "string"}, "ids": {"type": "array", "description": "search only among these photos"},
                                                       "limit": {"type": "integer"}, "strict": {"type": "boolean", "description": "only close matches"}}, mutates=False,
         description="Finds photos by what is in them, from a plain description such as 'two people on a beach at sunset' or 'red car in the rain', best match first. Only indexed photos can be found; missing says how many are not indexed yet.")
def search_describe(text: str = "", ids: Any = None, limit: int = 50, strict: bool = False) -> dict:
    text = (text or "").strip()
    if not text:
        raise CommandError("Describe what is in the photos you want")
    models.require(semantic.MODEL)
    hits = semantic.matches(text, _scope(ids), semantic.STRICT if strict else semantic.MATCH)
    live = set(_signatures([pid for pid, _ in hits])) if hits else set()
    hits = [(pid, cos) for pid, cos in hits if pid in live][:max(1, int(limit or 50))]
    st = _status()
    return {"ids": [pid for pid, _ in hits], "scores": [round(float(semantic.probability(np.float32(c))), 4) for _, c in hits],
            "indexed": st["indexed"], "missing": st["missing"]}


@command("search.similar", "Find Similar Photos", {"id": {"type": "integer"}, "limit": {"type": "integer"}}, mutates=False,
         description="Photos that look most like the given one (content and scene, not exact copies), most similar first, with a similarity from 0 to 1.")
def search_similar(id: int | None = None, limit: int = 30) -> dict:
    pid = int(id) if id is not None else resolve_ids("active")[0]
    models.require(semantic.MODEL)
    sig = _signatures([pid]).get(pid)
    if sig is None:
        raise CommandError(f"No photo with id {pid} that can be searched")
    if semantic.stored().get(pid) != sig:
        im = cv2.imread(str(previews.rendered(pid, "t")), cv2.IMREAD_COLOR)
        if im is None:
            raise CommandError("Could not read this photo's preview")
        semantic.save([(pid, sig, semantic.embed_images([cv2.cvtColor(im, cv2.COLOR_BGR2RGB)])[0])])
    ids_, vecs = semantic.matrix()
    me = vecs[int(np.searchsorted(ids_, pid))].astype(np.float32)
    live = set(_signatures())
    out = [(p, c) for p, c in semantic.rank(me) if p != pid and p in live][:max(1, int(limit or 30))]
    return {"ids": [p for p, _ in out], "similarity": [round(max(0.0, c), 3) for _, c in out]}
