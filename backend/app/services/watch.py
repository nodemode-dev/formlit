import threading
import time
from pathlib import Path

from app.engine import catalog as catalog_mod
from app.engine import events

DEFAULTS = {"enabled": False, "watch": "", "destination": "", "folderTemplate": "", "renameTemplate": "", "keywords": [], "preset": "", "interval": 2.0}
_thread: threading.Thread | None = None
_stop = threading.Event()
_sizes: dict[str, int] = {}
_ignored: set[str] = set()


def settings() -> dict:
    return {**DEFAULTS, **(catalog_mod.get().get_meta("autoImport", {}) or {})}


def _tick(s: dict) -> list[int]:
    from app.services import decode, importer
    watch = Path(s["watch"]).expanduser()
    if not watch.is_dir():
        return []
    ready = []
    for p in sorted(watch.iterdir()):
        if not p.is_file() or p.name.startswith(".") or not decode.supported(p) or str(p) in _ignored:
            continue
        size = p.stat().st_size
        if _sizes.get(str(p)) == size and size > 0:
            ready.append(str(p))
        _sizes[str(p)] = size
    if not ready:
        return []
    dev = None
    if s.get("preset"):
        from app.engine import presets
        try:
            dev = presets.settings_of(s["preset"])
        except Exception:
            dev = None
    dest = s.get("destination") or str(watch.parent / f"{watch.name} Imported")
    res = importer.import_files(ready, "move", dest, s.get("folderTemplate") or "", s.get("renameTemplate") or "", "", dev, None, s.get("keywords") or None, None, True, False)
    for p in ready:
        _sizes.pop(p, None)
        if Path(p).exists():
            _ignored.add(p)
    ids = [int(i) for i in res.get("ids") or []]
    if ids:
        events.publish("autoImport", ids=ids, count=len(ids))
    return ids


def _loop() -> None:
    while not _stop.is_set():
        s = settings()
        if not s.get("enabled"):
            break
        try:
            _tick(s)
        except Exception as exc:
            events.publish("autoImport", error=str(exc))
        _stop.wait(max(0.5, float(s.get("interval") or 2.0)))


def restart() -> bool:
    global _thread
    _stop.set()
    if _thread is not None and _thread.is_alive():
        _thread.join(timeout=5)
    _stop.clear()
    _sizes.clear()
    _ignored.clear()
    if not settings().get("enabled"):
        _thread = None
        return False
    _thread = threading.Thread(target=_loop, name="formlit-auto-import", daemon=True)
    _thread.start()
    return True


def stop() -> None:
    _stop.set()
