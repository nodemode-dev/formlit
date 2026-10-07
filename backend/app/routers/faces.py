from typing import Any

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from app.core import config

router = APIRouter(prefix="/api/faces", tags=["people"])


@router.get("/{fid}.jpg")
def face(fid: int) -> Any:
    path = config.faces_dir() / f"{fid}.jpg"
    if not path.is_file():
        return JSONResponse({"ok": False, "error": f"No crop for face {fid}"}, status_code=404)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=31536000, immutable"})
