import json
import threading
from typing import Any

from app.core import config

DEFAULTS: dict = {
    "editors": [],
    "editIn": {"format": "tiff", "space": "prophoto", "depth": 16, "ppi": 300, "naming": "{name}-Edit"},
    "slideshowMusic": "",
}
_lock = threading.Lock()


def _path():
    return config.data_dir() / "preferences.json"


def load() -> dict:
    with _lock:
        try:
            data = json.loads(_path().read_text())
        except (OSError, ValueError):
            data = {}
    out = json.loads(json.dumps(DEFAULTS))
    out.update(data if isinstance(data, dict) else {})
    return out


def update(values: dict[str, Any]) -> dict:
    cur = load()
    cur.update(values)
    with _lock:
        tmp = _path().with_suffix(".json.tmp")
        tmp.write_text(json.dumps(cur, indent=1))
        tmp.replace(_path())
    return cur
