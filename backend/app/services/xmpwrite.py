import json
import threading
from pathlib import Path

from app.core import prefs
from app.engine import catalog as catalog_mod
from app.engine import events, records
from app.services import metadata, xmpembed

WATCH = {"rating", "flag", "label", "meta", "develop", "capture_time", "gps_lat", "gps_lon", "keywords"}
_lock = threading.Lock()
_pending: set[int] = set()
_timer: threading.Timer | None = None
_settings = {"auto": False, "embed": True}


def configure() -> None:
    p = prefs.load()
    _settings["auto"] = bool(p.get("autoWriteXmp", False))
    _settings["embed"] = bool(p.get("xmpIntoFiles", True))


def record_of(pid: int) -> tuple[Path, dict] | None:
    d = records.detail(catalog_mod.get(), pid)
    if d is None or d.get("masterId"):
        return None
    rec = {"rating": d["r"], "label": d["l"], "meta": d["meta"], "keywords": d["keywords"], "captureTime": d["captureTime"],
           "develop": json.dumps(d["develop"], separators=(",", ":")) if d["develop"] else ""}
    return Path(d["path"]), rec


def write(pid: int) -> str:
    got = record_of(pid)
    if got is None:
        return ""
    path, rec = got
    where = ""
    if _settings["embed"] and xmpembed.supports(path) and not metadata.sidecar_path(path).is_file():
        try:
            xmpembed.write(path, metadata.build_xmp(rec))
            where = "file"
        except (OSError, ValueError):
            where = ""
    if not where:
        metadata.write_sidecar(path, rec)
        where = "sidecar"
    target = path if where == "file" else metadata.sidecar_path(path)
    st = target.stat()
    fields = {"xmp_state": 0, "xmp_time": st.st_mtime, "sidecars": ["xmp"] if where == "sidecar" else []}
    if where == "file":
        fields.update(file_mtime=st.st_mtime, file_size=st.st_size)
    with catalog_mod.get().change("Save Metadata", undoable=False) as ch:
        ch.update("photos", pid, **fields)
    return where


def check(ids: list[int] | None = None) -> dict:
    c = catalog_mod.get()
    rows = c.rows("SELECT id FROM photos WHERE master_id IS NULL AND xmp_time > 0" + (f" AND id IN ({','.join('?' * len(ids))})" if ids else ""), tuple(ids or []))
    conflicts = []
    for r in rows:
        pid = int(r["id"])
        path = c.photo_path(pid)
        if path is None:
            continue
        side = metadata.sidecar_path(path)
        target = side if side.is_file() else path
        try:
            mtime = target.stat().st_mtime
        except OSError:
            continue
        t = float(c.scalar("SELECT xmp_time FROM photos WHERE id=?", (pid,)) or 0)
        if mtime > t + 2.0:
            conflicts.append(pid)
    if conflicts:
        with c.change("Metadata Changed on Disk", undoable=False) as ch:
            for pid in conflicts:
                ch.update("photos", pid, xmp_state=2)
    return {"conflicts": conflicts}


def synced(ids: list[int]) -> None:
    with _lock:
        _pending.difference_update(ids)
    c = catalog_mod.get()
    with c.change("Read Metadata", undoable=False) as ch:
        for pid in ids:
            path = c.photo_path(pid)
            if path is None:
                continue
            side = metadata.sidecar_path(path)
            target = side if side.is_file() else path
            try:
                ch.update("photos", pid, xmp_state=0, xmp_time=target.stat().st_mtime)
            except OSError:
                continue


def _on(kind: str, payload: dict) -> None:
    if kind != "photos.changed":
        return
    ids = [int(k) for k, f in (payload.get("photos") or {}).items() if WATCH & set(f)]
    if not ids:
        return
    global _timer
    with _lock:
        _pending.update(ids)
        if _timer is not None:
            _timer.cancel()
        _timer = threading.Timer(1.5, _flush)
        _timer.daemon = True
        _timer.start()


def _flush() -> None:
    with _lock:
        ids = sorted(_pending)
        _pending.clear()
    if not ids:
        return
    c = catalog_mod.get()
    stale = []
    for pid in ids:
        if _settings["auto"]:
            try:
                if write(pid):
                    continue
            except OSError:
                pass
        stale.append(pid)
    stale = [pid for pid in stale if c.scalar("SELECT xmp_state FROM photos WHERE id=? AND master_id IS NULL", (pid,)) == 0]
    if stale:
        with c.change("Metadata Needs Saving", undoable=False) as ch:
            for pid in stale:
                ch.update("photos", pid, xmp_state=1)


def start() -> None:
    configure()
    if not _settings.get("listening"):
        _settings["listening"] = True
        events.listen(_on)
    threading.Thread(target=lambda: check(None), name="formlit-xmp-check", daemon=True).start()
