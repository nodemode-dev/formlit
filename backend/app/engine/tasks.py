import itertools
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from app.core import config
from app.engine import events

_ids = itertools.count(1)
_lock = threading.Lock()
TASKS: dict[int, dict] = {}
_runner = ThreadPoolExecutor(max_workers=2, thread_name_prefix="formlit-task")
POOL = ThreadPoolExecutor(max_workers=config.workers(), thread_name_prefix="formlit-render")


class Progress:
    def __init__(self, tid: int):
        self.tid = tid
        self.cancelled = False
        self._last = 0.0

    def __call__(self, done: int, total: int, label: str = "") -> None:
        with _lock:
            t = TASKS.get(self.tid)
            if t is None:
                return
            t.update(done=done, total=total, label=label or t["label"])
            self.cancelled = t.get("cancel", False)
        now = time.monotonic()
        if now - self._last > 0.15 or done >= total:
            self._last = now
            events.publish("task", id=self.tid, state="running", done=done, total=total, label=label)


def start(kind: str, label: str, fn: Callable[[Progress], Any]) -> int:
    tid = next(_ids)
    with _lock:
        TASKS[tid] = {"id": tid, "kind": kind, "label": label, "state": "running", "done": 0, "total": 0, "result": None, "error": None, "started": time.time()}
    events.publish("task", id=tid, kind=kind, state="running", done=0, total=0, label=label)

    def run() -> None:
        prog = Progress(tid)
        try:
            result = fn(prog)
            with _lock:
                state = "cancelled" if TASKS[tid].get("cancel") else "done"
                TASKS[tid].update(state=state, result=result)
            events.publish("task", id=tid, kind=kind, state=state, label=label, result=result)
        except Exception as exc:
            traceback.print_exc()
            with _lock:
                TASKS[tid].update(state="failed", error=str(exc))
            events.publish("task", id=tid, kind=kind, state="failed", label=label, error=str(exc))

    _runner.submit(run)
    return tid


def cancel(tid: int) -> bool:
    with _lock:
        t = TASKS.get(tid)
        if t is None or t["state"] != "running":
            return False
        t["cancel"] = True
        return True


def get(tid: int) -> dict | None:
    with _lock:
        t = TASKS.get(tid)
        return dict(t) if t else None


def wait(tid: int, timeout: float = 600.0) -> dict | None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        t = get(tid)
        if t is None or t["state"] != "running":
            return t
        time.sleep(0.05)
    return get(tid)
