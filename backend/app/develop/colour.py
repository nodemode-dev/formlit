from functools import lru_cache

import numpy as np

from app.services.decode import temp_tint_to_xy, xy_to_temp_tint

D65 = (0.3127, 0.3290)
D50 = (0.3457, 0.3585)

SPACES = {
    "srgb": ("sRGB", (0.6400, 0.3300), (0.3000, 0.6000), (0.1500, 0.0600), D65),
    "p3": ("Display P3", (0.680, 0.320), (0.265, 0.690), (0.150, 0.060), D65),
    "rec2020": ("Rec. 2020", (0.708, 0.292), (0.170, 0.797), (0.131, 0.046), D65),
    "adobergb": ("Adobe RGB (1998) compatible", (0.6400, 0.3300), (0.2100, 0.7100), (0.1500, 0.0600), D65),
    "prophoto": ("ProPhoto RGB", (0.7347, 0.2653), (0.1596, 0.8404), (0.0366, 0.0001), D50),
}
WORKING = "rec2020"

LUMA_2020 = np.array([0.2627, 0.6780, 0.0593], np.float32)
LUMA_709 = np.array([0.2126, 0.7152, 0.0722], np.float32)

BRADFORD = np.array([[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]], np.float64)

OKLAB_M1 = np.array([[0.8189330101, 0.3618667424, -0.1288597137],
                     [0.0329845436, 0.9293118715, 0.0361456387],
                     [0.0482003018, 0.2643662691, 0.6338517070]], np.float64)
OKLAB_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                     [1.9779984951, -2.4285922050, 0.4505937099],
                     [0.0259040371, 0.7827717662, -0.8086757660]], np.float64)


def xy_to_xyz(xy) -> np.ndarray:
    x, y = float(xy[0]), float(xy[1])
    return np.array([x / y, 1.0, (1.0 - x - y) / y], np.float64)


@lru_cache(maxsize=16)
def to_xyz(space: str) -> np.ndarray:
    _, r, g, b, w = SPACES[space]
    prim = np.stack([xy_to_xyz(r), xy_to_xyz(g), xy_to_xyz(b)], axis=1)
    return prim * np.linalg.solve(prim, xy_to_xyz(w))


@lru_cache(maxsize=16)
def from_xyz(space: str) -> np.ndarray:
    return np.linalg.inv(to_xyz(space))


def bradford(src_xy, dst_xy) -> np.ndarray:
    if abs(float(src_xy[0]) - float(dst_xy[0])) <= 1e-12 and abs(float(src_xy[1]) - float(dst_xy[1])) <= 1e-12:
        return np.eye(3)
    cone = (BRADFORD @ xy_to_xyz(dst_xy)) / (BRADFORD @ xy_to_xyz(src_xy))
    return np.linalg.solve(BRADFORD, cone[:, None] * BRADFORD)


@lru_cache(maxsize=16)
def working_to(space: str) -> np.ndarray:
    return from_xyz(space) @ bradford(SPACES[WORKING][4], SPACES[space][4]) @ to_xyz(WORKING)


def luma(space: str) -> np.ndarray:
    return to_xyz(space)[1].astype(np.float32)


def wb_matrix_xy(xy) -> np.ndarray:
    return from_xyz(WORKING) @ bradford(xy, SPACES[WORKING][4]) @ to_xyz(WORKING)


def wb_matrix(temp: float, tint: float, shot_temp: float, shot_tint: float) -> np.ndarray | None:
    if abs(temp - shot_temp) <= 1e-6 and abs(tint - shot_tint) <= 1e-6:
        return None
    m = wb_matrix_xy(temp_tint_to_xy(temp, tint)) @ np.linalg.inv(wb_matrix_xy(temp_tint_to_xy(shot_temp, shot_tint)))
    grey = float(to_xyz(WORKING)[1] @ m.sum(axis=1))
    return (m / grey).astype(np.float32)


@lru_cache(maxsize=1)
def oklab_mats() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    to_lms = OKLAB_M1 @ to_xyz(WORKING)
    return (to_lms.astype(np.float32), np.linalg.inv(to_lms).astype(np.float32), OKLAB_M2.astype(np.float32),
            np.linalg.inv(OKLAB_M2).astype(np.float32))


def oklab_from_2020(rgb: np.ndarray) -> np.ndarray:
    to_lms, _, to_lab, _ = oklab_mats()
    lms = np.asarray(rgb, np.float32) @ to_lms.T
    return (np.cbrt(lms) @ to_lab.T).astype(np.float32)


def oklab_to_2020(lab: np.ndarray) -> np.ndarray:
    _, from_lms, _, from_lab = oklab_mats()
    lms = np.asarray(lab, np.float32) @ from_lab.T
    return ((lms * lms * lms) @ from_lms.T).astype(np.float32)


def lab_to_lch(lab: np.ndarray) -> np.ndarray:
    lab = np.asarray(lab)
    return np.stack([lab[..., 0], np.hypot(lab[..., 1], lab[..., 2]), np.arctan2(lab[..., 2], lab[..., 1])], axis=-1)


def lch_to_lab(lch: np.ndarray) -> np.ndarray:
    lch = np.asarray(lch)
    return np.stack([lch[..., 0], lch[..., 1] * np.cos(lch[..., 2]), lch[..., 1] * np.sin(lch[..., 2])], axis=-1)


def srgb_encode(v: np.ndarray) -> np.ndarray:
    v = np.clip(np.asarray(v, np.float32), 0.0, 1.0)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(v, 1.0 / 2.4) - 0.055).astype(np.float32)


def srgb_decode(v: np.ndarray) -> np.ndarray:
    v = np.clip(np.asarray(v, np.float32), 0.0, 1.0)
    return np.where(v <= 0.04045, v / 12.92, np.power((v + 0.055) / 1.055, 2.4)).astype(np.float32)


def hsv_hue_to_oklch(deg):
    h6 = np.mod(np.asarray(deg, np.float64), 360.0) / 60.0
    rgb = np.stack([np.abs(h6 - 3.0) - 1.0, 2.0 - np.abs(h6 - 2.0), 2.0 - np.abs(h6 - 4.0)], axis=-1)
    lin = srgb_decode(np.clip(rgb, 0.0, 1.0)).astype(np.float64) @ (from_xyz(WORKING) @ to_xyz("srgb")).T
    lab = oklab_from_2020(lin)
    h = np.arctan2(lab[..., 2].astype(np.float64), lab[..., 1].astype(np.float64))
    return float(h) if h.ndim == 0 else h


__all__ = ["D65", "D50", "SPACES", "LUMA_2020", "LUMA_709", "xy_to_xyz", "to_xyz", "from_xyz", "bradford", "working_to", "luma", "wb_matrix_xy", "wb_matrix",
           "oklab_mats", "oklab_from_2020", "oklab_to_2020", "lab_to_lch", "lch_to_lab", "srgb_encode", "srgb_decode", "hsv_hue_to_oklch",
           "temp_tint_to_xy", "xy_to_temp_tint"]
