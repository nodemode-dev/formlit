import io
import struct
import zlib
from datetime import datetime

import cv2
import numpy as np
from PIL import ExifTags, Image

from app.develop.output import icc_profile, to_u8, to_u16
from app.services import metadata

FORMATS = {
    "jpeg": {"ext": "jpg", "label": "JPEG", "depths": [8], "quality": True},
    "png": {"ext": "png", "label": "PNG", "depths": [8, 16], "quality": False},
    "tiff": {"ext": "tif", "label": "TIFF", "depths": [8, 16], "quality": False},
    "psd": {"ext": "psd", "label": "PSD", "depths": [8, 16], "quality": False},
    "webp": {"ext": "webp", "label": "WebP", "depths": [8], "quality": True},
    "avif": {"ext": "avif", "label": "AVIF", "depths": [8], "quality": True},
    "heic": {"ext": "heic", "label": "HEIC", "depths": [8], "quality": True},
    "dng": {"ext": "dng", "label": "DNG", "depths": [16], "quality": False},
    "original": {"ext": "", "label": "Original", "depths": [], "quality": False},
}
SPACES = {"srgb": "sRGB", "p3": "Display P3", "adobergb": "Adobe RGB (1998)", "prophoto": "ProPhoto RGB", "rec2020": "Rec. 2020"}
METADATA = {"none": "None", "copyright": "Copyright Only", "contact": "Copyright and Contact Info Only",
            "noCamera": "All Except Camera and Camera Raw Info", "noRaw": "All Except Camera Raw Info", "all": "All Metadata"}
CONTACT = ("creator", "creatorJob", "creatorAddress", "creatorCity", "creatorState", "creatorCountry", "creatorEmail", "creatorPhone", "creatorUrl")
LOCATION = ("location", "city", "state", "country", "isoCountryCode", "sublocation")


def _dms(v: float) -> tuple[float, float, float]:
    v = abs(v)
    d = int(v)
    m = int((v - d) * 60)
    return float(d), float(m), round((v - d - m / 60) * 3600, 4)


def filtered(rec: dict, mode: str, remove_person: bool, remove_location: bool, export_keywords: dict | None = None) -> dict:
    meta = dict(rec.get("meta") or {})
    out: dict = {"fileName": rec.get("fileName"), "rating": 0, "label": "", "meta": {}, "keywords": []}
    if mode == "none":
        return out
    keep = {"copyright", "copyrightStatus", "rightsUsage", "copyrightUrl"}
    if mode != "copyright":
        keep |= set(CONTACT)
    if mode in ("noCamera", "noRaw", "all"):
        keep |= set(meta)
        out.update(rating=rec.get("rating", 0), label=rec.get("label") or "", captureTime=rec.get("captureTime"))
        kws = rec.get("keywords") or []
        kw = export_keywords or {}
        if kw.get("only") is not None:
            kws = [k for k in kws if k in kw["only"]]
        if remove_person:
            kws = [k for k in kws if not k.startswith("People|")]
        out["keywords"] = kws
        out["subjects"] = sorted({t for k in kws for t in (kw.get("extras") or {}).get(k, [])})
    if remove_person:
        keep.discard("personShown")
    if remove_location:
        keep -= set(LOCATION)
    out["meta"] = {k: v for k, v in meta.items() if k in keep and v not in (None, "")}
    if mode in ("noRaw", "all"):
        for k in ("camera", "lens", "focal", "aperture", "shutter", "iso", "bias", "flash"):
            out[k] = rec.get(k)
        if not remove_location and rec.get("gpsLat") is not None:
            out.update(gpsLat=rec["gpsLat"], gpsLon=rec["gpsLon"], gpsAlt=rec.get("gpsAlt"))
        exif = rec.get("exif") or {}
        out["make"] = exif.get("make") or exif.get("Make") or ""
    if mode == "all" and rec.get("develop"):
        import json
        out["develop"] = json.dumps(rec["develop"], separators=(",", ":"))
    return out


def exif_bytes(r: dict, w: int, h: int, ppi: int) -> bytes:
    ex = Image.Exif()
    ex[0x0131] = "formlit"
    ex[0x0132] = datetime.now().strftime("%Y:%m:%d %H:%M:%S")
    ex[0x0112] = 1
    meta = r.get("meta") or {}
    if meta.get("copyright"):
        ex[0x8298] = str(meta["copyright"])
    if meta.get("creator"):
        ex[0x013B] = str(meta["creator"])
    if meta.get("caption"):
        ex[0x010E] = str(meta["caption"])
    if r.get("make"):
        ex[0x010F] = str(r["make"])
    if r.get("camera"):
        ex[0x0110] = str(r["camera"])
    sub: dict = {0xA002: int(w), 0xA003: int(h)}
    ct = r.get("captureTime")
    if ct:
        try:
            sub[0x9003] = datetime.fromisoformat(ct[:19]).strftime("%Y:%m:%d %H:%M:%S")
        except ValueError:
            pass
    for key, tag in (("shutter", 0x829A), ("aperture", 0x829D), ("focal", 0x920A), ("bias", 0x9204)):
        if r.get(key) is not None:
            sub[tag] = float(r[key])
    if r.get("iso"):
        sub[0x8827] = int(r["iso"])
    if r.get("lens"):
        sub[0xA434] = str(r["lens"])
    if len(sub) > 2 or ct:
        ex[ExifTags.IFD.Exif] = sub
    if r.get("gpsLat") is not None and r.get("gpsLon") is not None:
        gps = {0: b"\x02\x03\x00\x00", 1: "N" if r["gpsLat"] >= 0 else "S", 2: _dms(r["gpsLat"]), 3: "E" if r["gpsLon"] >= 0 else "W", 4: _dms(r["gpsLon"])}
        if r.get("gpsAlt") is not None:
            gps[5] = b"\x00" if r["gpsAlt"] >= 0 else b"\x01"
            gps[6] = abs(float(r["gpsAlt"]))
        ex[ExifTags.IFD.GPSInfo] = gps
    return ex.tobytes()


def xmp_packet(r: dict) -> bytes:
    text = metadata.build_xmp(r)
    extra = []
    for key, tag in (("make", "tiff:Make"), ("camera", "tiff:Model"), ("iso", "exif:ISOSpeedRatings"), ("aperture", "exif:FNumber"),
                     ("shutter", "exif:ExposureTime"), ("focal", "exif:FocalLength")):
        v = r.get(key)
        if v not in (None, ""):
            extra.append(f'{tag}="{metadata._esc(str(v))}"')
    if r.get("gpsLat") is not None and r.get("gpsLon") is not None:
        extra.append(f'exif:GPSLatitude="{abs(r["gpsLat"]):.7f}{"N" if r["gpsLat"] >= 0 else "S"}"')
        extra.append(f'exif:GPSLongitude="{abs(r["gpsLon"]):.7f}{"E" if r["gpsLon"] >= 0 else "W"}"')
    if extra:
        text = text.replace('xmp:CreatorTool="formlit"', 'xmp:CreatorTool="formlit" ' + " ".join(extra), 1)
    return text.encode("utf-8")


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _png(arr: np.ndarray, icc: bytes, xmp: bytes | None, ppi: int, exif: bytes | None) -> bytes:
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".png", bgr, [cv2.IMWRITE_PNG_COMPRESSION, 6])
    if not ok:
        raise ValueError("PNG encoding failed")
    data = buf.tobytes()
    head, rest = data[:33], data[33:]
    extra = _chunk(b"iCCP", b"formlit\0\0" + zlib.compress(icc))
    ppm = int(round(ppi / 0.0254))
    extra += _chunk(b"pHYs", struct.pack(">IIB", ppm, ppm, 1))
    if exif:
        extra += _chunk(b"eXIf", exif[6:] if exif.startswith(b"Exif\0\0") else exif)
    if xmp:
        extra += _chunk(b"iTXt", b"XML:com.adobe.xmp\0\0\0\0\0" + xmp)
    return head + extra + rest


def _tiff(arr: np.ndarray, icc: bytes, xmp: bytes | None, ppi: int, r: dict, compression: str) -> bytes:
    import tifffile
    meta = r.get("meta") or {}
    tags = []
    if xmp:
        tags.append((700, 1, len(xmp), xmp, False))
    if meta.get("copyright"):
        tags.append((33432, 2, 0, str(meta["copyright"]), False))
    if meta.get("creator"):
        tags.append((315, 2, 0, str(meta["creator"]), False))
    buf = io.BytesIO()
    tifffile.imwrite(buf, arr, photometric="rgb", compression="zlib" if compression == "zip" else None, iccprofile=icc,
                     resolution=(float(ppi), float(ppi)), resolutionunit="INCH", software="formlit", metadata=None,
                     description=str(meta.get("caption") or "") or None, extratags=tags)
    return buf.getvalue()


def _psd(arr: np.ndarray, icc: bytes, xmp: bytes | None, ppi: int) -> bytes:
    h, w = arr.shape[:2]
    if max(h, w) > 30000:
        raise ValueError("PSD is limited to 30,000 pixels on a side")
    depth = 16 if arr.dtype == np.uint16 else 8

    def res(rid: int, data: bytes) -> bytes:
        return b"8BIM" + struct.pack(">H", rid) + b"\0\0" + struct.pack(">I", len(data)) + data + (b"\0" if len(data) % 2 else b"")
    fixed = struct.pack(">IHHIHH", int(ppi * 65536), 1, 1, int(ppi * 65536), 1, 1)
    block = res(1005, fixed) + res(1039, icc) + (res(1060, xmp) if xmp else b"")
    head = b"8BPS" + struct.pack(">H", 1) + b"\0" * 6 + struct.pack(">HIIHH", 3, h, w, depth, 3)
    planes = np.ascontiguousarray(np.moveaxis(arr[..., :3], -1, 0)).astype(">u2" if depth == 16 else np.uint8).tobytes()
    return head + struct.pack(">I", 0) + struct.pack(">I", len(block)) + block + struct.pack(">I", 0) + struct.pack(">H", 0) + planes


def _pil(arr: np.ndarray, fmt: str, quality: int, icc: bytes, exif: bytes | None, xmp: bytes | None, ppi: int) -> bytes:
    im = Image.fromarray(arr, "RGB")
    buf = io.BytesIO()
    kw: dict = {"icc_profile": icc}
    if exif:
        kw["exif"] = exif
    if xmp:
        kw["xmp"] = xmp
    if fmt == "jpeg":
        im.save(buf, "JPEG", quality=int(quality), optimize=True, progressive=True, subsampling=0 if quality >= 90 else 2, dpi=(ppi, ppi), **kw)
    elif fmt == "webp":
        im.save(buf, "WEBP", quality=int(quality), method=4, **kw)
    elif fmt == "avif":
        im.save(buf, "AVIF", quality=int(quality), **kw)
    elif fmt == "heic":
        import pillow_heif
        pillow_heif.register_heif_opener()
        kw.pop("xmp", None)
        im.save(buf, "HEIF", quality=int(quality), **kw)
    else:
        raise ValueError(f"Unknown format {fmt}")
    return buf.getvalue()


def encode(out: np.ndarray, fmt: str, space: str, quality: int = 85, depth: int = 8, ppi: int = 240, rec: dict | None = None,
           compression: str = "none", limit_kb: int = 0) -> bytes:
    r = rec or {}
    if space.startswith("icc:"):
        with open(space[4:], "rb") as fh:
            icc = fh.read()
    else:
        icc = icc_profile(space)
    h, w = out.shape[:2]
    has_meta = bool(r.get("meta") or r.get("keywords") or r.get("camera") or r.get("captureTime"))
    exif = exif_bytes(r, w, h, ppi)
    xmp = xmp_packet(r) if has_meta else None
    if fmt in ("png", "tiff", "psd"):
        arr = to_u16(out) if depth == 16 else to_u8(out)
        if fmt == "psd":
            return _psd(arr, icc, xmp, ppi)
        return _png(arr, icc, xmp, ppi, exif) if fmt == "png" else _tiff(arr, icc, xmp, ppi, r, compression)
    arr = to_u8(out)
    data = _pil(arr, fmt, quality, icc, exif, xmp, ppi)
    if limit_kb and fmt in ("jpeg", "webp", "avif", "heic") and len(data) > limit_kb * 1024:
        lo, hi, best = 5, int(quality) - 1, None
        while lo <= hi:
            mid = (lo + hi) // 2
            d = _pil(arr, fmt, mid, icc, exif, xmp, ppi)
            if len(d) <= limit_kb * 1024:
                best, lo = d, mid + 1
            else:
                hi = mid - 1
        data = best or _pil(arr, fmt, 5, icc, exif, xmp, ppi)
    return data
