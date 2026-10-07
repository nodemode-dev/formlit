import inspect
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


def dispatch(cid: str, params: dict | None = None) -> Any:
    spec = REGISTRY.get(cid)
    if spec is None:
        raise CommandError(f"Unknown command: {cid}", 404)
    params = dict(params or {})
    sig = inspect.signature(spec.fn)
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
