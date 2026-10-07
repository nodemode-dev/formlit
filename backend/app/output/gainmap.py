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


BANDS = np.array([[0.25, 0.55, 1.0], [0.3, 0.85, 0.45], [1.0, 0.85, 0.25], [1.0, 0.35, 0.3]], np.float32)


def hdr_on(dev: dict | None) -> bool:
    return bool(((dev or {}).get("hdr") or {}).get("enabled"))


def headroom(dev: dict | None, fallback: float = 2.0) -> float:
    h = (dev or {}).get("hdr") or {}
    return max(0.5, min(4.0, float(h.get("headroom", fallback) if h.get("enabled") else fallback)))


def sdr_settings(dev: dict) -> dict:
    out = copy.deepcopy({k: v for k, v in (dev or {}).items() if k != "hdr"})
    sdr = ((dev or {}).get("hdr") or {}).get("sdr") or {}
    light, effects, color = out.setdefault("light", {}), out.setdefault("effects", {}), out.setdefault("color", {})
    light["exposure"] = float(light.get("exposure", 0)) + float(sdr.get("brightness", 0)) / 50.0
    light["contrast"] = max(-100.0, min(100.0, float(light.get("contrast", 0)) + float(sdr.get("contrast", 0))))
    effects["clarity"] = max(-100.0, min(100.0, float(effects.get("clarity", 0)) + float(sdr.get("clarity", 0))))
    color["saturation"] = max(-100.0, min(100.0, float(color.get("saturation", 0)) + float(sdr.get("saturation", 0))))
    return out


def under_settings(dev: dict, stops: float) -> dict:
    lo = copy.deepcopy({k: v for k, v in (dev or {}).items() if k != "hdr"})
    light = lo.setdefault("light", {})
    light["exposure"] = float(light.get("exposure", 0)) - stops
    return lo


def gain_between(base: np.ndarray, hdr: np.ndarray, stops: float) -> np.ndarray:
    ratio = (_luma(hdr) + OFFSET) / (_luma(_decode(base)) + OFFSET)
    return np.clip(np.log2(np.maximum(ratio, 1e-6)), 0.0, stops).astype(np.float32)


def visualize(out: np.ndarray, gain: np.ndarray) -> np.ndarray:
    band = np.clip(np.floor(gain), 0, 3).astype(np.int32)
    a = np.clip(gain * 4.0, 0.0, 1.0)[..., None] * 0.65
    grey = np.repeat((out @ np.array([0.2126, 0.7152, 0.0722], np.float32))[..., None] * 0.6, 3, axis=2)
    return (grey * (1 - a) + BANDS[band] * a).astype(np.float32)


def hdr_linear(sdr: np.ndarray, gain: np.ndarray) -> np.ndarray:
    g = gain if gain.shape[:2] == sdr.shape[:2] else cv2.resize(gain, (sdr.shape[1], sdr.shape[0]), interpolation=cv2.INTER_LINEAR)
    return (_decode(sdr) * np.exp2(g)[..., None]).astype(np.float32)


def render_pair(pid: int, size: dict, dev: dict, stops: float) -> tuple[np.ndarray, np.ndarray]:
    from app.output import export
    main_dev = {k: v for k, v in (dev or {}).items() if k != "hdr"}
    sdr = export.render_photo(pid, size, "srgb", main_dev)
    under = export.render_photo(pid, size, "srgb", under_settings(dev, stops))
    if under.shape != sdr.shape:
        under = cv2.resize(under, (sdr.shape[1], sdr.shape[0]), interpolation=cv2.INTER_AREA)
    gain = gain_from(sdr, under, stops)
    if not hdr_on(dev):
        return sdr, gain
    hdr = hdr_linear(sdr, gain)
    base = export.render_photo(pid, size, "srgb", sdr_settings(dev))
    if base.shape != sdr.shape:
        base = cv2.resize(base, (sdr.shape[1], sdr.shape[0]), interpolation=cv2.INTER_AREA)
    return base, gain_between(base, hdr, stops)


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
