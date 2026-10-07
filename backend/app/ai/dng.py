import json
import math
from fractions import Fraction
from pathlib import Path

import numpy as np

from app.develop import colour

TAG_PREFIX = "formlit "


def _srational(v: float) -> tuple[int, int]:
    f = Fraction(v).limit_denominator(1_000_000)
    return f.numerator, f.denominator


def write_linear_dng(path: Path, lin: np.ndarray, info: dict | None = None, make: str = "formlit", model: str = "formlit", when: str | None = None) -> Path:
    import tifffile
    info = info or {}
    lin = np.maximum(np.nan_to_num(lin.astype(np.float32), nan=0.0, posinf=0.0), 0.0)
    peak = float(np.percentile(lin, 99.995)) if lin.size else 1.0
    baseline = max(0.0, math.log2(max(peak, 1e-6))) - 0.35
    scale = 2.0 ** -(baseline + 0.35)
    data = np.clip(lin * scale * 65535.0 + 0.5, 0, 65535).astype(np.uint16)
    xyz_to_cam = np.linalg.inv(colour.to_xyz("rec2020"))
    cm: list[int] = []
    for v in xyz_to_cam.reshape(-1):
        cm.extend(_srational(float(v)))
    b = _srational(baseline)
    keep = {k: info[k] for k in ("cameraTone", "cameraLook", "asShotTemp", "asShotTint") if k in info}
    desc = TAG_PREFIX + json.dumps({**keep, "source": info.get("source", "")}, separators=(",", ":"))
    tags = [
        (50706, "B", 4, (1, 4, 0, 0), True),
        (50707, "B", 4, (1, 1, 0, 0), True),
        (50708, "s", 0, model, True),
        (50721, "2i", 9, tuple(cm), True),
        (50778, "H", 1, 21, True),
        (50728, "2I", 3, (1, 1, 1, 1, 1, 1), True),
        (50730, "2i", 1, b, True),
        (50714, "I", 1, 0, True),
        (50717, "I", 1, 65535, True),
        (271, "s", 0, make, True),
        (272, "s", 0, model, True),
        (274, "H", 1, 1, True),
    ]
    if when:
        tags.append((306, "s", 0, when.replace("-", ":").replace("T", " ")[:19], True))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".dng.tmp")
    tifffile.imwrite(str(tmp), data, photometric=34892, planarconfig="contig", description=desc, extratags=tags, software="formlit", metadata=None)
    tmp.replace(path)
    return path


FLIP_TO_ORIENTATION = {0: 1, 3: 3, 5: 8, 6: 6}
COLOR_CODE = {ord("R"): 0, ord("G"): 1, ord("B"): 2}


def _urational(v: float) -> tuple[int, int]:
    f = Fraction(max(0.0, float(v))).limit_denominator(1_000_000)
    return f.numerator, max(1, f.denominator)


def write_cfa_dng(src: Path, dst: Path, exif: dict | None = None, compress: bool = False) -> bool:
    import rawpy
    import tifffile
    exif = exif or {}
    with rawpy.imread(str(src)) as raw:
        pattern = np.asarray(raw.raw_pattern)
        if pattern.shape != (2, 2) or raw.raw_type != rawpy.RawType.Flat:
            return False
        desc = bytes(raw.color_desc)
        cfa = tuple(COLOR_CODE.get(desc[int(i)], 1) for i in pattern.reshape(-1))
        black = raw.black_level_per_channel
        blacks = tuple(int(black[int(i)]) for i in pattern.reshape(-1))
        data = np.ascontiguousarray(raw.raw_image_visible.astype(np.uint16))
        cm: list[int] = []
        for v in np.asarray(raw.rgb_xyz_matrix)[:3].reshape(-1):
            cm.extend(_srational(float(v)))
        wb = list(raw.camera_whitebalance)
        g = wb[1] or 1.0
        neutral: list[int] = []
        for c in (wb[0], wb[1], wb[2]):
            neutral.extend(_urational(g / c if c else 1.0))
        orientation = FLIP_TO_ORIENTATION.get(int(raw.sizes.flip), 1)
        white = int(raw.white_level)
    make, model = str(exif.get("make") or "formlit"), str(exif.get("model") or "Camera")
    tags = [
        (33421, "H", 2, (2, 2), True), (33422, "B", 4, cfa, True),
        (50706, "B", 4, (1, 4, 0, 0), True), (50707, "B", 4, (1, 1, 0, 0), True),
        (50708, "s", 0, f"{make} {model}" if not model.startswith(make) else model, True),
        (50710, "B", 3, (0, 1, 2), True), (50711, "H", 1, 1, True),
        (50713, "H", 2, (2, 2), True), (50714, "H", 4, blacks, True), (50717, "I", 1, white, True),
        (50721, "2i", 9, tuple(cm), True), (50778, "H", 1, 21, True), (50728, "2I", 3, tuple(neutral), True),
        (271, "s", 0, make, True), (272, "s", 0, model, True), (274, "H", 1, orientation, True),
    ]
    if exif.get("captureTime"):
        tags.append((306, "s", 0, str(exif["captureTime"]).replace("-", ":").replace("T", " ")[:19], True))
    for code, key, kind in ((33434, "shutter", "2I"), (33437, "aperture", "2I"), (37386, "focal", "2I")):
        if exif.get(key):
            tags.append((code, kind, 1, _urational(float(exif[key])), True))
    if exif.get("iso"):
        tags.append((34855, "H", 1, int(min(65535, float(exif["iso"]))), True))
    if exif.get("lens"):
        tags.append((42036, "s", 0, str(exif["lens"]), True))
    tags.append((50827, "s", 0, src.name, True))
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".dng.tmp")
    tifffile.imwrite(str(tmp), data, photometric=32803, compression="zlib" if compress else None, predictor=2 if compress else None,
                     extratags=tags, software="formlit", metadata=None)
    tmp.replace(dst)
    return True


def read_private(path: Path) -> dict:
    try:
        import tifffile
        with tifffile.TiffFile(str(path)) as tf:
            d = tf.pages[0].tags.get(270)
            if d is not None and isinstance(d.value, str) and d.value.startswith(TAG_PREFIX):
                return json.loads(d.value[len(TAG_PREFIX):])
    except Exception:
        return {}
    return {}
