import io
import math
import threading
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms, ImageOps

RAW_EXTS = {".dng", ".cr2", ".cr3", ".crw", ".nef", ".nrw", ".arw", ".srf", ".sr2", ".raf", ".orf", ".rw2", ".pef", ".srw", ".x3f",
            ".3fr", ".fff", ".iiq", ".mos", ".mef", ".mrw", ".erf", ".kdc", ".dcr", ".raw", ".rwl", ".gpr", ".rwz", ".cap"}
IMAGE_EXTS = {".jpg", ".jpeg", ".jpe", ".png", ".tif", ".tiff", ".webp", ".heic", ".heif", ".hif", ".avif", ".psd", ".bmp", ".gif", ".jxl"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mts", ".m2ts", ".mkv", ".3gp", ".webm"}
SIDECAR_EXTS = {".xmp"}
SUPPORTED = RAW_EXTS | IMAGE_EXTS | VIDEO_EXTS
SOURCE_VERSION = 5

SRGB_TO_2020 = np.array([[0.6274040, 0.3292820, 0.0433136], [0.0690970, 0.9195400, 0.0113612], [0.0163916, 0.0880132, 0.8955950]], np.float32)
XYZ_FROM_SRGB = np.array([[0.412453, 0.357580, 0.180423], [0.212671, 0.715160, 0.072169], [0.019334, 0.119193, 0.950227]], np.float64)
REC2020_TO_SRGB = np.linalg.inv(SRGB_TO_2020).astype(np.float32)
XYZ_TO_2020 = np.array([[1.7166512, -0.3556708, -0.2533663], [-0.6666844, 1.6164812, 0.0157685], [0.0176399, -0.0427706, 0.9421031]], np.float64)

_heif_lock = threading.Lock()
_heif_ready = False


def _heif() -> None:
    global _heif_ready
    with _heif_lock:
        if _heif_ready:
            return
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            pass
        _heif_ready = True


def kind_of(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in RAW_EXTS:
        return "raw"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in IMAGE_EXTS:
        return {".jpg": "jpeg", ".jpeg": "jpeg", ".jpe": "jpeg", ".tif": "tiff", ".tiff": "tiff", ".heif": "heic", ".hif": "heic"}.get(ext, ext[1:])
    return "other"


def supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED


def srgb_to_linear(v: np.ndarray) -> np.ndarray:
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4).astype(np.float32)


def linear_to_srgb(v: np.ndarray) -> np.ndarray:
    v = np.clip(v, 0.0, 1.0)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(v, 1 / 2.4) - 0.055).astype(np.float32)


ROBERTSON = (
    (0.0, 0.18006, 0.26352, -0.24341), (10.0, 0.18066, 0.26589, -0.25479), (20.0, 0.18133, 0.26846, -0.26876), (30.0, 0.18208, 0.27119, -0.28539),
    (40.0, 0.18293, 0.27407, -0.30470), (50.0, 0.18388, 0.27709, -0.32675), (60.0, 0.18494, 0.28021, -0.35156), (70.0, 0.18611, 0.28342, -0.37915),
    (80.0, 0.18740, 0.28668, -0.40955), (90.0, 0.18880, 0.28997, -0.44278), (100.0, 0.19032, 0.29326, -0.47888), (125.0, 0.19462, 0.30141, -0.58204),
    (150.0, 0.19962, 0.30921, -0.70471), (175.0, 0.20525, 0.31647, -0.84901), (200.0, 0.21142, 0.32312, -1.0182), (225.0, 0.21807, 0.32909, -1.2168),
    (250.0, 0.22511, 0.33439, -1.4512), (275.0, 0.23247, 0.33904, -1.7298), (300.0, 0.24010, 0.34308, -2.0637), (325.0, 0.24792, 0.34655, -2.4681),
    (350.0, 0.25591, 0.34951, -2.9641), (375.0, 0.26400, 0.35200, -3.5814), (400.0, 0.27218, 0.35407, -4.3633), (425.0, 0.28039, 0.35577, -5.3762),
    (450.0, 0.28863, 0.35714, -6.7262), (475.0, 0.29685, 0.35823, -8.5955), (500.0, 0.30505, 0.35907, -11.324), (525.0, 0.31320, 0.35968, -15.628),
    (550.0, 0.32129, 0.36011, -23.325), (575.0, 0.32931, 0.36038, -40.770), (600.0, 0.33724, 0.36051, -116.45),
    (625.0, 0.34508, 0.36053, 189.78), (650.0, 0.35281, 0.36044, 57.748), (675.0, 0.36044, 0.36026, 35.979), (700.0, 0.36795, 0.36002, 27.095),
)
TINT_SCALE = 3000.0
MIN_RECIPROCAL = 1.0


def _line(r: float, u: float, v: float, t: float) -> tuple[float, float, float, float, float]:
    k = math.copysign(1.0 / math.hypot(1.0, t), -t)
    return r, u, v, k, k * t


ISO_LINES = tuple(_line(*row) for row in ROBERTSON)


def _uv(x: float, y: float) -> tuple[float, float]:
    d = -2.0 * x + 12.0 * y + 3.0
    return 4.0 * x / d, 6.0 * y / d


def _xy(u: float, v: float) -> tuple[float, float]:
    d = 2.0 * u - 8.0 * v + 4.0
    return 3.0 * u / d, 2.0 * v / d


def _side(i: int, u: float, v: float) -> float:
    _, lu, lv, du, dv = ISO_LINES[i]
    return (v - lv) * du - (u - lu) * dv


def _between(i: int, f: float) -> tuple[float, float, float, float, float]:
    r0, u0, v0, du0, dv0 = ISO_LINES[i]
    r1, u1, v1, du1, dv1 = ISO_LINES[i + 1]
    du, dv = du0 + (du1 - du0) * f, dv0 + (dv1 - dv0) * f
    n = math.hypot(du, dv)
    return r0 + (r1 - r0) * f, u0 + (u1 - u0) * f, v0 + (v1 - v0) * f, du / n, dv / n


def xy_to_temp_tint(x: float, y: float) -> tuple[float, float]:
    u, v = _uv(x, y)
    last = len(ISO_LINES) - 1
    i, f = last - 1, 1.0
    prev = _side(0, u, v)
    if prev <= 0.0:
        i, f = 0, 0.0
    else:
        for k in range(1, last + 1):
            e = _side(k, u, v)
            if e <= 0.0:
                i, f = k - 1, prev / (prev - e)
                break
            prev = e
    r, lu, lv, du, dv = _between(i, f)
    return 1e6 / max(r, MIN_RECIPROCAL), -TINT_SCALE * ((u - lu) * du + (v - lv) * dv)


def temp_tint_to_xy(t: float, tint: float) -> tuple[float, float]:
    last = len(ISO_LINES) - 1
    r = min(1e6 / t, ISO_LINES[last][0]) if t > 0 else ISO_LINES[last][0]
    i = 0
    while i < last - 1 and ISO_LINES[i + 1][0] <= r:
        i += 1
    r0, r1 = ISO_LINES[i][0], ISO_LINES[i + 1][0]
    f = (r - r0) / (r1 - r0)
    _, lu, lv, du, dv = _between(i, f)
    _, u0, v0, du0, dv0 = ISO_LINES[i]
    _, u1, v1, du1, dv1 = ISO_LINES[i + 1]
    nu, nv = -(dv0 + (dv1 - dv0) * f), du0 + (du1 - du0) * f
    c = (1.0 - f) * (v0 * du0 - u0 * dv0) + f * (v1 * du1 - u1 * dv1)
    a = (c - (nu * lu + nv * lv)) / (nu * nu + nv * nv)
    s = -float(tint) / TINT_SCALE
    return _xy(lu + a * nu + s * du, lv + a * nv + s * dv)


def _as_shot(raw) -> tuple[float, float]:
    try:
        cam = np.asarray(raw.rgb_xyz_matrix, np.float64)[:3, :3]
        wb = np.asarray(raw.camera_whitebalance, np.float64)[:3]
        if not np.all(np.isfinite(cam)) or abs(np.linalg.det(cam)) < 1e-9 or np.any(wb <= 0):
            wb = np.asarray(raw.daylight_whitebalance, np.float64)[:3]
        if np.any(wb <= 0) or abs(np.linalg.det(cam)) < 1e-9:
            return 5500.0, 0.0
        xyz = np.linalg.solve(cam, 1.0 / wb)
        s = xyz.sum()
        if s <= 0:
            return 5500.0, 0.0
        t, tint = xy_to_temp_tint(xyz[0] / s, xyz[1] / s)
        return float(min(50000.0, max(2000.0, t))), float(min(150.0, max(-150.0, tint)))
    except Exception:
        return 5500.0, 0.0


def _cam_to_2020(raw) -> list | None:
    try:
        if int(raw.num_colors) != 3:
            return None
        cam_rgb = np.asarray(raw.rgb_xyz_matrix, np.float64)[:3, :3] @ XYZ_FROM_SRGB
        sums = cam_rgb.sum(axis=1, keepdims=True)
        if not np.all(np.isfinite(cam_rgb)) or np.any(np.abs(sums) < 1e-9):
            return None
        cam_rgb = cam_rgb / sums
        if abs(np.linalg.det(cam_rgb)) < 1e-9:
            return None
        return (SRGB_TO_2020.astype(np.float64) @ np.linalg.inv(cam_rgb)).tolist()
    except Exception:
        return None


def _baseline_ev(path: Path) -> float | None:
    if path.suffix.lower() != ".dng":
        return None
    try:
        import tifffile
        with tifffile.TiffFile(str(path)) as tf:
            tag = tf.pages[0].tags.get(50730)
            if tag is not None:
                v = tag.value
                return float(v[0]) / float(v[1]) if isinstance(v, tuple) else float(v)
    except Exception:
        return None
    return None


def _raw_linear(path: Path, max_long: int | None, full: bool, algo: str = "AHD") -> tuple[np.ndarray, dict]:
    import rawpy
    with rawpy.imread(str(path)) as raw:
        long = max(raw.sizes.width, raw.sizes.height)
        fw, fh = (raw.sizes.height, raw.sizes.width) if raw.sizes.flip in (5, 6) else (raw.sizes.width, raw.sizes.height)
        half = (not full) and max_long is not None and long >= 2 * max_long
        extra = {"dcb_iterations": 2, "dcb_enhance": True} if algo == "DCB" else {}
        rgb = raw.postprocess(output_color=rawpy.ColorSpace.Rec2020, gamma=(1, 1), no_auto_bright=True, output_bps=16,
                              use_camera_wb=True, highlight_mode=rawpy.HighlightMode.Blend, half_size=half,
                              demosaic_algorithm=getattr(rawpy.DemosaicAlgorithm, algo, rawpy.DemosaicAlgorithm.AHD) if not half else None, **extra)
        temp, tint = _as_shot(raw)
        cam = _cam_to_2020(raw)
    img = rgb.astype(np.float32) * (1.0 / 65535.0)
    bev = _baseline_ev(path)
    gain = 2.0 ** ((bev or 0.0) + 0.35)
    img *= gain
    info = {"raw": True, "asShotTemp": temp, "asShotTint": tint, "relativeWb": False, "fullWidth": int(fw), "fullHeight": int(fh), "sensorGain": gain,
            "ownBaseline": bev is not None}
    if cam is not None:
        info["camToRec2020"] = cam
    from app.develop.camera_styles import as_shot
    style = as_shot(path)
    if style:
        info["cameraStyle"] = style
    if path.suffix.lower() == ".dng":
        from app.ai.dng import read_private
        own = read_private(path)
        if own:
            info.update({k: own[k] for k in ("cameraTone", "cameraLook", "asShotTemp", "asShotTint") if k in own})
            info["ownBaseline"] = bool(own.get("ownBaseline"))
            return img, info
    thumb = embedded_preview(path, 384)
    if thumb is not None:
        from app.develop import camera_look
        fitted = camera_look.fit(img, np.asarray(thumb.convert("RGB")))
        if "tone" in fitted:
            info["cameraTone"] = fitted["tone"]
        if "look" in fitted:
            info["cameraLook"] = fitted["look"]
    return img, info


def _icc_to_srgb(im: Image.Image) -> Image.Image:
    icc = im.info.get("icc_profile")
    if not icc:
        return im
    try:
        src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        desc = ImageCms.getProfileDescription(src) or ""
        if "srgb" in desc.lower().replace(" ", "").replace("-", ""):
            return im
        mode = "RGBA" if im.mode == "RGBA" else "RGB"
        return ImageCms.profileToProfile(im.convert(mode), src, ImageCms.createProfile("sRGB"), outputMode=mode)
    except Exception:
        return im


BRADFORD_D50_D65 = np.array([[0.9555766, -0.0230393, 0.0631636], [-0.0282895, 1.0099416, 0.0210077], [0.0122982, -0.0204830, 1.3299098]], np.float64)
_GRID = np.linspace(0.0, 1.0, 4096)


def _icc_curve(icc: bytes, off: int) -> np.ndarray | None:
    import struct
    sig = icc[off:off + 4]
    x = _GRID
    if sig == b"curv":
        n = struct.unpack(">I", icc[off + 8:off + 12])[0]
        if n == 0:
            return x
        if n == 1:
            return x ** (struct.unpack(">H", icc[off + 12:off + 14])[0] / 256.0)
        return np.interp(x, np.linspace(0.0, 1.0, n), np.frombuffer(icc, ">u2", n, off + 12).astype(np.float64) / 65535.0)
    if sig != b"para":
        return None
    kind = struct.unpack(">H", icc[off + 8:off + 10])[0]
    cnt = {0: 1, 1: 3, 2: 4, 3: 5, 4: 7}.get(kind)
    if cnt is None:
        return None
    p = [v / 65536.0 for v in struct.unpack(f">{cnt}i", icc[off + 12:off + 12 + 4 * cnt])]
    if kind == 0:
        return x ** p[0]
    g, a, b = p[0], p[1], p[2]
    pw = np.maximum(a * x + b, 0.0) ** g
    if kind in (1, 2):
        c = p[3] if kind == 2 else 0.0
        return np.where(x >= -b / a, pw + c, c)
    c, d = p[3], p[4]
    e, f = (p[5], p[6]) if kind == 4 else (0.0, 0.0)
    return np.where(x >= d, pw + e, c * x + f)


def icc_matrix(icc: bytes | None) -> tuple[list[np.ndarray], np.ndarray] | None:
    import struct
    if not icc or len(icc) < 132 or icc[16:20] != b"RGB " or icc[20:24] != b"XYZ ":
        return None
    tags = {}
    for i in range(min(struct.unpack(">I", icc[128:132])[0], 200)):
        sig, off, _size = struct.unpack(">4sII", icc[132 + 12 * i:144 + 12 * i])
        tags[sig] = off
    if not all(k in tags for k in (b"rXYZ", b"gXYZ", b"bXYZ", b"rTRC", b"gTRC", b"bTRC")):
        return None
    try:
        cols = [np.array(struct.unpack(">3i", icc[tags[k] + 8:tags[k] + 20]), np.float64) / 65536.0 for k in (b"rXYZ", b"gXYZ", b"bXYZ")]
        curves = [_icc_curve(icc, tags[k]) for k in (b"rTRC", b"gTRC", b"bTRC")]
    except (struct.error, ValueError):
        return None
    if any(c is None for c in curves):
        return None
    return curves, (XYZ_TO_2020 @ BRADFORD_D50_D65 @ np.stack(cols, axis=1)).astype(np.float32)


def is_srgb(icc: bytes | None) -> bool:
    if not icc:
        return True
    try:
        desc = ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(icc))) or ""
    except Exception:
        return False
    return "srgb" in desc.lower().replace(" ", "").replace("-", "")


def icc_linear(a: np.ndarray, icc: bytes | None) -> np.ndarray | None:
    got = icc_matrix(icc)
    if got is None:
        return None
    curves, m = got
    if a.dtype in (np.uint8, np.uint16):
        top = 255 if a.dtype == np.uint8 else 65535
        lin = np.stack([np.interp(np.arange(top + 1) / top, _GRID, curves[i]).astype(np.float32)[a[..., i]] for i in range(3)], axis=-1)
    else:
        lin = np.ascontiguousarray(a[..., :3], np.float32)
    return (lin.reshape(-1, 3) @ m.T).reshape(lin.shape).astype(np.float32)


def _pil_linear(path: Path) -> tuple[np.ndarray, dict]:
    _heif()
    im = Image.open(str(path))
    im = ImageOps.exif_transpose(im)
    if im.mode in ("I;16", "I;16B", "I;16L", "I"):
        a = np.asarray(im, np.float32)
        a = a / (65535.0 if a.max() > 255 else 255.0)
        rgb = np.repeat(a[..., None], 3, axis=2)
    elif im.mode == "F":
        a = np.asarray(im, np.float32)
        return np.repeat(a[..., None], 3, axis=2) @ SRGB_TO_2020.T, {"raw": False, "asShotTemp": 6500.0, "asShotTint": 0.0, "relativeWb": True}
    else:
        icc = im.info.get("icc_profile")
        wide = icc_linear(np.asarray(im)[..., :3], icc) if im.mode in ("RGB", "RGBA") and not is_srgb(icc) else None
        if wide is not None:
            return wide, {"raw": False, "asShotTemp": 6500.0, "asShotTint": 0.0, "relativeWb": True, "icc": True}
        im = _icc_to_srgb(im)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
        rgb = np.asarray(im, np.float32)[..., :3] / 255.0
    lin = srgb_to_linear(rgb)
    out = lin.reshape(-1, 3) @ SRGB_TO_2020.T
    return out.reshape(lin.shape).astype(np.float32), {"raw": False, "asShotTemp": 6500.0, "asShotTint": 0.0, "relativeWb": True}


def _tiff16_linear(path: Path) -> tuple[np.ndarray, dict] | None:
    try:
        import tifffile
        with tifffile.TiffFile(str(path)) as tf:
            page = tf.pages[0]
            a = page.asarray()
            tag = page.tags.get(34675)
            icc = bytes(tag.value) if tag is not None else None
    except Exception:
        return None
    if a.ndim != 3 or a.shape[2] < 3:
        return None
    info = {"raw": False, "asShotTemp": 6500.0, "asShotTint": 0.0, "relativeWb": True}
    wide = icc_linear(a[..., :3], icc) if a.dtype in (np.uint16, np.uint8, np.float32, np.float16, np.float64) and not is_srgb(icc) else None
    if wide is not None:
        return wide, {**info, "icc": True}
    if a.dtype == np.uint16:
        rgb = a[..., :3].astype(np.float32) / 65535.0
    elif a.dtype in (np.float32, np.float16, np.float64):
        lin = a[..., :3].astype(np.float32)
        return (lin.reshape(-1, 3) @ SRGB_TO_2020.T).reshape(lin.shape).astype(np.float32), info
    else:
        return None
    lin = srgb_to_linear(rgb)
    return (lin.reshape(-1, 3) @ SRGB_TO_2020.T).reshape(lin.shape).astype(np.float32), {"raw": False, "asShotTemp": 6500.0, "asShotTint": 0.0, "relativeWb": True}


def psd_header(data: bytes) -> tuple[int, int, int, int, int, int] | None:
    import struct
    if len(data) < 26 or data[:4] != b"8BPS":
        return None
    ver = struct.unpack(">H", data[4:6])[0]
    ch, h, w, depth, mode = struct.unpack(">HIIHH", data[12:26])
    return ver, ch, h, w, depth, mode


def _psd_linear(path: Path) -> tuple[np.ndarray, dict] | None:
    import struct
    data = path.read_bytes()
    head = psd_header(data)
    if head is None:
        return None
    ver, ch, h, w, depth, mode = head
    if depth not in (16, 32) or mode not in (1, 3):
        return None
    off = 26
    off += 4 + struct.unpack(">I", data[off:off + 4])[0]
    n = struct.unpack(">I", data[off:off + 4])[0]
    res, icc, pos = data[off + 4:off + 4 + n], None, 0
    while pos + 12 <= len(res) and res[pos:pos + 4] == b"8BIM":
        rid = struct.unpack(">H", res[pos + 4:pos + 6])[0]
        nl = res[pos + 6]
        pos += 6 + (nl + 2 if nl % 2 == 0 else nl + 1)
        size = struct.unpack(">I", res[pos:pos + 4])[0]
        if rid == 1039:
            icc = bytes(res[pos + 4:pos + 4 + size])
        pos += 4 + size + (size % 2)
    off += 4 + n
    lw = 8 if ver == 2 else 4
    off += lw + struct.unpack(">Q" if ver == 2 else ">I", data[off:off + lw])[0]
    comp = struct.unpack(">H", data[off:off + 2])[0]
    off += 2
    nch = 3 if mode == 3 else 1
    dt = np.dtype(">u2") if depth == 16 else np.dtype(">f4")
    bpr = w * dt.itemsize
    if comp == 0:
        planes = np.frombuffer(data, dt, ch * h * w, off).reshape(ch, h, w)[:nch]
    elif comp == 1:
        counts = np.frombuffer(data, ">u4" if ver == 2 else ">u2", ch * h, off).astype(np.int64)
        pos = off + ch * h * (4 if ver == 2 else 2)
        out = []
        for c in range(nch):
            size = int(counts[c * h:(c + 1) * h].sum())
            im = Image.frombytes("L", (bpr, h), data[pos:pos + size], "packbits", "L")
            out.append(np.frombuffer(im.tobytes(), dt).reshape(h, w))
            pos += size
        planes = np.stack(out)
    else:
        return None
    a = np.moveaxis(planes, 0, -1)
    if nch == 1:
        a = np.repeat(a, 3, axis=2)
    a = a.astype(np.uint16) if depth == 16 else a.astype(np.float32)
    info = {"raw": False, "asShotTemp": 6500.0, "asShotTint": 0.0, "relativeWb": True}
    wide = icc_linear(a, icc) if mode == 3 and not is_srgb(icc) else None
    if wide is not None:
        return wide, {**info, "icc": True}
    if depth == 32:
        lin = a
    else:
        lin = srgb_to_linear(a.astype(np.float32) / 65535.0)
    return (lin.reshape(-1, 3) @ SRGB_TO_2020.T).reshape(lin.shape).astype(np.float32), info


def _jxl_array(path: Path) -> np.ndarray:
    import imagecodecs
    a = imagecodecs.jpegxl_decode(path.read_bytes())
    if a.ndim == 2:
        a = np.repeat(a[..., None], 3, axis=2)
    elif a.shape[2] == 1:
        a = np.repeat(a, 3, axis=2)
    return a[..., :3]


def _jxl_linear(path: Path) -> tuple[np.ndarray, dict]:
    a = _jxl_array(path)
    if a.dtype in (np.uint8, np.uint16):
        lin = srgb_to_linear(a.astype(np.float32) / (255.0 if a.dtype == np.uint8 else 65535.0))
    else:
        lin = a.astype(np.float32)
    return (lin.reshape(-1, 3) @ SRGB_TO_2020.T).reshape(lin.shape).astype(np.float32), {"raw": False, "asShotTemp": 6500.0, "asShotTint": 0.0, "relativeWb": True}


def _video_frame(path: Path) -> tuple[np.ndarray, dict]:
    import subprocess
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.5", "-i", str(path), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, timeout=60)
    if out.returncode != 0 or not out.stdout:
        raise ValueError("ffmpeg could not read a frame from the video")
    im = Image.open(io.BytesIO(out.stdout)).convert("RGB")
    lin = srgb_to_linear(np.asarray(im, np.float32) / 255.0)
    return (lin.reshape(-1, 3) @ SRGB_TO_2020.T).reshape(lin.shape).astype(np.float32), {"raw": False, "asShotTemp": 6500.0, "asShotTint": 0.0, "relativeWb": True}


def resize_long(img: np.ndarray, long: int) -> np.ndarray:
    import cv2
    h, w = img.shape[:2]
    m = max(h, w)
    if m <= long:
        return img
    k = long / m
    return cv2.resize(img, (max(1, round(w * k)), max(1, round(h * k))), interpolation=cv2.INTER_AREA)


def load_linear(path: Path, max_long: int | None = None, full: bool = False) -> tuple[np.ndarray, dict]:
    kind = kind_of(path)
    if kind == "raw":
        img, info = _raw_linear(path, max_long, full)
    elif kind == "video":
        img, info = _video_frame(path)
    elif kind == "tiff":
        got = _tiff16_linear(path)
        img, info = got if got else _pil_linear(path)
    elif kind == "psd":
        got = _psd_linear(path)
        img, info = got if got else _pil_linear(path)
    elif kind == "jxl":
        img, info = _jxl_linear(path)
    else:
        img, info = _pil_linear(path)
    img = np.ascontiguousarray(np.clip(img, 0.0, 64.0).astype(np.float32))
    info.setdefault("fullWidth", int(img.shape[1]))
    info.setdefault("fullHeight", int(img.shape[0]))
    if max_long:
        img = resize_long(img, max_long)
    info["width"], info["height"] = img.shape[1], img.shape[0]
    info["v"] = SOURCE_VERSION
    return img, info


def embedded_preview(path: Path, max_long: int = 1024) -> Image.Image | None:
    kind = kind_of(path)
    try:
        if kind == "raw":
            import rawpy
            with rawpy.imread(str(path)) as raw:
                thumb = raw.extract_thumb()
                flip = raw.sizes.flip
            if thumb.format == rawpy.ThumbFormat.JPEG:
                im = Image.open(io.BytesIO(thumb.data))
                im.load()
            else:
                im = Image.fromarray(thumb.data)
            im = im.convert("RGB")
            rot = {3: Image.Transpose.ROTATE_180, 5: Image.Transpose.ROTATE_90, 6: Image.Transpose.ROTATE_270}.get(flip)
            if rot is not None:
                im = im.transpose(rot)
        elif kind in ("video", "jxl"):
            arr, _ = _video_frame(path) if kind == "video" else _jxl_linear(path)
            lin = arr.reshape(-1, 3) @ REC2020_TO_SRGB.T
            im = Image.fromarray((linear_to_srgb(lin.reshape(arr.shape)) * 255 + 0.5).astype(np.uint8))
        else:
            _heif()
            im = Image.open(str(path))
            im.draft("RGB", (max_long, max_long))
            im = ImageOps.exif_transpose(im)
            im = _icc_to_srgb(im)
            im = im.convert("RGB")
        im.thumbnail((max_long, max_long), Image.Resampling.LANCZOS)
        return im
    except Exception:
        return None


def dimensions(path: Path) -> tuple[int, int]:
    kind = kind_of(path)
    try:
        if kind == "raw":
            import rawpy
            with rawpy.imread(str(path)) as raw:
                w, h, flip = raw.sizes.width, raw.sizes.height, raw.sizes.flip
            return (h, w) if flip in (5, 6) else (w, h)
        if kind == "video":
            import json
            import subprocess
            out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(path)], capture_output=True, timeout=30)
            s = json.loads(out.stdout or b"{}").get("streams", [{}])[0]
            return int(s.get("width", 0)), int(s.get("height", 0))
        if kind == "psd":
            with open(path, "rb") as fh:
                head = psd_header(fh.read(26))
            if head:
                return head[3], head[2]
        if kind == "jxl":
            a = _jxl_array(path)
            return a.shape[1], a.shape[0]
        _heif()
        with Image.open(str(path)) as im:
            w, h = im.size
            o = im.getexif().get(0x0112, 1)
        return (h, w) if o in (5, 6, 7, 8) else (w, h)
    except Exception:
        return 0, 0
