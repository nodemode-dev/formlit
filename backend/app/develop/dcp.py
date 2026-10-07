import struct
from functools import lru_cache
from pathlib import Path

import numpy as np

TYPES = {1: ("B", 1), 2: ("s", 1), 3: ("H", 2), 4: ("I", 4), 5: ("II", 8), 7: ("B", 1), 8: ("h", 2), 9: ("i", 4), 10: ("ii", 8), 11: ("f", 4), 12: ("d", 8)}
TAGS = {50936: "name", 50937: "hsmDims", 50938: "hsm1", 50939: "hsm2", 50940: "toneCurve", 50942: "copyright", 50981: "lookDims", 50982: "look",
        51107: "hsmEncoding", 51108: "lookEncoding", 51109: "baselineExposureOffset", 50778: "illum1", 50779: "illum2"}


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


@lru_cache(maxsize=8)
def load(stem: str) -> dict | None:
    from app.core import config
    path = config.profiles_dir() / f"{stem}.dcp"
    return read(path) if path.is_file() else None


def apply_linear(lin: np.ndarray, prof: dict, rows: int = 256) -> np.ndarray:
    from app.develop import colour
    to_pp = colour.from_xyz("prophoto") @ colour.bradford(colour.D65, colour.D50) @ colour.to_xyz("rec2020")
    back = np.linalg.inv(to_pp)
    hsm = prof.get("hsm2") or prof.get("hsm1")
    out = np.empty_like(lin)
    for y0 in range(0, lin.shape[0], rows):
        pp = np.maximum(lin[y0:y0 + rows].astype(np.float64), 0.0) @ to_pp.T
        if prof.get("hsmDims") and hsm:
            pp = _apply_table(pp, prof["hsmDims"], hsm, int((prof.get("hsmEncoding") or (0,))[0]) == 1)
        if prof.get("lookDims") and prof.get("look"):
            pp = _apply_table(pp, prof["lookDims"], prof["look"], int((prof.get("lookEncoding") or (0,))[0]) == 1)
        out[y0:y0 + rows] = np.maximum(pp @ back.T, 0.0)
    return out
