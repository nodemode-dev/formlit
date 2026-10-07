import os
import queue
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

from app.core import config
from app.engine import events

SETTINGS = ("iso", "shutterspeed", "aperture", "f-number", "whitebalance", "batterylevel", "imagequality")
_session: "Session | None" = None
_lock = threading.Lock()


def binary() -> str | None:
    return os.environ.get("FORMLIT_GPHOTO2") or shutil.which("gphoto2")


def cameras() -> list[dict]:
    b = binary()
    if not b:
        return []
    try:
        r = subprocess.run([b, "--auto-detect"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return []
    out = []
    for line in r.stdout.splitlines():
        if line.startswith(("Model", "---")) or not line.strip():
            continue
        m = re.match(r"^(.+?)\s{2,}(\S+)\s*$", line)
        if m:
            out.append({"model": m.group(1).strip(), "port": m.group(2)})
    return out


class Session:
    def __init__(self, port: str, model: str, opts: dict):
        b = binary()
        if not b:
            raise RuntimeError("gphoto2 is not installed. Install it with your package manager (brew install gphoto2, apt install gphoto2) to shoot tethered")
        self.model = model
        self.opts = opts
        self.staging = config.temp_dir() / "tether" / str(int(time.time()))
        self.staging.mkdir(parents=True, exist_ok=True)
        cmd = [b, "--shell"] + (["--port", port] if port else [])
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=str(self.staging))
        self.cmds: "queue.Queue[str]" = queue.Queue()
        self.stop_flag = threading.Event()
        self.shots: list[int] = []
        self.settings: dict[str, str] = {}
        self.error = ""
        self._asked: list[str] = []
        self.started = time.time()
        threading.Thread(target=self._read, name="formlit-tether-read", daemon=True).start()
        threading.Thread(target=self._drive, name="formlit-tether-drive", daemon=True).start()
        self.refresh_settings()

    def _send(self, line: str) -> None:
        if self.proc.stdin is None or self.proc.poll() is not None:
            return
        try:
            self.proc.stdin.write(line + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            self.stop_flag.set()

    def _drive(self) -> None:
        while not self.stop_flag.is_set():
            try:
                self._send(self.cmds.get(timeout=2.5))
                continue
            except queue.Empty:
                pass
            self._send("wait-event-and-download 2s")
        self._send("exit")

    def _read(self) -> None:
        assert self.proc.stdout is not None
        for raw in self.proc.stdout:
            line = raw.strip()
            m = re.search(r"Saving file as (.+?)\s*$", line)
            if m:
                self._arrived(Path(m.group(1)) if Path(m.group(1)).is_absolute() else self.staging / m.group(1))
                continue
            cur = re.match(r"^Current:\s*(.+)$", line)
            if cur and self._asked:
                self.settings[self._asked.pop(0)] = cur.group(1)
                events.publish("tether", state="settings", settings=dict(self.settings))
                continue
            lab = re.match(r"^Label:\s*(.+)$", line)
            if lab:
                continue
            if "*** Error" in line or "Could not" in line:
                self.error = line
                events.publish("tether", state="error", error=line)
        self.stop_flag.set()
        events.publish("tether", state="stopped")

    def _arrived(self, path: Path) -> None:
        for _ in range(40):
            if path.is_file() and path.stat().st_size > 0:
                break
            time.sleep(0.1)
        if not path.is_file():
            return
        from app.services import importer
        o = self.opts
        dev = None
        if o.get("preset"):
            from app.engine import presets
            try:
                dev = presets.settings_of(str(o["preset"]))
            except Exception:
                dev = None
        dest = str(Path(str(o.get("destination") or (Path.home() / "Pictures" / "formlit Tether"))).expanduser() / str(o.get("session") or "Tethered"))
        try:
            res = importer.import_files([str(path)], "move", dest, "", str(o.get("renameTemplate") or ""), str(o.get("session") or ""), dev, None,
                                        list(o.get("keywords") or []) or None, o.get("collection"), False, False)
        except Exception as exc:
            events.publish("tether", state="error", error=str(exc))
            return
        ids = [int(i) for i in res.get("ids") or []]
        self.shots.extend(ids)
        if ids:
            events.publish("tether", state="shot", ids=ids, count=len(self.shots))

    def capture(self) -> None:
        self.cmds.put("capture-image-and-download")

    def refresh_settings(self) -> None:
        for key in ("iso", "shutterspeed", "aperture", "whitebalance"):
            self._asked.append(key)
            self.cmds.put(f"get-config {key}")

    def stop(self) -> None:
        self.stop_flag.set()
        try:
            self.proc.wait(timeout=6)
        except subprocess.TimeoutExpired:
            self.proc.kill()

    def state(self) -> dict:
        return {"active": not self.stop_flag.is_set() and self.proc.poll() is None, "model": self.model, "shots": len(self.shots), "last": self.shots[-1] if self.shots else None,
                "settings": dict(self.settings), "session": self.opts.get("session", ""), "error": self.error}


def start(port: str = "", model: str = "", opts: dict | None = None) -> dict:
    global _session
    with _lock:
        if _session is not None:
            _session.stop()
        _session = Session(port, model, opts or {})
        events.publish("tether", state="started", model=model)
        return _session.state()


def stop() -> dict:
    global _session
    with _lock:
        if _session is not None:
            _session.stop()
            st = _session.state()
            _session = None
            return st
    return {"active": False}


def capture() -> dict:
    if _session is None or _session.stop_flag.is_set():
        raise RuntimeError("Start tethered capture first")
    _session.capture()
    return _session.state()


def state() -> dict:
    return _session.state() if _session is not None else {"active": False, "installed": bool(binary())}
