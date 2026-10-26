import numpy as np
import pytest
from PIL import Image

from conftest import write_png

TOL = 0.012
GREYS = np.array([32, 64, 128, 192, 224], np.uint8)
COLOURS = np.array([[200, 40, 40], [40, 200, 40], [40, 40, 200], [128, 128, 128], [230, 230, 230]], np.uint8)


def decoded(path):
    from app.services import decode

    return decode.load_linear(path)


def rendered(img, info, dev, w, h):
    from app.develop import render

    return render.render(img, info, dev, size=(w, h), space="srgb")[h // 2]


@pytest.fixture(scope="module")
def grey_strip(client, tmp_path_factory):
    path = write_png(tmp_path_factory.mktemp("math") / "grey.png", np.tile(GREYS[None, :, None], (20, 1, 3)))
    return decoded(path)


@pytest.fixture(scope="module")
def colour_strip(client, tmp_path_factory):
    path = write_png(tmp_path_factory.mktemp("math") / "colour.png", np.tile(COLOURS[None, :, :], (20, 1, 1)))
    return decoded(path)


def grey_out(strip, dev):
    img, info = strip
    return rendered(img, info, dev, 5, 20)


def colour_out(strip, dev):
    img, info = strip
    return rendered(img, info, dev, 5, 20) * 255.0


def expected_exposure(stops):
    from app.develop import colour

    lin = colour.srgb_decode(GREYS.astype(np.float32) / 255.0) * (2.0 ** stops)
    return colour.srgb_encode(lin)


def test_default_settings_leave_the_image_as_decoded(grey_strip):
    out = grey_out(grey_strip, {})
    assert np.allclose(out, np.repeat((GREYS / 255.0)[:, None], 3, axis=1), atol=TOL)


@pytest.mark.parametrize("stops", [-1.0, -0.5, 0.5, 1.0])
def test_exposure_scales_linear_light_by_two_to_the_stops(grey_strip, stops):
    out = grey_out(grey_strip, {"light": {"exposure": stops}})
    want = expected_exposure(stops)
    unclipped = want < 0.97
    assert unclipped.sum() >= 3
    assert np.allclose(out[unclipped, 1], want[unclipped], atol=TOL)


def test_exposure_keeps_neutral_greys_neutral(grey_strip):
    out = grey_out(grey_strip, {"light": {"exposure": 0.7}})
    assert np.allclose(out[:, 0], out[:, 1], atol=0.004)
    assert np.allclose(out[:, 2], out[:, 1], atol=0.004)


def test_exposure_clips_to_the_display_range(grey_strip):
    out = grey_out(grey_strip, {"light": {"exposure": 5.0}})
    assert out.max() <= 1.0 and out.min() >= 0.0
    assert out[-1].min() == pytest.approx(1.0, abs=1e-3)


def test_as_shot_white_balance_changes_nothing(colour_strip):
    base = colour_out(colour_strip, {})
    shot = colour_out(colour_strip, {"wb": {"mode": "asShot"}})
    assert np.allclose(base, shot, atol=1.0)


def test_warmer_temperature_raises_red_and_lowers_blue(colour_strip):
    base = colour_out(colour_strip, {})[3:]
    warm = colour_out(colour_strip, {"wb": {"mode": "custom", "temp": 9000, "tint": 0}})[3:]
    assert (warm[:, 0] > base[:, 0] + 3).all()
    assert (warm[:, 2] < base[:, 2] - 3).all()


def test_cooler_temperature_raises_blue_and_lowers_red(colour_strip):
    base = colour_out(colour_strip, {})[3:]
    cool = colour_out(colour_strip, {"wb": {"mode": "custom", "temp": 4000, "tint": 0}})[3:]
    assert (cool[:, 2] > base[:, 2] + 3).all()
    assert (cool[:, 0] < base[:, 0] - 3).all()


def test_positive_tint_pulls_green_down_on_a_grey(colour_strip):
    base = colour_out(colour_strip, {})[3]
    tinted = colour_out(colour_strip, {"wb": {"mode": "custom", "temp": 6500, "tint": 50}})[3]
    assert tinted[1] < base[1] - 3
    assert tinted[0] > base[0] + 3


def test_white_balance_keeps_a_grey_close_to_its_brightness(colour_strip):
    base = colour_out(colour_strip, {})[3]
    warm = colour_out(colour_strip, {"wb": {"mode": "custom", "temp": 9000, "tint": 0}})[3]
    assert abs(float(np.mean(warm)) - float(np.mean(base))) < 6


def test_master_curve_maps_the_midpoint_where_the_point_says(grey_strip):
    out = grey_out(grey_strip, {"curve": {"master": [[0, 0], [0.5, 0.25], [1, 1]]}})
    assert out[2, 1] == pytest.approx(0.25, abs=TOL)
    assert out[0, 1] < GREYS[0] / 255.0
    assert out[4, 1] < GREYS[4] / 255.0


def test_master_curve_endpoints_are_held(grey_strip):
    out = grey_out(grey_strip, {"curve": {"master": [[0, 0.2], [1, 0.8]]}})
    assert out.min() >= 0.2 - TOL
    assert out.max() <= 0.8 + TOL


def test_an_identity_curve_changes_nothing(grey_strip):
    base = grey_out(grey_strip, {})
    flat = grey_out(grey_strip, {"curve": {"master": [[0, 0], [1, 1]]}})
    assert np.allclose(base, flat, atol=TOL)


def test_black_and_white_removes_all_colour_and_keeps_greys(colour_strip):
    out = colour_out(colour_strip, {"treatment": "bw"})
    assert np.abs(out[:, 0] - out[:, 1]).max() < 1.5
    assert np.abs(out[:, 2] - out[:, 1]).max() < 1.5
    assert np.allclose(out[3:, 1], COLOURS[3:, 1], atol=1.5)


def test_black_and_white_orders_patches_by_their_brightness(colour_strip):
    out = colour_out(colour_strip, {"treatment": "bw"})[:, 1]
    assert out[1] > out[0] > out[2]


def test_black_and_white_mix_moves_only_its_own_colour(colour_strip):
    base = colour_out(colour_strip, {"treatment": "bw"})[:, 1]
    up = colour_out(colour_strip, {"treatment": "bw", "bw": {"red": 100}})[:, 1]
    down = colour_out(colour_strip, {"treatment": "bw", "bw": {"red": -100}})[:, 1]
    assert up[0] > base[0] + 20
    assert down[0] < base[0] - 20
    assert np.allclose(up[1:], base[1:], atol=1.5)
    assert np.allclose(down[1:], base[1:], atol=1.5)


def test_contrast_darkens_darks_and_brightens_lights_around_the_middle(grey_strip):
    base = grey_out(grey_strip, {})[:, 1]
    hard = grey_out(grey_strip, {"light": {"contrast": 60}})[:, 1]
    assert hard[0] < base[0] and hard[1] < base[1]
    assert hard[3] > base[3] and hard[4] > base[4]


@pytest.mark.parametrize("space", ["srgb", "adobergb", "prophoto"])
def test_numba_kernel_and_numpy_reference_agree(client, space):
    from app.develop import finish, kernel, planes as planes_mod

    lin, info, dev, evaluated, h, w = kernel._probe()
    built: dict = {}
    planes_mod.build(built, lin, dev, float(w))
    fast = kernel.finish_compiled(lin, built, dev, None, info, w, h, float(w), evaluated, space)
    ref = finish.finish(lin, built, dev, None, info, w, h, float(w), evaluated, space)
    assert np.isfinite(fast).all()
    assert float(np.abs(fast - ref).max()) < 2e-4


def test_the_kernel_warms_up_on_this_machine(client):
    from app.develop import kernel

    kernel.warm()
    assert kernel.best_finish() is kernel.finish_compiled
