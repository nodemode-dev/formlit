import copy
import io
import struct

import cv2
import numpy as np
from PIL import Image

from app.develop.output import icc_profile, to_u8

HDRGM = "http://ns.adobe.com/hdr-gain-map/1.0/"
OFFSET = 1.0 / 64.0


def _decode(e: np.ndarray) -> np.ndarray:
    e = np.clip(e, 0.0, 1.0)
    return np.where(e <= 0.04045, e / 12.92, np.power((e + 0.055) / 1.055, 2.4))


def _luma(lin: np.ndarray) -> np.ndarray:
    return lin @ np.array([0.2126, 0.7152, 0.0722], np.float32)


def gain_from(sdr: np.ndarray, under: np.ndarray, stops: float) -> np.ndarray:
    lin_sdr = _decode(sdr)
    lin_hdr = _decode(under) * (2.0 ** stops)
    y_sdr = _luma(lin_sdr)
    y_hdr = _luma(lin_hdr)
    ratio = np.clip((y_hdr + OFFSET) / (y_sdr + OFFSET), 1.0, 2.0 ** stops)
    peak = sdr.max(axis=-1)
    w = np.clip((peak - 0.55) / 0.4, 0.0, 1.0)
    w = w * w * (3.0 - 2.0 * w)
    g = np.log2(1.0 + w * (ratio - 1.0))
    return cv2.GaussianBlur(g.astype(np.float32), (0, 0), max(1.0, max(g.shape) / 1200.0))


def render_pair(pid: int, size: dict, dev: dict, stops: float) -> tuple[np.ndarray, np.ndarray]:
    from app.output import export
    sdr = export.render_photo(pid, size, "srgb", dev)
    lo = copy.deepcopy(dev or {})
    light = lo.setdefault("light", {})
    light["exposure"] = float(light.get("exposure", 0)) - stops
    under = export.render_photo(pid, size, "srgb", lo)
    if under.shape != sdr.shape:
        under = cv2.resize(under, (sdr.shape[1], sdr.shape[0]), interpolation=cv2.INTER_AREA)
    return sdr, gain_from(sdr, under, stops)


def _segments(jpeg: bytes) -> list[tuple[int, bytes]]:
    assert jpeg[:2] == b"\xff\xd8"
    out = []
    i = 2
    while i < len(jpeg):
        if jpeg[i] != 0xFF:
            raise ValueError("Bad JPEG marker")
        m = jpeg[i + 1]
        if m == 0xDA:
            out.append((-1, jpeg[i:]))
            break
        n = struct.unpack(">H", jpeg[i + 2:i + 4])[0]
        out.append((m, jpeg[i:i + 2 + n]))
        i += 2 + n
    return out


def _app(marker: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker]) + struct.pack(">H", len(payload) + 2) + payload


def _xmp(body: str) -> bytes:
    pkt = ('<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?><x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
           f'{body}</rdf:RDF></x:xmpmeta><?xpacket end="w"?>')
    return b"http://ns.adobe.com/xap/1.0/\x00" + pkt.encode("utf-8")


def _primary_xmp(gain_len: int) -> bytes:
    return _xmp(f'<rdf:Description rdf:about="" xmlns:Container="http://ns.google.com/photos/1.0/container/" xmlns:Item="http://ns.google.com/photos/1.0/container/item/" '
                f'xmlns:hdrgm="{HDRGM}" hdrgm:Version="1.0"><Container:Directory><rdf:Seq>'
                '<rdf:li rdf:parseType="Resource"><Container:Item Item:Semantic="Primary" Item:Mime="image/jpeg"/></rdf:li>'
                f'<rdf:li rdf:parseType="Resource"><Container:Item Item:Semantic="GainMap" Item:Mime="image/jpeg" Item:Length="{gain_len}"/></rdf:li>'
                '</rdf:Seq></Container:Directory></rdf:Description>')


def _gain_xmp(lo: float, hi: float) -> bytes:
    return _xmp(f'<rdf:Description rdf:about="" xmlns:hdrgm="{HDRGM}" hdrgm:Version="1.0" hdrgm:GainMapMin="{lo:.4f}" hdrgm:GainMapMax="{hi:.4f}" hdrgm:Gamma="1" '
                f'hdrgm:OffsetSDR="{OFFSET:.6f}" hdrgm:OffsetHDR="{OFFSET:.6f}" hdrgm:HDRCapacityMin="0" hdrgm:HDRCapacityMax="{hi:.4f}" hdrgm:BaseRenditionIsHDR="False"/>')


def _mpf(primary_size: int, gain_size: int, gain_offset: int) -> bytes:
    entries = 3
    ifd_len = 2 + entries * 12 + 4
    data_off = 8 + ifd_len
    hdr = b"II*\x00" + struct.pack("<I", 8)
    ifd = struct.pack("<H", entries)
    ifd += struct.pack("<HHI", 0xB000, 7, 4) + b"0100"
    ifd += struct.pack("<HHII", 0xB001, 4, 1, 2)
    ifd += struct.pack("<HHII", 0xB002, 7, 32, data_off)
    ifd += struct.pack("<I", 0)
    mp = struct.pack("<IIIHH", 0x20030000, primary_size, 0, 0, 0) + struct.pack("<IIIHH", 0, gain_size, gain_offset, 0, 0)
    return b"MPF\x00" + hdr + ifd + mp


def ultrahdr(sdr: np.ndarray, log_gain: np.ndarray, quality: int = 90, ppi: int = 240, exif: bytes | None = None, extra_xmp: str = "") -> bytes:
    hi = max(float(np.percentile(log_gain, 99.9)), 0.05)
    lo = 0.0
    rec = np.clip((log_gain - lo) / (hi - lo), 0.0, 1.0)
    gh, gw = max(1, sdr.shape[0] // 4), max(1, sdr.shape[1] // 4)
    small = cv2.resize(rec, (gw, gh), interpolation=cv2.INTER_AREA)
    gbuf = io.BytesIO()
    Image.fromarray((small * 255.0 + 0.5).astype(np.uint8), "L").save(gbuf, "JPEG", quality=85)
    gsegs = _segments(gbuf.getvalue())
    gain = b"\xff\xd8" + _app(0xE1, _gain_xmp(lo, hi)) + b"".join(s for _, s in gsegs)
    pbuf = io.BytesIO()
    kw: dict = {"icc_profile": icc_profile("srgb")}
    if exif:
        kw["exif"] = exif
    Image.fromarray(to_u8(sdr), "RGB").save(pbuf, "JPEG", quality=int(quality), subsampling=0 if quality >= 90 else 2, dpi=(ppi, ppi), **kw)
    segs = [s for s in _segments(pbuf.getvalue()) if not (s[0] == 0xE1 and s[1][4:33].startswith(b"http://ns.adobe.com/xap/1.0/"))]
    head = [s for m, s in segs if m in (0xE0, 0xE1)]
    rest = [s for m, s in segs if m not in (0xE0, 0xE1)]
    xmp_seg = _app(0xE1, _primary_xmp(len(gain)))
    mpf_len = len(_app(0xE2, _mpf(0, 0, 0)))
    before = 2 + sum(len(s) for s in head) + len(xmp_seg)
    total = before + mpf_len + sum(len(s) for s in rest)
    mpf_hdr_start = before + 4 + 4
    mpf_seg = _app(0xE2, _mpf(total, len(gain), total - mpf_hdr_start))
    primary = b"\xff\xd8" + b"".join(head) + xmp_seg + mpf_seg + b"".join(rest)
    assert len(primary) == total
    return primary + gain
