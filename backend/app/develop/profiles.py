import copy
import json
from functools import lru_cache
from pathlib import Path
from struct import error as struct_error

import numpy as np

from app.core import config
from app.develop import camera_styles, settings as S

OWN = [
    {"id": "fl.neutral", "group": "Basic", "name": "Neutral", "delta": {"light.contrast": -14, "color.saturation": -8, "curve.highlights": -8, "curve.shadows": 8}},
    {"id": "fl.vivid", "group": "Basic", "name": "Vivid", "delta": {"light.contrast": 14, "color.vibrance": 24, "color.saturation": 8, "curve.darks": -4}},
    {"id": "fl.landscape", "group": "Basic", "name": "Landscape", "delta": {"light.contrast": 10, "color.vibrance": 16, "mixer.green.sat": 12, "mixer.aqua.sat": 8,
                                                                         "mixer.blue.sat": 10, "mixer.blue.lum": -10, "effects.clarity": 10, "effects.dehaze": 6}},
    {"id": "fl.portrait", "group": "Basic", "name": "Portrait", "delta": {"light.contrast": -6, "mixer.red.sat": -6, "mixer.orange.sat": -8, "mixer.orange.lum": 6,
                                                                       "curve.shadows": 4, "effects.texture": -12}},
    {"id": "fl.monochrome", "group": "Basic", "name": "Monochrome", "treatment": "bw", "delta": {"light.contrast": 10, "bw.red": 8, "bw.orange": 6, "bw.blue": -10}},
    {"id": "fl.creative.warmfade", "group": "Creative", "name": "Warm Fade", "delta": {"light.contrast": -8, "curve.shadows": 22, "color.saturation": -10,
                                                                                     "grading.highlights.hue": 45, "grading.highlights.sat": 18,
                                                                                     "grading.shadows.hue": 30, "grading.shadows.sat": 10}},
    {"id": "fl.creative.coolmatte", "group": "Creative", "name": "Cool Matte", "delta": {"light.contrast": -6, "curve.shadows": 24, "curve.highlights": -10,
                                                                                       "color.saturation": -14, "grading.shadows.hue": 210, "grading.shadows.sat": 18,
                                                                                       "grading.highlights.hue": 40, "grading.highlights.sat": 8}},
    {"id": "fl.creative.tealorange", "group": "Creative", "name": "Teal and Orange", "delta": {"light.contrast": 12, "mixer.orange.sat": 10, "mixer.blue.hue": -15,
                                                                                             "mixer.aqua.hue": 10, "grading.shadows.hue": 195, "grading.shadows.sat": 26,
                                                                                             "grading.highlights.hue": 35, "grading.highlights.sat": 18}},
    {"id": "fl.creative.golden", "group": "Creative", "name": "Golden Hour", "delta": {"light.contrast": 6, "color.vibrance": 8, "mixer.orange.sat": 8,
                                                                                     "mixer.yellow.sat": 10, "grading.global.hue": 40, "grading.global.sat": 12}},
    {"id": "fl.creative.muted", "group": "Creative", "name": "Silver Muted", "delta": {"light.contrast": 14, "color.saturation": -35, "curve.highlights": -8,
                                                                                     "grading.global.hue": 210, "grading.global.sat": 4}},
    {"id": "fl.bw.punch", "group": "B&W", "name": "High Contrast", "treatment": "bw", "delta": {"light.contrast": 30, "curve.shadows": -10, "curve.highlights": 8,
                                                                                               "effects.clarity": 10}},
    {"id": "fl.bw.soft", "group": "B&W", "name": "Soft", "treatment": "bw", "delta": {"light.contrast": -14, "curve.shadows": 12, "curve.highlights": -6}},
    {"id": "fl.bw.redfilter", "group": "B&W", "name": "Red Filter", "treatment": "bw", "delta": {"light.contrast": 12, "bw.red": 40, "bw.orange": 25, "bw.yellow": 10,
                                                                                               "bw.blue": -45, "bw.aqua": -25}},
    {"id": "fl.bw.cooltone", "group": "B&W", "name": "Cool Tone", "treatment": "bw", "delta": {"light.contrast": 8, "grading.global.hue": 220, "grading.global.sat": 10}},
]
PROFILES = [{"id": "fl.color", "group": "Basic", "name": "Color", "delta": {}}] + [dict(s, group=camera_styles.GROUP, raw=True) for s in camera_styles.STYLES] + OWN
BY_ID = {p["id"]: p for p in PROFILES}


SPATIAL = ("effects.clarity", "effects.texture", "effects.dehaze")
TABLE_N = 33


def is_table(p: dict) -> bool:
    return bool(p.get("delta")) or p.get("group") == camera_styles.GROUP


def _meta(stem: str) -> dict:
    path = config.profiles_dir() / f"{stem}.json"
    try:
        return _meta_at(str(path), path.stat().st_mtime_ns) if path.is_file() else {}
    except OSError:
        return {}


@lru_cache(maxsize=64)
def _meta_at(path: str, _mtime: int) -> dict:
    try:
        meta = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return meta if isinstance(meta, dict) else {}


def catalogue(camera: str = "", keep: str = "") -> list[dict]:
    from app.develop import dcp

    def row(p: dict) -> dict:
        return {"id": p["id"], "group": p["group"], "name": camera_styles.name_for(p["id"], camera, p["name"]), "mono": p.get("treatment") == "bw",
                "raw": bool(p.get("raw")), "table": is_table(p)}
    ids = camera_styles.listed(camera)
    if keep in BY_ID and BY_ID[keep]["group"] == camera_styles.GROUP and keep not in ids:
        ids = [*ids, keep]
    rest = [row(p) for p in PROFILES if p["group"] != camera_styles.GROUP]
    out = rest[:1] + [row(BY_ID[i]) for i in ids if i in BY_ID] + rest[1:]
    folder = config.profiles_dir()
    stems = {p.stem for p in folder.glob("*.cube")} | {p.stem for p in folder.glob("*.json") if _look_data(p.stem) is not None}
    for stem in sorted(stems):
        meta = _meta(stem)
        out.append({"id": f"lut:{stem}", "group": meta.get("group") or "Imported", "name": meta.get("name") or stem.replace("_", " "), "mono": bool(meta.get("mono")), "table": True})
    for path in sorted(config.profiles_dir().glob("*.dcp")):
        try:
            prof = dcp.load(path.stem) or {}
        except (OSError, ValueError, struct_error):
            continue
        if camera and prof.get("camera") and not dcp.fits_camera(prof, camera):
            continue
        out.append({"id": f"dcp:{path.stem}", "group": "Camera Profiles (DCP)", "name": _meta(path.stem).get("name") or path.stem.replace("_", " "), "mono": False, "raw": True,
                    "dcp": True, "camera": str(prof.get("camera") or "")})
    return out


def _angle(cid: str) -> bool:
    return cid.startswith("grading.") and cid.endswith(".hue")


def _delta(p: dict, base: str = "") -> dict:
    own = dict(p.get("delta") or {})
    ref = BY_ID.get(base) if base else None
    if ref is None or ref is p:
        return own
    out = {}
    other = ref.get("delta") or {}
    for cid in set(own) | set(other):
        if _angle(cid):
            out[cid] = own.get(cid, other.get(cid, 0))
        else:
            d = float(own.get(cid, 0)) - float(other.get(cid, 0))
            if d:
                out[cid] = d
    return out


def style_of(info: dict | None) -> str:
    s = str((info or {}).get("cameraStyle") or "")
    return s if s in BY_ID and s != "fl.camera.standard" else ""


def _with_delta(dev: dict, delta: dict, amount: float, keys) -> dict:
    controls = S.controls()
    for cid in keys:
        if cid not in controls or cid not in delta:
            continue
        if _angle(cid):
            S.put(dev, cid, float(delta[cid]))
        else:
            S.put(dev, cid, S.get(dev, cid) + float(delta[cid]) * amount)
    return dev


def offset_key(cid: str) -> bool:
    return cid in SPATIAL or cid.startswith("bw.")


def _amount(prof: dict) -> float:
    v = prof.get("amount", 100)
    v = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v) else 100.0
    return min(max(v, 0.0), 200.0) / 100.0


def effective(dev: dict, info: dict | None = None) -> dict:
    prof = dev.get("profile") if isinstance(dev.get("profile"), dict) else {}
    pid = str(prof.get("id", "") or "")
    if pid.startswith("lut:"):
        if _meta(pid[4:]).get("mono") and dev.get("treatment") != "bw":
            out = copy.deepcopy(dev)
            out["treatment"] = "bw"
            return out
        return dev
    p = BY_ID.get(pid)
    if p is None or pid == "fl.color":
        return dev
    out = copy.deepcopy(dev)
    camera = p.get("group") == camera_styles.GROUP
    base = style_of(info) if camera else ""
    delta = _delta(p, base)
    _with_delta(out, delta, _amount(prof), [k for k in delta if offset_key(k)])
    if p.get("treatment") == "bw":
        out["treatment"] = "bw"
    if camera:
        out.setdefault("profile", {})["base"] = base
    return out


@lru_cache(maxsize=64)
def table_of(pid: str, base: str = "") -> np.ndarray | None:
    from app.develop import colour, finish
    p = BY_ID.get(pid)
    if p is None or not is_table(p):
        return None
    delta = {k: v for k, v in _delta(p, base).items() if not offset_key(k)}
    if not delta:
        return None
    dev: dict = {}
    _with_delta(dev, delta, 1.0, list(delta))
    n = TABLE_N
    g = np.linspace(0.0, 1.0, n, dtype=np.float32)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")
    lin = colour.srgb_decode(np.stack([r, gg, b], axis=-1)).reshape(n * n, n, 3)
    to_work = (colour.from_xyz("rec2020") @ colour.to_xyz("srgb")).astype(np.float32)
    lin = np.ascontiguousarray(np.maximum(lin @ to_work.T, 0.0), np.float32)
    out = finish.finish(lin, {}, dev, None, {"raw": False}, n, n * n, float(n * n), [], "srgb")
    table = out.reshape(n, n, n, 3).astype(np.float32)
    table.setflags(write=False)
    return table


LUT_CHUNK = 1 << 15


def _cube_numbers(parts: list[str], n: int) -> list[float] | None:
    if len(parts) != n:
        return None
    try:
        return [float(p) for p in parts]
    except ValueError:
        return None


@lru_cache(maxsize=8)
def load_cube(name: str) -> np.ndarray | None:
    path = config.profiles_dir() / f"{name}.cube"
    try:
        text = path.read_bytes().decode("utf-8-sig", errors="replace")
    except OSError:
        return None
    size, size_1d, lo, hi, rows = 0, 0, [0.0, 0.0, 0.0], [1.0, 1.0, 1.0], []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key = line.split(None, 1)[0]
        if key == "TITLE":
            continue
        parts = line.split("#", 1)[0].split()
        if key[0].isalpha():
            if key == "LUT_3D_SIZE" and len(parts) == 2 and parts[1].isdigit():
                size = int(parts[1])
            elif key == "LUT_1D_SIZE" and len(parts) == 2 and parts[1].isdigit():
                size_1d = int(parts[1])
            elif key in ("DOMAIN_MIN", "DOMAIN_MAX"):
                got = _cube_numbers(parts[1:], 3)
                if got is not None:
                    lo, hi = (got, hi) if key == "DOMAIN_MIN" else (lo, got)
            continue
        got = _cube_numbers(parts, 3)
        if got is not None:
            rows.append(got)
    count = size ** 3
    if size < 2 or len(rows) < count:
        return None
    skip = size_1d if size_1d and len(rows) >= size_1d + count else 0
    data = np.asarray(rows[skip:skip + count], np.float64)
    lo_a, hi_a = np.asarray(lo, np.float64), np.asarray(hi, np.float64)
    span = np.where(np.abs(hi_a - lo_a) > 1e-12, hi_a - lo_a, 1.0)
    return np.clip((data - lo_a) / span, 0.0, 1.0).astype(np.float32).reshape(size, size, size, 3)


def _lerp_into(a: np.ndarray, b: np.ndarray, t: np.ndarray) -> np.ndarray:
    b -= a
    b *= t
    a += b
    return a


def _trilinear(e: np.ndarray, flat: np.ndarray, n: int) -> np.ndarray:
    f = np.clip(np.nan_to_num(e, nan=0.0), 0.0, 1.0)
    f *= np.float32(n - 1)
    i0 = np.minimum(f.astype(np.int32), n - 2)
    f -= i0
    fr, fg, fb = f[:, 0:1], f[:, 1:2], f[:, 2:3]
    base = (i0[:, 2] * n + i0[:, 1]) * n + i0[:, 0]
    rows = [_lerp_into(flat[base + off], flat[base + off + 1], fr) for off in (0, n, n * n, n * n + n)]
    return _lerp_into(_lerp_into(rows[0], rows[1], fg), _lerp_into(rows[2], rows[3], fg), fb)


def apply_lut(e: np.ndarray, lut: np.ndarray) -> np.ndarray:
    n = lut.shape[0]
    flat = np.ascontiguousarray(lut, np.float32).reshape(-1, 3)
    src = np.asarray(e, np.float32)
    pix = src.reshape(-1, 3)
    out = np.empty(pix.shape, np.float32)
    for s in range(0, pix.shape[0], LUT_CHUNK):
        out[s:s + LUT_CHUNK] = _trilinear(pix[s:s + LUT_CHUNK], flat, n)
    return out.reshape(src.shape)


def lut_of(dev: dict, space: str = "srgb") -> tuple[np.ndarray, float] | None:
    prof = dev.get("profile") if isinstance(dev.get("profile"), dict) else {}
    pid = str(prof.get("id", "") or "")
    if pid.startswith("lut:"):
        table = load_cube(pid[4:])
    elif pid in BY_ID and is_table(BY_ID[pid]):
        table = table_of(pid, str(prof.get("base", "") or ""))
    else:
        table = None
    if table is None:
        return None
    return in_space(table, "rec2020" if space == "linear" else space), _amount(prof)


_SPACE_TABLES: dict = {}
SPACE_N = 49


def in_space(lut: np.ndarray, space: str) -> np.ndarray:
    if space == "srgb":
        return lut
    hit = _SPACE_TABLES.get((id(lut), space))
    if hit is not None and hit[0] is lut:
        return hit[1]
    from app.develop import colour
    n = SPACE_N
    g = np.linspace(0.0, 1.0, n, dtype=np.float32)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")
    lt = colour.srgb_decode(np.stack([r, gg, b], axis=-1))
    t2s = colour.working_to("srgb") @ np.linalg.inv(colour.working_to(space))
    es = colour.srgb_encode(lt @ t2s.T.astype(np.float32))
    d = colour.srgb_decode(apply_lut(es, lut)) - colour.srgb_decode(es)
    out = colour.srgb_encode(lt + d @ np.linalg.inv(t2s).T.astype(np.float32))
    if len(_SPACE_TABLES) > 7:
        _SPACE_TABLES.clear()
    _SPACE_TABLES[(id(lut), space)] = (lut, out)
    return out


def _owner(stem: str) -> str:
    folder = config.profiles_dir()
    if (folder / f"{stem}.dcp").is_file():
        return "dcp"
    if (folder / f"{stem}.json").is_file():
        return "dcp" if str(_meta(stem).get("source", "")).lower().endswith(".dcp") else "xmp"
    return "cube" if (folder / f"{stem}.cube").is_file() else ""


def _stem_for(stem: str, kind: str) -> str:
    out, n = stem, 1
    while _owner(out) not in ("", kind):
        n += 1
        out = f"{stem}_{n}"
    return out


def _changed() -> None:
    from app.develop import dcp, render
    load_cube.cache_clear()
    _look_data.cache_clear()
    dcp.load.cache_clear()
    render.drop_stages()


def import_cube(path: Path) -> str:
    stem = _stem_for(Path(path).stem, "cube")
    dst = config.profiles_dir() / f"{stem}.cube"
    dst.write_bytes(Path(path).read_bytes())
    _changed()
    return f"lut:{stem}"


def import_profile_xmp(path: Path) -> str:
    from app.develop import adobe_profile
    prof = adobe_profile.read(path)
    folder = config.profiles_dir()
    stem = _stem_for(adobe_profile.stem_of(prof["name"]), "xmp")
    if prof["table"] is not None:
        adobe_profile.write_cube(prof, folder, stem)
    else:
        (folder / f"{stem}.cube").unlink(missing_ok=True)
    meta = {"name": prof["name"], "group": f"Imported: {prof['group']}" if prof["group"] else "Imported", "mono": prof["mono"], "source": Path(path).name}
    if prof.get("look"):
        meta["look"] = prof["look"]
    (folder / f"{stem}.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    _changed()
    return f"lut:{stem}"


@lru_cache(maxsize=16)
def _look_data(stem: str) -> dict | None:
    look = _meta(stem).get("look")
    if not isinstance(look, dict) or len(look.get("dims") or []) != 3:
        return None
    hd, sd, vd = (int(x) for x in look["dims"])
    data = np.asarray(look.get("data") or [], np.float64)
    if data.size != hd * sd * vd * 3:
        return None
    return {"dims": (hd, sd, vd), "data": data.reshape(-1, 3), "encoding": int(look.get("encoding", 0))}


def look_of(dev: dict) -> tuple[str, dict] | None:
    prof = dev.get("profile") or {}
    pid = str(prof.get("id", ""))
    if pid.startswith("dcp:"):
        from app.develop import dcp
        p = dcp.load(pid[4:])
        if p and p.get("lookDims") and p.get("look"):
            return pid, {"lookDims": p["lookDims"], "look": p["look"], "lookEncoding": p.get("lookEncoding")}
        return None
    if not pid.startswith("lut:"):
        return None
    look = _look_data(pid[4:])
    if look is None:
        return None
    a = max(0.0, min(2.0, float(prof.get("amount", 100)) / 100.0))
    d = look["data"]
    scaled = np.stack([d[:, 0] * a, np.maximum(1.0 + (d[:, 1] - 1.0) * a, 0.0), np.maximum(1.0 + (d[:, 2] - 1.0) * a, 0.0)], axis=-1)
    return f"{pid}|{a:.4f}", {"lookDims": look["dims"], "look": scaled.ravel(), "lookEncoding": (look["encoding"],)}


def import_dcp(path: Path) -> str:
    from app.develop import dcp
    prof = dcp.read(path)
    tables = (prof.get("hsmDims") and (prof.get("hsm1") or prof.get("hsm2"))) or (prof.get("lookDims") and prof.get("look")) or prof.get("toneCurve")
    if not tables and not (prof.get("camera") and (prof.get("fm1") or prof.get("fm2") or prof.get("cm1") or prof.get("cm2"))):
        raise ValueError("This file has no colour tables, tone curve or camera matrices to use")
    name = str(prof.get("name") or path.stem).strip() or path.stem
    stem = _stem_for("".join(ch for ch in name if ch.isalnum() or ch in " ._-").strip().replace(" ", "_")[:80] or path.stem, "dcp")
    dst = config.profiles_dir() / f"{stem}.dcp"
    dst.write_bytes(Path(path).read_bytes())
    (config.profiles_dir() / f"{stem}.json").write_text(json.dumps({"name": name, "source": Path(path).name}, indent=1), encoding="utf-8")
    _changed()
    return f"dcp:{stem}"
