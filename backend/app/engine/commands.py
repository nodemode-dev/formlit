import inspect
import math
import threading
from dataclasses import dataclass, field
from typing import Any, Callable


class CommandError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass
class Spec:
    id: str
    label: str
    fn: Callable[..., Any]
    params: dict[str, dict] = field(default_factory=dict)
    group: str = ""
    mutates: bool = True
    description: str = ""


REGISTRY: dict[str, Spec] = {}


def command(cid: str, label: str, params: dict[str, dict] | None = None, group: str = "", mutates: bool = True, description: str = "") -> Callable:
    def wrap(fn: Callable) -> Callable:
        if cid in REGISTRY:
            raise RuntimeError(f"command registered twice: {cid}")
        REGISTRY[cid] = Spec(cid, label, fn, params or {}, group or cid.split(".")[0], mutates, description or label)
        return fn
    return wrap


class Session:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.selection: list[int] = []
        self.active: int | None = None
        self.source: dict = {"kind": "all"}
        self.module = "library"
        self.clipboard: dict | None = None
        self.previous_settings: dict | None = None
        self.previous_photo: int | None = None


SESSION = Session()


def resolve_ids(ids: Any) -> list[int]:
    if ids is None or ids == "selection":
        with SESSION.lock:
            out = list(SESSION.selection) or ([SESSION.active] if SESSION.active else [])
        if not out:
            raise CommandError("Nothing is selected: pass ids, or select photos first")
        return out
    if ids == "active":
        if SESSION.active is None:
            raise CommandError("No active photo")
        return [SESSION.active]
    if isinstance(ids, (int, str)):
        return [int(ids)]
    return [int(i) for i in ids]


def _typed(cid: str, name: str, schema: dict, value: Any, default: Any) -> Any:
    kind = schema.get("type")
    if value is None:
        return None
    bad = CommandError(f"{cid}: {name} must be {'an' if kind in ('array', 'integer', 'object') else 'a'} {kind}")
    if kind in ("integer", "number") and isinstance(value, str):
        try:
            value = float(value.strip()) if kind == "number" or "." in value or "e" in value.lower() else int(value.strip())
        except ValueError:
            raise bad from None
    if kind == "integer":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value or (isinstance(value, float) and not value.is_integer()):
            raise bad
        value = int(value)
    elif kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise bad
    elif kind == "boolean":
        if isinstance(value, int) and not isinstance(value, bool) and value in (0, 1):
            value = bool(value)
        elif not isinstance(value, bool):
            raise bad
    elif kind == "string":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = str(value)
        elif not isinstance(value, str):
            raise bad
    elif kind == "object":
        if not isinstance(value, dict):
            raise bad
    elif kind == "array":
        ok = isinstance(value, list) or (name == "ids" and (value in ("selection", "active") or (isinstance(value, int) and not isinstance(value, bool))))
        if not ok:
            raise bad
    if "enum" in schema and value not in schema["enum"]:
        raise CommandError(f"{cid}: {name} must be one of {', '.join(map(str, schema['enum']))}")
    if kind in ("integer", "number") and ("minimum" in schema and value < schema["minimum"] or "maximum" in schema and value > schema["maximum"]):
        raise CommandError(f"{cid}: {name} must be between {schema.get('minimum', '-inf')} and {schema.get('maximum', 'inf')}")
    return value


def dispatch(cid: str, params: dict | None = None) -> Any:
    spec = REGISTRY.get(cid)
    if spec is None:
        raise CommandError(f"Unknown command: {cid}", 404)
    if params is not None and not isinstance(params, dict):
        raise CommandError(f"{cid}: parameters must be an object")
    params = dict(params or {})
    sig = inspect.signature(spec.fn)
    for name, schema in spec.params.items():
        if name in params and isinstance(schema, dict) and schema.get("type"):
            p = sig.parameters.get(name)
            params[name] = _typed(cid, name, schema, params[name], p.default if p is not None and p.default is not p.empty else ...)
    accepted = {k: v for k, v in params.items() if k in sig.parameters}
    unknown = sorted(set(params) - set(accepted))
    if unknown and not any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
        raise CommandError(f"{cid} does not take {', '.join(unknown)}")
    if any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
        accepted = params
    try:
        return spec.fn(**accepted)
    except CommandError:
        raise
    except (ValueError, KeyError, TypeError, FileNotFoundError) as exc:
        raise CommandError(f"{spec.label}: {exc}") from exc


def catalogue() -> list[dict]:
    return [{"id": s.id, "label": s.label, "group": s.group, "mutates": s.mutates, "params": s.params, "description": s.description} for s in sorted(REGISTRY.values(), key=lambda s: s.id)]
