import mimetypes
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from app.core import config

router = APIRouter(prefix="/api/output", tags=["output"])


def _allowed(p: Path) -> bool:
    roots = [config.exports_dir().resolve(), config.temp_dir().resolve()]
    rp = p.resolve()
    return any(rp == r or r in rp.parents for r in roots)


@router.get("/fs/{full:path}")
def browse(full: str) -> Any:
    return file(full if sys.platform == "win32" else "/" + full.lstrip("/"))


@router.get("/audio")
def audio(path: str) -> Any:
    from app.output.slideshow import AUDIO_EXTS
    p = Path(path).expanduser()
    if p.suffix.lower() not in AUDIO_EXTS or not p.is_file():
        return JSONResponse({"ok": False, "error": "Not an audio file"}, status_code=404)
    return FileResponse(p, media_type=mimetypes.guess_type(p.name)[0] or "audio/mpeg", headers={"Cache-Control": "no-store"})


@router.get("/file")
def file(path: str, download: bool = False) -> Any:
    p = Path(path).expanduser()
    if not p.is_file() or not _allowed(p):
        return JSONResponse({"ok": False, "error": "Only files formlit wrote to its Exports folder can be opened here"}, status_code=404)
    media = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    return FileResponse(p, media_type=media, filename=p.name if download else None, headers={"Cache-Control": "no-store"})
