from pathlib import Path

import numpy as np
import pytest
from PIL import Image

COPYRIGHT = "2026 Test Studio"
CREATOR = "Pat Example"
KEYWORD = "harbourfront"


@pytest.fixture
def described(commands, photo):
    pid = photo["id"]
    commands("photo.setMeta", {"ids": [pid], "fields": {"copyright": COPYRIGHT, "creator": CREATOR}})
    commands("photo.addKeywords", {"ids": [pid], "keywords": [KEYWORD]})
    return photo


def export(commands, pid, sandbox, name, settings):
    out = sandbox / "out" / name
    res = commands("export.run", {"ids": [pid], "settings": {**settings, "destination": {"folder": str(out)}}, "wait": True})
    assert res["paths"] and not res["failed"], res
    return Path(res["paths"][0])


def profile(space):
    from app.develop.output import icc_profile

    return icc_profile(space)


def test_jpeg_export_embeds_the_profile_and_the_metadata(commands, described, sandbox):
    path = export(commands, described["id"], sandbox, "jpeg-meta", {"file": {"format": "jpeg", "quality": 90, "space": "srgb"}, "metadata": {"include": "all"}})
    assert path.suffix == ".jpg"
    with Image.open(path) as im:
        assert im.format == "JPEG"
        assert im.info["icc_profile"] == profile("srgb")
        exif = im.getexif()
        assert exif[0x8298] == COPYRIGHT
        assert exif[0x013B] == CREATOR
        xmp = im.info.get("xmp") or im.info.get("XML:com.adobe.xmp") or b""
    assert KEYWORD.encode() in bytes(xmp)
    assert COPYRIGHT.encode() in bytes(xmp)


@pytest.mark.parametrize("space", ["srgb", "adobergb", "p3"])
def test_jpeg_export_embeds_the_profile_of_the_chosen_space(commands, described, sandbox, space):
    path = export(commands, described["id"], sandbox, f"jpeg-{space}", {"file": {"format": "jpeg", "space": space}})
    with Image.open(path) as im:
        assert im.info["icc_profile"] == profile(space)


def test_tiff_export_is_16_bit_with_profile_and_metadata(commands, described, sandbox):
    import tifffile

    path = export(commands, described["id"], sandbox, "tiff-meta", {"file": {"format": "tiff", "depth": 16, "compression": "zip", "space": "prophoto"}, "size": {"ppi": 300}, "metadata": {"include": "all"}})
    assert path.suffix == ".tif"
    with tifffile.TiffFile(path) as tf:
        page = tf.pages[0]
        assert page.dtype == np.uint16
        assert page.shape[-1] == 3
        tags = {t.code: t.value for t in page.tags.values()}
        assert bytes(tags[34675]) == profile("prophoto")
        assert tags[33432] == COPYRIGHT
        assert tags[315] == CREATOR
        assert KEYWORD.encode() in bytes(tags[700])
        num, den = page.tags["XResolution"].value
        assert num / den == 300.0


def test_tiff_8_bit_export_keeps_its_profile(commands, described, sandbox):
    import tifffile

    path = export(commands, described["id"], sandbox, "tiff-8", {"file": {"format": "tiff", "depth": 8, "space": "adobergb"}})
    with tifffile.TiffFile(path) as tf:
        assert tf.pages[0].dtype == np.uint8
        assert bytes(tf.pages[0].tags[34675].value) == profile("adobergb")


def test_png_export_embeds_the_profile(commands, described, sandbox):
    path = export(commands, described["id"], sandbox, "png-icc", {"file": {"format": "png", "space": "srgb"}})
    with Image.open(path) as im:
        assert im.format == "PNG"
        assert im.info["icc_profile"] == profile("srgb")


def test_metadata_none_writes_no_copyright_or_creator(commands, described, sandbox):
    path = export(commands, described["id"], sandbox, "jpeg-none", {"file": {"format": "jpeg"}, "metadata": {"include": "none"}})
    with Image.open(path) as im:
        exif = im.getexif()
        xmp = bytes(im.info.get("xmp") or b"")
        assert 0x8298 not in exif and 0x013B not in exif
        assert im.info["icc_profile"] == profile("srgb")
    assert COPYRIGHT.encode() not in xmp and KEYWORD.encode() not in xmp


def test_copyright_only_keeps_the_copyright_but_not_the_keywords(commands, described, sandbox):
    path = export(commands, described["id"], sandbox, "jpeg-copyright", {"file": {"format": "jpeg"}, "metadata": {"include": "copyright"}})
    with Image.open(path) as im:
        assert im.getexif()[0x8298] == COPYRIGHT
        xmp = bytes(im.info.get("xmp") or b"")
    assert KEYWORD.encode() not in xmp


def test_exported_pixels_carry_the_develop_settings(commands, photo, sandbox):
    base = np.asarray(Image.open(export(commands, photo["id"], sandbox, "px-base", {"file": {"format": "jpeg", "quality": 100}})).convert("RGB"), np.float32)
    commands("develop.set", {"ids": [photo["id"]], "values": {"light.exposure": 1.0}})
    bright = np.asarray(Image.open(export(commands, photo["id"], sandbox, "px-bright", {"file": {"format": "jpeg", "quality": 100}})).convert("RGB"), np.float32)
    from app.develop import colour

    mid = (slice(20, 40), slice(30, 60))
    want = colour.srgb_encode(colour.srgb_decode(base[mid] / 255.0) * 2.0) * 255.0
    ok = want < 240
    assert ok.mean() > 0.5
    assert np.abs(bright[mid] - want)[ok].mean() < 4.0


def test_resize_to_the_long_edge(commands, photo, sandbox):
    path = export(commands, photo["id"], sandbox, "resize", {"file": {"format": "jpeg"}, "size": {"resize": True, "mode": "long", "value": 48}})
    with Image.open(path) as im:
        assert max(im.size) == 48
        assert im.size[0] / im.size[1] == pytest.approx(96 / 64, abs=0.05)
