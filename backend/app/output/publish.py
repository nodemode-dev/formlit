import ftplib
import posixpath
from pathlib import Path
from typing import Any, Callable

from app.engine import catalog as catalog_mod
from app.engine.catalog import now_iso
from app.engine.records import loads
from app.output import export, web

KINDS = {"folder": "Hard Drive", "ftp": "FTP Server"}


def services() -> list[dict]:
    cat = catalog_mod.get()
    out = []
    for r in cat.rows("SELECT * FROM publish_services ORDER BY name COLLATE NOCASE"):
        sid = int(r["id"])
        cols = []
        for c in cat.rows("SELECT id, name FROM collections WHERE kind='published' AND service_id=? ORDER BY name COLLATE NOCASE", (sid,)):
            cols.append(dict(status(int(c["id"])), id=int(c["id"]), name=c["name"]))
        st = loads(r["settings"], {})
        safe = {k: v for k, v in st.items() if k != "password"}
        out.append({"id": sid, "kind": r["kind"], "name": r["name"], "label": KINDS.get(r["kind"], r["kind"]), "settings": safe, "collections": cols})
    return out


def status(cid: int) -> dict:
    cat = catalog_mod.get()
    members = [int(r["photo_id"]) for r in cat.rows("SELECT photo_id FROM collection_photos WHERE collection_id=? ORDER BY position", (cid,))]
    pub = {int(r["photo_id"]): r for r in cat.rows("SELECT * FROM published WHERE collection_id=?", (cid,))}
    new, modified, done = [], [], []
    for pid in members:
        row = cat.row("SELECT develop_rev, edit_time FROM photos WHERE id=?", (pid,))
        if row is None:
            continue
        p = pub.get(pid)
        if p is None:
            new.append(pid)
        elif int(p["rev"]) != int(row["develop_rev"]) or (row["edit_time"] or "") > (p["time"] or ""):
            modified.append(pid)
        else:
            done.append(pid)
    removed = [pid for pid in pub if pid not in set(members)]
    return {"new": new, "modified": modified, "published": done, "removed": removed}


def _service(cid: int) -> tuple[dict, dict]:
    cat = catalog_mod.get()
    c = cat.row("SELECT * FROM collections WHERE id=? AND kind='published'", (cid,))
    if c is None:
        raise RuntimeError(f"No published collection {cid}")
    s = cat.row("SELECT * FROM publish_services WHERE id=?", (c["service_id"],))
    if s is None:
        raise RuntimeError("The collection has no publish service")
    return dict(s), dict(c)


def run(cid: int, progress: Callable[..., Any] | None = None) -> dict:
    cat = catalog_mod.get()
    svc, col = _service(cid)
    st = loads(svc["settings"], {})
    todo_state = status(cid)
    todo = todo_state["new"] + todo_state["modified"]
    settings = export.merged(st.get("export") or {})
    staging = Path(st.get("folder") or export.merged({})["destination"]["folder"]).expanduser() / col["name"]
    if svc["kind"] == "ftp":
        from app.core import config
        staging = config.temp_dir() / "publish" / str(cid)
    staging.mkdir(parents=True, exist_ok=True)
    settings["destination"].update(folder=str(staging), useSubfolder=False, sameAsOriginal=False, existing="overwrite", addToCatalog=False)
    pub = {int(r["photo_id"]): r for r in cat.rows("SELECT * FROM published WHERE collection_id=?", (cid,))}
    ftp = web._ftp(st) if svc["kind"] == "ftp" else None
    remote_root = posixpath.join(st.get("path") or "/", col["name"]) if ftp else ""
    if ftp:
        web._mkdirs(ftp, remote_root)
    done, failed = [], []
    try:
        for i, pid in enumerate(todo):
            try:
                old = pub.get(pid)
                path = export.export_one(pid, settings, i + 1, None)
                if path is None:
                    continue
                remote = str(path)
                if ftp:
                    remote = posixpath.join(remote_root, path.name)
                    with path.open("rb") as fh:
                        ftp.storbinary(f"STOR {remote}", fh)
                    path.unlink(missing_ok=True)
                if old is not None and old["remote"] and old["remote"] != remote:
                    _delete(ftp, old["remote"])
                rev = int(cat.scalar("SELECT develop_rev FROM photos WHERE id=?", (pid,)) or 0)
                with cat.change("Publish", undoable=False) as ch:
                    ch.delete("published", collection_id=cid, photo_id=pid)
                    ch.insert("published", collection_id=cid, photo_id=pid, rev=rev, remote=remote, time=now_iso())
                done.append(pid)
            except Exception as exc:
                failed.append({"id": pid, "error": str(exc)})
            if progress is not None:
                progress(i + 1, len(todo), f"Publishing {i + 1} of {len(todo)}")
        for pid in todo_state["removed"]:
            old = pub.get(pid)
            if old is not None and old["remote"]:
                _delete(ftp, old["remote"])
            with cat.change("Unpublish", undoable=False) as ch:
                ch.delete("published", collection_id=cid, photo_id=pid)
    finally:
        if ftp is not None:
            try:
                ftp.quit()
            except ftplib.all_errors:
                ftp.close()
    return {"published": done, "failed": failed, "removed": todo_state["removed"]}


def _delete(ftp: ftplib.FTP | None, remote: str) -> None:
    try:
        if ftp is not None:
            ftp.delete(remote)
        else:
            Path(remote).unlink(missing_ok=True)
    except (OSError, ftplib.all_errors):
        return
