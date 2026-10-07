import struct
from functools import lru_cache

import numpy as np

from app.develop import colour

NAMES = {
    "srgb": "sRGB IEC61966-2.1 (formlit)",
    "p3": "Display P3 (formlit)",
    "rec2020": "Rec. 2020 (formlit)",
    "adobergb": "Compatible with Adobe RGB (1998) (formlit)",
    "prophoto": "ProPhoto RGB (formlit)",
    "linear": "Linear Rec. 2020 (formlit)",
}
D50_XYZ = (0.9642, 1.0, 0.8249)
COPYRIGHT = "No copyright, use freely"
CREATED = (2026, 1, 1, 0, 0, 0)
TRC_N = 1024
GAMMA_U8F8 = {"adobergb": 563, "prophoto": 461}


def _s15(v: float) -> bytes:
    return struct.pack(">i", int(round(v * 65536.0)))


def _xyz_tag(xyz) -> bytes:
    return b"XYZ \0\0\0\0" + b"".join(_s15(float(c)) for c in xyz)


def _text_tag(text: str) -> bytes:
    return b"text\0\0\0\0" + text.encode("ascii") + b"\0"


def _desc_tag(text: str) -> bytes:
    raw = text.encode("ascii") + b"\0"
    return b"desc\0\0\0\0" + struct.pack(">I", len(raw)) + raw + struct.pack(">II", 0, 0) + struct.pack(">HB", 0, 0) + bytes(67)


def _curve_tag(space: str) -> bytes:
    if space == "linear":
        return b"curv\0\0\0\0" + struct.pack(">I", 0)
    if space in GAMMA_U8F8:
        return b"curv\0\0\0\0" + struct.pack(">IH", 1, GAMMA_U8F8[space])
    table = colour.srgb_decode(np.linspace(0.0, 1.0, TRC_N)).astype(np.float64)
    codes = np.clip(np.floor(table * 65535.0 + 0.5), 0, 65535).astype(">u2")
    return b"curv\0\0\0\0" + struct.pack(">I", TRC_N) + codes.tobytes()


def _colorants(space: str) -> np.ndarray:
    sp = "rec2020" if space == "linear" else space
    pcs = np.asarray(D50_XYZ, np.float64)
    pcs_xy = (pcs[0] / pcs.sum(), pcs[1] / pcs.sum())
    return colour.bradford(colour.SPACES[sp][4], pcs_xy) @ colour.to_xyz(sp)


def _pad(b: bytes) -> bytes:
    return b + bytes(-len(b) % 4)


@lru_cache(maxsize=8)
def icc_profile(space: str) -> bytes:
    name = NAMES[space]
    cols = _colorants(space)
    trc = _curve_tag(space)
    tags = [(b"desc", _desc_tag(name)), (b"cprt", _text_tag(COPYRIGHT)), (b"wtpt", _xyz_tag(D50_XYZ)),
            (b"rXYZ", _xyz_tag(cols[:, 0])), (b"gXYZ", _xyz_tag(cols[:, 1])), (b"bXYZ", _xyz_tag(cols[:, 2])),
            (b"rTRC", trc), (b"gTRC", trc), (b"bTRC", trc)]
    offset = 128 + 4 + 12 * len(tags)
    table, data, placed = [], b"", {}
    for sig, body in tags:
        if body not in placed:
            placed[body] = offset + len(data)
            data += _pad(body)
        table.append(struct.pack(">4sII", sig, placed[body], len(body)))
    size = offset + len(data)
    header = (struct.pack(">I", size) + bytes(4) + bytes([2, 0x40, 0, 0]) + b"mntr" + b"RGB " + b"XYZ " + struct.pack(">6H", *CREATED) + b"acsp"
              + bytes(4) + struct.pack(">I", 0) + bytes(4) + bytes(4) + bytes(8) + struct.pack(">I", 0) + b"".join(_s15(c) for c in D50_XYZ)
              + bytes(4) + bytes(44))
    return header + struct.pack(">I", len(tags)) + b"".join(table) + data


def to_u8(e: np.ndarray) -> np.ndarray:
    return np.floor(np.clip(e, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def to_u16(e: np.ndarray) -> np.ndarray:
    return np.floor(np.clip(e, 0.0, 1.0) * 65535.0 + 0.5).astype(np.uint16)
