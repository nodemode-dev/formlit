import json
import threading
from typing import Any

from app.core import config, seal

DEFAULTS: dict = {
    "editors": [],
    "editIn": {"format": "tiff", "space": "prophoto", "depth": 16, "ppi": 300, "naming": "{name}-Edit"},
    "slideshowMusic": "",
    "outsideAgents": "ask",
    "claudeFolder": "",
    "claudeBin": "",
    "codexBin": "",
    "cursorBin": "",
    "antigravityBin": "",
    "claudeFirstMessage": "",
}
CHOICES: dict[str, tuple] = {"outsideAgents": ("ask", "allowed", "blocked")}
_lock = threading.Lock()


def _path():
    return config.data_dir() / "preferences.json"


def _stored() -> dict:
    with _lock:
        try:
            data = json.loads(_path().read_text())
        except (OSError, ValueError):
            data = {}
    return data if isinstance(data, dict) else {}


def load() -> dict:
    out = json.loads(json.dumps(DEFAULTS))
    out.update(seal.effective(_stored()))
    return out


def update(values: dict[str, Any]) -> dict:
    for key, default in DEFAULTS.items():
        if key in values and values[key] is not None and type(values[key]) is not type(default):
            raise ValueError(f"preference {key} must be {type(default).__name__}")
    for key, choices in CHOICES.items():
        if key in values and values[key] not in choices:
            raise ValueError(f"preference {key} must be one of {', '.join(choices)}")
    values = {k: v for k, v in values.items() if k != seal.FIELD and k not in seal.REPORTS}
    stored = {**json.loads(json.dumps(DEFAULTS)), **_stored()}
    if any(k in values for k in seal.SEALED):
        current = seal.effective(stored)
        cur = seal.sign({**stored, **{k: current.get(k) for k in seal.SEALED}, **values})
    else:
        cur = {**stored, **values}
    with _lock:
        tmp = _path().with_suffix(".json.tmp")
        tmp.write_text(json.dumps(cur, indent=1))
        tmp.replace(_path())
    return load()
