import hashlib
import os
import platform
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol
from urllib.parse import quote, unquote

from app.services import decode

PREFIX = "camera://"
CACHE_SECONDS = 5.0


class CameraError(RuntimeError):
    pass


@dataclass(frozen=True)
class Entry:
    name: str
    size: int
    mtime: float
    exact: bool = True


class Device(Protocol):
    id: str
    name: str
    backend: str

    def list_dir(self, folder: str) -> tuple[list[str], list[Entry]]: ...

    def fetch(self, file: str, dest: Path) -> Path: ...

    def delete(self, file: str) -> None: ...

    def thumbnail(self, file: str) -> bytes | None: ...


Provider = Callable[[], list[Device]]
_lock = threading.Lock()
_providers: list[Provider] | None = None
_cache: tuple[float, dict[str, Device]] = (0.0, {})


def safe_name(name: str) -> str:
    text = str(name)
    if not text.strip() or text in (".", "..") or ".." in text or any(ch in text for ch in "\\/:\x00"):
        raise CameraError(f"Refused a file name from the camera: {text!r}")
    return text


def _unsafe(name: str) -> bool:
    try:
        safe_name(name)
    except CameraError:
        return True
    return False


def inside(path: Path, folder: Path) -> Path:
    root = folder.resolve()
    full = path.resolve()
    if full.parent != root:
        raise CameraError(f"Refused a file outside the import folder: {path}")
    return full


def arrived(folder: Path, name: str) -> Path:
    raw = folder / safe_name(name)
    target = inside(raw, folder)
    if raw.is_symlink() or not target.is_file():
        raise CameraError(f"{name} did not arrive from the camera")
    return target


def short_id(backend: str, key: str) -> str:
    return f"{backend}-{hashlib.blake2b(key.encode('utf-8'), digest_size=5).hexdigest()}"


def _default_providers() -> list[Provider]:
    system = platform.system()
    if system == "Windows":
        from app.services.cameras import wpd
        return [wpd.devices]
    from app.services.cameras import gphoto
    return [gphoto.devices]


def set_providers(providers: list[Provider] | None) -> list[Provider] | None:
    global _providers, _cache
    with _lock:
        old = _providers
        _providers = providers
        _cache = (0.0, {})
    return old


def devices(refresh: bool = False) -> dict[str, Device]:
    global _cache
    with _lock:
        stamp, found = _cache
        if not refresh and found is not None and time.monotonic() - stamp < CACHE_SECONDS:
            return dict(found)
        providers = _providers if _providers is not None else _default_providers()
    fresh: dict[str, Device] = {}
    for provider in providers:
        try:
            for dev in provider():
                fresh[dev.id] = dev
        except (CameraError, OSError):
            continue
    with _lock:
        _cache = (time.monotonic(), fresh)
    return dict(fresh)


def device(dev_id: str) -> Device:
    found = devices().get(dev_id) or devices(refresh=True).get(dev_id)
    if found is None:
        raise CameraError("The camera is no longer connected. Connect it again, turn it on and choose it under Source")
    return found


def is_camera(path: str) -> bool:
    return str(path).startswith(PREFIX)


def path_for(dev_id: str, rel: str) -> str:
    clean = "/".join(p for p in rel.split("/") if p)
    return f"{PREFIX}{dev_id}/{quote(clean, safe='/')}"


def parse(path: str) -> tuple[str, str]:
    if not is_camera(path):
        raise CameraError(f"Not a camera path: {path}")
    rest = str(path)[len(PREFIX):]
    dev_id, _, rel = rest.partition("/")
    parts = [p for p in unquote(rel).split("/") if p]
    if not dev_id or any(p in (".", "..") for p in parts):
        raise CameraError(f"Not a camera path: {path}")
    return dev_id, "/".join(parts)


def _join(folder: str, name: str) -> str:
    return f"{folder}/{name}" if folder else name


def gvfs_mounts() -> list[dict]:
    if platform.system() != "Linux":
        return []
    base = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}") / "gvfs"
    try:
        children = sorted(base.iterdir()) if base.is_dir() else []
    except OSError:
        return []
    out = []
    for child in children:
        if child.name.startswith(("mtp:", "gphoto2:")) and child.is_dir():
            label = unquote(child.name.split("host=", 1)[-1]).replace("_", " ").strip() or child.name
            out.append({"name": label, "path": str(child), "kind": "camera"})
    return out


def roots() -> list[dict]:
    found = [{"name": dev.name, "path": path_for(dev.id, ""), "kind": "camera"} for dev in devices().values()]
    return found + gvfs_mounts()


def crumbs(path: str) -> list[dict]:
    dev_id, rel = parse(path)
    dev = devices().get(dev_id)
    parts = [p for p in rel.split("/") if p]
    head = [{"name": dev.name if dev else "Camera", "path": path_for(dev_id, "")}]
    return head + [{"name": p, "path": path_for(dev_id, "/".join(parts[:i + 1]))} for i, p in enumerate(parts)]


def listing(path: str) -> dict:
    dev_id, rel = parse(path)
    dev = device(dev_id)
    dirs, entries = dev.list_dir(rel)
    parent = path_for(dev_id, rel.rsplit("/", 1)[0] if "/" in rel else "") if rel else None
    files = [{"name": e.name, "path": path_for(dev_id, _join(rel, e.name)), "size": e.size, "mtime": e.mtime, "kind": decode.kind_of(Path(e.name))}
             for e in entries if decode.supported(Path(e.name))]
    return {"path": path_for(dev_id, rel), "parent": parent, "dirs": [{"name": d, "path": path_for(dev_id, _join(rel, d))} for d in dirs],
            "files": files, "crumbs": crumbs(path), "camera": True}


def walk(paths: list[str], recursive: bool = True, limit: int = 200_000) -> list[tuple[Device, str, Entry]]:
    out: list[tuple[Device, str, Entry]] = []
    seen: set[str] = set()
    for raw in paths:
        dev_id, rel = parse(raw)
        dev = device(dev_id)
        folder, _, name = rel.rpartition("/")
        if name and decode.supported(Path(name)):
            entry = next((e for e in dev.list_dir(folder)[1] if e.name == name), None)
            if entry is None:
                raise CameraError(f"{name} is no longer on the camera")
            key = path_for(dev.id, rel)
            if key not in seen:
                seen.add(key)
                out.append((dev, rel, entry))
            continue
        pending = [rel]
        while pending and len(out) < limit:
            here = pending.pop(0)
            dirs, entries = dev.list_dir(here)
            for e in entries:
                key = path_for(dev.id, _join(here, e.name))
                if decode.supported(Path(e.name)) and (not e.name.startswith(".") or _unsafe(e.name)) and key not in seen:
                    seen.add(key)
                    out.append((dev, _join(here, e.name), e))
            if recursive:
                pending.extend(_join(here, d) for d in dirs if not d.startswith("."))
    return out[:limit]


def thumbnail(path: str) -> bytes | None:
    dev_id, rel = parse(path)
    return device(dev_id).thumbnail(rel)
