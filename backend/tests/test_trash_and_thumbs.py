"""0.51.3. Delete from Disk without send2trash moves each file into a Trash folder in the home folder; across drives
shutil.move copied the file and then failed to remove the original, so every retry left one more copy in the Trash.
And a cached thumbnail or preview removed between the engine's listing and its read made /thumb answer 500 and
/preview 404 while an image was there to serve."""
import errno
import os
import sys
from pathlib import Path

import pytest


@pytest.fixture
def no_send2trash(monkeypatch, tmp_path):
    from app.engine import cmd_library

    monkeypatch.setitem(sys.modules, "send2trash", None)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(cmd_library.Path, "home", lambda: home)
    return cmd_library, home / ".Trash" if sys.platform == "darwin" else home / ".local/share/Trash/files"


def across_drives(monkeypatch, locked: Path | None):
    real_unlink = os.unlink

    def rename(src, dst, *a, **k):
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    def unlink(path, *a, **k):
        if locked is not None and Path(path) == locked:
            raise PermissionError(errno.EACCES, "Permission denied", str(path))
        return real_unlink(path, *a, **k)

    monkeypatch.setattr(os, "rename", rename)
    monkeypatch.setattr(os, "unlink", unlink)


def test_a_failed_move_to_the_trash_leaves_no_copy_behind(no_send2trash, monkeypatch, tmp_path):
    cmd_library, trash = no_send2trash
    photo = tmp_path / "card" / "IMG_0001.jpg"
    photo.parent.mkdir()
    photo.write_bytes(b"original")
    across_drives(monkeypatch, photo)
    for _ in range(2):
        with pytest.raises(OSError):
            cmd_library._trash(photo)
    assert photo.read_bytes() == b"original"
    assert not trash.exists() or not any(trash.iterdir()), sorted(p.name for p in trash.iterdir())


def test_a_move_to_the_trash_across_drives_still_moves_the_file(no_send2trash, monkeypatch, tmp_path):
    cmd_library, trash = no_send2trash
    photo = tmp_path / "card" / "IMG_0002.jpg"
    photo.parent.mkdir()
    photo.write_bytes(b"original")
    across_drives(monkeypatch, None)
    cmd_library._trash(photo)
    assert not photo.exists()
    assert [p.read_bytes() for p in trash.iterdir()] == [b"original"]


def test_a_move_to_the_trash_on_one_drive_renames_the_file(no_send2trash, tmp_path):
    cmd_library, trash = no_send2trash
    photo = tmp_path / "IMG_0003.jpg"
    photo.write_bytes(b"original")
    cmd_library._trash(photo)
    assert not photo.exists()
    assert (trash / "IMG_0003.jpg").read_bytes() == b"original"


class VanishingCache:
    def __init__(self, real: Path, gone: Path):
        self.real = real
        self.gone = gone

    def glob(self, pattern):
        return [self.gone, *self.real.glob(pattern)]

    def __truediv__(self, other):
        return self.real / other

    def __getattr__(self, name):
        return getattr(self.real, name)


@pytest.fixture
def vanishing(monkeypatch, tmp_path):
    from app.services import previews

    real = previews.cache_dir
    monkeypatch.setattr(previews, "request", lambda *a, **k: None)
    monkeypatch.setattr(previews, "thumb_path", lambda pid, rev, size: tmp_path / f"{pid}-{rev}-{size}-current.jpg")

    def cache_dir(pid):
        return VanishingCache(real(pid), tmp_path / f"{pid}-0-gone.jpg")

    monkeypatch.setattr(previews, "cache_dir", cache_dir)


@pytest.mark.parametrize("route", ["thumb", "preview"])
def test_a_cached_image_removed_before_its_read_does_not_fail_the_request(client, photo, vanishing, route):
    r = client.get(f"/api/photos/{photo['id']}/{route}")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "image/jpeg"
