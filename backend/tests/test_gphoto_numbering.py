"""gphoto2 addresses files by number, so a wrong number copies or deletes another photo. Numbers come only from what
gphoto2 printed: a single-folder listing is used as printed, a recursive listing is rebased by its folder's first printed
number, a folder with a line that does not parse is refused, and every --get-file and --delete-file is checked against a
fresh listing of its folder first."""
import pytest

FOLDER = "/store_00020001/DCIM/100CANON"
FILE = "store_00020001/DCIM/100CANON/{}"


def row(n, name, kb=1):
    return f"#{n}     {name:<27}rd {kb:>5} KB image/x-canon-cr3\n"


def header(count, folder=FOLDER):
    return f"There {'is' if count == 1 else 'are'} {count} file{'' if count == 1 else 's'} in folder '{folder}':\n"


class Camera:
    def __init__(self, *listings):
        self.listings = list(listings)
        self.calls: list[list[str]] = []

    def __call__(self, argv, timeout):
        from pathlib import Path

        self.calls.append(argv)
        if "--list-files" in argv:
            text = self.listings[0] if len(self.listings) == 1 else self.listings.pop(0)
            return 0, text, ""
        if "--get-file" in argv:
            out = Path(argv[argv.index("--filename") + 1])
            out.write_bytes(b"x" * 1024)
            return 0, f"Saving file as {out}\n", ""
        if "--delete-file" in argv:
            return 0, "", ""
        return 1, "", "*** Error: unexpected call"


def camera(runner):
    from app.services.cameras import gphoto

    return gphoto.GphotoCamera("/usr/bin/gphoto2", "Canon EOS R5", "usb:001,007", runner)


def numbered(runner, flag):
    return [c[c.index(flag) + 1] for c in runner.calls if flag in c]


def test_a_malformed_line_refuses_copy_and_delete_in_that_folder(tmp_path):
    from app.services.cameras import CameraError

    text = header(3) + row(1, "IMG_0001.CR3") + "#2     ??? garbled line\n" + row(3, "IMG_0003.CR3")
    runner = Camera(text)
    cam = camera(runner)
    for call in (lambda: cam.fetch(FILE.format("IMG_0003.CR3"), tmp_path), lambda: cam.delete(FILE.format("IMG_0003.CR3"))):
        with pytest.raises(CameraError, match="could not be read in full"):
            call()
    assert numbered(runner, "--get-file") == [] and numbered(runner, "--delete-file") == []
    assert cam.thumbnail(FILE.format("IMG_0003.CR3")) is None


def test_a_listing_with_fewer_rows_than_its_header_is_refused(tmp_path):
    from app.services.cameras import CameraError

    runner = Camera(header(3) + row(1, "IMG_0001.CR3") + row(3, "IMG_0003.CR3"))
    with pytest.raises(CameraError, match="could not be read in full"):
        camera(runner).delete(FILE.format("IMG_0003.CR3"))
    assert numbered(runner, "--delete-file") == []


def test_single_folder_numbers_are_used_as_printed_even_from_5_with_gaps(tmp_path):
    runner = Camera(header(2) + row(5, "IMG_0005.CR3") + row(9, "IMG_0009.CR3"))
    cam = camera(runner)
    cam.fetch(FILE.format("IMG_0009.CR3"), tmp_path)
    cam.delete(FILE.format("IMG_0005.CR3"))
    assert numbered(runner, "--get-file") == ["9"] and numbered(runner, "--delete-file") == ["5"]


def test_a_recursive_listing_is_rebased_per_folder_by_its_first_printed_number():
    from app.services.cameras import gphoto

    text = (header(2) + row(1, "A.CR3") + row(2, "B.CR3")
            + header(3, "/store_00020001/DCIM/101CANON") + row(3, "C.CR3") + row(4, "D.CR3") + row(6, "F.CR3"))
    tree = gphoto.parse_listing(text)
    assert [(n, e.name) for n, e in tree["/store_00020001/DCIM/101CANON"]] == [(1, "C.CR3"), (2, "D.CR3"), (4, "F.CR3")]
    assert not tree.untrusted
    out_of_order = gphoto.parse_listing(header(2) + row(2, "A.CR3") + row(1, "B.CR3"))
    assert FOLDER in out_of_order.untrusted


def test_delete_refuses_when_the_file_at_that_number_changed(tmp_path):
    from app.services.cameras import CameraError

    first = header(2) + row(1, "IMG_0001.CR3") + row(2, "IMG_0002.CR3")
    then = header(2) + row(1, "IMG_0002.CR3") + row(2, "IMG_0003.CR3")
    runner = Camera(first, then)
    with pytest.raises(CameraError, match="no longer file 1"):
        camera(runner).delete(FILE.format("IMG_0001.CR3"))
    assert numbered(runner, "--delete-file") == []


def test_delete_refuses_a_file_whose_size_is_not_the_imported_one():
    from app.services.cameras import CameraError, Entry

    runner = Camera(header(1) + row(1, "IMG_0001.CR3", kb=900))
    with pytest.raises(CameraError, match="not the file that was imported"):
        camera(runner).delete(FILE.format("IMG_0001.CR3"), Entry("IMG_0001.CR3", 45_000 * 1024, 0.0, exact=False))
    assert numbered(runner, "--delete-file") == []


def test_a_copy_whose_number_changed_during_the_download_is_dropped(tmp_path):
    from app.services.cameras import CameraError

    same = header(1) + row(1, "IMG_0001.CR3")
    runner = Camera(same, same, header(1) + row(1, "IMG_0099.CR3"))
    with pytest.raises(CameraError, match="no longer file 1"):
        camera(runner).fetch(FILE.format("IMG_0001.CR3"), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_the_happy_path_copies_and_deletes_by_the_checked_number(tmp_path):
    runner = Camera(header(2) + row(1, "IMG_0001.CR3") + row(2, "IMG_0002.CR3"))
    cam = camera(runner)
    got = cam.fetch(FILE.format("IMG_0002.CR3"), tmp_path)
    assert got.name == "IMG_0002.CR3"
    cam.delete(FILE.format("IMG_0002.CR3"))
    assert numbered(runner, "--get-file") == ["2"] and numbered(runner, "--delete-file") == ["2"]
    lists = [c for c in runner.calls if "--list-files" in c]
    assert all("--no-recurse" in c and FOLDER in c for c in lists) and len(lists) == 5
