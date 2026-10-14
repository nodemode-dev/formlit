import copy
import json
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.ai import cull as cull_mod
from app.ai import dng, enhance, merge, models, nets, upright as upright_mod
from app.core import config
from app.develop import settings as S
from app.develop.masks import bitmap_path
from app.develop.render import effective, render, to_u8
from app.engine import catalog as catalog_mod
from app.engine import tasks
from app.engine.cmd_develop import after, current, store
from app.engine.commands import CommandError, command, resolve_ids
from app.engine.records import loads
from app.services import previews

VIEW_DROP = ("crop", "masks", "vignette", "grain", "lensBlur")


def cat():
    return catalog_mod.get()


FACE_PARTS = {"faceSkin", "eyebrows", "sclera", "iris", "lips", "teeth", "hair"}


def _need(model: str) -> None:
    try:
        models.require(model)
    except models.ModelMissing as exc:
        raise CommandError(str(exc), 409) from exc


def view_rgb8(pid: int, dev: dict | None = None, long: int = 1024, keep: tuple = ()) -> np.ndarray:
    if dev is None:
        dev, _ = current(pid)
    view = {k: v for k, v in (dev or {}).items() if k not in VIEW_DROP or k in keep}
    img, info = previews.source(pid)
    return to_u8(render(img, info, view, max_long=long, photo_id=pid, apply_crop=False))


def save_bitmap(pid: int, key: str, a: np.ndarray) -> None:
    p = bitmap_path(pid, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(p), np.clip(a * 65535.0 + 0.5, 0, 65535).astype(np.uint16))


@command("ai.models", "AI Models", mutates=False)
def ai_models() -> dict:
    try:
        prov = models.providers()
    except Exception:
        prov = []
    return {"models": models.catalogue(), "providers": prov}


@command("ai.download", "Install AI Model", {"model": {"type": "string", "enum": list(models.MODELS)}, "wait": {"type": "boolean"}})
def ai_download(model: str, wait: bool = False) -> dict:
    if model not in models.MODELS:
        raise CommandError(f"Unknown model {model}; see ai.models")
    tid = tasks.start("model", f"Installing {models.MODELS[model]['name']}", lambda p: models.download(model, p))
    if wait:
        t = tasks.wait(tid, 3600)
        if t and t["state"] == "failed":
            raise CommandError(t["error"] or "Download failed")
    return {"task": tid, "model": model}


def _people(rgb8: np.ndarray) -> tuple[np.ndarray, list[dict], list[dict]]:
    from app.ai import people as people_mod
    _need("people")
    alpha = nets.u2net(rgb8, "people")
    ready = models.ready("faces")
    faces = nets.faces(rgb8) if ready else []
    if models.ready("instances"):
        return alpha, faces, people_mod.from_instances(alpha, nets.instances(rgb8))
    found = people_mod.persons(rgb8, alpha, faces, components=True)
    if len(found) > 1 and models.ready("objects"):
        found = people_mod.refine(alpha, found, lambda prompts: nets.sam_prompts(rgb8, prompts))
    return alpha, faces, found


def _part_maps(rgb8: np.ndarray, group: str, person: int | None = None) -> dict[str, np.ndarray]:
    from app.ai import parts as parts_mod
    if group == "people":
        alpha, faces, found = _people(rgb8)
        if person is not None:
            if person >= len(found):
                return {k: np.zeros(alpha.shape, np.float32) for k in parts_mod.PERSON_PARTS}
            box = found[person]["box"]
            faces = [f for f in faces if abs((f["box"][0] + f["box"][2]) / 2 - (box[0] + box[2]) / 2) < (box[2] - box[0]) / 2 + 1e-3] or faces
            alpha = found[person]["alpha"]
        return parts_mod.people_parts(rgb8, alpha, faces, nets.person_classes(rgb8) if models.ready("parts") else None)
    sky = nets.sky(rgb8) if models.ready("sky") else None
    dep = nets.depth(rgb8) if models.ready("depth") else None
    return parts_mod.landscape_parts(rgb8, sky, dep)


@command("develop.aiParts", "AI Mask Parts", {"id": {"type": "integer"}, "group": {"type": "string", "enum": ["people", "landscape"]},
                                             "parts": {"type": "array", "description": "people: faceSkin, bodySkin, eyebrows, sclera, iris, lips, teeth, hair, clothes; landscape: sky, water, vegetation, mountains, architecture, naturalGround, artificialGround"},
                                             "person": {"type": "integer", "description": "people only: the person's index from develop.aiPeople, left to right; omit for everyone"}})
def ai_parts(group: str, parts: list[str], id: int | None = None, person: int | None = None) -> dict:
    from app.ai import parts as parts_mod
    pid = int(id) if id is not None else resolve_ids("active")[0]
    names = parts_mod.PERSON_PARTS if group == "people" else parts_mod.LANDSCAPE_PARTS
    want = [p for p in parts if p in names]
    if not want:
        raise CommandError("Choose one or more parts: " + ", ".join(names))
    if group == "people" and set(want) & FACE_PARTS:
        _need("people")
        _need("faces")
    maps = _part_maps(view_rgb8(pid), group, person if group == "people" else None)
    shapes = []
    stamp = int(time.time() * 1000)
    for p in want:
        key = f"{group}-{p}-{stamp}"
        save_bitmap(pid, key, maps[p])
        shape = {"kind": group, "part": p, "label": names[p] if person is None else f"{names[p]}, Person {person + 1}", "bitmap": key, "coverage": round(float(maps[p].mean()), 4)}
        if person is not None and group == "people":
            shape["person"] = int(person)
        shapes.append(shape)
    return {"shapes": shapes}


@command("develop.aiPeople", "Detect People", {"id": {"type": "integer"}})
def ai_people(id: int | None = None) -> dict:
    import base64
    pid = int(id) if id is not None else resolve_ids("active")[0]
    rgb8 = view_rgb8(pid)
    alpha, _faces, found = _people(rgb8)
    stamp = int(time.time() * 1000)
    save_bitmap(pid, f"people-{stamp}", alpha)
    h, w = rgb8.shape[:2]
    out = []
    for i, p in enumerate(found):
        key = f"people-p{i}-{stamp}"
        save_bitmap(pid, key, p["alpha"])
        x0, y0, x1, y1 = p["box"]
        pad = 0.35 * max(x1 - x0, y1 - y0)
        crop = rgb8[max(0, int((y0 - pad) * h)):min(h, int((y1 + pad) * h)), max(0, int((x0 - pad) * w)):min(w, int((x1 + pad) * w))]
        thumb = ""
        if crop.size:
            crop = cv2.resize(crop, (64, max(1, int(64 * crop.shape[0] / max(1, crop.shape[1])))), interpolation=cv2.INTER_AREA)
            ok, buf = cv2.imencode(".jpg", cv2.cvtColor(crop, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 82])
            thumb = base64.b64encode(buf.tobytes()).decode() if ok else ""
        out.append({"index": i, "box": [round(v, 4) for v in p["box"]], "coverage": round(float(p["alpha"].mean()), 4), "thumb": thumb,
                    "shape": {"kind": "people", "person": i, "bitmap": key}})
    return {"all": {"kind": "people", "bitmap": f"people-{stamp}"}, "persons": out}


@command("develop.aiMask", "AI Mask", {"id": {"type": "integer"}, "kind": {"type": "string", "enum": ["subject", "background", "sky", "people", "object", "depth"]},
                                       "box": {"type": "array"}, "points": {"type": "array"}})
def ai_mask(kind: str, id: int | None = None, box: list[float] | None = None, points: list[list[float]] | None = None) -> dict:
    pid = int(id) if id is not None else resolve_ids("active")[0]
    need = {"subject": "subject", "background": "subject", "sky": "sky", "people": "people", "object": "objects", "depth": "depth"}.get(kind)
    if need is None:
        raise CommandError("kind is subject, background, sky, people, object or depth")
    _need(need)
    rgb8 = view_rgb8(pid)
    if kind in ("subject", "background"):
        a = nets.u2net(rgb8, "subject")
        if kind == "background":
            a = 1.0 - a
    elif kind == "people":
        a = nets.u2net(rgb8, "people")
    elif kind == "sky":
        a = nets.sky(rgb8)
    elif kind == "object":
        a = nets.sam_box(rgb8, box or (None if points else [0.25, 0.25, 0.75, 0.75]), points)
    else:
        a = nets.depth(rgb8)
    key = f"{kind}-{int(time.time() * 1000)}"
    save_bitmap(pid, key, a)
    shape: dict = {"kind": "depthRange" if kind == "depth" else kind, "bitmap": key, "coverage": round(float(a.mean()), 4)}
    if kind == "object":
        if box or not points:
            shape["box"] = [round(float(v), 4) for v in (box or [0.25, 0.25, 0.75, 0.75])]
        if points:
            shape["points"] = points
    return {"shape": shape, "coverage": round(float(a.mean()), 4)}


@command("develop.maskOutline", "Mask Edge Points", {"id": {"type": "integer"}, "bitmap": {"type": "string"}, "dots": {"type": "integer", "minimum": 8, "maximum": 400}}, mutates=False)
def mask_outline(bitmap: str, id: int | None = None, dots: int = 64) -> dict:
    from app.develop.masks import _read_bitmap
    pid = int(id) if id is not None else resolve_ids("active")[0]
    p = bitmap_path(pid, bitmap)
    if not p.is_file():
        raise CommandError("That mask has no bitmap on this photo yet")
    st = p.stat()
    bm = _read_bitmap(str(p), st.st_mtime_ns, st.st_size)
    bh, bw = bm.shape
    found, _ = cv2.findContours((bm > 0.5).astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    polys = []
    for c in sorted(found, key=cv2.contourArea, reverse=True):
        if cv2.contourArea(c) < 0.0015 * bw * bh or len(polys) >= 12:
            continue
        per = cv2.arcLength(c, True)
        n = int(max(8, min(int(dots), per / max(bw, bh) * dots * 1.5)))
        eps = 0.002 * max(bw, bh)
        while True:
            a = cv2.approxPolyDP(c, eps, True)
            if len(a) <= n or eps > per:
                break
            eps *= 1.3
        if len(a) < 8:
            a = c[np.linspace(0, len(c) - 1, 8).astype(int)]
        polys.append([[round((float(x) + 0.5) / bw, 5), round((float(y) + 0.5) / bh, 5)] for x, y in a.reshape(-1, 2)])
    return {"polys": polys, "sig": st.st_size}


def bitmap_refs(dev: dict) -> list[dict]:
    refs = []
    for m in dev.get("masks") or []:
        for comp in m.get("components") or []:
            sh = comp.get("shape") or {}
            if sh.get("bitmap") and (sh.get("kind") in ("subject", "background", "sky", "people", "object", "landscape", "depthRange")):
                refs.append(sh)
    key = (dev.get("lensBlur") or {}).get("depth")
    if key:
        refs.append({"kind": "depthRange", "bitmap": key})
    return refs


def missing_bitmaps(pid: int, dev: dict | None = None) -> list[dict]:
    if dev is None:
        dev, _ = current(pid)
    seen, out = set(), []
    for sh in bitmap_refs(dev):
        if sh["bitmap"] not in seen and not bitmap_path(pid, sh["bitmap"]).is_file():
            seen.add(sh["bitmap"])
            out.append(sh)
    return out


def _family(pid: int) -> list[int]:
    master = int(cat().scalar("SELECT COALESCE(master_id, id) FROM photos WHERE id=?", (pid,)) or pid)
    return [master] + [int(r["id"]) for r in cat().rows("SELECT id FROM photos WHERE master_id=?", (master,))]


def compute_shape(pid: int, sh: dict, memo: dict) -> bool:
    import shutil
    key = sh["bitmap"]
    for other in _family(pid):
        src = bitmap_path(other, key)
        if other != pid and src.is_file():
            dst = bitmap_path(pid, key)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            return True
    kind = sh.get("kind")
    need = {"subject": "subject", "background": "subject", "sky": "sky", "people": "people", "object": "objects", "depthRange": "depth"}.get(kind or "")
    if (need and not sh.get("part") and not models.ready(need)) or (sh.get("part") and sh.get("kind") == "people" and not models.ready("people")):
        return False
    if "rgb8" not in memo:
        memo["rgb8"] = view_rgb8(pid)
    rgb8 = memo["rgb8"]
    if sh.get("part"):
        mk = f"parts:{kind}:{sh.get('person')}"
        if mk not in memo:
            memo[mk] = _part_maps(rgb8, str(kind), sh.get("person"))
        a = memo[mk].get(sh["part"])
        if a is None:
            return False
    elif kind == "people" and sh.get("person") is not None:
        if "persons" not in memo:
            memo["persons"] = _people(rgb8)[2]
        i = int(sh["person"])
        a = memo["persons"][i]["alpha"] if i < len(memo["persons"]) else np.zeros(rgb8.shape[:2], np.float32)
    elif kind in ("subject", "background"):
        if "subject" not in memo:
            memo["subject"] = nets.u2net(rgb8, "subject")
        a = memo["subject"] if kind == "subject" else 1.0 - memo["subject"]
    elif kind == "people":
        a = nets.u2net(rgb8, "people")
    elif kind == "sky":
        a = nets.sky(rgb8)
    elif kind == "object":
        a = nets.sam_box(rgb8, sh.get("box") or (None if sh.get("points") else [0.25, 0.25, 0.75, 0.75]), sh.get("points"))
    elif kind == "depthRange":
        if "depth" not in memo:
            memo["depth"] = nets.depth(rgb8)
        a = memo["depth"]
    else:
        return False
    save_bitmap(pid, key, a)
    return True


def ensure_masks(pid: int, dev: dict | None = None) -> int:
    from app.develop.render import drop_stages
    todo = missing_bitmaps(pid, dev)
    memo: dict = {}
    made = sum(1 for sh in todo if compute_shape(pid, sh, memo))
    if made:
        drop_stages(pid)
    return made


_adapting: set[int] = set()


def adapt(pids: list[int]) -> None:
    todo = [pid for pid in pids if pid not in _adapting and missing_bitmaps(pid)]
    if not todo:
        return
    _adapting.update(todo)

    def job(progress):
        from app.engine import events
        done = []
        try:
            for i, pid in enumerate(todo):
                progress(i, len(todo), f"Updating AI masks {i + 1} of {len(todo)}")
                try:
                    if ensure_masks(pid):
                        done.append(pid)
                except Exception:
                    continue
            if done:
                with cat().change("AI Masks Updated", undoable=False) as ch:
                    for pid in done:
                        rev = int(cat().scalar("SELECT develop_rev FROM photos WHERE id=?", (pid,)) or 0)
                        ch.update("photos", pid, develop_rev=rev + 1)
                for pid in done:
                    previews.request(pid, "t")
                    events.publish("masks.updated", id=pid)
            return {"ids": done}
        finally:
            _adapting.difference_update(todo)
    tasks.start("masks", "Updating AI masks", job)


@command("ai.depth", "Build Depth Map", {"ids": {"type": "array"}})
def ai_depth(ids: Any = None) -> dict:
    pids = resolve_ids(ids)
    _need("depth")
    out = {}
    with cat().change("Depth Map") as ch:
        for pid in pids:
            key = ai_mask("depth", pid)["shape"]["bitmap"]
            dev, _ = current(pid)
            new = copy.deepcopy(dev)
            new.setdefault("lensBlur", {})["depth"] = key
            if not S.get(new, "lensBlur.amount"):
                S.put(new, "lensBlur.amount", 50)
            store(ch, pid, new, "Lens Blur Depth")
            out[pid] = key
    after(pids)
    return {"ids": pids, "depth": out}


def _derived(src: int, path: Path, label: str, dev: dict, progress, stack: list[int] | None = None) -> int:
    from app.engine.cmd_library import stack_group
    from app.services import importer
    res = importer.import_files([str(path)], "add", "", "", "", "", dev, None, None, None, False, False, progress)
    if not res.get("ids"):
        raise CommandError(f"{label}: the new file could not be added to the catalog")
    new = int(res["ids"][0])
    row = cat().photo(src)
    if row is not None:
        with cat().change(label, undoable=False) as ch:
            ch.update("photos", new, capture_time=row["capture_time"], camera=row["camera"], lens=row["lens"], focal=row["focal"], aperture=row["aperture"],
                      shutter=row["shutter"], iso=row["iso"], gps_lat=row["gps_lat"], gps_lon=row["gps_lon"], rating=row["rating"], label=row["label"],
                      meta=loads(row["meta"], {}))
    group = [new, src] if stack is None else ([new, *[p for p in stack if p != new]] if stack else [])
    if len(group) > 1:
        try:
            stack_group(group)
        except CommandError:
            pass
    previews.request(new, "t")
    return new


def _out_path(src: int, suffix: str) -> Path:
    path = cat().photo_path(src)
    if path is None:
        raise CommandError(f"No photo with id {src}", 404)
    folder = path.parent
    target = folder / f"{path.stem}-{suffix}.dng"
    n = 2
    while target.exists():
        target = folder / f"{path.stem}-{suffix}-{n}.dng"
        n += 1
    return target


def _settings_for(src: int, drop: tuple) -> dict:
    dev, _ = current(src)
    return {k: v for k, v in dev.items() if k not in drop}


@command("ai.denoise", "Denoise", {"ids": {"type": "array"}, "amount": {"type": "number", "minimum": 0, "maximum": 100}, "wait": {"type": "boolean"}})
def ai_denoise(ids: Any = None, amount: float = 50.0, wait: bool = False) -> dict:
    pids = resolve_ids(ids)

    def job(progress):
        made = []
        for pid in pids:
            img, info = previews.source(pid, None, full=True)
            out = enhance.denoise(img, float(amount), progress)
            target = _out_path(pid, "Enhanced-NR")
            dng.write_linear_dng(target, out, {**info, "source": target.name}, when=cat().scalar("SELECT capture_time FROM photos WHERE id=?", (pid,)))
            dev = _settings_for(pid, ("detail",))
            dev.setdefault("detail", {})["sharpenAmount"] = 20
            made.append(_derived(pid, target, "Denoise", dev, progress))
        return {"ids": made}
    return _maybe_wait(tasks.start("denoise", "Denoise", job), wait)


@command("ai.superResolution", "Super Resolution", {"ids": {"type": "array"}, "wait": {"type": "boolean"}})
def ai_superres(ids: Any = None, wait: bool = False) -> dict:
    pids = resolve_ids(ids)
    _need("upscale")

    def job(progress):
        made = []
        for pid in pids:
            img, info = previews.source(pid, None, full=True)
            if img.shape[0] * img.shape[1] > 30e6:
                raise CommandError("Super Resolution works on photos up to 30 megapixels")
            out = enhance.superres(img, progress)
            target = _out_path(pid, "Enhanced-SR")
            dng.write_linear_dng(target, out, {**info, "source": target.name}, when=cat().scalar("SELECT capture_time FROM photos WHERE id=?", (pid,)))
            made.append(_derived(pid, target, "Super Resolution", _settings_for(pid, ("crop", "masks", "spots", "redEye")), progress))
        return {"ids": made}
    return _maybe_wait(tasks.start("superres", "Super Resolution", job), wait)


@command("ai.rawDetails", "Raw Details", {"ids": {"type": "array"}, "wait": {"type": "boolean"}})
def ai_raw_details(ids: Any = None, wait: bool = False) -> dict:
    pids = [p for p in resolve_ids(ids) if (cat().scalar("SELECT kind FROM photos WHERE id=?", (p,)) or "") == "raw"]
    if not pids:
        raise CommandError("Raw Details works on raw photos")

    def job(progress):
        made = []
        for pid in pids:
            path = cat().photo_path(pid)
            if path is None:
                continue
            out, info = enhance.raw_details(path, progress)
            target = _out_path(pid, "Enhanced-RD")
            dng.write_linear_dng(target, out, {**info, "source": target.name}, when=cat().scalar("SELECT capture_time FROM photos WHERE id=?", (pid,)))
            made.append(_derived(pid, target, "Raw Details", _settings_for(pid, ()), progress))
        return {"ids": made}
    return _maybe_wait(tasks.start("rawdetails", "Raw Details", job), wait)


@command("ai.enhancePreview", "Enhance Preview", {"id": {"type": "integer"}, "kind": {"type": "string", "enum": ["denoise", "rawDetails"]}, "amount": {"type": "number"},
                                                  "x": {"type": "number"}, "y": {"type": "number"}, "size": {"type": "integer"}}, mutates=False)
def ai_enhance_preview(id: int | None = None, kind: str = "denoise", amount: float = 50.0, x: float = 0.5, y: float = 0.5, size: int = 360) -> dict:
    import base64
    from app.develop.output import to_u8
    pid = int(id) if id is not None else resolve_ids("active")[0]
    size = max(128, min(720, int(size)))
    if kind == "rawDetails":
        path = cat().photo_path(pid)
        if path is None or (cat().scalar("SELECT kind FROM photos WHERE id=?", (pid,)) or "") != "raw":
            raise CommandError("Raw Details works on raw photos")
        from app.services.decode import _raw_linear
        img, _ = _raw_linear(path, None, True, "AHD")
    else:
        img, _ = previews.source(pid, None, full=True)
    h, w = img.shape[:2]
    cx, cy = int(min(max(x, 0.0), 1.0) * w), int(min(max(y, 0.0), 1.0) * h)
    x0, y0 = max(0, min(w - size, cx - size // 2)), max(0, min(h - size, cy - size // 2))
    crop = np.ascontiguousarray(img[y0:y0 + size, x0:x0 + size])
    if kind == "rawDetails":
        after_img, _ = enhance.raw_details(path)
        after_crop = after_img[y0:y0 + size, x0:x0 + size]
    else:
        after_crop = enhance.denoise(crop, float(amount))
    gain = 0.45 / max(1e-6, float(np.percentile(crop, 50)) + 1e-4)

    def jpeg(a: np.ndarray) -> str:
        e = np.clip(a * min(gain, 64.0), 0.0, 1.0)
        e = np.where(e <= 0.0031308, e * 12.92, 1.055 * np.power(np.clip(e, 0.0031308, None), 1 / 2.4) - 0.055)
        ok, buf = cv2.imencode(".jpg", cv2.cvtColor(to_u8(e.astype(np.float32)), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
        return base64.b64encode(buf.tobytes()).decode("ascii") if ok else ""
    return {"before": jpeg(crop), "after": jpeg(after_crop), "x": x0 / w, "y": y0 / h, "size": size}


def _maybe_wait(tid: int, wait: bool) -> dict:
    if not wait:
        return {"task": tid}
    t = tasks.wait(tid, 3600)
    if t and t["state"] == "failed":
        raise CommandError(t["error"] or "Failed")
    return {"task": tid, **(t.get("result") or {} if t else {})}


@command("ai.mergePreview", "Merge Preview", {"ids": {"type": "array"}, "kind": {"type": "string", "enum": ["hdr", "pano", "hdrpano", "focus", "astro"]}, "projection": {"type": "string"},
                                             "reject": {"type": "string"}, "fixedGround": {"type": "boolean"},
                                             "boundaryWarp": {"type": "number"}, "fillEdges": {"type": "boolean"}, "autoCrop": {"type": "boolean"},
                                             "deghost": {"type": "string"}, "align": {"type": "boolean"}, "showGhosts": {"type": "boolean"}, "createStack": {"type": "boolean"}}, mutates=False)
def ai_merge_preview(ids: Any = None, kind: str = "pano", projection: str = "spherical", boundaryWarp: float = 0.0, fillEdges: bool = False, autoCrop: bool = True,
                     deghost: str = "off", align: bool = True, showGhosts: bool = False, createStack: bool = False, reject: str = "sigma", fixedGround: bool = True) -> dict:
    import base64
    from app.develop.output import to_u8
    pids = resolve_ids(ids)
    if len(pids) < 2:
        raise CommandError("Select two or more photos")
    imgs = []
    for pid in pids:
        img, _ = previews.source(pid)
        s = min(1.0, 900.0 / max(img.shape[:2]))
        imgs.append(cv2.resize(img, (max(1, round(img.shape[1] * s)), max(1, round(img.shape[0] * s))), interpolation=cv2.INTER_AREA) if s < 1 else img.copy())
    ghosts: list = []
    try:
        if kind == "hdrpano":
            groups = brackets(pids)
            merged = [merge.hdr([imgs[pids.index(p)] for p in g], _factors(g), deghost, None, True) for g in groups]
            out = merge.pano(merged, projection, None, 4e6, boundaryWarp, fillEdges, autoCrop)
            kind = "hdr"
        elif kind == "hdr":
            factors = []
            for pid in pids:
                r = cat().photo(pid)
                factors.append(merge.exposure_factor({"shutter": r["shutter"], "aperture": r["aperture"], "iso": r["iso"]}) if r else None)
            if len({im.shape for im in imgs}) > 1:
                raise CommandError("HDR merge needs photos of the same size and orientation")
            out = merge.hdr(imgs, factors, deghost, None, align, ghosts)
        elif kind == "focus":
            if len({im.shape for im in imgs}) > 1:
                raise CommandError("Focus stacking needs photos of the same size and orientation")
            order = sorted(range(len(pids)), key=lambda k: (str(cat().scalar("SELECT capture_time FROM photos WHERE id=?", (pids[k],)) or ""), pids[k]))
            out = merge.focus_stack([imgs[k] for k in order], None, align, autoCrop)
        elif kind == "astro":
            from app.ai import astro
            if len({im.shape for im in imgs}) > 1:
                raise CommandError("Astro stacking needs frames of the same size and orientation")
            order = sorted(range(len(pids)), key=lambda k: (str(cat().scalar("SELECT capture_time FROM photos WHERE id=?", (pids[k],)) or ""), pids[k]))
            sky = nets.sky(view_rgb8(pids[order[len(order) // 2]])) if fixedGround and models.ready("sky") else None
            out, _ = astro.stack(lambda i: imgs[order[i]], len(order), None, align, reject if reject in ("sigma", "median", "mean") else "sigma", sky, autoCrop)
        else:
            out = merge.pano(imgs, projection, None, 4e6, boundaryWarp, fillEdges, autoCrop)
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    gain = 0.5 / max(1e-6, float(np.percentile(out, 50))) if kind == "hdr" else 0.12 / max(1e-6, float(np.percentile(out, 50))) if kind == "astro" else 1.0 / max(1e-6, float(np.percentile(out, 99)))
    disp = np.clip(out * gain, 0.0, None)
    disp = disp / (1.0 + disp) * (1.6 if kind == "hdr" else 1.0) if kind == "hdr" else np.clip(disp, 0.0, 1.0)
    disp = np.where(disp <= 0.0031308, disp * 12.92, 1.055 * np.power(np.clip(disp, 0.0031308, None), 1 / 2.4) - 0.055)
    if showGhosts and ghosts:
        g = np.any(np.stack(ghosts), axis=0)[..., None]
        disp = np.where(g, disp * 0.45 + np.array([0.9, 0.15, 0.25], np.float32) * 0.55, disp)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(to_u8(np.clip(disp, 0.0, 1.0).astype(np.float32)), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise CommandError("Could not encode the preview")
    return {"jpeg": base64.b64encode(buf.tobytes()).decode("ascii"), "w": int(out.shape[1]), "h": int(out.shape[0]),
            "ghostPixels": int(np.any(np.stack(ghosts), axis=0).sum()) if ghosts else 0}


def _ev(pid: int) -> float:
    r = cat().photo(pid)
    f = merge.exposure_factor({"shutter": r["shutter"], "aperture": r["aperture"], "iso": r["iso"]}) if r else None
    return round(float(np.log2(f)) * 3) / 3 if f else 0.0


def brackets(pids: list[int]) -> list[list[int]]:
    order = sorted(pids, key=lambda p: (str(cat().scalar("SELECT capture_time FROM photos WHERE id=?", (p,)) or ""), p))
    evs = [_ev(p) for p in order]
    k = len(set(evs))
    if k < 2 or len(order) % k or len(order) // k < 2:
        raise CommandError("HDR Panorama needs two or more bracketed sets of the same size, for example 3 positions of 3 exposures")
    groups = [order[i:i + k] for i in range(0, len(order), k)]
    for g in groups:
        if len({evs[order.index(p)] for p in g}) != k:
            raise CommandError("Each bracketed set must hold one photo of every exposure; select whole sets in capture order")
    return groups


def _factors(pids: list[int]) -> list[float | None]:
    out = []
    for pid in pids:
        r = cat().photo(pid)
        out.append(merge.exposure_factor({"shutter": r["shutter"], "aperture": r["aperture"], "iso": r["iso"]}) if r else None)
    return out


@command("ai.hdrPanoMerge", "HDR Panorama Merge", {"ids": {"type": "array"}, "projection": {"type": "string", "enum": ["spherical", "cylindrical", "plane"]},
                                                  "boundaryWarp": {"type": "number"}, "fillEdges": {"type": "boolean"}, "autoCrop": {"type": "boolean"},
                                                  "deghost": {"type": "string", "enum": ["off", "low", "medium", "high"]}, "createStack": {"type": "boolean"}, "wait": {"type": "boolean"}})
def ai_hdr_pano(ids: Any = None, projection: str = "spherical", boundaryWarp: float = 0.0, fillEdges: bool = False, autoCrop: bool = True, deghost: str = "off",
                createStack: bool = False, wait: bool = False) -> dict:
    pids = resolve_ids(ids)
    groups = brackets(pids)

    def job(progress):
        merged, infos = [], []
        for gi, g in enumerate(groups):
            imgs = []
            for pid in g:
                img, info = previews.source(pid, None, full=True)
                imgs.append(img.copy())
            infos.append(info)
            merged.append(merge.hdr(imgs, _factors(g), deghost, None, True))
            progress(gi + 1, len(groups) + 2, f"HDR {gi + 1} of {len(groups)}")
        out = merge.pano(merged, projection, None, 80e6, boundaryWarp, fillEdges, autoCrop)
        ref = groups[0][len(groups[0]) // 2]
        target = _out_path(ref, "HDR-Pano")
        dng.write_linear_dng(target, out, {**infos[0], "raw": True, "source": target.name}, when=cat().scalar("SELECT capture_time FROM photos WHERE id=?", (ref,)))
        new = _derived(ref, target, "HDR Panorama Merge", _settings_for(ref, ("light", "crop", "masks", "spots", "redEye", "geometry", "optics", "lensBlur")), progress,
                       stack=pids if createStack else [])
        from app.engine.cmd_develop import auto
        auto([new])
        return {"ids": [new], "sets": len(groups)}
    return _maybe_wait(tasks.start("hdrpano", "HDR Panorama Merge", job), wait)


@command("ai.hdrMerge", "HDR Merge", {"ids": {"type": "array"}, "deghost": {"type": "string", "enum": ["off", "low", "medium", "high"]}, "autoTone": {"type": "boolean"},
                                      "align": {"type": "boolean"}, "createStack": {"type": "boolean"}, "wait": {"type": "boolean"}})
def ai_hdr(ids: Any = None, deghost: str = "off", autoTone: bool = True, align: bool = True, createStack: bool = False, wait: bool = False) -> dict:
    pids = resolve_ids(ids)
    if len(pids) < 2:
        raise CommandError("Select two or more bracketed photos")

    def job(progress):
        imgs, infos, factors = [], [], []
        for i, pid in enumerate(pids):
            img, info = previews.source(pid, None, full=True)
            imgs.append(img.copy())
            infos.append(info)
            r = cat().photo(pid)
            factors.append(merge.exposure_factor({"shutter": r["shutter"], "aperture": r["aperture"], "iso": r["iso"]}) if r else None)
            progress(i + 1, len(pids) + 2, "Reading brackets")
        out = merge.hdr(imgs, factors, deghost, progress, align)
        ref = pids[int(np.argsort([float(np.median(i)) for i in imgs])[len(imgs) // 2])]
        target = _out_path(ref, "HDR")
        dng.write_linear_dng(target, out, {**infos[pids.index(ref)], "raw": True, "source": target.name}, when=cat().scalar("SELECT capture_time FROM photos WHERE id=?", (ref,)))
        dev = _settings_for(ref, ("light", "crop", "masks", "spots", "redEye", "lensBlur"))
        new = _derived(ref, target, "HDR Merge", dev, progress, stack=pids if createStack else [])
        if autoTone:
            from app.engine.cmd_develop import auto
            auto([new])
        return {"ids": [new]}
    return _maybe_wait(tasks.start("hdr", "HDR Merge", job), wait)


@command("ai.panoMerge", "Panorama Merge", {"ids": {"type": "array"}, "projection": {"type": "string", "enum": ["spherical", "cylindrical", "plane"]},
                                            "boundaryWarp": {"type": "number", "description": "0 to 100: bend the edges out to fill the frame"},
                                            "fillEdges": {"type": "boolean"}, "autoCrop": {"type": "boolean"}, "createStack": {"type": "boolean"}, "wait": {"type": "boolean"}})
def ai_pano(ids: Any = None, projection: str = "spherical", boundaryWarp: float = 0.0, fillEdges: bool = False, autoCrop: bool = True, createStack: bool = False,
            wait: bool = False) -> dict:
    pids = resolve_ids(ids)
    if len(pids) < 2:
        raise CommandError("Select two or more overlapping photos")

    def job(progress):
        imgs, infos = [], []
        for i, pid in enumerate(pids):
            img, info = previews.source(pid, None, full=True)
            imgs.append(img.copy())
            infos.append(info)
            progress(i + 1, len(pids) + 1, "Reading photos")
        out = merge.pano(imgs, projection, progress, 80e6, boundaryWarp, fillEdges, autoCrop)
        target = _out_path(pids[0], "Pano")
        dng.write_linear_dng(target, out, {**infos[0], "source": target.name}, when=cat().scalar("SELECT capture_time FROM photos WHERE id=?", (pids[0],)))
        new = _derived(pids[0], target, "Panorama Merge", _settings_for(pids[0], ("crop", "masks", "spots", "redEye", "geometry", "optics", "lensBlur")), progress,
                       stack=pids if createStack else [])
        return {"ids": [new]}
    return _maybe_wait(tasks.start("pano", "Panorama Merge", job), wait)


@command("ai.focusStack", "Focus Stack", {"ids": {"type": "array"}, "align": {"type": "boolean"}, "autoCrop": {"type": "boolean"}, "createStack": {"type": "boolean"}, "wait": {"type": "boolean"}},
         description="Merges photos focused at different distances into one photo sharp throughout: aligns them to the middle frame (shift, scale and rotation, for focus breathing), keeps the sharpest frame at each point through a pyramid blend, and crops to the area every frame covers. Writes a linear DNG beside the middle frame with its settings.")
def ai_focus_stack(ids: Any = None, align: bool = True, autoCrop: bool = True, createStack: bool = False, wait: bool = False) -> dict:
    pids = resolve_ids(ids)
    if len(pids) < 2:
        raise CommandError("Select two or more photos of the same scene focused at different distances")
    order = sorted(pids, key=lambda p: (str(cat().scalar("SELECT capture_time FROM photos WHERE id=?", (p,)) or ""), p))

    def job(progress):
        imgs, infos = [], []
        for i, pid in enumerate(order):
            img, info = previews.source(pid, None, full=True)
            imgs.append(img.copy())
            infos.append(info)
            progress(i + 1, 3 * len(order) + 1, "Reading photos")
        try:
            out = merge.focus_stack(imgs, lambda a, b, label: progress(len(order) + a, len(order) + b, label), align, autoCrop)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        ref = order[len(order) // 2]
        target = _out_path(ref, "Focus")
        dng.write_linear_dng(target, out, {**infos[len(order) // 2], "source": target.name}, when=cat().scalar("SELECT capture_time FROM photos WHERE id=?", (ref,)))
        new = _derived(ref, target, "Focus Stack", _settings_for(ref, ("crop", "masks", "spots", "redEye", "lensBlur", "layers")), progress, stack=pids if createStack else [])
        return {"ids": [new], "frames": len(order)}
    return _maybe_wait(tasks.start("focus", "Focus Stack", job), wait)


@command("ai.astroStack", "Astro Stack", {"ids": {"type": "array"}, "align": {"type": "boolean"}, "reject": {"type": "string", "enum": ["sigma", "median", "mean"]},
                                          "ground": {"type": "string", "enum": ["fixed", "aligned"]}, "autoCrop": {"type": "boolean"}, "createStack": {"type": "boolean"}, "wait": {"type": "boolean"}},
         description="Stacks night-sky frames shot from a tripod: aligns each frame to the middle one on its stars (the sky's turn plus a smooth correction for wide-lens distortion), removes hot pixels, and averages with outlier rejection so noise drops by about the square root of the frame count and satellites, planes and meteors vanish. ground fixed keeps the landscape sharp by stacking it on its own, aligned to itself if the camera moved (needs the sky model; groundMoved reports each frame's move in pixels); aligned moves everything with the stars. Writes a linear DNG beside the middle frame.")
def ai_astro_stack(ids: Any = None, align: bool = True, reject: str = "sigma", ground: str = "fixed", autoCrop: bool = True, createStack: bool = False, wait: bool = False) -> dict:
    from app.ai import astro
    pids = resolve_ids(ids)
    if len(pids) < 3:
        raise CommandError("Select three or more frames of the same night sky; ten or more works best")
    if reject not in ("sigma", "median", "mean"):
        raise CommandError("reject is sigma, median or mean")
    order = sorted(pids, key=lambda p: (str(cat().scalar("SELECT capture_time FROM photos WHERE id=?", (p,)) or ""), p))
    ref = order[len(order) // 2]
    if ground == "fixed" and not models.ready("sky"):
        raise CommandError("Keeping the landscape sharp needs the sky model (Preferences, AI models), or use ground aligned")

    def job(progress):
        infos: dict[int, dict] = {}

        def load(i: int) -> np.ndarray:
            img, info = previews.source(order[i], None, full=True)
            infos[i] = info
            return img
        sky = nets.sky(view_rgb8(ref)) if ground == "fixed" else None
        try:
            out, report = astro.stack(load, len(order), progress, align, reject, sky, autoCrop)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        target = _out_path(ref, "Astro")
        dng.write_linear_dng(target, out, {**infos.get(len(order) // 2, {}), "source": target.name}, when=cat().scalar("SELECT capture_time FROM photos WHERE id=?", (ref,)))
        new = _derived(ref, target, "Astro Stack", _settings_for(ref, ("crop", "masks", "spots", "redEye", "lensBlur", "layers", "detail")), progress, stack=pids if createStack else [])
        return {"ids": [new], **report}
    return _maybe_wait(tasks.start("astro", "Astro Stack", job), wait)


@command("ai.flashBlend", "Flash and Window Blend", {"ids": {"type": "array"}, "flash": {"type": "integer", "description": "the flash frame; found from the Flash fired tag when left out"},
                                                    "flashAmount": {"type": "number", "description": "0 to 100: how much of the room's light comes from the flash frame"},
                                                    "colorAmount": {"type": "number", "description": "0 to 100: how much of the room's colour comes from the flash frame"},
                                                    "windowPull": {"type": "boolean"}, "windowEv": {"type": "number", "description": "stops the window view sits above the room's midtone, -1 to 3"},
                                                    "autoTone": {"type": "boolean"}, "createStack": {"type": "boolean"}, "wait": {"type": "boolean"}},
         description="Real estate and interiors: blends a bracket shot from a tripod into one linear DNG. The ambient frames are merged as HDR; a flash frame, if there is one, gives the room clean colour (luminosity from the ambient light, colour from the flash, the flambient method); windows are found as the areas far brighter than the room and pulled from the darker frames in darken mode, so window frames and mullions stay and flash reflections on the glass go.")
def ai_flash_blend(ids: Any = None, flash: int | None = None, flashAmount: float = 50.0, colorAmount: float = 100.0, windowPull: bool = True, windowEv: float = 1.0,
                   autoTone: bool = True, createStack: bool = False, wait: bool = False) -> dict:
    from app.ai import flash as flash_mod
    pids = resolve_ids(ids)
    fid = int(flash) if flash is not None else None
    if fid is None:
        fired = [p for p in pids if (cat().scalar("SELECT flash FROM photos WHERE id=?", (p,)) or 0)]
        if len(fired) > 1:
            raise CommandError(f"{len(fired)} frames have Flash fired; pass flash with the one to use")
        fid = fired[0] if fired else None
    if fid is not None and fid not in pids:
        pids = pids + [fid]
    amb_ids = [p for p in pids if p != fid]
    if not amb_ids:
        raise CommandError("Select the ambient frames as well as the flash frame")
    if fid is None and not windowPull:
        raise CommandError("Nothing to blend: no flash frame was found and the window pull is off")
    windowEv = min(max(float(windowEv), -1.0), 3.0)

    def job(progress):
        imgs, factors, infos = [], [], {}
        for i, pid in enumerate(amb_ids):
            img, info = previews.source(pid, None, full=True)
            imgs.append(img.copy())
            infos[pid] = info
            r = cat().photo(pid)
            factors.append(merge.exposure_factor({"shutter": r["shutter"], "aperture": r["aperture"], "iso": r["iso"]}) if r else None)
            progress(i + 1, len(pids) + 4, "Reading frames")
        fl = previews.source(fid, None, full=True)[0].copy() if fid is not None else None
        if fl is not None and fl.shape[:2] != imgs[0].shape[:2]:
            raise CommandError("The flash frame is not the same size as the ambient frames")
        out, report = flash_mod.blend(imgs, factors if all(factors) else [None] * len(imgs), fl, flashAmount, colorAmount, windowEv, windowPull,
                                      lambda a, b, label: progress(len(pids) + a, len(pids) + 4, label))
        ref = amb_ids[int(np.argsort([float(np.median(i)) for i in imgs])[len(imgs) // 2])]
        target = _out_path(ref, "Blend")
        dng.write_linear_dng(target, out, {**infos[ref], "raw": True, "source": target.name}, when=cat().scalar("SELECT capture_time FROM photos WHERE id=?", (ref,)))
        new = _derived(ref, target, "Flash and Window Blend", _settings_for(ref, ("light", "crop", "masks", "spots", "redEye", "lensBlur")), progress,
                       stack=pids if createStack else [])
        if autoTone:
            from app.engine.cmd_develop import auto
            auto([new])
        return {**report, "ids": [new], "flash": fid, "ambient": amb_ids}
    return _maybe_wait(tasks.start("blend", "Flash and Window Blend", job), wait)


def _segments(pid: int) -> np.ndarray:
    dev, _ = current(pid)
    plain = {k: v for k, v in dev.items() if k not in ("crop", "geometry", "masks", "vignette", "grain", "lensBlur")}
    rgb8 = view_rgb8(pid, plain, 1200)
    return upright_mod.segments(cv2.cvtColor(rgb8, cv2.COLOR_RGB2GRAY))


@command("develop.autoStraighten", "Auto Straighten", {"id": {"type": "integer"}}, mutates=False)
def auto_straighten(id: int | None = None) -> dict:
    pid = int(id) if id is not None else resolve_ids("active")[0]
    return {"angle": round(-upright_mod.straighten_angle(_segments(pid)), 2)}


@command("develop.upright", "Upright", {"ids": {"type": "array"}, "mode": {"type": "string", "enum": ["off", "auto", "level", "vertical", "full"]}})
def upright_cmd(mode: str = "auto", ids: Any = None) -> dict:
    pids = resolve_ids(ids)
    if mode not in ("off", "auto", "level", "vertical", "full"):
        raise CommandError("mode is off, auto, level, vertical or full")
    with cat().change(f"Upright: {mode.title()}") as ch:
        for pid in pids:
            dev, _ = current(pid)
            new = copy.deepcopy(dev)
            g = new.setdefault("geometry", {})
            if mode == "off":
                g.pop("upright", None)
                g.pop("uprightTransform", None)
            else:
                h = upright_mod.upright(_segments(pid), mode, strength=0.6 if mode == "auto" else 1.0)
                g["upright"] = mode
                g["uprightTransform"] = [round(float(v), 7) for v in h.reshape(-1)]
                g["constrainCrop"] = True
            store(ch, pid, new, f"Upright: {mode.title()}")
    after(pids)
    return {"ids": pids, "mode": mode}


@command("develop.uprightGuides", "Guided Upright", {"id": {"type": "integer"}, "add": {"type": "array"}, "remove": {"type": "integer"}, "clear": {"type": "boolean"}})
def upright_guides(id: int | None = None, add: list[float] | None = None, remove: int | None = None, clear: bool = False, read: bool = False) -> dict:
    import numpy as np
    from app.develop.geometry import Frame
    from app.develop.render import effective
    pid = int(id) if id is not None else resolve_ids("active")[0]
    dev, _ = current(pid)
    img, _ = previews.source(pid)
    sh, sw = img.shape[:2]
    fr = Frame(sw, sh, effective(dev), True)
    half = max(fr.ow, fr.oh) / 2
    geo = dev.get("geometry") or {}
    guides = [list(map(float, x)) for x in geo.get("uprightGuides") or []] if geo.get("upright") == "guided" else []
    new = dev
    if not read:
        if clear:
            guides = []
        if remove is not None and 0 <= int(remove) < len(guides):
            guides.pop(int(remove))
        if add and len(add) == 4:
            pts: list[float] = []
            for i in (0, 2):
                x, y = fr.to_corrected(np.array([float(add[i]) * fr.ow]), np.array([float(add[i + 1]) * fr.oh]))
                pts += [float((x[0] - fr.ow / 2) / half), float((y[0] - fr.oh / 2) / half)]
            guides.append(pts)
        guides = guides[-4:]
        new = copy.deepcopy(dev)
        g = new.setdefault("geometry", {})
        if guides:
            h = upright_mod.guided(np.array(guides, np.float64))
            g.update(upright="guided", uprightGuides=[[round(v, 6) for v in s] for s in guides], uprightTransform=[round(float(v), 7) for v in h.reshape(-1)], constrainCrop=True)
        else:
            for k in ("upright", "uprightGuides", "uprightTransform"):
                g.pop(k, None)
        with cat().change("Guided Upright") as ch:
            store(ch, pid, new, "Guided Upright")
        after([pid])
    fr2 = Frame(sw, sh, effective(new), True)
    shown = []
    for s in guides:
        seg = []
        for i in (0, 2):
            p = fr2.persp @ np.array([s[i], s[i + 1], 1.0])
            seg += [round(float((p[0] / p[2] * half + fr2.ow / 2) / fr2.ow), 6), round(float((p[1] / p[2] * half + fr2.oh / 2) / fr2.oh), 6)]
        shown.append(seg)
    return {"guides": shown, "count": len(guides)}


def _remove_view(pid: int) -> tuple:
    from app.develop.render import plan
    dev, _ = current(pid)
    img, info = previews.source(pid)
    eff = effective({k: v for k, v in dev.items() if k not in ("crop", "spots")})
    sh, sw = img.shape[:2]
    frame, w, h, ppl = plan(sw, sh, eff, None, None, False)
    return frame.sample(img, w, h), frame, w, h, ppl


def _fill_hole(pid: int, sampled: np.ndarray, frame, w: int, h: int, full: np.ndarray, r: float, variants: int, alpha: bool) -> list[str]:
    ys, xs = np.nonzero(full)
    if not len(xs):
        raise CommandError("Nothing to remove there")
    folder = config.masks_dir() / str(pid)
    folder.mkdir(parents=True, exist_ok=True)
    n = frame.out_to_norm(w, h)
    stamp = int(time.time() * 1000)
    out = []
    for vi, (padk, flip, shift) in enumerate([(4.0, False, 2), (6.5, True, 3), (2.8, False, -2)][:max(1, min(3, int(variants)))]):
        pad = max(r * padk, 0.35 * max(xs.max() - xs.min(), ys.max() - ys.min())) if alpha else r * padk
        x0, y0 = int(max(0, xs.min() - pad)), int(max(0, ys.min() - pad))
        x1, y1 = int(min(w, xs.max() + 1 + pad)), int(min(h, ys.max() + 1 + pad))
        crop = sampled[y0:y1, x0:x1]
        peak = max(1e-6, float(np.percentile(crop, 99.5)))
        enc = np.sqrt(np.clip(crop / peak, 0.0, 1.0))
        hole = full[y0:y1, x0:x1]
        src8 = (enc * 255 + 0.5).astype(np.uint8)
        hm = (hole > 0).astype(np.float32)
        if flip:
            filled = nets.lama(np.ascontiguousarray(src8[:, ::-1]), np.ascontiguousarray(hm[:, ::-1]))[:, ::-1].astype(np.float32) / 255.0
        else:
            filled = nets.lama(src8, hm).astype(np.float32) / 255.0
        lin = (filled ** 2) * peak
        detail = enc - cv2.GaussianBlur(enc, (0, 0), 1.0)
        if alpha:
            outside = (hm < 0.5)[..., None]
            grain = np.where(outside, detail, 0.0)
            ys0, xs0 = np.nonzero(hm < 0.5)
            if len(xs0):
                step = max(1, int(r))
                noise = np.roll(grain, (int(step * shift * 3), int(step * shift * 5)), (0, 1)) * 0.5 * (hm > 0.5)[..., None]
            else:
                noise = 0.0
        else:
            noise = np.where((hole > 0)[..., None], np.roll(detail, (int(r * shift), int(r * shift)), (0, 1)) * 0.6, 0.0)
        lin = np.maximum(((np.sqrt(lin / peak) + noise) ** 2) * peak, 0.0)
        if alpha:
            soft = cv2.GaussianBlur(hm, (0, 0), max(1.0, r * 0.15))
            lin = np.concatenate([lin, np.clip(np.maximum(soft, hm * 0.98), 0.0, 1.0)[..., None]], axis=-1)
        key = f"remove-{stamp}-{vi}"
        np.save(folder / f"{key}.npy", lin.astype(np.float16))
        a = n @ np.array([x0, y0, 1.0])
        b = n @ np.array([x1, y1, 1.0])
        (folder / f"{key}.json").write_text(json.dumps({"rect": [float(a[0]), float(a[1]), float(b[0]), float(b[1])]}))
        out.append(f"{pid}/{key}")
    return out


@command("develop.removeFill", "Generative Remove", {"id": {"type": "integer"}, "spot": {"type": "object"}, "variants": {"type": "integer", "minimum": 1, "maximum": 3, "description": "1 to 3 fills to choose from"},
                                                     "detect": {"type": "boolean", "description": "Detect Objects: grow the brushed area to the whole object under it"}})
def remove_fill(spot: dict, id: int | None = None, variants: int = 3, detect: bool = False) -> dict:
    pid = int(id) if id is not None else resolve_ids("active")[0]
    _need("remove")
    sampled, frame, w, h, ppl = _remove_view(pid)
    to_out = frame.norm_to_out(w, h)
    pts = [to_out @ np.array([float(p[0]), float(p[1]), 1.0]) for p in spot.get("points", [])]
    if not pts:
        raise CommandError("The spot has no points")
    r = max(2.0, float(spot.get("size", 0.02)) * ppl)
    full = np.zeros((h, w), np.uint8)
    for (px, py, _), q in zip(pts, pts[1:] + pts[-1:]):
        cv2.line(full, (int(px), int(py)), (int(q[0]), int(q[1])), 255, int(max(1, r * 2)))
        cv2.circle(full, (int(px), int(py)), int(r), 255, -1)
    detect = bool(detect or spot.get("detect"))
    if detect and models.ready("objects"):
        ys, xs = np.nonzero(full)
        grow = r * 1.2
        box = [max(0.0, (xs.min() - grow) / w), max(0.0, (ys.min() - grow) / h), min(1.0, (xs.max() + grow) / w), min(1.0, (ys.max() + grow) / h)]
        from app.services import decode
        lin709 = np.maximum(sampled.reshape(-1, 3) @ decode.REC2020_TO_SRGB.T, 0.0).reshape(sampled.shape)
        rgb8 = (decode.linear_to_srgb(lin709 / max(1e-6, float(np.percentile(lin709, 99.5)))) * 255 + 0.5).astype(np.uint8)
        obj = nets.sam_box(rgb8, box, [[float(p[0]) / w, float(p[1]) / h] for p in pts[:8]])
        within = np.zeros_like(full)
        cv2.rectangle(within, (int(box[0] * w), int(box[1] * h)), (int(box[2] * w), int(box[3] * h)), 255, -1)
        objm = ((obj > 0.5) & (within > 0)).astype(np.uint8) * 255
        grown = cv2.dilate(objm, np.ones((5, 5), np.uint8), iterations=max(1, int(r * 0.08)))
        if objm.sum() >= full.sum() * 0.3:
            full = grown
        elif objm.any():
            full = np.maximum(full, grown)
    out = _fill_hole(pid, sampled, frame, w, h, full, r, variants, alpha=detect)
    return {"patch": out[0], "variants": out, "detected": detect}


@command("develop.removePeople", "Remove People", {"id": {"type": "integer"}, "people": {"type": "array", "description": "person indexes from develop.aiPeople; omit for everyone"},
                                                   "variants": {"type": "integer"}})
def remove_people(id: int | None = None, people: list[int] | None = None, variants: int = 1) -> dict:
    pid = int(id) if id is not None else resolve_ids("active")[0]
    _need("remove")
    sampled, frame, w, h, ppl = _remove_view(pid)
    alpha, _faces, found = _people(view_rgb8(pid))
    up = lambda a: cv2.resize(a, (w, h), interpolation=cv2.INTER_LINEAR) if a.shape[:2] != (h, w) else a
    alpha = up(alpha)
    found = [{**p, "alpha": up(p["alpha"])} for p in found]
    targets = [found[i]["alpha"] for i in (people if people is not None else range(len(found))) if 0 <= int(i) < len(found)] if found else ([alpha] if people is None else [])
    n = frame.out_to_norm(w, h)
    spots = []
    for a in targets:
        full = ((a > 0.25).astype(np.uint8) * 255)
        if not full.any():
            continue
        full = cv2.dilate(full, np.ones((5, 5), np.uint8), iterations=max(2, int(max(w, h) / 300)))
        ys, xs = np.nonzero(full)
        r = max(4.0, 0.02 * max(w, h))
        keys = _fill_hole(pid, sampled, frame, w, h, full, r, variants, alpha=True)
        c = n @ np.array([float(xs.mean()), float(ys.mean()), 1.0])
        spots.append({"points": [[round(float(c[0]), 5), round(float(c[1]), 5)]], "size": 0.02, "source": None, "feather": 0, "opacity": 100, "mode": "remove",
                      "patch": keys[0], "variants": keys, "detect": True, "label": "Person"})
    if not spots:
        raise CommandError("No people found to remove")
    return {"spots": spots}


@command("develop.findDust", "Find Dust Spots", {"id": {"type": "integer"}, "sensitivity": {"type": "number", "description": "0 to 100"}}, mutates=False)
def find_dust(id: int | None = None, sensitivity: float = 50.0) -> dict:
    pid = int(id) if id is not None else resolve_ids("active")[0]
    sampled, frame, w, h, ppl = _remove_view(pid)
    y = np.sqrt(np.clip(sampled @ np.array([0.2627, 0.6780, 0.0593], np.float32) / max(1e-6, float(np.percentile(sampled, 99.5))), 0.0, 1.0)).astype(np.float32)
    s = max(w, h) / 2000.0
    small, large = cv2.GaussianBlur(y, (0, 0), 1.2 * s), cv2.GaussianBlur(y, (0, 0), 6.0 * s)
    dip = large - small
    ring = cv2.GaussianBlur(np.abs(y - cv2.GaussianBlur(y, (0, 0), 3.0 * s)), (0, 0), 14.0 * s)
    sens = max(0.0, min(100.0, float(sensitivity))) / 100.0
    cand = ((dip > np.maximum(0.012 * (1.6 - sens), (12.0 - 6.0 * sens) * ring)) & (large > 0.2)).astype(np.uint8)
    num, lab, stats, cent = cv2.connectedComponentsWithStats(cand, 8)
    from app.develop.retouch import auto_source
    n = frame.out_to_norm(w, h)
    found = []
    for i in range(1, num):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < 2 or area > (40 * s) ** 2:
            continue
        cx, cy = cent[i]
        found.append((float(dip[int(cy), int(cx)]), float(cx), float(cy), max(2.0, float(np.sqrt(area / np.pi)) * 1.8 + 2 * s)))
    out = []
    for strength, cx, cy, rad in sorted(found, reverse=True)[:200]:
        dx, dy = auto_source(sampled, (cx, cy), rad)
        c, src = n @ np.array([cx, cy, 1.0]), n @ np.array([cx + dx, cy + dy, 1.0])
        out.append({"points": [[round(float(c[0]), 5), round(float(c[1]), 5)]], "size": round(rad / ppl, 5), "source": [round(float(src[0] - c[0]), 5), round(float(src[1] - c[1]), 5)],
                    "feather": 50, "opacity": 100, "mode": "heal", "strength": round(strength, 4)})
    return {"spots": out}


@command("ai.findFaces", "Find Faces", {"ids": {"type": "array"}, "all": {"type": "boolean"}, "wait": {"type": "boolean"}})
def find_faces(ids: Any = None, all: bool = False, wait: bool = False) -> dict:
    _need("faces")
    pids = [int(r["id"]) for r in cat().rows("SELECT id FROM photos WHERE kind != 'video' ORDER BY id")] if all else resolve_ids(ids)

    def job(progress):
        found = 0
        for i, pid in enumerate(pids):
            if progress.cancelled:
                break
            try:
                rgb8 = view_rgb8(pid, None, 1280)
                fs = nets.faces(rgb8)
            except Exception:
                continue
            with cat().change("Find Faces", undoable=False) as ch:
                for r in cat().rows("SELECT id FROM faces WHERE photo_id=? AND confirmed=0", (pid,)):
                    ch.delete("faces", id=int(r["id"]))
                for f in fs:
                    x0, y0, x1, y1 = f["box"]
                    fid = ch.insert("faces", photo_id=pid, x=x0, y=y0, w=x1 - x0, h=y1 - y0, score=f["score"], embedding=np.asarray(f["embedding"], np.float32).tobytes(), person_id=None, confirmed=0)
                    _save_face(int(fid), rgb8, f["box"])
                    found += 1
            progress(i + 1, len(pids), f"Finding faces {i + 1} of {len(pids)}")
        _assign_known()
        return {"photos": len(pids), "faces": found}
    return _maybe_wait(tasks.start("faces", "Finding faces", job), wait)


def _save_face(fid: int, rgb8: np.ndarray, box: list[float], size: int = 160) -> None:
    h, w = rgb8.shape[:2]
    cx, cy = (box[0] + box[2]) * w / 2, (box[1] + box[3]) * h / 2
    half = max((box[2] - box[0]) * w, (box[3] - box[1]) * h) * 0.8
    x0, y0 = int(max(0, cx - half)), int(max(0, cy - half))
    x1, y1 = int(min(w, cx + half)), int(min(h, cy + half))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return
    crop = cv2.resize(rgb8[y0:y1, x0:x1], (size, size), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(config.faces_dir() / f"{fid}.jpg"), cv2.cvtColor(crop, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])


def _face_vectors(where: str = "", args: tuple = ()) -> list[tuple[int, int | None, np.ndarray, int]]:
    out = []
    for r in cat().rows(f"SELECT id, person_id, embedding, photo_id FROM faces {where}", args):
        if r["embedding"]:
            out.append((int(r["id"]), r["person_id"], np.frombuffer(r["embedding"], np.float32), int(r["photo_id"])))
    return out


def _assign_known(threshold: float = 0.45) -> None:
    known = _face_vectors("WHERE person_id IS NOT NULL AND confirmed=1")
    if not known:
        return
    centroids: dict[int, np.ndarray] = {}
    for _, p, v, _ in known:
        centroids.setdefault(int(p), []).append(v)
    cents = {p: np.mean(vs, axis=0) for p, vs in centroids.items()}
    with cat().change("Suggest People", undoable=False) as ch:
        for fid, _, v, _ in _face_vectors("WHERE person_id IS NULL"):
            best, score = None, threshold
            for p, c in cents.items():
                s = float(v @ c / max(1e-9, np.linalg.norm(c)))
                if s > score:
                    best, score = p, s
            if best is not None:
                ch.update("faces", fid, person_id=best, confirmed=0)


def _clusters(threshold: float = 0.5) -> list[list[int]]:
    faces = _face_vectors("WHERE person_id IS NULL")
    clusters: list[tuple[np.ndarray, list[int]]] = []
    for fid, _, v, _ in faces:
        for i, (c, members) in enumerate(clusters):
            if float(v @ c / max(1e-9, np.linalg.norm(c))) > threshold:
                members.append(fid)
                clusters[i] = (c + (v - c) / len(members), members)
                break
        else:
            clusters.append((v.copy(), [fid]))
    return sorted([m for _, m in clusters], key=len, reverse=True)


@command("people.list", "People", mutates=False)
def people_list() -> dict:
    named = [{"id": int(r["id"]), "name": r["name"], "count": int(r["n"]), "confirmed": int(r["c"] or 0), "cover": r["cover"]}
             for r in cat().rows("SELECT p.id, p.name, COUNT(f.id) AS n, SUM(f.confirmed) AS c, MIN(f.id) AS cover FROM people p LEFT JOIN faces f ON f.person_id=p.id GROUP BY p.id ORDER BY p.name COLLATE NOCASE")]
    owner = {int(r["id"]): int(r["photo_id"]) for r in cat().rows("SELECT id, photo_id FROM faces WHERE person_id IS NULL")}
    unnamed = [{"faces": m, "count": len(m), "cover": m[0], "photos": sorted({owner[f] for f in m if f in owner})} for m in _clusters()]
    return {"named": named, "unnamed": unnamed, "faces": int(cat().scalar("SELECT COUNT(*) FROM faces") or 0)}


@command("people.name", "Name People", {"faces": {"type": "array"}, "name": {"type": "string"}})
def people_name(faces: list[int], name: str) -> dict:
    name = name.strip()
    if not name:
        raise CommandError("A name is needed")
    c = cat()
    with c.change(f"Name {name}") as ch:
        pid = c.scalar("SELECT id FROM people WHERE name=? COLLATE NOCASE", (name,))
        if pid is None:
            kid = c.keyword_id(ch, f"People|{name}")
            ch.update("keywords", kid, person=1)
            pid = ch.insert("people", name=name, keyword_id=kid)
        kid = c.scalar("SELECT keyword_id FROM people WHERE id=?", (pid,))
        photos = set()
        for fid in faces:
            ch.update("faces", int(fid), person_id=int(pid), confirmed=1)
            ph = c.scalar("SELECT photo_id FROM faces WHERE id=?", (int(fid),))
            if ph is not None:
                photos.add(int(ph))
        for ph in photos:
            if kid and not c.scalar("SELECT 1 FROM photo_keywords WHERE photo_id=? AND keyword_id=?", (ph, kid)):
                ch.insert("photo_keywords", photo_id=ph, keyword_id=kid)
    _assign_known()
    return {"person": int(pid), "photos": sorted(photos)}


@command("people.confirm", "Confirm Suggested Faces", {"person": {"type": "integer"}})
def people_confirm(person: int) -> dict:
    fids = [int(r["id"]) for r in cat().rows("SELECT id FROM faces WHERE person_id=? AND confirmed=0", (int(person),))]
    name = cat().scalar("SELECT name FROM people WHERE id=?", (int(person),))
    if not fids or not name:
        return {"person": person, "confirmed": 0}
    people_name(fids, name)
    return {"person": person, "confirmed": len(fids)}


@command("people.unassign", "Not This Person", {"faces": {"type": "array"}})
def people_unassign(faces: list[int]) -> dict:
    with cat().change("Remove Face Name") as ch:
        for fid in faces:
            ch.update("faces", int(fid), person_id=None, confirmed=0)
    return {"faces": faces}


def _face_maps(pid: int):
    from app.develop.render import plan
    dev, _ = current(pid)
    eff = effective(dev or {})
    img, _ = previews.source(pid)
    sh, sw = img.shape[:2]
    view = {k: v for k, v in eff.items() if k not in VIEW_DROP}
    full, fw, fh, _ = plan(sw, sh, view, 1024, None, False)
    crop, cw, ch_, _ = plan(sw, sh, eff, 1024, None, True)
    to_view = np.diag([1 / cw, 1 / ch_, 1.0]) @ crop.norm_to_out(cw, ch_) @ full.out_to_norm(fw, fh) @ np.diag([float(fw), float(fh), 1.0])

    def apply(m: np.ndarray, x: float, y: float, w: float, h: float) -> list[float]:
        pts = np.array([[x, y, 1.0], [x + w, y, 1.0], [x, y + h, 1.0], [x + w, y + h, 1.0]]) @ m.T
        pts = pts[:, :2] / pts[:, 2:3]
        x0, y0 = pts.min(axis=0)
        x1, y1 = pts.max(axis=0)
        return [round(float(x0), 5), round(float(y0), 5), round(float(x1 - x0), 5), round(float(y1 - y0), 5)]
    return (lambda *b: apply(to_view, *b)), (lambda *b: apply(np.linalg.inv(to_view), *b))


@command("faces.forPhoto", "Face Regions", {"id": {"type": "integer"}}, mutates=False)
def faces_for_photo(id: int | None = None) -> dict:
    pid = int(id) if id is not None else resolve_ids("active")[0]
    rows = cat().rows("SELECT f.id, f.x, f.y, f.w, f.h, f.person_id, f.confirmed, p.name FROM faces f LEFT JOIN people p ON p.id=f.person_id WHERE f.photo_id=? ORDER BY f.x", (pid,))
    if not rows:
        return {"id": pid, "faces": [], "names": [r["name"] for r in cat().rows("SELECT name FROM people ORDER BY name COLLATE NOCASE")]}
    to_view, _ = _face_maps(pid)
    faces = [{"id": int(r["id"]), "box": to_view(float(r["x"]), float(r["y"]), float(r["w"]), float(r["h"])), "person": r["person_id"], "name": r["name"] or "",
              "confirmed": bool(r["confirmed"])} for r in rows]
    return {"id": pid, "faces": faces, "names": [r["name"] for r in cat().rows("SELECT name FROM people ORDER BY name COLLATE NOCASE")]}


@command("faces.add", "Draw Face Region", {"id": {"type": "integer"}, "box": {"type": "array", "description": "[x, y, w, h], 0 to 1 across the cropped photo as shown"}, "name": {"type": "string"}})
def faces_add(box: list[float], id: int | None = None, name: str = "") -> dict:
    pid = int(id) if id is not None else resolve_ids("active")[0]
    if len(box) != 4 or box[2] <= 0.002 or box[3] <= 0.002:
        raise CommandError("box is [x, y, w, h] with a size")
    _, to_full = _face_maps(pid)
    x, y, w, h = to_full(*(float(v) for v in box))
    emb = None
    try:
        rgb8 = view_rgb8(pid, None, 1280)
        if models.ready("faces"):
            H, W = rgb8.shape[:2]
            found = nets.faces(rgb8)
            best = max(found, key=lambda f: _overlap(f["box"], [x, y, x + w, y + h]), default=None)
            if best is not None and _overlap(best["box"], [x, y, x + w, y + h]) > 0.3:
                emb = np.asarray(best["embedding"], np.float32).tobytes()
    except Exception:
        rgb8 = None
    with cat().change("Add Face Region") as ch:
        fid = int(ch.insert("faces", photo_id=pid, x=x, y=y, w=w, h=h, score=1.0, embedding=emb, person_id=None, confirmed=0))
    if rgb8 is not None:
        _save_face(fid, rgb8, [x, y, x + w, y + h])
    if name.strip():
        people_name([fid], name)
    return {"face": fid, "matched": emb is not None}


def _overlap(a: list[float], b: list[float]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


@command("faces.delete", "Delete Face Region", {"faces": {"type": "array"}})
def faces_delete(faces: list[int]) -> dict:
    with cat().change("Delete Face Region") as ch:
        for fid in faces:
            ch.delete("faces", id=int(fid))
    for fid in faces:
        (config.faces_dir() / f"{int(fid)}.jpg").unlink(missing_ok=True)
    return {"deleted": faces}


@command("people.rename", "Rename Person", {"person": {"type": "integer"}, "name": {"type": "string"}})
def people_rename(person: int, name: str) -> dict:
    with cat().change("Rename Person") as ch:
        ch.update("people", int(person), name=name.strip())
        kid = cat().scalar("SELECT keyword_id FROM people WHERE id=?", (int(person),))
        if kid:
            ch.update("keywords", int(kid), name=name.strip())
    return {"person": person}


@command("cull.analyze", "Assisted Culling", {"ids": {"type": "array"}, "wait": {"type": "boolean"}})
def cull_analyze(ids: Any = None, wait: bool = False) -> dict:
    pids = resolve_ids(ids)
    use_faces = models.ready("faces")

    def job(progress):
        items = []
        for i, pid in enumerate(pids):
            if progress.cancelled:
                break
            rgb8 = view_rgb8(pid, None, 1024)
            fs = nets.faces(rgb8) if use_faces else None
            s = cull_mod.scores(rgb8, fs)
            items.append({"id": pid, "time": cat().scalar("SELECT capture_time FROM photos WHERE id=?", (pid,)), **s})
            progress(i + 1, len(pids) + 1, f"Assessing {i + 1} of {len(pids)}")
        groups = cull_mod.groups(items)
        by_id = {it["id"]: it for it in items}
        best = set()
        for g in groups:
            best.add(max(g, key=lambda i: cull_mod.quality(by_id[i])))
        run = int(time.time() * 1000)
        with cat().change("Assisted Culling", undoable=False) as ch:
            for gi, g in enumerate(groups):
                for pid in g:
                    row = cat().row("SELECT meta FROM photos WHERE id=?", (pid,))
                    meta = loads(row["meta"], {}) if row else {}
                    it = by_id[pid]
                    meta["cull"] = {"sharpness": it["sharpness"], "exposure": it["exposure"], "group": gi, "groupSize": len(g), "best": pid in best, "faces": it["faces"],
                                    "faceSharpness": it.get("faceSharpness"), "eyesOpen": it.get("eyesOpen"), "quality": round(cull_mod.quality(it), 1),
                                    "faceList": it.get("faceList") or [], "run": run}
                    ch.update("photos", pid, meta=meta)
        blurry = [i for i in by_id if by_id[i]["sharpness"] < 35]
        dupes = [i for g in groups if len(g) > 1 for i in g if i not in best]
        closed = [i for i in by_id if by_id[i].get("eyesOpen") is not None and by_id[i]["eyesOpen"] < 35]
        return {"photos": len(items), "groups": len([g for g in groups if len(g) > 1]), "best": sorted(best), "blurry": sorted(blurry), "duplicates": sorted(dupes),
                "eyesClosed": sorted(closed), "withFaces": len([i for i in by_id if by_id[i]["faces"]]),
                "scores": {str(i): {"sharpness": by_id[i]["sharpness"], "exposure": by_id[i]["exposure"], "eyesOpen": by_id[i].get("eyesOpen")} for i in by_id}}
    return _maybe_wait(tasks.start("cull", "Assisted Culling", job), wait)


@command("cull.groups", "Culling Groups", {"ids": {"type": "array"}}, mutates=False,
         description="The photos in the given order, gathered into near-duplicate groups from the last Assisted Culling run, with each photo's scores and faces. Photos not yet analyzed stand alone.")
def cull_groups(ids: Any = None) -> dict:
    pids = resolve_ids(ids)
    metas: dict[int, dict] = {}
    for i in range(0, len(pids), 500):
        chunk = pids[i:i + 500]
        for r in cat().rows(f"SELECT id, meta FROM photos WHERE id IN ({','.join('?' * len(chunk))})", tuple(chunk)):
            cl = (loads(r["meta"], {}) or {}).get("cull")
            if cl:
                metas[int(r["id"])] = cl
    out: list[dict] = []
    where: dict[tuple, int] = {}
    for pid in pids:
        cl = metas.get(pid)
        key = (cl.get("run", 0), cl.get("group")) if cl and cl.get("groupSize", 1) > 1 else None
        if key is not None and key in where:
            g = out[where[key]]
            g["ids"].append(pid)
        else:
            if key is not None:
                where[key] = len(out)
            out.append({"ids": [pid], "best": None})
        if cl and cl.get("best"):
            out[where[key] if key is not None else len(out) - 1]["best"] = pid
    scores = {str(pid): {k: cl.get(k) for k in ("sharpness", "exposure", "eyesOpen", "faceSharpness", "faces", "quality", "best", "faceList")} for pid, cl in metas.items()}
    return {"groups": out, "total": len(pids), "analyzed": len(metas), "scores": scores}


@command("cull.apply", "Apply Culling", {"ids": {"type": "array"}, "pickBest": {"type": "boolean"}, "rejectBlurry": {"type": "boolean"}, "rejectDuplicates": {"type": "boolean"},
                                         "rejectEyesClosed": {"type": "boolean"}, "threshold": {"type": "number", "minimum": 0, "maximum": 100, "description": "sharpness below this is blurry, 0 to 100"},
                                         "exposureMin": {"type": "number"}, "eyesMin": {"type": "number"},
                                         "applyAs": {"type": "string", "enum": ["flags", "ratings", "labels", "stacks"]}})
def cull_apply(ids: Any = None, pickBest: bool = True, rejectBlurry: bool = True, rejectDuplicates: bool = False, rejectEyesClosed: bool = False, threshold: float = 35.0,
               exposureMin: float = 0.0, eyesMin: float = 35.0, applyAs: str = "flags") -> dict:
    pids = resolve_ids(ids)
    picks, rejects, keeps = [], [], []
    info: dict[int, dict] = {}
    for pid in pids:
        row = cat().row("SELECT meta FROM photos WHERE id=?", (pid,))
        cl = (loads(row["meta"], {}) if row else {}).get("cull")
        if not cl:
            continue
        info[pid] = cl
        eyes = cl.get("eyesOpen")
        bad = (rejectBlurry and cl["sharpness"] < threshold) or (exposureMin > 0 and cl.get("exposure", 100) < exposureMin) \
            or (rejectEyesClosed and eyes is not None and eyes < eyesMin) or (rejectDuplicates and cl.get("groupSize", 1) > 1 and not cl.get("best"))
        if bad:
            rejects.append(pid)
        elif pickBest and cl.get("best") and cl.get("groupSize", 1) > 1:
            picks.append(pid)
        else:
            keeps.append(pid)
    stacked: list[list[int]] = []
    with cat().change("Apply Culling") as ch:
        if applyAs == "flags":
            for pid in rejects:
                ch.update("photos", pid, flag=-1)
            for pid in picks:
                ch.update("photos", pid, flag=1)
        elif applyAs == "labels":
            for pid, lab in [(p, "red") for p in rejects] + [(p, "green") for p in picks] + [(p, "yellow") for p in keeps]:
                ch.update("photos", pid, label=lab)
        elif applyAs == "ratings":
            for pid in rejects:
                ch.update("photos", pid, rating=1)
            for pid in picks + keeps:
                q = float(info[pid].get("quality") or info[pid]["sharpness"])
                stars = 2 + int(q >= 55) + int(q >= 72)
                ch.update("photos", pid, rating=min(5, stars + (1 if pid in picks else 0)))
    if applyAs == "stacks":
        from app.engine.cmd_library import stack_group
        groups: dict[int, list[int]] = {}
        for pid, cl in info.items():
            if cl.get("groupSize", 1) > 1:
                groups.setdefault(int(cl["group"]), []).append(pid)
        for members in groups.values():
            if len(members) > 1:
                members.sort(key=lambda p: (not info[p].get("best"), -float(info[p].get("quality") or 0)))
                stack_group(members)
                stacked.append(members)
    return {"picks": picks, "rejects": rejects, "kept": keeps, "stacks": stacked, "applyAs": applyAs}
