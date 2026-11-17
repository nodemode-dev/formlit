"""Import straight from a camera on USB. A camera in PTP or MTP mode has no drive letter or mount point, so the
importer reads it through a device backend (WPD through the Windows Shell, gphoto2 on macOS and Linux) behind one small
interface. These tests drive that interface with a fake camera: the camera shows as a source beside the drives, its DCIM
folders browse, Copy, Move, Add and Copy as DNG bring the files in with the usual options, Move removes from the camera
only what was imported, and a file that fails to arrive is reported without touching the others. The gphoto2 and WPD
backends are checked against recorded output with their processes replaced."""
import io
import json
import zlib
from pathlib import Path

import numpy as np
import pytest

from conftest import gradient

RAW_NAMES = ["IMG_0001.CR3", "IMG_0002.CR2", "DSC_0003.NEF", "DSC04.ARW", "DSCF0005.RAF", "L1000006.DNG", "IMG_0007.JPG", "IMG_0008.HEIC", "MVI_0009.MP4"]


def jpeg_bytes(seed: str) -> bytes:
    from PIL import Image

    px = gradient()
    px[0, 0] = [zlib.crc32(seed.encode()) % 251, 11, 13]
    px[0, 1] = [zlib.crc32(seed.encode()[::-1]) % 251, 17, 19]
    buf = io.BytesIO()
    Image.fromarray(px).save(buf, "JPEG", quality=95)
    return buf.getvalue()


class FakeCamera:
    backend = "fake"

    def __init__(self, files: dict[str, bytes], name: str = "Canon EOS R5", broken: set[str] | None = None):
        from app.services.cameras import short_id

        self.id = short_id("fake", name)
        self.name = name
        self.files = dict(files)
        self.broken = set(broken or ())
        self.deleted: list[str] = []

    def list_dir(self, folder):
        from app.services.cameras import CameraError, Entry

        prefix = folder.strip("/") + "/" if folder.strip("/") else ""
        dirs = sorted({k[len(prefix):].split("/", 1)[0] for k in self.files if k.startswith(prefix) and "/" in k[len(prefix):]})
        here = [Entry(k[len(prefix):], len(v), 1_700_000_000.0) for k, v in sorted(self.files.items()) if k.startswith(prefix) and "/" not in k[len(prefix):]]
        if prefix and not dirs and not here:
            raise CameraError(f"No folder {folder}")
        return dirs, here

    def fetch(self, file, dest):
        from app.services.cameras import CameraError

        if file in self.broken:
            raise CameraError(f"{file} could not be read from the camera")
        target = dest / file.rsplit("/", 1)[-1]
        target.write_bytes(self.files[file])
        return target

    def delete(self, file):
        self.deleted.append(file)
        self.files.pop(file)

    def thumbnail(self, file):
        return jpeg_bytes("thumb" + file)


@pytest.fixture
def camera(client, request):
    from app.services import cameras

    seed = request.node.name
    cam = FakeCamera({
        "DCIM/100CANON/IMG_0001.JPG": jpeg_bytes(seed + "1"),
        "DCIM/100CANON/IMG_0002.JPG": jpeg_bytes(seed + "2"),
        "DCIM/101CANON/IMG_0003.JPG": jpeg_bytes(seed + "3"),
        "DCIM/101CANON/notes.txt": b"not a photo",
        "MISC/settings.dat": b"",
    })
    old = cameras.set_providers([lambda: [cam]])
    yield cam
    cameras.set_providers(old)


def test_a_connected_camera_is_a_source_beside_the_drives(client, camera):
    from app.services import cameras

    roots = client.get("/api/files/roots").json()["roots"]
    mine = [r for r in roots if r["kind"] == "camera"]
    assert mine == [{"name": "Canon EOS R5", "path": cameras.path_for(camera.id, ""), "kind": "camera", "removable": False, "card": True}]


def test_the_camera_browses_like_a_folder(client, camera):
    from app.services import cameras

    top = client.get("/api/files/list", params={"path": cameras.path_for(camera.id, "")}).json()
    assert [d["name"] for d in top["dirs"]] == ["DCIM", "MISC"] and top["parent"] is None
    dcim = client.get("/api/files/list", params={"path": top["dirs"][0]["path"]}).json()
    assert [d["name"] for d in dcim["dirs"]] == ["100CANON", "101CANON"]
    folder = client.get("/api/files/list", params={"path": dcim["dirs"][1]["path"]}).json()
    assert [f["name"] for f in folder["files"]] == ["IMG_0003.JPG"]
    assert [c["name"] for c in folder["crumbs"]] == ["Canon EOS R5", "DCIM", "101CANON"]
    assert folder["parent"] == dcim["path"]


def test_camera_paths_refuse_to_climb_out_of_the_camera(client, camera):
    from app.services import cameras

    with pytest.raises(cameras.CameraError):
        cameras.parse(f"camera://{camera.id}/DCIM/../../etc")
    r = client.get("/api/files/list", params={"path": "camera://nothing-here/DCIM"})
    assert r.status_code == 404


def test_a_scan_of_the_camera_lists_every_supported_kind(client, commands):
    from app.services import cameras

    cam = FakeCamera({f"DCIM/100CANON/{n}": b"x" * (i + 1) for i, n in enumerate(RAW_NAMES)} | {"DCIM/100CANON/IMG_0010.THM": b"t"})
    old = cameras.set_providers([lambda: [cam]])
    try:
        res = commands("library.scan", {"paths": [cameras.path_for(cam.id, "DCIM")], "recursive": True})
    finally:
        cameras.set_providers(old)
    assert sorted(f["name"] for f in res["files"]) == sorted(RAW_NAMES)
    kinds = {f["name"]: f["kind"] for f in res["files"]}
    assert kinds["IMG_0001.CR3"] == "raw" and kinds["IMG_0007.JPG"] == "jpeg" and kinds["MVI_0009.MP4"] == "video"


def test_copy_from_the_camera_imports_and_leaves_the_camera_as_it_was(client, commands, camera, tmp_path):
    from app.services import cameras

    before = dict(camera.files)
    paths = [f["path"] for f in commands("library.scan", {"paths": [cameras.path_for(camera.id, "DCIM")]})["files"]]
    res = commands("library.import", {"paths": paths, "mode": "copy", "destination": str(tmp_path / "lib"), "folderTemplate": "", "wait": True})
    assert res["count"] == 3 and not res["failed"]
    assert sorted(p.name for p in (tmp_path / "lib").iterdir()) == ["IMG_0001.JPG", "IMG_0002.JPG", "IMG_0003.JPG"]
    assert (tmp_path / "lib" / "IMG_0003.JPG").read_bytes() == before["DCIM/101CANON/IMG_0003.JPG"]
    assert camera.files == before and camera.deleted == []
    rows = {commands("photo.get", {"id": i})["fileName"] for i in res["ids"]}
    assert rows == {"IMG_0001.JPG", "IMG_0002.JPG", "IMG_0003.JPG"}


def test_a_second_scan_marks_what_is_already_imported(client, commands, camera, tmp_path):
    from app.services import cameras

    one = cameras.path_for(camera.id, "DCIM/100CANON/IMG_0001.JPG")
    commands("library.import", {"paths": [one], "mode": "copy", "destination": str(tmp_path / "lib"), "folderTemplate": "", "wait": True})
    scan = commands("library.scan", {"paths": [cameras.path_for(camera.id, "DCIM")]})
    assert {f["name"]: f["duplicate"] for f in scan["files"]} == {"IMG_0001.JPG": True, "IMG_0002.JPG": False, "IMG_0003.JPG": False}


def test_move_from_the_camera_deletes_only_what_was_imported(client, commands, camera, tmp_path):
    from app.services import cameras

    first = cameras.path_for(camera.id, "DCIM/100CANON/IMG_0001.JPG")
    commands("library.import", {"paths": [first], "mode": "copy", "destination": str(tmp_path / "a"), "folderTemplate": "", "wait": True})
    camera.broken = {"DCIM/101CANON/IMG_0003.JPG"}
    res = commands("library.import", {"paths": [cameras.path_for(camera.id, "DCIM")], "mode": "move", "destination": str(tmp_path / "b"),
                                      "folderTemplate": "", "wait": True})
    assert res["count"] == 1
    assert camera.deleted == ["DCIM/100CANON/IMG_0002.JPG"]
    assert res["skipped"] == [first]
    assert [f["path"] for f in res["failed"]] == [cameras.path_for(camera.id, "DCIM/101CANON/IMG_0003.JPG")]
    assert "DCIM/100CANON/IMG_0001.JPG" in camera.files and "DCIM/101CANON/IMG_0003.JPG" in camera.files


def test_add_from_a_camera_copies_into_the_library_folder(client, commands, camera, sandbox):
    from app.core import config
    from app.services import cameras

    res = commands("library.import", {"paths": [cameras.path_for(camera.id, "DCIM/101CANON/IMG_0003.JPG")], "mode": "add", "folderTemplate": "", "wait": True})
    assert res["count"] == 1
    d = commands("photo.get", {"id": res["ids"][0]})
    assert Path(d["path"]).parent.resolve() == config.library_dir().resolve()
    assert Path(d["path"]).read_bytes() == camera.files["DCIM/101CANON/IMG_0003.JPG"]


def test_copy_as_dng_from_a_camera_brings_in_non_raw_files_as_they_are(client, commands, camera, tmp_path):
    from app.services import cameras

    res = commands("library.import", {"paths": [cameras.path_for(camera.id, "DCIM/100CANON")], "mode": "dng", "destination": str(tmp_path / "dng"),
                                      "folderTemplate": "", "renameTemplate": "{seq:3}", "wait": True})
    assert res["count"] == 2
    assert sorted(p.name for p in (tmp_path / "dng").iterdir()) == ["001.jpg", "002.jpg"]


def test_copy_as_dng_is_accepted_for_files_on_a_drive(client, commands, tmp_path):
    src = tmp_path / "card" / "IMG_0100.JPG"
    src.parent.mkdir()
    src.write_bytes(jpeg_bytes("drive-dng"))
    res = commands("library.import", {"paths": [str(src)], "mode": "dng", "destination": str(tmp_path / "out"), "folderTemplate": "", "wait": True})
    assert res["count"] == 1 and (tmp_path / "out" / "IMG_0100.JPG").is_file() and src.is_file()


def test_the_staging_folder_is_removed_after_the_import(client, commands, camera, tmp_path):
    from app.core import config
    from app.services import cameras

    commands("library.import", {"paths": [cameras.path_for(camera.id, "DCIM")], "mode": "copy", "destination": str(tmp_path / "lib"), "wait": True})
    staging = config.temp_dir() / "camera"
    assert not staging.exists() or not any(staging.iterdir())


def test_a_camera_thumbnail_is_served(client, camera):
    from app.services import cameras

    r = client.get("/api/files/thumb", params={"path": cameras.path_for(camera.id, "DCIM/100CANON/IMG_0001.JPG"), "long": 64})
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"


def test_a_camera_unplugged_before_the_scan_says_so(client, commands, camera):
    from app.engine.commands import CommandError
    from app.services import cameras

    path = cameras.path_for(camera.id, "DCIM")
    cameras.set_providers([lambda: []])
    with pytest.raises(CommandError) as err:
        commands("library.scan", {"paths": [path]})
    assert "no longer connected" in str(err.value)


GPHOTO_LIST = """There is no file in folder '/'.
There is no file in folder '/store_00020001'.
There is no file in folder '/store_00020001/DCIM'.
There are 3 files in folder '/store_00020001/DCIM/100CANON':
#1     IMG_0001.CR3               rd 45210 KB image/x-canon-cr3 1731840000
#2     IMG_0002.JPG               rd  8120 KB 8192x5464 image/jpeg 1731840010
#3     A very long file name number three.CR3rd 30000 KB image/x-canon-cr3
There is 1 file in folder '/store_00020001/DCIM/101CANON':
#4     MVI_0004.MP4              rd 512000 KB video/mp4 1731840100
There is no file in folder '/store_00020001/MISC'.
"""


class Gphoto2:
    def __init__(self, listing=GPHOTO_LIST, folders=None):
        self.calls: list[list[str]] = []
        self.listing = listing
        self.folders = folders or {}

    def __call__(self, argv, timeout):
        self.calls.append(argv)
        if "--auto-detect" in argv:
            return 0, "Model                          Port\n----------------------------------------------------------\nCanon EOS R5                   usb:001,007\n", ""
        if "--get-file" in argv:
            pattern = Path(argv[argv.index("--filename") + 1])
            folder = argv[argv.index("--folder") + 1]
            number = int(argv[argv.index("--get-file") + 1])
            name = [ln.split()[1] for ln in self.folders.get(folder, "").splitlines() if ln.startswith(f"#{number} ")][0]
            stem, _, ext = name.rpartition(".")
            out = Path(str(pattern).replace("%f", stem).replace("%C", ext).replace("%n", str(number)).replace("%:", name))
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"raw")
            return 0, f"Saving file as {out}\n", ""
        if "--folder" in argv and "--list-files" in argv:
            folder = argv[argv.index("--folder") + 1]
            return 0, f"There are 2 files in folder '{folder}':\n" + self.folders.get(folder, ""), ""
        if "--list-files" in argv:
            return 0, self.listing, ""
        if "--delete-file" in argv:
            return 0, "", ""
        return 1, "", "*** Error: unexpected call"


def test_gphoto2_listings_become_folders_and_files():
    from app.services.cameras import gphoto

    tree = gphoto.parse_listing(GPHOTO_LIST)
    assert set(tree) == {"/", "/store_00020001", "/store_00020001/DCIM", "/store_00020001/DCIM/100CANON", "/store_00020001/DCIM/101CANON", "/store_00020001/MISC"}
    files = tree["/store_00020001/DCIM/100CANON"]
    assert [(n, e.name, e.size) for n, e in files] == [(1, "IMG_0001.CR3", 45210 * 1024), (2, "IMG_0002.JPG", 8120 * 1024),
                                                       (3, "A very long file name number three.CR3", 30000 * 1024)]
    assert files[0][1].mtime == 1731840000.0 and files[2][1].mtime == 0.0 and not files[0][1].exact


def test_gphoto2_file_numbers_count_within_each_folder():
    """gphoto2's recursive --list-files numbers files on across folders (actions.c print_file_action keeps a static
    counter), but --folder F --no-recurse --get-file N takes the Nth file of F (foreach.c get_path_for_id)."""
    from app.services.cameras import gphoto

    tree = gphoto.parse_listing(GPHOTO_LIST)
    assert [(n, e.name) for n, e in tree["/store_00020001/DCIM/101CANON"]] == [(1, "MVI_0004.MP4")]
    fake = Gphoto2()
    cam = gphoto.GphotoCamera("/usr/bin/gphoto2", "Canon EOS R5", "usb:001,007", fake)
    cam.thumbnail("store_00020001/DCIM/101CANON/MVI_0004.MP4")
    call = next(c for c in fake.calls if "--get-thumbnail" in c)
    assert call[call.index("--folder") + 1] == "/store_00020001/DCIM/101CANON" and call[call.index("--get-thumbnail") + 1] == "1"


def test_the_gphoto2_camera_browses_fetches_and_deletes_by_name(monkeypatch, tmp_path):
    from app.services import tether
    from app.services.cameras import gphoto

    folder = "/store_00020001/DCIM/100CANON"
    fake = Gphoto2(folders={folder: "#1     IMG_0002.JPG               rd     1 KB image/jpeg\n#2     IMG_0001.CR3               rd     1 KB image/x-canon-cr3\n"})
    monkeypatch.setattr(tether, "binary", lambda: "/usr/bin/gphoto2")
    monkeypatch.setattr(tether, "digicam", lambda: None)
    cams = gphoto.devices(fake)
    assert [(c.name, c.port) for c in cams] == [("Canon EOS R5", "usb:001,007")]
    cam = cams[0]
    assert cam.list_dir("") == (["store_00020001"], [])
    dirs, files = cam.list_dir("store_00020001/DCIM")
    assert dirs == ["100CANON", "101CANON"] and files == []
    assert [e.name for e in cam.list_dir("store_00020001/DCIM/100CANON")[1]][:2] == ["IMG_0001.CR3", "IMG_0002.JPG"]
    fake.listing = GPHOTO_LIST.replace("#1     IMG_0001.CR3", "#9     IMG_0001.CR3").replace("#2     IMG_0002.JPG", "#1     IMG_0002.JPG").replace("#9     IMG_0001.CR3", "#2     IMG_0001.CR3")
    cam._tree = (0.0, {})
    got = cam.fetch("store_00020001/DCIM/100CANON/IMG_0001.CR3", tmp_path)
    assert got == tmp_path / "IMG_0001.CR3"
    get = next(c for c in fake.calls if "--get-file" in c)
    assert get[:3] == ["/usr/bin/gphoto2", "--port", "usb:001,007"] and get[get.index("--get-file") + 1] == "2"
    cam.delete("store_00020001/DCIM/100CANON/IMG_0002.JPG")
    gone = next(c for c in fake.calls if "--delete-file" in c)
    assert gone[gone.index("--delete-file") + 1] == "1" and "--no-recurse" in gone


def test_a_busy_camera_names_the_program_to_close():
    from app.services.cameras import CameraError, gphoto

    cam = gphoto.GphotoCamera("/usr/bin/gphoto2", "Canon EOS R5", "usb:001,007", lambda argv, t: (1, "", "*** Error (-53: 'Could not claim the USB device') ***"))
    with pytest.raises(CameraError) as err:
        cam.list_dir("")
    assert "Another program is using the camera" in str(err.value)


def test_without_gphoto2_no_camera_is_listed(monkeypatch):
    from app.services import tether
    from app.services.cameras import gphoto

    monkeypatch.setattr(tether, "binary", lambda: None)
    assert gphoto.devices(lambda argv, t: pytest.fail("gphoto2 was started")) == []


class Wpd:
    def __init__(self):
        self.requests: list[dict] = []

    def __call__(self, request, timeout):
        from app.services.cameras import wpd

        self.requests.append(request)
        op = request["op"]
        if op == "devices":
            return wpd.decode_reply(json.dumps([{"name": "Canon EOS R5", "key": "::{20D04FE0}\\\\?\\usb#vid_04a9&pid_32f4#1#{6ac27878}"}]), 0)
        if op == "list":
            if request["path"] == "":
                return wpd.decode_reply(json.dumps({"dirs": "SD", "files": []}), 0)
            return wpd.decode_reply(json.dumps({"dirs": [], "files": [{"name": "IMG_0001.CR3", "size": 46295040, "mtime": 1731840000}]}), 0)
        if op == "get":
            target = Path(request["dest"]) / request["path"].rsplit("/", 1)[-1]
            target.write_bytes(b"raw")
            return wpd.decode_reply(json.dumps({"path": str(target)}), 0)
        if op == "delete":
            return wpd.decode_reply(json.dumps({"deleted": request["path"]}), 0)
        return wpd.decode_reply(json.dumps({"error": "Unknown request"}), 1)


def test_the_wpd_camera_answers_through_its_helper(tmp_path):
    from app.services.cameras import wpd

    fake = Wpd()
    cams = wpd.devices(fake)
    assert [c.name for c in cams] == ["Canon EOS R5"] and cams[0].id.startswith("wpd-")
    cam = cams[0]
    assert cam.list_dir("") == (["SD"], [])
    _, files = cam.list_dir("SD/DCIM/100CANON")
    assert files[0].name == "IMG_0001.CR3" and files[0].size == 46295040 and files[0].exact
    assert cam.fetch("SD/DCIM/100CANON/IMG_0001.CR3", tmp_path) == tmp_path / "IMG_0001.CR3"
    cam.delete("SD/DCIM/100CANON/IMG_0001.CR3")
    assert [r["op"] for r in fake.requests] == ["devices", "list", "list", "get", "delete"]
    assert all(r.get("device") == cams[0].key for r in fake.requests[1:])


def test_a_wpd_helper_error_is_raised_with_its_message():
    from app.services.cameras import CameraError, wpd

    with pytest.raises(CameraError) as err:
        wpd.decode_reply('{"error":"The camera is no longer connected"}', 1)
    assert "no longer connected" in str(err.value)
    with pytest.raises(CameraError):
        wpd.decode_reply("Get-Item : not json", 1)
    assert wpd.decode_reply("[]", 0) == {"items": []}


def test_gvfs_camera_mounts_show_on_linux(monkeypatch, tmp_path):
    from app.services import cameras

    gvfs = tmp_path / "gvfs"
    (gvfs / "mtp:host=Canon_Inc._Canon_Digital_Camera_0123").mkdir(parents=True)
    (gvfs / "smb-share:server=nas").mkdir()
    monkeypatch.setattr(cameras.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    assert cameras.gvfs_mounts() == [{"name": "Canon Inc. Canon Digital Camera 0123", "path": str(gvfs / "mtp:host=Canon_Inc._Canon_Digital_Camera_0123"), "kind": "camera"}]


def test_large_imports_are_staged_in_batches(monkeypatch):
    from app.services.cameras import Entry, transfer

    monkeypatch.setattr(transfer, "BATCH_BYTES", 100)
    items = [(None, f"f{i}", Entry(f"f{i}.jpg", 60, 0.0)) for i in range(5)]
    assert [len(b) for b in transfer._batches(items)] == [1, 1, 1, 1, 1]
    monkeypatch.setattr(transfer, "BATCH_BYTES", 130)
    assert [len(b) for b in transfer._batches(items)] == [2, 2, 1]
