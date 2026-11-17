"""A camera is an outside device: the names it reports and the paths its helper answers are not trusted. A name that
could leave the import folder ("..\\..\\x.CR3", "a/b.CR3") is refused before anything is copied, a path the helper
returns is never used, and Move deletes from the camera only the files the import reports by name as imported; when
that report is missing or does not match the files copied, nothing is deleted."""
from pathlib import Path

import pytest

from test_camera_import import FakeCamera, Gphoto2, jpeg_bytes

HOSTILE = ["..\\..\\x.CR3", "a/b.CR3", "..", "c:x.CR3"]


class HostileCamera(FakeCamera):
    def __init__(self, good: bytes):
        super().__init__({"DCIM/ok.JPG": good})
        self.fetched: list[str] = []

    def list_dir(self, folder):
        from app.services.cameras import Entry

        if folder.strip("/") in ("", ):
            return ["DCIM"], []
        return [], [Entry(n, 10, 0.0) for n in HOSTILE] + [Entry("ok.JPG", len(self.files["DCIM/ok.JPG"]), 0.0)]

    def fetch(self, file, dest):
        self.fetched.append(file)
        target = dest / file.rsplit("/", 1)[-1]
        target.write_bytes(self.files[file])
        return target


@pytest.mark.parametrize("name", HOSTILE + ["", " ", "x\x00.CR3"])
def test_unsafe_camera_names_are_refused(name):
    from app.services.cameras import CameraError, safe_name

    with pytest.raises(CameraError):
        safe_name(name)


def test_hostile_names_are_refused_reported_and_never_deleted(client, commands, tmp_path):
    from app.core import config
    from app.services import cameras

    cam = HostileCamera(jpeg_bytes("hostile-ok"))
    old = cameras.set_providers([lambda: [cam]])
    try:
        res = commands("library.import", {"paths": [cameras.path_for(cam.id, "DCIM")], "mode": "move", "destination": str(tmp_path / "lib"),
                                          "folderTemplate": "", "wait": True})
    finally:
        cameras.set_providers(old)
    assert res["count"] == 1 and cam.fetched == ["DCIM/ok.JPG"] and cam.deleted == ["DCIM/ok.JPG"]
    refused = [f for f in res["failed"] if "Refused a file name" in f["error"]]
    assert sorted(f["path"].rsplit("/DCIM/", 1)[1] for f in refused) == sorted(cameras.path_for("x", n).split("/", 3)[3] for n in HOSTILE if n != ".."), res["failed"]
    assert sorted(p.name for p in (tmp_path / "lib").iterdir()) == ["ok.JPG"]
    for base in (tmp_path, config.temp_dir(), config.temp_dir().parent):
        assert not (base / "x.CR3").exists() and not (base / "b.CR3").exists()


def test_a_file_that_lands_outside_its_slot_is_refused(client, tmp_path):
    from app.services.cameras import Entry, transfer

    class Escaping(FakeCamera):
        def fetch(self, file, dest):
            out = dest.parent / "escaped.JPG"
            out.write_bytes(b"x")
            return out

    cam = Escaping({"DCIM/IMG_0001.JPG": b"x"})
    staged, failed = transfer._fetch([(cam, "DCIM/IMG_0001.JPG", Entry("IMG_0001.JPG", 1, 0.0))], tmp_path, 0, 1, None)
    assert staged == [] and "did not arrive" in failed[0]["error"]


class Wpd:
    def __init__(self, outside: Path):
        self.outside = outside
        self.requests: list[dict] = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        return {"path": str(self.outside)}


def test_the_wpd_reply_path_is_never_trusted(tmp_path):
    from app.services.cameras import CameraError, wpd

    outside = tmp_path / "elsewhere" / "IMG_0001.CR3"
    outside.parent.mkdir()
    outside.write_bytes(b"not from the camera")
    fake = Wpd(outside)
    cam = wpd.WpdCamera("Canon EOS R5", "key", fake)
    dest = tmp_path / "slot"
    with pytest.raises(CameraError):
        cam.fetch("SD/DCIM/IMG_0001.CR3", dest)
    assert outside.read_bytes() == b"not from the camera" and not any(dest.iterdir())
    assert fake.requests[-1]["name"] == "IMG_0001.CR3"


@pytest.mark.parametrize("name", ["..\\..\\x.CR3", "..", "c:x.CR3"])
def test_wpd_and_gphoto2_refuse_a_hostile_name_before_asking_the_camera(tmp_path, name):
    from app.services.cameras import CameraError, gphoto, wpd

    fake = Wpd(tmp_path / "x")
    with pytest.raises(CameraError):
        wpd.WpdCamera("Canon EOS R5", "key", fake).fetch(f"SD/DCIM/{name}", tmp_path / "slot")
    with pytest.raises(CameraError):
        wpd.WpdCamera("Canon EOS R5", "key", fake).delete(f"SD/DCIM/{name}")
    assert fake.requests == []
    runner = Gphoto2()
    cam = gphoto.GphotoCamera("/usr/bin/gphoto2", "Canon EOS R5", "usb:001,007", runner)
    with pytest.raises(CameraError):
        cam.fetch(f"store_00020001/DCIM/100CANON/{name}", tmp_path / "slot2")
    with pytest.raises(CameraError):
        cam.delete(f"store_00020001/DCIM/100CANON/{name}")
    assert runner.calls == []


def test_gphoto2_writes_to_a_name_formlit_chose(tmp_path):
    from app.services.cameras import gphoto

    folder = "/store_00020001/DCIM/100CANON"
    runner = Gphoto2(folders={folder: "#1     IMG_0001.CR3               rd     1 KB image/x-canon-cr3\n"})
    cam = gphoto.GphotoCamera("/usr/bin/gphoto2", "Canon EOS R5", "usb:001,007", runner)
    got = cam.fetch("store_00020001/DCIM/100CANON/IMG_0001.CR3", tmp_path)
    call = next(c for c in runner.calls if "--get-file" in c)
    assert call[call.index("--filename") + 1] == str((tmp_path / "IMG_0001.CR3").resolve()) and "%f" not in " ".join(call)
    assert got == (tmp_path / "IMG_0001.CR3").resolve()


class Recorder:
    id = "rec"
    name = "Recorder"

    def __init__(self):
        self.deleted: list[str] = []

    def delete(self, rel):
        self.deleted.append(rel)


def staged_list(tmp_path, n):
    dev = Recorder()
    return dev, [((tmp_path / f"{i}" / f"IMG_{i}.JPG"), dev, f"DCIM/IMG_{i}.JPG") for i in range(n)]


def test_move_deletes_exactly_the_imported_files(tmp_path):
    from app.services.cameras import transfer

    dev, staged = staged_list(tmp_path, 5)
    p = [str(s[0]) for s in staged]
    res = {"ids": [10, 11], "imported": [p[0], p[3]], "skipped": [p[1]], "failed": [{"path": p[2], "error": "bad"}]}
    _, _, kept = transfer._settle(staged, res, True)
    assert dev.deleted == ["DCIM/IMG_0.JPG", "DCIM/IMG_3.JPG"] and kept == []


@pytest.mark.parametrize("res", [
    {"ids": [10, 11], "imported": ["A"], "skipped": [], "failed": []},
    {"ids": [10], "skipped": [], "failed": []},
    {"ids": [10], "imported": ["/not/staged.JPG"], "skipped": [], "failed": []},
    {"ids": [10, 11], "imported": ["P0", "P0"], "skipped": [], "failed": []},
    {"ids": [10], "imported": ["P1"], "skipped": ["P1"], "failed": []},
], ids=["short", "missing", "unknown-path", "repeated", "also-skipped"])
def test_a_result_that_does_not_match_deletes_nothing(tmp_path, res):
    from app.services.cameras import transfer

    dev, staged = staged_list(tmp_path, 3)
    names = {f"P{i}": str(s[0]) for i, s in enumerate(staged)}
    fixed = {**res}
    for key in ("imported", "skipped"):
        if key in fixed:
            fixed[key] = [names.get(x, x) for x in fixed[key]]
    _, _, kept = transfer._settle(staged, fixed, True)
    assert dev.deleted == [] and len(kept) == 3


def test_the_importer_reports_the_files_it_imported(client, tmp_path):
    from app.services import importer

    paths = []
    for i in range(3):
        f = tmp_path / f"IMG_{i}.JPG"
        f.write_bytes(jpeg_bytes(f"report-{i}-{tmp_path.name}"))
        paths.append(str(f.resolve()))
    first = importer.import_files(paths[:1], "add")
    res = importer.import_files(paths + [str(tmp_path / "missing.JPG")], "add")
    assert first["imported"] == paths[:1]
    assert res["imported"] == paths[1:] and res["skipped"] == paths[:1] and len(res["ids"]) == 2
