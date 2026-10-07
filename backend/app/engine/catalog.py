import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.core import config
from app.engine import events

SCHEMA_VERSION = 1
UNDO_DEPTH = 300

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS folders(id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, parent_id INTEGER, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS photos(
  id INTEGER PRIMARY KEY,
  folder_id INTEGER NOT NULL,
  file_name TEXT NOT NULL,
  sidecars TEXT NOT NULL DEFAULT '[]',
  master_id INTEGER,
  copy_name TEXT,
  kind TEXT NOT NULL DEFAULT 'other',
  format TEXT NOT NULL DEFAULT '',
  file_size INTEGER NOT NULL DEFAULT 0,
  file_mtime REAL NOT NULL DEFAULT 0,
  content_hash TEXT NOT NULL DEFAULT '',
  width INTEGER NOT NULL DEFAULT 0,
  height INTEGER NOT NULL DEFAULT 0,
  capture_time TEXT,
  import_time TEXT,
  edit_time TEXT,
  rating INTEGER NOT NULL DEFAULT 0,
  flag INTEGER NOT NULL DEFAULT 0,
  label TEXT NOT NULL DEFAULT '',
  camera TEXT NOT NULL DEFAULT '',
  lens TEXT NOT NULL DEFAULT '',
  focal REAL, aperture REAL, shutter REAL, iso INTEGER, bias REAL, flash INTEGER,
  gps_lat REAL, gps_lon REAL, gps_alt REAL, gps_dir REAL,
  meta TEXT NOT NULL DEFAULT '{}',
  exif TEXT NOT NULL DEFAULT '{}',
  develop TEXT NOT NULL DEFAULT '{}',
  develop_rev INTEGER NOT NULL DEFAULT 0,
  edited INTEGER NOT NULL DEFAULT 0,
  stack_id INTEGER,
  stack_pos INTEGER NOT NULL DEFAULT 0,
  missing INTEGER NOT NULL DEFAULT 0,
  smart_preview INTEGER NOT NULL DEFAULT 0,
  duration REAL,
  xmp_state INTEGER NOT NULL DEFAULT 0,
  xmp_time REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS photos_folder ON photos(folder_id);
CREATE INDEX IF NOT EXISTS photos_capture ON photos(capture_time);
CREATE INDEX IF NOT EXISTS photos_hash ON photos(content_hash);
CREATE INDEX IF NOT EXISTS photos_master ON photos(master_id);
CREATE INDEX IF NOT EXISTS photos_stack ON photos(stack_id);
CREATE TABLE IF NOT EXISTS stacks(id INTEGER PRIMARY KEY, collapsed INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS collections(id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, parent_id INTEGER, rules TEXT, sort TEXT, position INTEGER NOT NULL DEFAULT 0, target INTEGER NOT NULL DEFAULT 0, service_id INTEGER, cover_id INTEGER, settings TEXT);
CREATE TABLE IF NOT EXISTS collection_photos(collection_id INTEGER NOT NULL, photo_id INTEGER NOT NULL, position INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(collection_id, photo_id));
CREATE INDEX IF NOT EXISTS collection_photos_photo ON collection_photos(photo_id);
CREATE TABLE IF NOT EXISTS keywords(id INTEGER PRIMARY KEY, name TEXT NOT NULL, parent_id INTEGER, synonyms TEXT NOT NULL DEFAULT '[]', export INTEGER NOT NULL DEFAULT 1, person INTEGER NOT NULL DEFAULT 0);
CREATE UNIQUE INDEX IF NOT EXISTS keywords_unique ON keywords(COALESCE(parent_id, 0), name);
CREATE TABLE IF NOT EXISTS photo_keywords(photo_id INTEGER NOT NULL, keyword_id INTEGER NOT NULL, PRIMARY KEY(photo_id, keyword_id));
CREATE INDEX IF NOT EXISTS photo_keywords_kw ON photo_keywords(keyword_id);
CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY, photo_id INTEGER NOT NULL, name TEXT NOT NULL, settings TEXT NOT NULL, time TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS history_photo ON history(photo_id);
CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY, photo_id INTEGER NOT NULL, name TEXT NOT NULL, settings TEXT NOT NULL, time TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS faces(id INTEGER PRIMARY KEY, photo_id INTEGER NOT NULL, x REAL, y REAL, w REAL, h REAL, score REAL, embedding BLOB, person_id INTEGER, confirmed INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS faces_photo ON faces(photo_id);
CREATE TABLE IF NOT EXISTS people(id INTEGER PRIMARY KEY, name TEXT NOT NULL, keyword_id INTEGER);
CREATE TABLE IF NOT EXISTS publish_services(id INTEGER PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL, settings TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS published(collection_id INTEGER NOT NULL, photo_id INTEGER NOT NULL, rev INTEGER NOT NULL, remote TEXT, time TEXT, PRIMARY KEY(collection_id, photo_id));
CREATE TABLE IF NOT EXISTS locations(id INTEGER PRIMARY KEY, name TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL, radius REAL NOT NULL DEFAULT 0.2, private INTEGER NOT NULL DEFAULT 0);
"""

JSON_FIELDS = {"photos": {"sidecars", "meta", "exif", "develop"}, "collections": {"rules", "sort", "settings"}, "keywords": {"synonyms"}, "publish_services": {"settings"}}
LABELS = ["red", "yellow", "green", "blue", "purple"]


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


class Change:
    def __init__(self, cat: "Catalog", label: str, undoable: bool):
        self.cat = cat
        self.label = label
        self.undoable = undoable
        self.ops: list[tuple] = []
        self.photos: dict[int, set[str]] = {}
        self.lists: set[str] = set()
        self.added: list[int] = []
        self.removed: list[int] = []
        self.result: Any = None

    def _enc(self, table: str, key: str, value: Any) -> Any:
        if key in JSON_FIELDS.get(table, ()) and not isinstance(value, str) and value is not None:
            return json.dumps(value, separators=(",", ":"))
        return value

    def touch(self, table: str, row_id: int | None, fields) -> None:
        if table == "photos" and row_id is not None:
            self.photos.setdefault(int(row_id), set()).update(fields)
        elif table in ("collections", "collection_photos"):
            self.lists.add("collections")
        elif table in ("keywords", "photo_keywords"):
            self.lists.add("keywords")
            if table == "photo_keywords":
                self.lists.add("photoKeywords")
        elif table == "folders":
            self.lists.add("folders")
        elif table in ("people", "faces"):
            self.lists.add("people")
        elif table in ("publish_services", "published"):
            self.lists.add("publish")
        elif table == "stacks":
            self.lists.add("stacks")
        elif table == "locations":
            self.lists.add("locations")
        elif table == "meta":
            self.lists.add("meta")

    def update(self, table: str, row_id: int, **fields: Any) -> None:
        if not fields:
            return
        db = self.cat.db
        cols = ",".join(fields)
        before = db.execute(f"SELECT {cols} FROM {table} WHERE id=?", (row_id,)).fetchone()
        if before is None:
            return
        after = {k: self._enc(table, k, v) for k, v in fields.items()}
        prev = dict(before)
        changed = {k: v for k, v in after.items() if prev.get(k) != v}
        if not changed:
            return
        db.execute(f"UPDATE {table} SET {','.join(f'{k}=?' for k in changed)} WHERE id=?", (*changed.values(), row_id))
        self.ops.append(("update", table, row_id, {k: prev[k] for k in changed}, changed))
        self.touch(table, row_id, changed.keys())

    def insert(self, table: str, **row: Any) -> int:
        enc = {k: self._enc(table, k, v) for k, v in row.items()}
        cur = self.cat.db.execute(f"INSERT INTO {table}({','.join(enc)}) VALUES({','.join('?' * len(enc))})", tuple(enc.values()))
        rid = cur.lastrowid
        if "id" not in enc and table not in ("collection_photos", "photo_keywords", "published"):
            enc["id"] = rid
        self.ops.append(("insert", table, enc))
        if table == "photos":
            self.added.append(int(enc["id"]))
            from app.services import previews
            previews.drop_source(int(enc["id"]))
            previews.clear(int(enc["id"]))
        self.touch(table, enc.get("id") if table == "photos" else None, enc.keys())
        if table == "photo_keywords":
            self.touch("photos", enc["photo_id"], {"keywords"})
        if table == "collection_photos":
            self.touch("photos", enc["photo_id"], {"collections"})
        return int(rid or 0)

    def delete(self, table: str, **where: Any) -> int:
        db = self.cat.db
        clause = " AND ".join(f"{k}=?" for k in where)
        rows = [dict(r) for r in db.execute(f"SELECT * FROM {table} WHERE {clause}", tuple(where.values())).fetchall()]
        if not rows:
            return 0
        db.execute(f"DELETE FROM {table} WHERE {clause}", tuple(where.values()))
        for r in rows:
            self.ops.append(("delete", table, r))
            if table == "photos":
                self.removed.append(int(r["id"]))
            if table == "photo_keywords":
                self.touch("photos", r["photo_id"], {"keywords"})
            if table == "collection_photos":
                self.touch("photos", r["photo_id"], {"collections"})
            self.touch(table, r.get("id") if table == "photos" else None, r.keys())
        return len(rows)

    def set_meta(self, key: str, value: Any) -> None:
        db = self.cat.db
        row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        enc = json.dumps(value)
        if row is None:
            db.execute("INSERT INTO meta(key, value) VALUES(?, ?)", (key, enc))
            self.ops.append(("insert", "meta", {"key": key, "value": enc}))
        elif row["value"] != enc:
            db.execute("UPDATE meta SET value=? WHERE key=?", (enc, key))
            self.ops.append(("meta", key, row["value"], enc))
        self.touch("meta", None, ())


class Catalog:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.execute("PRAGMA foreign_keys=OFF")
        self.db.executescript(SCHEMA)
        have = {r["name"] for r in self.db.execute("PRAGMA table_info(photos)").fetchall()}
        for col, decl in (("xmp_state", "INTEGER NOT NULL DEFAULT 0"), ("xmp_time", "REAL NOT NULL DEFAULT 0")):
            if col not in have:
                self.db.execute(f"ALTER TABLE photos ADD COLUMN {col} {decl}")
        self.revision = 0
        self.undo_stack: list[Change] = []
        self.redo_stack: list[Change] = []
        if self.get_meta("schema") is None:
            with self.change("Create Catalog", undoable=False) as ch:
                ch.set_meta("schema", SCHEMA_VERSION)
                ch.set_meta("created", now_iso())
                ch.set_meta("labelNames", {"red": "Red", "yellow": "Yellow", "green": "Green", "blue": "Blue", "purple": "Purple"})

    def close(self) -> None:
        with self.lock:
            self.db.close()

    def get_meta(self, key: str, default: Any = None) -> Any:
        with self.lock:
            row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    @contextmanager
    def change(self, label: str, undoable: bool = True) -> Iterator[Change]:
        with self.lock:
            ch = Change(self, label, undoable)
            self.db.execute("BEGIN")
            try:
                yield ch
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            if not ch.ops:
                return
            self.revision += 1
            if undoable:
                self.undo_stack.append(ch)
                del self.undo_stack[:-UNDO_DEPTH]
                self.redo_stack.clear()
        self._announce(ch, label)

    def push_undo(self, label: str, ops: list[tuple]) -> None:
        if not ops:
            return
        with self.lock:
            entry = Change(self, label, True)
            entry.ops = list(ops)
            self.undo_stack.append(entry)
            del self.undo_stack[:-UNDO_DEPTH]
            self.redo_stack.clear()

    def _announce(self, ch: Change, label: str) -> None:
        if ch.added:
            events.publish("photos.added", ids=ch.added, revision=self.revision)
        if ch.removed:
            events.publish("photos.removed", ids=ch.removed, revision=self.revision)
        changed = {pid: sorted(f) for pid, f in ch.photos.items() if pid not in ch.added and pid not in ch.removed}
        if changed:
            events.publish("photos.changed", photos=changed, revision=self.revision, label=label)
        for name in sorted(ch.lists):
            events.publish("list.changed", list=name, revision=self.revision)

    def _apply(self, ops: list[tuple], reverse: bool, ch: Change) -> None:
        seq = reversed(ops) if reverse else ops
        for op in seq:
            kind = op[0]
            if kind == "update":
                _, table, rid, before, after = op
                vals = before if reverse else after
                self.db.execute(f"UPDATE {table} SET {','.join(f'{k}=?' for k in vals)} WHERE id=?", (*vals.values(), rid))
                ch.touch(table, rid, vals.keys())
            elif kind in ("insert", "delete"):
                _, table, row = op
                remove = (kind == "insert") == reverse
                if remove:
                    keys = ["id"] if "id" in row else list(row.keys())
                    self.db.execute(f"DELETE FROM {table} WHERE {' AND '.join(f'{k}=?' for k in keys)}", tuple(row[k] for k in keys))
                    if table == "photos":
                        ch.removed.append(int(row["id"]))
                else:
                    self.db.execute(f"INSERT OR REPLACE INTO {table}({','.join(row)}) VALUES({','.join('?' * len(row))})", tuple(row.values()))
                    if table == "photos":
                        ch.added.append(int(row["id"]))
                ch.touch(table, row.get("id") if table == "photos" else None, row.keys())
                if table in ("photo_keywords", "collection_photos"):
                    ch.touch("photos", row["photo_id"], {"keywords" if table == "photo_keywords" else "collections"})
            elif kind == "meta":
                _, key, before, after = op
                self.db.execute("UPDATE meta SET value=? WHERE key=?", (before if reverse else after, key))
                ch.touch("meta", None, ())

    def undo(self) -> str | None:
        with self.lock:
            if not self.undo_stack:
                return None
            entry = self.undo_stack.pop()
            ch = Change(self, entry.label, False)
            self.db.execute("BEGIN")
            try:
                self._apply(entry.ops, True, ch)
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            self.redo_stack.append(entry)
            self.revision += 1
        self._announce(ch, f"Undo {entry.label}")
        events.publish("undo", label=entry.label, revision=self.revision)
        return entry.label

    def redo(self) -> str | None:
        with self.lock:
            if not self.redo_stack:
                return None
            entry = self.redo_stack.pop()
            ch = Change(self, entry.label, False)
            self.db.execute("BEGIN")
            try:
                self._apply(entry.ops, False, ch)
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            self.undo_stack.append(entry)
            self.revision += 1
        self._announce(ch, f"Redo {entry.label}")
        events.publish("redo", label=entry.label, revision=self.revision)
        return entry.label

    def rows(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.db.execute(sql, args).fetchall()

    def row(self, sql: str, args: tuple = ()) -> sqlite3.Row | None:
        with self.lock:
            return self.db.execute(sql, args).fetchone()

    def scalar(self, sql: str, args: tuple = ()) -> Any:
        r = self.row(sql, args)
        return r[0] if r else None

    def photo(self, pid: int) -> sqlite3.Row | None:
        return self.row("SELECT p.*, f.path AS folder_path FROM photos p JOIN folders f ON f.id=p.folder_id WHERE p.id=?", (pid,))

    def photo_path(self, pid: int) -> Path | None:
        r = self.row("SELECT f.path, p.file_name FROM photos p JOIN folders f ON f.id=p.folder_id WHERE p.id=?", (pid,))
        return Path(r["path"]) / r["file_name"] if r else None

    def folder_id(self, ch: Change, folder: Path) -> int:
        folder = folder.resolve()
        r = self.db.execute("SELECT id FROM folders WHERE path=?", (str(folder),)).fetchone()
        if r:
            return int(r["id"])
        parent = folder.parent
        parent_id = None
        if parent != folder:
            pr = self.db.execute("SELECT id FROM folders WHERE path=?", (str(parent),)).fetchone()
            parent_id = int(pr["id"]) if pr else None
        fid = ch.insert("folders", path=str(folder), parent_id=parent_id, name=folder.name or str(folder))
        for child in self.db.execute("SELECT id FROM folders WHERE path LIKE ? AND parent_id IS NULL", (str(folder).rstrip("/\\") + "%",)).fetchall():
            cpath = Path(self.db.execute("SELECT path FROM folders WHERE id=?", (child["id"],)).fetchone()["path"])
            if cpath.parent == folder:
                ch.update("folders", int(child["id"]), parent_id=fid)
        return fid

    def keyword_id(self, ch: Change, path: str) -> int:
        parent = None
        kid = 0
        for part in [p.strip() for p in path.replace(">", "|").split("|") if p.strip()]:
            r = self.db.execute("SELECT id FROM keywords WHERE name=? AND COALESCE(parent_id, 0)=?", (part, parent or 0)).fetchone()
            kid = int(r["id"]) if r else ch.insert("keywords", name=part, parent_id=parent)
            parent = kid
        return kid

    def keyword_path(self, kid: int) -> str:
        parts = []
        cur: int | None = kid
        guard = 0
        while cur and guard < 64:
            r = self.row("SELECT name, parent_id FROM keywords WHERE id=?", (cur,))
            if not r:
                break
            parts.append(r["name"])
            cur = r["parent_id"]
            guard += 1
        return "|".join(reversed(parts))

    def photo_keywords(self, pid: int) -> list[str]:
        return [self.keyword_path(int(r["keyword_id"])) for r in self.rows("SELECT keyword_id FROM photo_keywords WHERE photo_id=?", (pid,))]


_catalog: Catalog | None = None
_catalog_lock = threading.Lock()


def get() -> Catalog:
    global _catalog
    with _catalog_lock:
        if _catalog is None:
            _catalog = Catalog(config.catalog_path())
        return _catalog


def reopen(path: Path) -> Catalog:
    global _catalog
    with _catalog_lock:
        if _catalog is not None:
            _catalog.close()
        _catalog = Catalog(path)
        return _catalog
