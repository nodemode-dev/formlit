import json
from pathlib import Path
from typing import Any

from app.engine.catalog import Catalog

SUMMARY_SQL = ("SELECT p.id, p.file_name, p.kind, p.format, p.width, p.height, p.capture_time, p.import_time, p.edit_time, p.rating, p.flag, p.label, p.edited, "
               "p.develop_rev, p.develop, p.master_id, p.copy_name, p.stack_id, p.stack_pos, p.missing, p.duration, p.camera, p.lens, p.iso, p.focal, p.aperture, "
               "p.shutter, p.gps_lat, p.gps_lon, p.file_size, p.folder_id, p.smart_preview, p.xmp_state FROM photos p")


def loads(text: str | None, default: Any) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except ValueError:
        return default


def oriented_dims(w: int, h: int, develop: dict) -> tuple[int, int]:
    turns = int(develop.get("orientation", 0) or 0) % 4
    return (h, w) if turns % 2 else (w, h)


def aspect(w: int, h: int, develop: dict) -> float:
    ow, oh = oriented_dims(max(1, w), max(1, h), develop)
    crop = (develop.get("crop") or {}).get("rect")
    if crop and len(crop) == 4:
        x0, y0, x1, y1 = crop
        cw, ch = max(1e-6, (x1 - x0) * ow), max(1e-6, (y1 - y0) * oh)
        return round(cw / ch, 4)
    return round(ow / oh, 4)


def summary(r: Any) -> dict:
    dev = loads(r["develop"], {})
    out = {"id": r["id"], "file": r["file_name"], "kind": r["kind"], "fmt": r["format"], "w": r["width"], "h": r["height"],
           "a": aspect(r["width"], r["height"], dev), "t": r["capture_time"], "r": r["rating"], "f": r["flag"], "l": r["label"],
           "e": r["edited"], "rev": r["develop_rev"], "folder": r["folder_id"]}
    if r["master_id"]:
        out["m"] = r["master_id"]
        out["cn"] = r["copy_name"]
    if r["stack_id"]:
        out["st"] = r["stack_id"]
        out["sp"] = r["stack_pos"]
    if r["missing"]:
        out["miss"] = 1
    if r["duration"]:
        out["dur"] = r["duration"]
    if r["gps_lat"] is not None:
        out["gps"] = [r["gps_lat"], r["gps_lon"]]
    if r["smart_preview"]:
        out["sp2"] = 1
    if r["xmp_state"]:
        out["xs"] = r["xmp_state"]
    return out


def detail(cat: Catalog, pid: int) -> dict | None:
    r = cat.photo(pid)
    if r is None:
        return None
    dev = loads(r["develop"], {})
    out = summary(r)
    out.update({
        "path": str(Path(r["folder_path"]) / r["file_name"]), "folderPath": r["folder_path"], "fileName": r["file_name"],
        "captureTime": r["capture_time"], "importTime": r["import_time"], "editTime": r["edit_time"],
        "fileSize": r["file_size"], "camera": r["camera"], "lens": r["lens"], "focal": r["focal"], "aperture": r["aperture"], "shutter": r["shutter"],
        "iso": r["iso"], "bias": r["bias"], "flash": r["flash"], "gpsLat": r["gps_lat"], "gpsLon": r["gps_lon"], "gpsAlt": r["gps_alt"], "gpsDir": r["gps_dir"],
        "meta": loads(r["meta"], {}), "exif": loads(r["exif"], {}), "develop": dev, "sidecars": loads(r["sidecars"], []),
        "keywords": cat.photo_keywords(pid),
        "collections": [int(x["collection_id"]) for x in cat.rows("SELECT collection_id FROM collection_photos WHERE photo_id=?", (pid,))],
        "copyName": r["copy_name"], "masterId": r["master_id"], "stackId": r["stack_id"], "missing": bool(r["missing"]),
        "history": int(cat.scalar("SELECT COUNT(*) FROM history WHERE photo_id=?", (pid,)) or 0),
    })
    return out
