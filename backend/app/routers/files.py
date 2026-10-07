import io
import os
import platform
import string
import time
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse, Response

from app.core import config
from app.services import decode
from app.services.rename import safe, unique

router = APIRouter(prefix="/api/files", tags=["files"])


def _roots() -> list[dict]:
    home = Path.home()
    out = [{"name": "Home", "path": str(home), "kind": "home"}]
    for name in ("Pictures", "Desktop", "Downloads"):
        p = home / name
        if p.is_dir():
            out.append({"name": name, "path": str(p), "kind": name.lower()})
    system = platform.system()
    if system == "Windows":
        for letter in string.ascii_uppercase:
            drive = Path(f"{letter}:\\")
            if drive.exists():
                out.append({"name": f"{letter}:", "path": str(drive), "kind": "drive"})
    else:
        for base in ("/Volumes", "/media", f"/media/{os.environ.get('USER', '')}", "/mnt", f"/run/media/{os.environ.get('USER', '')}"):
            b = Path(base)
            if b.is_dir():
                for child in sorted(b.iterdir()):
                    if child.is_dir() and not child.name.startswith("."):
                        out.append({"name": child.name, "path": str(child), "kind": "volume"})
        out.append({"name": "Computer", "path": "/", "kind": "root"})
    return out


@router.get("/roots")
def roots() -> dict:
    return {"roots": _roots(), "library": str(config.library_dir())}


@router.get("/list")
def listing(path: str, hidden: bool = False) -> Any:
    p = Path(path).expanduser()
    if not p.is_dir():
        return JSONResponse({"ok": False, "error": f"Not a folder: {path}"}, status_code=404)
    dirs, files = [], []
    try:
        entries = sorted(p.iterdir(), key=lambda e: e.name.lower())
    except OSError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=403)
    for e in entries:
        if not hidden and e.name.startswith("."):
            continue
        try:
            if e.is_dir():
                dirs.append({"name": e.name, "path": str(e)})
            elif decode.supported(e):
                st = e.stat()
                files.append({"name": e.name, "path": str(e), "size": st.st_size, "mtime": st.st_mtime, "kind": decode.kind_of(e)})
        except OSError:
            continue
    parent = str(p.parent) if p.parent != p else None
    return {"path": str(p), "parent": parent, "dirs": dirs, "files": files}


@router.get("/thumb")
def thumb(path: str, long: int = 320) -> Any:
    p = Path(path).expanduser()
    if not p.is_file() or not decode.supported(p):
        return JSONResponse({"ok": False, "error": "Not a supported image"}, status_code=404)
    im = decode.embedded_preview(p, max(64, min(long, 1024)))
    if im is None:
        return JSONResponse({"ok": False, "error": "No preview"}, status_code=404)
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=80)
    return Response(buf.getvalue(), media_type="image/jpeg", headers={"Cache-Control": "private, max-age=600"})


@router.post("/upload")
async def upload(files: list[UploadFile] = File(...)) -> dict:
    dest = config.library_dir() / "Uploads" / date.today().isoformat()
    dest.mkdir(parents=True, exist_ok=True)
    saved, skipped = [], []
    for f in files:
        name = safe(Path(f.filename or "upload").name)
        if not decode.supported(Path(name)):
            skipped.append(name)
            continue
        target = unique(dest / name)
        with target.open("wb") as out:
            while chunk := await f.read(1 << 20):
                out.write(chunk)
        saved.append(str(target))
    return {"paths": saved, "skipped": skipped, "folder": str(dest)}


@router.post("/upload/presets")
async def upload_presets(files: list[UploadFile] = File(...)) -> dict:
    dest = config.temp_dir() / "presets-in" / f"{time.time_ns()}"
    dest.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in files:
        name = safe(Path(f.filename or "preset.xmp").name)
        if Path(name).suffix.lower() not in (".xmp", ".lrtemplate", ".flpreset", ".cube"):
            continue
        target = unique(dest / name)
        with target.open("wb") as out:
            while chunk := await f.read(1 << 20):
                out.write(chunk)
        saved.append(str(target))
    return {"paths": saved}
