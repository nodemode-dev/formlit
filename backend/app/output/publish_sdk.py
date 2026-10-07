import importlib
import importlib.util
import sys
import threading
from pathlib import Path
from types import ModuleType
from typing import Any

from app.core import config

API_VERSION = 1
BUILTIN = ("webdav", "s3")
RESERVED = {"folder": "Hard Drive", "ftp": "FTP Server"}
SECRET = {"password", "secret", "secretKey", "token", "apiKey"}

_lock = threading.Lock()
_plugins: dict[str, ModuleType] = {}
_errors: list[dict] = []
_loaded = False


def folder() -> Path:
    p = config.data_dir() / "Plugins"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _check(mod: ModuleType) -> dict:
    svc = getattr(mod, "SERVICE", None)
    if not isinstance(svc, dict) or not isinstance(svc.get("kind"), str) or not svc["kind"]:
        raise RuntimeError("SERVICE must be a dict with a kind")
    if not callable(getattr(mod, "connect", None)):
        raise RuntimeError("the plugin needs a connect(settings) function")
    if svc["kind"] in RESERVED:
        raise RuntimeError(f"kind {svc['kind']} is reserved")
    if int(svc.get("api", API_VERSION)) > API_VERSION:
        raise RuntimeError(f"written for plugin API {svc.get('api')}, formlit speaks {API_VERSION}")
    return svc


def _entries() -> list[Path]:
    out = []
    for p in sorted(folder().iterdir()):
        if p.name.startswith((".", "_")):
            continue
        if p.is_file() and p.suffix == ".py":
            out.append(p)
        elif p.is_dir() and (p / "__init__.py").is_file():
            out.append(p / "__init__.py")
    return out


def load(force: bool = False) -> None:
    global _loaded
    with _lock:
        if _loaded and not force:
            return
        _plugins.clear()
        _errors.clear()
        for name in BUILTIN:
            mod = importlib.import_module(f"app.output.services.{name}")
            _plugins[_check(mod)["kind"]] = mod
        for path in _entries():
            stem = path.parent.name if path.name == "__init__.py" else path.stem
            modname = f"formlit_plugin_{stem}"
            try:
                spec = importlib.util.spec_from_file_location(modname, path, submodule_search_locations=[str(path.parent)] if path.name == "__init__.py" else None)
                if spec is None or spec.loader is None:
                    raise RuntimeError("not a Python module")
                mod = importlib.util.module_from_spec(spec)
                sys.modules[modname] = mod
                spec.loader.exec_module(mod)
                svc = _check(mod)
                if svc["kind"] in _plugins:
                    raise RuntimeError(f"kind {svc['kind']} is already registered")
                setattr(mod, "__formlit_file__", str(path))
                _plugins[svc["kind"]] = mod
            except Exception as exc:
                sys.modules.pop(modname, None)
                _errors.append({"file": str(path), "error": f"{type(exc).__name__}: {exc}"})
        _loaded = True


def get(kind: str) -> ModuleType | None:
    load()
    return _plugins.get(kind)


def label(kind: str) -> str:
    if kind in RESERVED:
        return RESERVED[kind]
    mod = get(kind)
    return str(mod.SERVICE.get("label") or kind) if mod else f"{kind} (plug-in missing)"


def kinds() -> list[dict]:
    load()
    out: list[dict] = [{"kind": k, "label": v, "fields": [], "comments": False, "builtin": True} for k, v in RESERVED.items()]
    for k, mod in _plugins.items():
        s = mod.SERVICE
        out.append({"kind": k, "label": str(s.get("label") or k), "fields": list(s.get("fields") or []), "comments": bool(s.get("comments")), "builtin": k in BUILTIN, "help": str(s.get("help") or "")})
    return out


def plugins() -> dict:
    load()
    rows = []
    for k, mod in _plugins.items():
        s = mod.SERVICE
        rows.append({"kind": k, "label": str(s.get("label") or k), "version": str(s.get("version") or ""), "author": str(s.get("author") or ""), "url": str(s.get("url") or ""),
                     "description": str(s.get("description") or ""), "comments": bool(s.get("comments")), "builtin": k in BUILTIN, "file": getattr(mod, "__formlit_file__", "")})
    return {"plugins": rows, "errors": list(_errors), "folder": str(folder()), "api": API_VERSION}


def public(settings: dict) -> dict:
    return {k: v for k, v in settings.items() if k not in SECRET}


def keep_secrets(new: dict, old: dict) -> dict:
    out = dict(new)
    for k in SECRET:
        if k not in out and k in old:
            out[k] = old[k]
    return out


class Session:
    def __init__(self, kind: str, settings: dict):
        mod = get(kind)
        if mod is None:
            raise RuntimeError(f"No publish plug-in provides {kind}. Open File > Plug-in Manager to see what loaded.")
        self.mod = mod
        self.client: Any = mod.connect(dict(settings))

    def upload(self, path: Path, folders: list[str], photo: dict, old: str) -> str:
        return str(self.client.upload(path, list(folders), dict(photo), old or ""))

    def delete(self, remote: str) -> None:
        fn = getattr(self.client, "delete", None)
        if fn is not None and remote:
            fn(remote)

    def comments(self, remote: str) -> list[dict]:
        fn = getattr(self.client, "comments", None)
        return [dict(c) for c in fn(remote)] if fn is not None and remote else []

    def comment(self, remote: str, text: str) -> None:
        fn = getattr(self.client, "comment", None)
        if fn is None:
            raise RuntimeError("This service does not take comments")
        fn(remote, text)

    def close(self) -> None:
        fn = getattr(self.client, "close", None)
        if fn is not None:
            fn()
