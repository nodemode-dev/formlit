from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

from app.engine import cmd_extensions
from app.services import formext_host as fx

router = APIRouter(prefix="/api/extensions", tags=["extensions"])


@router.get("")
def listing(since: str = "", reload: bool = False) -> dict:
    body = cmd_extensions.listing(reload)
    if since and since == body["stamp"] and not reload:
        return {"stamp": body["stamp"], "changed": False}
    return {**body, "changed": True}


@router.api_route("/files/{ext_id}/{version}/{path:path}", methods=["GET", "HEAD"])
def package_file(ext_id: str, version: str, path: str) -> Response:
    found = fx.file_for(cmd_extensions.resolved(), ext_id, version, path)
    if found is None:
        return Response(status_code=404, headers=fx.headers_for("text/plain", ""))
    target, content_type = found
    return FileResponse(target, media_type=content_type, headers=fx.headers_for(content_type, ""))
