import json
import os
import platform
import shutil
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.engine import catalog as catalog_mod
from app.engine import query, records, tasks
from app.engine.catalog import LABELS, now_iso
from app.engine.commands import SESSION, CommandError, command, resolve_ids
from app.services import importer, metadata, previews, rename

FLAG_NAMES = {"pick": 1, "reject": -1, "none": 0, "unflag": 0, "unflagged": 0}
COLLECTION_KINDS = {"collection": "Collection", "set": "Collection Set", "smart": "Smart Collection", "book": "Book", "print": "Print",
                    "slideshow": "Slideshow", "web": "Web Gallery", "published": "Published Collection", "publishedSet": "Published Collection Set"}


def cat():
    return catalog_mod.get()


def _ids(ids: Any) -> list[int]:
    out = resolve_ids(ids)
    if not out:
        raise CommandError("No photos given")
    return out


@command("library.select", "Select Photos", {"ids": {"type": "array"}, "active": {"type": "integer"}}, mutates=False)
def select(ids: list[int] | None = None, active: int | None = None, source: dict | None = None, module: str | None = None) -> dict:
    with SESSION.lock:
        if ids is not None:
            SESSION.selection = [int(i) for i in ids]
        if active is not None:
            if SESSION.active and SESSION.active != int(active):
                SESSION.previous_photo = SESSION.active
            SESSION.active = int(active)
        if source is not None:
            SESSION.source = source
        if module:
            SESSION.module = module
        return {"selection": list(SESSION.selection), "active": SESSION.active}


@command("library.session", "Current Selection", mutates=False)
def session() -> dict:
    with SESSION.lock:
        return {"selection": list(SESSION.selection), "active": SESSION.active, "source": SESSION.source, "module": SESSION.module}


@command("library.query", "Find Photos", {"source": {"type": "object"}, "filter": {"type": "object"}, "sort": {"type": "object"}}, mutates=False)
def run_query(source: dict | None = None, filter: dict | None = None, sort: dict | None = None, stacks: bool = True, limit: int | None = None) -> dict:
    return query.query(cat(), source, filter, sort, stacks, limit)


@command("library.facets", "Metadata Facets", mutates=False)
def facets(source: dict | None = None) -> dict:
    return query.facets(cat(), source)


@command("library.facetColumns", "Metadata Filter Columns", {"source": {"type": "object"}, "columns": {"type": "array", "description": "facet ids, left to right; each column counts photos that match the selections in the columns to its left"}, "meta": {"type": "object"}, "filter": {"type": "object"}}, mutates=False)
def facet_columns(columns: list | None = None, source: dict | None = None, meta: dict | None = None, filter: dict | None = None) -> dict:
    cols = [str(c) for c in (columns or ["date", "camera", "lens", "label"])]
    return {"columns": query.facet_columns(cat(), source, cols, meta, filter), "available": [[k, v[0]] for k, v in query.FACETS.items()]}


DEFAULT_FILTER_PRESETS = [
    {"name": "Default Columns", "builtin": True, "tab": "metadata", "columns": ["date", "camera", "lens", "label"], "filter": {}},
    {"name": "Exposure Info", "builtin": True, "tab": "metadata", "columns": ["focal", "shutter", "aperture", "iso"], "filter": {}},
    {"name": "Location Columns", "builtin": True, "tab": "metadata", "columns": ["country", "state", "city", "location"], "filter": {}},
    {"name": "Flagged", "builtin": True, "tab": "attribute", "filter": {"flags": ["pick"]}},
    {"name": "Rated", "builtin": True, "tab": "attribute", "filter": {"rating": 1, "ratingOp": ">="}},
    {"name": "Unrated", "builtin": True, "tab": "attribute", "filter": {"rating": 0, "ratingOp": "="}},
    {"name": "Edited", "builtin": True, "tab": "attribute", "filter": {"edited": True}},
    {"name": "Unedited", "builtin": True, "tab": "attribute", "filter": {"edited": False}},
    {"name": "Filters Off", "builtin": True, "tab": "", "filter": {}},
]


@command("library.filterPresets", "Library Filter Presets", mutates=False)
def filter_presets() -> dict:
    from app.core import prefs
    return {"presets": DEFAULT_FILTER_PRESETS + list(prefs.load().get("filterPresets") or [])}


@command("library.filterPresetSave", "Save Library Filter Preset", {"name": {"type": "string"}, "filter": {"type": "object"}, "columns": {"type": "array"}, "tab": {"type": "string"}})
def filter_preset_save(name: str, filter: dict | None = None, columns: list | None = None, tab: str = "") -> dict:
    from app.core import prefs
    name = name.strip()
    if not name or any(p["name"] == name for p in DEFAULT_FILTER_PRESETS):
        raise ValueError("choose a name that is not a built-in preset")
    mine = [p for p in (prefs.load().get("filterPresets") or []) if p.get("name") != name]
    entry = {"name": name, "tab": tab, "filter": filter or {}}
    if columns:
        entry["columns"] = [str(c) for c in columns if str(c) in query.FACETS]
    prefs.update({"filterPresets": mine + [entry]})
    return {"saved": name}


@command("library.filterPresetDelete", "Delete Library Filter Preset", {"name": {"type": "string"}})
def filter_preset_delete(name: str) -> dict:
    from app.core import prefs
    mine = [p for p in (prefs.load().get("filterPresets") or []) if p.get("name") != name]
    prefs.update({"filterPresets": mine})
    return {"deleted": name}


@command("photo.get", "Photo Details", {"id": {"type": "integer"}}, mutates=False)
def get_photo(id: int | None = None) -> dict:
    pid = id if id is not None else resolve_ids("active")[0]
    d = records.detail(cat(), int(pid))
    if d is None:
        raise CommandError(f"No photo with id {pid}", 404)
    return d


@command("library.scan", "Scan for Photos", {"paths": {"type": "array"}, "recursive": {"type": "boolean"}}, mutates=False)
def scan(paths: list[str], recursive: bool = True, limit: int = 5000) -> dict:
    return importer.scan(paths, recursive, max(1, min(int(limit), 200_000)))


@command("library.import", "Import Photos", {"paths": {"type": "array"}, "mode": {"type": "string", "enum": ["add", "copy", "move"]}, "destination": {"type": "string"}})
def do_import(paths: list[str], mode: str = "add", destination: str = "", folderTemplate: str = "{date:%Y}/{date:%Y-%m-%d}", renameTemplate: str = "",
              custom: str = "", develop: Any = None, metadata: dict | None = None, keywords: list[str] | None = None, collection: int | None = None,
              skipDuplicates: bool = True, recursive: bool = True, wait: bool = False, buildPreviews: str = "", backup: str = "",
              smartPreviews: bool = False, eject: str = "") -> dict:
    dev = None
    if isinstance(develop, dict):
        dev = develop
    elif isinstance(develop, str) and develop:
        from app.engine import presets
        dev = presets.settings_of(develop)
    if mode not in ("add", "copy", "move", "dng"):
        raise CommandError("mode is add, copy, dng (Copy as DNG) or move")

    def job(progress):
        res = importer.import_files(paths, mode, destination, folderTemplate, renameTemplate, custom, dev, metadata, keywords, collection,
                                    skipDuplicates, recursive, progress, backup=backup)
        if dev and res["ids"]:
            from app.engine.cmd_ai import bitmap_refs, ensure_masks
            if bitmap_refs(dev):
                for i, pid in enumerate(res["ids"]):
                    progress(i + 1, len(res["ids"]), f"Adaptive masks {i + 1} of {len(res['ids'])}")
                    try:
                        ensure_masks(pid)
                    except Exception:
                        continue
        if buildPreviews in ("standard", "1:1") and res["ids"]:
            previews.build_all(res["ids"], "p", progress)
        if buildPreviews == "1:1" and res["ids"]:
            previews.build_all(res["ids"], "f", progress)
        if smartPreviews and res["ids"]:
            built = []
            for i, pid in enumerate(res["ids"]):
                try:
                    previews.source(pid)
                    built.append(pid)
                except (FileNotFoundError, OSError, ValueError):
                    continue
                progress(i + 1, len(res["ids"]), f"Smart preview {i + 1} of {len(res['ids'])}")
            with cat().change("Build Smart Previews", undoable=False) as ch:
                for pid in built:
                    ch.update("photos", pid, smart_preview=1)
        if eject:
            res["ejected"] = _eject(eject)
        if res["ids"]:
            from app.engine.cmd_ai import adapt
            adapt(res["ids"])
        return res
    tid = tasks.start("import", "Importing photos", job)
    if wait:
        t = tasks.wait(tid)
        if t and t["state"] == "failed":
            raise CommandError(t["error"] or "Import failed")
        return {"task": tid, **(t["result"] if t and t.get("result") else {})}
    return {"task": tid}


def _eject(path: str) -> bool:
    p = Path(path).expanduser()
    while not os.path.ismount(p) and p.parent != p:
        p = p.parent
    if p == Path(p.anchor):
        return False
    system = platform.system()
    if system == "Darwin":
        cmd = ["diskutil", "eject", str(p)]
    elif system == "Windows":
        cmd = ["powershell", "-NoProfile", "-Command", f"(New-Object -ComObject Shell.Application).Namespace(17).ParseName('{str(p).rstrip(chr(92))}').InvokeVerb('Eject')"]
    else:
        cmd = ["gio", "mount", "-e", str(p)]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _flag(v: Any) -> int:
    if isinstance(v, (int, float)):
        return max(-1, min(1, int(v)))
    if str(v).lower() not in FLAG_NAMES:
        raise CommandError("flag is pick, reject or none")
    return FLAG_NAMES[str(v).lower()]


@command("photo.rate", "Set Rating", {"ids": {"type": "array"}, "rating": {"type": "integer", "minimum": 0, "maximum": 5}, "delta": {"type": "integer"}})
def rate(ids: Any = None, rating: int | None = None, delta: int | None = None) -> dict:
    pids = _ids(ids)
    c = cat()
    with c.change("Set Rating") as ch:
        for pid in pids:
            r = c.db.execute("SELECT rating FROM photos WHERE id=?", (pid,)).fetchone()
            if r is None:
                continue
            new = max(0, min(5, int(r["rating"]) + int(delta))) if delta is not None else max(0, min(5, int(rating or 0)))
            ch.update("photos", pid, rating=new)
    return {"ids": pids}


@command("photo.flag", "Set Flag", {"ids": {"type": "array"}, "flag": {"type": "string", "enum": ["pick", "reject", "none"]}})
def flag(ids: Any = None, flag: Any = "pick", toggle: bool = False) -> dict:
    pids = _ids(ids)
    value = _flag(flag)
    c = cat()
    with c.change("Set Flag") as ch:
        for pid in pids:
            if toggle:
                cur = c.db.execute("SELECT flag FROM photos WHERE id=?", (pid,)).fetchone()
                ch.update("photos", pid, flag=0 if cur and int(cur["flag"]) == value else value)
            else:
                ch.update("photos", pid, flag=value)
    return {"ids": pids}


@command("photo.label", "Set Color Label", {"ids": {"type": "array"}, "label": {"type": "string", "enum": LABELS + ["none"]}})
def label(ids: Any = None, label: str = "red", toggle: bool = True) -> dict:
    pids = _ids(ids)
    value = "" if label in ("none", "", None) else str(label).lower()
    if value and value not in LABELS:
        raise CommandError(f"label is one of {', '.join(LABELS)} or none")
    c = cat()
    with c.change("Set Color Label") as ch:
        for pid in pids:
            cur = c.db.execute("SELECT label FROM photos WHERE id=?", (pid,)).fetchone()
            ch.update("photos", pid, label="" if toggle and cur and cur["label"] == value else value)
    return {"ids": pids}


@command("photo.setMeta", "Edit Metadata", {"ids": {"type": "array"}, "fields": {"type": "object"}})
def set_meta(ids: Any = None, fields: dict | None = None) -> dict:
    pids = _ids(ids)
    fields = fields or {}
    c = cat()
    direct = {"gpsLat": "gps_lat", "gpsLon": "gps_lon", "gpsAlt": "gps_alt", "captureTime": "capture_time"}
    with c.change("Edit Metadata") as ch:
        for pid in pids:
            r = c.db.execute("SELECT meta FROM photos WHERE id=?", (pid,)).fetchone()
            if r is None:
                continue
            meta = records.loads(r["meta"], {})
            cols = {}
            for k, v in fields.items():
                if k in direct:
                    cols[direct[k]] = v
                elif k in metadata.META_FIELDS:
                    if v in (None, ""):
                        meta.pop(k, None)
                    else:
                        meta[k] = v
            ch.update("photos", pid, meta=meta, **cols)
    return {"ids": pids}


@command("photo.addKeywords", "Add Keywords", {"ids": {"type": "array"}, "keywords": {"type": "array"}})
def add_keywords(ids: Any = None, keywords: list[str] | None = None) -> dict:
    pids = _ids(ids)
    c = cat()
    with c.change("Add Keywords") as ch:
        for kw in keywords or []:
            kid = c.keyword_id(ch, kw)
            for pid in pids:
                if not c.db.execute("SELECT 1 FROM photo_keywords WHERE photo_id=? AND keyword_id=?", (pid, kid)).fetchone():
                    ch.insert("photo_keywords", photo_id=pid, keyword_id=kid)
    return {"ids": pids}


@command("photo.removeKeywords", "Remove Keywords", {"ids": {"type": "array"}, "keywords": {"type": "array"}})
def remove_keywords(ids: Any = None, keywords: list[str] | None = None) -> dict:
    pids = _ids(ids)
    c = cat()
    with c.change("Remove Keywords") as ch:
        for kw in keywords or []:
            leaf = kw.split("|")[-1].strip()
            for r in c.db.execute("SELECT id FROM keywords WHERE name=? COLLATE NOCASE", (leaf,)).fetchall():
                if "|" in kw and c.keyword_path(int(r["id"])).lower() != kw.lower():
                    continue
                for pid in pids:
                    ch.delete("photo_keywords", photo_id=pid, keyword_id=int(r["id"]))
    return {"ids": pids}


@command("photo.setKeywords", "Set Keywords", {"ids": {"type": "array"}, "keywords": {"type": "array"}})
def set_keywords(ids: Any = None, keywords: list[str] | None = None) -> dict:
    pids = _ids(ids)
    c = cat()
    with c.change("Set Keywords") as ch:
        want = {c.keyword_id(ch, kw) for kw in keywords or []}
        for pid in pids:
            have = {int(r["keyword_id"]) for r in c.db.execute("SELECT keyword_id FROM photo_keywords WHERE photo_id=?", (pid,)).fetchall()}
            for kid in have - want:
                ch.delete("photo_keywords", photo_id=pid, keyword_id=kid)
            for kid in want - have:
                ch.insert("photo_keywords", photo_id=pid, keyword_id=kid)
    return {"ids": pids}


@command("photo.rotate", "Rotate", {"ids": {"type": "array"}, "turns": {"type": "integer"}})
def rotate(ids: Any = None, turns: int = 1) -> dict:
    from app.engine import cmd_develop
    pids = _ids(ids)
    c = cat()
    with c.change("Rotate Left" if turns < 0 else "Rotate Right") as ch:
        for pid in pids:
            dev = records.loads(c.db.execute("SELECT develop FROM photos WHERE id=?", (pid,)).fetchone()["develop"], {})
            dev["orientation"] = (int(dev.get("orientation", 0)) + int(turns)) % 4
            if not dev["orientation"]:
                dev.pop("orientation")
            cmd_develop.store(ch, pid, dev, "Rotate")
    return {"ids": pids}


@command("photo.virtualCopy", "Create Virtual Copy", {"ids": {"type": "array"}, "name": {"type": "string"}})
def virtual_copy(ids: Any = None, name: str = "") -> dict:
    pids = _ids(ids)
    c = cat()
    made = []
    with c.change("Create Virtual Copy") as ch:
        for pid in pids:
            r = c.db.execute("SELECT * FROM photos WHERE id=?", (pid,)).fetchone()
            if r is None:
                continue
            master = int(r["master_id"] or r["id"])
            n = int(c.db.execute("SELECT COUNT(*) FROM photos WHERE master_id=?", (master,)).fetchone()[0]) + 1
            row = {k: r[k] for k in r.keys() if k not in ("id",)}
            row.update(master_id=master, copy_name=f"{name} {n}" if name else f"Copy {n}", import_time=now_iso())
            stack = r["stack_id"]
            if not stack:
                stack = ch.insert("stacks", collapsed=0)
                ch.update("photos", master, stack_id=stack, stack_pos=0)
            row.update(stack_id=stack, stack_pos=int(c.db.execute("SELECT COALESCE(MAX(stack_pos), 0) FROM photos WHERE stack_id=?", (stack,)).fetchone()[0]) + 1)
            new = ch.insert("photos", **row)
            for kw in c.db.execute("SELECT keyword_id FROM photo_keywords WHERE photo_id=?", (pid,)).fetchall():
                ch.insert("photo_keywords", photo_id=new, keyword_id=int(kw["keyword_id"]))
            for col in c.db.execute("SELECT collection_id, position FROM collection_photos WHERE photo_id=?", (pid,)).fetchall():
                ch.insert("collection_photos", collection_id=int(col["collection_id"]), photo_id=new, position=int(col["position"]))
            made.append(new)
    from app.engine.cmd_ai import adapt
    adapt(made)
    return {"ids": made}


@command("photo.setMasterCopy", "Set Copy as Master", {"id": {"type": "integer"}})
def set_master(id: int) -> dict:
    c = cat()
    r = c.row("SELECT master_id, copy_name FROM photos WHERE id=?", (int(id),))
    if r is None or not r["master_id"]:
        raise CommandError("That photo is not a virtual copy")
    old = int(r["master_id"])
    with c.change("Set Copy as Master") as ch:
        for other in c.db.execute("SELECT id FROM photos WHERE master_id=? AND id!=?", (old, int(id))).fetchall():
            ch.update("photos", int(other["id"]), master_id=int(id))
        ch.update("photos", old, master_id=int(id), copy_name=r["copy_name"])
        ch.update("photos", int(id), master_id=None, copy_name=None)
    return {"id": int(id)}


@command("photo.remove", "Remove from Catalog", {"ids": {"type": "array"}})
def remove(ids: Any = None) -> dict:
    pids = _ids(ids)
    c = cat()
    with c.change("Remove Photos") as ch:
        stacks = {int(r["stack_id"]) for pid in pids for r in c.db.execute("SELECT stack_id FROM photos WHERE id=? AND stack_id IS NOT NULL", (pid,)).fetchall()}
        for pid in pids:
            for table, col in (("photo_keywords", "photo_id"), ("collection_photos", "photo_id"), ("history", "photo_id"), ("snapshots", "photo_id"), ("faces", "photo_id")):
                ch.delete(table, **{col: pid})
            for vc in c.db.execute("SELECT id FROM photos WHERE master_id=?", (pid,)).fetchall():
                if int(vc["id"]) not in pids:
                    ch.update("photos", int(vc["id"]), master_id=None)
            ch.delete("photos", id=pid)
        for sid in stacks:
            left = [int(r["id"]) for r in c.db.execute("SELECT id FROM photos WHERE stack_id=? ORDER BY stack_pos, id", (sid,)).fetchall()]
            if len(left) < 2:
                for one in left:
                    ch.update("photos", one, stack_id=None, stack_pos=0)
                ch.delete("stacks", id=sid)
            else:
                for pos, one in enumerate(left):
                    ch.update("photos", one, stack_pos=pos)
    for pid in pids:
        previews.drop_source(pid)
        previews.clear(pid)
    with SESSION.lock:
        SESSION.selection = [i for i in SESSION.selection if i not in pids]
        if SESSION.active in pids:
            SESSION.active = None
    return {"ids": pids}


def _trash(path: Path) -> None:
    try:
        from send2trash import send2trash
        send2trash(str(path))
        return
    except ImportError:
        pass
    trash = Path.home() / (".Trash" if platform.system() == "Darwin" else ".local/share/Trash/files")
    trash.mkdir(parents=True, exist_ok=True)
    path.replace(rename.unique(trash / path.name))


@command("photo.delete", "Delete from Disk", {"ids": {"type": "array"}})
def delete(ids: Any = None) -> dict:
    pids = _ids(ids)
    c = cat()
    paths = []
    for pid in pids:
        r = c.row("SELECT master_id FROM photos WHERE id=?", (pid,))
        if r and not r["master_id"]:
            p = c.photo_path(pid)
            if p is not None:
                paths.append(p)
    remove(pids)
    trashed = []
    for p in paths:
        if p.is_file():
            _trash(p)
            side = metadata.sidecar_path(p)
            if side.is_file():
                _trash(side)
            trashed.append(str(p))
    return {"ids": pids, "trashed": trashed}


@command("photo.setCaptureTime", "Edit Capture Time", {"ids": {"type": "array"}, "time": {"type": "string"}, "shiftSeconds": {"type": "number"}})
def set_capture_time(ids: Any = None, time: str | None = None, shiftSeconds: float | None = None, each: bool = False) -> dict:
    pids = _ids(ids)
    c = cat()
    rows = {pid: c.row("SELECT capture_time FROM photos WHERE id=?", (pid,)) for pid in pids}
    shift = timedelta(seconds=shiftSeconds or 0)
    if time and not each:
        first = rows[pids[0]]["capture_time"] if rows.get(pids[0]) else None
        try:
            shift = datetime.fromisoformat(time[:19]) - datetime.fromisoformat((first or time)[:19])
        except ValueError as exc:
            raise CommandError(f"time must be YYYY-MM-DDTHH:MM:SS: {exc}")
    with c.change("Edit Capture Time") as ch:
        for pid, r in rows.items():
            if r is None:
                continue
            if time and each:
                ch.update("photos", pid, capture_time=time[:19])
                continue
            try:
                base = datetime.fromisoformat((r["capture_time"] or now_iso())[:19])
            except ValueError:
                base = datetime.now()
            ch.update("photos", pid, capture_time=(base + shift).strftime("%Y-%m-%dT%H:%M:%S"))
    return {"ids": pids}


@command("photo.rename", "Rename Photos", {"ids": {"type": "array"}, "template": {"type": "string"}, "custom": {"type": "string"}, "start": {"type": "integer"}})
def rename_photos(ids: Any = None, template: str = "{name}", custom: str = "", start: int = 1, preview: bool = False) -> dict:
    pids = _ids(ids)
    c = cat()
    plan = []
    for i, pid in enumerate(pids):
        d = records.detail(c, pid)
        if d is None or d.get("masterId"):
            continue
        rec = {"fileName": d["fileName"], "captureTime": d["captureTime"], "camera": d["camera"], "lens": d["lens"], "iso": d["iso"], "rating": d["r"],
               "label": d["l"], "meta": d["meta"], "folder": d["folderPath"], "focal": d["focal"], "aperture": d["aperture"]}
        name = rename.expand(template, rec, start + i, custom) + Path(d["fileName"]).suffix.lower()
        plan.append((pid, Path(d["path"]), Path(d["folderPath"]) / Path(name).name))
    if preview:
        return {"plan": [{"id": pid, "from": src.name, "to": dst.name} for pid, src, dst in plan]}
    done = []
    with c.change("Rename Photos") as ch:
        for pid, src, dst in plan:
            if src == dst:
                continue
            if not src.is_file():
                continue
            target = rename.unique(dst)
            src.rename(target)
            side = metadata.sidecar_path(src)
            if side.is_file():
                side.rename(metadata.sidecar_path(target))
            ch.update("photos", pid, file_name=target.name)
            for vc in c.db.execute("SELECT id FROM photos WHERE master_id=?", (pid,)).fetchall():
                ch.update("photos", int(vc["id"]), file_name=target.name)
            done.append({"id": pid, "name": target.name})
    return {"renamed": done}


@command("photo.reveal", "Show in Finder", {"id": {"type": "integer"}}, mutates=False)
def reveal(id: int | None = None) -> dict:
    pid = id if id is not None else resolve_ids("active")[0]
    p = cat().photo_path(int(pid))
    if p is None:
        raise CommandError("No such photo")
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.Popen(["open", "-R", str(p)])
        elif system == "Windows":
            subprocess.Popen(["explorer", "/select,", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p.parent)])
    except OSError as exc:
        raise CommandError(f"Could not open the file manager: {exc}")
    return {"path": str(p)}


@command("photo.relink", "Locate Missing Photo", {"id": {"type": "integer"}, "path": {"type": "string"}})
def relink(id: int, path: str, nearby: bool = True) -> dict:
    c = cat()
    p = Path(path).expanduser()
    if p.is_dir():
        row = c.row("SELECT p.file_name, f.path FROM photos p JOIN folders f ON f.id=p.folder_id WHERE p.id=?", (int(id),))
        if row is None:
            raise CommandError("No such photo")
        old_dir = row["path"]
        hit = next((q for q in [p / row["file_name"], *p.glob(f"*/{row['file_name']}")] if q.is_file()), None)
        if hit is None:
            raise CommandError(f"{row['file_name']} is not in {p}")
        relink(int(id), str(hit), False)
        found = [int(id)]
        if nearby:
            for o in c.rows("SELECT p.id, p.file_name FROM photos p JOIN folders f ON f.id=p.folder_id WHERE f.path=? AND p.missing=1 AND p.master_id IS NULL AND p.id!=?", (old_dir, int(id))):
                cand = hit.parent / o["file_name"]
                if cand.is_file():
                    relink(int(o["id"]), str(cand), False)
                    found.append(int(o["id"]))
        return {"id": int(id), "found": found}
    if not p.is_file():
        raise CommandError(f"No file at {p}")
    with c.change("Locate Photo") as ch:
        fid = c.folder_id(ch, p.parent)
        ch.update("photos", int(id), folder_id=fid, file_name=p.name, missing=0)
        for vc in c.db.execute("SELECT id FROM photos WHERE master_id=?", (int(id),)).fetchall():
            ch.update("photos", int(vc["id"]), folder_id=fid, file_name=p.name, missing=0)
    previews.drop_source(int(id))
    return {"id": int(id)}


@command("library.findMissing", "Find Missing Photos", mutates=False)
def find_missing() -> dict:
    c = cat()
    rows = c.rows("SELECT p.id, f.path, p.file_name, p.missing FROM photos p JOIN folders f ON f.id=p.folder_id")
    missing, found = [], []
    for r in rows:
        exists = (Path(r["path"]) / r["file_name"]).is_file()
        if exists == bool(r["missing"]):
            (found if exists else missing).append(int(r["id"]))
    if missing or found:
        with c.change("Find Missing Photos", undoable=False) as ch:
            for pid in missing:
                ch.update("photos", pid, missing=1)
            for pid in found:
                ch.update("photos", pid, missing=0)
    return {"missing": [int(r["id"]) for r in c.rows("SELECT id FROM photos WHERE missing=1")]}


@command("photo.saveMetadata", "Save Metadata to File", {"ids": {"type": "array"}}, mutates=False)
def save_metadata(ids: Any = None) -> dict:
    from app.services import xmpwrite
    pids = _ids(ids)
    written, where = [], {}
    for pid in pids:
        try:
            w = xmpwrite.write(pid)
        except OSError as exc:
            raise CommandError(f"Could not write the metadata of photo {pid}: {exc}")
        if w:
            written.append(pid)
            where[w] = where.get(w, 0) + 1
    return {"ids": written, "into": where}


@command("library.checkMetadata", "Check Metadata Files", {"ids": {"type": "array"}})
def check_metadata(ids: Any = None) -> dict:
    from app.services import xmpwrite
    return xmpwrite.check(_ids(ids) if ids is not None else None)


WATCH: set[int] = set()


def changed_files(pids: list[int], apply: bool = True) -> list[int]:
    c = cat()
    found: list[tuple[int, os.stat_result, Path]] = []
    for i in range(0, len(pids), 900):
        chunk = pids[i:i + 900]
        for r in c.rows(f"SELECT p.id, f.path, p.file_name, p.file_size, p.file_mtime FROM photos p JOIN folders f ON f.id=p.folder_id WHERE p.master_id IS NULL AND p.id IN ({','.join('?' * len(chunk))})", tuple(chunk)):
            path = Path(r["path"]) / r["file_name"]
            try:
                st = path.stat()
            except OSError:
                continue
            if st.st_size != int(r["file_size"] or 0) or abs(st.st_mtime - float(r["file_mtime"] or 0)) > 1.0:
                found.append((int(r["id"]), st, path))
    if apply and found:
        from app.services import decode
        with c.change("Files Changed on Disk", undoable=False) as ch:
            for pid, st, path in found:
                w, h = decode.dimensions(path)
                previews.drop_source(pid)
                fam = [pid] + [int(x["id"]) for x in c.rows("SELECT id FROM photos WHERE master_id=?", (pid,))]
                for one in fam:
                    previews.clear(one)
                    rev = int(c.scalar("SELECT develop_rev FROM photos WHERE id=?", (one,)) or 0)
                    ch.update("photos", one, file_size=st.st_size, file_mtime=st.st_mtime, develop_rev=rev + 1, **({"width": w, "height": h} if w and h else {}))
        previews.warm([pid for pid, _, _ in found])
    return [pid for pid, _, _ in found]


@command("library.checkFiles", "Check for Changed Files", {"ids": {"type": "array"}})
def check_files(ids: Any = None) -> dict:
    from app.services import xmpwrite
    pids = sorted(set(resolve_ids(ids) if ids else []) | WATCH)
    if not pids:
        return {"changed": [], "conflicts": []}
    return {"changed": changed_files(pids), "conflicts": xmpwrite.check(pids)["conflicts"]}


@command("photo.readMetadata", "Read Metadata from File", {"ids": {"type": "array"}})
def read_metadata(ids: Any = None) -> dict:
    pids = _ids(ids)
    c = cat()
    with c.change("Read Metadata from File") as ch:
        for pid in pids:
            p = c.photo_path(pid)
            if p is None or not p.is_file():
                continue
            x = metadata.read_xmp(p)
            cols: dict = {}
            if "rating" in x:
                cols["rating"] = max(0, min(5, int(x["rating"])))
            if "label" in x and x["label"].lower() in LABELS:
                cols["label"] = x["label"].lower()
            if x.get("meta"):
                meta = records.loads(c.db.execute("SELECT meta FROM photos WHERE id=?", (pid,)).fetchone()["meta"], {})
                meta.update(x["meta"])
                cols["meta"] = meta
            ch.update("photos", pid, **cols)
            for kw in x.get("keywords", []):
                kid = c.keyword_id(ch, kw)
                if not c.db.execute("SELECT 1 FROM photo_keywords WHERE photo_id=? AND keyword_id=?", (pid, kid)).fetchone():
                    ch.insert("photo_keywords", photo_id=pid, keyword_id=kid)
            dev = None
            if x.get("develop"):
                dev = records.loads(x["develop"], None)
            elif x.get("crs"):
                from app.services import xmp_presets
                wh = c.row("SELECT width, height FROM photos WHERE id=?", (pid,))
                dev = xmp_presets.from_crs(x["crs"], (wh["width"] or 3) / max(1, wh["height"] or 2) if wh else 1.5)
            if isinstance(dev, dict):
                from app.engine.cmd_develop import store
                store(ch, pid, dev, "Read Metadata from File")
    from app.engine.cmd_develop import after
    from app.services import xmpwrite
    after(pids)
    xmpwrite.synced(pids)
    return {"ids": pids}


@command("stack.group", "Group into Stack", {"ids": {"type": "array"}})
def stack_group(ids: Any = None) -> dict:
    pids = _ids(ids)
    if len(pids) < 2:
        raise CommandError("A stack needs two or more photos")
    c = cat()
    with c.change("Group into Stack") as ch:
        sid = ch.insert("stacks", collapsed=1)
        for i, pid in enumerate(pids):
            ch.update("photos", pid, stack_id=sid, stack_pos=i)
    return {"stack": sid}


@command("stack.ungroup", "Unstack", {"ids": {"type": "array"}})
def stack_ungroup(ids: Any = None) -> dict:
    pids = _ids(ids)
    c = cat()
    sids = {int(r["stack_id"]) for pid in pids for r in [c.row("SELECT stack_id FROM photos WHERE id=?", (pid,))] if r and r["stack_id"]}
    with c.change("Unstack") as ch:
        for sid in sids:
            for r in c.db.execute("SELECT id FROM photos WHERE stack_id=?", (sid,)).fetchall():
                ch.update("photos", int(r["id"]), stack_id=None, stack_pos=0)
            ch.delete("stacks", id=sid)
    return {"stacks": sorted(sids)}


@command("stack.toggle", "Expand or Collapse Stack", {"ids": {"type": "array"}, "collapsed": {"type": "boolean"}})
def stack_toggle(ids: Any = None, collapsed: bool | None = None) -> dict:
    pids = _ids(ids)
    c = cat()
    with c.change("Expand or Collapse Stack", undoable=False) as ch:
        for pid in pids:
            r = c.db.execute("SELECT stack_id FROM photos WHERE id=?", (pid,)).fetchone()
            if r and r["stack_id"]:
                s = c.db.execute("SELECT collapsed FROM stacks WHERE id=?", (r["stack_id"],)).fetchone()
                if s:
                    ch.update("stacks", int(r["stack_id"]), collapsed=int(not s["collapsed"]) if collapsed is None else int(collapsed))
    return {"ids": pids}


@command("stack.setTop", "Move to Top of Stack", {"id": {"type": "integer"}})
def stack_top(id: int) -> dict:
    c = cat()
    r = c.row("SELECT stack_id, stack_pos FROM photos WHERE id=?", (int(id),))
    if not r or not r["stack_id"]:
        raise CommandError("That photo is not in a stack")
    with c.change("Move to Top of Stack") as ch:
        for o in c.db.execute("SELECT id, stack_pos FROM photos WHERE stack_id=? ORDER BY stack_pos", (r["stack_id"],)).fetchall():
            if int(o["id"]) == int(id):
                ch.update("photos", int(id), stack_pos=0)
            elif int(o["stack_pos"]) < int(r["stack_pos"]):
                ch.update("photos", int(o["id"]), stack_pos=int(o["stack_pos"]) + 1)
    return {"id": int(id)}


@command("stack.auto", "Auto-Stack by Capture Time", {"seconds": {"type": "number"}, "ids": {"type": "array"}})
def stack_auto(seconds: float = 30.0, ids: Any = None) -> dict:
    c = cat()
    if ids is None:
        rows = c.rows("SELECT id, capture_time FROM photos WHERE stack_id IS NULL AND master_id IS NULL ORDER BY capture_time")
    else:
        pids = _ids(ids)
        rows = c.rows(f"SELECT id, capture_time FROM photos WHERE id IN ({','.join('?' * len(pids))}) AND stack_id IS NULL ORDER BY capture_time", tuple(pids))
    groups: list[list[int]] = []
    last = None
    for r in rows:
        try:
            t = datetime.fromisoformat((r["capture_time"] or "")[:19])
        except ValueError:
            last = None
            continue
        if last is not None and (t - last).total_seconds() <= seconds and groups:
            groups[-1].append(int(r["id"]))
        else:
            groups.append([int(r["id"])])
        last = t
    made = 0
    with c.change("Auto-Stack by Capture Time") as ch:
        for g in groups:
            if len(g) < 2:
                continue
            sid = ch.insert("stacks", collapsed=1)
            for i, pid in enumerate(g):
                ch.update("photos", pid, stack_id=sid, stack_pos=i)
            made += 1
    return {"stacks": made}


def _quick_id(ch) -> int:
    c = cat()
    r = c.db.execute("SELECT id FROM collections WHERE kind='quick'").fetchone()
    return int(r["id"]) if r else ch.insert("collections", name="Quick Collection", kind="quick", position=-1)


@command("collection.create", "New Collection", {"name": {"type": "string"}, "kind": {"type": "string", "enum": list(COLLECTION_KINDS)}, "parent": {"type": "integer"}, "ids": {"type": "array"}, "rules": {"type": "object"}, "settings": {"type": "object"}, "service": {"type": "integer"}})
def collection_create(name: str, kind: str = "collection", parent: int | None = None, ids: list[int] | None = None, rules: dict | None = None, target: bool = False,
                      settings: dict | None = None, service: int | None = None) -> dict:
    if kind not in COLLECTION_KINDS:
        raise CommandError("kind is " + ", ".join(COLLECTION_KINDS))
    c = cat()
    with c.change(f"New {COLLECTION_KINDS[kind]}") as ch:
        pos = int(c.db.execute("SELECT COALESCE(MAX(position), 0) FROM collections").fetchone()[0]) + 1
        cid = ch.insert("collections", name=name.strip() or "Untitled", kind=kind, parent_id=parent, rules=rules or ({"match": "all", "rules": []} if kind == "smart" else None), position=pos,
                        settings=settings, service_id=service)
        if target:
            for o in c.db.execute("SELECT id FROM collections WHERE target=1").fetchall():
                ch.update("collections", int(o["id"]), target=0)
            ch.update("collections", cid, target=1)
        if kind not in ("set", "smart", "publishedSet") and not rules:
            for i, pid in enumerate(ids or []):
                ch.insert("collection_photos", collection_id=cid, photo_id=int(pid), position=i)
    return {"id": cid}


@command("collection.update", "Edit Collection", {"id": {"type": "integer"}, "name": {"type": "string"}, "parent": {"type": "integer"}, "rules": {"type": "object"}, "settings": {"type": "object"}, "cover": {"type": "integer"}})
def collection_update(id: int, name: str | None = None, parent: int | None = -1, rules: dict | None = None, settings: dict | None = None, cover: int | None = None) -> dict:
    c = cat()
    fields: dict = {}
    if name is not None:
        fields["name"] = name.strip() or "Untitled"
    if parent != -1:
        fields["parent_id"] = parent
    if rules is not None:
        fields["rules"] = rules
    if settings is not None:
        fields["settings"] = settings
    if cover is not None:
        fields["cover_id"] = cover
    with c.change("Edit Collection") as ch:
        ch.update("collections", int(id), **fields)
    return {"id": int(id)}


@command("collection.delete", "Delete Collection", {"id": {"type": "integer"}})
def collection_delete(id: int) -> dict:
    c = cat()
    with c.change("Delete Collection") as ch:
        todo = [int(id)] + query.collection_descendants(c, int(id))
        for cid in todo:
            ch.delete("collection_photos", collection_id=cid)
            ch.delete("published", collection_id=cid)
            ch.delete("collections", id=cid)
    return {"deleted": todo}


@command("collection.addPhotos", "Add to Collection", {"id": {"type": "integer"}, "ids": {"type": "array"}})
def collection_add(id: int | None = None, ids: Any = None) -> dict:
    pids = _ids(ids)
    c = cat()
    with c.change("Add to Collection") as ch:
        cid = int(id) if id is not None else int((c.db.execute("SELECT id FROM collections WHERE target=1").fetchone() or [0])[0]) or _quick_id(ch)
        kind = c.db.execute("SELECT kind FROM collections WHERE id=?", (cid,)).fetchone()
        if kind is None or kind["kind"] in ("set", "smart"):
            raise CommandError("Photos go into a collection, not a set or a smart collection")
        pos = int(c.db.execute("SELECT COALESCE(MAX(position), 0) FROM collection_photos WHERE collection_id=?", (cid,)).fetchone()[0])
        for pid in pids:
            if not c.db.execute("SELECT 1 FROM collection_photos WHERE collection_id=? AND photo_id=?", (cid, pid)).fetchone():
                pos += 1
                ch.insert("collection_photos", collection_id=cid, photo_id=pid, position=pos)
    return {"id": cid, "ids": pids}


@command("collection.removePhotos", "Remove from Collection", {"id": {"type": "integer"}, "ids": {"type": "array"}})
def collection_remove(id: int, ids: Any = None) -> dict:
    pids = _ids(ids)
    c = cat()
    with c.change("Remove from Collection") as ch:
        for pid in pids:
            ch.delete("collection_photos", collection_id=int(id), photo_id=pid)
    return {"id": int(id), "ids": pids}


@command("collection.reorder", "Custom Order", {"id": {"type": "integer"}, "ids": {"type": "array"}})
def collection_reorder(id: int, ids: list[int]) -> dict:
    c = cat()
    with c.change("Custom Order") as ch:
        for i, pid in enumerate(ids):
            r = c.db.execute("SELECT position FROM collection_photos WHERE collection_id=? AND photo_id=?", (int(id), int(pid))).fetchone()
            if r is not None and int(r["position"]) != i:
                ch.delete("collection_photos", collection_id=int(id), photo_id=int(pid))
                ch.insert("collection_photos", collection_id=int(id), photo_id=int(pid), position=i)
    return {"id": int(id)}


@command("collection.setTarget", "Set as Target Collection", {"id": {"type": "integer"}})
def collection_target(id: int | None = None) -> dict:
    c = cat()
    with c.change("Set Target Collection", undoable=False) as ch:
        for o in c.db.execute("SELECT id FROM collections WHERE target=1").fetchall():
            ch.update("collections", int(o["id"]), target=0)
        if id:
            ch.update("collections", int(id), target=1)
    return {"id": id}


@command("quick.toggle", "Add to Quick Collection", {"ids": {"type": "array"}})
def quick_toggle(ids: Any = None) -> dict:
    pids = _ids(ids)
    c = cat()
    with c.change("Quick Collection") as ch:
        tgt = c.db.execute("SELECT id FROM collections WHERE target=1").fetchone()
        cid = int(tgt["id"]) if tgt else _quick_id(ch)
        inside = all(c.db.execute("SELECT 1 FROM collection_photos WHERE collection_id=? AND photo_id=?", (cid, pid)).fetchone() for pid in pids)
        pos = int(c.db.execute("SELECT COALESCE(MAX(position), 0) FROM collection_photos WHERE collection_id=?", (cid,)).fetchone()[0])
        for pid in pids:
            if inside:
                ch.delete("collection_photos", collection_id=cid, photo_id=pid)
            elif not c.db.execute("SELECT 1 FROM collection_photos WHERE collection_id=? AND photo_id=?", (cid, pid)).fetchone():
                pos += 1
                ch.insert("collection_photos", collection_id=cid, photo_id=pid, position=pos)
    return {"id": cid, "added": not inside}


@command("quick.clear", "Clear Quick Collection")
def quick_clear() -> dict:
    c = cat()
    r = c.row("SELECT id FROM collections WHERE kind='quick'")
    if r:
        with c.change("Clear Quick Collection") as ch:
            ch.delete("collection_photos", collection_id=int(r["id"]))
    return {}


@command("keyword.create", "New Keyword", {"path": {"type": "string"}})
def keyword_create(path: str, synonyms: list[str] | None = None, person: bool = False) -> dict:
    c = cat()
    with c.change("New Keyword") as ch:
        kid = c.keyword_id(ch, path)
        if synonyms or person:
            ch.update("keywords", kid, synonyms=synonyms or [], person=int(person))
    return {"id": kid}


@command("keyword.update", "Edit Keyword", {"id": {"type": "integer"}, "name": {"type": "string"}, "parent": {"type": "integer"}})
def keyword_update(id: int, name: str | None = None, parent: int | None = -1, synonyms: list[str] | None = None, export: bool | None = None, person: bool | None = None) -> dict:
    c = cat()
    fields: dict = {}
    if name is not None:
        fields["name"] = name.strip()
    if parent != -1:
        fields["parent_id"] = parent
    if synonyms is not None:
        fields["synonyms"] = synonyms
    if export is not None:
        fields["export"] = int(export)
    if person is not None:
        fields["person"] = int(person)
    with c.change("Edit Keyword") as ch:
        ch.update("keywords", int(id), **fields)
    return {"id": int(id)}


@command("keyword.delete", "Delete Keyword", {"id": {"type": "integer"}})
def keyword_delete(id: int) -> dict:
    c = cat()
    rows = c.rows("WITH RECURSIVE t(id) AS (SELECT ? UNION ALL SELECT k.id FROM keywords k JOIN t ON k.parent_id=t.id) SELECT id FROM t", (int(id),))
    with c.change("Delete Keyword") as ch:
        for r in rows:
            ch.delete("photo_keywords", keyword_id=int(r["id"]))
            ch.delete("keywords", id=int(r["id"]))
    return {"deleted": [int(r["id"]) for r in rows]}


@command("keyword.merge", "Merge Keywords", {"ids": {"type": "array"}, "into": {"type": "integer"}})
def keyword_merge(ids: list[int], into: int) -> dict:
    c = cat()
    with c.change("Merge Keywords") as ch:
        for kid in ids:
            if int(kid) == int(into):
                continue
            for r in c.db.execute("SELECT photo_id FROM photo_keywords WHERE keyword_id=?", (int(kid),)).fetchall():
                if not c.db.execute("SELECT 1 FROM photo_keywords WHERE photo_id=? AND keyword_id=?", (r["photo_id"], int(into))).fetchone():
                    ch.insert("photo_keywords", photo_id=int(r["photo_id"]), keyword_id=int(into))
            ch.delete("photo_keywords", keyword_id=int(kid))
            for child in c.db.execute("SELECT id FROM keywords WHERE parent_id=?", (int(kid),)).fetchall():
                ch.update("keywords", int(child["id"]), parent_id=int(into))
            ch.delete("keywords", id=int(kid))
    return {"into": int(into)}


@command("keyword.purge", "Purge Unused Keywords")
def keyword_purge() -> dict:
    c = cat()
    parent = {int(r["id"]): r["parent_id"] for r in c.rows("SELECT id, parent_id FROM keywords")}
    used = {int(r["keyword_id"]) for r in c.rows("SELECT DISTINCT keyword_id FROM photo_keywords")}
    used |= {int(r["keyword_id"]) for r in c.rows("SELECT keyword_id FROM people WHERE keyword_id IS NOT NULL")}
    keep: set[int] = set()
    for kid in used:
        k: int | None = kid
        while k is not None and k not in keep:
            keep.add(k)
            p = parent.get(k)
            k = int(p) if p is not None else None
    gone = [kid for kid in parent if kid not in keep]
    if gone:
        with c.change("Purge Unused Keywords") as ch:
            for kid in gone:
                ch.delete("keywords", id=kid)
    return {"deleted": len(gone)}


@command("keyword.suggest", "Keyword Suggestions", {"ids": {"type": "array"}}, mutates=False)
def keyword_suggest(ids: Any = None, limit: int = 9) -> dict:
    c = cat()
    try:
        pids = _ids(ids)
    except CommandError:
        pids = []
    have = {int(r["keyword_id"]) for pid in pids for r in c.rows("SELECT keyword_id FROM photo_keywords WHERE photo_id=?", (pid,))}
    scores: dict[int, float] = {}
    if have:
        marks = ",".join("?" * len(have))
        for r in c.rows(f"SELECT b.keyword_id AS kid, COUNT(*) AS n FROM photo_keywords a JOIN photo_keywords b ON a.photo_id=b.photo_id WHERE a.keyword_id IN ({marks}) AND b.keyword_id NOT IN ({marks}) GROUP BY b.keyword_id", tuple(have) * 2):
            scores[int(r["kid"])] = scores.get(int(r["kid"]), 0) + 2 * int(r["n"])
    if pids:
        r0 = c.row("SELECT capture_time FROM photos WHERE id=?", (pids[0],))
        if r0 and r0["capture_time"]:
            for r in c.rows("SELECT pk.keyword_id AS kid, COUNT(*) AS n FROM photo_keywords pk JOIN photos p ON p.id=pk.photo_id WHERE substr(p.capture_time,1,10)=substr(?,1,10) GROUP BY pk.keyword_id", (r0["capture_time"],)):
                if int(r["kid"]) not in have:
                    scores[int(r["kid"])] = scores.get(int(r["kid"]), 0) + int(r["n"])
    for r in c.rows("SELECT keyword_id AS kid, COUNT(*) AS n FROM photo_keywords GROUP BY keyword_id ORDER BY n DESC LIMIT 30"):
        if int(r["kid"]) not in have:
            scores[int(r["kid"])] = scores.get(int(r["kid"]), 0) + 0.1 * int(r["n"])
    best = sorted(scores, key=lambda k: -scores[k])[:limit]
    return {"keywords": [{"id": k, "path": c.keyword_path(k)} for k in best]}


@command("folder.update", "Rename Folder", {"id": {"type": "integer"}, "name": {"type": "string"}})
def folder_update(id: int, name: str) -> dict:
    c = cat()
    r = c.row("SELECT path FROM folders WHERE id=?", (int(id),))
    if r is None:
        raise CommandError("No such folder")
    old = Path(r["path"])
    new = old.with_name(rename.safe(name))
    if new.exists():
        raise CommandError(f"{new.name} already exists")
    old.rename(new)
    with c.change("Rename Folder") as ch:
        for f in c.db.execute("SELECT id, path FROM folders WHERE path=? OR path LIKE ?", (str(old), str(old) + os.sep + "%")).fetchall():
            p = str(new) + f["path"][len(str(old)):]
            ch.update("folders", int(f["id"]), path=p, name=Path(p).name)
    return {"id": int(id), "path": str(new)}


@command("folder.create", "New Folder", {"parent": {"type": "integer"}, "name": {"type": "string"}, "path": {"type": "string"}})
def folder_create(name: str = "", parent: int | None = None, path: str = "") -> dict:
    c = cat()
    if path:
        target = Path(path).expanduser()
    else:
        r = c.row("SELECT path FROM folders WHERE id=?", (int(parent or 0),))
        if r is None:
            raise CommandError("Give a parent folder or a path")
        target = Path(r["path"]) / rename.safe(name)
    target.mkdir(parents=True, exist_ok=True)
    with c.change("New Folder") as ch:
        fid = c.folder_id(ch, target)
    return {"id": fid, "path": str(target)}


@command("folder.synchronize", "Synchronize Folder", {"id": {"type": "integer"}, "importNew": {"type": "boolean"}, "removeMissing": {"type": "boolean"},
                                                      "scanMetadata": {"type": "boolean"}, "dryRun": {"type": "boolean"}})
def folder_sync(id: int, importNew: bool = True, removeMissing: bool = False, scanMetadata: bool = True, dryRun: bool = False) -> dict:
    from app.services import xmpwrite
    c = cat()
    r = c.row("SELECT path FROM folders WHERE id=?", (int(id),))
    if r is None:
        raise CommandError("No such folder")
    rows = c.rows("SELECT p.id, f.path, p.file_name, p.missing FROM photos p JOIN folders f ON f.id=p.folder_id WHERE p.master_id IS NULL AND (f.path=? OR f.path LIKE ?)", (r["path"], r["path"] + os.sep + "%"))
    gone = {int(x["id"]) for x in rows if not (Path(x["path"]) / x["file_name"]).is_file()}
    flip = [x for x in rows if (int(x["id"]) in gone) != bool(x["missing"])]
    if flip:
        with c.change("Find Missing Photos", undoable=False) as ch:
            for x in flip:
                ch.update("photos", int(x["id"]), missing=1 if int(x["id"]) in gone else 0)
    missing = sorted(gone)
    missing += [int(x["id"]) for x in c.rows(f"SELECT id FROM photos WHERE master_id IN ({','.join('?' * len(gone))})", tuple(gone))] if gone else []
    present = [int(x["id"]) for x in rows if int(x["id"]) not in gone]
    new = [f["path"] for f in importer.scan([r["path"]], True, 50_000)["files"] if not f["inCatalog"]] if importNew or dryRun else []
    if dryRun:
        return {"new": len(new), "missing": len(gone), "changed": len(changed_files(present, apply=False)), "path": r["path"]}
    res: dict = {"imported": 0, "missing": len(gone), "removed": 0, "changed": [], "conflicts": []}
    if importNew and new:
        res["imported"] = importer.import_files(new, "add", skip_duplicates=False, recursive=False)["count"]
    if removeMissing and missing:
        remove(missing)
        res["removed"] = len(gone)
    if scanMetadata and present:
        res["changed"] = changed_files(present)
        res["conflicts"] = xmpwrite.check(present)["conflicts"]
    return res


@command("folder.remove", "Remove Folder", {"id": {"type": "integer"}})
def folder_remove(id: int) -> dict:
    c = cat()
    r = c.row("SELECT path FROM folders WHERE id=?", (int(id),))
    if r is None:
        raise CommandError("No such folder")
    ids = [int(x["id"]) for x in c.rows("SELECT p.id FROM photos p JOIN folders f ON f.id=p.folder_id WHERE f.path=? OR f.path LIKE ?", (r["path"], r["path"] + os.sep + "%"))]
    if ids:
        remove(ids)
    with c.change("Remove Folder") as ch:
        for f in c.db.execute("SELECT id FROM folders WHERE path=? OR path LIKE ?", (r["path"], r["path"] + os.sep + "%")).fetchall():
            ch.delete("folders", id=int(f["id"]))
    return {"removed": ids}


def _repath(ch, fid: int, old: Path, new: Path) -> None:
    c = cat()
    for f in c.db.execute("SELECT id, path FROM folders WHERE path=? OR path LIKE ?", (str(old), str(old) + os.sep + "%")).fetchall():
        p = str(new) + f["path"][len(str(old)):]
        ch.update("folders", int(f["id"]), path=p, name=Path(p).name)
    up = c.row("SELECT id FROM folders WHERE path=?", (str(new.parent),))
    ch.update("folders", int(fid), parent_id=int(up["id"]) if up else None)


def _recheck(root: Path) -> int:
    c = cat()
    found = 0
    with c.change("Check Files", undoable=False) as ch:
        for p in c.db.execute("SELECT p.id, p.file_name, f.path FROM photos p JOIN folders f ON f.id=p.folder_id WHERE f.path=? OR f.path LIKE ?", (str(root), str(root) + os.sep + "%")).fetchall():
            ok = (Path(p["path"]) / p["file_name"]).is_file()
            ch.update("photos", int(p["id"]), missing=0 if ok else 1)
            found += int(ok)
            previews.drop_source(int(p["id"]))
    return found


@command("folder.relocate", "Update Folder Location", {"id": {"type": "integer"}, "path": {"type": "string"}})
def folder_relocate(id: int, path: str) -> dict:
    c = cat()
    r = c.row("SELECT path FROM folders WHERE id=?", (int(id),))
    if r is None:
        raise CommandError("No such folder")
    new = Path(path).expanduser()
    if not new.is_dir():
        raise CommandError(f"No folder at {new}")
    other = c.row("SELECT id FROM folders WHERE path=?", (str(new),))
    if other and int(other["id"]) != int(id):
        raise CommandError(f"{new} is already a folder in this catalog")
    with c.change("Update Folder Location") as ch:
        _repath(ch, int(id), Path(r["path"]), new)
    return {"id": int(id), "path": str(new), "found": _recheck(new)}


@command("folder.move", "Move Folder", {"id": {"type": "integer"}, "into": {"type": "integer"}})
def folder_move(id: int, into: int) -> dict:
    c = cat()
    r = c.row("SELECT path FROM folders WHERE id=?", (int(id),))
    t = c.row("SELECT path FROM folders WHERE id=?", (int(into),))
    if r is None or t is None:
        raise CommandError("No such folder")
    old = Path(r["path"])
    new = Path(t["path"]) / old.name
    if new == old or str(new).startswith(str(old) + os.sep):
        raise CommandError("A folder cannot move inside itself")
    if new.exists():
        raise CommandError(f"{new} already exists")
    shutil.move(str(old), str(new))
    with c.change("Move Folder", undoable=False) as ch:
        _repath(ch, int(id), old, new)
    return {"id": int(id), "path": str(new)}


@command("photo.move", "Move Photos", {"ids": {"type": "array"}, "folder": {"type": "integer"}})
def photo_move(ids: Any = None, folder: int = 0) -> dict:
    pids = _ids(ids)
    c = cat()
    r = c.row("SELECT path FROM folders WHERE id=?", (int(folder),))
    if r is None:
        raise CommandError("No such folder")
    dest = Path(r["path"])
    if not dest.is_dir():
        raise CommandError(f"The folder {dest} is offline")
    masters = []
    for row in c.rows(f"SELECT id, master_id FROM photos WHERE id IN ({','.join('?' * len(pids))})", tuple(pids)):
        mid = int(row["master_id"] or row["id"])
        if mid not in masters:
            masters.append(mid)
    moved: list[int] = []
    skipped: list[int] = []
    with c.change("Move Photos", undoable=False) as ch:
        for mid in masters:
            m = c.row("SELECT p.file_name, f.path FROM photos p JOIN folders f ON f.id=p.folder_id WHERE p.id=?", (mid,))
            if m is None or Path(m["path"]) == dest:
                continue
            src = Path(m["path"]) / m["file_name"]
            if not src.is_file():
                skipped.append(mid)
                continue
            target = rename.unique(dest / src.name)
            shutil.move(str(src), str(target))
            side = metadata.sidecar_path(src)
            if side.is_file():
                shutil.move(str(side), str(metadata.sidecar_path(target)))
            for pid in [mid] + [int(v["id"]) for v in c.db.execute("SELECT id FROM photos WHERE master_id=?", (mid,)).fetchall()]:
                ch.update("photos", pid, folder_id=int(folder), file_name=target.name)
            moved.append(mid)
    return {"moved": moved, "skipped": skipped, "folder": str(dest)}


@command("library.labelNames", "Edit Color Label Set", {"names": {"type": "object"}})
def label_names(names: dict | None = None) -> dict:
    c = cat()
    if names:
        cur = c.get_meta("labelNames", {}) or {}
        cur.update({k: v for k, v in names.items() if k in LABELS})
        with c.change("Edit Color Label Set") as ch:
            ch.set_meta("labelNames", cur)
    return {"names": c.get_meta("labelNames", {})}


def _mount(path: str) -> str:
    p = Path(path)
    if os.name == "nt":
        return p.drive + "\\" if p.drive else p.anchor
    parts = p.parts
    if len(parts) > 2 and parts[1] == "Volumes":
        return str(Path(*parts[:3]))
    if len(parts) > 3 and parts[1] == "media":
        return str(Path(*parts[:4]))
    if len(parts) > 4 and parts[1] == "run" and parts[2] == "media":
        return str(Path(*parts[:5]))
    q = p
    while q != q.parent and not os.path.ismount(q):
        q = q.parent
    return str(q)


def _volume(mount: str) -> dict:
    if mount in ("/", ""):
        name = "Macintosh HD" if platform.system() == "Darwin" else "File System"
    elif os.name == "nt":
        name = f"Local Disk ({mount.rstrip(chr(92))})"
    else:
        name = Path(mount).name or mount
    try:
        du = shutil.disk_usage(mount)
        return {"mount": mount, "name": name, "free": du.free, "total": du.total, "online": True}
    except OSError:
        return {"mount": mount, "name": name, "free": 0, "total": 0, "online": False}


@command("folder.showParent", "Show Parent Folder", {"id": {"type": "integer"}})
def folder_show_parent(id: int) -> dict:
    c = cat()
    r = c.row("SELECT path FROM folders WHERE id=?", (int(id),))
    if r is None:
        raise CommandError("No such folder")
    up = Path(r["path"]).parent
    if up == Path(r["path"]):
        raise CommandError("This folder is already at the top of its volume")
    with c.change("Show Parent Folder") as ch:
        return {"id": c.folder_id(ch, up)}


@command("folder.hideParent", "Hide This Parent", {"id": {"type": "integer"}})
def folder_hide_parent(id: int) -> dict:
    c = cat()
    if c.row("SELECT id FROM folders WHERE id=?", (int(id),)) is None:
        raise CommandError("No such folder")
    if int(c.scalar("SELECT COUNT(*) FROM photos WHERE folder_id=?", (int(id),)) or 0):
        raise CommandError("This folder holds photos of its own, so it cannot be hidden")
    kids = [int(x["id"]) for x in c.rows("SELECT id FROM folders WHERE parent_id=?", (int(id),))]
    with c.change("Hide This Parent") as ch:
        for k in kids:
            ch.update("folders", k, parent_id=None)
        ch.delete("folders", id=int(id))
    return {"children": kids}


@command("library.tree", "Catalog Panels", mutates=False)
def tree() -> dict:
    c = cat()
    total = int(c.scalar("SELECT COUNT(*) FROM photos") or 0)
    folders = [{"id": int(r["id"]), "path": r["path"], "name": r["name"], "parent": r["parent_id"], "count": int(r["n"]),
                "missing": int(r["miss"] or 0), "online": Path(r["path"]).is_dir()}
               for r in c.rows("SELECT f.id, f.path, f.name, f.parent_id, COUNT(p.id) AS n, SUM(p.missing) AS miss FROM folders f LEFT JOIN photos p ON p.folder_id=f.id GROUP BY f.id ORDER BY f.path COLLATE NOCASE")]
    volumes: dict[str, dict] = {}
    for f in folders:
        if f["parent"] is None:
            f["volume"] = _mount(f["path"])
            volumes.setdefault(f["volume"], _volume(f["volume"]))
    cols = []
    for r in c.rows("SELECT c.*, (SELECT COUNT(*) FROM collection_photos cp WHERE cp.collection_id=c.id) AS n FROM collections c ORDER BY c.kind='set' DESC, c.name COLLATE NOCASE"):
        item = {"id": int(r["id"]), "name": r["name"], "kind": r["kind"], "parent": r["parent_id"], "count": int(r["n"]), "target": bool(r["target"]),
                "rules": records.loads(r["rules"], None), "settings": records.loads(r["settings"], None), "service": r["service_id"], "cover": r["cover_id"]}
        if r["kind"] == "smart":
            item["count"] = len(query.query(c, {"kind": "collection", "id": int(r["id"])}, stacks=False)["ids"])
        cols.append(item)
    kws = [{"id": int(r["id"]), "name": r["name"], "parent": r["parent_id"], "count": int(r["n"]), "synonyms": records.loads(r["synonyms"], []),
            "export": bool(r["export"]), "person": bool(r["person"])}
           for r in c.rows("SELECT k.*, (SELECT COUNT(*) FROM photo_keywords pk WHERE pk.keyword_id=k.id) AS n FROM keywords k ORDER BY k.name COLLATE NOCASE")]
    last = c.get_meta("lastImport", []) or []
    return {
        "catalog": {"name": c.path.stem, "path": str(c.path), "total": total, "previousImport": len(last),
                    "quick": int(c.scalar("SELECT COUNT(*) FROM collection_photos cp JOIN collections c ON c.id=cp.collection_id WHERE c.kind='quick'") or 0),
                    "missing": int(c.scalar("SELECT COUNT(*) FROM photos WHERE missing=1") or 0), "revision": c.revision},
        "folders": folders, "volumes": list(volumes.values()), "collections": cols, "keywords": kws, "labelNames": c.get_meta("labelNames", {}),
    }


@command("edit.undo", "Undo")
def undo() -> dict:
    label = cat().undo()
    if label is None:
        raise CommandError("Nothing to undo")
    return {"label": label}


@command("edit.redo", "Redo")
def redo() -> dict:
    label = cat().redo()
    if label is None:
        raise CommandError("Nothing to redo")
    return {"label": label}


def _switch_catalog(path: Path) -> dict:
    from app.core import prefs
    from app.develop import render as render_mod
    os.environ["FORMLIT_CATALOG"] = str(path)
    with previews._sources_lock:
        previews._sources.clear()
    with render_mod._stages_lock:
        render_mod._stages.clear()
    with SESSION.lock:
        SESSION.selection.clear()
        SESSION.active = None
    c = catalog_mod.reopen(path)
    from app.services import watch
    watch.restart()
    prefs.update({"catalog": str(path), "recentCatalogs": [str(path)] + [p for p in (prefs.load().get("recentCatalogs") or []) if p != str(path)][:7]})
    from app.engine import events
    events.publish("catalog.changed", path=str(path), name=path.stem)
    return {"path": str(path), "name": path.stem, "photos": int(c.scalar("SELECT COUNT(*) FROM photos") or 0)}


@command("catalog.open", "Open Catalog", {"path": {"type": "string"}})
def catalog_open(path: str) -> dict:
    p = Path(path).expanduser()
    if p.is_dir():
        found = sorted(p.glob("*.fldb"))
        if not found:
            raise CommandError(f"No formlit catalog (.fldb) in {p}")
        p = found[0]
    if p.suffix != ".fldb" or not p.is_file():
        raise CommandError(f"Not a formlit catalog: {p}. Catalogs end in .fldb", 404)
    return _switch_catalog(p.resolve())


@command("catalog.exportAs", "Export as Catalog", {"ids": {"type": "array"}, "folder": {"type": "string"}, "name": {"type": "string"},
                                                   "negatives": {"type": "boolean", "description": "copy the original files next to the new catalog"},
                                                   "previews": {"type": "boolean"}, "smart": {"type": "boolean", "description": "include smart previews"}, "wait": {"type": "boolean"}})
def catalog_export_as(folder: str, name: str = "Exported Catalog", ids: Any = None, negatives: bool = False, previews: bool = True, smart: bool = False,
                      wait: bool = False) -> dict:
    from app.services import catalog_io
    pids = _ids(ids)

    def job(progress):
        return catalog_io.export_catalog(pids, folder, name, negatives, previews, smart, progress)
    tid = tasks.start("catalogExport", "Exporting catalog", job)
    if wait:
        t = tasks.wait(tid)
        if t and t["state"] == "failed":
            raise CommandError(t["error"] or "Export as Catalog failed")
        return {"task": tid, **(t["result"] if t else {})}
    return {"task": tid}


@command("catalog.importFrom", "Import from Another Catalog", {"path": {"type": "string"}, "mode": {"type": "string", "enum": ["add", "copy"]},
                                                              "destination": {"type": "string"}, "replace": {"type": "boolean", "description": "update photos already here with the other catalog's settings and metadata"},
                                                              "wait": {"type": "boolean"}})
def catalog_import_from(path: str, mode: str = "add", destination: str = "", replace: bool = True, wait: bool = False) -> dict:
    from app.services import catalog_io

    def job(progress):
        r = catalog_io.import_catalog(path, mode, destination, replace, progress)
        from app.engine.cmd_ai import adapt
        adapt(r["added"])
        previews.warm(r["added"] + r["updated"])
        return r
    tid = tasks.start("catalogImport", "Importing from catalog", job)
    if wait:
        t = tasks.wait(tid)
        if t and t["state"] == "failed":
            raise CommandError(t["error"] or "Import from Catalog failed")
        return {"task": tid, **(t["result"] if t else {})}
    return {"task": tid}


@command("catalog.create", "New Catalog", {"folder": {"type": "string"}, "name": {"type": "string"}})
def catalog_create(folder: str, name: str = "formlit") -> dict:
    base = Path(folder).expanduser() / rename.safe(name or "formlit")
    target = base / f"{rename.safe(name or 'formlit')}.fldb"
    if target.exists():
        raise CommandError(f"A catalog already exists at {target}; open it instead")
    base.mkdir(parents=True, exist_ok=True)
    return _switch_catalog(target.resolve())


@command("library.buildSmartPreviews", "Build Smart Previews", {"ids": {"type": "array"}, "wait": {"type": "boolean"}})
def build_smart_previews(ids: Any = None, wait: bool = False) -> dict:
    pids = _ids(ids) if ids is not None else [int(r["id"]) for r in cat().rows("SELECT id FROM photos WHERE kind != 'video' AND missing=0")]

    def job(progress):
        done = []
        for i, pid in enumerate(pids):
            if progress.cancelled:
                break
            try:
                previews.source(pid)
                done.append(pid)
            except (FileNotFoundError, OSError, ValueError):
                continue
            progress(i + 1, len(pids), f"Smart preview {i + 1} of {len(pids)}")
        with cat().change("Build Smart Previews", undoable=False) as ch:
            for pid in done:
                ch.update("photos", pid, smart_preview=1)
        return {"built": len(done)}
    tid = tasks.start("smartPreviews", "Building smart previews", job)
    if not wait:
        return {"task": tid}
    t = tasks.wait(tid, 7200) or {}
    return {"task": tid, **(t.get("result") or {})}


@command("library.discardSmartPreviews", "Discard Smart Previews", {"ids": {"type": "array"}})
def discard_smart_previews(ids: Any = None) -> dict:
    pids = _ids(ids)
    with cat().change("Discard Smart Previews", undoable=False) as ch:
        for pid in pids:
            previews.drop_source(pid)
            ch.update("photos", pid, smart_preview=0)
    return {"ids": pids}


@command("autoImport.get", "Auto Import Settings", mutates=False)
def auto_import_get() -> dict:
    from app.services import watch
    return watch.settings()


@command("autoImport.set", "Auto Import Settings", {"enabled": {"type": "boolean"}, "watch": {"type": "string"}, "destination": {"type": "string"},
                                                    "folderTemplate": {"type": "string"}, "renameTemplate": {"type": "string"}, "keywords": {"type": "array"}, "preset": {"type": "string"}})
def auto_import_set(enabled: bool | None = None, watch: str | None = None, destination: str | None = None, folderTemplate: str | None = None,
                    renameTemplate: str | None = None, keywords: list[str] | None = None, preset: str | None = None) -> dict:
    from app.services import watch as watch_mod
    s = watch_mod.settings()
    for k, v in (("enabled", enabled), ("watch", watch), ("destination", destination), ("folderTemplate", folderTemplate), ("renameTemplate", renameTemplate),
                 ("keywords", keywords), ("preset", preset)):
        if v is not None:
            s[k] = v
    if s.get("enabled"):
        folder = Path(str(s.get("watch") or "")).expanduser()
        if not folder.is_dir():
            raise CommandError("Choose an existing folder to watch first")
        if s.get("destination") and Path(str(s["destination"])).expanduser().resolve() == folder.resolve():
            raise CommandError("The destination must differ from the watched folder")
    with cat().change("Auto Import Settings", undoable=False) as ch:
        ch.set_meta("autoImport", s)
    s["running"] = watch_mod.restart()
    return s


@command("tether.cameras", "Tethered Cameras", mutates=False)
def tether_cameras() -> dict:
    from app.services import tether
    return {"installed": bool(tether.binary()), "cameras": tether.cameras()}


@command("tether.start", "Start Tethered Capture", {"port": {"type": "string"}, "model": {"type": "string"}, "session": {"type": "string"}, "destination": {"type": "string"},
                                                    "renameTemplate": {"type": "string"}, "keywords": {"type": "array"}, "preset": {"type": "string"}, "collection": {"type": "integer"}})
def tether_start(port: str = "", model: str = "", session: str = "Tethered", destination: str = "", renameTemplate: str = "", keywords: list[str] | None = None,
                 preset: str = "", collection: int | None = None) -> dict:
    from app.services import tether
    try:
        return tether.start(port, model, {"session": session, "destination": destination, "renameTemplate": renameTemplate, "keywords": keywords or [], "preset": preset,
                                          "collection": collection})
    except RuntimeError as exc:
        raise CommandError(str(exc)) from exc


@command("tether.capture", "Capture", mutates=False)
def tether_capture() -> dict:
    from app.services import tether
    try:
        return tether.capture()
    except RuntimeError as exc:
        raise CommandError(str(exc)) from exc


@command("tether.stop", "Stop Tethered Capture", mutates=False)
def tether_stop() -> dict:
    from app.services import tether
    return tether.stop()


@command("tether.state", "Tethered Capture Status", mutates=False)
def tether_state() -> dict:
    from app.services import tether
    return tether.state()


@command("tether.liveView", "Live View Frame", mutates=False)
def tether_live() -> dict:
    import base64
    from app.services import tether
    try:
        data = tether.live()
    except RuntimeError as exc:
        raise CommandError(str(exc)) from exc
    if not data:
        raise CommandError("The camera sent no live view frame; not every camera supports live view over USB")
    return {"jpeg": base64.b64encode(data).decode("ascii")}


@command("tether.set", "Camera Setting", {"key": {"type": "string", "description": "iso, shutterspeed, aperture, whitebalance, exposurecompensation, imagequality"},
                                          "value": {"type": "string"}}, mutates=False)
def tether_set(key: str, value: str) -> dict:
    from app.services import tether
    try:
        return tether.set_config(str(key), str(value))
    except (RuntimeError, ValueError) as exc:
        raise CommandError(str(exc)) from exc


@command("tether.develop", "Tethered Develop Settings", {"preset": {"type": "string", "description": "a preset id or name, previous for Same as Previous, empty for none"}}, mutates=False)
def tether_develop(preset: str = "") -> dict:
    from app.services import tether
    try:
        return tether.set_preset(preset)
    except RuntimeError as exc:
        raise CommandError(str(exc)) from exc


@command("catalog.recent", "Recent Catalogs", mutates=False)
def catalog_recent() -> dict:
    from app.core import prefs
    return {"current": str(cat().path), "recent": [p for p in (prefs.load().get("recentCatalogs") or []) if Path(p).is_file()]}


@command("edit.history", "Undo History", mutates=False)
def edit_history() -> dict:
    c = cat()
    return {"undo": [e.label for e in c.undo_stack[-20:]], "redo": [e.label for e in c.redo_stack[-20:]]}


@command("library.buildPreviews", "Build Previews", {"ids": {"type": "array"}, "size": {"type": "string", "enum": ["thumb", "standard"]}})
def build_previews(ids: Any = None, size: str = "standard") -> dict:
    pids = _ids(ids) if ids is not None else [int(r["id"]) for r in cat().rows("SELECT id FROM photos")]
    tid = tasks.start("previews", "Building previews", lambda p: previews.build_all(pids, "p" if size == "standard" else "t", p))
    return {"task": tid, "count": len(pids)}


@command("task.cancel", "Cancel Task", {"id": {"type": "integer"}}, mutates=False)
def task_cancel(id: int) -> dict:
    return {"cancelled": tasks.cancel(int(id))}


@command("task.get", "Task Status", {"id": {"type": "integer"}}, mutates=False)
def task_get(id: int) -> dict:
    t = tasks.get(int(id))
    if t is None:
        raise CommandError("No such task", 404)
    return t


@command("library.stats", "Catalog Statistics", mutates=False)
def stats() -> dict:
    c = cat()
    return {"photos": int(c.scalar("SELECT COUNT(*) FROM photos") or 0), "raw": int(c.scalar("SELECT COUNT(*) FROM photos WHERE kind='raw'") or 0),
            "edited": int(c.scalar("SELECT COUNT(*) FROM photos WHERE edited=1") or 0), "picks": int(c.scalar("SELECT COUNT(*) FROM photos WHERE flag=1") or 0),
            "rejects": int(c.scalar("SELECT COUNT(*) FROM photos WHERE flag=-1") or 0), "keywords": int(c.scalar("SELECT COUNT(*) FROM keywords") or 0),
            "collections": int(c.scalar("SELECT COUNT(*) FROM collections") or 0), "revision": c.revision, "time": time.time()}
