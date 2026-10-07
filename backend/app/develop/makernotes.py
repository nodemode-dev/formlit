import struct

HEAD = 4 * 1024 * 1024
SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 13: 4}

C = "fl.camera."
CANON = {0x81: "standard", 0x82: "portrait", 0x83: "landscape", 0x84: "neutral", 0x85: "canon.faithful", 0x86: "monochrome", 0x87: "standard",
         0x88: "canon.finedetail", 0x01: "standard", 0x02: "portrait", 0x03: "vivid", 0x05: "neutral"}
NIKON = {"STANDARD": "standard", "AUTO": "standard", "NEUTRAL": "neutral", "VIVID": "vivid", "MONOCHROME": "monochrome", "PORTRAIT": "portrait",
         "LANDSCAPE": "landscape", "FLAT": "nikon.flat", "FLAT MONOCHROME": "monochrome", "DEEP TONE MONO": "monochrome", "RICH TONE PORTRAIT": "portrait"}
SONY = {"standard": "standard", "vivid": "vivid", "neutral": "neutral", "clear": "sony.clear", "deep": "sony.deep", "light": "sony.light",
        "portrait": "portrait", "landscape": "landscape", "sunset": "sony.sunset", "nightview": "sony.night", "night": "sony.night",
        "nightscene": "sony.night", "autumn": "sony.autumn", "autumnleaves": "sony.autumn", "bw": "monochrome", "b&w": "monochrome", "sepia": "sepia"}
FUJI_FILM = {0x000: "standard", 0x200: "fujifilm.velvia", 0x400: "fujifilm.velvia", 0x120: "fujifilm.astia", 0x500: "fujifilm.pronegstd",
             0x501: "fujifilm.proneghi", 0x600: "fujifilm.classicchrome", 0x700: "fujifilm.eterna", 0x800: "fujifilm.classicneg",
             0x900: "fujifilm.bleachbypass", 0xA00: "fujifilm.nostalgicneg", 0xB00: "fujifilm.realaace"}
FUJI_MONO = {0x300: "monochrome", 0x301: "monochrome", 0x302: "monochrome", 0x303: "monochrome", 0x310: "sepia", 0x500: "fujifilm.acros",
             0x501: "fujifilm.acrosr", 0x502: "fujifilm.acrosye", 0x503: "fujifilm.acrosg"}
PANASONIC = {0: "standard", 1: "standard", 2: "vivid", 3: "panasonic.natural", 4: "monochrome", 5: "landscape", 6: "portrait", 8: "panasonic.cineliked",
             9: "panasonic.cinelikev", 11: "panasonic.lmonochrome", 15: "panasonic.lmonochrome", 18: "panasonic.cineliked"}
OLYMPUS = {1: "vivid", 2: "olympus.natural", 3: "olympus.muted", 4: "portrait", 5: "olympus.ienhance", 256: "monochrome", 512: "sepia"}
PENTAX = {0: "pentax.natural", 1: "pentax.bright", 2: "portrait", 3: "landscape", 4: "pentax.vibrant", 5: "monochrome", 6: "pentax.muted",
          7: "pentax.reversal", 8: "pentax.bleachbypass", 9: "pentax.radiant", 10: "pentax.cross", 11: "pentax.flat"}


class Tiff:
    def __init__(self, buf: bytes, start: int = 0) -> None:
        self.buf = buf
        self.start = start
        self.end = "<" if buf[start:start + 2] == b"II" else ">"

    def u16(self, off: int) -> int:
        return struct.unpack_from(self.end + "H", self.buf, off)[0]

    def u32(self, off: int) -> int:
        return struct.unpack_from(self.end + "I", self.buf, off)[0]

    def ifd(self, at: int, base: int | None = None) -> dict:
        base = self.start if base is None else base
        out: dict = {}
        if at < 0 or at + 2 > len(self.buf):
            return out
        n = self.u16(at)
        if n > 1000 or at + 2 + 12 * n > len(self.buf):
            return out
        for i in range(n):
            e = at + 2 + 12 * i
            tag, typ, count = struct.unpack_from(self.end + "HHI", self.buf, e)
            size = SIZES.get(typ, 1) * count
            off = e + 8 if size <= 4 else base + self.u32(e + 8)
            if 0 <= off and off + size <= len(self.buf):
                out[tag] = (typ, count, off, size)
        return out

    def raw(self, entry) -> bytes:
        return self.buf[entry[2]:entry[2] + entry[3]]

    def ints(self, entry) -> list[int]:
        typ, count, off, _ = entry
        fmt = {3: "H", 8: "h", 4: "I", 9: "i", 13: "I", 1: "B", 7: "B", 6: "b"}.get(typ)
        return list(struct.unpack_from(self.end + fmt * count, self.buf, off)) if fmt else []

    def text(self, entry) -> str:
        return self.raw(entry).split(b"\0")[0].decode("latin-1").strip()

    def main(self) -> dict:
        return self.ifd(self.start + self.u32(self.start + 4))


def _makernote(t: Tiff) -> tuple[int, int] | None:
    exif = t.main().get(0x8769)
    if exif is None:
        return None
    note = t.ifd(t.start + t.ints(exif)[0]).get(0x927C)
    return (note[2], note[3]) if note else None


def _canon(t: Tiff, at: int, base: int) -> str | None:
    info = t.ifd(at, base).get(0x00A0)
    vals = t.ints(info) if info else []
    return CANON.get(vals[10]) if len(vals) > 10 else None


def _cr3(buf: bytes) -> str | None:
    i = buf.find(b"CMT3")
    if i < 4:
        return None
    start = i + 4
    if buf[start:start + 2] not in (b"II", b"MM"):
        return None
    t = Tiff(buf, start)
    return _canon(t, start + t.u32(start + 4), start)


def _from_tiff(t: Tiff) -> str | None:
    found = _makernote(t)
    if found is None:
        return None
    mn, _size = found
    head = t.buf[mn:mn + 16]
    make_tag = t.main().get(0x010F)
    make = t.text(make_tag).lower() if make_tag else ""
    if head.startswith(b"Nikon\0"):
        inner = Tiff(t.buf, mn + 10)
        data = inner.ifd(mn + 10 + inner.u32(mn + 14)).get(0x0023)
        if data is None:
            return None
        blob = inner.raw(data)
        at = 8 if blob[:2] >= b"03" else 4
        name = blob[at + 20:at + 40].split(b"\0")[0].decode("latin-1").strip() or blob[at:at + 20].split(b"\0")[0].decode("latin-1").strip()
        return NIKON.get(name.upper())
    if make.startswith("sony"):
        at = mn + 12 if head.startswith(b"SONY") else mn
        style = t.ifd(at).get(0xB020)
        return SONY.get(t.text(style).lower().replace(" ", "")) if style else None
    if head.startswith(b"OLYMPUS\0") or head.startswith(b"OM SYSTEM\0"):
        inner = Tiff(t.buf, mn + (8 if head.startswith(b"OLYMPUS") else 12))
        at = mn + (12 if head.startswith(b"OLYMPUS") else 16)
        sub = inner.ifd(at, mn).get(0x2020)
        if sub is None:
            return None
        mode = inner.ifd(mn + inner.ints(sub)[0], mn).get(0x0520) if inner.ints(sub) else None
        vals = inner.ints(mode) if mode else []
        return OLYMPUS.get(vals[0]) if vals else None
    if head.startswith(b"PENTAX \0") or head.startswith(b"AOC\0"):
        rel = head.startswith(b"PENTAX")
        inner = Tiff(t.buf, mn + (8 if rel else 4))
        tone = inner.ifd(mn + (10 if rel else 6), mn if rel else t.start).get(0x004F)
        vals = inner.ints(tone) if tone else []
        return PENTAX.get(vals[0]) if vals else None
    if head.startswith(b"Panasonic\0"):
        style = t.ifd(mn + 12).get(0x0089)
        vals = t.ints(style) if style else []
        return PANASONIC.get(vals[0]) if vals else None
    if head.startswith(b"FUJIFILM"):
        return _fuji(t.buf, mn)
    if make.startswith("canon"):
        return _canon(t, mn, t.start)
    return None


def _fuji(buf: bytes, mn: int) -> str | None:
    inner = Tiff(buf, 0)
    inner.end = "<"
    tags = inner.ifd(mn + struct.unpack_from("<I", buf, mn + 8)[0], mn)
    film = tags.get(0x1401)
    if film is not None:
        return FUJI_FILM.get(inner.ints(film)[0])
    sat = tags.get(0x1003)
    return FUJI_MONO.get(inner.ints(sat)[0]) if sat is not None else None


def _embedded(buf: bytes) -> str | None:
    t = Tiff(buf, 0)
    jpeg = t.main().get(0x002E)
    return _exif_in(t.raw(jpeg)) if jpeg else None


def _raf(buf: bytes) -> str | None:
    jo, jl = struct.unpack_from(">II", buf, 84)
    return _exif_in(buf[jo:jo + jl])


def _exif_in(jpeg: bytes) -> str | None:
    i = jpeg.find(b"Exif\0\0")
    if i < 0:
        return None
    return _from_tiff(Tiff(jpeg, i + 6))


def _box(buf: bytes, name: bytes) -> bytes | None:
    i = buf.find(name)
    if i < 4:
        return None
    size = struct.unpack_from(">I", buf, i - 4)[0]
    return buf[i + 4:i - 4 + size] if 8 < size <= len(buf) - i + 4 else None


def container_exif(path) -> dict:
    import io

    import exifread
    from exifread.tags.exif import GPS_TAGS
    try:
        with open(path, "rb") as f:
            buf = f.read(HEAD)
    except OSError:
        return {}
    try:
        if buf.startswith(b"FUJIFILMCCD-RAW"):
            jo, jl = struct.unpack_from(">II", buf, 84)
            return dict(exifread.process_file(io.BytesIO(buf[jo:jo + jl]), details=False))
        if not (buf[4:8] == b"ftyp" and b"crx " in buf[:32]):
            return {}
        tags: dict = {}
        for name, group in ((b"CMT1", "Image"), (b"CMT2", "EXIF"), (b"CMT4", "GPS")):
            blob = _box(buf, name)
            if not blob:
                continue
            for key, value in exifread.process_file(io.BytesIO(blob), details=False).items():
                if not key.startswith("Image "):
                    continue
                label = key[6:]
                if group == "GPS":
                    known = GPS_TAGS.get(getattr(value, "tag", -1))
                    label = known[0] if known else label
                tags[f"{group} {label}"] = value
        return tags
    except (struct.error, ValueError, KeyError, IndexError):
        return {}


def picture_style(path) -> str | None:
    try:
        with open(path, "rb") as f:
            buf = f.read(HEAD)
    except OSError:
        return None
    try:
        if buf.startswith(b"FUJIFILMCCD-RAW"):
            style = _raf(buf)
        elif buf[4:8] == b"ftyp" and b"crx " in buf[:32]:
            style = _cr3(buf)
        elif buf[:4] == b"IIU\0":
            style = _embedded(buf)
        elif buf[:2] in (b"II", b"MM"):
            style = _from_tiff(Tiff(buf, 0))
        else:
            style = None
    except (struct.error, IndexError, ValueError):
        return None
    return C + style if style else None
