import hashlib
import json
import os
import shutil
import time
from datetime import date
from pathlib import Path
from typing import Any

from app.engine import catalog as catalog_mod
from app.engine.catalog import LABELS, now_iso
from app.services import decode, metadata, previews, rename

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".Trash", "$RECYCLE.BIN", "System Volume Information", ".formlit"}


def quick_hash(path: Path) -> str:
    h = hashlib.blake2b(digest_size=16)
    size = path.stat().st_size
    h.update(str(size).encode())
    with open(path, "rb") as f:
        h.update(f.read(262144))
        if size > 524288:
            f.seek(-262144, os.SEEK_END)
            h.update(f.read(262144))
    return h.hexdigest()


def walk(paths: list[str], recursive: bool = True, limit: int = 200_000, budget: float | None = None) -> list[Path]:
    out: list[Path] = []
    deadline = time.monotonic() + budget if budget else None
    for raw in paths:
        p = Path(raw).expanduser()
        if p.is_file():
            if decode.supported(p):
                out.append(p.resolve())
            continue
        if not p.is_dir():
            continue
        if recursive:
            for root, dirs, files in os.walk(p):
                if deadline is not None and time.monotonic() > deadline:
                    return out
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
                for name in sorted(files):
                    fp = Path(root) / name
                    if not name.startswith(".") and decode.supported(fp):
                        out.append(fp.resolve())
                        if len(out) >= limit:
                            return out
        else:
            for fp in sorted(p.iterdir()):
                if fp.is_file() and not fp.name.startswith(".") and decode.supported(fp):
                    out.append(fp.resolve())
    seen: set[Path] = set()
    unique = []
    for p in out:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def scan(paths: list[str], recursive: bool = True, limit: int = 5000) -> dict:
    cat = catalog_mod.get()
    files = walk(paths, recursive, limit, budget=6.0)
    known_paths = {(r["path"], r["file_name"]) for r in cat.rows("SELECT f.path, p.file_name FROM photos p JOIN folders f ON f.id=p.folder_id")}
    known_sizes = {(r["file_name"].lower(), r["file_size"]) for r in cat.rows("SELECT file_name, file_size FROM photos")}
    hashes = {r["content_hash"] for r in cat.rows("SELECT content_hash FROM photos WHERE content_hash != ''")} if len(files) <= 400 else set()
    out = []
    for p in files:
        try:
            st = p.stat()
        except OSError:
            continue
        in_catalog = (str(p.parent), p.name) in known_paths
        dup = in_catalog or (p.name.lower(), st.st_size) in known_sizes
        if not dup and hashes:
            try:
                dup = quick_hash(p) in hashes
            except OSError:
                dup = False
        out.append({"path": str(p), "name": p.name, "size": st.st_size, "mtime": st.st_mtime, "kind": decode.kind_of(p), "duplicate": dup, "inCatalog": in_catalog})
    return {"files": out, "count": len(out), "duplicates": sum(1 for f in out if f["duplicate"]), "truncated": len(files) >= limit}


def _meta_from(info: dict, preset: dict | None) -> dict:
    exif = info.get("exif", {})
    xmp = info.get("xmp", {})
    meta: dict[str, Any] = {}
    if exif.get("artist"):
        meta["creator"] = exif["artist"]
    if exif.get("copyright"):
        meta["copyright"] = exif["copyright"]
    meta.update(xmp.get("meta", {}))
    for k, v in (preset or {}).items():
        if v not in (None, "") and (k not in meta or not meta[k]):
            meta[k] = v
    return meta


def _destination(src: Path, info: dict, dest_root: Path, folder_tmpl: str, rename_tmpl: str, seq: int, custom: str) -> Path:
    rec = {"fileName": src.name, "captureTime": info.get("captureTime"), "camera": info.get("exif", {}).get("camera"), "folder": str(src.parent)}
    sub = rename.expand(folder_tmpl, rec, seq, custom) if folder_tmpl else ""
    name = (rename.expand(rename_tmpl, rec, seq, custom) + src.suffix.lower()) if rename_tmpl else src.name
    target = dest_root / sub / name if sub else dest_root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    return rename.unique(target)


def _transfer(src: Path, dst: Path, move: bool) -> None:
    tmp = dst.with_name(dst.name + ".formlit-part")
    shutil.copy2(src, tmp)
    if tmp.stat().st_size != src.stat().st_size:
        tmp.unlink()
        raise OSError(f"copy of {src.name} came out short")
    tmp.replace(dst)
    side = metadata.sidecar_path(src)
    if side.is_file():
        shutil.copy2(side, metadata.sidecar_path(dst))
    if move:
        src.unlink()
        if side.is_file():
            side.unlink()


def import_files(paths: list[str], mode: str = "add", destination: str = "", folder_template: str = "{date:%Y}/{date:%Y-%m-%d}",
                 rename_template: str = "", custom: str = "", develop: dict | None = None, meta_preset: dict | None = None,
                 keywords: list[str] | None = None, collection: int | None = None, skip_duplicates: bool = True,
                 recursive: bool = True, progress=None, backup: str = "") -> dict:
    cat = catalog_mod.get()
    files = walk(paths, recursive)
    hashes = {r["content_hash"] for r in cat.rows("SELECT content_hash FROM photos WHERE content_hash != ''")}
    known = {(r["path"], r["file_name"]) for r in cat.rows("SELECT f.path, p.file_name FROM photos p JOIN folders f ON f.id=p.folder_id")}
    dest_root = Path(destination).expanduser() if destination else None
    backup_root = Path(backup).expanduser() / f"Imported on {date.today().isoformat()}" if backup and mode in ("copy", "move", "dng") else None
    if mode in ("copy", "move", "dng") and dest_root is None:
        raise ValueError("Copy and Move need a destination folder")
    added: list[int] = []
    skipped: list[str] = []
    failed: list[dict] = []
    stamp = now_iso()
    total = len(files)
    merged: list[tuple] = []
    for i, src in enumerate(files):
        if progress is not None:
            if progress.cancelled:
                break
            progress(i, total, f"Importing {src.name}")
        try:
            if (str(src.parent), src.name) in known:
                skipped.append(str(src))
                continue
            h = quick_hash(src)
            if skip_duplicates and h in hashes:
                skipped.append(str(src))
                continue
            info = metadata.probe(src)
            final = src
            if mode in ("copy", "move", "dng") and dest_root is not None:
                final = _destination(src, info, dest_root, folder_template, rename_template, len(added) + 1, custom)
                converted = False
                if mode == "dng" and info.get("kind") == "raw" and final.suffix.lower() != ".dng":
                    from app.ai import dng as dng_mod
                    target = rename.unique(final.with_suffix(".dng"))
                    try:
                        converted = dng_mod.write_cfa_dng(src, target, {**info.get("exif", {}), "captureTime": info.get("captureTime")})
                    except Exception:
                        converted = False
                    if converted:
                        final = target
                        side = metadata.sidecar_path(src)
                        if side.is_file():
                            shutil.copy2(side, metadata.sidecar_path(final))
                        st = final.stat()
                        info = {**info, "format": "dng", "size": st.st_size, "mtime": st.st_mtime}
                if not converted:
                    _transfer(src, final, mode == "move")
                if backup_root is not None:
                    second = rename.unique(backup_root / src.name)
                    second.parent.mkdir(parents=True, exist_ok=True)
                    _transfer(src if converted else final, second, False)
            exif = info.get("exif", {})
            xmp = info.get("xmp", {})
            dev = dict(develop or {})
            if xmp.get("develop") and not dev:
                try:
                    dev = json.loads(xmp["develop"])
                except ValueError:
                    dev = {}
            if xmp.get("crs") and not dev:
                from app.services import xmp_presets
                dev = xmp_presets.from_crs(xmp["crs"])
            label = (xmp.get("label") or "").lower()
            sidecars = ["xmp"] if metadata.sidecar_path(final).is_file() else []
            with cat.change(f"Import {final.name}", undoable=False) as ch:
                fid = cat.folder_id(ch, final.parent)
                pid = ch.insert("photos", folder_id=fid, file_name=final.name, sidecars=sidecars, kind=info["kind"], format=info["format"],
                                file_size=info["size"], file_mtime=info["mtime"], content_hash=h, width=info.get("width", 0), height=info.get("height", 0),
                                capture_time=info.get("captureTime"), import_time=stamp, rating=max(0, min(5, int(xmp.get("rating", 0) or 0))),
                                flag=-1 if int(xmp.get("rating", 0) or 0) == -1 else 0, label=label if label in LABELS else "",
                                camera=exif.get("camera", ""), lens=exif.get("lens", ""), focal=exif.get("focal"), aperture=exif.get("aperture"),
                                shutter=exif.get("shutter"), iso=exif.get("iso"), bias=exif.get("bias"), flash=exif.get("flash"),
                                gps_lat=exif.get("gpsLat"), gps_lon=exif.get("gpsLon"), gps_alt=exif.get("gpsAlt"), gps_dir=exif.get("gpsDir"),
                                meta=_meta_from(info, meta_preset), exif={k: v for k, v in exif.items() if k != "all"} | {"all": exif.get("all", {})},
                                develop=dev, develop_rev=1 if dev else 0, edited=1 if dev else 0, duration=info.get("duration"))
                for kw in list(xmp.get("keywords", [])) + list(keywords or []):
                    kid = cat.keyword_id(ch, kw)
                    if not cat.db.execute("SELECT 1 FROM photo_keywords WHERE photo_id=? AND keyword_id=?", (pid, kid)).fetchone():
                        ch.insert("photo_keywords", photo_id=pid, keyword_id=kid)
                if collection:
                    ch.insert("collection_photos", collection_id=int(collection), photo_id=pid, position=len(added))
            merged.extend(ch.ops)
            hashes.add(h)
            known.add((str(final.parent), final.name))
            added.append(pid)
            previews.make_embedded(pid, final)
        except Exception as exc:
            failed.append({"path": str(src), "error": str(exc)})
    if added:
        cat.push_undo(f"Import {len(added)} Photos", [op for op in merged if not (op[0] == "insert" and op[1] == "folders")])
        with cat.change("Import", undoable=False) as ch:
            ch.set_meta("lastImport", added)
        previews.warm(added)
    if progress is not None:
        progress(total, total, f"Imported {len(added)} photos")
    return {"ids": added, "skipped": skipped, "failed": failed, "count": len(added)}
