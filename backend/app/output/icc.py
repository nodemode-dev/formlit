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
