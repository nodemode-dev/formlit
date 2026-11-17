import os
from pathlib import Path

import numpy as np
import pytest

from conftest import write_png

SHARP = {"detail": {"sharpenAmount": 60, "sharpenRadius": 1.0, "sharpenDetail": 25, "sharpenMasking": 70}}


@pytest.fixture(scope="module")
def edge_photo(client, tmp_path_factory):
    from app.services import decode

    rng = np.random.default_rng(7)
    px = np.full((96, 128, 3), 120, np.uint8)
    px[:, :64] += rng.integers(0, 2, (96, 64, 1), dtype=np.uint8)
    px[:, 64:] = np.where((np.indices((96, 64)).sum(axis=0) // 6 % 2)[..., None] == 1, 220, 30)
    px[..., 0] = np.clip(px[..., 0].astype(int) + 25, 0, 255)
    return decode.load_linear(write_png(tmp_path_factory.mktemp("sharpen") / "edges.png", px))


def rendered(photo, overlay, dev=SHARP):
    from app.develop import render

    img, info = photo
    return render.render(img, info, dev, size=(128, 96), space="srgb", overlay=overlay)


def grey(out):
    return np.allclose(out[..., 0], out[..., 1], atol=1e-4) and np.allclose(out[..., 1], out[..., 2], atol=1e-4)


def test_sharpen_mask_view_is_white_on_edges_and_dark_on_flat_areas(edge_photo):
    out = rendered(edge_photo, {"sharpen": "mask"})
    assert grey(out)
    flat, edges = out[8:88, 8:56, 0].mean(), out[8:88, 72:120, 0].mean()
    assert flat < 0.1 and edges > 0.3, (flat, edges)


def test_sharpen_mask_view_with_no_masking_is_all_white(edge_photo):
    out = rendered(edge_photo, {"sharpen": "mask"}, {"detail": {**SHARP["detail"], "sharpenMasking": 0}})
    assert np.allclose(out, 1.0)


def test_sharpen_amount_view_is_the_sharpened_result_in_greyscale(edge_photo):
    normal = rendered(edge_photo, None)
    out = rendered(edge_photo, {"sharpen": "amount"})
    assert not grey(normal) and grey(out)
    luma = normal @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    assert np.allclose(out[..., 0], luma, atol=2e-3)


@pytest.mark.parametrize("mode", ["radius", "detail"])
def test_sharpen_radius_and_detail_views_are_mid_grey_away_from_edges(edge_photo, mode):
    out = rendered(edge_photo, {"sharpen": mode})
    assert grey(out)
    assert abs(out[8:88, 8:56, 0].mean() - 0.5) < 0.05
    assert out[8:88, 72:120, 0].std() > 0.05


def test_unknown_sharpen_view_leaves_the_render_alone(edge_photo):
    assert np.allclose(rendered(edge_photo, {"sharpen": "nope"}), rendered(edge_photo, None))


def test_render_route_takes_the_sharpen_view(client, photo):
    import io

    from PIL import Image

    r = client.post(f"/api/photos/{photo['id']}/render", json={"long": 96, "settings": SHARP, "overlay": {"sharpen": "amount"}})
    assert r.status_code == 200
    a = np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB")).astype(int)
    assert np.abs(a[..., 0] - a[..., 2]).max() <= 3


def card(model):
    from app.ai import models

    spec = models.MODELS[model]
    return {"model": model, "name": spec["name"], "sizeMB": spec["size"], "license": spec["license"]}


@pytest.mark.parametrize("kind,choices", [("subject", ["subjectHq", "subject"]), ("background", ["subjectHq", "subject"]), ("sky", ["sky"]), ("object", ["objectsHq", "objects"])])
def test_missing_ai_model_answers_with_what_to_install(client, photo, kind, choices):
    from app.ai import models

    assert not any(models.ready(m) for m in choices)
    r = client.post("/api/commands/develop.aiMask", json={"id": photo["id"], "kind": kind})
    assert r.status_code == 409
    body = r.json()
    assert body["missingModel"] == {**card(choices[0]), "choices": [card(m) for m in choices]}
    assert "not installed yet" in body["error"]


def test_other_command_errors_carry_no_model(client):
    r = client.post("/api/commands/develop.aiMask", json={"kind": "nope", "id": 1})
    assert r.status_code == 400
    assert "missingModel" not in r.json()


def set_kind(pid, kind):
    from app.engine import catalog as catalog_mod

    cat = catalog_mod.get()
    with cat.lock:
        cat.db.execute("UPDATE photos SET kind=? WHERE id=?", (kind, pid))


def test_lens_profiles_are_offered_once_for_a_raw_without_the_database(client, commands, photo):
    from app.core import prefs
    from app.services import lensdb

    assert not lensdb.available()
    assert commands("develop.lensProfileInfo", {"id": photo["id"]})["askDownload"] is False
    set_kind(photo["id"], "raw")
    try:
        info = commands("develop.lensProfileInfo", {"id": photo["id"]})
        assert info["askDownload"] is True and info["downloadMB"] == lensdb.DOWNLOAD_MB
        commands("prefs.set", {"values": {"askLensProfiles": False}})
        assert commands("develop.lensProfileInfo", {"id": photo["id"]})["askDownload"] is False
        assert prefs.load()["askLensProfiles"] is False
    finally:
        prefs.update({"askLensProfiles": True})
        set_kind(photo["id"], "jpeg")


def test_lens_prompt_preference_must_be_a_boolean(commands):
    from app.engine.commands import CommandError

    with pytest.raises(CommandError):
        commands("prefs.set", {"values": {"askLensProfiles": "no"}})


@pytest.mark.parametrize("letter,kind,dcim,removable,card", [
    ("E", 2, False, True, False),
    ("E", 2, True, True, True),
    ("F", 3, True, True, True),
    ("D", 3, False, False, False),
    ("C", 3, True, False, False),
    ("G", 4, True, False, False),
    ("H", 5, False, False, False),
])
def test_windows_drive_roots_report_removable_and_card(monkeypatch, letter, kind, dcim, removable, card):
    from app.routers import files

    monkeypatch.delenv("SystemDrive", raising=False)
    monkeypatch.setattr(files, "_has_dcim", lambda p: dcim)
    got = files._drive(letter, lambda root: kind)
    assert got == {"name": f"{letter}:", "path": f"{letter}:\\", "kind": "drive", "removable": removable, "card": card}


def test_windows_system_drive_follows_the_environment(monkeypatch):
    from app.routers import files

    monkeypatch.setenv("SystemDrive", "D:")
    monkeypatch.setattr(files, "_has_dcim", lambda p: True)
    assert files._drive("D", lambda root: 3)["removable"] is False
    assert files._drive("C", lambda root: 3)["card"] is True


def test_drive_type_is_zero_off_windows():
    from app.routers import files

    if os.name == "nt":
        pytest.skip("GetDriveTypeW answers on Windows")
    assert files._drive_type("E:\\") == 0


def test_mounted_volumes_are_removable_and_a_card_has_dcim(tmp_path):
    from app.routers import files

    card = tmp_path / "EOS_DIGITAL"
    (card / "DCIM" / "100CANON").mkdir(parents=True)
    disk = tmp_path / "Backup"
    disk.mkdir()
    assert files._volume(card) == {"name": "EOS_DIGITAL", "path": str(card), "kind": "volume", "removable": True, "card": True}
    assert files._volume(disk)["removable"] is True and files._volume(disk)["card"] is False


@pytest.mark.skipif(os.name == "nt", reason="symlinks to / are a macOS and Linux case")
def test_the_boot_volume_link_is_not_removable(tmp_path):
    from app.routers import files

    link = tmp_path / "Macintosh HD"
    link.symlink_to(Path("/"))
    assert files._volume(link)["removable"] is False


def test_roots_route_answers_with_the_removable_flag(client):
    roots = client.get("/api/files/roots").json()["roots"]
    assert all("removable" in r for r in roots if r["kind"] in ("volume", "drive"))
