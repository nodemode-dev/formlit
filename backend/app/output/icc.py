import os
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms

from app.core import config


def folders() -> list[Path]:
    home = Path.home()
    if sys.platform == "darwin":
        out = [Path("/Library/ColorSync/Profiles"), home / "Library/ColorSync/Profiles", Path("/System/Library/ColorSync/Profiles")]
    elif sys.platform == "win32":
        out = [Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/spool/drivers/color"]
    else:
        out = [Path("/usr/share/color/icc"), Path("/usr/local/share/color/icc"), home / ".local/share/icc", home / ".color/icc"]
    out.append(config.profiles_dir() / "ICC")
    return out


def describe(path: Path) -> str:
    try:
        return ImageCms.getProfileDescription(ImageCms.getOpenProfile(str(path))).strip() or path.stem
    except Exception:
        return path.stem


def profiles() -> list[dict]:
    seen: set[str] = set()
    out = []
    for folder in folders():
        if not folder.is_dir():
            continue
        for p in sorted(folder.rglob("*")):
            if p.suffix.lower() in (".icc", ".icm") and p.is_file() and str(p) not in seen:
                seen.add(str(p))
                try:
                    prof = ImageCms.getOpenProfile(str(p))
                    if prof.profile.xcolor_space.strip() not in ("RGB", "CMYK"):
                        continue
                    out.append({"name": describe(p), "path": str(p), "space": prof.profile.xcolor_space.strip(), "class": prof.profile.device_class})
                except Exception:
                    continue
    return out


INTENTS = {"perceptual": ImageCms.Intent.PERCEPTUAL, "relative": ImageCms.Intent.RELATIVE_COLORIMETRIC, "saturation": ImageCms.Intent.SATURATION,
           "absolute": ImageCms.Intent.ABSOLUTE_COLORIMETRIC}


@lru_cache(maxsize=8)
def _proof(path: str, intent: str, paper: bool):
    srgb = ImageCms.createProfile("sRGB")
    proof = ImageCms.getOpenProfile(path)
    return ImageCms.buildProofTransform(srgb, srgb, proof, "RGB", "RGB", renderingIntent=INTENTS.get(intent, ImageCms.Intent.PERCEPTUAL),
                                        proofRenderingIntent=ImageCms.Intent.ABSOLUTE_COLORIMETRIC if paper else ImageCms.Intent.RELATIVE_COLORIMETRIC,
                                        flags=ImageCms.Flags.SOFTPROOFING)


@lru_cache(maxsize=8)
def _roundtrip(path: str):
    srgb = ImageCms.createProfile("sRGB")
    proof = ImageCms.getOpenProfile(path)
    mode = "CMYK" if proof.profile.xcolor_space.strip() == "CMYK" else "RGB"
    there = ImageCms.buildTransform(srgb, proof, "RGB", mode, renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC)
    back = ImageCms.buildTransform(proof, srgb, mode, "RGB", renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC)
    return there, back


def soft_proof(out: np.ndarray, path: str, intent: str = "perceptual", paper: bool = False, gamut: bool = False) -> np.ndarray:
    u8 = (np.clip(out, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    im = Image.fromarray(u8, "RGB")
    proofed = np.asarray(ImageCms.applyTransform(im, _proof(path, intent, paper)), np.float32) / 255.0
    if gamut:
        there, back = _roundtrip(path)
        rt = np.asarray(ImageCms.applyTransform(ImageCms.applyTransform(im, there), back), np.int16)
        outside = np.max(np.abs(rt - u8.astype(np.int16)), axis=-1) > 6
        proofed = proofed.copy()
        proofed[outside] = np.array([1.0, 0.1, 0.55], np.float32)
    return proofed


LUT_N = 33


@lru_cache(maxsize=8)
def _lut(path: str, intent: str, bpc: bool, src: str = "srgb") -> np.ndarray:
    v = np.round(np.linspace(0, 255, LUT_N)).astype(np.uint8)
    r, g, b = np.meshgrid(v, v, v, indexing="ij")
    grid = np.stack([r, g, b], axis=-1).reshape(LUT_N * LUT_N, LUT_N, 3)
    dst = ImageCms.getOpenProfile(path)
    if dst.profile.xcolor_space.strip() != "RGB":
        raise ValueError("Choose an RGB printer profile; CMYK profiles are for prepress, not desktop printers")
    flags = ImageCms.Flags.BLACKPOINTCOMPENSATION if bpc else ImageCms.Flags.NONE
    if src == "srgb":
        source = ImageCms.createProfile("sRGB")
    else:
        import io
        from app.develop.output import icc_profile
        source = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile(src)))
    t = ImageCms.buildTransform(source, dst, "RGB", "RGB", renderingIntent=INTENTS.get(intent, ImageCms.Intent.PERCEPTUAL), flags=flags)
    out = np.asarray(ImageCms.applyTransform(Image.fromarray(grid, "RGB"), t), np.float32) / 255.0
    return out.reshape(LUT_N, LUT_N, LUT_N, 3)


def convert(img: np.ndarray, src: str, path: str, intent: str = "relative") -> np.ndarray:
    from app.develop.output import icc_profile
    from app.services import decode
    a, b = decode.icc_matrix(icc_profile(src)), decode.icc_matrix(icc_bytes(path))
    if a is None or b is None or intent == "perceptual":
        return to_printer(img, path, intent, True, src)
    grid = np.linspace(0.0, 1.0, 4096)
    m = (np.linalg.inv(b[1].astype(np.float64)) @ a[1].astype(np.float64)).astype(np.float32)
    out = np.empty(img.shape, np.float32)
    for y0 in range(0, img.shape[0], 512):
        part = img[y0:y0 + 512]
        lin = np.stack([np.interp(np.clip(part[..., i], 0.0, 1.0), grid, a[0][i]) for i in range(3)], axis=-1).astype(np.float32)
        rgb = np.clip(lin.reshape(-1, 3) @ m.T, 0.0, 1.0).reshape(lin.shape)
        out[y0:y0 + 512] = np.stack([np.interp(rgb[..., i], b[0][i], grid) for i in range(3)], axis=-1)
    return out


def to_printer(img: np.ndarray, path: str, intent: str = "perceptual", bpc: bool = True, src: str = "srgb") -> np.ndarray:
    lut = _lut(path, intent, bpc, src)
    n = LUT_N - 1
    out = np.empty(img.shape, np.float32)
    for y0 in range(0, img.shape[0], 256):
        x = np.clip(img[y0:y0 + 256], 0.0, 1.0) * n
        i = np.minimum(np.floor(x).astype(np.int32), n - 1)
        f = (x - i).astype(np.float32)
        r, g, b = i[..., 0], i[..., 1], i[..., 2]
        fr, fg, fb = f[..., 0:1], f[..., 1:2], f[..., 2:3]
        c00 = lut[r, g, b] * (1 - fr) + lut[r + 1, g, b] * fr
        c01 = lut[r, g, b + 1] * (1 - fr) + lut[r + 1, g, b + 1] * fr
        c10 = lut[r, g + 1, b] * (1 - fr) + lut[r + 1, g + 1, b] * fr
        c11 = lut[r, g + 1, b + 1] * (1 - fr) + lut[r + 1, g + 1, b + 1] * fr
        out[y0:y0 + 256] = (c00 * (1 - fb) + c01 * fb) * (1 - fg) + (c10 * (1 - fb) + c11 * fb) * fg
    return out


def icc_bytes(path: str) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError:
        return b""
