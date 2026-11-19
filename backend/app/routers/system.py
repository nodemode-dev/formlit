import importlib.util
import os
import platform
import shutil

from fastapi import APIRouter, HTTPException, Request

from app.core import config, window_key

router = APIRouter(prefix="/api", tags=["system"])


def _has(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


@router.get("/health")
def health() -> dict:
    return {"ok": True, "app": config.APP_NAME, "version": config.VERSION}


@router.get("/version")
def version() -> dict:
    return {"app": config.APP_NAME, "version": config.VERSION, "desktop": config.is_desktop()}


@router.get("/capabilities")
def capabilities() -> dict:
    return {
        "version": config.VERSION,
        "platform": platform.system().lower(),
        "desktop": config.is_desktop(),
        "raw": _has("rawpy"),
        "heic": _has("pillow_heif"),
        "onnx": _has("onnxruntime"),
        "pdf": _has("reportlab"),
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "workers": config.workers(),
        "dataDir": str(config.data_dir()),
        "catalog": str(config.catalog_path()),
        "home": os.path.expanduser("~"),
    }


@router.post("/window/key")
def claim_window_key() -> dict:
    if window_key.stdout_mode():
        raise HTTPException(404, "Not Found")
    key = window_key.claim()
    if key is None:
        raise HTTPException(409, "Another window already holds this engine's window key; use that window, or restart formlit")
    return {"key": key}


@router.post("/window/ticket")
def window_ticket(request: Request) -> dict:
    window_key.require(request)
    return {"ticket": window_key.ticket()}


@router.get("/window/state")
def window_state() -> dict:
    return {"secondClaim": window_key.STATE["secondClaim"]}
