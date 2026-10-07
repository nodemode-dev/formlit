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


def digicam() -> str | None:
    found = os.environ.get("FORMLIT_DIGICAM") or shutil.which("CameraControlCmd")
    if found:
        return found
    for base in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")):
        p = Path(base) / "digiCamControl" / "CameraControlCmd.exe" if base else None
        if p is not None and p.is_file():
            return str(p)
    return None


def binary() -> str | None:
    return os.environ.get("FORMLIT_GPHOTO2") or shutil.which("gphoto2") or (digicam() if os.name == "nt" else None)


def cameras() -> list[dict]:
    b = binary()
    if not b:
        return []
    if b == digicam():
        return [{"model": "Camera (digiCamControl)", "port": "digicam"}]
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
        self.choices: dict[str, list[str]] = {}
        self.live: bytes = b""
        self.live_seq = 0
        self._live_wait = threading.Event()
        self._choice_key = ""
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
                p = Path(m.group(1)) if Path(m.group(1)).is_absolute() else self.staging / m.group(1)
                if p.name.startswith("capture_preview"):
                    self._preview(p)
                else:
                    self._arrived(p)
                continue
            cur = re.match(r"^Current:\s*(.+)$", line)
            if cur and self._asked:
                self._choice_key = self._asked.pop(0)
                self.settings[self._choice_key] = cur.group(1)
                self.choices[self._choice_key] = []
                events.publish("tether", state="settings", settings=dict(self.settings))
                continue
            ch = re.match(r"^Choice:\s*\d+\s+(.+)$", line)
            if ch and self._choice_key:
                self.choices.setdefault(self._choice_key, []).append(ch.group(1).strip())
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
        if o.get("preset") == "previous":
            if self.shots:
                from app.engine.cmd_develop import current
                try:
                    dev = current(self.shots[-1])[0] or None
                except Exception:
                    dev = None
        elif o.get("preset"):
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

    def _preview(self, path: Path) -> None:
        for _ in range(20):
            if path.is_file() and path.stat().st_size > 0:
                break
            time.sleep(0.05)
        try:
            self.live = path.read_bytes()
            self.live_seq += 1
        except OSError:
            return
        self._live_wait.set()

    def preview(self, timeout: float = 4.0) -> bytes:
        self._live_wait.clear()
        self.cmds.put("capture-preview")
        self._live_wait.wait(timeout)
        return self.live

    def set_config(self, key: str, value: str) -> None:
        if not re.fullmatch(r"[a-z0-9-]+", key) or "\n" in value:
            raise ValueError("Invalid camera setting")
        self.cmds.put(f"set-config {key}={value}")
        self._asked.append(key)
        self.cmds.put(f"get-config {key}")

    def refresh_settings(self) -> None:
        for key in ("iso", "shutterspeed", "aperture", "whitebalance", "exposurecompensation", "imagequality"):
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
                "settings": dict(self.settings), "choices": {k: v for k, v in self.choices.items() if v}, "session": self.opts.get("session", ""), "error": self.error,
                "preset": self.opts.get("preset", "")}


class DigiCamSession(Session):
    FLAGS = {"iso": "/iso", "shutterspeed": "/shutter", "aperture": "/aperture", "exposurecompensation": "/ec"}

    def __init__(self, port: str, model: str, opts: dict):
        self.exe = digicam() or ""
        self.model = model
        self.opts = opts
        self.staging = config.temp_dir() / "tether" / str(int(time.time()))
        self.staging.mkdir(parents=True, exist_ok=True)
        self.proc = None
        self.cmds = queue.Queue()
        self.stop_flag = threading.Event()
        self.shots = []
        self.settings = {}
        self.choices = {k: [] for k in self.FLAGS}
        self.live, self.live_seq, self._live_wait, self._choice_key = b"", 0, threading.Event(), ""
        self.error = ""
        self._asked = []
        self.started = time.time()
        self.n = 0
        threading.Thread(target=self._drive, name="formlit-digicam", daemon=True).start()

    def _drive(self) -> None:
        while not self.stop_flag.is_set():
            try:
                job = self.cmds.get(timeout=1.0)
            except queue.Empty:
                continue
            if job != "capture":
                continue
            self.n += 1
            target = self.staging / f"shot_{self.n:04d}"
            args = [self.exe]
            for key, flag in self.FLAGS.items():
                if self.settings.get(key):
                    args += [flag, self.settings[key]]
            args += ["/filename", str(target), "/capture"]
            before = set(self.staging.iterdir())
            try:
                subprocess.run(args, capture_output=True, text=True, timeout=60)
            except (OSError, subprocess.SubprocessError) as exc:
                self.error = str(exc)
                events.publish("tether", state="error", error=self.error)
                continue
            for p in sorted(set(self.staging.iterdir()) - before):
                if p.is_file():
                    self._arrived(p)

    def capture(self) -> None:
        self.cmds.put("capture")

    def preview(self, timeout: float = 4.0) -> bytes:
        raise RuntimeError("Live view needs gphoto2; digiCamControl's own window offers it on Windows")

    def set_config(self, key: str, value: str) -> None:
        if key not in self.FLAGS or "\n" in value:
            raise ValueError("Invalid camera setting")
        self.settings[key] = value
        events.publish("tether", state="settings", settings=dict(self.settings))

    def refresh_settings(self) -> None:
        return

    def stop(self) -> None:
        self.stop_flag.set()

    def state(self) -> dict:
        return {"active": not self.stop_flag.is_set(), "model": self.model, "shots": len(self.shots), "last": self.shots[-1] if self.shots else None,
                "settings": dict(self.settings), "choices": {}, "session": self.opts.get("session", ""), "error": self.error, "preset": self.opts.get("preset", ""),
                "backend": "digiCamControl"}


def start(port: str = "", model: str = "", opts: dict | None = None) -> dict:
    global _session
    with _lock:
        if _session is not None:
            _session.stop()
        _session = DigiCamSession(port, model, opts or {}) if port == "digicam" else Session(port, model, opts or {})
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


def live() -> bytes:
    if _session is None or _session.stop_flag.is_set():
        raise RuntimeError("Start tethered capture first")
    return _session.preview()


def set_config(key: str, value: str) -> dict:
    if _session is None or _session.stop_flag.is_set():
        raise RuntimeError("Start tethered capture first")
    _session.set_config(key, value)
    return _session.state()


def set_preset(preset: str) -> dict:
    if _session is None:
        raise RuntimeError("Start tethered capture first")
    _session.opts["preset"] = preset
    return _session.state()
