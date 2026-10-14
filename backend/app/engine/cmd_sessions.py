import json
import shutil
import threading
import time
from pathlib import Path
from typing import Any

from app.core import prefs
from app.engine import catalog as catalog_mod
from app.engine import events, records
from app.engine.commands import CommandError, command, resolve_ids

FOLDERS = {"capture": "Capture", "selects": "Selects", "output": "Output", "trash": "Trash"}
SUFFIX = ".flsession"
_lock = threading.Lock()
_written: dict[int, tuple[str, str]] = {}
_saver: threading.Thread | None = None


def cat():
    return catalog_mod.get()


def _manifest(root: Path) -> Path | None:
    found = sorted(root.glob(f"*{SUFFIX}"))
    return found[0] if found else None


def active_root() -> Path | None:
    p = (prefs.load().get("session") or {}).get("path")
    if not p:
        return None
    root = Path(p)
    return root if root.is_dir() and _manifest(root) else None


def output_folder() -> Path | None:
    root = active_root()
    return root / _names(root)["output"] if root else None


def _names(root: Path) -> dict[str, str]:
    m = _manifest(root)
    try:
        got = json.loads(m.read_text()).get("folders") if m else None
    except (OSError, ValueError):
        got = None
    return {**FOLDERS, **(got if isinstance(got, dict) else {})}


def _settings_file(root: Path, photo: Path) -> Path:
    return root / ".formlit" / "settings" / (str(photo.relative_to(root)) + ".json")


def _session_rows(root: Path) -> list:
    like = str(root.resolve()).rstrip("/") + "/%"
    return cat().rows("SELECT p.id, p.file_name, p.develop, p.rating, p.flag, p.label, p.meta, f.path FROM photos p JOIN folders f ON f.id=p.folder_id "
                      "WHERE p.master_id IS NULL AND (f.path=? OR f.path LIKE ?)", (str(root.resolve()), like))


def save(root: Path | None = None, force: bool = False) -> int:
    root = root or active_root()
    if root is None:
        return 0
    n = 0
    with _lock:
        for r in _session_rows(root):
            photo = Path(r["path"]) / r["file_name"]
            key = (str(photo), f"{r['develop']}|{r['rating']}|{r['flag']}|{r['label']}|{r['meta']}")
            if not force and _written.get(int(r["id"])) == key:
                continue
            try:
                out = _settings_file(root, photo)
            except ValueError:
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            data = {"format": "formlit-settings", "version": 1, "file": r["file_name"], "develop": records.loads(r["develop"], {}),
                    "rating": r["rating"], "flag": r["flag"], "label": r["label"], "meta": records.loads(r["meta"], {})}
            tmp = out.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, indent=1, sort_keys=True))
            tmp.replace(out)
            _written[int(r["id"])] = key
            n += 1
    return n


def _loop() -> None:
    while True:
        time.sleep(5)
        try:
            save()
        except Exception:
            pass


def _ensure_saver() -> None:
    global _saver
    if _saver is None or not _saver.is_alive():
        _saver = threading.Thread(target=_loop, name="session-saver", daemon=True)
        _saver.start()


def _register(root: Path) -> dict[str, int]:
    names = _names(root)
    ids = {}
    with cat().change("Open Session", undoable=False) as ch:
        for k, sub in names.items():
            (root / sub).mkdir(parents=True, exist_ok=True)
            ids[k] = cat().folder_id(ch, root / sub)
    return ids


def _restore(root: Path, pids: list[int]) -> list[int]:
    from app.engine.cmd_develop import after, store
    done = []
    with cat().change("Session Settings", undoable=False) as ch:
        for pid in pids:
            r = cat().row("SELECT p.develop, p.file_name, f.path FROM photos p JOIN folders f ON f.id=p.folder_id WHERE p.id=?", (pid,))
            if r is None or records.loads(r["develop"], {}):
                continue
            try:
                data = json.loads(_settings_file(root, Path(r["path"]) / r["file_name"]).read_text())
            except (OSError, ValueError):
                continue
            if isinstance(data.get("develop"), dict) and data["develop"]:
                store(ch, pid, data["develop"], "Session Settings", history=False)
            fields = {k: data[k] for k in ("rating", "flag", "label") if data.get(k) is not None}
            if isinstance(data.get("meta"), dict) and data["meta"]:
                fields["meta"] = data["meta"]
            if fields:
                ch.update("photos", pid, **fields)
            done.append(pid)
    if done:
        after(done)
    return done


def _activate(root: Path) -> None:
    rec = [str(root)] + [p for p in prefs.load().get("sessionRecent", []) if p != str(root)]
    prefs.update({"session": {"path": str(root)}, "sessionRecent": rec[:10]})
    _written.clear()
    _ensure_saver()
    events.publish("session", state="open", path=str(root))


def _state() -> dict:
    root = active_root()
    recent = [p for p in prefs.load().get("sessionRecent", []) if Path(p).is_dir()]
    if root is None:
        return {"active": None, "recent": recent}
    names = _names(root)
    folders = {}
    for k, sub in names.items():
        path = (root / sub).resolve()
        r = cat().row("SELECT id FROM folders WHERE path=?", (str(path),))
        n = cat().scalar("SELECT COUNT(*) FROM photos p JOIN folders f ON f.id=p.folder_id WHERE f.path=? AND p.master_id IS NULL", (str(path),)) or 0
        if k == "output" and path.is_dir():
            n = max(int(n), sum(1 for f in path.iterdir() if f.is_file() and not f.name.startswith(".") and f.suffix.lower() not in (".xmp", ".json")))
        folders[k] = {"name": sub, "path": str(path), "id": int(r["id"]) if r else None, "count": int(n)}
    m = _manifest(root)
    return {"active": {"name": m.stem if m else root.name, "path": str(root), "folders": folders}, "recent": recent}


@command("session.state", "Session", mutates=False)
def session_state() -> dict:
    if active_root() is not None:
        _ensure_saver()
    return _state()


@command("session.new", "New Session", {"parent": {"type": "string", "description": "folder to make the session in"}, "name": {"type": "string"}})
def session_new(parent: str, name: str) -> dict:
    name = name.strip().strip("/\\")
    if not name or any(c in name for c in '<>:"|?*'):
        raise CommandError("Give the session a name without < > : \" | ? *")
    base = Path(parent).expanduser()
    if not base.is_dir():
        raise CommandError(f"The folder {base} does not exist")
    root = base / name
    if root.exists() and any(root.iterdir()):
        raise CommandError(f"{root} already exists and is not empty; open it as a session instead")
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{name}{SUFFIX}").write_text(json.dumps({"format": "formlit-session", "version": 1, "name": name, "created": catalog_mod.now_iso(), "folders": FOLDERS}, indent=1))
    _register(root)
    _activate(root)
    return _state()


@command("session.open", "Open Session", {"path": {"type": "string", "description": "the session folder or its .flsession file"}})
def session_open(path: str) -> dict:
    from app.services import importer
    p = Path(path).expanduser()
    root = p.parent if p.suffix == SUFFIX else p
    if not root.is_dir():
        raise CommandError(f"No session at {root}")
    if _manifest(root) is None:
        if not all((root / sub).is_dir() for sub in ("Capture", "Selects")):
            raise CommandError(f"{root} is not a session (no {SUFFIX} file and no Capture and Selects folders)")
        (root / f"{root.name}{SUFFIX}").write_text(json.dumps({"format": "formlit-session", "version": 1, "name": root.name, "created": catalog_mod.now_iso(), "folders": FOLDERS}, indent=1))
    prev = active_root()
    if prev is not None and prev != root:
        save(prev)
    _register(root)
    names = _names(root)
    res = importer.import_files([str(root / names[k]) for k in ("capture", "selects", "output")], "add", "", "", "", "", None, None, None, None, True, True)
    restored = _restore(root, [int(r["id"]) for r in _session_rows(root)])
    _activate(root)
    return {**_state(), "imported": len(res.get("ids") or []), "restored": len(restored)}


@command("session.close", "Close Session")
def session_close() -> dict:
    root = active_root()
    if root is not None:
        save(root)
    prefs.update({"session": {}})
    events.publish("session", state="closed")
    return _state()


@command("session.save", "Save Session Settings", {"all": {"type": "boolean", "description": "rewrite every settings file, not only changed ones"}})
def session_save(all: bool = False) -> dict:
    root = active_root()
    if root is None:
        raise CommandError("No session is open")
    return {"written": save(root, force=bool(all)), "folder": str(root / ".formlit" / "settings")}


def _move(ids: Any, to: str, label: str) -> dict:
    from app.engine.cmd_library import photo_move
    root = active_root()
    if root is None:
        raise CommandError("No session is open")
    st = _state()["active"]["folders"]
    fid = st[to]["id"]
    if fid is None:
        raise CommandError(f"The session's {st[to]['name']} folder is not in the catalog")
    pids = resolve_ids(ids)
    before = {}
    for pid in pids:
        r = cat().row("SELECT f.path, p.file_name FROM photos p JOIN folders f ON f.id=p.folder_id WHERE p.id=?", (pid,))
        if r:
            before[pid] = Path(r["path"]) / r["file_name"]
    res = photo_move(pids, fid)
    for pid, old in before.items():
        r = cat().row("SELECT f.path, p.file_name FROM photos p JOIN folders f ON f.id=p.folder_id WHERE p.id=?", (pid,))
        if r is None:
            continue
        try:
            src, dst = _settings_file(root, old), _settings_file(root, Path(r["path"]) / r["file_name"])
        except ValueError:
            continue
        if src.is_file() and src != dst:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
    save(root)
    events.publish("session", state="moved", to=to)
    return {**res, "to": st[to]["name"]}


@command("session.select", "Move to Selects", {"ids": {"type": "array"}})
def session_select(ids: Any = None) -> dict:
    return _move(ids, "selects", "Move to Selects")


@command("session.trash", "Move to Session Trash", {"ids": {"type": "array"}})
def session_trash(ids: Any = None) -> dict:
    return _move(ids, "trash", "Move to Session Trash")


@command("session.restore", "Move Back to Capture", {"ids": {"type": "array"}})
def session_restore(ids: Any = None) -> dict:
    return _move(ids, "capture", "Move Back to Capture")
