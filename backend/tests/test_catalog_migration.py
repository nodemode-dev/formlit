import json
import sqlite3

import pytest

LEGACY_PHOTOS = """
CREATE TABLE photos(
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
  duration REAL
);
"""
CREATED = "2025-01-02T03:04:05"
DEVELOP = {"light": {"exposure": 0.8}, "treatment": "bw"}


@pytest.fixture
def legacy(tmp_path):
    path = tmp_path / "old.fldb"
    db = sqlite3.connect(path)
    db.executescript(
        "CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);"
        "CREATE TABLE folders(id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, parent_id INTEGER, name TEXT NOT NULL);"
        "CREATE TABLE keywords(id INTEGER PRIMARY KEY, name TEXT NOT NULL, parent_id INTEGER, synonyms TEXT NOT NULL DEFAULT '[]', export INTEGER NOT NULL DEFAULT 1, person INTEGER NOT NULL DEFAULT 0);"
        "CREATE TABLE photo_keywords(photo_id INTEGER NOT NULL, keyword_id INTEGER NOT NULL, PRIMARY KEY(photo_id, keyword_id));"
        + LEGACY_PHOTOS
    )
    db.execute("INSERT INTO meta VALUES('schema', '1')")
    db.execute("INSERT INTO meta VALUES('created', ?)", (json.dumps(CREATED),))
    db.execute("INSERT INTO folders(id, path, name) VALUES(1, '/old/shoot', 'shoot')")
    db.execute("INSERT INTO keywords(id, name) VALUES(1, 'harbour')")
    for pid, rating, flag in ((1, 4, 1), (2, 1, -1)):
        db.execute("INSERT INTO photos(id, folder_id, file_name, rating, flag, label, develop, develop_rev, edited, meta, width, height) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                   (pid, 1, f"IMG_{pid}.JPG", rating, flag, "red" if pid == 1 else "", json.dumps(DEVELOP), 3, 1, json.dumps({"copyright": "kept"}), 600, 400))
    db.execute("INSERT INTO photo_keywords VALUES(1, 1)")
    db.commit()
    db.close()
    return path


def columns(path):
    db = sqlite3.connect(path)
    try:
        return {r[1] for r in db.execute("PRAGMA table_info(photos)")}
    finally:
        db.close()


def test_the_legacy_fixture_really_lacks_the_new_columns(legacy):
    assert not {"xmp_state", "xmp_time"} & columns(legacy)


def test_opening_an_old_catalog_adds_the_missing_columns(legacy):
    from app.engine.catalog import Catalog

    cat = Catalog(legacy)
    try:
        assert {"xmp_state", "xmp_time"} <= columns(legacy)
        assert cat.scalar("SELECT xmp_state FROM photos WHERE id=1") == 0
        assert cat.scalar("SELECT xmp_time FROM photos WHERE id=1") == 0
    finally:
        cat.close()


def test_opening_an_old_catalog_keeps_every_photo_and_its_edits(legacy):
    from app.engine.catalog import Catalog

    cat = Catalog(legacy)
    try:
        rows = {r["id"]: r for r in cat.rows("SELECT * FROM photos ORDER BY id")}
        assert sorted(rows) == [1, 2]
        assert (rows[1]["rating"], rows[1]["flag"], rows[1]["label"]) == (4, 1, "red")
        assert (rows[2]["rating"], rows[2]["flag"]) == (1, -1)
        assert json.loads(rows[1]["develop"]) == DEVELOP
        assert rows[1]["develop_rev"] == 3 and rows[1]["edited"] == 1
        assert json.loads(rows[1]["meta"]) == {"copyright": "kept"}
        assert (rows[1]["width"], rows[1]["height"]) == (600, 400)
        assert cat.photo_keywords(1) == ["harbour"]
        assert cat.photo_keywords(2) == []
    finally:
        cat.close()


def test_opening_an_old_catalog_keeps_its_identity(legacy):
    from app.engine.catalog import Catalog

    cat = Catalog(legacy)
    try:
        assert cat.get_meta("schema") == 1
        assert cat.get_meta("created") == CREATED
        assert cat.scalar("SELECT path FROM folders WHERE id=1") == "/old/shoot"
    finally:
        cat.close()


def test_an_old_catalog_gets_the_tables_it_never_had(legacy):
    from app.engine.catalog import Catalog

    cat = Catalog(legacy)
    try:
        names = {r["name"] for r in cat.rows("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"collections", "collection_photos", "history", "snapshots", "faces", "people", "publish_services", "published", "locations", "stacks"} <= names
    finally:
        cat.close()


def test_a_migrated_catalog_accepts_changes_and_undo(legacy):
    from app.engine.catalog import Catalog

    cat = Catalog(legacy)
    try:
        with cat.change("Rate") as ch:
            ch.update("photos", 1, rating=2, xmp_state=1)
        assert cat.scalar("SELECT rating FROM photos WHERE id=1") == 2
        assert cat.scalar("SELECT xmp_state FROM photos WHERE id=1") == 1
        cat.undo()
        assert cat.scalar("SELECT rating FROM photos WHERE id=1") == 4
        assert cat.scalar("SELECT xmp_state FROM photos WHERE id=1") == 0
    finally:
        cat.close()


def test_migrating_twice_changes_nothing(legacy):
    from app.engine.catalog import Catalog

    first = Catalog(legacy)
    snapshot = [dict(r) for r in first.rows("SELECT * FROM photos ORDER BY id")]
    first.close()
    second = Catalog(legacy)
    try:
        assert [dict(r) for r in second.rows("SELECT * FROM photos ORDER BY id")] == snapshot
        assert second.get_meta("created") == CREATED
    finally:
        second.close()


def test_a_new_catalog_starts_at_the_current_schema(tmp_path):
    from app.engine.catalog import SCHEMA_VERSION, Catalog

    cat = Catalog(tmp_path / "fresh.fldb")
    try:
        assert cat.get_meta("schema") == SCHEMA_VERSION
        assert {"xmp_state", "xmp_time"} <= columns(tmp_path / "fresh.fldb")
    finally:
        cat.close()
