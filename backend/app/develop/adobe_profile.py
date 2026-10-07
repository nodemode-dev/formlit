import re
import struct
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

import numpy as np

from app.develop import colour

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-:+=^!/*?`'|()[]{}@%$#"
DECODE = {c: i for i, c in enumerate(ALPHABET)}
CRS = "http://ns.adobe.com/camera-raw-settings/1.0/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
PRIMARIES = {0: "srgb", 1: "adobergb", 2: "prophoto", 3: "p3", 4: "rec2020"}
GAMMAS = {0: "linear", 1: "srgb", 2: 1.8, 3: 2.2, 4: "rec709"}


def _base85(text: str) -> bytes:
    out = bytearray()
    val, phase = 0, 0
    scale = (1, 85, 85 ** 2, 85 ** 3, 85 ** 4)
    for ch in text:
        if ch.isspace():
            continue
        if ch not in DECODE:
            raise ValueError("The profile's table holds a character outside its encoding")
        val += DECODE[ch] * scale[phase]
        phase += 1
        if phase == 5:
            if val > 0xFFFFFFFF:
                raise ValueError("The profile's table is not valid")
            out += struct.pack("<I", val)
            val, phase = 0, 0
    if phase == 1:
        raise ValueError("The profile's table is truncated")
    if phase:
        out += struct.pack("<I", val)[:phase - 1]
    return bytes(out)


def _alt(node: ET.Element, tag: str) -> str:
    n = node.find(f".//{{{CRS}}}{tag}/{{{RDF}}}Alt/{{{RDF}}}li")
    return (n.text or "").strip() if n is not None and n.text else ""


def is_profile(path: Path) -> bool:
    try:
        head = Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return "RGBTable" in head and "Table_" in head


def look_table_only(path: Path) -> bool:
    try:
        head = Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return "LookTable" in head and "Table_" in head and "RGBTable" not in head


def read(path: Path) -> dict:
    root = ET.parse(path).getroot()
    desc = None
    table = ""
    for d in root.iter(f"{{{RDF}}}Description"):
        digest = d.get(f"{{{CRS}}}RGBTable") or ""
        if re.fullmatch(r"[0-9a-fA-F]{32}", digest) and d.get(f"{{{CRS}}}Table_{digest}"):
            desc, table = d, d.get(f"{{{CRS}}}Table_{digest}") or ""
            break
    if desc is None:
        raise ValueError("This XMP is not a profile with a colour table (no crs:RGBTable)")
    data = _base85(table)
    if len(data) < 5:
        raise ValueError("The profile's table is empty")
    size = struct.unpack("<I", data[:4])[0]
    block = zlib.decompress(data[4:])
    if len(block) != size or size < 16:
        raise ValueError("The profile's table did not decompress to its stated size")
    _kind, _version, dims, n = struct.unpack("<4I", block[:16])
    if dims != 3:
        raise ValueError(f"Only three-dimensional profile tables are supported (this one is {dims}D)")
    if not 2 <= n <= 130 or len(block) < 16 + n ** 3 * 6:
        raise ValueError("The profile's table has an unexpected size")
    raw = np.frombuffer(block, "<u2", count=n ** 3 * 3, offset=16).reshape(n, n, n, 3).astype(np.int64)
    nop = (np.arange(n, dtype=np.int64) * 0xFFFF + n // 2) // (n - 1)
    base = np.stack(np.meshgrid(nop, nop, nop, indexing="ij"), axis=-1)
    rgb = ((raw + base) & 0xFFFF).astype(np.float32) / 65535.0
    tail = block[16 + n ** 3 * 6:]
    primaries, gamma, gamut, lo, hi = 0, 1, 0, 0.0, 2.0
    if len(tail) >= 12:
        primaries, gamma, gamut = struct.unpack("<3I", tail[:12])
    if len(tail) >= 28:
        lo, hi = struct.unpack("<2d", tail[12:28])
    name = _alt(desc, "Name") or Path(path).stem
    return {"name": name, "group": _alt(desc, "Group"), "table": rgb.transpose(2, 1, 0, 3).copy(), "primaries": PRIMARIES.get(primaries, "srgb"),
            "gamma": GAMMAS.get(gamma, "srgb"), "extend": gamut == 1, "amount": (lo, hi),
            "mono": str(desc.get(f"{{{CRS}}}ConvertToGrayscale", "")).lower() == "true"}


def _encode(v: np.ndarray, gamma) -> np.ndarray:
    v = np.clip(v, 0.0, 1.0)
    if gamma == "srgb":
        return colour.srgb_encode(v)
    if gamma == "linear":
        return v
    if gamma == "rec709":
        return np.where(v < 0.018, 4.5 * v, 1.099 * np.power(v, 0.45) - 0.099)
    return np.power(v, 1.0 / float(gamma))


def _decode(v: np.ndarray, gamma) -> np.ndarray:
    v = np.clip(v, 0.0, 1.0)
    if gamma == "srgb":
        return colour.srgb_decode(v)
    if gamma == "linear":
        return v
    if gamma == "rec709":
        return np.where(v < 0.081, v / 4.5, np.power((v + 0.099) / 1.099, 1 / 0.45))
    return np.power(v, float(gamma))


def _sample(table: np.ndarray, e: np.ndarray) -> np.ndarray:
    from app.develop.profiles import apply_lut
    return apply_lut(e.astype(np.float32), table)


def to_srgb(prof: dict, n: int = 33) -> np.ndarray:
    g = np.linspace(0.0, 1.0, n, dtype=np.float64)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")
    enc = np.stack([r, gg, b], axis=-1)
    sp = prof["primaries"]
    w = colour.SPACES[sp][4]
    to_t = colour.from_xyz(sp) @ colour.bradford(colour.D65, w) @ colour.to_xyz("srgb")
    from_t = np.linalg.inv(to_t)
    lin = colour.srgb_decode(enc).astype(np.float64) @ to_t.T
    mapped = _sample(prof["table"], _encode(lin, prof["gamma"]))
    out = _decode(mapped.astype(np.float64), prof["gamma"]) @ from_t.T
    return colour.srgb_encode(np.clip(out, 0.0, 1.0)).astype(np.float32)


def write_cube(prof: dict, dst_dir: Path) -> Path:
    stem = re.sub(r"[^A-Za-z0-9 ._-]+", "", prof["name"]).strip().replace(" ", "_")[:80] or "Profile"
    lut = to_srgb(prof)
    lines = [f'TITLE "{prof["name"]}"', f"LUT_3D_SIZE {lut.shape[0]}"]
    lines += [f"{px[0]:.6f} {px[1]:.6f} {px[2]:.6f}" for px in lut.reshape(-1, 3)]
    dst = dst_dir / f"{stem}.cube"
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dst
