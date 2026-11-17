import os
import shutil
import time
from pathlib import Path
from typing import Any

from app.core import config
from app.engine import catalog as catalog_mod
from app.services import cameras, decode, importer
from app.services.cameras import CameraError, Device, Entry

BATCH_BYTES = 4 << 30


def split(paths: list[str]) -> tuple[list[str], list[str]]:
    return [p for p in paths if not cameras.is_camera(p)], [p for p in paths if cameras.is_camera(p)]


def _same(entry: Entry, size: int) -> bool:
    return entry.size == size if entry.exact else abs(entry.size - size) < 1024


def scan(paths: list[str], recursive: bool = True, limit: int = 5000) -> dict:
    cat = catalog_mod.get()
    found = cameras.walk(paths, recursive, limit)
    sizes: dict[str, list[int]] = {}
    for r in cat.rows("SELECT file_name, file_size FROM photos"):
        sizes.setdefault(str(r["file_name"]).lower(), []).append(int(r["file_size"] or 0))
    out = []
    for dev, rel, e in found:
        dup = any(_same(e, s) for s in sizes.get(e.name.lower(), []))
        out.append({"path": cameras.path_for(dev.id, rel), "name": e.name, "size": e.size, "mtime": e.mtime, "kind": decode.kind_of(Path(e.name)),
                    "duplicate": dup, "inCatalog": False})
    return {"files": out, "count": len(out), "duplicates": sum(1 for f in out if f["duplicate"]), "truncated": len(found) >= limit}


def _batches(found: list[tuple[Device, str, Entry]]) -> list[list[tuple[Device, str, Entry]]]:
    out: list[list[tuple[Device, str, Entry]]] = []
    size = 0
    for item in found:
        if not out or (size + item[2].size > BATCH_BYTES and out[-1]):
            out.append([])
            size = 0
        out[-1].append(item)
        size += item[2].size
    return out


def _fetch(batch: list[tuple[Device, str, Entry]], staging: Path, offset: int, total: int, progress) -> tuple[list[tuple[Path, Device, str]], list[dict]]:
    staged: list[tuple[Path, Device, str]] = []
    failed: list[dict] = []
    for i, (dev, rel, e) in enumerate(batch):
        if progress is not None:
            if progress.cancelled:
                break
            progress(offset + i, total, f"Copying {e.name} from {dev.name}")
        slot = staging / f"{offset + i:06d}"
        slot.mkdir(parents=True, exist_ok=True)
        try:
            name = cameras.safe_name(e.name)
            if rel.rsplit("/", 1)[-1] != name or any(slot.iterdir()):
                raise CameraError(f"Refused a file name from the camera: {e.name!r}")
            dev.fetch(rel, slot)
            got = cameras.arrived(slot, name)
            if [p.name for p in slot.iterdir()] != [name]:
                raise CameraError(f"The camera sent more than {name}; nothing was imported from it")
            if e.exact and e.size and got.stat().st_size != e.size:
                raise CameraError(f"{e.name} came from the camera short ({got.stat().st_size} of {e.size} bytes)")
            if e.mtime:
                os.utime(got, (e.mtime, e.mtime))
            staged.append((got.resolve(), dev, rel))
        except (CameraError, OSError) as exc:
            failed.append({"path": cameras.path_for(dev.id, rel), "error": str(exc)})
    return staged, failed


def imported_set(staged: list[tuple[Path, Device, str]], res: dict) -> set[str] | None:
    done = res.get("imported")
    ids = res.get("ids")
    if not isinstance(done, list) or not isinstance(ids, list) or len(done) != len(ids) or len(set(done)) != len(done):
        return None
    known = {str(p) for p, _, _ in staged}
    if not set(done) <= known or set(done) & (set(res.get("skipped") or []) | {f.get("path") for f in res.get("failed") or []}):
        return None
    return set(done)


def _settle(staged: list[tuple[Path, Device, str]], res: dict, move: bool) -> tuple[list[str], list[dict], list[dict]]:
    back = {str(p): cameras.path_for(dev.id, rel) for p, dev, rel in staged}
    skipped = [back.get(s, s) for s in res["skipped"]]
    failed = [{**f, "path": back.get(f["path"], f["path"])} for f in res["failed"]]
    kept: list[dict] = []
    if move:
        done = imported_set(staged, res)
        if done is None:
            return skipped, failed, [{"path": path, "error": "Kept on the camera: the import result could not be matched to the files copied"}
                                     for path in back.values()]
        for p, dev, rel in staged:
            if str(p) not in done:
                continue
            try:
                dev.delete(rel)
            except (CameraError, OSError) as exc:
                kept.append({"path": cameras.path_for(dev.id, rel), "error": str(exc)})
    return skipped, failed, kept


def import_paths(paths: list[str], mode: str, destination: str, recursive: bool, progress, **options: Any) -> dict:
    found = cameras.walk(paths, recursive)
    target = destination or str(config.library_dir())
    wanted = "dng" if mode == "dng" else "copy"
    staging = config.temp_dir() / "camera" / str(time.time_ns())
    result: dict = {"ids": [], "skipped": [], "failed": [], "notDeleted": [], "count": 0}
    total = len(found)
    offset = 0
    try:
        for batch in _batches(found):
            staged, fetch_failed = _fetch(batch, staging, offset, total, progress)
            result["failed"].extend(fetch_failed)
            if staged:
                res = importer.import_files([str(p) for p, _, _ in staged], wanted, target, recursive=False, progress=None,
                                            start_seq=1 + len(result["ids"]), **options)
                skipped, failed, kept = _settle(staged, res, mode == "move")
                result["ids"].extend(res["ids"])
                result["skipped"].extend(skipped)
                result["failed"].extend(failed)
                result["notDeleted"].extend(kept)
            shutil.rmtree(staging, ignore_errors=True)
            offset += len(batch)
            if progress is not None and progress.cancelled:
                break
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    if progress is not None:
        progress(total, total, f"Imported {len(result['ids'])} photos from the camera")
    result["count"] = len(result["ids"])
    return result
