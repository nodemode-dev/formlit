import importlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import zlib
from pathlib import Path

import numpy as np
import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent

APP_ID = "formlit"
APP_MODULE = "app.main:app"
ENV_PREFIX = "FORMLIT"
DATA_ENV = "FORMLIT_DATA_DIR"
PORT_ENV = "FORMLIT_PORT"
ENGINE_PORT = 8390
HEALTH_PATH = "/api/health"
VERSION_PATH = "/api/version"
VERSION_KEY = "version"
WINDOW_ORIGINS = ["http://localhost:5390", "http://127.0.0.1:5390", "http://localhost:5391", "http://127.0.0.1:5391", "tauri://localhost"]
WS_PATH = "/api/terminal/probe"
MCP_PATH = "/mcp"
STDIO_CMD = [sys.executable, str(REPO / "setup" / "mcp_stdio.py")]
READ_TOOL = ("get_catalog", {})
CHANGING_TOOL = ("undo", {})
INAPP_HEADER = "x-formlit-inapp"
VERSION_SITES = [
    ("README.md", r'badge/version-([0-9.]+)-'),
    ("backend/app/__init__.py", r'^__version__ = "([^"]+)"'),
    ("frontend/package.json", r'^  "version": "([^"]+)"'),
    ("frontend/src/version.ts", r"^export const VERSION = '([^']+)'"),
    ("src-tauri/Cargo.toml", r'^version = "([^"]+)"'),
    ("src-tauri/tauri.conf.json", r'^  "version": "([^"]+)"'),
]
STRIP_EXEMPT = []


def tool_catalogue():
    return [t[0] for t in importlib.import_module("app.routers.mcp").TOOLS]


def set_policy(mode):
    importlib.import_module("app.core.prefs").update({"outsideAgents": mode})


def inapp_token():
    return importlib.import_module("app.engine.agents").INAPP_TOKEN


_SANDBOX = Path(tempfile.mkdtemp(prefix=f"{APP_ID}-tests-"))
for _name in ("data", "home", "library"):
    (_SANDBOX / _name).mkdir()
os.environ[DATA_ENV] = str(_SANDBOX / "data")
os.environ[PORT_ENV] = str(ENGINE_PORT)
os.environ["HOME"] = str(_SANDBOX / "home")
os.environ["USERPROFILE"] = str(_SANDBOX / "home")
os.environ["FORMLIT_LIBRARY_DIR"] = str(_SANDBOX / "library")
for _key in [k for k in os.environ if k.startswith(f"{ENV_PREFIX}_") and k not in (DATA_ENV, PORT_ENV, "FORMLIT_LIBRARY_DIR")]:
    os.environ.pop(_key)
sys.path.insert(0, str(BACKEND))


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_SANDBOX, ignore_errors=True)


def own_origin():
    return f"http://127.0.0.1:{ENGINE_PORT}"


@pytest.fixture(scope="session")
def sandbox():
    return _SANDBOX


@pytest.fixture(scope="session")
def app():
    module, _, attr = APP_MODULE.partition(":")
    return getattr(importlib.import_module(module), attr)


@pytest.fixture(scope="session")
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app, base_url=own_origin()) as c:
        yield c


@pytest.fixture(scope="session")
def repo_versions():
    found = {}
    for rel, pattern in VERSION_SITES:
        text = (REPO / rel).read_text(encoding="utf-8")
        match = re.search(pattern, text, re.MULTILINE)
        found[rel] = match.group(1) if match else None
    return found


@pytest.fixture(scope="session")
def repo_version(repo_versions):
    return next(iter(repo_versions.values()))


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_json(url, timeout=2.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode("utf-8") or "null")


@pytest.fixture(scope="session")
def engine():
    port = free_port()
    data = _SANDBOX / "engine-data"
    data.mkdir()
    env = dict(os.environ, **{DATA_ENV: str(data), PORT_ENV: str(port)})
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", APP_MODULE, "--host", "127.0.0.1", "--port", str(port)],
        cwd=BACKEND, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 90
    ready = False
    while time.monotonic() < deadline and proc.poll() is None:
        try:
            status, _ = get_json(base + HEALTH_PATH)
            ready = status == 200
        except OSError:
            ready = False
        if ready:
            break
        time.sleep(0.25)
    if not ready:
        proc.kill()
        out = proc.communicate(timeout=5)[0].decode("utf-8", "replace")
        raise RuntimeError(f"engine did not answer {HEALTH_PATH} within 90 s:\n{out[-4000:]}")
    yield {"base": base, "port": port, "data": data, "env": env, "proc": proc}
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def write_png(path, rgb8):
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.ascontiguousarray(rgb8, dtype=np.uint8)).save(path, "PNG")
    return path


def write_jpeg(path, rgb8, quality=95):
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.ascontiguousarray(rgb8, dtype=np.uint8)).save(path, "JPEG", quality=quality)
    return path


def gradient(w=96, h=64):
    x = np.linspace(40, 215, w, dtype=np.float32)
    y = np.linspace(0.8, 1.1, h, dtype=np.float32)[:, None]
    base = np.clip(x[None, :] * y, 0, 255)
    return np.stack([base, base * 0.9, base * 0.75], axis=-1).astype(np.uint8)


@pytest.fixture(scope="session")
def commands(client):
    from app.engine.commands import dispatch

    return dispatch


@pytest.fixture
def photo(client, commands, sandbox, request):
    full = re.sub(r"\W", "_", request.node.name)
    name = f"{full[:40]}_{zlib.crc32(full.encode()):08x}"
    pixels = gradient()
    pixels[0, 0] = [zlib.crc32(full.encode()) % 251, 7, 9]
    pixels[0, 1] = [zlib.crc32(full.encode()[::-1]) % 251, 5, 3]
    path = write_jpeg(sandbox / "src" / f"{name}.jpg", pixels)
    res = commands("library.import", {"paths": [str(path)], "mode": "add", "wait": True})
    assert res["ids"], res
    return {"id": int(res["ids"][0]), "path": path}
