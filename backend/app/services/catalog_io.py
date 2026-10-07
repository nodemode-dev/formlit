import json
import shutil
import sqlite3
from pathlib import Path
from typing import Callable

from app.core import config
from app.engine import catalog as catalog_mod
from app.engine import records
from app.engine.catalog import JSON_FIELDS, Catalog, now_iso
from app.services import rename

SIDECARS = (".xmp", ".XMP")


def _copy_file(src: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dst = dest_dir / src.name
    if not dst.exists():
        shutil.copy2(src, dst)
    for ext in SIDECARS:
        side = src.with_suffix(ext)
        if side.is_file() and not (dest_dir / side.name).exists():
            shutil.copy2(side, dest_dir / side.name)
    return dst


def _copy_tree(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)


def _preview_files(base: Path, pid: int) -> list[Path]:
    d = base / "Previews" / f"{pid // 1000:04d}"
    return sorted(d.glob(f"{pid}-*")) if d.is_dir() else []


def _with_family(db: sqlite3.Connection, ids: list[int]) -> list[int]:
    out = set(ids)
    for pid in ids:
        r = db.execute("SELECT master_id FROM photos WHERE id=?", (pid,)).fetchone()
        if r and r[0]:
            out.add(int(r[0]))
    return sorted(out, key=lambda p: (db.execute("SELECT master_id IS NOT NULL FROM photos WHERE id=?", (p,)).fetchone()[0], p))


def _keyword_path(db: sqlite3.Connection, kid: int) -> list[tuple]:
    chain = []
    cur = db.execute("SELECT id, name, parent_id, synonyms, export, person FROM keywords WHERE id=?", (kid,)).fetchone()
    while cur is not None:
        chain.insert(0, tuple(cur))
        cur = db.execute("SELECT id, name, parent_id, synonyms, export, person FROM keywords WHERE id=?", (cur[2],)).fetchone() if cur[2] is not None else None
    return chain


def export_catalog(ids: list[int], folder: str, name: str, negatives: bool = False, previews: bool = True, smart: bool = False,
                   progress: Callable | None = None) -> dict:
    cur = catalog_mod.get()
    safe = rename.safe(name or "Exported Catalog")
    base = Path(folder).expanduser() / safe
    target = base / f"{safe}.fldb"
    if target.exists():
        raise ValueError(f"A catalog already exists at {target}")
    base.mkdir(parents=True, exist_ok=True)
    out = Catalog(target)
    src, dst = cur.db, out.db
    src_base = cur.path.parent
    photo_cols = [r[1] for r in src.execute("PRAGMA table_info(photos)").fetchall() if r[1] != "id"]
    pids = _with_family(src, ids)
    folders: dict[str, int] = {}
    neg_dirs: dict[str, Path] = {}
    photo_map: dict[int, int] = {}
    stack_map: dict[int, int] = {}

    def folder_for(path: str) -> int:
        if path not in folders:
            parent = folders.get(str(Path(path).parent))
            folders[path] = int(dst.execute("INSERT INTO folders(path, parent_id, name) VALUES(?, ?, ?)", (path, parent, Path(path).name or path)).lastrowid)
        return folders[path]
    try:
        dst.execute("BEGIN")
        for i, pid in enumerate(pids):
            row = src.execute("SELECT * FROM photos WHERE id=?", (pid,)).fetchone()
            if row is None:
                continue
            fpath = src.execute("SELECT path FROM folders WHERE id=?", (row["folder_id"],)).fetchone()[0]
            data = {c: row[c] for c in photo_cols}
            if negatives:
                if fpath not in neg_dirs:
                    leaf = rename.safe(Path(fpath).name or "Photos")
                    cand, n = base / leaf, 2
                    while cand in neg_dirs.values():
                        cand, n = base / f"{leaf} {n}", n + 1
                    neg_dirs[fpath] = cand
                srcfile = Path(fpath) / row["file_name"]
                if srcfile.is_file() and not row["master_id"]:
                    _copy_file(srcfile, neg_dirs[fpath])
                fpath = str(neg_dirs[fpath])
            data["folder_id"] = folder_for(fpath)
            data["master_id"] = photo_map.get(int(row["master_id"])) if row["master_id"] else None
            data["smart_preview"] = row["smart_preview"] if smart else 0
            if row["stack_id"]:
                sid = int(row["stack_id"])
                if sid not in stack_map:
                    coll = src.execute("SELECT collapsed FROM stacks WHERE id=?", (sid,)).fetchone()
                    stack_map[sid] = int(dst.execute("INSERT INTO stacks(collapsed) VALUES(?)", (coll[0] if coll else 1,)).lastrowid)
                data["stack_id"] = stack_map[sid]
            cols = ", ".join(data)
            nid = int(dst.execute(f"INSERT INTO photos({cols}) VALUES({', '.join('?' * len(data))})", tuple(data.values())).lastrowid)
            photo_map[pid] = nid
            _copy_tree(src_base / "Masks" / str(pid), base / "Masks" / str(nid))
            for f in _preview_files(src_base, pid):
                keep = f.name.endswith(("-src.npy", "-src.json")) if smart else False
                keep = keep or (previews and f.suffix == ".jpg")
                if keep:
                    to = base / "Previews" / f"{nid // 1000:04d}" / f.name.replace(f"{pid}-", f"{nid}-", 1)
                    to.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, to)
            if progress is not None:
                progress(i + 1, len(pids), f"Exporting {i + 1} of {len(pids)}")
        kw_map: dict[int, int] = {}
        for pid, nid in photo_map.items():
            for (kid,) in src.execute("SELECT keyword_id FROM photo_keywords WHERE photo_id=?", (pid,)).fetchall():
                parent = None
                for k in _keyword_path(src, int(kid)):
                    if k[0] not in kw_map:
                        kw_map[k[0]] = int(dst.execute("INSERT INTO keywords(name, parent_id, synonyms, export, person) VALUES(?, ?, ?, ?, ?)",
                                                       (k[1], parent, k[3], k[4], k[5])).lastrowid)
                    parent = kw_map[k[0]]
                dst.execute("INSERT OR IGNORE INTO photo_keywords(photo_id, keyword_id) VALUES(?, ?)", (nid, kw_map[int(kid)]))
            for table in ("history", "snapshots"):
                for r in src.execute(f"SELECT name, settings, time FROM {table} WHERE photo_id=?", (pid,)).fetchall():
                    dst.execute(f"INSERT INTO {table}(photo_id, name, settings, time) VALUES(?, ?, ?, ?)", (nid, *tuple(r)))
        people: dict[int, int] = {}
        for pid, nid in photo_map.items():
            for f in src.execute("SELECT x, y, w, h, score, embedding, person_id, confirmed FROM faces WHERE photo_id=?", (pid,)).fetchall():
                person = None
                if f["person_id"] is not None:
                    if int(f["person_id"]) not in people:
                        p = src.execute("SELECT name, keyword_id FROM people WHERE id=?", (f["person_id"],)).fetchone()
                        people[int(f["person_id"])] = int(dst.execute("INSERT INTO people(name, keyword_id) VALUES(?, ?)",
                                                                      (p["name"] if p else "Person", kw_map.get(int(p["keyword_id"])) if p and p["keyword_id"] else None)).lastrowid)
                    person = people[int(f["person_id"])]
                dst.execute("INSERT INTO faces(photo_id, x, y, w, h, score, embedding, person_id, confirmed) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (nid, f["x"], f["y"], f["w"], f["h"], f["score"], f["embedding"], person, f["confirmed"]))
        col_map: dict[int, int] = {}

        def collection(cid: int) -> int:
            if cid not in col_map:
                c = src.execute("SELECT * FROM collections WHERE id=?", (cid,)).fetchone()
                parent = collection(int(c["parent_id"])) if c["parent_id"] else None
                col_map[cid] = int(dst.execute("INSERT INTO collections(name, kind, parent_id, rules, sort, position, target, settings) VALUES(?, ?, ?, ?, ?, ?, 0, ?)",
                                               (c["name"], c["kind"], parent, c["rules"], c["sort"], c["position"], c["settings"])).lastrowid)
            return col_map[cid]
        for pid, nid in photo_map.items():
            for r in src.execute("SELECT cp.collection_id, cp.position FROM collection_photos cp JOIN collections c ON c.id=cp.collection_id "
                                 "WHERE cp.photo_id=? AND c.kind IN ('collection', 'book', 'print', 'slideshow', 'web')", (pid,)).fetchall():
                dst.execute("INSERT OR IGNORE INTO collection_photos(collection_id, photo_id, position) VALUES(?, ?, ?)", (collection(int(r[0])), nid, r[1]))
        for c in src.execute("SELECT id FROM collections WHERE kind='smart'").fetchall():
            collection(int(c[0]))
        for key in ("labelNames",):
            v = src.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
            if v:
                dst.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)", (key, v[0]))
        dst.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('exportedFrom', ?)", (json.dumps(str(cur.path)),))
        dst.execute("COMMIT")
    except Exception:
        dst.execute("ROLLBACK")
        out.close()
        raise
    out.close()
    return {"path": str(target), "photos": len(photo_map), "negatives": negatives}


def _decoded(table: str, data: dict) -> dict:
    return {k: (records.loads(v, None) if k in JSON_FIELDS.get(table, set()) and isinstance(v, str) else v) for k, v in data.items()}


def import_catalog(path: str, mode: str = "add", destination: str = "", replace: bool = True, progress: Callable | None = None) -> dict:
    cur = catalog_mod.get()
    p = Path(path).expanduser()
    if p.is_dir():
        found = sorted(p.glob("*.fldb"))
        p = found[0] if found else p
    if p.suffix != ".fldb" or not p.is_file():
        raise ValueError(f"Not a formlit catalog: {p}")
    if p.resolve() == cur.path.resolve():
        raise ValueError("That is the open catalog")
    if mode == "copy" and not destination:
        raise ValueError("Choose a folder to copy the photos into")
    src = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    src_base = p.parent
    photo_cols = [r[1] for r in src.execute("PRAGMA table_info(photos)").fetchall() if r[1] != "id"]
    have_cols = {r[1] for r in cur.db.execute("PRAGMA table_info(photos)").fetchall()}
    rows = src.execute("SELECT p.*, f.path AS fpath FROM photos p JOIN folders f ON f.id=p.folder_id ORDER BY p.master_id IS NOT NULL, p.id").fetchall()
    photo_map: dict[int, int] = {}
    added, updated, kw_map, col_map = [], [], {}, {}
    copied: list[tuple[int, int]] = []
    with cur.change(f"Import from {p.stem}") as ch:
        stacks: dict[int, int] = {}
        for i, row in enumerate(rows):
            fpath = Path(row["fpath"])
            if mode == "copy" and not row["master_id"]:
                srcfile = fpath / row["file_name"]
                if srcfile.is_file():
                    fpath = _copy_file(srcfile, Path(destination).expanduser() / (fpath.name or "Photos")).parent
            existing = None
            if not row["master_id"]:
                existing = cur.db.execute("SELECT p.id FROM photos p JOIN folders f ON f.id=p.folder_id WHERE f.path=? AND p.file_name=? AND p.master_id IS NULL",
                                          (str(fpath.resolve()), row["file_name"])).fetchone()
            if existing is not None:
                nid = int(existing["id"])
                if replace:
                    rev = int(cur.db.execute("SELECT develop_rev FROM photos WHERE id=?", (nid,)).fetchone()[0])
                    fields = _decoded("photos", {k: row[k] for k in ("develop", "meta", "rating", "flag", "label", "capture_time", "gps_lat", "gps_lon", "edited") if k in photo_cols})
                    ch.update("photos", nid, develop_rev=rev + 1, **fields)
                    updated.append(nid)
                photo_map[int(row["id"])] = nid
                continue
            data = _decoded("photos", {c: row[c] for c in photo_cols if c in have_cols})
            data["folder_id"] = cur.folder_id(ch, fpath)
            data["master_id"] = photo_map.get(int(row["master_id"])) if row["master_id"] else None
            if row["stack_id"]:
                sid = int(row["stack_id"])
                if sid not in stacks:
                    stacks[sid] = ch.insert("stacks", collapsed=1)
                data["stack_id"] = stacks[sid]
            data["import_time"] = now_iso()
            nid = ch.insert("photos", **data)
            photo_map[int(row["id"])] = nid
            added.append(nid)
            copied.append((int(row["id"]), nid))
            if progress is not None:
                progress(i + 1, len(rows), f"Importing {i + 1} of {len(rows)}")
        for old, nid in photo_map.items():
            for (kid,) in src.execute("SELECT keyword_id FROM photo_keywords WHERE photo_id=?", (old,)).fetchall():
                if int(kid) not in kw_map:
                    chain = _keyword_path(src, int(kid))
                    kw_map[int(kid)] = cur.keyword_id(ch, "|".join(k[1] for k in chain))
                if not cur.db.execute("SELECT 1 FROM photo_keywords WHERE photo_id=? AND keyword_id=?", (nid, kw_map[int(kid)])).fetchone():
                    ch.insert("photo_keywords", photo_id=nid, keyword_id=kw_map[int(kid)])
            if nid in added:
                for table in ("history", "snapshots"):
                    for r in src.execute(f"SELECT name, settings, time FROM {table} WHERE photo_id=?", (old,)).fetchall():
                        ch.insert(table, photo_id=nid, name=r["name"], settings=r["settings"], time=r["time"])

        def collection(cid: int) -> int:
            if cid not in col_map:
                c = src.execute("SELECT * FROM collections WHERE id=?", (cid,)).fetchone()
                parent = collection(int(c["parent_id"])) if c["parent_id"] else None
                same = cur.db.execute("SELECT id FROM collections WHERE name=? AND kind=? AND COALESCE(parent_id, 0)=?", (c["name"], c["kind"], parent or 0)).fetchone()
                col_map[cid] = int(same["id"]) if same else ch.insert("collections", **_decoded("collections", {"name": c["name"], "kind": c["kind"], "parent_id": parent,
                                                                                                                "rules": c["rules"], "sort": c["sort"], "position": c["position"],
                                                                                                                "settings": c["settings"]}))
            return col_map[cid]
        for old, nid in photo_map.items():
            for r in src.execute("SELECT cp.collection_id, cp.position FROM collection_photos cp JOIN collections c ON c.id=cp.collection_id "
                                 "WHERE cp.photo_id=? AND c.kind IN ('collection', 'book', 'print', 'slideshow', 'web')", (old,)).fetchall():
                col = collection(int(r[0]))
                if not cur.db.execute("SELECT 1 FROM collection_photos WHERE collection_id=? AND photo_id=?", (col, nid)).fetchone():
                    ch.insert("collection_photos", collection_id=col, photo_id=nid, position=int(r[1]))
        for c in src.execute("SELECT id FROM collections WHERE kind='smart'").fetchall():
            collection(int(c[0]))
    src.close()
    for old, nid in copied:
        _copy_tree(src_base / "Masks" / str(old), config.masks_dir() / str(nid))
        for f in _preview_files(src_base, old):
            if f.name.endswith(("-src.npy", "-src.json")):
                to = config.previews_dir() / f"{nid // 1000:04d}" / f.name.replace(f"{old}-", f"{nid}-", 1)
                to.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, to)
    return {"added": added, "updated": updated, "catalog": str(p)}
