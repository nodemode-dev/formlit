import base64
import binascii
import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any

from app.core import config
from app.engine import catalog as catalog_mod
from app.engine import events, records
from app.engine.commands import SESSION, CommandError, command, dispatch
from app.services import formext_host as fx

PRODUCT = "formlit"
FILES_BASE = "/api/extensions/files"
MANAGE_URL = f"formai://extensions?product={PRODUCT}"
STAYS_WITH_PERSON = {"photo.delete", "folder.remove", "catalog.open", "catalog.create", "agents.respond"}
WINDOW_GROUPS = {"terminal", "claudecode", "chat", "extensions"}
MAX_PHOTOS = 500
MAX_SAVE = 200 * 1024 * 1024
FLAGS = {1: "pick", -1: "reject"}
WHAT = ("summary", "selection", "photo", "catalog")

_lock = threading.Lock()
_cache: dict[str, Any] = {"stamp": None, "list": []}
_waiting: dict[str, dict] = {}


def stamp() -> str:
    a, b = fx.stamp(PRODUCT)
    return f"{a:.6f}:{b:.6f}"


def resolved(force: bool = False) -> list[fx.Extension]:
    now = stamp()
    with _lock:
        if force or _cache["stamp"] != now:
            _cache["list"] = fx.resolve(PRODUCT, config.VERSION, config.APP_NAME)
            _cache["stamp"] = now
        return list(_cache["list"])


def listing(force: bool = False) -> dict:
    found = resolved(force)
    return {"product": PRODUCT, "app": config.APP_NAME, "appVersion": config.VERSION, "api": fx.API, "stamp": _cache["stamp"],
            "root": str(fx.portal_root()), "extensions": [e.public(FILES_BASE) for e in found]}


def allowed(cid: str) -> None:
    if cid.split(".")[0] in WINDOW_GROUPS or cid in STAYS_WITH_PERSON:
        raise CommandError(f"{cid} stays with the person in formlit's window", 403)


@command("extensions.list", "Extensions", {"reload": {"type": "boolean"}}, mutates=False,
         description="The extensions formlit found in FormPortal's enabled.json and form.ext's dev.json, with each refusal's reason.")
def list_extensions(reload: bool = False) -> dict:
    return listing(reload)


def _split_time(t: str | None) -> tuple[str | None, str | None]:
    if t and len(t) > 19:
        return t[:19], t[19:]
    return t, None


def _record(d: dict) -> dict:
    t, offset = _split_time(d.get("captureTime"))
    gps = {"lat": d["gpsLat"], "lon": d["gpsLon"], "alt": d["gpsAlt"], "dir": d["gpsDir"]} if d.get("gpsLat") is not None else None
    return {"id": d["id"], "file": d["fileName"], "path": d["path"], "kind": d["kind"], "format": d["fmt"], "width": d["w"], "height": d["h"],
            "captureTime": t, "offset": offset, "camera": d["camera"], "lens": d["lens"], "focal": d["focal"], "aperture": d["aperture"],
            "shutter": d["shutter"], "iso": d["iso"], "gps": gps, "rating": d["r"], "flag": FLAGS.get(int(d["f"] or 0), "none"),
            "label": d["l"] or "", "edited": bool(d["e"]), "keywords": d["keywords"]}


def _short(r: dict) -> dict:
    return {k: r[k] for k in ("id", "file", "captureTime", "offset", "rating", "flag", "label", "gps")}


@command("extensions.document", "Extension Document Snapshot",
         {"what": {"type": "string", "enum": list(WHAT)}, "ids": {"type": "array"}, "active": {"type": "integer"}, "module": {"type": "string"}, "source": {"type": "object"}},
         mutates=False, description="What document.read returns to an extension: summary, selection, photo or catalog.")
def document(what: str = "summary", ids: list[int] | None = None, active: int | None = None, module: str | None = None, source: dict | None = None) -> dict:
    cat = catalog_mod.get()
    with SESSION.lock:
        sel = [int(i) for i in (ids if ids is not None else SESSION.selection)]
        act = int(active) if active is not None else SESSION.active
        mod = module or SESSION.module
        src = source if source is not None else SESSION.source
    if what == "summary":
        a = records.detail(cat, act) if act is not None else None
        return {"what": what, "catalog": {"name": cat.path.stem, "path": str(cat.path), "photos": int(cat.scalar("SELECT COUNT(*) FROM photos") or 0)},
                "module": mod, "source": src, "selection": sel[:1000], "selectionCount": len(sel), "active": _short(_record(a)) if a else None, "revision": cat.revision}
    if what == "selection":
        pick = sel or ([act] if act is not None else [])
        out = [_record(d) for d in (records.detail(cat, pid) for pid in pick[:MAX_PHOTOS]) if d]
        return {"what": what, "photos": out, "count": len(pick), "truncated": len(pick) > MAX_PHOTOS}
    if what == "photo":
        pid = act if act is not None else (sel[0] if sel else None)
        d = records.detail(cat, pid) if pid is not None else None
        if d is None:
            return {"what": what, "photo": None}
        return {"what": what, "photo": {**_record(d), "meta": d["meta"], "exif": d["exif"], "develop": d["develop"], "collections": d["collections"],
                                        "history": d["history"], "masterId": d["masterId"], "copyName": d["copyName"], "stackId": d["stackId"], "missing": d["missing"]}}
    t = dispatch("library.tree")
    return {"what": what, "catalog": t.get("catalog"),
            "folders": [{k: f[k] for k in ("id", "path", "name", "parent", "count")} for f in t.get("folders", [])],
            "collections": [{k: c[k] for k in ("id", "name", "kind", "parent", "count")} for c in t.get("collections", []) if c["kind"] != "quick"],
            "keywords": [{"id": k["id"], "name": k["name"], "parent": k["parent"], "count": k["count"]} for k in t.get("keywords", [])]}


@command("extensions.apply", "Extension Changes", {"label": {"type": "string"}, "ops": {"type": "array"}},
         description="Runs an extension's ops (engine commands with their args) in order as one undo step named label.")
def apply(label: str = "Extension", ops: list | None = None) -> dict:
    if not isinstance(ops, list) or not ops or any(not isinstance(o, dict) or not isinstance(o.get("command"), str) for o in ops):
        raise CommandError("ops must be a list of { command, args }")
    for o in ops:
        allowed(o["command"])
        if o.get("args") is not None and not isinstance(o["args"], dict):
            raise CommandError(f"{o['command']}: args must be an object")
    cat = catalog_mod.get()
    with _lock:
        start = len(cat.undo_stack)
        results = []
        try:
            for o in ops:
                results.append(dispatch(o["command"], o.get("args") or {}))
        except Exception:
            while len(cat.undo_stack) > start:
                cat.undo()
                cat.redo_stack.pop()
            raise
        with cat.lock:
            entries = cat.undo_stack[start:]
            del cat.undo_stack[start:]
            cat.push_undo(str(label or "Extension")[:80], [op for e in entries for op in e.ops])
    return {"applied": len(results), "results": results}


def _free_name(folder: Path, name: str) -> Path:
    target = folder / name
    stem, suffix = Path(name).stem, Path(name).suffix
    n = 2
    while target.exists():
        target = folder / f"{stem} {n}{suffix}"
        n += 1
    return target


@command("extensions.saveFile", "Save Extension File", {"folder": {"type": "string"}, "name": {"type": "string"}, "data": {"type": "string"}},
         description="Writes an extension's files.save data (base64) into a folder the person chose; an existing file is never replaced.")
def save_file(folder: str, name: str, data: str) -> dict:
    where = Path(folder).expanduser()
    if not where.is_absolute() or not where.is_dir():
        raise CommandError(f"{folder} is not a folder")
    clean = Path(str(name).replace("\\", "/")).name.strip()
    if not clean or clean.startswith("."):
        raise CommandError("the file needs a name")
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise CommandError("data is not base64") from None
    if len(raw) > MAX_SAVE:
        raise CommandError("the file is larger than 200 MB")
    target = _free_name(where, clean)
    tmp = target.with_name(target.name + ".part")
    tmp.write_bytes(raw)
    os.replace(tmp, target)
    return {"saved": True, "name": target.name, "path": str(target)}


@command("extensions.manage", "Manage in FormPortal", mutates=False, description="Opens FormPortal's extensions page for formlit.")
def manage() -> dict:
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return {"url": MANAGE_URL, "opened": False, "error": "no desktop session"}
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", MANAGE_URL])
        elif sys.platform == "win32":
            os.startfile(MANAGE_URL)
        else:
            subprocess.Popen(["xdg-open", MANAGE_URL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        return {"url": MANAGE_URL, "opened": False, "error": str(exc)}
    return {"url": MANAGE_URL, "opened": True}


def ask_window(kind: str, timeout: float, **payload: Any) -> Any:
    rid = uuid.uuid4().hex
    slot: dict[str, Any] = {"done": threading.Event(), "reply": None}
    _waiting[rid] = slot
    try:
        events.publish("extensions.request", request=rid, kind=kind, **payload)
        if not slot["done"].wait(timeout):
            raise CommandError("formlit's window did not answer. Open formlit, then try again.", 504)
    finally:
        _waiting.pop(rid, None)
    reply = slot["reply"] or {}
    if reply.get("error"):
        raise CommandError(str(reply["error"]), 409)
    return reply.get("result")


def _windows() -> int:
    return len(events._subscribers)


@command("extensions.agentList", "Extensions for Agents", mutates=False,
         description="id, name, version, source, state and commands of every extension; the state comes from the window when it is open.")
def agent_list() -> dict:
    if _windows():
        try:
            return {"window": True, "extensions": ask_window("list", 5)}
        except CommandError:
            pass
    rows = [e.public(FILES_BASE) for e in resolved()]
    return {"window": False, "note": "formlit's window is not open, so permissions are not known and commands cannot run.",
            "extensions": [{"id": r["id"], "name": r["name"], "version": r["version"], "source": r["source"], "state": r["state"], "reason": r["reason"],
                            "commands": r["commands"]} for r in rows]}


@command("extensions.run", "Run Extension Command", {"id": {"type": "string"}, "command": {"type": "string"}, "args": {"type": "object"}},
         description="Runs an extension's contributed command in formlit's window, with the same consent as the menu.")
def run(id: str, command: str, args: dict | None = None) -> Any:
    ext = next((e for e in resolved() if e.id == id), None)
    if ext is None:
        raise CommandError(f"No extension {id}", 404)
    if ext.state != "ready":
        raise CommandError(f"{ext.name} is refused: {ext.reason}", 409)
    if not any(c["id"] == command for c in ext.commands):
        raise CommandError(f"{ext.name} has no command {command}", 404)
    if not _windows():
        raise CommandError("Extensions run in formlit's window, and it is not open. Open formlit, then try again.", 409)
    return {"id": id, "command": command, "result": ask_window("command", 150, id=id, command=command, args=args or {})}


@command("extensions.reply", "Extension Reply", {"request": {"type": "string"}}, mutates=False, description="The window's answer to an agent's extensions request.")
def reply(request: str, result: Any = None, error: str | None = None) -> dict:
    slot = _waiting.get(request)
    if slot is None:
        return {"waiting": False}
    slot["reply"] = {"result": result, "error": error}
    slot["done"].set()
    return {"waiting": True}
