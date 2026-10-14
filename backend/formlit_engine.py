import json
import os
import sys


def resource_dir() -> str:
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def selfcheck() -> int:
    info = {"python": sys.version.split()[0]}
    for name in ("PIL", "fastapi", "uvicorn", "numpy", "cv2", "rawpy", "exifread", "reportlab", "paramiko", "pikepdf"):
        try:
            module = __import__(name)
            info[name.lower()] = getattr(module, "__version__", "ok")
        except Exception as exc:
            info[name.lower()] = f"missing: {exc}"
    from app import __version__

    info["formlit"] = __version__
    info["dist_bundled"] = os.path.isdir(os.path.join(resource_dir(), "frontend_dist"))
    info["shared_bundled"] = os.path.isdir(os.path.join(resource_dir(), "shared"))
    import importlib

    from app.engine.boot import COMMAND_MODULES
    missing = []
    for name in [*COMMAND_MODULES, "app.output.services.s3", "app.output.services.webdav", "app.develop.makernotes", "app.develop.dcp_kernel"]:
        try:
            importlib.import_module(name)
        except Exception as exc:
            missing.append(f"{name}: {exc}")
    info["modules_missing"] = missing
    print(json.dumps(info))
    return 1 if missing else 0


def usable_port(port: int) -> int:
    if not port:
        return 0
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return 0 if probe.connect_ex(("127.0.0.1", port)) == 0 else port


def free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def main() -> int:
    if "--selfcheck" in sys.argv:
        return selfcheck()
    bundled = os.path.join(resource_dir(), "frontend_dist")
    if os.path.isdir(bundled):
        os.environ.setdefault("FORMLIT_DIST", bundled)
    os.environ.setdefault("FORMLIT_DESKTOP", "1")
    import uvicorn

    from app.main import app as fastapi_app

    port = usable_port(int(os.environ.get("FORMLIT_PORT", "0") or 0)) or free_port()
    os.environ["FORMLIT_PORT"] = str(port)
    uvicorn.run(fastapi_app, host="127.0.0.1", port=port, log_level="info")
    return 0


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    sys.exit(main())
