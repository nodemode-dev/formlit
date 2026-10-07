import struct
from functools import lru_cache
from pathlib import Path

import numpy as np

TYPES = {1: ("B", 1), 2: ("s", 1), 3: ("H", 2), 4: ("I", 4), 5: ("II", 8), 7: ("B", 1), 8: ("h", 2), 9: ("i", 4), 10: ("ii", 8), 11: ("f", 4), 12: ("d", 8)}
TAGS = {50936: "name", 50937: "hsmDims", 50938: "hsm1", 50939: "hsm2", 50940: "toneCurve", 50942: "copyright", 50981: "lookDims", 50982: "look",
        51107: "hsmEncoding", 51108: "lookEncoding", 51109: "baselineExposureOffset", 50778: "illum1", 50779: "illum2",
        50708: "camera", 50721: "cm1", 50722: "cm2", 50964: "fm1", 50965: "fm2"}
LIGHT_K = {1: 5500.0, 2: 4150.0, 3: 2850.0, 4: 5500.0, 9: 5500.0, 10: 6500.0, 11: 7500.0, 12: 6400.0, 13: 5000.0, 14: 4150.0, 15: 3450.0,
           16: 2925.0, 17: 2850.0, 18: 5500.0, 19: 6500.0, 20: 5500.0, 21: 6500.0, 22: 7500.0, 23: 5000.0, 24: 3200.0}
SENSOR_EV = 0.35


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


def _enc(v: np.ndarray) -> np.ndarray:
    v = np.clip(v, 0.0, 1.0)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(np.maximum(v, 0.0031308), 1 / 2.4) - 0.055)


def _dec(v: np.ndarray) -> np.ndarray:
    v = np.clip(v, 0.0, 1.0)
    return np.where(v <= 0.04045, v / 12.92, np.power((np.maximum(v, 0.04045) + 0.055) / 1.055, 2.4))


def _apply_table(rgb: np.ndarray, dims: tuple, table, srgb_value: bool, vscale: float = 1.0) -> np.ndarray:
    hd, sd, vd = (int(x) for x in dims[:3])
    deltas = np.asarray(table, np.float64).reshape(max(1, vd), hd, sd, 3)
    h, s, v = _rgb_to_hsv(np.maximum(rgb, 0.0))
    vs = np.minimum(v * vscale, 1.0)
    vv = _enc(vs) if srgb_value else vs
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
    if srgb_value:
        v2 = v * _dec(vv * acc[..., 2]) / np.maximum(vs, 1e-12)
    else:
        v2 = v * acc[..., 2]
    return _hsv_to_rgb(h2, s2, v2)


@lru_cache(maxsize=8)
def load(stem: str) -> dict | None:
    from app.core import config
    path = config.profiles_dir() / f"{stem}.dcp"
    return read(path) if path.is_file() else None


def _norm(s: str) -> str:
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def fits_camera(prof: dict, camera: str) -> bool:
    own = _norm(prof.get("camera") or "")
    other = _norm(camera)
    return bool(own) and bool(other) and (own == other or own.endswith(other) or other.endswith(own))


def weight1(prof: dict, temp: float) -> float:
    t1 = LIGHT_K.get(int((prof.get("illum1") or (0,))[0]), 0.0)
    t2 = LIGHT_K.get(int((prof.get("illum2") or (0,))[0]), 0.0)
    if not t1 or not t2 or t1 == t2:
        return 1.0
    lo, hi, flip = (t1, t2, False) if t1 < t2 else (t2, t1, True)
    g = 1.0 if temp <= lo else 0.0 if temp >= hi else (1.0 / temp - 1.0 / hi) / (1.0 / lo - 1.0 / hi)
    return 1.0 - g if flip else g


def _pick(prof: dict, a: str, b: str, g: float) -> np.ndarray | None:
    one, two = prof.get(a), prof.get(b)
    if one is None and two is None:
        return None
    if one is None or two is None:
        return np.asarray(one if two is None else two, np.float64)
    return np.asarray(one, np.float64) * g + np.asarray(two, np.float64) * (1.0 - g)


def needs_exposure(prof: dict) -> bool:
    dims = prof.get("lookDims")
    return prof.get("look") is not None and bool(dims) and (int(dims[2]) > 1 or int((prof.get("lookEncoding") or (0,))[0]) == 1)


def to_prophoto(prof: dict, info: dict, wb: tuple[float, float]) -> np.ndarray:
    from app.develop import colour
    from app.services.decode import temp_tint_to_xy
    base = colour.from_xyz("prophoto") @ colour.bradford(colour.D65, colour.D50) @ colour.to_xyz("rec2020")
    cam = info.get("camToRec2020")
    if cam is None or not fits_camera(prof, info.get("camera", "")):
        return base
    g = weight1(prof, float(wb[0]))
    from_cam = np.linalg.inv(np.asarray(cam, np.float64))
    fm = _pick(prof, "fm1", "fm2", g)
    if fm is not None and fm.size == 9:
        return colour.from_xyz("prophoto") @ fm.reshape(3, 3) @ from_cam
    cm = _pick(prof, "cm1", "cm2", g)
    if cm is None or cm.size != 9:
        return base
    cm = cm.reshape(3, 3)
    xy = temp_tint_to_xy(float(wb[0]), float(wb[1]))
    white = colour.xy_to_xyz(xy)
    neutral = cm @ white
    return colour.from_xyz("prophoto") @ colour.bradford(xy, colour.D50) @ np.linalg.inv(cm) @ np.diag(neutral) @ from_cam


def _pp_matrix() -> np.ndarray:
    from app.develop import colour
    return colour.from_xyz("prophoto") @ colour.bradford(colour.D65, colour.D50) @ colour.to_xyz("rec2020")


def lookup(rgb: np.ndarray, dims, table, srgb_value: bool, vscale: float = 1.0) -> np.ndarray:
    hd, sd, vd = (int(x) for x in dims[:3])
    try:
        from app.develop import dcp_kernel
    except ImportError:
        return _apply_table(rgb, dims, table, srgb_value, vscale)
    deltas = np.ascontiguousarray(np.asarray(table, np.float64).reshape(max(1, vd), hd, sd, 3))
    flat = np.ascontiguousarray(rgb.reshape(-1, 3), np.float64)
    return dcp_kernel.table(flat, deltas, bool(srgb_value), float(vscale)).reshape(rgb.shape)


def apply_camera(lin: np.ndarray, prof: dict, info: dict | None = None, wb: tuple[float, float] = (6500.0, 0.0), rows: int = 512) -> np.ndarray:
    info = info or {}
    to_pp = to_prophoto(prof, info, wb)
    back = np.linalg.inv(_pp_matrix())
    gain = float(info.get("sensorGain") or 2.0 ** SENSOR_EV)
    offset = 2.0 ** float((prof.get("baselineExposureOffset") or (0.0,))[0])
    hsm = _pick(prof, "hsm1", "hsm2", weight1(prof, float(wb[0])))
    out = np.empty_like(lin)
    for y0 in range(0, lin.shape[0], rows):
        pp = np.maximum(lin[y0:y0 + rows].astype(np.float64), 0.0) @ to_pp.T
        if prof.get("hsmDims") and hsm is not None:
            pp = lookup(pp, prof["hsmDims"], hsm, int((prof.get("hsmEncoding") or (0,))[0]) == 1, 1.0 / gain)
        out[y0:y0 + rows] = np.maximum((pp * offset) @ back.T, 0.0)
    return out


def apply_look(lin: np.ndarray, prof: dict, ev: float = 0.0, rows: int = 512) -> np.ndarray:
    if not (prof.get("lookDims") and prof.get("look") is not None):
        return lin
    to_pp = _pp_matrix()
    back = np.linalg.inv(to_pp)
    scale = 2.0 ** (float(ev) - SENSOR_EV)
    srgb = int((prof.get("lookEncoding") or (0,))[0]) == 1
    out = np.empty_like(lin)
    for y0 in range(0, lin.shape[0], rows):
        pp = np.maximum(lin[y0:y0 + rows].astype(np.float64), 0.0) @ to_pp.T
        pp = lookup(pp, prof["lookDims"], prof["look"], srgb, scale)
        out[y0:y0 + rows] = np.maximum(pp @ back.T, 0.0)
    return out


def apply_linear(lin: np.ndarray, prof: dict, info: dict | None = None, wb: tuple[float, float] = (6500.0, 0.0), ev: float = 0.0) -> np.ndarray:
    return apply_look(apply_camera(lin, prof, info, wb), prof, ev)


def tone_knots(prof: dict) -> list | None:
    curve = prof.get("toneCurve")
    if not curve or len(curve) < 4:
        return None
    pts = np.asarray(curve, np.float64).reshape(-1, 2)
    xs = np.geomspace(0.0007, 1.2, 32)
    ys = np.interp(xs * 2.0 ** -SENSOR_EV, pts[:, 0], pts[:, 1])
    ys = np.minimum(np.maximum.accumulate(ys), 0.999)
    return [[float(x), float(y)] for x, y in zip(xs, ys)]
