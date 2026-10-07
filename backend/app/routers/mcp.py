import asyncio
import base64
import io
import json
import os
import urllib.parse
from typing import Any, Callable

from fastapi import APIRouter, Request, Response

from app import __version__
from app.core import config
from app.engine import catalog as catalog_mod
from app.engine import events
from app.engine.commands import REGISTRY, CommandError, catalogue, dispatch

router = APIRouter()
VERSIONS = ["2026-07-28", "2025-11-25"]
INSTRUCTIONS = ("formlit is a photo library and raw developer running on this computer, a Lightroom alternative. Every tool works on its catalog "
                "with or without the window open, and every change is one undoable step (undo). Start with get_catalog, then find_photos to get "
                "photo ids. Look with get_preview before and after developing. Develop values use dotted ids from get_develop_controls (for "
                "example light.exposure, color.vibrance, effects.clarity); pass delta true to nudge. Long jobs (import, AI, export) wait until done. For a full "
                "plan, get the culling_workflow or develop_strategy prompt. run_command reaches every engine command listed by list_commands.")
CULLING = """How to cull a shoot in formlit.

1. find_photos with source {"kind": "previousImport"} (or a folder id from get_catalog) lists the shoot.
2. analyze_culling scores sharpness, exposure, faces and groups near-duplicates; it writes nothing visible.
3. apply_culling with pickBest true flags the best frame of each group of near-duplicates as a pick; rejectBlurry rejects frames whose sharpness score is under the threshold (35 by default) and rejectDuplicates rejects the rest of each group. Check a few with get_preview.
4. set_flag, set_rating and set_label adjust by hand. Ratings 0 to 5, flags pick, reject or none.
5. find_photos with filter {"flags": ["pick"]} gives the selects; create_collection with those ids keeps them together.
6. Nothing is deleted. Rejected photos stay in the catalog until a person removes them in the window.
"""
DEVELOP = """How to develop a photo in formlit.

1. get_photo tells you the camera, lens, exposure and current settings; get_preview shows it (long side up to 2048).
2. auto_tone gives a balanced starting point; develop_set refines. Basic ids: wb.temp, wb.tint, light.exposure, light.contrast, light.highlights, light.shadows, light.whites, light.blacks, effects.texture, effects.clarity, effects.dehaze, color.vibrance, color.saturation. get_develop_controls lists every id with its range.
3. Preview a change before committing: get_preview with values renders the proposal without saving it.
4. Local edits: add_ai_mask with kind sky, subject, background, people or depth and an adjust object (exposure, contrast, highlights, shadows, temp, tint, saturation, clarity, dehaze, texture, sharpness, noise). add_gradient_mask adds a linear or radial mask.
5. Presets: list_presets then apply_preset with an amount. sync_settings copies one photo's look to others, by group (whiteBalance, basicTone, presence, toneCurve, colorMixer, colorGrading, treatment, detail, lensCorrections, transform, effects, calibration, profile, crop, masks); with no groups it copies everything except crop, masks, spots and red eye.
6. Geometry: auto_straighten levels the horizon; upright applies auto, level, vertical or full perspective correction.
7. Check with get_preview after every step; undo steps back one change.
8. Deliver with export_photos (a preset such as builtin.web, or settings) to an absolute folder.
"""
PROMPTS = [
    {"name": "culling_workflow", "title": "Cull a shoot", "description": "Score, group, pick and reject a shoot with formlit's tools.", "arguments": []},
    {"name": "develop_strategy", "title": "Develop a photo", "description": "The order formlit's develop tools work best in, with the setting ids.", "arguments": []},
]
ALLOW_DELETE = os.environ.get("FORMLIT_MCP_ALLOW_DELETE") == "1"
BLOCKED = {"photo.delete", "folder.remove", "library.newCatalog", "library.openCatalog"}


def _tool(name: str, description: str, props: dict, required: list[str] | None = None, **hints: bool) -> dict:
    return {"name": name, "description": description, "inputSchema": {"type": "object", "properties": props, "required": required or [], "additionalProperties": False},
            "annotations": {"readOnlyHint": hints.get("read", False), "destructiveHint": hints.get("destructive", False), "idempotentHint": hints.get("idempotent", False), "openWorldHint": False}}


IDS = {"type": "array", "items": {"type": "integer"}, "description": "Photo ids from find_photos."}
ID = {"type": "integer", "description": "A photo id from find_photos."}
WAIT = {"type": "boolean", "default": True, "description": "Wait for the job to finish (default) or return its task id."}


def _cmd(cid: str, **params: Any) -> Any:
    return dispatch(cid, {k: v for k, v in params.items() if v is not None})


def _preview(args: dict) -> dict:
    from PIL import Image
    from app.develop import settings as S
    from app.engine.records import loads
    from app.services import previews
    pid = int(args["id"])
    long = max(64, min(2048, int(args.get("max_size", 1024))))
    dev = None
    if args.get("values") or args.get("before"):
        row = catalog_mod.get().row("SELECT develop FROM photos WHERE id=?", (pid,))
        if row is None:
            raise CommandError(f"No photo with id {pid}", 404)
        dev = {} if args.get("before") else json.loads(json.dumps(loads(row["develop"], {})))
        for k, v in (args.get("values") or {}).items():
            S.put(dev, k, float(v))
    rgb = previews.render_rgb8(pid, long, dev)
    buf = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(buf, "JPEG", quality=88)
    return {"__image": base64.b64encode(buf.getvalue()).decode(), "meta": {"id": pid, "width": int(rgb.shape[1]), "height": int(rgb.shape[0]), "proposed": bool(args.get("values")), "before": bool(args.get("before"))}}


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
    if shape is None:
        got = _cmd("develop.aiMask", id=pid, kind=args.get("kind", "subject"), box=args.get("box"))
        shape = got["shape"]
    dev = _cmd("develop.get", id=pid)["settings"]
    masks = list(dev.get("masks") or [])
    mid = max([int(m.get("id", 0)) for m in masks] + [0]) + 1
    masks.append({"id": mid, "name": args.get("name") or f"{str(shape.get('kind', 'Mask')).title()} {mid}", "visible": True,
                  "components": [{"shape": shape, "op": "add"}], "adjust": args.get("adjust") or {}})
    _cmd("develop.update", ids=[pid], patch={"masks": masks}, label=f"Add {shape.get('kind', 'mask')} mask")
    return {"id": pid, "mask": mid, "masks": len(masks)}


def _gradient(args: dict) -> dict:
    kind = args.get("kind", "linear")
    if kind == "radial":
        shape = {"kind": "radial", "center": args.get("center") or [0.5, 0.5], "rx": float(args.get("rx", 0.3)), "ry": float(args.get("ry", 0.25)), "angle": float(args.get("angle", 0)),
                 "feather": float(args.get("feather", 50)), "invert": bool(args.get("invert", False))}
    else:
        shape = {"kind": "linear", "start": args.get("start") or [0.5, 0.0], "end": args.get("end") or [0.5, 0.45]}
    return _add_mask(args, shape)


def _run_command(args: dict) -> Any:
    cid = str(args.get("command") or "")
    if cid in BLOCKED and not ALLOW_DELETE:
        raise CommandError(f"{cid} is only available in the formlit window, so a person confirms it.", 403)
    return dispatch(cid, args.get("params") or {})


def _show(args: dict) -> dict:
    events.publish("agent.show", module=args.get("module"), photo=args.get("photo"), source=args.get("source"), message=args.get("message"))
    return {"shown": True, "note": "The formlit window follows when it is open."}


TOOLS: list[tuple[dict, Callable[[dict], Any]]] = [
    (_tool("get_catalog", "The catalog: name and counts, folders (id, path, count), collections (id, name, kind, count) and keywords. Use the ids as find_photos sources.", {}, read=True, idempotent=True), _catalog),
    (_tool("find_photos", "Lists photos: source picks where (kind all, folder, collection, keyword, person, previousImport, quick, ids), filter narrows (text, rating with ratingOp >= <= =, flags [pick reject none], labels, kinds [raw jpeg video...], edited, cameras, lenses, keywords [ids], dates [YYYY or YYYY-MM-DD]), sort orders (by captureTime, importTime, editTime, fileName, rating; desc). Returns ids with file, capture time, rating, flag, label and size.",
           {"source": {"type": "object"}, "filter": {"type": "object"}, "sort": {"type": "object"}, "limit": {"type": "integer", "minimum": 1, "maximum": 5000, "default": 200}}, read=True, idempotent=True), _find),
    (_tool("get_photo", "One photo in full: path, camera, lens, exposure, GPS, metadata, keywords, collections and develop settings.", {"id": ID}, ["id"], read=True, idempotent=True), lambda a: _cmd("photo.get", id=a["id"])),
    (_tool("get_preview", "The photo as developed, as a JPEG image (long side max_size). values renders proposed develop values without saving them; before true shows it with no edits.",
           {"id": ID, "max_size": {"type": "integer", "minimum": 64, "maximum": 2048, "default": 1024}, "values": {"type": "object", "description": "Develop ids to values, e.g. {\"light.exposure\": 0.5}."}, "before": {"type": "boolean", "default": False}}, ["id"], read=True, idempotent=True), _preview),
    (_tool("import_photos", "Adds photos from folders or files (absolute paths) to the catalog; mode add keeps them in place, copy or move put them under destination.",
           {"paths": {"type": "array", "items": {"type": "string"}}, "mode": {"type": "string", "enum": ["add", "copy", "move"], "default": "add"}, "destination": {"type": "string"}, "keywords": {"type": "array", "items": {"type": "string"}}}, ["paths"]),
     lambda a: _cmd("library.import", paths=a["paths"], mode=a.get("mode", "add"), destination=a.get("destination"), keywords=a.get("keywords"), wait=True)),
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
    (_tool("develop_set", "Sets develop values on photos: values maps ids from get_develop_controls to numbers; delta true adds to the current values.",
           {"ids": IDS, "values": {"type": "object"}, "delta": {"type": "boolean", "default": False}}, ["ids", "values"]), lambda a: _cmd("develop.set", ids=a["ids"], values=a["values"], delta=a.get("delta", False))),
    (_tool("develop_patch", "Merges a nested develop object into the photos' settings: treatment (\"color\" or \"bw\"), crop (rect [x0,y0,x1,y1] 0 to 1, angle), geometry, masks, curve points. Plain numbers such as grading.shadows.hue go through develop_set.", {"ids": IDS, "patch": {"type": "object"}, "label": {"type": "string"}}, ["ids", "patch"]),
     lambda a: _cmd("develop.update", ids=a["ids"], patch=a["patch"], label=a.get("label") or "Agent edit")),
    (_tool("auto_tone", "Auto exposure, contrast, highlights, shadows, whites and blacks, like the Auto button.", {"ids": IDS}, ["ids"]), lambda a: _cmd("develop.auto", ids=a["ids"])),
    (_tool("auto_white_balance", "Auto white balance.", {"ids": IDS}, ["ids"]), lambda a: _cmd("develop.autoWhiteBalance", ids=a["ids"])),
    (_tool("reset_develop", "Resets develop settings to defaults (undoable).", {"ids": IDS}, ["ids"], destructive=True), lambda a: _cmd("develop.reset", ids=a["ids"])),
    (_tool("list_presets", "Develop presets by group, with ids for apply_preset.", {}, read=True, idempotent=True), lambda a: _cmd("preset.list")),
    (_tool("apply_preset", "Applies a develop preset at an amount (0 to 200 percent).", {"ids": IDS, "preset": {"type": "string"}, "amount": {"type": "number", "minimum": 0, "maximum": 200, "default": 100}}, ["ids", "preset"]),
     lambda a: _cmd("preset.apply", ids=a["ids"], preset=a["preset"], amount=a.get("amount", 100))),
    (_tool("sync_settings", "Copies develop settings from one photo to others, limited to groups when given (whiteBalance, basicTone, presence, toneCurve, colorMixer, pointColor, bwMix, treatment, colorGrading, detail, lensCorrections, transform, effects, calibration, profile, crop, masks, spots, redEye, lensBlur); with no groups, everything but crop, masks, spots and red eye.",
           {"from": ID, "ids": IDS, "groups": {"type": "array", "items": {"type": "string"}}}, ["from", "ids"]), lambda a: _cmd("develop.sync", ids=a["ids"], **{"from": a["from"]}, groups=a.get("groups"))),
    (_tool("add_ai_mask", "Adds a local adjustment through an AI mask (sky, subject, background, people, object with box [x0,y0,x1,y1] 0 to 1, or depth). adjust uses local ids: exposure, contrast, highlights, shadows, whites, blacks, temp, tint, saturation, texture, clarity, dehaze, sharpness, noise.",
           {"id": ID, "kind": {"type": "string", "enum": ["sky", "subject", "background", "people", "object", "depth"]}, "box": {"type": "array", "items": {"type": "number"}}, "adjust": {"type": "object"}, "name": {"type": "string"}}, ["id", "kind"]), _add_mask),
    (_tool("add_gradient_mask", "Adds a linear gradient (start and end points, 0 to 1 of the frame) or a radial gradient (center, rx, ry, feather, invert) with local adjust values.",
           {"id": ID, "kind": {"type": "string", "enum": ["linear", "radial"]}, "start": {"type": "array", "items": {"type": "number"}}, "end": {"type": "array", "items": {"type": "number"}},
            "center": {"type": "array", "items": {"type": "number"}}, "rx": {"type": "number"}, "ry": {"type": "number"}, "feather": {"type": "number"}, "invert": {"type": "boolean"}, "adjust": {"type": "object"}}, ["id", "kind"]), _gradient),
    (_tool("auto_straighten", "Levels the horizon from the lines in the photo.", {"ids": IDS}, ["ids"]), lambda a: _cmd("develop.autoStraighten", ids=a["ids"])),
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


async def call_tool(name: str, args: dict) -> dict:
    tool, fn = SPECS[name]
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
    req_id, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if req_id is None:
        return Response(status_code=202)
    meta = params.get("_meta") or {}
    version = meta.get("io.modelcontextprotocol/protocolVersion") or request.headers.get("mcp-protocol-version") or "2025-11-25"
    modern = version == "2026-07-28"
    server = {"name": "formlit", "version": __version__}
    caps = {"tools": {}, "prompts": {}}
    if version not in VERSIONS and method != "initialize":
        out = _err(req_id, -32602, f"Unsupported protocol version {version}; supported: {', '.join(VERSIONS)}")
    elif method == "server/discover":
        out = _ok(req_id, {"supportedVersions": VERSIONS, "capabilities": caps, "_meta": {"io.modelcontextprotocol/serverInfo": server}, "instructions": INSTRUCTIONS}, True)
    elif method == "initialize":
        asked = params.get("protocolVersion")
        out = _ok(req_id, {"protocolVersion": asked if asked in VERSIONS else "2025-11-25", "capabilities": caps, "serverInfo": server, "instructions": INSTRUCTIONS}, False)
    elif method == "ping":
        out = _ok(req_id, {}, modern)
    elif method == "prompts/list":
        out = _ok(req_id, {"prompts": PROMPTS}, modern)
    elif method == "prompts/get":
        text = {"culling_workflow": CULLING, "develop_strategy": DEVELOP}.get(params.get("name"))
        out = _ok(req_id, {"description": next(p["description"] for p in PROMPTS if p["name"] == params.get("name")), "messages": [{"role": "user", "content": {"type": "text", "text": text}}]}, modern) if text else _err(req_id, -32602, f"No prompt named {params.get('name')}")
    elif method == "tools/list":
        out = _ok(req_id, {"tools": [t[0] for t in TOOLS]}, modern)
    elif method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        out = _ok(req_id, await call_tool(name, args), modern) if name in SPECS and isinstance(args, dict) else _err(req_id, -32602, f"No tool named {name}")
    else:
        out = _err(req_id, -32601, f"Method not found: {method}")
    return Response(content=json.dumps(out, default=str), media_type="application/json")


@router.get("/api/mcp/status")
def status() -> dict:
    return {"endpoint": f"http://127.0.0.1:{config.BACKEND_PORT}/mcp", "tools": len(TOOLS), "commands": len(REGISTRY), "versions": VERSIONS, "deleteAllowed": ALLOW_DELETE}
