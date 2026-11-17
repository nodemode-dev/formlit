from pathlib import Path

import pytest

from test_camera_import import FakeCamera, jpeg_bytes


@pytest.fixture
def restore_providers(client):
    from app.services import cameras

    old = cameras.set_providers(None)
    yield cameras
    cameras.set_providers(old)


def test_a_refresh_keeps_the_same_camera_object_and_its_lock(restore_providers):
    from app.services.cameras import gphoto

    cameras = restore_providers
    made = []

    def provider():
        cam = gphoto.GphotoCamera("/usr/bin/gphoto2", "Canon EOS R5", "usb:001,007", lambda argv, t: (0, "", ""))
        made.append(cam)
        return [cam]

    cameras.set_providers([provider])
    first = cameras.devices(refresh=True)
    second = cameras.devices(refresh=True)
    assert len(made) == 2
    (dev_id, a), = first.items()
    assert second[dev_id] is a and second[dev_id]._lock is a._lock


def test_camera_thumbnails_wait_while_that_camera_imports(restore_providers, commands, tmp_path):
    cameras = restore_providers
    seen = []

    class Watching(FakeCamera):
        def fetch(self, file, dest):
            seen.append(cameras.thumbnail(cameras.path_for(self.id, file)))
            return super().fetch(file, dest)

    cam = Watching({"DCIM/100CANON/IMG_0001.JPG": jpeg_bytes("busy1")})
    cameras.set_providers([lambda: [cam]])
    path = cameras.path_for(cam.id, "DCIM/100CANON/IMG_0001.JPG")
    assert cameras.thumbnail(path)
    res = commands("library.import", {"paths": [cameras.path_for(cam.id, "DCIM")], "mode": "copy", "destination": str(tmp_path / "lib"), "wait": True})
    assert res["count"] == 1
    assert seen == [None]
    assert not cameras.busy(cam.id) and cameras.thumbnail(path)


def test_the_folder_token_keeps_the_camera_folder_name(restore_providers, commands, tmp_path):
    cameras = restore_providers
    cam = FakeCamera({"DCIM/100CANON/IMG_0001.JPG": jpeg_bytes("folder1"), "DCIM/101CANON/IMG_0002.JPG": jpeg_bytes("folder2")})
    cameras.set_providers([lambda: [cam]])
    dest = tmp_path / "lib"
    res = commands("library.import", {"paths": [cameras.path_for(cam.id, "DCIM")], "mode": "copy", "destination": str(dest), "folderTemplate": "{folder}",
                                      "wait": True})
    assert res["count"] == 2
    assert sorted(str(p.relative_to(dest)) for p in dest.rglob("*.JPG")) == [str(Path("100CANON/IMG_0001.JPG")), str(Path("101CANON/IMG_0002.JPG"))]


class Counting(FakeCamera):
    def __init__(self, files):
        super().__init__(files)
        self.listed: list[str] = []

    def list_dir(self, folder):
        self.listed.append(folder)
        return super().list_dir(folder)


def test_selected_files_list_their_folder_once(restore_providers):
    cameras = restore_providers
    names = [f"DCIM/100CANON/IMG_{i:04d}.JPG" for i in range(5)]
    cam = Counting({n: jpeg_bytes(n) for n in names})
    cameras.set_providers([lambda: [cam]])
    found = cameras.walk([cameras.path_for(cam.id, n) for n in names])
    assert [rel for _, rel, _ in found] == names
    assert cam.listed == ["DCIM/100CANON"]


def test_a_deep_device_root_stops_at_the_depth_and_time_budget(restore_providers):
    cameras = restore_providers
    deep = "/".join(f"d{i}" for i in range(9))
    cam = Counting({"DCIM/100CANON/IMG_0001.JPG": jpeg_bytes("deep1"), f"{deep}/IMG_0002.JPG": jpeg_bytes("deep2")})
    cameras.set_providers([lambda: [cam]])
    report: dict = {}
    found = cameras.walk([cameras.path_for(cam.id, "")], report=report)
    assert [rel for _, rel, _ in found] == ["DCIM/100CANON/IMG_0001.JPG"]
    assert report == {"truncated": True}
    assert max(len([p for p in f.split("/") if p]) for f in cam.listed) == cameras.WALK_DEPTH
    report = {}
    assert cameras.walk([cameras.path_for(cam.id, "")], seconds=-1.0, report=report) == [] and report == {"truncated": True}


def test_wpd_runs_windows_powershell_by_full_path_and_reads_a_bom(monkeypatch):
    import subprocess

    from app.services.cameras import wpd

    seen = {}

    class Done:
        returncode = 0
        stdout = '\ufeff{"dirs": ["DCIM"], "files": []}'.encode("utf-8")
        stderr = b""

    def run(argv, **kw):
        seen["argv"] = argv
        return Done()

    monkeypatch.setenv("SystemRoot", r"D:\Win")
    monkeypatch.setattr(subprocess, "run", run)
    assert wpd._run({"op": "list", "device": "x", "path": ""}, 5.0) == {"dirs": ["DCIM"], "files": []}
    assert seen["argv"][0] == r"D:\Win\System32\WindowsPowerShell\v1.0\powershell.exe"
    assert "UTF8Encoding $false" in wpd.SCRIPT and "[System.Text.Encoding]::UTF8" not in wpd.SCRIPT


def test_wpd_delete_checks_the_camera_no_longer_has_the_file():
    from app.services.cameras import wpd

    requests = []
    cam = wpd.WpdCamera("Canon EOS R5", r"\\?\usb#vid", lambda req, t: requests.append(req) or {"deleted": "IMG_0001.CR3"})
    cam.delete("DCIM/100CANON/IMG_0001.CR3")
    assert requests[-1]["op"] == "delete" and requests[-1]["folder"] == "DCIM/100CANON" and requests[-1]["name"] == "IMG_0001.CR3"
    block = wpd.SCRIPT.split("'delete' {", 1)[1].split("default {", 1)[0]
    assert block.index("Remove-Item") < block.index("Resolve-Item (Find-Device $shell $req.device) $req.folder") < block.index("it was copied, not moved")


def test_a_scan_says_when_the_walk_was_cut_short(restore_providers, commands):
    cameras = restore_providers
    deep = "/".join(f"d{i}" for i in range(9))
    cam = FakeCamera({f"{deep}/IMG_0002.JPG": jpeg_bytes("deep3")})
    cameras.set_providers([lambda: [cam]])
    res = commands("library.scan", {"paths": [cameras.path_for(cam.id, "")]})
    assert res["files"] == [] and res["truncated"] is True
