from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from app.core import config
from app.routers import ROUTERS, startup, shutdown


@asynccontextmanager
async def lifespan(_: FastAPI):
    await startup()
    yield
    await shutdown()


app = FastAPI(title=config.APP_NAME, version=config.VERSION, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.cors_origins(), allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=4096, compresslevel=3)
for router in ROUTERS:
    app.include_router(router)

_dist = config.dist_dir()
if _dist is not None:
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
