import json
import os
import sys


def resource_dir() -> str:
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def selfcheck() -> int:
    info = {"python": sys.version.split()[0]}
    for name in ("PIL", "fastapi", "uvicorn", "numpy", "cv2", "rawpy", "exifread", "reportlab"):
        try:
            module = __import__(name)
            info[name.lower()] = getattr(module, "__version__", "ok")
        except Exception as exc:
            info[name.lower()] = f"missing: {exc}"
    from app import __version__

    info["formlit"] = __version__
    info["dist_bundled"] = os.path.isdir(os.path.join(resource_dir(), "frontend_dist"))
    info["shared_bundled"] = os.path.isdir(os.path.join(resource_dir(), "shared"))
    print(json.dumps(info))
    return 0


def main() -> int:
    if "--selfcheck" in sys.argv:
        return selfcheck()
    bundled = os.path.join(resource_dir(), "frontend_dist")
    if os.path.isdir(bundled):
        os.environ.setdefault("FORMLIT_DIST", bundled)
    os.environ.setdefault("FORMLIT_DESKTOP", "1")
    import uvicorn

    from app.main import app as fastapi_app

    port = int(os.environ.get("FORMLIT_PORT", "0") or 0)
    uvicorn.run(fastapi_app, host="127.0.0.1", port=port, log_level="info")
    return 0


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    sys.exit(main())
