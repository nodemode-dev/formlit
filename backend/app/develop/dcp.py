import re
import struct
from pathlib import Path

import numpy as np

TYPES = {1: ("B", 1), 2: ("s", 1), 3: ("H", 2), 4: ("I", 4), 5: ("II", 8), 7: ("B", 1), 8: ("h", 2), 9: ("i", 4), 10: ("ii", 8), 11: ("f", 4), 12: ("d", 8)}
TAGS = {50936: "name", 50937: "hsmDims", 50938: "hsm1", 50939: "hsm2", 50940: "toneCurve", 50942: "copyright", 50981: "lookDims", 50982: "look",
        51107: "hsmEncoding", 51108: "lookEncoding", 51109: "baselineExposureOffset", 50778: "illum1", 50779: "illum2"}

PROPHOTO_TO_XYZ = np.array([[0.7976749, 0.1351917, 0.0313534], [0.2880402, 0.7118741, 0.0000857], [0.0, 0.0, 0.8252100]])
SRGB_TO_XYZ = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
BRADFORD = np.array([[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]])


def _adapt(src_white: np.ndarray, dst_white: np.ndarray) -> np.ndarray:
    s, d = BRADFORD @ src_white, BRADFORD @ dst_white
    return np.linalg.inv(BRADFORD) @ np.diag(d / s) @ BRADFORD


D65 = np.array([0.95047, 1.0, 1.08883])
D50 = np.array([0.96422, 1.0, 0.82521])
SRGB_TO_PP = np.linalg.inv(PROPHOTO_TO_XYZ) @ _adapt(D65, D50) @ SRGB_TO_XYZ
PP_TO_SRGB = np.linalg.inv(SRGB_TO_PP)


def read(path: Path) -> dict:
    data = Path(path).read_bytes()
    if len(data) < 8 or data[:2] not in (b"II", b"MM") or data[2:4] not in (b"RC", b"CR", b"*\x00", b"\x00*"):
        raise ValueError("Not a DNG camera profile (.dcp)")
    end = "<" if data[:2] == b"II" else ">"
    off = struct.unpack(end + "I", data[4:8])[0]
    n = struct.unpack(end + "H", data[off:off + 2])[0]
    out: dict = {}
    for i in range(n):
        e = off + 2 + 12 * i
        tag, typ, count = struct.unpack(end + "HHI", data[e:e + 8])
        if tag not in TAGS or typ not in TYPES:
            continue
        fmt, size = TYPES[typ]
        total = size * count
        start = e + 8 if total <= 4 else struct.unpack(end + "I", data[e + 8:e + 12])[0]
        raw = data[start:start + total]
        if typ == 2:
            out[TAGS[tag]] = raw.split(b"\x00")[0].decode("utf-8", "replace")
            continue
        vals = struct.unpack(end + fmt * count, raw) if typ not in (5, 10) else struct.unpack(end + fmt * count, raw)
        if typ in (5, 10):
            vals = tuple(vals[k] / vals[k + 1] if vals[k + 1] else 0.0 for k in range(0, len(vals), 2))
        out[TAGS[tag]] = vals
    return out


def _rgb_to_hsv(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    v = np.max(rgb, axis=-1)
    mn = np.min(rgb, axis=-1)
    d = v - mn
    s = np.where(v > 0, d / np.maximum(v, 1e-12), 0.0)
    safe = np.maximum(d, 1e-12)
    h = np.where(r == v, (g - b) / safe, np.where(g == v, 2.0 + (b - r) / safe, 4.0 + (r - g) / safe))
    h = np.where(d > 0, np.mod(h, 6.0), 0.0)
    return h, s, v


def _hsv_to_rgb(h: np.ndarray, s: np.ndarray, v: np.ndarray) -> np.ndarray:
    h = np.mod(h, 6.0)
    i = np.floor(h)
    f = h - i
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    i = i.astype(np.int32)
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], axis=-1)


def _apply_table(rgb: np.ndarray, dims: tuple, table: tuple, srgb_value: bool) -> np.ndarray:
    hd, sd, vd = (int(x) for x in dims[:3])
    deltas = np.asarray(table, np.float64).reshape(max(1, vd), hd, sd, 3)
    h, s, v = _rgb_to_hsv(np.maximum(rgb, 0.0))
    vv = np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(np.clip(v, 0.0031308, None), 1 / 2.4) - 0.055) if srgb_value else v
    hf = h * hd / 6.0
    h0 = np.floor(hf).astype(np.int32) % hd
    h1 = (h0 + 1) % hd
    fh = hf - np.floor(hf)
    sf = np.clip(s, 0.0, 1.0) * (sd - 1)
    s0 = np.minimum(np.floor(sf).astype(np.int32), max(0, sd - 2))
    s1 = np.minimum(s0 + 1, sd - 1)
    fs = sf - s0
    if vd > 1:
        vf = np.clip(vv, 0.0, 1.0) * (vd - 1)
        v0 = np.minimum(np.floor(vf).astype(np.int32), vd - 2)
        v1 = v0 + 1
        fv = vf - v0
    else:
        v0 = v1 = np.zeros_like(h0)
        fv = np.zeros_like(h)

    def at(vi, hi, si):
        return deltas[vi, hi, si]
    acc = 0.0
    for vi, wv in ((v0, 1 - fv), (v1, fv)):
        for hi, wh in ((h0, 1 - fh), (h1, fh)):
            for si, ws in ((s0, 1 - fs), (s1, fs)):
                acc = acc + at(vi, hi, si) * (wv * wh * ws)[..., None]
    h2 = h + acc[..., 0] * 6.0 / 360.0
    s2 = np.clip(s * acc[..., 1], 0.0, 1.0)
    v2 = v * acc[..., 2]
    return _hsv_to_rgb(h2, s2, v2)


def bake(prof: dict, size: int = 33) -> np.ndarray:
    g = np.linspace(0.0, 1.0, size)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")
    enc = np.stack([r, gg, b], axis=-1)
    lin = np.where(enc <= 0.04045, enc / 12.92, np.power((enc + 0.055) / 1.055, 2.4))
    pp = lin @ SRGB_TO_PP.T
    hsm = prof.get("hsm2") or prof.get("hsm1")
    if prof.get("hsmDims") and hsm:
        pp = _apply_table(pp, prof["hsmDims"], hsm, int((prof.get("hsmEncoding") or (0,))[0]) == 1)
    if prof.get("lookDims") and prof.get("look"):
        pp = _apply_table(pp, prof["lookDims"], prof["look"], int((prof.get("lookEncoding") or (0,))[0]) == 1)
    out = np.clip(pp @ PP_TO_SRGB.T, 0.0, 1.0)
    return np.where(out <= 0.0031308, out * 12.92, 1.055 * np.power(out, 1 / 2.4) - 0.055).astype(np.float32)


def to_cube(src: Path, dst_dir: Path) -> tuple[Path, str]:
    prof = read(src)
    if not (prof.get("hsmDims") and (prof.get("hsm1") or prof.get("hsm2"))) and not (prof.get("lookDims") and prof.get("look")):
        raise ValueError("This profile has no hue and saturation map or look table to carry over; its matrices only fit its own camera")
    name = str(prof.get("name") or src.stem).strip() or src.stem
    stem = re.sub(r"[^A-Za-z0-9 ._-]+", "", name).strip().replace(" ", "_")[:80] or src.stem
    lut = bake(prof)
    n = lut.shape[0]
    lines = [f'TITLE "{name}"', f"# Baked by formlit from {src.name}: hue/saturation map and look table, in sRGB", f"LUT_3D_SIZE {n}"]
    for px in lut.reshape(-1, 3):
        lines.append(f"{px[0]:.6f} {px[1]:.6f} {px[2]:.6f}")
    dst = dst_dir / f"{stem}.cube"
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dst, name
