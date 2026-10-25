import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import DEFAULT_EXCLUDED_CONTENT_TYPES

from app.core import config
from app.core.local_guard import LocalGuard
from app.routers import ROUTERS, startup, shutdown


@asynccontextmanager
async def lifespan(_: FastAPI):
    await startup()
    yield
    await shutdown()


app = FastAPI(title=config.APP_NAME, version=config.VERSION, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.cors_origins(), allow_methods=["*"], allow_headers=["*"])
app.add_middleware(LocalGuard, origins=config.cors_origins())
app.add_middleware(GZipMiddleware, minimum_size=4096, compresslevel=3,
                   exclude_content_types=DEFAULT_EXCLUDED_CONTENT_TYPES + ("application/octet-stream", "image/tiff", "application/pdf"))
for router in ROUTERS:
    app.include_router(router)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger("formlit").exception("unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status_code=500)


_dist = config.dist_dir()
if _dist is not None:
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
