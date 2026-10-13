import asyncio
import base64
import io
import json
import os
import urllib.parse
import uuid
from typing import Any, Callable

from fastapi import APIRouter, Request, Response

from app import __version__
from app.core import config
from app.engine import agents
from app.engine import catalog as catalog_mod
from app.engine import events
from app.engine.commands import REGISTRY, CommandError, catalogue, dispatch
from app.routers.mcp_workflows import WORKFLOWS

router = APIRouter()
VERSIONS = ["2026-07-28", "2025-11-25"]
INSTRUCTIONS = ("formlit is a photo library and raw developer running on this computer, a Lightroom alternative. Every tool works on its catalog "
                "with or without the window open, and every change is one undoable step (undo). Start with get_catalog, then find_photos to get "
                "photo ids. Measure with analyze_photo (tonal zones, clipping, colour cast, findings with suggested values) and look with get_preview before and after developing; "
                "both take proposed values or a preset without saving. list_presets takes a query (\"moody forest\", \"bw street\") and describes each preset. "
                "match_look copies a reference photo's look in one call. Be efficient: batch every slider into one develop_set, pass report true on edits instead of a separate analyze_photo, and preview at max_size 512. Develop values use dotted ids from get_develop_controls (for "
                "example light.exposure, color.vibrance, effects.clarity); pass delta true to nudge. Long jobs (import, AI, export) wait until done. For a full "
                "plan, get the culling_workflow or develop_strategy prompt. run_command reaches every engine command listed by list_commands. The first call asks the person "
                "to allow outside agents in formlit's window; if a call is refused with a message about outside agents, tell them to open formlit and answer there, or to "
                "change AI agents in Preferences, and stop instead of retrying.")
CULLING = """How to cull a shoot in formlit.

1. find_photos with source {"kind": "previousImport"} (or a folder id from get_catalog) lists the shoot.
2. analyze_culling scores sharpness, exposure, faces and groups near-duplicates; it writes nothing visible.
3. apply_culling with pickBest true flags the best frame of each group of near-duplicates as a pick; rejectBlurry rejects frames whose sharpness score is under the threshold (35 by default) and rejectDuplicates rejects the rest of each group. Check a few with get_preview.
4. set_flag, set_rating and set_label adjust by hand. Ratings 0 to 5, flags pick, reject or none.
5. find_photos with filter {"flags": ["pick"]} gives the selects; create_collection with those ids keeps them together.
6. Nothing is deleted. Rejected photos stay in the catalog until a person removes them in the window.
"""
DEVELOP = """How to develop a photo in formlit.

1. get_photo tells you the camera, lens, exposure and current settings; get_preview shows it (long side up to 2048); analyze_photo measures it: luminance percentiles, tonal zones, clipping, colour cast and findings with suggested values.
2. auto_tone gives a balanced starting point, or a preset: list_presets with a query finds one by purpose, and get_preview or analyze_photo with preset and amount previews it before apply_preset. develop_set refines. Basic ids: wb.temp, wb.tint, light.exposure, light.contrast, light.highlights, light.shadows, light.whites, light.blacks, effects.texture, effects.clarity, effects.dehaze, color.vibrance, color.saturation. get_develop_controls lists every id with its range.
3. Preview a change before committing: get_preview and analyze_photo with values render the proposal without saving it. Colour grading (grading.shadows.hue, .sat, grading.blending, grading.balance) reads best at saturation 7 to 20.
4. Local edits: add_ai_mask with kind sky, subject, background, people or depth and an adjust object (exposure, contrast, highlights, shadows, temp, tint, saturation, clarity, dehaze, texture, sharpness, noise). add_gradient_mask adds a linear or radial mask.
5. Presets: list_presets then apply_preset with an amount. sync_settings copies one photo's look to others, by group (whiteBalance, basicTone, presence, toneCurve, colorMixer, colorGrading, treatment, detail, lensCorrections, transform, effects, calibration, profile, crop, masks); with no groups it copies everything except crop, masks, spots and red eye.
6. Geometry: auto_straighten levels the horizon; upright applies auto, level, vertical or full perspective correction.
7. Check with get_preview after every step; undo steps back one change.
8. Deliver with export_photos (a preset such as builtin.web, or settings) to an absolute folder.
"""
PROMPTS = [
    {"name": "culling_workflow", "title": "Cull a shoot", "description": "Score, group, pick and reject a shoot with formlit's tools.", "arguments": []},
    {"name": "develop_strategy", "title": "Develop a photo", "description": "The order formlit's develop tools work best in, with the setting ids.", "arguments": []},
] + [{"name": k, "title": v["title"], "description": v["description"], "arguments": []} for k, v in WORKFLOWS.items()]
ALLOW_DELETE = os.environ.get("FORMLIT_MCP_ALLOW_DELETE") == "1"
BLOCKED = {"photo.delete", "folder.remove", "catalog.open", "catalog.create", "agents.respond"}
WINDOW_ONLY = {"terminal", "claudecode"}
LIST_CACHE = {"ttlMs": 60_000, "cacheScope": "private"}
SESSIONS: dict[str, str] = {}
MAX_SESSIONS = 64


def _tool(name: str, description: str, props: dict, required: list[str] | None = None, **hints: bool) -> dict:
    return {"name": name, "description": description, "inputSchema": {"type": "object", "properties": props, "required": required or [], "additionalProperties": False},
            "annotations": {"readOnlyHint": hints.get("read", False), "destructiveHint": hints.get("destructive", False), "idempotentHint": hints.get("idempotent", False), "openWorldHint": False}}


IDS = {"type": "array", "items": {"type": "integer"}, "description": "Photo ids from find_photos."}
ID = {"type": "integer", "description": "A photo id from find_photos."}
WAIT = {"type": "boolean", "default": True, "description": "Wait for the job to finish (default) or return its task id."}


def _cmd(cid: str, **params: Any) -> Any:
    return dispatch(cid, {k: v for k, v in params.items() if v is not None})


def _straighten(args: dict) -> dict:
    from app.develop.geometry import crop_fit_angle
    from app.engine import catalog as catalog_mod
    from app.engine.commands import resolve_ids
    out = []
    for pid in resolve_ids(args.get("ids")):
        angle = float(dispatch("develop.autoStraighten", {"id": pid})["angle"])
        r = catalog_mod.get().row("SELECT width, height FROM photos WHERE id=?", (pid,))
        w, h = (float(r["width"] or 3), float(r["height"] or 2)) if r else (3.0, 2.0)
        rect = [round(v, 6) for v in crop_fit_angle(w, h, angle)]
        dispatch("develop.update", {"ids": [pid], "patch": {"crop": {"angle": angle, "rect": rect}}, "label": "Auto Straighten"})
        out.append({"id": pid, "angle": angle})
    return {"photos": out}


def _preview(args: dict) -> dict:
    from PIL import Image
    from app.develop import settings as S
    from app.engine.records import loads
    from app.services import previews
    pid = int(args["id"])
    long = max(64, min(2048, int(args.get("max_size", 1024))))
    dev = None
    if args.get("values") or args.get("before") or args.get("preset"):
        row = catalog_mod.get().row("SELECT develop FROM photos WHERE id=?", (pid,))
        if row is None:
            raise CommandError(f"No photo with id {pid}", 404)
        dev = {} if args.get("before") else json.loads(json.dumps(loads(row["develop"], {})))
        if args.get("preset") and not args.get("before"):
            from app.engine import presets
            dev = presets.blended(dev, str(args["preset"]), float(args.get("amount", 100)))
        for k, v in (args.get("values") or {}).items():
            S.put(dev, k, float(v))
    rgb = previews.render_rgb8(pid, long, dev)
    buf = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(buf, "JPEG", quality=88)
    meta = {"id": pid, "width": int(rgb.shape[1]), "height": int(rgb.shape[0]), "proposed": bool(args.get("values") or args.get("preset")), "before": bool(args.get("before"))}
    if args.get("analyze"):
        from app.engine import cmd_analyze
        meta["analysis"] = cmd_analyze.quick(pid, rgb)
    return {"__image": base64.b64encode(buf.getvalue()).decode(), "meta": meta}


def _report(args: dict, result: Any, ids: Any) -> Any:
    if not args.get("report"):
        return result
    from app.engine import cmd_analyze
    from app.engine.commands import resolve_ids
    out = result if isinstance(result, dict) else {"result": result}
    out["report"] = [cmd_analyze.quick(p) for p in resolve_ids(ids)[:12]]
    return out


REPORT = {"type": "boolean", "default": False, "description": "Return a compact measurement of each changed photo (median, end points, contrast, clipping, saturation, cast, issues) so no separate analyze_photo call is needed."}


def _find(args: dict) -> dict:
    res = _cmd("library.query", source=args.get("source") or {"kind": "all"}, filter=args.get("filter"), sort=args.get("sort"), stacks=False)
    ids = list(res.get("ids") or [])
    limit = int(args.get("limit", 200))
    photos = res.get("photos") or {}
    keys = {"file": "file", "t": "captureTime", "r": "rating", "f": "flag", "l": "label", "e": "edited", "w": "width", "h": "height", "kind": "kind", "gps": "gps"}
    out = []
    for pid in ids[:limit]:
        p = photos.get(str(pid)) or photos.get(pid) or {}
        out.append({"id": pid, **{v: p.get(k) for k, v in keys.items() if p.get(k) not in (None, "")}})
    return {"total": len(ids), "returned": len(out), "photos": out}


def _catalog(_: dict) -> dict:
    t = _cmd("library.tree")
    cols = [{k: c[k] for k in ("id", "name", "kind", "count", "parent")} for c in t.get("collections", []) if c["kind"] != "quick"]
    folders = [{k: f[k] for k in ("id", "path", "count", "online")} for f in t.get("folders", [])]
    kws = [{"id": k["id"], "name": k["name"], "count": k["count"], "parent": k["parent"]} for k in t.get("keywords", [])]
    return {"catalog": t.get("catalog"), "folders": folders, "collections": cols, "keywords": kws[:300], "sources": ["all", "folder (id)", "collection (id)", "keyword (id)", "person (id)", "previousImport", "quick", "ids (ids)"]}


def _add_mask(args: dict, shape: dict | None = None) -> dict:
    pid = int(args["id"])
    kind = args.get("kind", "subject")
    shapes = [shape] if shape is not None else []
    if not shapes and (args.get("parts") or kind == "landscape"):
        group = "landscape" if kind == "landscape" else "people"
        shapes = _cmd("develop.aiParts", id=pid, group=group, parts=args.get("parts") or [], person=args.get("person"))["shapes"]
    elif not shapes:
        shapes = [_cmd("develop.aiMask", id=pid, kind=kind, box=args.get("box"))["shape"]]
    empty = [str(s.get("part") or s.get("kind")) for s in shapes if "coverage" in s and float(s["coverage"]) < 0.002]
    shapes = [s for s in shapes if "coverage" not in s or float(s["coverage"]) >= 0.002]
    if not shapes:
        raise CommandError(f"The {', '.join(empty)} mask came out empty: the model found nothing there in this photo, so no mask was added. Try another kind (subject, people, a box with object) or a gradient.", 422)
    shape = shapes[0]
    dev = _cmd("develop.get", id=pid)["settings"]
    masks = list(dev.get("masks") or [])
    mid = max([int(m.get("id", 0)) for m in masks] + [0]) + 1
    masks.append({"id": mid, "name": args.get("name") or f"{str(shape.get('label') or shape.get('kind', 'Mask')).title()} {mid}", "visible": True,
                  "components": [{"shape": s, "op": "add"} for s in shapes], "adjust": args.get("adjust") or {}})
    _cmd("develop.update", ids=[pid], patch={"masks": masks}, label=f"Add {shape.get('kind', 'mask')} mask")
    out = {"id": pid, "mask": mid, "masks": len(masks), "coverage": {str(s.get("part") or s.get("kind")): s["coverage"] for s in shapes if "coverage" in s}}
    if empty:
        out["empty"] = empty
    return out


def _gradient(args: dict) -> dict:
    kind = args.get("kind", "linear")
    if kind == "radial":
        shape = {"kind": "radial", "center": args.get("center") or [0.5, 0.5], "rx": float(args.get("rx", 0.3)), "ry": float(args.get("ry", 0.25)), "angle": float(args.get("angle", 0)),
                 "feather": float(args.get("feather", 50)), "invert": bool(args.get("invert", False))}
    else:
        shape = {"kind": "linear", "start": args.get("start") or [0.5, 0.0], "end": args.get("end") or [0.5, 0.45]}
    return _add_mask(args, shape)


def _snapshot(args: dict) -> Any:
    action = args.get("action")
    if action == "create":
        if args.get("id") is None:
            raise CommandError("snapshot create needs id (the photo) and a name")
        return _cmd("snapshot.create", id=args["id"], name=args.get("name") or "")
    if action == "list":
        if args.get("id") is None:
            raise CommandError("snapshot list needs id (the photo)")
        return _cmd("snapshot.list", id=args["id"])
    if action == "apply":
        if args.get("snapshot") is None:
            raise CommandError("snapshot apply needs snapshot (an id from snapshot list)")
        return _cmd("snapshot.apply", snapshot=args["snapshot"])
    raise CommandError("action is create, list or apply")


def _params(args: dict) -> dict:
    raw = args.get("params", args.get("args"))
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else {}
        except ValueError:
            raise CommandError("params must be an object, for example {\"command\": \"ai.download\", \"params\": {\"model\": \"objects\"}}") from None
    out = dict(raw) if isinstance(raw, dict) else {}
    skip = {"command", "params", "args"} | ({"id"} if not args.get("command") else set())
    for k, v in args.items():
        if k not in skip:
            out.setdefault(k, v)
    return out


def _run_command(args: dict) -> Any:
    cid = str(args.get("command") or args.get("id") or "")
    if cid.split(".")[0] in WINDOW_ONLY:
        raise CommandError(f"{cid} is only available in the formlit window, so a person runs it.", 403)
    if cid in BLOCKED and not ALLOW_DELETE:
        raise CommandError(f"{cid} is only available in the formlit window, so a person confirms it.", 403)
    return dispatch(cid, _params(args))


def _show(args: dict) -> dict:
    events.publish("agent.show", module=args.get("module"), photo=args.get("photo"), source=args.get("source"), message=args.get("message"))
    return {"shown": True, "note": "The formlit window follows when it is open."}


TOOLS: list[tuple[dict, Callable[[dict], Any]]] = [
    (_tool("get_catalog", "The catalog: name and counts, folders (id, path, count), collections (id, name, kind, count) and keywords. Use the ids as find_photos sources.", {}, read=True, idempotent=True), _catalog),
    (_tool("find_photos", "Lists photos: source picks where (kind all, folder, collection, keyword, person, previousImport, quick, ids), filter narrows (text, which also takes field operators such as iso>=3200, rating>=3, camera:x100, lens:35; rating with ratingOp >= <= =, flags [pick reject none], labels, kinds [raw jpeg video...], edited, cameras, lenses, keywords [ids], dates [YYYY or YYYY-MM-DD]), sort orders (by captureTime, importTime, editTime, fileName, rating; desc). Returns ids with file, capture time, rating, flag, label and size.",
           {"source": {"type": "object"}, "filter": {"type": "object"}, "sort": {"type": "object"}, "limit": {"type": "integer", "minimum": 1, "maximum": 5000, "default": 200}}, read=True, idempotent=True), _find),
    (_tool("get_photo", "One photo in full: path, camera, lens, exposure, GPS, metadata, keywords, collections and develop settings.", {"id": ID}, ["id"], read=True, idempotent=True), lambda a: _cmd("photo.get", id=a["id"])),
    (_tool("get_preview", "The photo as developed, as a JPEG image (long side max_size; 512 is enough to judge a look and costs a quarter of 1024). values renders proposed develop values without saving them; preset (an id or name from list_presets) with amount previews a preset before apply_preset; before true shows it with no edits; analyze true adds the compact measurement of the same render.",
           {"id": ID, "max_size": {"type": "integer", "minimum": 64, "maximum": 2048, "default": 768}, "values": {"type": "object", "description": "Develop ids to values, e.g. {\"light.exposure\": 0.5}."},
            "preset": {"type": "string"}, "amount": {"type": "number", "minimum": 0, "maximum": 200, "default": 100}, "before": {"type": "boolean", "default": False}, "analyze": {"type": "boolean", "default": False}}, ["id"], read=True, idempotent=True), _preview),
    (_tool("analyze_photo", "Measures a photo as developed, or with proposed values or a preset without saving: luminance percentiles and tonal zones (blacks, shadows, midtones, highlights, whites), clipping, saturation, colour cast in neutral areas, the share and strength of each colour-mixer band, and findings with suggested develop values. Use it before and after edits instead of judging exposure by eye. Pass ids instead of id for one compact line per photo and the spread across the set.",
           {"id": ID, "ids": IDS, "values": {"type": "object", "description": "Proposed develop ids to values."}, "preset": {"type": "string"}, "amount": {"type": "number", "minimum": 0, "maximum": 200, "default": 100}}, [], read=True, idempotent=True),
     lambda a: _cmd("develop.analyze", id=a.get("id"), ids=a.get("ids") if a.get("id") is None else None, values=a.get("values"), preset=a.get("preset"), amount=a.get("amount", 100))),
    (_tool("match_look", "Matches photos to a reference photo's look in one call: measures the reference as developed, then adjusts each target's exposure, contrast, highlights, shadows, whites, blacks, saturation, white balance and colour-mixer saturation and luminance over several internal render rounds until tone and colour converge. Returns the changes and the distance before and after. Use it when the person points at an example (\"make these look like this one\") or to make a set consistent; then add creative grading or masks.",
           {"ids": IDS, "reference": ID, "strength": {"type": "number", "minimum": 0, "maximum": 100, "default": 100}, "tone": {"type": "boolean", "default": True}, "color": {"type": "boolean", "default": True},
            "apply": {"type": "boolean", "default": True, "description": "false returns the proposal without saving."}, "report": REPORT}, ["ids", "reference"]),
     lambda a: _report(a, _cmd("develop.match", ids=a["ids"], reference=a["reference"], strength=a.get("strength", 100), tone=a.get("tone", True), color=a.get("color", True), apply=a.get("apply", True)), a["ids"])),
    (_tool("import_photos", "Adds photos from folders or files (absolute paths) to the catalog the way working photographers ingest: mode add keeps them in place, copy or move put them under destination, dng copies as DNG. folderTemplate builds the folders (default {date:%Y}/{date:%Y-%m-%d}); renameTemplate renames files with tokens {custom} {shoot} {date:%Y%m%d} {seq:4} {name} {camera} {iso}; metadata applies a copyright preset to every file ({\"copyright\": ..., \"creator\": ..., \"city\": ...}); develop applies a preset id at import; backup makes a second copy in another folder; buildPreviews standard or 1:1; collection adds them to a collection id.",
           {"paths": {"type": "array", "items": {"type": "string"}}, "mode": {"type": "string", "enum": ["add", "copy", "move", "dng"], "default": "add"}, "destination": {"type": "string"},
            "folderTemplate": {"type": "string"}, "renameTemplate": {"type": "string"}, "custom": {"type": "string"}, "metadata": {"type": "object"}, "develop": {"type": "string"},
            "keywords": {"type": "array", "items": {"type": "string"}}, "collection": {"type": "integer"}, "backup": {"type": "string"}, "skipDuplicates": {"type": "boolean", "default": True},
            "buildPreviews": {"type": "string", "enum": ["", "standard", "1:1"]}, "smartPreviews": {"type": "boolean", "default": False}}, ["paths"]),
     lambda a: _cmd("library.import", paths=a["paths"], mode=a.get("mode", "add"), destination=a.get("destination") or "", keywords=a.get("keywords"), wait=True,
                    **{k: a[k] for k in ("folderTemplate", "renameTemplate", "custom", "metadata", "develop", "collection", "backup", "skipDuplicates", "buildPreviews", "smartPreviews") if k in a})),
    (_tool("refine_photos", "Lightroom's Refine Photos for a multi-pass cull: unflagged photos become rejects and picks become unflagged, so the next pass sees only the survivors. Rejects stay rejects; nothing is deleted.",
           {"ids": IDS}, ["ids"]), lambda a: _cmd("library.refine", ids=a["ids"])),
    (_tool("match_exposures", "Lightroom's Match Total Exposures: evens out the brightness of a run of photos of the same scene to the first id (the best-exposed frame), using their exposure metadata. For bracket sets and uneven series; match_look also matches colour.",
           {"ids": IDS, "report": REPORT}, ["ids"]), lambda a: _report(a, _cmd("develop.matchExposure", ids=a["ids"]), a["ids"])),
    (_tool("virtual_copy", "Makes virtual copies (catalog-only versions that share the original file) for alternate edits such as colour and black and white, or another crop; returns the new ids.",
           {"ids": IDS, "name": {"type": "string"}}, ["ids"]), lambda a: _cmd("photo.virtualCopy", ids=a["ids"], name=a.get("name"))),
    (_tool("snapshot", "Named develop states inside one photo: action create saves the current settings under name, list shows them, apply restores one by its id.",
           {"action": {"type": "string", "enum": ["create", "list", "apply"]}, "id": ID, "name": {"type": "string"}, "snapshot": {"type": "integer"}}, ["action"]),
     lambda a: _snapshot(a)),
    (_tool("set_rating", "Sets star ratings, 0 to 5.", {"ids": IDS, "rating": {"type": "integer", "minimum": 0, "maximum": 5}}, ["ids", "rating"], idempotent=True), lambda a: _cmd("photo.rate", ids=a["ids"], rating=a["rating"])),
    (_tool("set_flag", "Flags photos as pick, reject or none.", {"ids": IDS, "flag": {"type": "string", "enum": ["pick", "reject", "none"]}}, ["ids", "flag"], idempotent=True), lambda a: _cmd("photo.flag", ids=a["ids"], flag=a["flag"])),
    (_tool("set_label", "Sets colour labels.", {"ids": IDS, "label": {"type": "string", "enum": ["red", "yellow", "green", "blue", "purple", "none"]}}, ["ids", "label"], idempotent=True), lambda a: _cmd("photo.label", ids=a["ids"], label=a["label"])),
    (_tool("add_keywords", "Adds keywords; a | separates levels (Places|France|Paris).", {"ids": IDS, "keywords": {"type": "array", "items": {"type": "string"}}}, ["ids", "keywords"], idempotent=True), lambda a: _cmd("photo.addKeywords", ids=a["ids"], keywords=a["keywords"])),
    (_tool("set_metadata", "Sets IPTC fields: title, caption, headline, creator, copyright, location, city, state, country and the rest of the Metadata panel.", {"ids": IDS, "fields": {"type": "object"}}, ["ids", "fields"], idempotent=True), lambda a: _cmd("photo.setMeta", ids=a["ids"], fields=a["fields"])),
    (_tool("set_location", "Sets GPS coordinates (decimal degrees), or clears them when lat and lon are left out.", {"ids": IDS, "lat": {"type": "number"}, "lon": {"type": "number"}}, ["ids"], idempotent=True), lambda a: _cmd("photo.setGps", ids=a["ids"], lat=a.get("lat"), lon=a.get("lon"))),
    (_tool("create_collection", "Makes a collection holding the photos; returns its id.", {"name": {"type": "string"}, "ids": IDS}, ["name"]), lambda a: _cmd("collection.create", name=a["name"], ids=a.get("ids") or [])),
    (_tool("add_to_collection", "Adds photos to a collection by id.", {"collection": {"type": "integer"}, "ids": IDS}, ["collection", "ids"], idempotent=True), lambda a: _cmd("collection.addPhotos", id=a["collection"], ids=a["ids"])),
    (_tool("stack_photos", "Stacks photos together, the first on top.", {"ids": IDS}, ["ids"]), lambda a: _cmd("stack.group", ids=a["ids"])),
    (_tool("analyze_culling", "Scores sharpness and exposure, finds faces when the faces model is installed, and groups near-duplicates. Writes the scores; changes no flags.", {"ids": IDS, "wait": WAIT}, ["ids"]), lambda a: _cmd("cull.analyze", ids=a["ids"], wait=a.get("wait", True))),
    (_tool("apply_culling", "After analyze_culling: pickBest flags the best of each group as a pick; rejectBlurry and rejectDuplicates flag the rest as rejects.",
           {"ids": IDS, "pickBest": {"type": "boolean", "default": True}, "rejectBlurry": {"type": "boolean", "default": False}, "rejectDuplicates": {"type": "boolean", "default": False},
            "threshold": {"type": "number", "minimum": 0, "maximum": 100, "default": 35, "description": "Sharpness score under which rejectBlurry rejects."}}, ["ids"]),
     lambda a: _cmd("cull.apply", ids=a["ids"], pickBest=a.get("pickBest", True), rejectBlurry=a.get("rejectBlurry", False), rejectDuplicates=a.get("rejectDuplicates", False), threshold=a.get("threshold", 35))),
    (_tool("find_faces", "Finds faces in the photos (all when ids is left out) and groups them by person.", {"ids": IDS, "wait": WAIT}), lambda a: _cmd("ai.findFaces", ids=a.get("ids"), all=not a.get("ids"), wait=a.get("wait", True))),
    (_tool("list_people", "Named people with counts, and unnamed face groups with their face and photo ids.", {}, read=True, idempotent=True), lambda a: _cmd("people.list")),
    (_tool("name_person", "Names a group of faces (face ids from list_people); adds a People keyword to their photos.", {"faces": {"type": "array", "items": {"type": "integer"}}, "name": {"type": "string"}}, ["faces", "name"]), lambda a: _cmd("people.name", faces=a["faces"], name=a["name"])),
    (_tool("get_develop_controls", "Every develop setting id with its label, range and default, the local (mask) adjustment ids, white balance presets and crop aspects.", {}, read=True, idempotent=True), lambda a: _cmd("develop.controls")),
    (_tool("get_develop", "A photo's develop settings and their effective values.", {"id": ID}, ["id"], read=True, idempotent=True), lambda a: _cmd("develop.get", id=a["id"])),
    (_tool("develop_set", "Sets develop values on photos in one undo step: values maps ids from get_develop_controls to numbers (send every change together rather than one call per slider); delta true adds to the current values; report true returns the measurement after the change.",
           {"ids": IDS, "values": {"type": "object"}, "delta": {"type": "boolean", "default": False}, "report": REPORT}, ["ids", "values"]),
     lambda a: _report(a, _cmd("develop.set", ids=a["ids"], values=a["values"], delta=a.get("delta", False)), a["ids"])),
    (_tool("develop_patch", "Merges a nested develop object into the photos' settings: treatment (\"color\" or \"bw\"), crop (rect [x0,y0,x1,y1] 0 to 1, angle), geometry, masks, curve points. Plain numbers such as grading.shadows.hue go through develop_set.", {"ids": IDS, "patch": {"type": "object"}, "label": {"type": "string"}, "report": REPORT}, ["ids", "patch"]),
     lambda a: _report(a, _cmd("develop.update", ids=a["ids"], patch=a["patch"], label=a.get("label") or "Agent edit"), a["ids"])),
    (_tool("auto_tone", "Auto exposure, contrast, highlights, shadows, whites and blacks, like the Auto button.", {"ids": IDS}, ["ids"]), lambda a: _cmd("develop.auto", ids=a["ids"])),
    (_tool("auto_white_balance", "Auto white balance.", {"ids": IDS}, ["ids"]), lambda a: _cmd("develop.autoWhiteBalance", ids=a["ids"])),
    (_tool("reset_develop", "Resets develop settings to defaults (undoable).", {"ids": IDS}, ["ids"], destructive=True), lambda a: _cmd("develop.reset", ids=a["ids"])),
    (_tool("list_presets", "Develop presets with ids for apply_preset, each with its group, a description of what it does and what it suits, and tags. query (for example \"moody forest\", \"portrait warm\", \"bw street\") and group narrow the list.",
           {"query": {"type": "string"}, "group": {"type": "string"}}, read=True, idempotent=True), lambda a: _cmd("preset.list", query=a.get("query"), group=a.get("group"))),
    (_tool("apply_preset", "Applies a develop preset at an amount (0 to 200 percent).", {"ids": IDS, "preset": {"type": "string"}, "amount": {"type": "number", "minimum": 0, "maximum": 200, "default": 100}, "report": REPORT}, ["ids", "preset"]),
     lambda a: _report(a, _cmd("preset.apply", ids=a["ids"], preset=a["preset"], amount=a.get("amount", 100)), a["ids"])),
    (_tool("save_preset", "Saves a photo's current develop settings as a user preset the person can apply in the window and that list_presets returns. groups limits what it stores (whiteBalance, basicTone, presence, toneCurve, colorMixer, bwMix, treatment, colorGrading, detail, effects, calibration, profile, masks); by default everything but crop, masks, spots and red eye.",
           {"id": ID, "name": {"type": "string"}, "group": {"type": "string", "default": "User Presets"}, "groups": {"type": "array", "items": {"type": "string"}}}, ["id", "name"]),
     lambda a: _cmd("preset.create", id=a["id"], name=a["name"], group=a.get("group") or "User Presets", groups=a.get("groups"))),
    (_tool("sync_settings", "Copies develop settings from one photo to others, limited to groups when given (whiteBalance, basicTone, presence, toneCurve, colorMixer, pointColor, bwMix, treatment, colorGrading, detail, lensCorrections, transform, effects, calibration, profile, crop, masks, spots, redEye, lensBlur); with no groups, everything but crop, masks, spots and red eye.",
           {"from": ID, "ids": IDS, "groups": {"type": "array", "items": {"type": "string"}}, "report": REPORT}, ["from", "ids"]),
     lambda a: _report(a, _cmd("develop.sync", ids=a["ids"], **{"from": a["from"]}, groups=a.get("groups")), a["ids"])),
    (_tool("add_ai_mask", "Adds a local adjustment through an AI mask: sky, subject, background, people, object (with box [x0,y0,x1,y1] 0 to 1), depth, or parts: kind people with parts (faceSkin, bodySkin, eyebrows, sclera, iris, lips, teeth, hair, clothes; person for one person by index) or kind landscape with parts (sky, water, vegetation, mountains, architecture, naturalGround, artificialGround), several parts in one mask. adjust uses local ids: exposure, contrast, highlights, shadows, whites, blacks, temp, tint, hue, saturation, texture, clarity, dehaze, sharpness, noise, plus a local colour grade: colorHue (0 to 359) with colorSat (0 to 100) tints the masked area, and curve ({\"master\"|\"red\"|\"green\"|\"blue\": [[x, y], ...]}, 0 to 1) is a local tone curve. To grade a subject and its background differently, add a subject mask and a background mask with different adjust values. The result reports each mask's coverage of the frame; an empty mask is refused. Each kind runs a local model (subject and background: U2-Net; people: U2-Net human segmentation; face, hair, eye, lip and teeth parts also need the YuNet face model; sky: the sky segmenter; object: SAM 2.1; depth: Depth Anything V2); a refusal names the exact install call.",
           {"id": ID, "kind": {"type": "string", "enum": ["sky", "subject", "background", "people", "object", "depth", "landscape"]}, "parts": {"type": "array", "items": {"type": "string"}},
            "person": {"type": "integer"}, "box": {"type": "array", "items": {"type": "number"}}, "adjust": {"type": "object"}, "name": {"type": "string"}}, ["id", "kind"]), _add_mask),
    (_tool("add_gradient_mask", "Adds a linear gradient (start and end points, 0 to 1 of the frame) or a radial gradient (center, rx, ry, feather, invert) with local adjust values.",
           {"id": ID, "kind": {"type": "string", "enum": ["linear", "radial"]}, "start": {"type": "array", "items": {"type": "number"}}, "end": {"type": "array", "items": {"type": "number"}},
            "center": {"type": "array", "items": {"type": "number"}}, "rx": {"type": "number"}, "ry": {"type": "number"}, "feather": {"type": "number"}, "invert": {"type": "boolean"}, "adjust": {"type": "object"}}, ["id", "kind"]), _gradient),
    (_tool("auto_straighten", "Levels the horizon from the lines in the photo.", {"ids": IDS}, ["ids"]), _straighten),
    (_tool("upright", "Perspective correction: auto, level, vertical or full.", {"ids": IDS, "mode": {"type": "string", "enum": ["auto", "level", "vertical", "full", "off"]}}, ["ids", "mode"]), lambda a: _cmd("develop.upright", ids=a["ids"], mode=a["mode"])),
    (_tool("denoise", "AI Denoise: writes an enhanced DNG next to each raw and stacks it.", {"ids": IDS, "amount": {"type": "number", "minimum": 0, "maximum": 100, "default": 50}, "wait": WAIT}, ["ids"]),
     lambda a: _cmd("ai.denoise", ids=a["ids"], amount=a.get("amount", 50), wait=a.get("wait", True))),
    (_tool("super_resolution", "Doubles the resolution into an enhanced DNG, stacked with the original.", {"ids": IDS, "wait": WAIT}, ["ids"]), lambda a: _cmd("ai.superResolution", ids=a["ids"], wait=a.get("wait", True))),
    (_tool("merge_hdr", "Merges bracketed exposures into an HDR DNG, stacked with the brackets.", {"ids": IDS, "deghost": {"type": "string", "enum": ["off", "low", "medium", "high"], "default": "off"}, "wait": WAIT}, ["ids"]),
     lambda a: _cmd("ai.hdrMerge", ids=a["ids"], deghost=a.get("deghost", "off"), wait=a.get("wait", True))),
    (_tool("merge_panorama", "Stitches overlapping photos into a panorama DNG.", {"ids": IDS, "projection": {"type": "string", "enum": ["spherical", "cylindrical", "plane"], "default": "spherical"}, "wait": WAIT}, ["ids"]),
     lambda a: _cmd("ai.panoMerge", ids=a["ids"], projection=a.get("projection", "spherical"), wait=a.get("wait", True))),
    (_tool("list_export_presets", "Export presets (id and name) and the last export's settings.", {}, read=True, idempotent=True), lambda a: _cmd("export.presets")),
    (_tool("export_photos", "Exports photos to files: a preset id (builtin.web, builtin.full, builtin.tiff, builtin.print, builtin.original, builtin.dng or a user preset) and/or settings (destination.folder absolute path, file.format jpeg png tiff webp avif heic dng original, file.quality, size.resize with size.mode long and size.value, sharpen, metadata.include, watermark). Returns the written paths.",
           {"ids": IDS, "preset": {"type": "string"}, "settings": {"type": "object"}, "folder": {"type": "string", "description": "Absolute output folder; shorthand for settings.destination.folder."}}, ["ids"]),
     lambda a: _cmd("export.run", ids=a["ids"], preset=a.get("preset"), settings={**(a.get("settings") or {}), **({"destination": {**((a.get("settings") or {}).get("destination") or {}), "folder": a["folder"]}} if a.get("folder") else {})}, wait=True)),
    (_tool("print_pdf", "Lays photos out for print (settings as the Print module: paper, orientation, rows, cols, margins, style grid or package, fill, caption) and writes a PDF; path optional.",
           {"ids": IDS, "settings": {"type": "object"}, "path": {"type": "string"}}, ["ids"]), lambda a: _cmd("print.run", ids=a["ids"], settings=a.get("settings") or {}, output="pdf", path=a.get("path"), name="Print", wait=True)),
    (_tool("make_book", "Auto-lays out the photos as a book (size, title) and writes a PDF.", {"ids": IDS, "title": {"type": "string"}, "size": {"type": "string", "default": "standard-landscape"}, "path": {"type": "string"}}, ["ids"]), lambda a: _book(a)),
    (_tool("export_slideshow", "Writes a slideshow of the photos as MP4 (needs ffmpeg) or PDF; settings as the Slideshow module (duration, fade, panZoom, fill, music.path).",
           {"ids": IDS, "format": {"type": "string", "enum": ["mp4", "pdf"], "default": "mp4"}, "settings": {"type": "object"}, "path": {"type": "string"}}, ["ids"]),
     lambda a: _cmd("slideshow.export", ids=a["ids"], format=a.get("format", "mp4"), settings=a.get("settings") or {}, path=a.get("path"), wait=True)),
    (_tool("export_web_gallery", "Writes a web gallery folder (index.html plus images); settings as the Web module (site.title, layout, colors).", {"ids": IDS, "settings": {"type": "object"}, "folder": {"type": "string"}}, ["ids"]),
     lambda a: _cmd("web.export", ids=a["ids"], settings=a.get("settings") or {}, folder=a.get("folder"), wait=True)),
    (_tool("publish", "Publishes a published collection: new and edited photos go out, removed ones are deleted from the service.", {"collection": {"type": "integer"}}, ["collection"]), lambda a: _cmd("publish.run", collection=a["collection"], wait=True)),
    (_tool("show_in_window", "Shows something in the formlit window if it is open: a module (library, develop, map, book, slideshow, print, web), a photo id, a source like find_photos takes, and a short message for the person.",
           {"module": {"type": "string"}, "photo": {"type": "integer"}, "source": {"type": "object"}, "message": {"type": "string", "maxLength": 200}}, idempotent=True), _show),
    (_tool("undo", "Undoes the last change.", {}), lambda a: _cmd("edit.undo")),
    (_tool("redo", "Redoes the last undone change.", {}), lambda a: _cmd("edit.redo")),
    (_tool("list_commands", "Every engine command (id, group, parameters) for run_command, optionally one group.", {"group": {"type": "string"}}, read=True, idempotent=True),
     lambda a: {"commands": [{k: c[k] for k in ("id", "label", "group", "mutates", "params")} for c in catalogue() if not a.get("group") or c["group"] == a["group"]]}),
    (_tool("run_command", "Runs any engine command by id with its params (see list_commands). Deleting files and switching catalogs stay in the window.", {"command": {"type": "string"}, "params": {"type": "object"}}, ["command"]), _run_command),
    (_tool("get_agent_access", "Whether outside agents such as Claude may use formlit (outsideAgents: ask, allowed or blocked), which clients have called since formlit started, and whether a call is waiting for the person's answer. Like every tool it is refused while the setting is blocked.", {}, read=True, idempotent=True), lambda a: _cmd("agents.status")),
]


def _book(a: dict) -> dict:
    lay = _cmd("book.autoLayout", ids=a["ids"])
    lay["cover"]["texts"] = [a.get("title") or "Untitled", ""]
    return _cmd("book.export", settings={"size": a.get("size", "standard-landscape"), "cover": lay["cover"], "pages": lay["pages"]}, format="pdf", path=a.get("path"), name=a.get("title") or "Book", wait=True)


SPECS = {t[0]["name"]: t for t in TOOLS}


def _local_origin(origin: str | None) -> bool:
    if not origin:
        return True
    host = urllib.parse.urlparse(origin).hostname or ""
    return host in ("localhost", "127.0.0.1", "::1", "tauri.localhost") or origin.startswith("tauri://")


def _client_name(info: Any) -> str:
    if not isinstance(info, dict):
        return ""
    return str(info.get("title") or info.get("name") or "").strip()[:80]


def _open_session(client: str) -> str:
    sid = uuid.uuid4().hex
    SESSIONS[sid] = client
    while len(SESSIONS) > MAX_SESSIONS:
        SESSIONS.pop(next(iter(SESSIONS)))
    return sid


def _caller(request: Request, params: dict) -> tuple[str, str]:
    if request.headers.get("x-formlit-inapp", "") == agents.INAPP_TOKEN:
        return agents.INAPP_CLIENT, "inapp"
    header = request.headers.get("x-formlit-agent", "").strip()
    if header:
        return header[:80], "stdio"
    meta = params.get("_meta")
    named = _client_name(meta.get("io.modelcontextprotocol/clientInfo") if isinstance(meta, dict) else None)
    return named or SESSIONS.get(request.headers.get("mcp-session-id", ""), ""), "http"


def _ok(req_id, result: dict, modern: bool) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": {**result, **({"resultType": "complete"} if modern else {})}}


def _err(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _result(value: Any) -> dict:
    if isinstance(value, dict) and "__image" in value:
        return {"content": [{"type": "image", "data": value["__image"], "mimeType": "image/jpeg"}, {"type": "text", "text": json.dumps(value.get("meta") or {})}], "structuredContent": value.get("meta") or {}}
    data = value if isinstance(value, dict) else {"result": value}
    text = json.dumps(data, default=str)
    if len(text) > 200_000:
        text = text[:200_000] + " ... (truncated: narrow the request)"
    return {"content": [{"type": "text", "text": text}], "structuredContent": data}


async def call_tool(name: str, args: dict, client: str = "", channel: str = "http") -> dict:
    tool, fn = SPECS[name]
    try:
        await agents.require(client, channel)
    except CommandError as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    events.publish("agent.activity", tool=name, label=tool["description"].split(".")[0][:80])
    try:
        value = await asyncio.to_thread(fn, args)
    except CommandError as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    except KeyError as exc:
        return {"content": [{"type": "text", "text": f"Missing argument {exc}."}], "isError": True}
    except Exception as exc:
        return {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}], "isError": True}
    return _result(value)


@router.post("/mcp")
async def mcp(request: Request) -> Response:
    if not _local_origin(request.headers.get("origin")):
        return Response(status_code=403, content=json.dumps(_err(None, -32600, "Origin not allowed")), media_type="application/json")
    try:
        msg = json.loads(await request.body())
    except ValueError:
        return Response(content=json.dumps(_err(None, -32700, "Parse error")), media_type="application/json", status_code=400)
    if isinstance(msg, list):
        return Response(content=json.dumps(_err(None, -32600, "Batches are not supported")), media_type="application/json", status_code=400)
    if not isinstance(msg, dict):
        return Response(content=json.dumps(_err(None, -32600, "Invalid request: expected a JSON-RPC object")), media_type="application/json", status_code=400)
    req_id, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if req_id is None:
        return Response(status_code=202)
    if not isinstance(params, dict):
        return Response(content=json.dumps(_err(req_id, -32602, "params must be an object")), media_type="application/json")
    meta = params.get("_meta") or {}
    version = meta.get("io.modelcontextprotocol/protocolVersion") or request.headers.get("mcp-protocol-version") or "2025-11-25"
    modern = version == "2026-07-28"
    server = {"name": "formlit", "version": __version__}
    caps = {"tools": {}, "prompts": {}}
    headers: dict[str, str] = {}
    if version not in VERSIONS and method != "initialize":
        out = _err(req_id, -32602, f"Unsupported protocol version {version}; supported: {', '.join(VERSIONS)}")
    elif method == "server/discover":
        out = _ok(req_id, {"supportedVersions": VERSIONS, "capabilities": caps, "_meta": {"io.modelcontextprotocol/serverInfo": server}, "instructions": INSTRUCTIONS}, True)
    elif method == "initialize":
        asked = params.get("protocolVersion")
        out = _ok(req_id, {"protocolVersion": asked if asked in VERSIONS else "2025-11-25", "capabilities": caps, "serverInfo": server, "instructions": INSTRUCTIONS}, False)
        named = _client_name(params.get("clientInfo"))
        if named:
            headers["Mcp-Session-Id"] = _open_session(named)
    elif method == "ping":
        out = _ok(req_id, {}, modern)
    elif method == "prompts/list":
        out = _ok(req_id, {"prompts": PROMPTS, **(LIST_CACHE if modern else {})}, modern)
    elif method == "prompts/get":
        text = {"culling_workflow": CULLING, "develop_strategy": DEVELOP, **{k: v["text"] for k, v in WORKFLOWS.items()}}.get(params.get("name") if isinstance(params.get("name"), str) else "")
        out = _ok(req_id, {"description": next(p["description"] for p in PROMPTS if p["name"] == params.get("name")), "messages": [{"role": "user", "content": {"type": "text", "text": text}}]}, modern) if text else _err(req_id, -32602, f"No prompt named {params.get('name')}")
    elif method == "tools/list":
        out = _ok(req_id, {"tools": [t[0] for t in TOOLS], **(LIST_CACHE if modern else {})}, modern)
    elif method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        if not isinstance(name, str) or not isinstance(args, dict):
            out = _err(req_id, -32602, "tools/call needs a tool name and an arguments object")
        else:
            client, channel = _caller(request, params)
            out = _ok(req_id, await call_tool(name, args, client, channel), modern) if name in SPECS else _err(req_id, -32602, f"No tool named {name}")
    else:
        out = _err(req_id, -32601, f"Method not found: {method}")
    return Response(content=json.dumps(out, default=str), media_type="application/json", headers=headers)


@router.get("/api/mcp/status")
def status() -> dict:
    return {"endpoint": f"http://127.0.0.1:{config.BACKEND_PORT}/mcp", "tools": len(TOOLS), "commands": len(REGISTRY), "versions": VERSIONS, "deleteAllowed": ALLOW_DELETE}
