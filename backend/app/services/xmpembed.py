import struct
from pathlib import Path

XMP_NS = b"http://ns.adobe.com/xap/1.0/\x00"
JPEG_EXT = {".jpg", ".jpeg", ".jpe"}
TIFF_EXT = {".tif", ".tiff", ".dng"}
TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 13: 4}


def supports(path: Path) -> bool:
    return path.suffix.lower() in JPEG_EXT | TIFF_EXT


def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".formlit-xmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def write_jpeg(path: Path, packet: bytes) -> None:
    data = path.read_bytes()
    if data[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG")
    body = XMP_NS + packet
    if len(body) + 2 > 65535:
        raise ValueError("XMP packet too large for one JPEG segment")
    out = bytearray(b"\xff\xd8")
    i, inserted = 2, False
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            break
        marker = data[i + 1]
        if marker in (0xD9, 0xDA):
            break
        length = struct.unpack(">H", data[i + 2:i + 4])[0]
        seg = data[i:i + 2 + length]
        is_xmp = marker == 0xE1 and seg[4:4 + len(XMP_NS)] == XMP_NS
        if not inserted and marker not in (0xE0, 0xE1):
            out += b"\xff\xe1" + struct.pack(">H", len(body) + 2) + body
            inserted = True
        if not is_xmp:
            out += seg
        i += 2 + length
    if not inserted:
        out += b"\xff\xe1" + struct.pack(">H", len(body) + 2) + body
    out += data[i:]
    _write_atomic(path, bytes(out))


def _ifd0(data: bytes) -> tuple[str, int]:
    if data[:4] == b"II*\x00":
        return "<", struct.unpack("<I", data[4:8])[0]
    if data[:4] == b"MM\x00*":
        return ">", struct.unpack(">I", data[4:8])[0]
    raise ValueError("not a classic TIFF")


def read_tiff(path: Path) -> str | None:
    try:
        with open(path, "rb") as f:
            head = f.read(8)
            e, off = _ifd0(head)
            f.seek(off)
            n = struct.unpack(e + "H", f.read(2))[0]
            entries = f.read(12 * n)
            for k in range(n):
                tag, typ, count, val = struct.unpack(e + "HHI4s", entries[12 * k:12 * k + 12])
                if tag == 700:
                    size = count * TYPE_SIZE.get(typ, 1)
                    if size <= 4:
                        raw = val[:size]
                    else:
                        f.seek(struct.unpack(e + "I", val)[0])
                        raw = f.read(size)
                    return raw.decode("utf-8", errors="replace")
    except (OSError, ValueError, struct.error):
        return None
    return None


def write_tiff(path: Path, packet: bytes) -> None:
    data = bytearray(path.read_bytes())
    e, off = _ifd0(bytes(data[:8]))
    n = struct.unpack(e + "H", data[off:off + 2])[0]
    entries = [bytes(data[off + 2 + 12 * k:off + 14 + 12 * k]) for k in range(n)]
    next_ifd = data[off + 2 + 12 * n:off + 6 + 12 * n]
    if len(data) % 2:
        data += b"\x00"
    at = len(data)
    data += packet
    if len(data) % 2:
        data += b"\x00"
    entry = struct.pack(e + "HHII", 700, 7, len(packet), at)
    tags = [struct.unpack(e + "H", x[:2])[0] for x in entries]
    if 700 in tags:
        k = tags.index(700)
        data[off + 2 + 12 * k:off + 14 + 12 * k] = entry
    else:
        entries.append(entry)
        entries.sort(key=lambda x: struct.unpack(e + "H", x[:2])[0])
        new_off = len(data)
        data += struct.pack(e + "H", len(entries)) + b"".join(entries) + next_ifd
        data[4:8] = struct.pack(e + "I", new_off)
    tmp = path.with_name(path.name + ".formlit-xmp")
    tmp.write_bytes(bytes(data))
    if read_tiff(tmp) != packet.decode("utf-8", errors="replace"):
        tmp.unlink(missing_ok=True)
        raise ValueError("XMP did not read back")
    tmp.replace(path)


def write(path: Path, packet: str) -> None:
    raw = packet.encode("utf-8")
    if path.suffix.lower() in JPEG_EXT:
        write_jpeg(path, raw)
    elif path.suffix.lower() in TIFF_EXT:
        write_tiff(path, raw)
    else:
        raise ValueError("this format keeps metadata in a sidecar")
