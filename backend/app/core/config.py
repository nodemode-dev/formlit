import os
import sys
import tempfile
from pathlib import Path

from app import __version__

APP_NAME = "formlit"
VERSION = __version__
FRONTEND_PORT = 5390
BACKEND_PORT = 8390
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent
PREVIEW_LONG = 2560
THUMB_LONG = 512
PROXY_LONG = 1024
MAX_IMPORT_FILES = 200_000


def _load_env_file() -> None:
    env = BACKEND_DIR / ".env"
    if not env.is_file():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if value.strip():
            os.environ.setdefault(key.strip(), value.strip())


_load_env_file()


def _ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", str(BACKEND_DIR)))


def data_dir() -> Path:
    raw = os.environ.get("FORMLIT_DATA_DIR", "").strip()
    return _ensure(Path(raw).expanduser() if raw else Path.home() / "Formlit")


def catalog_path() -> Path:
    raw = os.environ.get("FORMLIT_CATALOG", "").strip()
    if raw:
        p = Path(raw).expanduser()
        _ensure(p.parent)
        return p
    return _ensure(data_dir() / "Catalog") / "formlit.fldb"


def previews_dir() -> Path:
    return _ensure(catalog_path().parent / "Previews")


def masks_dir() -> Path:
    return _ensure(catalog_path().parent / "Masks")


def faces_dir() -> Path:
    return _ensure(catalog_path().parent / "Faces")


def presets_dir() -> Path:
    return _ensure(data_dir() / "Presets")


def profiles_dir() -> Path:
    return _ensure(data_dir() / "Profiles")


def models_dir() -> Path:
    raw = os.environ.get("FORMLIT_MODELS_DIR", "").strip()
    return _ensure(Path(raw).expanduser() if raw else data_dir() / "Models")


def exports_dir() -> Path:
    return _ensure(data_dir() / "Exports")


def library_dir() -> Path:
    raw = os.environ.get("FORMLIT_LIBRARY_DIR", "").strip()
    return Path(raw).expanduser() if raw else Path.home() / "Pictures" / "formlit"


def temp_dir() -> Path:
    return _ensure(Path(tempfile.gettempdir()) / "formlit")


def shared_dir() -> Path:
    bundled = resource_dir() / "shared"
    return bundled if bundled.is_dir() else REPO_DIR / "shared"


def dist_dir() -> Path | None:
    raw = os.environ.get("FORMLIT_DIST")
    candidate = Path(raw) if raw else REPO_DIR / "frontend" / "dist"
    return candidate if (candidate / "index.html").is_file() else None


def engine_port() -> int:
    raw = os.environ.get("FORMLIT_PORT", "").strip()
    return int(raw) if raw.isdigit() and int(raw) > 0 else BACKEND_PORT


def engine_url() -> str:
    return f"http://127.0.0.1:{engine_port()}"


def is_desktop() -> bool:
    return os.environ.get("FORMLIT_DESKTOP") == "1"


def workers() -> int:
    raw = os.environ.get("FORMLIT_WORKERS", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return max(1, min(6, (os.cpu_count() or 2) - 1))


os.environ.setdefault("NUMBA_CACHE_DIR", str(_ensure(data_dir() / "Cache" / "kernels")))


def cors_origins() -> list[str]:
    raw = os.environ.get("FORMLIT_CORS_ORIGINS")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [f"http://localhost:{FRONTEND_PORT}", f"http://127.0.0.1:{FRONTEND_PORT}",
            f"http://localhost:{FRONTEND_PORT + 1}", f"http://127.0.0.1:{FRONTEND_PORT + 1}", "tauri://localhost"]
