import json
import os
import platform
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
                    "slideshow": "Slideshow", "web": "Web Gallery", "published": "Published Collection"}


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
              skipDuplicates: bool = True, recursive: bool = True, wait: bool = False, buildPreviews: str = "", backup: str = "") -> dict:
    dev = None
    if isinstance(develop, dict):
        dev = develop
    elif isinstance(develop, str) and develop:
        from app.engine import presets
        dev = presets.settings_of(develop)
    if mode not in ("add", "copy", "move"):
        raise CommandError("mode is add, copy or move")

    def job(progress):
        res = importer.import_files(paths, mode, destination, folderTemplate, renameTemplate, custom, dev, metadata, keywords, collection,
                                    skipDuplicates, recursive, progress, backup=backup)
        if buildPreviews in ("standard", "1:1") and res["ids"]:
            previews.build_all(res["ids"], "p", progress)
        return res
    tid = tasks.start("import", "Importing photos", job)
    if wait:
        t = tasks.wait(tid)
        if t and t["state"] == "failed":
            raise CommandError(t["error"] or "Import failed")
        return {"task": tid, **(t["result"] if t and t.get("result") else {})}
    return {"task": tid}


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


@command("photo.virtualCopy", "Create Virtual Copy", {"ids": {"type": "array"}})
def virtual_copy(ids: Any = None) -> dict:
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
            row.update(master_id=master, copy_name=f"Copy {n}", import_time=now_iso())
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
        for pid in pids:
            for table, col in (("photo_keywords", "photo_id"), ("collection_photos", "photo_id"), ("history", "photo_id"), ("snapshots", "photo_id"), ("faces", "photo_id")):
                ch.delete(table, **{col: pid})
            for vc in c.db.execute("SELECT id FROM photos WHERE master_id=?", (pid,)).fetchall():
                if int(vc["id"]) not in pids:
                    ch.update("photos", int(vc["id"]), master_id=None)
            ch.delete("photos", id=pid)
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
def relink(id: int, path: str) -> dict:
    c = cat()
    p = Path(path).expanduser()
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
    pids = _ids(ids)
    c = cat()
    written = []
    for pid in pids:
        d = records.detail(c, pid)
        if d is None or d.get("masterId"):
            continue
        rec = {"rating": d["r"], "label": d["l"], "meta": d["meta"], "keywords": d["keywords"], "captureTime": d["captureTime"],
               "develop": json.dumps(d["develop"], separators=(",", ":")) if d["develop"] else ""}
        try:
            metadata.write_sidecar(Path(d["path"]), rec)
            written.append(pid)
        except OSError as exc:
            raise CommandError(f"Could not write the XMP sidecar of {d['fileName']}: {exc}")
    if written:
        with c.change("Save Metadata", undoable=False) as ch:
            for pid in written:
                ch.update("photos", pid, sidecars=["xmp"])
    return {"ids": written}


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
        if kind not in ("set", "smart"):
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


@command("folder.synchronize", "Synchronize Folder", {"id": {"type": "integer"}, "importNew": {"type": "boolean"}})
def folder_sync(id: int, importNew: bool = True, removeMissing: bool = False) -> dict:
    c = cat()
    r = c.row("SELECT path FROM folders WHERE id=?", (int(id),))
    if r is None:
        raise CommandError("No such folder")
    found = find_missing()
    res: dict = {"missing": len(found["missing"])}
    if importNew:
        out = importer.import_files([r["path"]], "add", recursive=True)
        res["imported"] = out["count"]
    if removeMissing and found["missing"]:
        remove(found["missing"])
        res["removed"] = len(found["missing"])
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


@command("library.labelNames", "Edit Color Label Set", {"names": {"type": "object"}})
def label_names(names: dict | None = None) -> dict:
    c = cat()
    if names:
        cur = c.get_meta("labelNames", {}) or {}
        cur.update({k: v for k, v in names.items() if k in LABELS})
        with c.change("Edit Color Label Set") as ch:
            ch.set_meta("labelNames", cur)
    return {"names": c.get_meta("labelNames", {})}


@command("library.tree", "Catalog Panels", mutates=False)
def tree() -> dict:
    c = cat()
    total = int(c.scalar("SELECT COUNT(*) FROM photos") or 0)
    folders = [{"id": int(r["id"]), "path": r["path"], "name": r["name"], "parent": r["parent_id"], "count": int(r["n"]),
                "missing": int(r["miss"] or 0), "online": Path(r["path"]).is_dir()}
               for r in c.rows("SELECT f.id, f.path, f.name, f.parent_id, COUNT(p.id) AS n, SUM(p.missing) AS miss FROM folders f LEFT JOIN photos p ON p.folder_id=f.id GROUP BY f.id ORDER BY f.path COLLATE NOCASE")]
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
        "folders": folders, "collections": cols, "keywords": kws, "labelNames": c.get_meta("labelNames", {}),
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
