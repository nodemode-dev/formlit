import copy
import json
from typing import Any

from app.develop import settings as S
from app.engine import catalog as catalog_mod
from app.engine import records
from app.engine.catalog import Change, now_iso
from app.engine.commands import SESSION, CommandError, command, resolve_ids
from app.services import previews

HISTORY_KEEP = 400


def cat():
    return catalog_mod.get()


def current(pid: int) -> tuple[dict, str]:
    r = cat().row("SELECT develop, kind FROM photos WHERE id=?", (pid,))
    if r is None:
        raise CommandError(f"No photo with id {pid}", 404)
    return records.loads(r["develop"], {}), r["kind"]


def store(ch: Change, pid: int, dev: dict, label: str, history: bool = True) -> None:
    c = ch.cat
    r = c.db.execute("SELECT develop, develop_rev, kind FROM photos WHERE id=?", (pid,)).fetchone()
    if r is None:
        return
    new = S.prune(dev)
    if json.dumps(new, sort_keys=True) == json.dumps(records.loads(r["develop"], {}), sort_keys=True):
        return
    ch.update("photos", pid, develop=new, develop_rev=int(r["develop_rev"]) + 1, edit_time=now_iso(), edited=1 if S.edited(new, r["kind"]) else 0)
    if history:
        ch.insert("history", photo_id=pid, name=label, settings=json.dumps(new, separators=(",", ":")), time=now_iso())


def after(pids: list[int]) -> None:
    from app.engine.cmd_ai import adapt
    for pid in pids:
        previews.request(pid, "t")
    adapt(pids)


def _apply_values(dev: dict, values: dict, delta: bool) -> dict:
    out = copy.deepcopy(dev)
    for cid, v in values.items():
        if cid not in S.controls():
            raise CommandError(f"Unknown control {cid}; list them with develop.controls")
        base = S.get(out, cid) if delta else 0.0
        S.put(out, cid, base + float(v))
        if cid in ("wb.temp", "wb.tint"):
            out.setdefault("wb", {})["mode"] = "custom"
    return out


@command("develop.controls", "Develop Controls", mutates=False)
def controls() -> dict:
    d = S.doc()
    return {"controls": d["controls"], "local": d["local"], "panels": d["panels"], "wbPresets": d["wbPresets"], "mixerBands": d["mixerBands"], "aspects": d["aspects"]}


@command("develop.get", "Develop Settings", {"id": {"type": "integer"}}, mutates=False)
def get(id: int | None = None) -> dict:
    pid = int(id) if id is not None else resolve_ids("active")[0]
    dev, kind = current(pid)
    vals = {cid: S.get(dev, cid) for cid in S.controls()}
    return {"id": pid, "settings": dev, "values": vals, "kind": kind}


@command("develop.spotSource", "Find Spot Source", {"id": {"type": "integer"}, "spot": {"type": "object"}, "settings": {"type": "object"}}, mutates=False)
def spot_source(spot: dict, id: int | None = None, settings: dict | None = None) -> dict:
    import numpy as np
    from app.develop.render import effective, plan
    from app.develop.retouch import auto_source
    pid = int(id) if id is not None else resolve_ids("active")[0]
    dev = settings if settings is not None else current(pid)[0]
    img, _ = previews.source(pid)
    eff = effective({k: v for k, v in dev.items() if k != "spots"})
    sh, sw = img.shape[:2]
    frame, w, h, ppl = plan(sw, sh, eff, 1024)
    sampled = frame.sample(img, w, h)
    pts = spot.get("points") or [[0.5, 0.5]]
    p = frame.norm_to_out(w, h) @ np.array([float(pts[0][0]), float(pts[0][1]), 1.0])
    off = auto_source(sampled, (float(p[0]), float(p[1])), max(1.0, float(spot.get("size", 0.02)) * ppl))
    n = frame.out_to_norm(w, h)
    return {"source": [round(float(n[0, 0] * off[0] + n[0, 1] * off[1]), 6), round(float(n[1, 0] * off[0] + n[1, 1] * off[1]), 6)]}


@command("develop.lensBlurFocus", "Lens Blur Focus Point", {"id": {"type": "integer"}, "x": {"type": "number"}, "y": {"type": "number"}, "box": {"type": "array", "description": "[x0, y0, x1, y1] to focus on an area instead of a point"}, "apply": {"type": "boolean"}})
def lens_blur_focus(x: float = 0.5, y: float = 0.5, id: int | None = None, box: list[float] | None = None, apply: bool = True) -> dict:
    import numpy as np
    from app.develop.masks import load_bitmap
    from app.develop.render import effective, plan
    pid = int(id) if id is not None else resolve_ids("active")[0]
    dev, _ = current(pid)
    key = (dev.get("lensBlur") or {}).get("depth")
    if not key:
        raise CommandError("Build the depth map first (ai.depth)")
    img, _ = previews.source(pid)
    sh, sw = img.shape[:2]
    frame, w, h, _ = plan(sw, sh, effective(dev), 512)
    depth = load_bitmap(pid, key, frame, w, h)
    to = frame.norm_to_out(w, h)
    pts = [(float(box[0]), float(box[1])), (float(box[2]), float(box[3]))] if box and len(box) == 4 else [(float(x), float(y))]
    px = [to @ np.array([a, b, 1.0]) for a, b in pts]
    xs = sorted(int(min(max(p[0], 0), w - 1)) for p in px)
    ys = sorted(int(min(max(p[1], 0), h - 1)) for p in px)
    r = 2 if len(pts) == 1 else 0
    patch = depth[max(0, ys[0] - r):ys[-1] + r + 1, max(0, xs[0] - r):xs[-1] + r + 1]
    far = float(1.0 - np.median(patch))
    spread = float(np.percentile(patch, 90) - np.percentile(patch, 10)) if patch.size > 4 else 0.0
    focus = round(far * 100.0, 1)
    rng = round(min(100.0, max(5.0, spread * 200.0)), 1) if len(pts) > 1 else None
    if apply:
        with cat().change("Lens Blur Focus") as ch:
            new = json.loads(json.dumps(dev))
            lb = new.setdefault("lensBlur", {})
            lb["focalDistance"] = focus
            if rng is not None:
                lb["focalRange"] = rng
            store(ch, pid, new, "Lens Blur Focus")
        after([pid])
    return {"id": pid, "focalDistance": focus, "focalRange": rng}


@command("develop.sampleColor", "Sample Color", {"id": {"type": "integer"}, "x": {"type": "number"}, "y": {"type": "number"}}, mutates=False)
def sample_color(x: float, y: float, id: int | None = None, settings: dict | None = None) -> dict:
    import numpy as np
    from app.develop import colour
    from app.develop.masks import tonemap_for_select
    from app.develop.render import effective, plan, white_balance
    pid = int(id) if id is not None else resolve_ids("active")[0]
    dev = settings if settings is not None else current(pid)[0]
    img, info_ = previews.source(pid)
    eff = effective(dev)
    sh, sw = img.shape[:2]
    frame, w, h, _ = plan(sw, sh, eff, 1024)
    p = frame.norm_to_out(w, h) @ np.array([float(x), float(y), 1.0])
    px, py = int(min(max(p[0], 0), w - 1)), int(min(max(p[1], 0), h - 1))
    lin = white_balance(frame.sample(img, w, h), info_, eff, pid, full=img)
    patch = lin[max(0, py - 2):py + 3, max(0, px - 2):px + 3].reshape(-1, 3).mean(axis=0)
    ev = float((eff.get("light") or {}).get("exposure", 0))
    lab = colour.oklab_from_2020(tonemap_for_select(patch[None, :] * (2.0 ** ev)))[0]
    from app.develop.colorops import band_weights
    from app.develop.settings import BANDS
    hue = np.array([np.arctan2(lab[2], lab[1])], np.float64)
    weights = band_weights(hue)[0]
    l = float(lab[0])
    region = "shadows" if l < 0.3 else "darks" if l < 0.5 else "lights" if l < 0.72 else "highlights"
    return {"lab": [round(float(v), 5) for v in lab], "band": BANDS[int(np.argmax(weights))], "region": region,
            "chroma": round(float(np.hypot(lab[1], lab[2])), 5)}


@command("lens.database", "Lens Profile Database", {"download": {"type": "boolean"}, "wait": {"type": "boolean"}})
def lens_database(download: bool = False, wait: bool = False) -> dict:
    from app.engine import tasks
    from app.services import lensdb
    status = {"available": lensdb.available(), "lenses": len(lensdb.index()["lenses"]) if lensdb.available() else 0, "attribution": lensdb.ATTRIBUTION}
    if not download:
        return status
    tid = tasks.start("lensdb", "Downloading lens profiles", lambda progress: lensdb.download(progress))
    if wait:
        t = tasks.wait(tid)
        if t and t["state"] == "failed":
            raise CommandError(t["error"] or "Download failed")
        return {**status, "task": tid, **(t.get("result") or {} if t else {}), "available": lensdb.available()}
    return {**status, "task": tid}


@command("lens.makers", "Lens Makers", mutates=False)
def lens_makers() -> dict:
    from app.services import lensdb
    return {"makers": lensdb.makers()}


@command("lens.models", "Lens Models", {"maker": {"type": "string"}}, mutates=False)
def lens_models(maker: str) -> dict:
    from app.services import lensdb
    return {"models": lensdb.models(maker)}


@command("develop.autoCa", "Measure Chromatic Aberration", {"id": {"type": "integer"}}, mutates=False)
def auto_ca(id: int | None = None) -> dict:
    from app.develop import fringe
    pid = int(id) if id is not None else resolve_ids("active")[0]
    prof = ((current(pid)[0].get("optics") or {}).get("profile") or {})
    if prof.get("enabled") and (prof.get("lensfun") or {}).get("tca"):
        return {"autoCaRed": 0.0, "autoCaBlue": 0.0, "fromProfile": True}
    img, _ = previews.source(pid)
    red, blue = fringe.estimate_ca(img)
    return {"autoCaRed": red, "autoCaBlue": blue}


@command("develop.fringeHue", "Defringe Color Selector", {"id": {"type": "integer"}, "x": {"type": "number"}, "y": {"type": "number"}}, mutates=False)
def fringe_hue(x: float, y: float, id: int | None = None) -> dict:
    from app.develop import fringe
    s = sample_color(x, y, id)
    deg = fringe.degrees(s["lab"])
    kind = "purple" if fringe.PURPLE_BASE - 20 <= deg <= fringe.PURPLE_BASE + 140 else "green" if fringe.GREEN_BASE - 30 <= deg <= fringe.GREEN_BASE + 130 else ""
    if not kind or s["chroma"] < 0.02:
        return {"kind": "", "hue": round(deg, 1), "chroma": s["chroma"]}
    centre = fringe.slider_for_hue(kind, deg)
    return {"kind": kind, "hue": round(deg, 1), "lo": round(max(0.0, centre - 15)), "hi": round(min(100.0, centre + 15)), "chroma": s["chroma"]}


@command("develop.proofProfiles", "Soft Proofing Profiles", mutates=False)
def proof_profiles() -> dict:
    from app.output import icc
    return {"profiles": icc.profiles(), "folders": [str(f) for f in icc.folders()], "intents": list(icc.INTENTS)}


@command("develop.lensProfileInfo", "Lens Profile", {"id": {"type": "integer"}}, mutates=False)
def lens_profile_info(id: int) -> dict:
    from app.develop import lensprofile
    from app.services import lensdb
    path = cat().photo_path(int(id))
    found = lensprofile.read(path) if path is not None and path.is_file() else None
    dev, _ = current(int(id))
    prof = (dev.get("optics") or {}).get("profile") or {}
    out = {"available": bool(found), "kinds": sorted(found) if found else [], "enabled": bool(prof.get("enabled")), "source": "DNG opcodes" if found else None,
           "database": lensdb.available(), "lens": (prof.get("lensfun") or {}).get("lens"), "maker": (prof.get("lensfun") or {}).get("maker"), "guess": None}
    if not found and lensdb.available():
        lens, score = _lens_guess(int(id))
        if lens is not None:
            out.update(available=True, source="Lensfun", guess={"maker": lens["maker"], "model": lens["model"], "score": round(score, 2)})
    return out


def _photo_optics(pid: int) -> tuple[str, str, str, float | None, float | None, float | None]:
    r = cat().row("SELECT camera, lens, focal, exif FROM photos WHERE id=?", (pid,))
    exif = records.loads(r["exif"], {}) if r else {}
    focal = float(r["focal"]) if r and r["focal"] else (float(exif["focal"]) if exif.get("focal") else None)
    f35 = exif.get("focal35")
    crop = (float(f35) / focal) if f35 and focal else None
    aperture = float(exif["aperture"]) if exif.get("aperture") else None
    return str(exif.get("make") or ""), str((r["camera"] if r else "") or exif.get("model") or ""), str((r["lens"] if r else "") or exif.get("lens") or ""), focal, aperture, crop


def _lens_guess(pid: int) -> tuple[dict | None, float]:
    from app.services import lensdb
    make, model, lens, focal, _, _ = _photo_optics(pid)
    if not lens:
        return None, 0.0
    best, score = lensdb.match(lens, make, model, focal)
    return (best, score) if best is not None and score >= 0.6 else (None, score)


def _lensfun_profile(pid: int, model: str | None) -> dict | None:
    from app.services import lensdb
    if not lensdb.available():
        return None
    lens = lensdb.lens(model) if model else _lens_guess(pid)[0]
    if lens is None:
        return None
    make, cam_model, _, focal, aperture, crop = _photo_optics(pid)
    cam = lensdb.camera(make, cam_model)
    return lensdb.profile_for(lens, focal or lens["fmin"] or 50.0, aperture, (cam or {}).get("crop") or crop)


@command("develop.lensProfile", "Enable Profile Corrections", {"ids": {"type": "array"}, "enable": {"type": "boolean"}})
def lens_profile(ids: Any = None, enable: bool = True, lens: str | None = None) -> dict:
    from app.develop import lensprofile
    pids = resolve_ids(ids)
    applied, missing = [], []
    with cat().change("Enable Profile Corrections" if enable else "Disable Profile Corrections") as ch:
        for pid in pids:
            dev, _ = current(pid)
            new = copy.deepcopy(dev)
            optics = new.setdefault("optics", {})
            if not enable:
                optics.pop("profile", None)
                store(ch, pid, new, "Disable Profile Corrections")
                applied.append(pid)
                continue
            path = cat().photo_path(pid)
            found = None if lens else (lensprofile.read(path) if path is not None and path.is_file() else None)
            if not found:
                lf = _lensfun_profile(pid, lens)
                found = {"lensfun": lf, "source": "Lensfun"} if lf else None
            if not found:
                missing.append(pid)
                continue
            optics["profile"] = {"enabled": True, **found}
            store(ch, pid, new, "Enable Profile Corrections")
            applied.append(pid)
    after(applied)
    return {"ids": applied, "noProfile": missing}


@command("develop.info", "Develop Source Info", {"id": {"type": "integer"}, "settings": {"type": "object"}}, mutates=False)
def info(id: int | None = None, settings: dict | None = None) -> dict:
    from app.develop import profiles
    from app.develop.render import effective_wb
    pid = int(id) if id is not None else resolve_ids("active")[0]
    dev, kind = current(pid)
    if settings is not None:
        dev = settings
    img, src = previews.source(pid)
    t, ti = effective_wb(img, src, dev, pid)
    return {"id": pid, "kind": kind, "raw": bool(src.get("raw")), "asShotTemp": round(float(src.get("asShotTemp", 6500))), "asShotTint": round(float(src.get("asShotTint", 0))),
            "temp": round(t), "tint": round(ti), "relativeWb": bool(src.get("relativeWb")), "cameraLook": "cameraLook" in src,
            "width": src.get("fullWidth"), "height": src.get("fullHeight"), "profiles": profiles.catalogue(str(src.get("camera") or ""), str((dev.get("profile") or {}).get("id", ""))),
            "cameraStyle": src.get("cameraStyle")}


@command("develop.set", "Develop", {"ids": {"type": "array"}, "values": {"type": "object"}, "delta": {"type": "boolean"}})
def set_values(ids: Any = None, values: dict | None = None, delta: bool = False, label: str = "") -> dict:
    pids = resolve_ids(ids)
    values = values or {}
    if not values:
        raise CommandError("values is empty: pass {control id: value}")
    c = cat()
    name = label or (S.controls()[next(iter(values))]["label"] if len(values) == 1 and next(iter(values)) in S.controls() else "Develop Settings")
    with c.change(name) as ch:
        for pid in pids:
            dev, _ = current(pid)
            if any(k in ("wb.temp", "wb.tint") for k in values):
                dev = seed_wb(pid, dev)
            store(ch, pid, _apply_values(dev, values, delta), name)
    after(pids)
    return {"ids": pids}


def seed_wb(pid: int, dev: dict) -> dict:
    wb = dev.get("wb") or {}
    if wb.get("mode", "asShot") == "custom":
        return dev
    from app.develop.render import effective_wb
    img, info = previews.source(pid)
    t, ti = effective_wb(img, info, dev, pid)
    out = copy.deepcopy(dev)
    out["wb"] = {"mode": "custom", "temp": round(t), "tint": round(ti)}
    return out


def deep_patch(dev: dict, patch: dict) -> dict:
    out = copy.deepcopy(dev)
    for k, v in patch.items():
        if v is None:
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict) and not k.startswith("="):
            out[k] = deep_patch(out[k], v)
        else:
            out[k.lstrip("=")] = copy.deepcopy(v)
    return out


@command("develop.update", "Develop", {"ids": {"type": "array"}, "patch": {"type": "object"}, "label": {"type": "string"}})
def update(ids: Any = None, patch: dict | None = None, label: str = "Develop", replace: bool = False) -> dict:
    pids = resolve_ids(ids)
    c = cat()
    with c.change(label) as ch:
        for pid in pids:
            dev, _ = current(pid)
            store(ch, pid, copy.deepcopy(patch or {}) if replace else deep_patch(dev, patch or {}), label)
    after(pids)
    return {"ids": pids}


@command("develop.reset", "Reset", {"ids": {"type": "array"}, "groups": {"type": "array"}})
def reset(ids: Any = None, groups: list[str] | None = None, controls: list[str] | None = None) -> dict:
    pids = resolve_ids(ids)
    c = cat()
    with c.change("Reset") as ch:
        for pid in pids:
            dev, kind = current(pid)
            if controls:
                new = copy.deepcopy(dev)
                for cid in controls:
                    S.put(new, cid, S.controls()[cid]["default"])
            elif groups:
                new = S.apply_groups(dev, S.defaults_for(kind), groups)
            else:
                new = S.defaults_for(kind)
            store(ch, pid, new, "Reset")
    after(pids)
    return {"ids": pids}


@command("develop.auto", "Auto Settings", {"ids": {"type": "array"}})
def auto(ids: Any = None) -> dict:
    from app.develop.auto import auto_tone
    pids = resolve_ids(ids)
    c = cat()
    out = {}
    with c.change("Auto Settings") as ch:
        for pid in pids:
            dev, _ = current(pid)
            img, info = previews.source(pid)
            a = auto_tone(img, info, dev)
            new = S.merge(dev, a)
            store(ch, pid, new, "Auto Settings")
            out[pid] = a
    after(pids)
    return {"ids": pids, "values": out}


@command("develop.autoWhiteBalance", "Auto White Balance", {"ids": {"type": "array"}})
def auto_wb(ids: Any = None) -> dict:
    from app.develop.auto import auto_wb as compute
    pids = resolve_ids(ids)
    c = cat()
    with c.change("Auto White Balance") as ch:
        for pid in pids:
            dev, _ = current(pid)
            img, info = previews.source(pid)
            t, tint = compute(img, info)
            new = copy.deepcopy(dev)
            new["wb"] = {"mode": "auto", "temp": t, "tint": tint}
            store(ch, pid, new, "Auto White Balance")
    after(pids)
    return {"ids": pids}


@command("develop.whiteBalancePreset", "White Balance", {"ids": {"type": "array"}, "mode": {"type": "string"}})
def wb_preset(ids: Any = None, mode: str = "asShot") -> dict:
    if mode == "auto":
        return auto_wb(ids)
    pids = resolve_ids(ids)
    c = cat()
    with c.change(f"White Balance: {mode}") as ch:
        for pid in pids:
            dev, _ = current(pid)
            new = copy.deepcopy(dev)
            from app.develop.render import WB_PRESETS
            new["wb"] = {"mode": mode}
            if mode in WB_PRESETS:
                new["wb"].update(temp=WB_PRESETS[mode][0], tint=WB_PRESETS[mode][1])
            store(ch, pid, new, "White Balance")
    after(pids)
    return {"ids": pids}


@command("develop.whiteBalancePick", "White Balance Selector", {"id": {"type": "integer"}, "x": {"type": "number"}, "y": {"type": "number"}})
def wb_pick(x: float, y: float, id: int | None = None, apply: bool = True) -> dict:
    from app.develop import auto as auto_mod
    from app.develop.render import effective, plan
    pid = int(id) if id is not None else resolve_ids("active")[0]
    dev, _ = current(pid)
    img, info = previews.source(pid)
    eff = effective(dev)
    sh, sw = img.shape[:2]
    frame, w, h, ppl = plan(sw, sh, eff, 1024)
    sampled = frame.sample(img, w, h)
    to_out = frame.norm_to_out(w, h)
    import numpy as np
    p = to_out @ np.array([float(x), float(y), 1.0])
    px, py = int(p[0]), int(p[1])
    r = max(1, int(min(w, h) * 0.004))

    def patch(_x: float, _y: float):
        return sampled[max(0, py - r):py + r + 1, max(0, px - r):px + r + 1]
    t, tint = auto_mod.pick_wb(img, info, eff, x, y, patch)
    if apply:
        with cat().change("White Balance Selector") as ch:
            new = copy.deepcopy(dev)
            new["wb"] = {"mode": "custom", "temp": t, "tint": tint}
            store(ch, pid, new, "White Balance Selector")
        after([pid])
    return {"temp": t, "tint": tint}


@command("develop.autoBw", "Auto B&W Mix", {"ids": {"type": "array"}})
def auto_bw(ids: Any = None) -> dict:
    from app.develop.auto import auto_bw as compute
    pids = resolve_ids(ids)
    with cat().change("Auto B&W Mix") as ch:
        for pid in pids:
            dev, _ = current(pid)
            img, info = previews.source(pid)
            new = copy.deepcopy(dev)
            new["bw"] = compute(img, info, dev)
            new["treatment"] = "bw"
            store(ch, pid, new, "Auto B&W Mix")
    after(pids)
    return {"ids": pids}


@command("develop.copy", "Copy Settings", {"id": {"type": "integer"}, "groups": {"type": "array"}}, mutates=False)
def copy_settings(id: int | None = None, groups: list[str] | None = None) -> dict:
    pid = int(id) if id is not None else resolve_ids("active")[0]
    dev, _ = current(pid)
    with SESSION.lock:
        SESSION.clipboard = {"settings": copy.deepcopy(dev), "groups": groups, "from": pid}
    return {"groups": groups or [], "from": pid}


@command("develop.paste", "Paste Settings", {"ids": {"type": "array"}, "amount": {"type": "number"}})
def paste(ids: Any = None, groups: list[str] | None = None, amount: float = 1.0) -> dict:
    pids = resolve_ids(ids)
    with SESSION.lock:
        clip = copy.deepcopy(SESSION.clipboard)
    if not clip:
        raise CommandError("Nothing copied: develop.copy first")
    g = groups if groups is not None else clip["groups"]
    with cat().change("Paste Settings") as ch:
        for pid in pids:
            dev, _ = current(pid)
            store(ch, pid, S.apply_groups(dev, clip["settings"], g, amount), "Paste Settings")
    after(pids)
    return {"ids": pids}


@command("develop.sync", "Sync Settings", {"ids": {"type": "array"}, "from": {"type": "integer"}, "groups": {"type": "array"}})
def sync(ids: Any = None, groups: list[str] | None = None, **kw: Any) -> dict:
    src = kw.get("from") or SESSION.active
    if not src:
        raise CommandError("No source photo: pass from, or make a photo active")
    pids = [p for p in resolve_ids(ids) if p != int(src)]
    dev, _ = current(int(src))
    with cat().change("Sync Settings") as ch:
        for pid in pids:
            target, _ = current(pid)
            store(ch, pid, S.apply_groups(target, dev, groups), "Sync Settings")
    after(pids)
    return {"ids": pids, "from": int(src)}


@command("develop.pastePrevious", "Paste Settings from Previous", {"ids": {"type": "array"}})
def paste_previous(ids: Any = None) -> dict:
    prev = SESSION.previous_photo
    if not prev:
        raise CommandError("No previous photo")
    return sync(ids, None, **{"from": prev})


@command("develop.matchExposure", "Match Total Exposures", {"ids": {"type": "array"}})
def match_exposure(ids: Any = None) -> dict:
    import math
    pids = resolve_ids(ids)
    ref = SESSION.active or pids[0]
    c = cat()

    def ev_of(pid: int) -> float | None:
        r = c.row("SELECT shutter, iso, aperture FROM photos WHERE id=?", (pid,))
        if not r or not r["shutter"] or not r["iso"] or not r["aperture"]:
            return None
        return math.log2(float(r["shutter"]) * float(r["iso"]) / (float(r["aperture"]) ** 2))
    base = ev_of(ref)
    if base is None:
        raise CommandError("The active photo has no exposure data")
    ref_dev, _ = current(ref)
    ref_exp = S.get(ref_dev, "light.exposure")
    with c.change("Match Total Exposures") as ch:
        for pid in pids:
            e = ev_of(pid)
            if e is None or pid == ref:
                continue
            dev, _ = current(pid)
            new = copy.deepcopy(dev)
            S.put(new, "light.exposure", ref_exp + (base - e))
            store(ch, pid, new, "Match Total Exposures")
    after(pids)
    return {"ids": pids}


@command("develop.history", "History", {"id": {"type": "integer"}}, mutates=False)
def history(id: int | None = None) -> dict:
    pid = int(id) if id is not None else resolve_ids("active")[0]
    rows = cat().rows("SELECT id, name, time FROM history WHERE photo_id=? ORDER BY id DESC LIMIT ?", (pid, HISTORY_KEEP))
    return {"id": pid, "steps": [{"id": int(r["id"]), "name": r["name"], "time": r["time"]} for r in rows]}


@command("develop.historyRestore", "Go to History Step", {"id": {"type": "integer"}, "step": {"type": "integer"}})
def history_restore(step: int, id: int | None = None) -> dict:
    pid = int(id) if id is not None else resolve_ids("active")[0]
    r = cat().row("SELECT settings, name FROM history WHERE id=? AND photo_id=?", (int(step), pid))
    if r is None:
        raise CommandError("No such history step")
    with cat().change(f"History: {r['name']}") as ch:
        store(ch, pid, json.loads(r["settings"]), f"History: {r['name']}", history=False)
    after([pid])
    return {"id": pid}


@command("develop.historyClear", "Clear History", {"id": {"type": "integer"}})
def history_clear(id: int | None = None) -> dict:
    pid = int(id) if id is not None else resolve_ids("active")[0]
    with cat().change("Clear History") as ch:
        ch.delete("history", photo_id=pid)
    return {"id": pid}


@command("snapshot.create", "New Snapshot", {"id": {"type": "integer"}, "name": {"type": "string"}})
def snapshot_create(name: str = "", id: int | None = None) -> dict:
    pid = int(id) if id is not None else resolve_ids("active")[0]
    dev, _ = current(pid)
    with cat().change("New Snapshot") as ch:
        sid = ch.insert("snapshots", photo_id=pid, name=name or now_iso().replace("T", " "), settings=json.dumps(dev, separators=(",", ":")), time=now_iso())
    return {"id": sid}


@command("snapshot.list", "Snapshots", {"id": {"type": "integer"}}, mutates=False)
def snapshot_list(id: int | None = None) -> dict:
    pid = int(id) if id is not None else resolve_ids("active")[0]
    rows = cat().rows("SELECT id, name, time FROM snapshots WHERE photo_id=? ORDER BY name COLLATE NOCASE", (pid,))
    return {"id": pid, "snapshots": [{"id": int(r["id"]), "name": r["name"], "time": r["time"]} for r in rows]}


@command("snapshot.apply", "Apply Snapshot", {"snapshot": {"type": "integer"}})
def snapshot_apply(snapshot: int) -> dict:
    r = cat().row("SELECT photo_id, settings, name FROM snapshots WHERE id=?", (int(snapshot),))
    if r is None:
        raise CommandError("No such snapshot")
    with cat().change(f"Snapshot: {r['name']}") as ch:
        store(ch, int(r["photo_id"]), json.loads(r["settings"]), f"Snapshot: {r['name']}")
    after([int(r["photo_id"])])
    return {"id": int(r["photo_id"])}


@command("snapshot.update", "Update Snapshot", {"snapshot": {"type": "integer"}, "name": {"type": "string"}})
def snapshot_update(snapshot: int, name: str | None = None, settings: bool = False) -> dict:
    r = cat().row("SELECT photo_id FROM snapshots WHERE id=?", (int(snapshot),))
    if r is None:
        raise CommandError("No such snapshot")
    fields: dict = {}
    if name is not None:
        fields["name"] = name
    if settings:
        dev, _ = current(int(r["photo_id"]))
        fields["settings"] = json.dumps(dev, separators=(",", ":"))
    with cat().change("Update Snapshot") as ch:
        ch.update("snapshots", int(snapshot), **fields)
    return {"snapshot": int(snapshot)}


@command("snapshot.delete", "Delete Snapshot", {"snapshot": {"type": "integer"}})
def snapshot_delete(snapshot: int) -> dict:
    with cat().change("Delete Snapshot") as ch:
        ch.delete("snapshots", id=int(snapshot))
    return {"snapshot": int(snapshot)}


def before_of(pid: int) -> dict:
    got = cat().get_meta(f"before:{pid}", None)
    if isinstance(got, dict):
        return got
    return S.defaults_for(str(cat().scalar("SELECT kind FROM photos WHERE id=?", (pid,)) or ""))


@command("develop.before", "Before Settings", {"id": {"type": "integer"}}, mutates=False)
def before_get(id: int | None = None) -> dict:
    pid = int(id) if id is not None else resolve_ids("active")[0]
    return {"id": pid, "settings": before_of(pid), "custom": isinstance(cat().get_meta(f"before:{pid}", None), dict)}


@command("develop.setBefore", "Set Before", {"id": {"type": "integer"}, "source": {"type": "string", "enum": ["after", "defaults", "history", "snapshot"]},
                                             "step": {"type": "integer"}, "snapshot": {"type": "integer"}})
def before_set(source: str = "after", id: int | None = None, step: int | None = None, snapshot: int | None = None) -> dict:
    from app.engine import events
    pid = int(id) if id is not None else resolve_ids("active")[0]
    if source == "after":
        dev, label = current(pid)[0], "Copy After to Before"
    elif source == "history":
        r = cat().row("SELECT settings, name FROM history WHERE id=? AND photo_id=?", (int(step or 0), pid))
        if r is None:
            raise CommandError("No such history step")
        dev, label = json.loads(r["settings"]), f"Before: {r['name']}"
    elif source == "snapshot":
        r = cat().row("SELECT settings, name FROM snapshots WHERE id=? AND photo_id=?", (int(snapshot or 0), pid))
        if r is None:
            raise CommandError("No such snapshot")
        dev, label = json.loads(r["settings"]), f"Before: {r['name']}"
    else:
        dev, label = None, "Reset Before"
    with cat().change(label) as ch:
        ch.set_meta(f"before:{pid}", dev)
    events.publish("before", id=pid)
    return {"id": pid, "label": label}


@command("develop.beforeToAfter", "Copy Before to After", {"id": {"type": "integer"}, "swap": {"type": "boolean"}})
def before_to_after(id: int | None = None, swap: bool = False) -> dict:
    from app.engine import events
    pid = int(id) if id is not None else resolve_ids("active")[0]
    now = current(pid)[0]
    label = "Swap Before and After" if swap else "Copy Before to After"
    with cat().change(label) as ch:
        store(ch, pid, copy.deepcopy(before_of(pid)), label)
        if swap:
            ch.set_meta(f"before:{pid}", now)
    after([pid])
    events.publish("before", id=pid)
    return {"id": pid}
