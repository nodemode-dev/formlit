import logging
from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from app.engine import catalog as catalog_mod
from app.engine.commands import REGISTRY, CommandError, catalogue, dispatch

router = APIRouter(prefix="/api", tags=["commands"])
log = logging.getLogger("formlit.commands")


def _run(cid: str, params: dict | None) -> tuple[int, dict]:
    try:
        result = dispatch(cid, params or {})
    except CommandError as exc:
        return exc.status, {"ok": False, "command": cid, "error": str(exc)}
    except Exception as exc:
        log.exception("command %s failed", cid)
        return 500, {"ok": False, "command": cid, "error": f"{type(exc).__name__}: {exc}"}
    return 200, {"ok": True, "command": cid, "result": result, "revision": catalog_mod.get().revision}


@router.get("/commands")
def list_commands(group: str | None = None) -> dict:
    items = catalogue()
    if group:
        items = [c for c in items if c["group"] == group]
    return {"commands": items, "count": len(items)}


@router.get("/commands/{cid}")
def describe(cid: str) -> Any:
    spec = REGISTRY.get(cid)
    if spec is None:
        return JSONResponse({"ok": False, "error": f"Unknown command: {cid}"}, status_code=404)
    return {"id": spec.id, "label": spec.label, "group": spec.group, "mutates": spec.mutates, "params": spec.params, "description": spec.description}


@router.post("/commands/{cid}")
def run(cid: str, params: dict | None = Body(default=None)) -> Any:
    status, body = _run(cid, params)
    return body if status == 200 else JSONResponse(body, status_code=status)


@router.post("/batch")
def batch(steps: list[dict] = Body(...), stopOnError: bool = True) -> dict:
    results = []
    for step in steps:
        status, body = _run(str(step.get("id") or step.get("command") or ""), step.get("params") or {})
        results.append(body)
        if status != 200 and stopOnError:
            break
    return {"ok": all(r["ok"] for r in results), "results": results, "revision": catalog_mod.get().revision}
