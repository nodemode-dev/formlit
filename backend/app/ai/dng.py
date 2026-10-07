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
