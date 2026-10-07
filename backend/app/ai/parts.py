import cv2
import numpy as np

PERSON_PARTS = {"faceSkin": "Face Skin", "bodySkin": "Body Skin", "eyebrows": "Eyebrows", "sclera": "Eye Sclera", "iris": "Iris and Pupil", "lips": "Lips",
                "teeth": "Teeth", "hair": "Hair", "clothes": "Clothes"}
LANDSCAPE_PARTS = {"sky": "Sky", "water": "Water", "vegetation": "Vegetation", "mountains": "Mountains", "architecture": "Architecture",
                   "naturalGround": "Natural Ground", "artificialGround": "Artificial Ground"}


def _smooth(a: np.ndarray, sigma: float) -> np.ndarray:
    return np.clip(cv2.GaussianBlur(a.astype(np.float32), (0, 0), max(0.8, sigma)), 0.0, 1.0)


def _ellipse(h: int, w: int, cx: float, cy: float, rx: float, ry: float, soft: float = 0.25) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - cx) / max(rx, 1.0)) ** 2 + ((yy - cy) / max(ry, 1.0)) ** 2)
    return np.clip((1.0 + soft - d) / max(soft, 1e-3), 0.0, 1.0)


def skin(rgb8: np.ndarray) -> np.ndarray:
    ycc = cv2.cvtColor(rgb8, cv2.COLOR_RGB2YCrCb).astype(np.float32)
    cr, cb, y = ycc[..., 1], ycc[..., 2], ycc[..., 0]
    m = np.clip((cr - 133) / 8, 0, 1) * np.clip((176 - cr) / 8, 0, 1) * np.clip((cb - 76) / 8, 0, 1) * np.clip((128 - cb) / 8, 0, 1) * np.clip((y - 35) / 20, 0, 1)
    return _smooth(m, max(rgb8.shape[:2]) / 600.0)


def people_parts(rgb8: np.ndarray, person: np.ndarray, faces: list[dict]) -> dict[str, np.ndarray]:
    h, w = rgb8.shape[:2]
    hsv = cv2.cvtColor(rgb8, cv2.COLOR_RGB2HSV).astype(np.float32)
    sat, val = hsv[..., 1] / 255.0, hsv[..., 2] / 255.0
    lab = cv2.cvtColor(rgb8, cv2.COLOR_RGB2LAB).astype(np.float32)
    sk = skin(rgb8) * np.clip(person * 1.4, 0.0, 1.0)
    face_zone = np.zeros((h, w), np.float32)
    head_zone = np.zeros((h, w), np.float32)
    hair_zone = np.zeros((h, w), np.float32)
    out = {k: np.zeros((h, w), np.float32) for k in PERSON_PARTS}
    for f in faces:
        x0, y0, x1, y1 = f["box"][0] * w, f["box"][1] * h, f["box"][2] * w, f["box"][3] * h
        fw, fh = x1 - x0, y1 - y0
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        face_zone = np.maximum(face_zone, _ellipse(h, w, cx, cy + fh * 0.04, fw * 0.58, fh * 0.66, 0.15))
        head = _ellipse(h, w, cx, cy - fh * 0.12, fw * 0.95, fh * 0.98, 0.2)
        head_zone = np.maximum(head_zone, head)
        cut = y0 + fh * 0.62
        hair_zone = np.maximum(hair_zone, head * np.clip((cut - np.arange(h, dtype=np.float32))[:, None] / max(2.0, h * 0.01), 0.0, 1.0))
        lm = [(px * w, py * h) for px, py in (f.get("landmarks") or [])]
        if len(lm) < 5:
            continue
        eyes = lm[:2]
        er = fw * 0.075
        for ex, ey in eyes:
            iris = _ellipse(h, w, ex, ey, er * 0.62, er * 0.62, 0.3)
            out["iris"] = np.maximum(out["iris"], iris * np.clip((0.75 - val) / 0.3, 0.0, 1.0))
            eye = _ellipse(h, w, ex, ey, er * 1.6, er * 0.8, 0.3)
            sclera = eye * (1.0 - iris) * np.clip((val - 0.45) / 0.2, 0.0, 1.0) * np.clip((0.35 - sat) / 0.2, 0.0, 1.0)
            out["sclera"] = np.maximum(out["sclera"], sclera)
            brow = _ellipse(h, w, ex, ey - fh * 0.16, er * 2.1, er * 0.65, 0.4)
            out["eyebrows"] = np.maximum(out["eyebrows"], brow * np.clip((0.55 - val) / 0.25, 0.0, 1.0) * (1.0 - _ellipse(h, w, ex, ey, er * 1.4, er * 0.9, 0.2)))
        (mx0, my0), (mx1, my1) = lm[3], lm[4]
        mcx, mcy = (mx0 + mx1) / 2, (my0 + my1) / 2
        mw = max(abs(mx1 - mx0), fw * 0.2)
        mouth = _ellipse(h, w, mcx, mcy + fh * 0.01, mw * 0.62, fh * 0.1, 0.35)
        a_star = (lab[..., 1] - 128.0) / 40.0
        out["lips"] = np.maximum(out["lips"], mouth * np.clip((a_star - 0.18) / 0.25, 0.0, 1.0))
        out["teeth"] = np.maximum(out["teeth"], mouth * np.clip((val - 0.55) / 0.2, 0.0, 1.0) * np.clip((0.3 - sat) / 0.15, 0.0, 1.0))
    features = np.maximum.reduce([out["iris"], out["sclera"], out["eyebrows"], out["lips"], out["teeth"]])
    face_skin = sk * face_zone * (1.0 - features)
    sim = np.ones((h, w), np.float32)
    wsum = float(face_skin.sum())
    if wsum > 50:
        mean = (lab * face_skin[..., None]).sum(axis=(0, 1)) / wsum
        sd = np.sqrt(((lab - mean) ** 2 * face_skin[..., None]).sum(axis=(0, 1)) / wsum) + np.array([6.0, 3.0, 3.0], np.float32)
        sim = np.exp(-0.5 * (((lab - mean) / (sd * 2.2)) ** 2).sum(axis=-1)).astype(np.float32)
    out["faceSkin"] = _smooth(face_skin, max(h, w) / 900.0)
    out["bodySkin"] = _smooth(sk * sim * (1.0 - np.clip(face_zone * 1.3, 0, 1)) * (1.0 - head_zone), max(h, w) / 900.0)
    hair = person * hair_zone * (1.0 - np.clip(face_zone * 1.2, 0.0, 1.0)) * np.clip((0.9 - val) / 0.3, 0.3, 1.0)
    out["hair"] = _smooth(hair, max(h, w) / 700.0)
    out["clothes"] = _smooth(np.clip(person - np.maximum.reduce([sk, out["hair"], face_zone, hair_zone]), 0.0, 1.0), max(h, w) / 700.0)
    for k in ("iris", "sclera", "eyebrows", "lips", "teeth"):
        out[k] = _smooth(out[k], max(h, w) / 1500.0)
    return out


def _texture(gray: np.ndarray, sigma: float) -> np.ndarray:
    g = gray.astype(np.float32) / 255.0
    mu = cv2.GaussianBlur(g, (0, 0), sigma)
    var = cv2.GaussianBlur(g * g, (0, 0), sigma) - mu * mu
    return np.sqrt(np.maximum(var, 0.0))


def landscape_parts(rgb8: np.ndarray, sky: np.ndarray | None, depth: np.ndarray | None) -> dict[str, np.ndarray]:
    h, w = rgb8.shape[:2]
    s = max(h, w) / 1000.0
    f = rgb8.astype(np.float32) / 255.0
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    hsv = cv2.cvtColor(rgb8, cv2.COLOR_RGB2HSV).astype(np.float32)
    hue, sat, val = hsv[..., 0] * 2.0, hsv[..., 1] / 255.0, hsv[..., 2] / 255.0
    gray = cv2.cvtColor(rgb8, cv2.COLOR_RGB2GRAY)
    tex = _texture(gray, 3.0 * s)
    sky_a = sky if sky is not None else np.clip((b - r) * 3 + 0.3, 0, 1) * np.clip(1.4 - np.linspace(0, 2.2, h)[:, None], 0, 1)
    not_sky = 1.0 - np.clip(sky_a * 1.3, 0.0, 1.0)
    rows = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None] * np.ones((1, w), np.float32)
    exg = 2 * g - r - b
    veg = np.clip((exg - 0.04) / 0.1, 0.0, 1.0) * np.clip((hue - 55) / 15, 0, 1) * np.clip((170 - hue) / 15, 0, 1) * not_sky
    veg = np.maximum(veg, np.clip((exg - 0.02) / 0.08, 0, 1) * np.clip(tex / 0.04, 0, 1) * not_sky * np.clip((hue - 60) / 10, 0, 1) * np.clip((165 - hue) / 10, 0, 1))
    blue = np.clip((hue - 165) / 15, 0, 1) * np.clip((250 - hue) / 15, 0, 1)
    water = blue * np.clip((0.06 - tex) / 0.04, 0, 1) * np.clip((rows - 0.3) / 0.15, 0, 1) * not_sky * (1.0 - veg)
    edges = cv2.Canny(gray, 60, 160)
    lines = np.zeros_like(gray)
    found = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=70, minLineLength=int(70 * s), maxLineGap=int(3 * s) + 1)
    if found is not None:
        for x1, y1, x2, y2 in np.asarray(found).reshape(-1, 4):
            ang = abs(np.degrees(np.arctan2(float(y2 - y1), float(x2 - x1)))) % 90
            if min(ang, 90 - ang) <= 10:
                cv2.line(lines, (int(x1), int(y1)), (int(x2), int(y2)), 255, max(1, int(3 * s)))
    density = cv2.GaussianBlur(lines.astype(np.float32) / 255.0, (0, 0), 14 * s)
    arch = np.clip((density - 0.05) / 0.12, 0, 1) * np.clip((0.45 - sat) / 0.3, 0, 1) * np.clip((0.1 - tex) / 0.05, 0, 1) * not_sky * (1.0 - veg) * (1.0 - water)
    far = 1.0 - depth if depth is not None else np.clip(1.0 - rows * 1.4, 0, 1)
    horizon = np.clip(1.0 - rows / 0.65, 0, 1)
    mountains = np.clip((far - 0.55) / 0.2, 0, 1) * horizon * not_sky * (1.0 - veg * 0.6) * (1.0 - water) * (1.0 - arch)
    ground = np.clip((rows - 0.45) / 0.2, 0, 1) * not_sky * (1.0 - water) * (1.0 - arch * 0.8) * (1.0 - mountains)
    earthy = np.clip((hue - 10) / 15, 0, 1) * np.clip((70 - hue) / 15, 0, 1) * np.clip((sat - 0.12) / 0.15, 0, 1)
    natural = ground * np.maximum(earthy, veg * 0.6) * np.maximum(np.clip(tex / 0.05, 0, 1), 0.4)
    artificial = ground * np.clip((0.2 - sat) / 0.12, 0, 1) * np.clip((0.05 - tex) / 0.04, 0, 1) * (1.0 - veg)
    sm = 2.5 * s
    return {"sky": _smooth(sky_a, sm), "water": _smooth(water, sm * 2), "vegetation": _smooth(veg, sm), "mountains": _smooth(mountains, sm * 2),
            "architecture": _smooth(arch, sm * 2), "naturalGround": _smooth(natural, sm * 2), "artificialGround": _smooth(artificial, sm * 2)}
