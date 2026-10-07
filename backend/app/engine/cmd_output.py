import bisect
import json
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core import config, prefs
from app.engine import catalog as catalog_mod
from app.engine import tasks
from app.engine.commands import CommandError, command, resolve_ids
from app.engine.records import aspect, loads
from app.output import encode, export, layout, pages, publish, slideshow, web
from app.services import rename


def cat():
    return catalog_mod.get()


def _wait(tid: int, wait: bool) -> dict:
    if not wait:
        return {"task": tid}
    t = tasks.wait(tid, 7200)
    if t and t["state"] == "failed":
        raise CommandError(t["error"] or "Failed")
    return {"task": tid, **((t.get("result") or {}) if t else {})}


def _aspects(ids: list[int]) -> dict[int, float]:
    out = {}
    for r in cat().rows(f"SELECT id, width, height, develop FROM photos WHERE id IN ({','.join('?' * len(ids))})", tuple(ids)) if ids else []:
        out[int(r["id"])] = aspect(int(r["width"] or 1), int(r["height"] or 1), loads(r["develop"], {}))
    return out


def _ids(ids: Any, collection: int | None = None) -> list[int]:
    if collection is not None:
        from app.engine import query
        return [int(i) for i in query.query(cat(), {"kind": "collection", "id": int(collection)}, stacks=False)["ids"]]
    return resolve_ids(ids)


def _out_dir(kind: str) -> Path:
    p = config.exports_dir() / kind
    p.mkdir(parents=True, exist_ok=True)
    return p


def _out_path(kind: str, name: str, ext: str, path: str | None) -> Path:
    if path:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    return rename.unique(_out_dir(kind) / f"{rename.safe(name or kind)}.{ext}")


@command("export.options", "Export Options", mutates=False)
def export_options() -> dict:
    import importlib.util
    formats = dict(encode.FORMATS)
    if importlib.util.find_spec("pillow_heif") is None:
        formats.pop("heic", None)
    return {"formats": formats, "spaces": encode.SPACES, "metadata": encode.METADATA, "tokens": rename.TOKENS, "defaults": export.merged({}),
            "anchors": list(export.ANCHORS), "ffmpeg": bool(shutil.which("ffmpeg"))}


@command("export.presets", "Export Presets", mutates=False)
def export_presets() -> dict:
    return {"presets": export.list_presets(), "previous": cat().get_meta("lastExport", None)}


@command("export.savePreset", "Save Export Preset", {"name": {"type": "string"}, "settings": {"type": "object"}})
def export_save_preset(name: str, settings: dict) -> dict:
    if not name.strip():
        raise CommandError("A preset needs a name")
    return export.save_preset(name.strip(), settings)


@command("export.deletePreset", "Delete Export Preset", {"id": {"type": "string"}})
def export_delete_preset(id: str) -> dict:
    if not export.delete_preset(id):
        raise CommandError("Only your own presets can be deleted")
    return {"deleted": id}


@command("export.run", "Export", {"ids": {"type": "array"}, "settings": {"type": "object"}, "preset": {"type": "string"}, "wait": {"type": "boolean"}})
def export_run(ids: Any = None, settings: dict | None = None, preset: str | None = None, wait: bool = False) -> dict:
    pids = resolve_ids(ids)
    s: dict = {}
    if preset:
        p = export.find_preset(preset)
        if p is None:
            raise CommandError(f"No export preset {preset}")
        s = layout.deep_merge(s, p["settings"])
    s = layout.deep_merge(s, settings or {})
    with cat().change("Export", undoable=False) as ch:
        ch.set_meta("lastExport", s)

    def job(progress):
        res = export.run(pids, s, progress)
        post = res["settings"]["post"]
        paths = [Path(p) for p in res["paths"]]
        if res["settings"]["destination"].get("addToCatalog") and paths:
            from app.services import importer
            imp = importer.import_files([str(p) for p in paths], "add", "", "", "", "", None, None, None, None, False, False)
            res["imported"] = imp.get("ids", [])
            if res["settings"]["destination"].get("stack"):
                from app.engine.cmd_library import stack_group
                for new, src in zip(res["imported"], pids):
                    try:
                        stack_group([int(new), int(src)])
                    except CommandError:
                        continue
        if paths and post.get("action") == "reveal":
            export.reveal(paths[0])
        elif paths and post.get("action") == "open" and post.get("app"):
            export.open_with(post["app"], paths)
        res.pop("settings", None)
        return res
    return _wait(tasks.start("export", f"Exporting {len(pids)} {'photo' if len(pids) == 1 else 'photos'}", job), wait)


@command("export.previous", "Export with Previous", {"ids": {"type": "array"}, "wait": {"type": "boolean"}})
def export_previous(ids: Any = None, wait: bool = False) -> dict:
    last = cat().get_meta("lastExport", None)
    if not last:
        raise CommandError("Nothing has been exported yet")
    return export_run(ids, last, None, wait)


def _known_editors() -> list[dict]:
    found = []
    cands = {"darwin": ["/Applications/formvis.app"], "win32": [os.path.expandvars(r"%LOCALAPPDATA%\Programs\formvis\formvis.exe"), r"C:\Program Files\formvis\formvis.exe"]}.get(sys.platform, [])
    for c in cands:
        if Path(c).exists():
            found.append({"name": "formvis", "path": c})
    which = shutil.which("formvis")
    if which and not found:
        found.append({"name": "formvis", "path": which})
    return found


@command("editIn.apps", "External Editors", mutates=False)
def edit_in_apps() -> dict:
    p = prefs.load()
    return {"editors": _known_editors() + list(p.get("editors") or []), "options": p.get("editIn")}


@command("editIn.addApp", "Add External Editor", {"name": {"type": "string"}, "path": {"type": "string"}})
def edit_in_add(name: str, path: str) -> dict:
    p = prefs.load()
    eds = [e for e in (p.get("editors") or []) if e.get("path") != path]
    eds.append({"name": name.strip() or Path(path).stem, "path": path})
    prefs.update({"editors": eds})
    return {"editors": eds}


@command("photo.editIn", "Edit In", {"ids": {"type": "array"}, "app": {"type": "string"}, "mode": {"type": "string", "enum": ["copy", "copyNoEdits", "original"]},
                                     "format": {"type": "string", "enum": ["tiff", "png", "jpeg"]}, "space": {"type": "string"}, "depth": {"type": "integer"}, "wait": {"type": "boolean"}})
def photo_edit_in(ids: Any = None, app: str = "", mode: str = "copy", format: str | None = None, space: str | None = None, depth: int | None = None, wait: bool = True) -> dict:
    pids = resolve_ids(ids)
    opts = dict(prefs.load().get("editIn") or {})
    fmt, sp, dp = format or opts.get("format", "tiff"), space or opts.get("space", "prophoto"), int(depth or opts.get("depth", 16))
    if not app:
        eds = _known_editors() + list(prefs.load().get("editors") or [])
        app = eds[0]["path"] if eds else ""

    def job(progress):
        from app.engine.cmd_ai import _derived
        outs, new_ids = [], []
        for i, pid in enumerate(pids):
            row = cat().photo(pid)
            src = cat().photo_path(pid)
            if row is None or src is None:
                continue
            if mode == "original":
                outs.append(src)
                continue
            dev = loads(row["develop"], {}) if mode == "copy" else {}
            ext = encode.FORMATS[fmt]["ext"]
            dest = rename.unique(src.with_name(f"{src.stem}-Edit.{ext}"))
            out = export.render_photo(pid, {"resize": False}, sp, dev)
            rec = encode.filtered(json.loads(json.dumps(_detail(pid))), "noRaw", False, False)
            dest.write_bytes(encode.encode(out, fmt, sp, 95, dp if fmt != "jpeg" else 8, int(opts.get("ppi", 300)), rec, "zip"))
            new_ids.append(_derived(pid, dest, "Edit In", {}, None))
            outs.append(dest)
            progress(i + 1, len(pids), f"Preparing {i + 1} of {len(pids)}")
        launched = export.open_with(app, outs) if app else False
        return {"paths": [str(p) for p in outs], "ids": new_ids, "launched": launched, "app": app}
    return _wait(tasks.start("editIn", "Preparing for external editing", job), wait)


def _detail(pid: int) -> dict:
    from app.engine.records import detail
    return detail(cat(), pid) or {}


@command("print.options", "Print Options", mutates=False)
def print_options() -> dict:
    return {"paper": {k: {"name": v[0], "w": v[1], "h": v[2]} for k, v in layout.PAPER.items()}, "packages": layout.PACKAGE_SIZES,
            "templates": layout.PRINT_TEMPLATES, "defaults": layout.PRINT_DEFAULTS}


@command("print.layout", "Print Layout", {"settings": {"type": "object"}, "ids": {"type": "array"}, "collection": {"type": "integer"}}, mutates=False)
def print_layout(settings: dict | None = None, ids: Any = None, collection: int | None = None) -> dict:
    pids = _ids(ids, collection)
    asp = _aspects(pids)
    return _with_overlays(layout.print_pages(settings or {}, [{"id": p, "aspect": asp.get(p, 1.5)} for p in pids]))


def _with_overlays(lay: dict) -> dict:
    total = len(lay["pages"])
    for page in lay["pages"]:
        page["overlays"] = pages._overlays(page, lay, lay["settings"], total)
    return lay


@command("print.printers", "Printers", mutates=False)
def print_printers() -> dict:
    return {"printers": pages.printers()}


@command("print.run", "Print", {"settings": {"type": "object"}, "ids": {"type": "array"}, "collection": {"type": "integer"},
                                "output": {"type": "string", "enum": ["pdf", "jpeg", "printer"]}, "path": {"type": "string"}, "name": {"type": "string"}, "wait": {"type": "boolean"}})
def print_run(settings: dict | None = None, ids: Any = None, collection: int | None = None, output: str | None = None, path: str | None = None,
              name: str = "Print", wait: bool = False) -> dict:
    lay = print_layout(settings, ids, collection)
    out = output or (lay["settings"].get("job") or {}).get("output", "pdf")

    def job(progress):
        if out == "jpeg":
            folder = Path(path).expanduser() if path else rename.unique(_out_dir("Print") / rename.safe(name))
            files = pages.write_jpegs(lay, folder, rename.safe(name), progress)
            return {"paths": [str(f) for f in files], "folder": str(folder)}
        pdf = _out_path("Print", name, "pdf", path if out == "pdf" else None)
        pages.write_pdf(lay, pdf, progress)
        res: dict = {"path": str(pdf), "pages": len(lay["pages"])}
        if out == "printer":
            j = lay["settings"].get("job") or {}
            res["printer"] = pages.send_to_printer(pdf, j.get("printer", ""), int(j.get("copies", 1)))
        return res
    return _wait(tasks.start("print", "Printing" if out == "printer" else f"Rendering {len(lay['pages'])} {'page' if len(lay['pages']) == 1 else 'pages'}", job), wait)


@command("book.options", "Book Options", mutates=False)
def book_options() -> dict:
    return {"sizes": {k: {"name": v[0], "w": v[1], "h": v[2]} for k, v in layout.BOOK_SIZES.items()},
            "templates": {k: {"name": v["name"], "cells": v["cells"], "texts": v["texts"]} for k, v in layout.BOOK_TEMPLATES.items()}, "defaults": layout.BOOK_DEFAULTS,
            "presets": layout.BOOK_PRESETS}


@command("book.autoLayout", "Auto Layout Book", {"ids": {"type": "array"}, "collection": {"type": "integer"}, "mode": {"type": "string", "enum": ["mixed", "one"]}}, mutates=False)
def book_auto(ids: Any = None, collection: int | None = None, mode: str = "mixed") -> dict:
    pids = _ids(ids, collection)
    return {"pages": layout.auto_book(pids, _aspects(pids), mode), "cover": {"template": "cover", "photos": pids[:1], "texts": ["Untitled", ""]}}


@command("book.layout", "Book Layout", {"settings": {"type": "object"}}, mutates=False)
def book_layout(settings: dict | None = None) -> dict:
    s = layout.deep_merge(layout.BOOK_DEFAULTS, settings)
    used = [int(p) for pg in [s["cover"]] + list(s["pages"]) for p in (pg.get("photos") or []) if p is not None]
    return _with_overlays(layout.book_pages(s, _aspects(used)))


@command("book.export", "Export Book", {"settings": {"type": "object"}, "format": {"type": "string", "enum": ["pdf", "jpeg"]}, "path": {"type": "string"},
                                        "name": {"type": "string"}, "wait": {"type": "boolean"}})
def book_export(settings: dict | None = None, format: str = "pdf", path: str | None = None, name: str = "Book", wait: bool = False) -> dict:
    lay = book_layout(settings)

    def job(progress):
        if format == "jpeg":
            folder = Path(path).expanduser() if path else rename.unique(_out_dir("Books") / rename.safe(name))
            files = pages.write_jpegs(lay, folder, rename.safe(name), progress)
            return {"paths": [str(f) for f in files], "folder": str(folder)}
        pdf = _out_path("Books", name, "pdf", path)
        pages.write_pdf(lay, pdf, progress)
        return {"path": str(pdf), "pages": len(lay["pages"])}
    return _wait(tasks.start("book", f"Exporting book, {len(lay['pages'])} pages", job), wait)


@command("slideshow.options", "Slideshow Options", mutates=False)
def slideshow_options() -> dict:
    return {"templates": slideshow.TEMPLATES, "defaults": slideshow.DEFAULTS, "sizes": {k: {"w": v[0], "h": v[1]} for k, v in slideshow.SIZES.items()},
            "ffmpeg": bool(shutil.which("ffmpeg"))}


@command("slideshow.layout", "Slideshow Layout", {"ids": {"type": "array"}, "collection": {"type": "integer"}, "settings": {"type": "object"}}, mutates=False)
def slideshow_layout(ids: Any = None, collection: int | None = None, settings: dict | None = None) -> dict:
    pids = _ids(ids, collection)
    s = slideshow.merged(settings)
    lay = _with_overlays(slideshow.page_layout(pids, _aspects(pids), s, for_pdf=False))
    lay["slideshow"] = s
    return lay


@command("slideshow.export", "Export Slideshow", {"ids": {"type": "array"}, "collection": {"type": "integer"}, "settings": {"type": "object"},
                                                  "format": {"type": "string", "enum": ["mp4", "pdf", "jpeg"]}, "path": {"type": "string"}, "name": {"type": "string"}, "wait": {"type": "boolean"}})
def slideshow_export(ids: Any = None, collection: int | None = None, settings: dict | None = None, format: str = "mp4", path: str | None = None,
                     name: str = "Slideshow", wait: bool = False) -> dict:
    pids = _ids(ids, collection)
    asp = _aspects(pids)
    s = slideshow.merged(settings)

    def job(progress):
        if format == "mp4":
            p = _out_path("Slideshows", name, "mp4", path)
            slideshow.write_video(pids, asp, s, p, progress)
            return {"path": str(p)}
        lay = slideshow.page_layout(pids, asp, s, for_pdf=format == "pdf")
        if format == "jpeg":
            folder = Path(path).expanduser() if path else rename.unique(_out_dir("Slideshows") / rename.safe(name))
            return {"paths": [str(f) for f in pages.write_jpegs(lay, folder, rename.safe(name), progress)], "folder": str(folder)}
        p = _out_path("Slideshows", name, "pdf", path)
        pages.write_pdf(lay, p, progress)
        return {"path": str(p)}
    return _wait(tasks.start("slideshow", f"Exporting slideshow ({format.upper()})", job), wait)


@command("web.options", "Web Gallery Options", mutates=False)
def web_options() -> dict:
    return {"templates": web.TEMPLATES, "defaults": web.DEFAULTS}


@command("web.preview", "Preview Web Gallery", {"ids": {"type": "array"}, "collection": {"type": "integer"}, "settings": {"type": "object"}, "base": {"type": "string"}}, mutates=False)
def web_preview(ids: Any = None, collection: int | None = None, settings: dict | None = None, base: str = "") -> dict:
    return {"html": web.preview_html(_ids(ids, collection), settings or {}, base)}


@command("web.export", "Export Web Gallery", {"ids": {"type": "array"}, "collection": {"type": "integer"}, "settings": {"type": "object"}, "folder": {"type": "string"},
                                              "name": {"type": "string"}, "upload": {"type": "boolean"}, "wait": {"type": "boolean"}})
def web_export(ids: Any = None, collection: int | None = None, settings: dict | None = None, folder: str | None = None, name: str = "Web Gallery",
               upload: bool = False, wait: bool = False) -> dict:
    pids = _ids(ids, collection)
    s = web.merged(settings)
    dest = Path(folder).expanduser() if folder else rename.unique(_out_dir("Web") / rename.safe(name))

    def job(progress):
        index = web.write_site(pids, s, dest, progress)
        res: dict = {"path": str(index), "folder": str(dest), "photos": len(pids)}
        if upload:
            res["uploaded"] = web.upload(dest, s["upload"], progress)
        return res
    return _wait(tasks.start("web", "Uploading web gallery" if upload else "Exporting web gallery", job), wait)


@command("publish.services", "Publish Services", mutates=False)
def publish_services() -> dict:
    return {"services": publish.services(), "kinds": publish.KINDS}


@command("publish.createService", "New Publish Service", {"kind": {"type": "string", "enum": list(publish.KINDS)}, "name": {"type": "string"}, "settings": {"type": "object"}})
def publish_create_service(kind: str, name: str, settings: dict | None = None) -> dict:
    if kind not in publish.KINDS:
        raise CommandError("kind is folder or ftp")
    with cat().change("New Publish Service") as ch:
        sid = ch.insert("publish_services", kind=kind, name=name.strip() or publish.KINDS[kind], settings=settings or {})
    return {"id": sid}


@command("publish.updateService", "Edit Publish Service", {"id": {"type": "integer"}, "name": {"type": "string"}, "settings": {"type": "object"}})
def publish_update_service(id: int, name: str | None = None, settings: dict | None = None) -> dict:
    fields: dict = {}
    if name is not None:
        fields["name"] = name.strip()
    if settings is not None:
        old = loads(cat().scalar("SELECT settings FROM publish_services WHERE id=?", (int(id),)), {})
        if "password" not in settings and "password" in old:
            settings = dict(settings, password=old["password"])
        fields["settings"] = settings
    with cat().change("Edit Publish Service") as ch:
        ch.update("publish_services", int(id), **fields)
    return {"id": int(id)}


@command("publish.deleteService", "Remove Publish Service", {"id": {"type": "integer"}})
def publish_delete_service(id: int) -> dict:
    with cat().change("Remove Publish Service") as ch:
        for r in cat().rows("SELECT id FROM collections WHERE kind IN ('published', 'publishedSet') AND service_id=?", (int(id),)):
            ch.delete("published", collection_id=int(r["id"]))
            ch.delete("collection_photos", collection_id=int(r["id"]))
            ch.delete("collections", id=int(r["id"]))
        ch.delete("publish_services", id=int(id))
    return {"deleted": int(id)}


@command("publish.status", "Publish Status", {"collection": {"type": "integer"}}, mutates=False)
def publish_status(collection: int) -> dict:
    return publish.status(int(collection))


@command("publish.markRepublish", "Mark to Republish", {"collection": {"type": "integer"}, "ids": {"type": "array", "description": "photos to mark; omit for every published photo in the collection"}})
def publish_mark_republish(collection: int, ids: Any = None) -> dict:
    pids = resolve_ids(ids) if ids else None
    return {"marked": publish.mark(int(collection), pids, False)}


@command("publish.markUpToDate", "Mark as Up-to-Date", {"collection": {"type": "integer"}, "ids": {"type": "array", "description": "photos to mark; omit for every new and modified photo"}})
def publish_mark_up_to_date(collection: int, ids: Any = None) -> dict:
    pids = resolve_ids(ids) if ids else None
    return {"marked": publish.mark(int(collection), pids, True)}


@command("publish.run", "Publish", {"collection": {"type": "integer"}, "wait": {"type": "boolean"}})
def publish_run(collection: int, wait: bool = False) -> dict:
    name = cat().scalar("SELECT name FROM collections WHERE id=?", (int(collection),)) or "collection"
    return _wait(tasks.start("publish", f"Publishing {name}", lambda progress: publish.run(int(collection), progress)), wait)


@command("photo.setGps", "Set Location", {"ids": {"type": "array"}, "lat": {"type": "number"}, "lon": {"type": "number"}, "alt": {"type": "number"}})
def photo_set_gps(ids: Any = None, lat: float | None = None, lon: float | None = None, alt: float | None = None) -> dict:
    pids = resolve_ids(ids)
    if (lat is None) != (lon is None):
        raise CommandError("Pass both lat and lon, or neither to clear the location")
    if lat is not None and not (-90 <= float(lat) <= 90 and -180 <= float(lon) <= 180):
        raise CommandError("lat is -90 to 90 and lon is -180 to 180")
    with cat().change("Set Location" if lat is not None else "Remove Location") as ch:
        for pid in pids:
            ch.update("photos", pid, gps_lat=lat, gps_lon=lon, gps_alt=alt)
    return {"ids": pids, "lat": lat, "lon": lon}


_search_last = [0.0]


@command("gps.search", "Search the Map", {"query": {"type": "string", "description": "a place name or address"}, "limit": {"type": "integer"}}, mutates=False)
def gps_search(query: str, limit: int = 6) -> dict:
    import time as _time
    import httpx
    from app import __version__
    q = (query or "").strip()
    if not q:
        return {"results": []}
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$", q)
    if m and -90 <= float(m.group(1)) <= 90 and -180 <= float(m.group(2)) <= 180:
        return {"results": [{"name": f"{float(m.group(1)):.6f}, {float(m.group(2)):.6f}", "lat": float(m.group(1)), "lon": float(m.group(2)), "bbox": None}]}
    wait = 1.05 - (_time.time() - _search_last[0])
    if wait > 0:
        _time.sleep(wait)
    _search_last[0] = _time.time()
    try:
        with httpx.Client(headers={"User-Agent": f"formlit/{__version__} (desktop photo library; map search)", "Accept-Language": "en"}, timeout=15) as client:
            resp = client.get("https://nominatim.openstreetmap.org/search", params={"q": q, "format": "jsonv2", "limit": max(1, min(10, int(limit)))})
    except httpx.HTTPError as e:
        raise CommandError(f"Map search is unavailable: {e}") from e
    if resp.status_code != 200:
        raise CommandError(f"Map search failed ({resp.status_code})")
    out = []
    for r in resp.json() or []:
        bb = r.get("boundingbox")
        out.append({"name": r.get("display_name", ""), "lat": float(r["lat"]), "lon": float(r["lon"]), "kind": r.get("type", ""),
                    "bbox": [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])] if bb and len(bb) == 4 else None})
    return {"results": out, "attribution": "Data from OpenStreetMap contributors, ODbL 1.0"}


@command("gps.lookupAddress", "Look Up Addresses", {"ids": {"type": "array"}, "overwrite": {"type": "boolean"}, "wait": {"type": "boolean"}})
def gps_lookup(ids: Any = None, overwrite: bool = False, wait: bool = True) -> dict:
    import time as _time
    import httpx
    from app import __version__
    pids = resolve_ids(ids)
    rows = [r for r in cat().rows(f"SELECT id, gps_lat, gps_lon, meta FROM photos WHERE id IN ({','.join('?' * len(pids))}) AND gps_lat IS NOT NULL", tuple(pids))] if pids else []

    def job(progress):
        groups: dict[tuple, list] = {}
        for r in rows:
            groups.setdefault((round(float(r["gps_lat"]), 4), round(float(r["gps_lon"]), 4)), []).append(r)
        filled = 0
        with httpx.Client(headers={"User-Agent": f"formlit/{__version__} (desktop photo library; address lookup)", "Accept-Language": "en"}, timeout=20) as client:
            for i, ((la, lo), members) in enumerate(groups.items()):
                if progress.cancelled:
                    break
                resp = client.get("https://nominatim.openstreetmap.org/reverse", params={"lat": la, "lon": lo, "format": "jsonv2", "zoom": 16, "addressdetails": 1})
                if resp.status_code == 200:
                    a = (resp.json() or {}).get("address") or {}
                    found = {"city": a.get("city") or a.get("town") or a.get("village") or a.get("hamlet") or a.get("municipality") or "",
                             "state": a.get("state") or a.get("region") or a.get("county") or "", "country": a.get("country") or "",
                             "isoCountryCode": (a.get("country_code") or "").upper(),
                             "sublocation": a.get("road") or a.get("neighbourhood") or a.get("suburb") or ""}
                    with cat().change("Look Up Addresses") as ch:
                        for r in members:
                            meta = loads(r["meta"], {})
                            for k, v in found.items():
                                if v and (overwrite or not meta.get(k)):
                                    meta[k] = v
                            ch.update("photos", int(r["id"]), meta=meta)
                            filled += 1
                progress(i + 1, len(groups), f"Looking up {i + 1} of {len(groups)} places")
                _time.sleep(1.05)
        return {"photos": filled, "places": len(groups), "attribution": "Data from OpenStreetMap contributors, ODbL 1.0"}
    return _wait(tasks.start("geocode", "Looking up addresses", job), wait)


@command("location.list", "Saved Locations", mutates=False)
def location_list() -> dict:
    out = []
    for r in cat().rows("SELECT * FROM locations ORDER BY name COLLATE NOCASE"):
        n = 0
        lat, lon, rad = float(r["lat"]), float(r["lon"]), float(r["radius"])
        dlat = rad / 111.0
        for p in cat().rows("SELECT gps_lat, gps_lon FROM photos WHERE gps_lat BETWEEN ? AND ?", (lat - dlat, lat + dlat)):
            if _km(lat, lon, float(p["gps_lat"]), float(p["gps_lon"])) <= rad:
                n += 1
        out.append({"id": int(r["id"]), "name": r["name"], "lat": lat, "lon": lon, "radius": rad, "private": bool(r["private"]), "count": n})
    return {"locations": out}


def _km(a: float, b: float, c: float, d: float) -> float:
    import math
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = p2 - p1, math.radians(d - b)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(h)))


@command("location.save", "Save Location", {"id": {"type": "integer"}, "name": {"type": "string"}, "lat": {"type": "number"}, "lon": {"type": "number"},
                                            "radius": {"type": "number"}, "private": {"type": "boolean"}})
def location_save(name: str, lat: float, lon: float, radius: float = 0.2, private: bool = False, id: int | None = None) -> dict:
    with cat().change("Save Location") as ch:
        if id is None:
            lid = ch.insert("locations", name=name.strip() or "Location", lat=float(lat), lon=float(lon), radius=max(0.01, float(radius)), private=int(bool(private)))
        else:
            lid = int(id)
            ch.update("locations", lid, name=name.strip() or "Location", lat=float(lat), lon=float(lon), radius=max(0.01, float(radius)), private=int(bool(private)))
    return {"id": lid}


@command("location.delete", "Delete Location", {"id": {"type": "integer"}})
def location_delete(id: int) -> dict:
    with cat().change("Delete Location") as ch:
        ch.delete("locations", id=int(id))
    return {"deleted": int(id)}


def _gpx_points(text: str) -> list[tuple[float, float, float, float | None]]:
    root = ET.fromstring(text)
    pts = []
    for el in root.iter():
        if not el.tag.endswith("trkpt") and not el.tag.endswith("rtept"):
            continue
        t = next((c.text for c in el if c.tag.endswith("time")), None)
        ele = next((c.text for c in el if c.tag.endswith("ele")), None)
        if not t:
            continue
        when = datetime.fromisoformat(t.strip().replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        pts.append((when.timestamp(), float(el.get("lat")), float(el.get("lon")), float(ele) if ele else None))
    pts.sort()
    return pts


@command("gps.tracklog", "Auto-Tag from Track Log", {"ids": {"type": "array"}, "path": {"type": "string"}, "gpx": {"type": "string"}, "offsetMinutes": {"type": "number"},
                                                     "maxGapMinutes": {"type": "number"}, "apply": {"type": "boolean"}})
def gps_tracklog(ids: Any = None, path: str | None = None, gpx: str | None = None, offsetMinutes: float | None = None, maxGapMinutes: float = 30.0,
                 apply: bool = True) -> dict:
    text = gpx if gpx else Path(path or "").expanduser().read_text(encoding="utf-8") if path else ""
    if not text:
        raise CommandError("Pass a GPX file path or its contents")
    pts = _gpx_points(text)
    if not pts:
        raise CommandError("The track log has no timed points")
    pids = resolve_ids(ids)
    explicit = offsetMinutes is not None
    if offsetMinutes is None:
        local = datetime.now().astimezone().utcoffset() or timedelta(0)
        offsetMinutes = local.total_seconds() / 60
    times = [p[0] for p in pts]
    matched: dict[int, list[float]] = {}
    for r in cat().rows(f"SELECT id, capture_time FROM photos WHERE id IN ({','.join('?' * len(pids))})", tuple(pids)):
        if not r["capture_time"]:
            continue
        try:
            when = datetime.fromisoformat(r["capture_time"])
        except ValueError:
            continue
        if when.tzinfo is not None and not explicit:
            ts = when.timestamp()
        else:
            ts = (when.replace(tzinfo=None) - timedelta(minutes=offsetMinutes)).replace(tzinfo=timezone.utc).timestamp()
        i = bisect.bisect_left(times, ts)
        cands = [j for j in (i - 1, i) if 0 <= j < len(pts)]
        if not cands:
            continue
        if 0 < i < len(pts) and times[i] - times[i - 1] <= maxGapMinutes * 60:
            a, b = pts[i - 1], pts[i]
            k = (ts - a[0]) / max(1e-6, b[0] - a[0])
            matched[int(r["id"])] = [a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k]
        else:
            j = min(cands, key=lambda j: abs(times[j] - ts))
            if abs(times[j] - ts) <= maxGapMinutes * 60:
                matched[int(r["id"])] = [pts[j][1], pts[j][2]]
    if apply and matched:
        with cat().change("Auto-Tag Locations") as ch:
            for pid, (la, lo) in matched.items():
                ch.update("photos", pid, gps_lat=la, gps_lon=lo)
    return {"matched": {str(k): v for k, v in matched.items()}, "count": len(matched), "points": len(pts), "track": [[p[1], p[2]] for p in pts[:: max(1, len(pts) // 2000)]],
            "start": datetime.fromtimestamp(pts[0][0], timezone.utc).isoformat(), "end": datetime.fromtimestamp(pts[-1][0], timezone.utc).isoformat(), "offsetMinutes": offsetMinutes}


@command("output.reveal", "Show in Folder", {"path": {"type": "string"}}, mutates=False)
def output_reveal(path: str) -> dict:
    p = Path(path).expanduser()
    if not p.exists():
        raise CommandError(f"Not found: {p}")
    export.reveal(p)
    return {"path": str(p), "desktop": config.is_desktop()}


@command("prefs.get", "Preferences", mutates=False)
def prefs_get() -> dict:
    return prefs.load()


@command("prefs.set", "Set Preferences", {"values": {"type": "object"}})
def prefs_set(values: dict) -> dict:
    out = prefs.update(values)
    if {"autoWriteXmp", "xmpIntoFiles"} & set(values):
        from app.services import xmpwrite
        xmpwrite.configure()
    return out
