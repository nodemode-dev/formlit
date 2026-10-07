import io
import threading
import time
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

from app.core import config
from app.engine import catalog as catalog_mod
from app.engine import events
from app.engine.records import loads
from app.services import decode

THUMB = config.THUMB_LONG
PREVIEW = config.PREVIEW_LONG
_bg = ThreadPoolExecutor(max_workers=max(1, config.workers() - 1), thread_name_prefix="formlit-bg")
_fg = ThreadPoolExecutor(max_workers=2, thread_name_prefix="formlit-fg")
_inflight: dict[str, Future] = {}
_inflight_lock = threading.Lock()
_sources: "OrderedDict[tuple, tuple[np.ndarray, dict]]" = OrderedDict()
_sources_lock = threading.Lock()
SOURCE_CACHE_ENTRIES = 6


def cache_dir(pid: int) -> Path:
    d = config.previews_dir() / f"{pid // 1000:04d}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def thumb_path(pid: int, rev: int, size: str) -> Path:
    return cache_dir(pid) / f"{pid}-{rev}-{size}.jpg"


def embedded_path(pid: int) -> Path:
    return cache_dir(pid) / f"{pid}-e.jpg"


def source_path(pid: int) -> Path:
    return cache_dir(pid) / f"{pid}-src.npy"


def clear(pid: int, keep_rev: int | None = None) -> None:
    for p in cache_dir(pid).glob(f"{pid}-*"):
        name = p.name
        if keep_rev is not None and (name.startswith(f"{pid}-{keep_rev}-") or name.endswith("-e.jpg") or name.endswith("-src.npy")):
            continue
        try:
            p.unlink()
        except OSError:
            continue


def _once(key: str, pool: ThreadPoolExecutor, fn) -> Future:
    with _inflight_lock:
        fut = _inflight.get(key)
        if fut is not None and not fut.done():
            return fut
        fut = pool.submit(fn)
        _inflight[key] = fut

        def done(_f: Future) -> None:
            with _inflight_lock:
                if _inflight.get(key) is _f:
                    del _inflight[key]
        fut.add_done_callback(done)
        return fut


def encode_jpeg(rgb8: np.ndarray, quality: int = 86) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgb8).save(buf, "JPEG", quality=quality, optimize=False, progressive=False, subsampling=0 if quality >= 90 else 2)
    return buf.getvalue()


def write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + f".{threading.get_ident()}.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def make_embedded(pid: int, path: Path) -> Path | None:
    out = embedded_path(pid)
    if out.is_file():
        return out
    im = decode.embedded_preview(path, 1024)
    if im is None:
        return None
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=84)
    write_atomic(out, buf.getvalue())
    return out


def source(pid: int, long: int | None = PREVIEW, full: bool = False) -> tuple[np.ndarray, dict]:
    cat = catalog_mod.get()
    path = cat.photo_path(pid)
    if path is None:
        raise FileNotFoundError(f"No photo with id {pid}")
    master = cat.scalar("SELECT COALESCE(master_id, id) FROM photos WHERE id=?", (pid,)) or pid
    key = (int(master), "full" if full else int(long or 0))
    with _sources_lock:
        if key in _sources:
            _sources.move_to_end(key)
            return _sources[key]
    if not path.is_file():
        raise FileNotFoundError(f"The original is missing: {path}")
    disk = source_path(int(master))
    img: np.ndarray | None = None
    info: dict = {}
    if not full and long == PREVIEW and disk.is_file():
        try:
            data = np.load(disk, allow_pickle=False)
            img = data.astype(np.float32)
            meta = disk.with_suffix(".json")
            import json
            info = json.loads(meta.read_text()) if meta.is_file() else {}
            if info.get("v") != decode.SOURCE_VERSION:
                img = None
        except (OSError, ValueError):
            img = None
    if img is None:
        img, info = decode.load_linear(path, None if full else long, full=full)
        if not full and long == PREVIEW:
            import json
            try:
                buf = io.BytesIO()
                np.save(buf, img.astype(np.float16), allow_pickle=False)
                write_atomic(disk, buf.getvalue())
                write_atomic(disk.with_suffix(".json"), json.dumps(info).encode())
            except OSError:
                pass
    with _sources_lock:
        if full:
            for k in [k for k in _sources if k[1] == "full" and k != key]:
                del _sources[k]
        _sources[key] = (img, info)
        _sources.move_to_end(key)
        limit = SOURCE_CACHE_ENTRIES
        while len(_sources) > limit:
            _sources.popitem(last=False)
    return img, info


def drop_source(pid: int) -> None:
    with _sources_lock:
        for k in [k for k in _sources if k[0] == pid]:
            del _sources[k]
    for p in (source_path(pid), source_path(pid).with_suffix(".json")):
        try:
            p.unlink()
        except OSError:
            continue


def render_rgb8(pid: int, long: int, settings: dict | None = None) -> np.ndarray:
    from app.develop import render
    cat = catalog_mod.get()
    row = cat.row("SELECT develop FROM photos WHERE id=?", (pid,))
    if row is None:
        raise FileNotFoundError(f"No photo with id {pid}")
    dev = settings if settings is not None else loads(row["develop"], {})
    full = not long or long > PREVIEW
    img, info = source(pid, None if full else PREVIEW, full=full)
    out = render.render(img, info, dev, max_long=long or None, photo_id=pid, src_long=max(img.shape[:2]) if full else None)
    return render.to_u8(out)


def rendered(pid: int, size: str) -> Path:
    cat = catalog_mod.get()
    rev = int(cat.scalar("SELECT develop_rev FROM photos WHERE id=?", (pid,)) or 0)
    out = thumb_path(pid, rev, size)
    if out.is_file():
        return out
    long = {"t": THUMB, "p": PREVIEW}.get(size, 0)
    rgb8 = render_rgb8(pid, long)
    write_atomic(out, encode_jpeg(rgb8, {"t": 82, "p": 88}.get(size, 92)))
    for old in cache_dir(pid).glob(f"{pid}-*-{size}.jpg"):
        if old != out:
            try:
                old.unlink()
            except OSError:
                continue
    return out


def request(pid: int, size: str, foreground: bool = False) -> Future:
    cat = catalog_mod.get()
    rev = int(cat.scalar("SELECT develop_rev FROM photos WHERE id=?", (pid,)) or 0)

    def job() -> Path:
        p = rendered(pid, size)
        events.publish("render", id=pid, rev=rev, size=size)
        return p
    return _once(f"{pid}:{rev}:{size}", _fg if foreground else _bg, job)


def best_thumb(pid: int) -> tuple[Path | None, bool]:
    cat = catalog_mod.get()
    r = cat.row("SELECT develop_rev FROM photos WHERE id=?", (pid,))
    if r is None:
        return None, False
    rev = int(r["develop_rev"])
    p = thumb_path(pid, rev, "t")
    if p.is_file():
        return p, True
    request(pid, "t")
    older = sorted(cache_dir(pid).glob(f"{pid}-*-t.jpg"), key=lambda x: x.stat().st_mtime, reverse=True)
    if older:
        return older[0], False
    e = embedded_path(pid)
    if e.is_file():
        return e, False
    path = cat.photo_path(pid)
    if path and path.is_file():
        return make_embedded(pid, path), False
    return None, False


def best_preview(pid: int, wait: float = 0.0) -> tuple[Path | None, bool]:
    cat = catalog_mod.get()
    rev = int(cat.scalar("SELECT develop_rev FROM photos WHERE id=?", (pid,)) or 0)
    p = thumb_path(pid, rev, "p")
    if p.is_file():
        return p, True
    fut = request(pid, "p", foreground=True)
    if wait > 0:
        try:
            return fut.result(timeout=wait), True
        except Exception:
            pass
    older = sorted(cache_dir(pid).glob(f"{pid}-*-p.jpg"), key=lambda x: x.stat().st_mtime, reverse=True)
    if older:
        return older[0], False
    t, ok = best_thumb(pid)
    return t, False


def build_all(ids: list[int], size: str, progress) -> int:
    done = 0
    for pid in ids:
        if progress.cancelled:
            break
        try:
            rendered(pid, size)
        except Exception:
            pass
        done += 1
        progress(done, len(ids), f"Building previews {done} of {len(ids)}")
    return done


def warm(ids: list[int]) -> None:
    for pid in ids:
        request(pid, "t")


def now() -> float:
    return time.time()
