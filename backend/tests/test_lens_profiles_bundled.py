"""Lens profiles without a download. The Lensfun database ships unmodified in shared/lensfun, so profile correction
works offline on first run; a later download still updates it and wins only when it is newer than the bundled copy.
Canon RF lenses are matched from the LensModel a CR3 carries (its CMT2 box), and a lens that Lensfun does not have,
such as a Z version or an aperture that differs, is not matched to a different lens."""
import io
import json
import struct
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from conftest import gradient

RF_MATCHES = [
    ("RF15-35mm F2.8 L IS USM", 24, "Canon RF 15-35mm F2.8L IS USM"),
    ("RF24-70mm F2.8 L IS USM", 50, "Canon RF 24-70mm F2.8L IS USM"),
    ("RF70-200mm F2.8 L IS USM", 135, "Canon RF 70-200mm F2.8L IS USM"),
    ("RF24-105mm F4 L IS USM", 50, "Canon RF 24-105mm F4L IS USM"),
    ("RF24-105mm F4-7.1 IS STM", 50, "Canon RF 24-105mm F4-7.1 IS STM"),
    ("RF14-35mm F4 L IS USM", 20, "Canon RF 14-35mm F4 L IS USM"),
    ("RF100-500mm F4.5-7.1 L IS USM", 300, "Canon RF 100-500mm F4.5-7.1L IS USM"),
    ("RF28-70mm F2 L USM", 50, "Canon RF 28-70mm F2 L USM"),
    ("RF50mm F1.2 L USM", 50, "Canon RF 50mm F1.2 L USM"),
    ("RF50mm F1.8 STM", 50, "Canon RF 50mm F1.8 STM"),
    ("RF85mm F1.2 L USM", 85, "Canon RF 85mm F1.2L USM"),
    ("RF35mm F1.8 MACRO IS STM", 35, "Canon RF 35mm F1.8 MACRO IS STM"),
    ("RF100mm F2.8 L MACRO IS USM", 100, "Canon RF 100mm F2.8L Macro IS USM"),
    ("RF24-240mm F4-6.3 IS USM", 100, "Canon RF 24-240mm F4-6.3 IS USM"),
    ("RF10-20mm F4 L IS STM", 15, "Canon RF 10-20mm f/4L IS STM"),
    ("RF-S18-45mm F4.5-6.3 IS STM", 30, "Canon RF-S 18-45mm F4.5-6.3 IS STM"),
    ("RF-S18-150mm F3.5-6.3 IS STM", 50, "Canon RF-S 18-150mm F3.5-6.3 IS STM"),
    ("RF800mm F11 IS STM", 800, "Canon RF 800mm F11 IS STM"),
]
NOT_IN_LENSFUN = [("RF24-70mm F2.8 L IS USM Z", 50), ("RF70-200mm F2.8 L IS USM Z", 135), ("RF24-105mm F2.8 L IS USM Z", 50),
                  ("RF20mm F1.4 L VCM", 20), ("RF100-300mm F2.8 L IS USM", 200)]


@pytest.fixture
def bundled_only(client, tmp_path, monkeypatch):
    from app.services import lensdb

    monkeypatch.setenv("FORMLIT_MODELS_DIR", str(tmp_path / "models"))
    lensdb.reload()
    yield lensdb
    lensdb.reload()


def test_the_bundled_database_works_without_a_download(bundled_only):
    lensdb = bundled_only
    assert not lensdb.index_path().is_file()
    assert lensdb.available() and lensdb.source()["source"] == "bundled"
    assert len(lensdb.index()["lenses"]) > 1000
    assert lensdb.camera("Canon", "Canon EOS R5")["mount"] == "Canon RF"


def test_the_bundled_copy_carries_its_licence_and_source(bundled_only):
    folder = bundled_only.bundled_folder()
    assert "Attribution-ShareAlike 3.0" in (folder / "COPYING.CC_BY-SA_3.0").read_text(encoding="utf-8")
    source = (folder / "SOURCE.txt").read_text(encoding="utf-8")
    assert "github.com/lensfun/lensfun" in source and "CC BY-SA 3.0" in source and bundled_only.bundled_snapshot()


def test_the_download_list_names_every_bundled_file(bundled_only):
    stems = {p.stem for p in (bundled_only.bundled_folder() / "db").glob("*.xml")}
    assert stems <= set(bundled_only.FILES), sorted(stems - set(bundled_only.FILES))


@pytest.mark.parametrize("exif,focal,want", RF_MATCHES, ids=[m[0] for m in RF_MATCHES])
def test_canon_rf_lenses_match_their_lensfun_profile(bundled_only, exif, focal, want):
    lens, score = bundled_only.match(exif, "Canon", "Canon EOS R5", float(focal))
    assert lens is not None and lens["model"] == want and score >= 0.6, (lens and lens["model"], score)
    assert lens["dist"], want


@pytest.mark.parametrize("exif,focal", NOT_IN_LENSFUN, ids=[m[0] for m in NOT_IN_LENSFUN])
def test_a_lens_lensfun_lacks_is_not_given_another_lens_profile(bundled_only, exif, focal):
    lens, score = bundled_only.match(exif, "Canon", "Canon EOS R5", float(focal))
    assert lens is None or score < 0.6, lens["model"]


def test_a_lens_without_a_focal_element_takes_its_range_from_its_name(bundled_only):
    lens = bundled_only.lens("Canon RF 24-105mm F4L IS USM")
    assert (lens["fmin"], lens["fmax"]) == (24.0, 105.0)


def test_a_newer_download_replaces_the_bundled_copy_and_an_older_one_does_not(bundled_only):
    lensdb = bundled_only
    entry = {"maker": "Test", "model": "Test 50mm f/2", "mounts": ["Canon RF"], "crop": 1.0, "aspect": 1.5, "fmin": 50.0, "fmax": 50.0,
             "dist": [{"focal": 50.0, "model": "ptlens", "a": 0.0, "b": 0.01, "c": 0.0, "k1": 0.0, "k2": 0.0}], "tca": [], "vig": []}
    lensdb.index_path().write_text(json.dumps({"cameras": [], "lenses": [entry], "mounts": {}, "downloaded": "2099-01-01"}), encoding="utf-8")
    lensdb.reload()
    assert lensdb.source()["source"] == "downloaded" and [ln["model"] for ln in lensdb.index()["lenses"]] == ["Test 50mm f/2"]
    lensdb.index_path().write_text(json.dumps({"cameras": [], "lenses": [entry], "mounts": {}, "downloaded": "2001-01-01"}), encoding="utf-8")
    lensdb.reload()
    assert lensdb.source()["source"] == "bundled" and len(lensdb.index()["lenses"]) > 1000


def _tiff(entries: list[tuple[int, int, bytes, int]]) -> bytes:
    rows, data = b"", b""
    base = 8 + 2 + 12 * len(entries) + 4
    for tag, typ, raw, count in sorted(entries):
        if len(raw) <= 4:
            rows += struct.pack("<HHI", tag, typ, count) + raw.ljust(4, b"\x00")
        else:
            rows += struct.pack("<HHII", tag, typ, count, base + len(data))
            data += raw
    return b"II*\x00" + struct.pack("<I", 8) + struct.pack("<H", len(entries)) + rows + b"\x00\x00\x00\x00" + data


def _ascii(tag: int, text: str) -> tuple[int, int, bytes, int]:
    raw = text.encode() + b"\x00"
    return tag, 2, raw, len(raw)


def _rational(tag: int, num: int, den: int) -> tuple[int, int, bytes, int]:
    return tag, 5, struct.pack("<II", num, den), 1


def _box(name: bytes, body: bytes) -> bytes:
    return struct.pack(">I", 8 + len(body)) + name + body


def fake_cr3(path: Path, lens: str, focal: int) -> Path:
    cmt1 = _tiff([_ascii(0x010F, "Canon"), _ascii(0x0110, "Canon EOS R5")])
    cmt2 = _tiff([_ascii(0xA434, lens), _rational(0x920A, focal, 1), _rational(0x829D, 4, 1)])
    uuid = _box(b"uuid", b"\x85\xc0\xb6\x87\x82\x0f\x11\xe0\x81\x11\xf4\xce\x46\x2b\x6a\x48" + _box(b"CMT1", cmt1) + _box(b"CMT2", cmt2))
    path.write_bytes(_box(b"ftyp", b"crx \x00\x00\x00\x01crx isom") + _box(b"moov", uuid) + b"\x00" * 64)
    return path


def test_the_lens_in_a_cr3_is_read_and_matched_offline(bundled_only, tmp_path):
    from app.services import metadata

    exif = metadata.read_exif(fake_cr3(tmp_path / "IMG_0001.CR3", "RF24-105mm F4 L IS USM", 70))
    assert exif["lens"] == "RF24-105mm F4 L IS USM" and exif["camera"] == "Canon EOS R5" and exif["focal"] == 70
    lens, score = bundled_only.match(exif["lens"], exif["make"], exif["model"], exif["focal"])
    assert lens["model"] == "Canon RF 24-105mm F4L IS USM" and score >= 0.6


def _canon_jpeg(path: Path, lens: str, focal: float) -> Path:
    im = Image.fromarray(gradient(120, 80))
    exif = Image.Exif()
    exif[0x010F] = "Canon"
    exif[0x0110] = "Canon EOS R5"
    sub = exif.get_ifd(0x8769)
    sub[0xA434] = lens
    sub[0x920A] = focal
    sub[0x829D] = 4.0
    buf = io.BytesIO()
    im.save(buf, "JPEG", exif=exif, quality=92)
    path.write_bytes(buf.getvalue())
    return path


def test_profile_corrections_find_the_rf_lens_on_first_run(bundled_only, commands, tmp_path):
    src = _canon_jpeg(tmp_path / "rf.jpg", "RF24-105mm F4 L IS USM", 35.0)
    pid = commands("library.import", {"paths": [str(src)], "mode": "add", "wait": True})["ids"][0]
    info = commands("develop.lensProfileInfo", {"id": pid})
    assert info["database"] and info["databaseSource"]["source"] == "bundled"
    assert info["guess"]["model"] == "Canon RF 24-105mm F4L IS USM", info
    res = commands("develop.lensProfile", {"ids": [pid], "enable": True})
    prof = commands("photo.get", {"id": pid})["develop"]["optics"]["profile"]
    assert prof["enabled"] and prof["lensfun"]["lens"] == "Canon RF 24-105mm F4L IS USM", res
    assert np.isfinite(prof["lensfun"]["dist"]["a"])
