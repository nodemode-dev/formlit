"""DNG camera profiles (.dcp). A synthetic dual-illuminant profile written to the DNG 1.6 tag layout (both byte orders)
checks the reader and each pipeline stage against values worked out by hand: illuminant weighting in inverse colour
temperature, forward and colour matrices, the HueSatMap and LookTable lookups (numba kernel and numpy reference), the
sRGB value encoding and the tone curve. A real profile, RawTherapee's public-domain Canon EOS R5 DCP, checks that a
profile made by another tool imports, is offered for its camera only, and keeps greys neutral."""
import struct
from pathlib import Path

import numpy as np
import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REAL_R5 = FIXTURES / "dcp" / "Canon EOS R5.dcp"

ASCII, BYTE, SHORT, LONG, SRATIONAL, FLOAT = 2, 1, 3, 4, 10, 11
CAMERA = "Formlit Test Camera"
FM_A = [[0.70, 0.15, 0.1142], [0.27, 0.70, 0.03], [0.05, 0.10, 0.6749]]
FM_D65 = [[0.60, 0.25, 0.1142], [0.25, 0.72, 0.03], [0.02, 0.10, 0.7049]]
CM_A = [[1.10, -0.30, -0.05], [-0.45, 1.35, 0.10], [-0.05, 0.20, 0.60]]
CM_D65 = [[0.90, -0.25, -0.08], [-0.40, 1.25, 0.15], [-0.08, 0.15, 0.75]]


def _flat(m):
    return [float(x) for row in m for x in row]


def _table(hd, sd, vd, hue, sat, val):
    return [x for _ in range(hd * sd * vd) for x in (hue, sat, val)]


def write_dcp(path: Path, entries: dict, big: bool = False) -> Path:
    end = ">" if big else "<"
    head = (b"MMCR" if big else b"IIRC") + struct.pack(end + "I", 8)
    tags = sorted(entries.items())
    ifd_size = 2 + 12 * len(tags) + 4
    data = b""
    rows = b""
    for tag, (typ, values) in tags:
        if typ in (ASCII, BYTE) and isinstance(values, str):
            raw = values.encode("utf-8") + b"\x00"
            count = len(raw)
        elif typ == SRATIONAL:
            raw = b"".join(struct.pack(end + "ii", int(round(v * 10000)), 10000) for v in values)
            count = len(values)
        else:
            fmt = {SHORT: "H", LONG: "I", FLOAT: "f", BYTE: "B"}[typ]
            raw = struct.pack(end + fmt * len(values), *values)
            count = len(values)
        if len(raw) <= 4:
            rows += struct.pack(end + "HHI", tag, typ, count) + raw.ljust(4, b"\x00")
        else:
            rows += struct.pack(end + "HHII", tag, typ, count, 8 + ifd_size + len(data))
            data += raw + (b"\x00" if len(raw) % 2 else b"")
    path.write_bytes(head + struct.pack(end + "H", len(tags)) + rows + struct.pack(end + "I", 0) + data)
    return path


def synthetic(path: Path, big: bool = False, name_type: int = ASCII, camera: str = CAMERA) -> Path:
    hsm_dims, look_dims = (6, 3, 1), (6, 3, 2)
    return write_dcp(path, {
        50708: (ASCII, camera),
        50936: (name_type, "Formlit Synthetic Dual"),
        50942: (ASCII, "Made for formlit's tests"),
        50778: (SHORT, [17]),
        50779: (SHORT, [21]),
        50721: (SRATIONAL, _flat(CM_A)),
        50722: (SRATIONAL, _flat(CM_D65)),
        50964: (SRATIONAL, _flat(FM_A)),
        50965: (SRATIONAL, _flat(FM_D65)),
        50937: (LONG, list(hsm_dims)),
        50938: (FLOAT, _table(*hsm_dims, 0.0, 1.0, 1.0)),
        50939: (FLOAT, _table(*hsm_dims, 60.0, 1.0, 1.0)),
        50981: (LONG, list(look_dims)),
        50982: (FLOAT, _table(*look_dims, 0.0, 0.5, 1.0)),
        50940: (FLOAT, [0.0, 0.0, 0.25, 0.40, 1.0, 1.0]),
        51107: (LONG, [0]),
        51108: (LONG, [1]),
        51109: (SRATIONAL, [0.5]),
    }, big)


@pytest.mark.parametrize("big", [False, True], ids=["little-endian", "big-endian"])
def test_a_synthetic_dual_illuminant_profile_reads_back_every_tag(tmp_path, big):
    from app.develop import dcp

    prof = dcp.read(synthetic(tmp_path / "s.dcp", big))
    assert prof["camera"] == CAMERA and prof["name"] == "Formlit Synthetic Dual"
    assert prof["illum1"] == (17,) and prof["illum2"] == (21,)
    assert np.allclose(prof["fm1"], _flat(FM_A), atol=1e-4) and np.allclose(prof["fm2"], _flat(FM_D65), atol=1e-4)
    assert np.allclose(prof["cm1"], _flat(CM_A), atol=1e-4) and np.allclose(prof["cm2"], _flat(CM_D65), atol=1e-4)
    assert prof["hsmDims"] == (6, 3, 1) and len(prof["hsm1"]) == len(prof["hsm2"]) == 6 * 3 * 3
    assert prof["lookDims"] == (6, 3, 2) and len(prof["look"]) == 6 * 3 * 2 * 3
    assert prof["lookEncoding"] == (1,) and prof["hsmEncoding"] == (0,)
    assert prof["baselineExposureOffset"] == pytest.approx((0.5,))
    assert prof["toneCurve"] == pytest.approx((0.0, 0.0, 0.25, 0.40, 1.0, 1.0))


def test_a_profile_name_stored_as_bytes_reads_as_text(tmp_path):
    from app.develop import dcp

    prof = dcp.read(synthetic(tmp_path / "b.dcp", name_type=BYTE))
    assert prof["name"] == "Formlit Synthetic Dual"


def test_illuminants_are_weighted_in_inverse_colour_temperature(tmp_path):
    from app.develop import dcp

    prof = dcp.read(synthetic(tmp_path / "w.dcp"))
    assert dcp.weight1(prof, 2000.0) == 1.0 and dcp.weight1(prof, 2850.0) == 1.0
    assert dcp.weight1(prof, 6500.0) == 0.0 and dcp.weight1(prof, 9000.0) == 0.0
    mid = 2.0 / (1 / 2850.0 + 1 / 6500.0)
    assert dcp.weight1(prof, mid) == pytest.approx(0.5, abs=1e-9)


def test_the_forward_matrix_is_blended_by_white_balance_and_maps_to_prophoto(tmp_path):
    from app.develop import colour, dcp

    prof = dcp.read(synthetic(tmp_path / "f.dcp"))
    info = {"camera": CAMERA, "camToRec2020": np.eye(3).tolist()}
    mid = 2.0 / (1 / 2850.0 + 1 / 6500.0)
    got = dcp.to_prophoto(prof, info, (mid, 0.0))
    fm = 0.5 * np.asarray(FM_A) + 0.5 * np.asarray(FM_D65)
    assert np.allclose(got, colour.from_xyz("prophoto") @ fm, atol=1e-4)
    white = got @ np.ones(3)
    assert np.allclose(white, white[1], atol=2e-3), white


def test_without_forward_matrices_the_colour_matrix_keeps_white_neutral(tmp_path):
    from app.develop import dcp

    prof = {k: v for k, v in dcp.read(synthetic(tmp_path / "c.dcp")).items() if k not in ("fm1", "fm2")}
    info = {"camera": CAMERA, "camToRec2020": np.eye(3).tolist()}
    for temp in (3000.0, 5000.0, 6500.0):
        white = dcp.to_prophoto(prof, info, (temp, 0.0)) @ np.ones(3)
        assert np.allclose(white / white[1], 1.0, atol=5e-3), (temp, white)


def test_a_profile_for_another_camera_keeps_the_built_in_matrix(tmp_path):
    from app.develop import dcp

    prof = dcp.read(synthetic(tmp_path / "o.dcp"))
    info = {"camera": "Other Maker X1", "camToRec2020": np.eye(3).tolist()}
    assert np.allclose(dcp.to_prophoto(prof, info, (5000.0, 0.0)), dcp._pp_matrix())


@pytest.mark.parametrize("srgb", [False, True])
def test_hue_shift_tables_rotate_hue_and_the_kernel_matches_the_reference(srgb):
    from app.develop import dcp

    dims = (6, 3, 2)
    table = _table(*dims, 60.0, 1.0, 1.0)
    rgb = np.array([[[0.8, 0.1, 0.1], [0.1, 0.6, 0.1], [0.3, 0.3, 0.3]]], np.float64)
    ref = dcp._apply_table(rgb, dims, table, srgb)
    fast = dcp.lookup(rgb, dims, table, srgb)
    assert np.allclose(ref, fast, atol=1e-6)
    h, s, v = dcp._rgb_to_hsv(ref)
    h0, s0, v0 = dcp._rgb_to_hsv(rgb)
    assert np.allclose(h[0, :2], (h0[0, :2] + 1.0) % 6.0, atol=1e-6)
    assert np.allclose(s, s0, atol=1e-6) and np.allclose(v, v0, atol=1e-6)
    assert np.allclose(ref[0, 2], rgb[0, 2], atol=1e-9)


def test_value_and_saturation_scales_follow_the_table():
    from app.develop import dcp

    dims = (6, 3, 1)
    rgb = np.array([[[0.8, 0.2, 0.4]]], np.float64)
    out = dcp.lookup(rgb, dims, _table(*dims, 0.0, 0.5, 0.5), False)
    _, s, v = dcp._rgb_to_hsv(out)
    _, s0, v0 = dcp._rgb_to_hsv(rgb)
    assert s[0, 0] == pytest.approx(s0[0, 0] * 0.5, abs=1e-6) and v[0, 0] == pytest.approx(v0[0, 0] * 0.5, abs=1e-6)
    enc = dcp.lookup(rgb, dims, _table(*dims, 0.0, 1.0, 0.5), True)
    want = dcp._dec(dcp._enc(np.array(0.8)) * 0.5)
    assert dcp._rgb_to_hsv(enc)[2][0, 0] == pytest.approx(float(want), abs=1e-6)


def test_dual_hue_sat_maps_blend_with_white_balance(tmp_path):
    from app.develop import dcp

    prof = dcp.read(synthetic(tmp_path / "h.dcp"))
    info = {"camera": "Other Maker X1"}
    red = np.array([[[0.5, 0.05, 0.05]]], np.float32)
    h_of = lambda out: dcp._rgb_to_hsv(np.asarray(out, np.float64) @ dcp._pp_matrix().T)[0][0, 0]
    base = h_of(red)
    warm = h_of(dcp.apply_camera(red, prof, info, (2850.0, 0.0)))
    cool = h_of(dcp.apply_camera(red, prof, info, (6500.0, 0.0)))
    mid = h_of(dcp.apply_camera(red, prof, info, (2.0 / (1 / 2850.0 + 1 / 6500.0), 0.0)))
    assert warm == pytest.approx(base, abs=1e-4)
    assert cool == pytest.approx((base + 1.0) % 6.0, abs=1e-4)
    assert mid == pytest.approx((base + 0.5) % 6.0, abs=1e-4)


def test_the_look_table_and_baseline_offset_apply(tmp_path):
    from app.develop import dcp

    prof = dcp.read(synthetic(tmp_path / "l.dcp"))
    red = np.array([[[0.5, 0.05, 0.05]]], np.float32)
    pp = lambda x: np.asarray(x, np.float64) @ dcp._pp_matrix().T
    looked = dcp.apply_look(red, prof, 0.0)
    assert dcp._rgb_to_hsv(pp(looked))[1][0, 0] == pytest.approx(dcp._rgb_to_hsv(pp(red))[1][0, 0] * 0.5, abs=1e-4)
    grey = np.full((1, 1, 3), 0.2, np.float32)
    lit = dcp.apply_camera(grey, prof, {"camera": "Other Maker X1"}, (2850.0, 0.0))
    assert np.allclose(lit, grey * 2.0 ** 0.5, atol=1e-5)
    assert dcp.needs_exposure(prof)


def test_the_tone_curve_becomes_monotone_knots(tmp_path):
    from app.develop import dcp

    prof = dcp.read(synthetic(tmp_path / "t.dcp"))
    knots = np.asarray(dcp.tone_knots(prof), np.float64)
    assert knots.shape[1] == 2 and np.all(np.diff(knots[:, 1]) >= 0) and knots[-1, 1] < 1.0
    xs = knots[:, 0] * 2.0 ** -dcp.SENSOR_EV
    assert np.allclose(knots[:, 1], np.minimum(np.interp(xs, [0, 0.25, 1], [0, 0.40, 1]), 0.999), atol=1e-9)


def test_an_imported_profile_is_offered_for_its_camera_only(client, commands, tmp_path):
    from app.develop import profiles

    res = commands("preset.import", {"paths": [str(synthetic(tmp_path / "Formlit Synthetic Dual.dcp"))]})
    pid = res["imported"][0]
    assert pid.startswith("dcp:")
    assert pid in {p["id"] for p in profiles.catalogue(CAMERA)}
    assert pid not in {p["id"] for p in profiles.catalogue("Other Maker X1")}


def test_a_render_with_an_imported_profile_shifts_hue(client, commands, tmp_path):
    from app.develop import dcp, render
    from conftest import write_png

    res = commands("preset.import", {"paths": [str(synthetic(tmp_path / "Hue Probe.dcp"))]})
    pid = res["imported"][0]
    from app.services import decode
    img, info = decode.load_linear(write_png(tmp_path / "red.png", np.tile(np.array([[[200, 40, 40]]], np.uint8), (8, 8, 1))))
    info = {**info, "asShotTemp": 6500.0, "asShotTint": 0.0}
    dev = {"profile": {"id": pid}, "basic": {"temp": 6500, "tint": 0}}
    plain = render.render(img, info, {}, size=(8, 8))[4, 4]
    shifted = render.render(img, info, dev, size=(8, 8))[4, 4]
    assert dcp.load(pid[4:]) is not None
    assert shifted[1] > plain[1] + 0.05, (plain, shifted)


@pytest.mark.skipif(not REAL_R5.is_file(), reason="real DCP fixture missing")
def test_a_real_canon_eos_r5_profile_imports_and_keeps_greys_neutral(client, commands, tmp_path):
    from app.develop import dcp, profiles

    prof = dcp.read(REAL_R5)
    assert prof["camera"] == "CANON EOS R5" and prof["copyright"] == "public domain"
    assert prof["illum1"] == (17,) and prof["illum2"] == (21,) and prof["hsmDims"] == (90, 30, 1)
    assert len(prof["hsm1"]) == 90 * 30 * 3 and len(prof["fm1"]) == len(prof["fm2"]) == 9
    pid = commands("preset.import", {"paths": [str(REAL_R5)]})["imported"][0]
    assert pid in {p["id"] for p in profiles.catalogue("Canon EOS R5")}
    assert pid not in {p["id"] for p in profiles.catalogue("Nikon Z 6")}
    info = {"camera": "Canon EOS R5", "camToRec2020": np.eye(3).tolist()}
    greys = np.linspace(0.02, 0.9, 12, dtype=np.float32)[:, None, None] * np.ones((1, 1, 3), np.float32)
    for temp in (2850.0, 4500.0, 6500.0):
        out = dcp.apply_camera(greys, prof, info, (temp, 0.0))
        assert np.allclose(out, out[..., 1:2], rtol=0.01, atol=1e-4), (temp, out[:, 0])
        assert np.allclose(out[..., 1], greys[..., 1], rtol=0.02), (temp, out[:, 0, 1])
    sat = np.array([[[0.6, 0.1, 0.1], [0.1, 0.5, 0.1], [0.1, 0.1, 0.6]]], np.float32)
    assert not np.allclose(dcp.apply_camera(sat, prof, info, (5000.0, 0.0)), sat, atol=1e-3)
