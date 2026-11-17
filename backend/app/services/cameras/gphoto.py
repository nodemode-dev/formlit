import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

from app.services import tether
from app.services.cameras import CameraError, Entry, arrived, inside, safe_name, short_id

Runner = Callable[[list[str], float], tuple[int, str, str]]
FOLDER = re.compile(r"^There (?:is|are) (?:no|\d+) files? in folder '(.*)'[.:]?\s*$")
FILE = re.compile(r"^#(\d+)\s+(.+?)\s*[r-][d-]\s+(\d+) KB(?:\s+\d+x\d+)?(?:\s+(\S+/\S+))?(?:\s+(\d+))?\s*$")
TREE_SECONDS = 15.0
BUSY_HINT = ("Another program is using the camera. On a Mac, quit Image Capture and Photos; on Linux, unmount the camera in the file manager; "
             "stop tethered capture in formlit")


PART = "download.part"


def _plain_path(path: Path) -> Path:
    if "%" in str(path):
        raise CameraError(f"Refused a download folder whose path has a % in it: {path}")
    return path


def folder_key(folder: str) -> str:
    parts = [p for p in folder.strip("/").split("/") if p]
    if any(p in (".", "..") or any(ch in p for ch in "%\\:\x00\n\r") for p in parts):
        raise CameraError(f"Refused a folder name from the camera: {folder!r}")
    return "/" + "/".join(parts)


def _run(argv: list[str], timeout: float) -> tuple[int, str, str]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise CameraError(f"The camera did not answer within {int(timeout)} s") from exc
    except OSError as exc:
        raise CameraError(f"gphoto2 could not be started: {exc}") from exc
    return r.returncode, r.stdout, r.stderr


def parse_listing(text: str) -> dict[str, list[tuple[int, Entry]]]:
    tree: dict[str, list[tuple[int, Entry]]] = {}
    current: str | None = None
    for line in text.splitlines():
        head = FOLDER.match(line.strip())
        if head:
            current = head.group(1).rstrip("/") or "/"
            tree.setdefault(current, [])
            continue
        row = FILE.match(line.strip())
        if row and current is not None:
            stamp = float(row.group(5)) if row.group(5) else 0.0
            tree[current].append((int(row.group(1)), Entry(row.group(2), int(row.group(3)) * 1024, stamp, exact=False)))
    for folder in list(tree):
        parts = [p for p in folder.split("/") if p]
        for i in range(len(parts)):
            tree.setdefault("/" + "/".join(parts[:i]) if i else "/", [])
    return tree


def _error(stderr: str, stdout: str) -> str:
    text = (stderr or stdout).strip()
    if "Could not claim" in text or "-53" in text or "busy" in text.lower():
        return BUSY_HINT
    line = next((ln.strip(" *") for ln in text.splitlines() if "Error" in ln or "error" in ln), "")
    return line or text.splitlines()[-1] if text else "gphoto2 failed"


class GphotoCamera:
    backend = "gphoto2"

    def __init__(self, binary: str, model: str, port: str, run: Runner = _run):
        self.binary = binary
        self.name = model
        self.port = port
        self.id = short_id("gp", f"{model}|{port}")
        self._run = run
        self._lock = threading.Lock()
        self._tree: tuple[float, dict[str, list[tuple[int, Entry]]]] = (0.0, {})

    def _call(self, args: list[str], timeout: float = 120.0) -> str:
        with self._lock:
            code, out, err = self._run([self.binary, "--port", self.port, *args], timeout)
        if code != 0:
            raise CameraError(_error(err, out))
        return out

    def tree(self, refresh: bool = False) -> dict[str, list[tuple[int, Entry]]]:
        stamp, found = self._tree
        if refresh or not found or time.monotonic() - stamp > TREE_SECONDS:
            found = parse_listing(self._call(["--list-files"], 300.0))
            self._tree = (time.monotonic(), found)
        return found

    def list_dir(self, folder: str) -> tuple[list[str], list[Entry]]:
        key = "/" + folder.strip("/") if folder.strip("/") else "/"
        tree = self.tree()
        if key not in tree:
            raise CameraError(f"No folder {key} on the camera")
        prefix = key.rstrip("/") + "/"
        dirs = sorted({k[len(prefix):].split("/", 1)[0] for k in tree if k.startswith(prefix) and k != key})
        return dirs, [e for _, e in tree[key]]

    def _number(self, file: str, refresh: bool = False) -> tuple[str, int, Entry]:
        folder, _, name = file.strip("/").rpartition("/")
        key = folder_key(folder)
        if refresh:
            listed = parse_listing(self._call(["--folder", key, "--no-recurse", "--list-files"], 120.0)).get(key, [])
        else:
            listed = self.tree().get(key, [])
        hit = next(((n, e) for n, e in listed if e.name == name), None)
        if hit is None:
            raise CameraError(f"{name} is no longer on the camera")
        return key, hit[0], hit[1]

    def fetch(self, file: str, dest: Path) -> Path:
        name = safe_name(file.strip("/").rpartition("/")[2])
        key, number, entry = self._number(file, refresh=True)
        dest.mkdir(parents=True, exist_ok=True)
        target = inside(dest / safe_name(entry.name), dest)
        part = _plain_path(inside(dest / PART, dest))
        if target.exists() or part.exists() or target.name != name:
            raise CameraError(f"Refused to overwrite or rename {name} while copying it from the camera")
        self._call(["--folder", key, "--no-recurse", "--get-file", str(number), "--filename", str(part)], 900.0)
        got = arrived(dest, PART)
        if entry.size and abs(got.stat().st_size - entry.size) >= 1024:
            got.unlink()
            raise CameraError(f"The camera sent a different file than {name}; nothing was imported from it")
        got.rename(target)
        return arrived(dest, name)

    def delete(self, file: str) -> None:
        safe_name(file.strip("/").rpartition("/")[2])
        key, number, _ = self._number(file, refresh=True)
        self._call(["--folder", key, "--no-recurse", "--delete-file", str(number)], 120.0)
        self._tree = (0.0, {})

    def thumbnail(self, file: str) -> bytes | None:
        key, number, _ = self._number(file)
        with tempfile.TemporaryDirectory(prefix="formlit-thumb-") as tmp:
            try:
                target = _plain_path(Path(tmp) / "thumb.jpg")
            except CameraError:
                return None
            try:
                self._call(["--folder", key, "--no-recurse", "--get-thumbnail", str(number), "--filename", str(target), "--force-overwrite"], 60.0)
            except CameraError:
                return None
            return target.read_bytes() if target.is_file() else None


def devices(run: Runner = _run) -> list[GphotoCamera]:
    binary = tether.binary()
    if not binary or binary == tether.digicam():
        return []
    code, out, _ = run([binary, "--auto-detect"], 20.0)
    if code != 0:
        return []
    found = []
    for line in out.splitlines():
        if line.startswith(("Model", "---")) or not line.strip():
            continue
        m = re.match(r"^(.+?)\s{2,}(\S+)\s*$", line)
        if m and m.group(2).startswith(("usb:", "ptpip:", "serial:")):
            found.append(GphotoCamera(binary, m.group(1).strip(), m.group(2), run))
    return found
