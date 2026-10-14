import copy
from typing import Any

import cv2
import numpy as np

from app.ai import models, nets, skin
from app.develop.render import effective, plan
from app.develop.retouch import auto_source
from app.engine import catalog as catalog_mod
from app.engine import tasks
from app.engine.cmd_ai import VIEW_DROP, _maybe_wait, _part_maps, save_bitmap, view_rgb8
from app.engine.cmd_develop import after, current, store
from app.engine.commands import CommandError, command, resolve_ids
from app.services import previews

MASK_NAME = "Skin Retouch"
TAG = "skin"
WORK = 2048


def _clean(dev: dict) -> dict:
    out = copy.deepcopy(dev)
    out["spots"] = [s for s in out.get("spots") or [] if s.get("auto") != TAG]
    out["masks"] = [m for m in out.get("masks") or [] if m.get("name") != MASK_NAME]
    return out


def retouch_one(pid: int, smooth: float, shine: float, blemish: bool, sensitivity: float, keep_freckles: bool, max_size: float = 3.0) -> tuple[dict, dict]:
    dev, _ = current(pid)
    base = _clean(dev)
    img, info = previews.source(pid)
    view = {k: v for k, v in base.items() if k not in VIEW_DROP}
    rgb = view_rgb8(pid, base, WORK)
    frame, w, h, ppl = plan(img.shape[1], img.shape[0], effective(view, info), WORK, apply_crop=False)
    if (w, h) != (rgb.shape[1], rgb.shape[0]):
        rgb = cv2.resize(rgb, (w, h), interpolation=cv2.INTER_AREA)
    small = cv2.resize(rgb, (max(1, w // 2), max(1, h // 2)), interpolation=cv2.INTER_AREA) if max(w, h) > 1100 else rgb
    faces = nets.faces(small)
    report = {"id": pid, "faces": len(faces), "blemishes": 0}
    if not faces:
        return dev, report
    maps = _part_maps(small, "people")
    face_skin, body_skin = maps.get("faceSkin"), maps.get("bodySkin")
    if face_skin is None or body_skin is None:
        return dev, report
    new = base
    if smooth > 0 or shine > 0:
        save_bitmap(pid, "adaptive-faceSkin", face_skin)
        save_bitmap(pid, "adaptive-bodySkin", body_skin)
        adjust = {k: v for k, v in (("texture", round(-0.7 * smooth)), ("clarity", round(-0.25 * smooth)), ("highlights", round(-0.6 * shine))) if v}
        nid = max([int(m.get("id", 0)) for m in new.get("masks") or []] + [0]) + 1
        new["masks"] = (new.get("masks") or []) + [{"id": nid, "name": MASK_NAME, "visible": True, "adjust": adjust, "components": [
            {"shape": {"kind": "people", "part": "faceSkin", "label": "Face Skin", "bitmap": "adaptive-faceSkin"}, "op": "add"},
            {"shape": {"kind": "people", "part": "bodySkin", "label": "Body Skin", "bitmap": "adaptive-bodySkin"}, "op": "add"}]}]
    if blemish:
        sk = cv2.resize(np.maximum(face_skin, body_skin), (w, h), interpolation=cv2.INTER_LINEAR)
        found = skin.blemishes(rgb, sk, faces, sensitivity, keep_freckles, max_size=max_size)
        n = np.asarray(frame.out_to_norm(w, h), np.float64)
        work = rgb.astype(np.float32) / 255.0
        spots = []
        for x, y, r, _ in found:
            dx, dy = auto_source(work, (x + 0.5, y + 0.5), r)
            p = n @ np.array([x + 0.5, y + 0.5, 1.0])
            spots.append({"mode": "heal", "points": [[round(float(p[0]), 6), round(float(p[1]), 6)]], "size": round(r / ppl, 6), "feather": 40.0, "opacity": 100.0,
                          "source": [round(float(n[0, 0] * dx + n[0, 1] * dy), 6), round(float(n[1, 0] * dx + n[1, 1] * dy), 6)], "auto": TAG})
        new["spots"] = (new.get("spots") or []) + spots
        report["blemishes"] = len(spots)
    return new, report


@command("retouch.skin", "Retouch Skin", {"ids": {"type": "array"}, "smooth": {"type": "number", "description": "0 to 100: softens skin texture (texture and clarity on a skin mask)"},
                                          "blemishes": {"type": "boolean", "description": "heal spots found on the skin"}, "sensitivity": {"type": "number", "description": "0 to 100, how faint a blemish may be"},
                                          "keepFreckles": {"type": "boolean", "description": "leave freckles and moles (brown spots); only red spots are healed"},
                                          "shine": {"type": "number", "description": "0 to 100: tames bright shine on skin"},
                                          "maxSize": {"type": "number", "description": "largest spot healed, as a percent of the face width (0.5 to 8, default 3)"}, "wait": {"type": "boolean"}},
         description="Batch skin retouching: for every photo with a face, adds a Skin Retouch mask over face and body skin (softer texture, optional shine) and heal spots on blemishes it finds, all as normal editable settings. Photos without a face are left alone. Running it again replaces its own mask and spots, so amounts can be changed.")
def retouch_skin(ids: Any = None, smooth: float = 40.0, blemishes: bool = True, sensitivity: float = 50.0, keepFreckles: bool = True, shine: float = 0.0, maxSize: float = 3.0, wait: bool = False) -> dict:
    pids = resolve_ids(ids)
    for m in ("faces", "people"):
        models.require(m)
    smooth, shine, sensitivity = (min(max(float(v), 0.0), 100.0) for v in (smooth, shine, sensitivity))
    if smooth <= 0 and shine <= 0 and not blemishes:
        raise CommandError("Nothing to do: set smooth or shine above 0, or blemishes on")

    def job(progress) -> dict:
        changed, reports = {}, []
        for i, pid in enumerate(pids):
            if progress.cancelled:
                break
            progress(i, len(pids), f"Retouching skin {i + 1} of {len(pids)}")
            try:
                new, rep = retouch_one(pid, smooth, shine, blemishes, sensitivity, keepFreckles, float(maxSize or 3.0))
            except Exception as exc:
                reports.append({"id": pid, "error": str(exc)})
                continue
            reports.append(rep)
            if rep["faces"]:
                changed[pid] = new
        if changed:
            with catalog_mod.get().change("Retouch Skin") as ch:
                for pid, new in changed.items():
                    store(ch, pid, new, "Retouch Skin")
            after(list(changed))
        progress(len(pids), len(pids), "Retouching skin")
        return {"ids": list(changed), "skipped": [r["id"] for r in reports if not r.get("faces")], "photos": reports}
    return _maybe_wait(tasks.start("retouch", "Retouch Skin", job), wait)
