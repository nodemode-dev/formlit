import asyncio
import json
import threading
from collections import deque
from typing import Any, Callable

_loop: asyncio.AbstractEventLoop | None = None
_subscribers: set[asyncio.Queue] = set()
_listeners: list[Callable[[str, dict], None]] = []
_lock = threading.Lock()
_recent: deque = deque(maxlen=64)
_seq = 0


def bind(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def _deliver(message: str) -> None:
    for q in list(_subscribers):
        if q.qsize() < 2000:
            q.put_nowait(message)


def listen(fn: Callable[[str, dict], None]) -> None:
    _listeners.append(fn)


def publish(kind: str, /, **payload: Any) -> None:
    global _seq
    with _lock:
        _seq += 1
        message = json.dumps({"seq": _seq, "type": kind, **payload}, default=str)
        _recent.append(message)
    for fn in list(_listeners):
        try:
            fn(kind, payload)
        except Exception:
            continue
    loop = _loop
    if loop is None or loop.is_closed():
        return
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is loop:
        _deliver(message)
    else:
        loop.call_soon_threadsafe(_deliver, message)


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    _subscribers.discard(q)


def recent() -> list[str]:
    with _lock:
        return list(_recent)
