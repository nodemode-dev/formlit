import hashlib
import os

import numpy as np
import pytest

from conftest import gradient, write_jpeg


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stat_of(path):
    s = path.stat()
    return s.st_size, s.st_mtime_ns


class Original:
    def __init__(self, path):
        self.path = path
        self.hash = digest(path)
        self.stat = stat_of(path)

    def assert_untouched(self):
        assert self.path.is_file(), "the original is gone"
        assert digest(self.path) == self.hash
        assert stat_of(self.path) == self.stat


@pytest.fixture
def original(photo):
    return Original(photo["path"])


def test_develop_edits_never_write_the_original(commands, photo, original):
    pid = photo["id"]
    commands("develop.set", {"ids": [pid], "values": {"light.exposure": 1.2, "wb.temp": 8000, "light.contrast": 30}})
    commands("develop.update", {"ids": [pid], "patch": {"treatment": "bw", "curve": {"master": [[0, 0], [0.5, 0.4], [1, 1]]}}})
    commands("develop.auto", {"ids": [pid]})
    commands("develop.reset", {"ids": [pid]})
    commands("edit.undo", {})
    original.assert_untouched()


def test_rendering_previews_and_thumbnails_never_write_the_original(client, commands, photo, original):
    pid = photo["id"]
    commands("develop.set", {"ids": [pid], "values": {"light.exposure": -0.8}})
    commands("library.buildPreviews", {"ids": [pid]})
    for kind in ("thumb", "preview", "full"):
        assert client.get(f"/api/photos/{pid}/{kind}").status_code in (200, 202)
    assert client.post(f"/api/photos/{pid}/render", json={"max": 256}).status_code in (200, 422)
    original.assert_untouched()


@pytest.mark.parametrize("settings", [
    {"file": {"format": "jpeg", "quality": 90}},
    {"file": {"format": "tiff", "depth": 16, "space": "prophoto"}},
    {"file": {"format": "png"}},
    {"file": {"format": "original"}},
    {"file": {"format": "dng"}},
], ids=["jpeg", "tiff", "png", "original", "dng"])
def test_export_never_writes_the_original(commands, photo, original, sandbox, settings, request):
    out = sandbox / "out" / request.node.callspec.id
    commands("develop.set", {"ids": [photo["id"]], "values": {"light.exposure": 0.6}})
    res = commands("export.run", {"ids": [photo["id"]], "settings": {**settings, "destination": {"folder": str(out)}}, "wait": True})
    assert res["paths"] and not res["failed"], res
    assert all(os.path.isfile(p) for p in res["paths"])
    original.assert_untouched()


@pytest.mark.parametrize("existing", ["overwrite", "unique", "skip"])
def test_export_beside_the_original_with_the_same_name_does_not_replace_it(commands, photo, original, existing):
    res = commands("export.run", {"ids": [photo["id"]], "settings": {"file": {"format": "jpeg"}, "destination": {"sameAsOriginal": True, "existing": existing}}, "wait": True})
    assert not res["failed"], res
    for p in res["paths"]:
        assert os.path.realpath(p) != os.path.realpath(photo["path"])
    original.assert_untouched()


def test_exported_original_is_a_byte_copy_of_the_source(commands, photo, original, sandbox):
    out = sandbox / "out" / "bytecopy"
    res = commands("export.run", {"ids": [photo["id"]], "settings": {"file": {"format": "original"}, "destination": {"folder": str(out)}}, "wait": True})
    copy = [p for p in res["paths"] if p.lower().endswith(".jpg")]
    assert copy and digest(__import__("pathlib").Path(copy[0])) == original.hash
    original.assert_untouched()


def test_removing_a_photo_from_the_catalog_keeps_the_file(commands, photo, original):
    commands("photo.remove", {"ids": [photo["id"]]})
    original.assert_untouched()
    left = commands("library.query", {"source": {"kind": "ids", "ids": [photo["id"]]}})
    assert not (left.get("ids") or left.get("photos") or [])


def test_removing_a_folder_from_the_catalog_keeps_its_files(commands, sandbox):
    folder = sandbox / "gone-folder"
    files = [write_jpeg(folder / f"g{i}.jpg", np.flip(gradient(), axis=i)) for i in range(2)]
    res = commands("library.import", {"paths": [str(f) for f in files], "mode": "add", "wait": True})
    assert len(res["ids"]) == 2
    before = {f: digest(f) for f in files}
    row = [f for f in commands("library.tree", {})["folders"] if f["path"] == str(folder.resolve())]
    assert row, "the imported folder is not in the catalog tree"
    commands("folder.remove", {"id": row[0]["id"]})
    for f, h in before.items():
        assert f.is_file() and digest(f) == h


def test_a_virtual_copy_edit_leaves_the_master_file_alone(commands, photo, original):
    copy = commands("photo.virtualCopy", {"ids": [photo["id"]]})
    ids = copy.get("ids") or [copy.get("id")]
    commands("develop.set", {"ids": [int(ids[0])], "values": {"light.exposure": 2.0}})
    commands("photo.remove", {"ids": [int(ids[0])]})
    original.assert_untouched()


def test_an_agent_cannot_delete_files_from_disk(client, photo, original):
    from conftest import set_policy

    set_policy("allowed")
    try:
        for cmd, params in (("photo.delete", {"ids": [photo["id"]]}),):
            reply = client.post("/mcp", json={"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "run_command", "arguments": {"command": cmd, "params": params}}}).json()
            assert reply["result"]["isError"], reply
    finally:
        set_policy("ask")
    original.assert_untouched()
