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
        a = nets.sam_box(rgb8, box or [0.25, 0.25, 0.75, 0.75], points)
    else:
        a = nets.depth(rgb8)
    key = f"{kind}-{int(time.time() * 1000)}"
    save_bitmap(pid, key, a)
    return {"shape": {"kind": "depthRange" if kind == "depth" else kind, "bitmap": key}, "coverage": round(float(a.mean()), 4)}


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


def _derived(src: int, path: Path, label: str, dev: dict, progress) -> int:
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
    try:
        stack_group([new, src])
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


def _maybe_wait(tid: int, wait: bool) -> dict:
    if not wait:
        return {"task": tid}
    t = tasks.wait(tid, 3600)
    if t and t["state"] == "failed":
        raise CommandError(t["error"] or "Failed")
    return {"task": tid, **(t.get("result") or {} if t else {})}


@command("ai.mergePreview", "Merge Preview", {"ids": {"type": "array"}, "kind": {"type": "string", "enum": ["hdr", "pano"]}, "projection": {"type": "string"},
                                             "boundaryWarp": {"type": "number"}, "fillEdges": {"type": "boolean"}, "autoCrop": {"type": "boolean"},
                                             "deghost": {"type": "string"}, "align": {"type": "boolean"}, "showGhosts": {"type": "boolean"}}, mutates=False)
def ai_merge_preview(ids: Any = None, kind: str = "pano", projection: str = "spherical", boundaryWarp: float = 0.0, fillEdges: bool = False, autoCrop: bool = True,
                     deghost: str = "off", align: bool = True, showGhosts: bool = False) -> dict:
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
        if kind == "hdr":
            factors = []
            for pid in pids:
                r = cat().photo(pid)
                factors.append(merge.exposure_factor({"shutter": r["shutter"], "aperture": r["aperture"], "iso": r["iso"]}) if r else None)
            if len({im.shape for im in imgs}) > 1:
                raise CommandError("HDR merge needs photos of the same size and orientation")
            out = merge.hdr(imgs, factors, deghost, None, align, ghosts)
        else:
            out = merge.pano(imgs, projection, None, 4e6, boundaryWarp, fillEdges, autoCrop)
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    gain = 0.5 / max(1e-6, float(np.percentile(out, 50))) if kind == "hdr" else 1.0 / max(1e-6, float(np.percentile(out, 99)))
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


@command("ai.hdrMerge", "HDR Merge", {"ids": {"type": "array"}, "deghost": {"type": "string", "enum": ["off", "low", "medium", "high"]}, "autoTone": {"type": "boolean"},
                                      "align": {"type": "boolean"}, "wait": {"type": "boolean"}})
def ai_hdr(ids: Any = None, deghost: str = "off", autoTone: bool = True, align: bool = True, wait: bool = False) -> dict:
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
        dng.write_linear_dng(target, out, {**infos[pids.index(ref)], "source": target.name}, when=cat().scalar("SELECT capture_time FROM photos WHERE id=?", (ref,)))
        dev = _settings_for(ref, ("light", "crop", "masks", "spots", "redEye", "lensBlur"))
        new = _derived(ref, target, "HDR Merge", dev, progress)
        if autoTone:
            from app.engine.cmd_develop import auto
            auto([new])
        return {"ids": [new]}
    return _maybe_wait(tasks.start("hdr", "HDR Merge", job), wait)


@command("ai.panoMerge", "Panorama Merge", {"ids": {"type": "array"}, "projection": {"type": "string", "enum": ["spherical", "cylindrical", "plane"]},
                                            "boundaryWarp": {"type": "number", "description": "0 to 100: bend the edges out to fill the frame"},
                                            "fillEdges": {"type": "boolean"}, "autoCrop": {"type": "boolean"}, "wait": {"type": "boolean"}})
def ai_pano(ids: Any = None, projection: str = "spherical", boundaryWarp: float = 0.0, fillEdges: bool = False, autoCrop: bool = True, wait: bool = False) -> dict:
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
        new = _derived(pids[0], target, "Panorama Merge", _settings_for(pids[0], ("crop", "masks", "spots", "redEye", "geometry", "optics", "lensBlur")), progress)
        return {"ids": [new]}
    return _maybe_wait(tasks.start("pano", "Panorama Merge", job), wait)


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


@command("develop.removeFill", "Generative Remove", {"id": {"type": "integer"}, "spot": {"type": "object"}})
def remove_fill(spot: dict, id: int | None = None) -> dict:
    from app.develop.render import plan
    pid = int(id) if id is not None else resolve_ids("active")[0]
    _need("remove")
    dev, _ = current(pid)
    img, info = previews.source(pid)
    eff = effective({k: v for k, v in dev.items() if k not in ("crop", "spots")})
    sh, sw = img.shape[:2]
    frame, w, h, ppl = plan(sw, sh, eff, None, None, False)
    sampled = frame.sample(img, w, h)
    to_out = frame.norm_to_out(w, h)
    pts = [to_out @ np.array([float(p[0]), float(p[1]), 1.0]) for p in spot.get("points", [])]
    if not pts:
        raise CommandError("The spot has no points")
    r = max(2.0, float(spot.get("size", 0.02)) * ppl)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    pad = r * 4
    x0, y0 = int(max(0, min(xs) - pad)), int(max(0, min(ys) - pad))
    x1, y1 = int(min(w, max(xs) + pad)), int(min(h, max(ys) + pad))
    crop = sampled[y0:y1, x0:x1]
    peak = max(1e-6, float(np.percentile(crop, 99.5)))
    enc = np.sqrt(np.clip(crop / peak, 0.0, 1.0))
    hole = np.zeros(crop.shape[:2], np.uint8)
    for (px, py, _), q in zip(pts, pts[1:] + pts[-1:]):
        cv2.line(hole, (int(px - x0), int(py - y0)), (int(q[0] - x0), int(q[1] - y0)), 255, int(max(1, r * 2)))
        cv2.circle(hole, (int(px - x0), int(py - y0)), int(r), 255, -1)
    filled = nets.lama((enc * 255 + 0.5).astype(np.uint8), hole.astype(np.float32) / 255.0).astype(np.float32) / 255.0
    lin = (filled ** 2) * peak
    detail = enc - cv2.GaussianBlur(enc, (0, 0), 1.0)
    noise = np.where((hole > 0)[..., None], np.roll(detail, (int(r * 2), int(r * 2)), (0, 1)) * 0.6, 0.0)
    lin = np.maximum(((np.sqrt(lin / peak) + noise) ** 2) * peak, 0.0)
    key = f"remove-{int(time.time() * 1000)}"
    folder = config.masks_dir() / str(pid)
    folder.mkdir(parents=True, exist_ok=True)
    np.save(folder / f"{key}.npy", lin.astype(np.float16))
    n = frame.out_to_norm(w, h)
    a = n @ np.array([x0, y0, 1.0])
    b = n @ np.array([x1, y1, 1.0])
    (folder / f"{key}.json").write_text(json.dumps({"rect": [float(a[0]), float(a[1]), float(b[0]), float(b[1])]}))
    return {"patch": f"{pid}/{key}"}


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
            best.add(max(g, key=lambda i: by_id[i]["sharpness"] * 0.75 + by_id[i]["exposure"] * 0.25))
        with cat().change("Assisted Culling", undoable=False) as ch:
            for gi, g in enumerate(groups):
                for pid in g:
                    row = cat().row("SELECT meta FROM photos WHERE id=?", (pid,))
                    meta = loads(row["meta"], {}) if row else {}
                    it = by_id[pid]
                    meta["cull"] = {"sharpness": it["sharpness"], "exposure": it["exposure"], "group": gi, "groupSize": len(g), "best": pid in best, "faces": it["faces"]}
                    ch.update("photos", pid, meta=meta)
        blurry = [i for i in by_id if by_id[i]["sharpness"] < 35]
        dupes = [i for g in groups if len(g) > 1 for i in g if i not in best]
        return {"photos": len(items), "groups": len([g for g in groups if len(g) > 1]), "best": sorted(best), "blurry": sorted(blurry), "duplicates": sorted(dupes)}
    return _maybe_wait(tasks.start("cull", "Assisted Culling", job), wait)


@command("cull.apply", "Apply Culling", {"ids": {"type": "array"}, "pickBest": {"type": "boolean"}, "rejectBlurry": {"type": "boolean"}, "rejectDuplicates": {"type": "boolean"},
                                         "threshold": {"type": "number"}})
def cull_apply(ids: Any = None, pickBest: bool = True, rejectBlurry: bool = True, rejectDuplicates: bool = False, threshold: float = 35.0) -> dict:
    pids = resolve_ids(ids)
    picks, rejects = [], []
    with cat().change("Apply Culling") as ch:
        for pid in pids:
            row = cat().row("SELECT meta, flag FROM photos WHERE id=?", (pid,))
            cl = (loads(row["meta"], {}) if row else {}).get("cull")
            if not cl:
                continue
            if rejectBlurry and cl["sharpness"] < threshold or rejectDuplicates and cl.get("groupSize", 1) > 1 and not cl.get("best"):
                ch.update("photos", pid, flag=-1)
                rejects.append(pid)
            elif pickBest and cl.get("best") and cl.get("groupSize", 1) > 1:
                ch.update("photos", pid, flag=1)
                picks.append(pid)
    return {"picks": picks, "rejects": rejects}
