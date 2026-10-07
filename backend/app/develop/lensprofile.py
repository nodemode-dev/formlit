import struct
from pathlib import Path

OPCODE_TAGS = (51008, 51009, 51022)


def _parse(blob: bytes) -> dict:
    out: dict = {}
    if len(blob) < 4:
        return out
    (count,) = struct.unpack(">I", blob[:4])
    pos = 4
    for _ in range(count):
        if pos + 16 > len(blob):
            break
        oid, _ver, _flags, size = struct.unpack(">IIII", blob[pos:pos + 16])
        params = blob[pos + 16:pos + 16 + size]
        pos += 16 + size
        if oid == 1 and len(params) >= 4:
            (planes,) = struct.unpack(">I", params[:4])
            need = 4 + planes * 48 + 16
            if len(params) >= need:
                coef = struct.unpack(">" + "d" * (planes * 6), params[4:4 + planes * 48])
                cx, cy = struct.unpack(">dd", params[4 + planes * 48:need])
                out["warp"] = {"kr": [float(v) for v in coef[0:4]], "kt": [float(v) for v in coef[4:6]], "cx": float(cx), "cy": float(cy)}
        elif oid == 3 and len(params) >= 56:
            vals = struct.unpack(">ddddddd", params[:56])
            out["vignette"] = {"k": [float(v) for v in vals[:5]], "cx": float(vals[5]), "cy": float(vals[6])}
    return out


def read(path: Path) -> dict | None:
    if path.suffix.lower() != ".dng":
        return None
    try:
        import tifffile
        from tifffile import TiffPage
        found: dict = {}
        with tifffile.TiffFile(str(path)) as t:
            pages = [t.pages[0]]
            sub = t.pages[0].tags.get(330)
            for off in (sub.value if sub is not None else []):
                t.filehandle.seek(off)
                pages.append(TiffPage(t, index=0))
            for page in pages:
                for code in OPCODE_TAGS:
                    tag = page.tags.get(code)
                    if tag is not None and isinstance(tag.value, (bytes, bytearray)):
                        for k, v in _parse(bytes(tag.value)).items():
                            found.setdefault(k, v)
        return found or None
    except Exception:
        return None
