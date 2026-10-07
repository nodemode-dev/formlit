import math
import numbers

import cv2
import numpy as np
from numba import njit, prange

from app.develop.settings import section_enabled

BLANK = (0.18, 0.18, 0.18)
FOCAL = 1.5
KEYSTONE_MAX = 30.0
ASPECT_MAX = 0.5
OFFSET_FULL = 0.5
DISTORTION_MAX = 0.15
VIGNETTE_STOPS = 2.0
VIGNETTE_REACH = 0.75
CA_FULL = 0.002
EDGE = 0.5
AREA_RATIO = 1.25
MIN_CROP = 0.02
CONSTRAIN_STEPS = 30
BORDER_POINTS = 64
BAND_PIXELS = 4_200_000
NP = 52
LN2 = math.log(2.0)
TABLE_N = 8193
TABLE_MAX = 1.1
FAST = {"contract", "afn", "arcp", "reassoc", "nsz"}


def _num(v, fallback: float = 0.0) -> float:
    return float(v) if isinstance(v, numbers.Real) and not isinstance(v, (bool, np.bool_)) and math.isfinite(v) else fallback


def rot_x(t: float) -> np.ndarray:
    c, s = math.cos(t), math.sin(t)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def rot_y(t: float) -> np.ndarray:
    c, s = math.cos(t), math.sin(t)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def rot_z(t: float) -> np.ndarray:
    c, s = math.cos(t), math.sin(t)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def recentre(m: np.ndarray) -> np.ndarray:
    m = np.asarray(m, np.float64)
    if abs(m[2, 2]) < 1e-12:
        return np.eye(3)
    m = m / m[2, 2]
    x0, y0 = m[0, 2], m[1, 2]
    t = np.array([[1.0, 0.0, -x0], [0.0, 1.0, -y0], [0.0, 0.0, 1.0]]) @ m
    det = abs(t[0, 0] * t[1, 1] - t[0, 1] * t[1, 0])
    if det < 1e-12:
        return np.eye(3)
    s = 1.0 / math.sqrt(det)
    out = np.diag([s, s, 1.0]) @ t
    return out / out[2, 2]


def camera(r: np.ndarray, focal: float = FOCAL) -> np.ndarray:
    k = np.diag([focal, focal, 1.0])
    return recentre(k @ np.asarray(r, np.float64) @ np.linalg.inv(k))


def keystone(vertical: float, horizontal: float, focal: float = FOCAL) -> np.ndarray:
    tx = math.radians(-vertical / 100.0 * KEYSTONE_MAX)
    ty = math.radians(horizontal / 100.0 * KEYSTONE_MAX)
    if tx == 0.0 and ty == 0.0:
        return np.eye(3)
    return camera(rot_x(tx) @ rot_y(ty), focal)


def manual(geo: dict) -> np.ndarray:
    rot = rot_z(math.radians(_num(geo.get("rotate"))))
    key = keystone(_num(geo.get("vertical")), _num(geo.get("horizontal")))
    a = _num(geo.get("aspect")) / 100.0 * ASPECT_MAX
    asp = np.diag([2.0 ** -a, 2.0 ** a, 1.0])
    k = max(0.01, _num(geo.get("scale"), 100.0) / 100.0)
    off = np.array([[1.0, 0.0, _num(geo.get("offsetX")) / 100.0 * OFFSET_FULL], [0.0, 1.0, -_num(geo.get("offsetY")) / 100.0 * OFFSET_FULL], [0.0, 0.0, 1.0]])
    return off @ np.diag([k, k, 1.0]) @ asp @ key @ rot


def _upright_matrix(geo: dict) -> np.ndarray:
    mode = geo.get("upright")
    vals = geo.get("uprightTransform")
    if not mode or mode == "off" or not isinstance(vals, (list, tuple)) or len(vals) != 9:
        return np.eye(3)
    m = np.array([_num(v, math.nan) for v in vals], np.float64).reshape(3, 3)
    if not np.all(np.isfinite(m)) or abs(np.linalg.det(m)) < 1e-12:
        return np.eye(3)
    return m


def crop_fit_angle(w: float, h: float, angle: float, aspect: float | None = None) -> list[float]:
    w, h = max(float(w), 1e-9), max(float(h), 1e-9)
    asp = float(aspect) if aspect else w / h
    t = math.radians(float(angle))
    c, s = abs(math.cos(t)), abs(math.sin(t))
    a = min((w / 2.0) / (c + s / asp), (h / 2.0) / (s + c / asp))
    b = a / asp
    return [0.5 - a / w, 0.5 - b / h, 0.5 + a / w, 0.5 + b / h]


@njit(cache=True, inline="always")
def _to_src(x, y, t, sw, sh):
    if t == 0:
        return x, y
    if t == 1:
        return y, sh - x
    if t == 2:
        return sw - x, sh - y
    return sw - y, x


@njit(cache=True, inline="always")
def _from_src(x, y, t, sw, sh):
    if t == 0:
        return x, y
    if t == 1:
        return sh - y, x
    if t == 2:
        return sw - x, sh - y
    return y, sw - x


@njit(cache=True, inline="always")
def _common(x, y, p):
    cx, cy = p[0], p[1]
    dx, dy = x - cx, y - cy
    if p[3] != 0.0:
        f = 1.0 + p[3] * (dx * dx + dy * dy) / (p[2] * p[2])
        dx *= f
        dy *= f
    if p[7] != 0.0:
        t, sw, sh = int(p[4]), p[5], p[6]
        sx, sy = _to_src(cx + dx, cy + dy, t, sw, sh)
        xd, yd = sx - 0.5, sy - 0.5
        m = p[16]
        ux, uy = (xd - p[14]) / m, (yd - p[15]) / m
        r2 = ux * ux + uy * uy
        f = p[8] + r2 * (p[9] + r2 * (p[10] + r2 * p[11]))
        tx = p[12] * 2.0 * ux * uy + p[13] * (r2 + 2.0 * ux * ux)
        ty = p[13] * 2.0 * ux * uy + p[12] * (r2 + 2.0 * uy * uy)
        wx = p[14] + m * (f * ux + tx)
        wy = p[15] + m * (f * uy + ty)
        xd += p[17] * (wx - xd)
        yd += p[17] * (wy - yd)
        ox, oy = _from_src(xd + 0.5, yd + 0.5, t, sw, sh)
        dx, dy = ox - cx, oy - cy
    elif p[18] != 0.0:
        r = math.sqrt(dx * dx + dy * dy) * p[23]
        model = int(p[18])
        if model == 1:
            f = p[19] * r * r * r + p[20] * r * r + p[21] * r + 1.0 - p[19] - p[20] - p[21]
        elif model == 2:
            f = 1.0 - p[19] + p[19] * r * r
        else:
            f = 1.0 + p[19] * r * r + p[20] * r * r * r * r
        f = 1.0 + p[22] * (f - 1.0)
        dx *= f
        dy *= f
    return dx, dy


@njit(cache=True, inline="always")
def _channel(dx, dy, ch, p):
    if p[24] != 0.0:
        o = 25 if ch == 0 else 28
        if p[24] == 1.0:
            f = p[o]
        else:
            r = math.sqrt(dx * dx + dy * dy) * p[23]
            f = p[o + 2] * r * r + p[o + 1] * r + p[o]
        dx *= f
        dy *= f
    k = p[31] if ch == 0 else p[32]
    return dx * k, dy * k


@njit(cache=True)
def _lens(x, y, ch, p):
    dx, dy = _common(x, y, p)
    if ch != 1:
        dx, dy = _channel(dx, dy, ch, p)
    return p[0] + dx, p[1] + dy


@njit(cache=True, inline="always")
def _power(v, e):
    v = max(v, 1e-6)
    return v if e == 1.0 else math.exp(e * math.log(v))


@njit(cache=True, inline="always")
def _dng_r2(x, y, p):
    sx, sy = _to_src(x, y, int(p[4]), p[5], p[6])
    ux, uy = sx - 0.5 - p[39], sy - 0.5 - p[40]
    return (ux * ux + uy * uy) / (p[41] * p[41])


@njit(cache=True, inline="always")
def _vig_dng(r2, p):
    return _power(1.0 + r2 * (p[34] + r2 * (p[35] + r2 * (p[36] + r2 * (p[37] + r2 * p[38])))), p[42])


@njit(cache=True, inline="always")
def _vig_centre(u, p):
    g = 1.0
    if p[43] != 0.0:
        r2 = u * p[2] * p[2] * p[47] * p[47]
        g /= _power(1.0 + r2 * (p[44] + r2 * (p[45] + r2 * p[46])), p[48])
    if p[49] != 0.0:
        t = min(max((math.sqrt(u) - p[51]) / (1.0 - p[51]), 0.0), 1.0)
        g *= math.exp(p[50] * t * t * LN2)
    return g


@njit(cache=True, inline="always")
def _vig(x, y, p):
    g = 1.0
    if p[33] != 0.0:
        g *= _vig_dng(_dng_r2(x, y, p), p)
    if p[43] != 0.0 or p[49] != 0.0:
        g *= _vig_centre(((x - p[0]) ** 2 + (y - p[1]) ** 2) / (p[2] * p[2]), p)
    return g


@njit(cache=True)
def _lens_points(x, y, ch, p, ox, oy):
    for i in range(x.shape[0]):
        ox[i], oy[i] = _lens(x[i], y[i], ch, p)


@njit(cache=True)
def _gain_points(x, y, p, g):
    for i in range(x.shape[0]):
        g[i] = _vig(x[i], y[i], p)


@njit(cache=True)
def _tables(p):
    n = TABLE_N
    tc, td = np.ones(n), np.ones(n)
    for k in range(n):
        u = k * TABLE_MAX / (n - 1)
        if p[43] != 0.0 or p[49] != 0.0:
            tc[k] = _vig_centre(u, p)
        if p[33] != 0.0:
            td[k] = _vig_dng(u, p)
    return tc, td


@njit(cache=True, inline="always")
def _lookup(t, u):
    f = u * ((TABLE_N - 1) / TABLE_MAX)
    if f >= TABLE_N - 1:
        return t[TABLE_N - 1]
    i = int(f)
    return t[i] + (f - i) * (t[i + 1] - t[i])


@njit(cache=True, parallel=True, fastmath=FAST)
def _maps(row0, rows, a, hi, geo, p, q, tc, td, mx, my, inside, gain):
    nch, w = mx.shape[0], mx.shape[2]
    ow, oh, l, hom, lim_w, lim_h, need = geo[0], geo[1], geo[2], geo[3], geo[4], geo[5], geo[6]
    for j in prange(rows):
        gy = row0 + j + 0.5
        for i in range(w):
            gx = i + 0.5
            x = a[0] * gx + a[1] * gy + a[2]
            y = a[3] * gx + a[4] * gy + a[5]
            ok = True
            if hom != 0.0:
                u = (x - ow * 0.5) / l
                v = (y - oh * 0.5) / l
                d = hi[6] * u + hi[7] * v + hi[8]
                if d <= 1e-9:
                    ok = False
                else:
                    x = (hi[0] * u + hi[1] * v + hi[2]) / d * l + ow * 0.5
                    y = (hi[3] * u + hi[4] * v + hi[5]) / d * l + oh * 0.5
            dx, dy = 0.0, 0.0
            if ok:
                dx, dy = _common(x, y, p)
                ok = -EDGE <= p[0] + dx <= ow + EDGE and -EDGE <= p[1] + dy <= oh + EDGE
            gox, goy = p[0] + dx, p[1] + dy
            inside[j, i] = ok
            if not ok:
                for c in range(nch):
                    mx[c, j, i] = 0.0
                    my[c, j, i] = 0.0
                if need != 0.0:
                    gain[j, i] = 1.0
                continue
            for c in range(nch):
                ox, oy = gox, goy
                if nch == 3 and c != 1:
                    rx, ry = _channel(dx, dy, c, p)
                    ox, oy = p[0] + rx, p[1] + ry
                sx = q[0] * ox + q[1] * oy + q[2]
                sy = q[3] * ox + q[4] * oy + q[5]
                mx[c, j, i] = min(max(sx, -2.0), lim_w + 1.0)
                my[c, j, i] = min(max(sy, -2.0), lim_h + 1.0)
            if need != 0.0:
                g = _lookup(tc, (dx * dx + dy * dy) / (p[2] * p[2]))
                if p[33] != 0.0:
                    g *= _lookup(td, _dng_r2(gox, goy, p))
                gain[j, i] = g


@njit(cache=True, parallel=True)
def _blank_affine(out, a, ow, oh, b0, b1, b2):
    h, w = out.shape[0], out.shape[1]
    for j in prange(h):
        gy = j + 0.5
        for i in range(w):
            gx = i + 0.5
            x = a[0] * gx + a[1] * gy + a[2]
            y = a[3] * gx + a[4] * gy + a[5]
            if x < -EDGE or x > ow + EDGE or y < -EDGE or y > oh + EDGE:
                out[j, i, 0] = b0
                out[j, i, 1] = b1
                out[j, i, 2] = b2


@njit(cache=True, parallel=True)
def _finish(out, inside, gain, need, b0, b1, b2):
    h, w = inside.shape
    for j in prange(h):
        for i in range(w):
            if not inside[j, i]:
                out[j, i, 0] = b0
                out[j, i, 1] = b1
                out[j, i, 2] = b2
            elif need:
                g = gain[j, i]
                out[j, i, 0] *= g
                out[j, i, 1] *= g
                out[j, i, 2] *= g


def _quarter(turns: int, sw: float, sh: float) -> np.ndarray:
    return [np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]), np.array([[0.0, 1.0, 0.0], [-1.0, 0.0, sh], [0.0, 0.0, 1.0]]),
            np.array([[-1.0, 0.0, sw], [0.0, -1.0, sh], [0.0, 0.0, 1.0]]), np.array([[0.0, -1.0, sw], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])][turns]


def _shift(dx: float, dy: float) -> np.ndarray:
    return np.array([[1.0, 0.0, dx], [0.0, 1.0, dy], [0.0, 0.0, 1.0]])


class Frame:
    def __init__(self, src_w: int, src_h: int, dev: dict, apply_crop: bool = True) -> None:
        dev = dev if isinstance(dev, dict) else {}
        self.src_w, self.src_h = int(src_w), int(src_h)
        self.turns = int(_num(dev.get("orientation"))) % 4
        self.ow, self.oh = (float(self.src_w), float(self.src_h)) if self.turns % 2 == 0 else (float(self.src_h), float(self.src_w))
        self.rect, self.angle, self.flip_h, self.flip_v = [0.0, 0.0, 1.0, 1.0], 0.0, False, False
        crop = dev.get("crop") if apply_crop else None
        if isinstance(crop, dict):
            r = crop.get("rect")
            if isinstance(r, (list, tuple)) and len(r) == 4 and all(math.isfinite(_num(v, math.nan)) for v in r) and r[2] > r[0] and r[3] > r[1]:
                self.rect = [float(v) for v in r]
            self.angle = _num(crop.get("angle"))
            self.flip_h, self.flip_v = crop.get("flipH") is True, crop.get("flipV") is True
        geo = dev.get("geometry") if section_enabled(dev, "geometry") else None
        geo = geo if isinstance(geo, dict) else {}
        persp = manual(geo) @ _upright_matrix(geo)
        self.persp = persp / persp[2, 2] if abs(persp[2, 2]) > 1e-12 else np.eye(3)
        self._hom = not np.allclose(self.persp, np.eye(3), rtol=0.0, atol=1e-12)
        self._hinv = np.linalg.inv(self.persp) if self._hom else np.eye(3)
        opt = dev.get("optics") if section_enabled(dev, "optics") else None
        self._lens_setup(opt if isinstance(opt, dict) else {})
        if apply_crop and geo.get("constrainCrop") is True and self.moves_pixels():
            self.rect = self._constrain(self.rect)

    def _lens_setup(self, opt: dict) -> None:
        p = np.zeros(NP, np.float64)
        ow, oh = self.ow, self.oh
        diag = math.hypot(ow, oh)
        p[0], p[1], p[2] = ow / 2.0, oh / 2.0, diag / 2.0
        p[3] = -_num(opt.get("distortion")) / 100.0 * DISTORTION_MAX
        p[4], p[5], p[6] = self.turns, self.src_w, self.src_h
        p[31] = (1.0 + _num(opt.get("autoCaRed"))) * (1.0 + _num(opt.get("caRed")) / 100.0 * CA_FULL)
        p[32] = (1.0 + _num(opt.get("autoCaBlue"))) * (1.0 + _num(opt.get("caBlue")) / 100.0 * CA_FULL)
        amount = _num(opt.get("vignetting")) / 100.0 * VIGNETTE_STOPS
        if amount != 0.0:
            p[49], p[50] = 1.0, amount
            p[51] = min(max(_num(opt.get("vignettingMidpoint"), 50.0), 0.0), 100.0) / 100.0 * VIGNETTE_REACH
        prof = opt.get("profile")
        if isinstance(prof, dict) and prof.get("enabled") is True:
            self._profile(p, prof, _num(opt.get("profileDistortion"), 100.0) / 100.0, _num(opt.get("profileVignetting"), 100.0) / 100.0,
                          opt.get("removeCa") is True, diag)
        self._p = p
        self._channels = p[24] != 0.0 or p[31] != 1.0 or p[32] != 1.0
        self._moves = self._hom or p[3] != 0.0 or p[7] != 0.0 or p[18] != 0.0 or self._channels
        self._vig_on = p[33] != 0.0 or p[43] != 0.0 or p[49] != 0.0

    def _dng_centre(self, cx: float, cy: float) -> tuple[float, float, float]:
        x1, y1 = self.src_w - 1.0, self.src_h - 1.0
        px, py = cx * x1, cy * y1
        return px, py, max(math.hypot(max(abs(px), abs(x1 - px)), max(abs(py), abs(y1 - py))), 1e-9)

    def _profile(self, p: np.ndarray, prof: dict, dist_amt: float, vig_pow: float, remove_ca: bool, diag: float) -> None:
        warp = prof.get("warp")
        lf = prof.get("lensfun") if isinstance(prof.get("lensfun"), dict) else {}
        if isinstance(warp, dict) and dist_amt != 0.0:
            kr = [_num(v, d) for v, d in zip(list(warp.get("kr") or [])[:4] + [None] * 4, (1.0, 0.0, 0.0, 0.0))]
            kt = [_num(v) for v in list(warp.get("kt") or [])[:2] + [None] * 2][:2]
            if kr != [1.0, 0.0, 0.0, 0.0] or kt != [0.0, 0.0]:
                cx, cy, m = self._dng_centre(_num(warp.get("cx"), 0.5), _num(warp.get("cy"), 0.5))
                p[7] = 1.0
                p[8:12], p[12:14] = kr, kt
                p[14], p[15], p[16], p[17] = cx, cy, m, dist_amt
        scale = _num(lf.get("hugin"), 0.0) / diag if diag > 0 else 0.0
        p[23] = scale
        dist = lf.get("dist")
        if p[7] == 0.0 and isinstance(dist, dict) and dist_amt != 0.0 and scale > 0.0:
            model = {"ptlens": 1.0, "poly3": 2.0, "poly5": 3.0}.get(str(dist.get("model")), 0.0)
            coef = {1.0: ("a", "b", "c"), 2.0: ("k1",), 3.0: ("k1", "k2")}.get(model, ())
            vals = [_num(dist.get(k)) for k in coef]
            if model and any(v != 0.0 for v in vals):
                p[18] = model
                p[19:19 + len(vals)] = vals
                p[22] = dist_amt
        tca = lf.get("tca")
        if remove_ca and isinstance(tca, dict) and scale > 0.0:
            if tca.get("model") == "linear":
                kr, kb = _num(tca.get("kr"), 1.0), _num(tca.get("kb"), 1.0)
                if kr != 1.0 or kb != 1.0:
                    p[24], p[25], p[28] = 1.0, kr, kb
            elif tca.get("model") == "poly3":
                red = [_num(tca.get("vr"), 1.0), _num(tca.get("cr")), _num(tca.get("br"))]
                blue = [_num(tca.get("vb"), 1.0), _num(tca.get("cb")), _num(tca.get("bb"))]
                if red != [1.0, 0.0, 0.0] or blue != [1.0, 0.0, 0.0]:
                    p[24] = 2.0
                    p[25:28], p[28:31] = red, blue
        vig = prof.get("vignette")
        if isinstance(vig, dict) and vig_pow != 0.0:
            k = ([_num(v) for v in (vig.get("k") or [])] + [0.0] * 5)[:5]
            if any(v != 0.0 for v in k):
                cx, cy, m = self._dng_centre(_num(vig.get("cx"), 0.5), _num(vig.get("cy"), 0.5))
                p[33] = 1.0
                p[34:39] = k
                p[39], p[40], p[41], p[42] = cx, cy, m, vig_pow
        lv = lf.get("vig")
        pa = _num(lf.get("pa"), 0.0) / diag if diag > 0 else 0.0
        if p[33] == 0.0 and isinstance(lv, (list, tuple)) and len(lv) >= 3 and vig_pow != 0.0 and pa > 0.0:
            k = [_num(v) for v in lv[:3]]
            if any(v != 0.0 for v in k):
                p[43], p[44:47], p[47], p[48] = 1.0, k, pa, vig_pow

    def moves_pixels(self) -> bool:
        return bool(self._moves)

    def has_warp(self) -> bool:
        return bool(self._moves or self._vig_on)

    def rect_px(self) -> tuple[float, float, float, float]:
        x0, y0, x1, y1 = self.rect
        return x0 * self.ow, y0 * self.oh, x1 * self.ow, y1 * self.oh

    def native_size(self) -> tuple[float, float]:
        x0, y0, x1, y1 = self.rect
        return (x1 - x0) * self.ow, (y1 - y0) * self.oh

    def aspect(self) -> float:
        w, h = self.native_size()
        return max(w, 1e-9) / max(h, 1e-9)

    def fit(self, max_w: float, max_h: float) -> tuple[int, int]:
        nw, nh = (max(v, 1e-9) for v in self.native_size())
        s = min(max_w / nw, max_h / nh)
        return max(1, min(int(max_w), round(nw * s))), max(1, min(int(max_h), round(nh * s)))

    def fit_long(self, long: int | None) -> tuple[int, int]:
        nw, nh = self.native_size()
        if long is None or max(nw, nh) <= long:
            return max(1, round(nw)), max(1, round(nh))
        return self.fit(long, long)

    def px_per_long(self, out_w: float) -> float:
        return float(out_w) / max(self.native_size()[0], 1e-9) * max(self.ow, self.oh)

    def out_to_oriented(self, w: float, h: float) -> np.ndarray:
        m = np.eye(3)
        if self.flip_h:
            m = np.array([[-1.0, 0.0, float(w)], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]) @ m
        if self.flip_v:
            m = np.array([[1.0, 0.0, 0.0], [0.0, -1.0, float(h)], [0.0, 0.0, 1.0]]) @ m
        x0, y0, x1, y1 = self.rect
        m = np.array([[(x1 - x0) * self.ow / w, 0.0, x0 * self.ow], [0.0, (y1 - y0) * self.oh / h, y0 * self.oh], [0.0, 0.0, 1.0]]) @ m
        cx, cy = self.ow / 2.0, self.oh / 2.0
        return _shift(cx, cy) @ rot_z(math.radians(-self.angle)) @ _shift(-cx, -cy) @ m

    def out_to_norm(self, w: float, h: float) -> np.ndarray:
        return np.diag([1.0 / self.ow, 1.0 / self.oh, 1.0]) @ self.out_to_oriented(w, h)

    def norm_to_out(self, w: float, h: float) -> np.ndarray:
        return np.linalg.inv(self.out_to_norm(w, h))

    def _corrected(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        x, y = np.asarray(x, np.float64), np.asarray(y, np.float64)
        if not self._hom:
            return x, y, np.ones(np.broadcast(x, y).shape, bool)
        l = max(self.ow, self.oh) / 2.0
        u, v = (x - self.ow / 2.0) / l, (y - self.oh / 2.0) / l
        m = self._hinv
        d = m[2, 0] * u + m[2, 1] * v + m[2, 2]
        safe = np.where(np.abs(d) < 1e-12, 1e-12, d)
        return (m[0, 0] * u + m[0, 1] * v + m[0, 2]) / safe * l + self.ow / 2.0, (m[1, 0] * u + m[1, 1] * v + m[1, 2]) / safe * l + self.oh / 2.0, d > 1e-9

    def to_corrected(self, x, y) -> tuple[np.ndarray, np.ndarray]:
        if not self._hom:
            return x, y
        cx, cy, _ = self._corrected(x, y)
        return cx, cy

    def corrected_to_source(self, x, y, ch: int) -> tuple[np.ndarray, np.ndarray]:
        x, y = np.broadcast_arrays(np.asarray(x, np.float64), np.asarray(y, np.float64))
        fx, fy = np.ascontiguousarray(x).reshape(-1), np.ascontiguousarray(y).reshape(-1)
        ox, oy = np.empty_like(fx), np.empty_like(fy)
        _lens_points(fx, fy, int(ch), self._p, ox, oy)
        return ox.reshape(x.shape), oy.reshape(y.shape)

    def gain(self, x, y) -> np.ndarray | None:
        if not self._vig_on:
            return None
        x, y = np.broadcast_arrays(np.asarray(x, np.float64), np.asarray(y, np.float64))
        g = np.empty(x.size, np.float64)
        _gain_points(np.ascontiguousarray(x).reshape(-1), np.ascontiguousarray(y).reshape(-1), self._p, g)
        return g.reshape(x.shape).astype(np.float32)

    def to_source_px(self, ox, oy, sw: float, sh: float) -> tuple:
        if self.turns == 0:
            return ox, oy
        if self.turns == 1:
            return oy, sh - ox
        if self.turns == 2:
            return sw - ox, sh - oy
        return sw - oy, ox

    def _trace(self, m: np.ndarray, x: np.ndarray, y: np.ndarray, tol: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        tx = m[0, 0] * x + m[0, 1] * y + m[0, 2]
        ty = m[1, 0] * x + m[1, 1] * y + m[1, 2]
        lx, ly, ok = self._corrected(tx, ty)
        ox, oy = self.corrected_to_source(lx, ly, 1)
        ok = ok & (ox >= -tol) & (ox <= self.ow + tol) & (oy >= -tol) & (oy <= self.oh + tol)
        return ox, oy, ok

    def _constrain(self, rect: list[float]) -> list[float]:
        x0, y0, x1, y1 = rect
        cx, cy, hw, hh = (x0 + x1) / 2.0, (y0 + y1) / 2.0, (x1 - x0) / 2.0, (y1 - y0) / 2.0
        t = np.linspace(-1.0, 1.0, BORDER_POINTS + 1)
        bx = np.concatenate([t, np.ones_like(t), -t, -np.ones_like(t)])
        by = np.concatenate([-np.ones_like(t), t, np.ones_like(t), -t])
        m = _shift(self.ow / 2.0, self.oh / 2.0) @ rot_z(math.radians(-self.angle)) @ _shift(-self.ow / 2.0, -self.oh / 2.0) @ np.diag([self.ow, self.oh, 1.0])

        def fits(k: float) -> bool:
            return bool(np.all(self._trace(m, cx + bx * hw * k, cy + by * hh * k, 1e-6)[2]))
        if fits(1.0):
            return rect
        lo, hi = MIN_CROP, 1.0
        if fits(lo):
            for _ in range(CONSTRAIN_STEPS):
                mid = (lo + hi) / 2.0
                if fits(mid):
                    lo = mid
                else:
                    hi = mid
        return [cx - hw * lo, cy - hh * lo, cx + hw * lo, cy + hh * lo]

    def _source_affine(self, arr_w: int, arr_h: int) -> np.ndarray:
        return np.diag([arr_w / self.src_w, arr_h / self.src_h, 1.0]) @ _quarter(self.turns, float(self.src_w), float(self.src_h))

    def _prepare(self, src: np.ndarray, w: int, h: int) -> tuple[np.ndarray, np.ndarray] | None:
        ah, aw = src.shape[:2]
        base = self._source_affine(aw, ah)
        a = self.out_to_oriented(w, h)
        gx, gy = np.meshgrid(np.linspace(0.5, w - 0.5, 17), np.linspace(0.5, h - 0.5, 17))
        sx, sy, ok = self._trace_src(a, base, gx, gy)
        if not ok.any():
            return None
        ratio = self._ratio(a, base, gx[ok], gy[ok], sx[ok], sy[ok])
        if ratio <= AREA_RATIO:
            return src, _shift(-0.5, -0.5) @ base
        margin = 4.0 + 2.0 * ratio
        bx0 = int(max(0, math.floor(sx[ok].min() - margin - 0.01 * aw)))
        by0 = int(max(0, math.floor(sy[ok].min() - margin - 0.01 * ah)))
        bx1 = int(min(aw, math.ceil(sx[ok].max() + margin + 0.01 * aw)))
        by1 = int(min(ah, math.ceil(sy[ok].max() + margin + 0.01 * ah)))
        if bx1 <= bx0 or by1 <= by0:
            return src, _shift(-0.5, -0.5) @ base
        nw, nh = max(1, round((bx1 - bx0) / ratio)), max(1, round((by1 - by0) / ratio))
        small = cv2.resize(src[by0:by1, bx0:bx1], (nw, nh), interpolation=cv2.INTER_AREA)
        z = np.diag([nw / (bx1 - bx0), nh / (by1 - by0), 1.0]) @ _shift(-bx0, -by0)
        return small, _shift(-0.5, -0.5) @ z @ base

    def _trace_src(self, a: np.ndarray, base: np.ndarray, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        ox, oy, ok = self._trace(a, x, y, EDGE)
        return base[0, 0] * ox + base[0, 1] * oy + base[0, 2], base[1, 0] * ox + base[1, 1] * oy + base[1, 2], ok

    def _ratio(self, a: np.ndarray, base: np.ndarray, gx: np.ndarray, gy: np.ndarray, sx: np.ndarray, sy: np.ndarray) -> float:
        ux, uy, _ = self._trace_src(a, base, gx + 1.0, gy)
        vx, vy, _ = self._trace_src(a, base, gx, gy + 1.0)
        det = np.abs((ux - sx) * (vy - sy) - (uy - sy) * (vx - sx))
        return float(np.sqrt(np.median(det))) if det.size else 1.0

    def sample(self, src: np.ndarray, w: int, h: int) -> np.ndarray:
        w, h = max(1, int(w)), max(1, int(h))
        prep = self._prepare(src, w, h)
        if prep is None:
            return np.broadcast_to(np.array(BLANK, np.float32), (h, w, 3)).copy()
        img, q = prep
        if not self.has_warp():
            return self._sample_affine(img, q, w, h)
        return self._sample_warp(img, q, w, h)

    def _sample_affine(self, img: np.ndarray, q: np.ndarray, w: int, h: int) -> np.ndarray:
        a = self.out_to_oriented(w, h)
        m = q @ a @ _shift(0.5, 0.5)
        out = cv2.warpAffine(img, m[:2], (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
        out = np.ascontiguousarray(out, np.float32)
        cx = np.array([0.5, w - 0.5, 0.5, w - 0.5])
        cy = np.array([0.5, 0.5, h - 0.5, h - 0.5])
        ox, oy = a[0, 0] * cx + a[0, 1] * cy + a[0, 2], a[1, 0] * cx + a[1, 1] * cy + a[1, 2]
        if not np.all((ox >= -EDGE) & (ox <= self.ow + EDGE) & (oy >= -EDGE) & (oy <= self.oh + EDGE)):
            _blank_affine(out, np.ascontiguousarray(a[:2].reshape(-1)), self.ow, self.oh, BLANK[0], BLANK[1], BLANK[2])
        return out

    def _sample_warp(self, img: np.ndarray, q: np.ndarray, w: int, h: int) -> np.ndarray:
        a = self.out_to_oriented(w, h)
        nch = 3 if self._channels else 1
        ih, iw = img.shape[:2]
        geo = np.array([self.ow, self.oh, max(self.ow, self.oh) / 2.0, 1.0 if self._hom else 0.0, iw - 1.0, ih - 1.0, 1.0 if self._vig_on else 0.0])
        a6, h9, q6 = np.ascontiguousarray(a[:2].reshape(-1)), np.ascontiguousarray(self._hinv.reshape(-1)), np.ascontiguousarray(q[:2].reshape(-1))
        tc, td = _tables(self._p) if self._vig_on else (np.ones(TABLE_N), np.ones(TABLE_N))
        img = np.ascontiguousarray(img, np.float32)
        band = min(h, max(1, BAND_PIXELS // w))
        out = np.empty((h, w, 3), np.float32)
        mx, my = np.empty((nch, band, w), np.float32), np.empty((nch, band, w), np.float32)
        inside = np.empty((band, w), np.bool_)
        gain = np.empty((band, w) if self._vig_on else (1, 1), np.float32)
        tmp = np.empty((band, w, 3), np.float32) if nch == 3 else None
        for r0 in range(0, h, band):
            n = min(h, r0 + band) - r0
            part = out[r0:r0 + n]
            _maps(float(r0), n, a6, h9, geo, self._p, q6, tc, td, mx, my, inside, gain)
            if tmp is None:
                cv2.remap(img, mx[0, :n], my[0, :n], cv2.INTER_LINEAR, dst=part, borderMode=cv2.BORDER_REPLICATE)
            else:
                for c in range(3):
                    cv2.remap(img, mx[c, :n], my[c, :n], cv2.INTER_LINEAR, dst=tmp[:n], borderMode=cv2.BORDER_REPLICATE)
                    part[..., c] = tmp[:n, :, c]
            _finish(part, inside[:n], gain[:n] if self._vig_on else gain, self._vig_on, BLANK[0], BLANK[1], BLANK[2])
        return out
