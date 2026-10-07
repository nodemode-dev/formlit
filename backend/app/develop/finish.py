import math

import cv2
import numpy as np

from app.develop import colour, colorops as co, curves as cv, planes as pl, settings as S

K1, K2 = 2.3892, 0.8552
SAT_GAIN = 1.15
HL_K, HL_W = 0.62, 0.6
SH_K, SH_W, SH_MAX = 0.9, 0.7, 2.6
WH_K, WH_W = 0.85, 0.5
BL_K, BL_W, BL_CLIP = 0.75, 0.6, 0.035
CON_K = 0.45
CLA_K, CLA_W, CLA_NEG = 1.1, 2.2, 0.75
TEX_K, TEX_POS, TEX_NEG = 1.6, 0.35, 0.22
SHARP_K = 1.6
DH_OMEGA, DH_TMIN, DH_K, DH_SAT, DH_FLOOR = 0.95, 0.2, 0.7, 0.9, 0.03
HAZE_ADD = (0.25, 0.75, 0.85)
VIG_STOPS = 2.0
GRAIN_SIGMA = 0.075
GRAIN_REF = 6000.0
ROWS = 192
E_HL, E_SH, E_WH, E_BL, E_MID, E_AIR = 0.62, 0.35, 0.82, 0.18, 0.50, 0.92
NL = 17
L_EXP, L_CON, L_HL, L_SH, L_WH, L_BL, L_TEX, L_CLA, L_DHZ, L_SAT, L_HUE, L_SHP, L_NZ, L_MO, L_DF, L_TA, L_TB = range(NL)
LOCAL_KEYS = ("exposure", "contrast", "highlights", "shadows", "whites", "blacks", "texture", "clarity", "dehaze", "saturation")
STYLES = {"highlightPriority": 0, "colorPriority": 1, "paintOverlay": 2}
SPACES = ("srgb", "p3", "rec2020", "adobergb", "prophoto", "linear")
NG = 22
KNEE = 0.8
PREFILTER = 0.5
GAMUT_TOL = 1e-3
TRC_TOE = 4e-6
NZ_RATIO = 0.6
FRINGE_EDGE = (0.02, 0.12)
FRINGE_HUES = (math.radians(315.0), math.radians(35.0), math.radians(140.0), math.radians(25.0))
VIB_SKIN, VIB_NEG = 0.6, 0.5
VIG_PAINT, VIG_PROTECT = 0.85, 0.45
VIG_SHAPE = (2.0, 6.0, 1.6, 0.9, 0.02)
GRAIN_MID = (0.25, 3.0)
NH = 2048
GRAIN_OCT = (0.55, 0.25, 0.75)
SHARP_CORE, SHARP_CLAMP, SHARP_MASK = (0.012, 1e-4), (0.06, 0.45), (0.004, 0.14)


def _num(v, d: float = 0.0) -> float:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else d


class Plan:
    pass


def _v_at(e_lut: np.ndarray, e: float) -> float:
    i = int(np.searchsorted(e_lut, e))
    i = min(max(i, 1), len(e_lut) - 1)
    lo, hi = float(e_lut[i - 1]), float(e_lut[i])
    f = 0.0 if hi <= lo else (e - lo) / (hi - lo)
    return cv.VMIN + (i - 1 + f) * (cv.VMAX - cv.VMIN) / (len(e_lut) - 1)


def base_knots(dev: dict, info: dict) -> tuple[list | None, np.ndarray | None]:
    if not info.get("raw"):
        return None, None
    pid = str((dev.get("profile") or {}).get("id", "") or "")
    if pid.startswith("dcp:"):
        from app.develop import dcp
        prof = dcp.load(pid[4:])
        if prof:
            k = dcp.tone_knots(prof, None if info.get("ownBaseline") else info.get("cameraTone"))
            if cv.valid_knots(k) is not None:
                return k, None
    look = info.get("cameraLook")
    if pid.startswith("fl.camera") and isinstance(look, dict) and cv.valid_knots(look.get("tone")) is not None:
        m = look.get("matrix")
        try:
            m = np.asarray(m, np.float64).reshape(3, 3) if m is not None else None
        except (TypeError, ValueError):
            m = None
        if m is not None and not np.all(np.isfinite(m)):
            m = None
        return look["tone"], m
    if cv.valid_knots(info.get("cameraTone")) is not None:
        return info["cameraTone"], None
    return cv.generic_knots(), None


def _out_matrix(space: str) -> np.ndarray:
    return np.eye(3) if space in ("rec2020", "linear") else colour.working_to(space)


def _local_rows(evaluated: list) -> tuple:
    rows, wbs, alphas, curves, points = [], [], [], [], []
    for alpha, mask, _ in evaluated or []:
        adj = mask.get("adjust") if isinstance(mask, dict) else None
        adj = adj if isinstance(adj, dict) else {}
        amt = min(max(_num(adj.get("amount"), 100.0), 0.0), 200.0) / 100.0
        if amt <= 0 or alpha is None:
            continue
        r = np.zeros(NL)
        r[L_EXP] = _num(adj.get("exposure"))
        for k, key in enumerate(LOCAL_KEYS[1:], start=1):
            r[k] = _num(adj.get(key)) / 100.0
        r[L_HUE] = math.radians(_num(adj.get("hue")))
        r[L_SHP] = _num(adj.get("sharpness")) / 100.0
        r[L_NZ] = _num(adj.get("noise")) / 100.0
        r[L_MO] = max(_num(adj.get("moire")) / 100.0, 0.0)
        r[L_DF] = max(_num(adj.get("defringe")) / 100.0, 0.0)
        cs = min(max(_num(adj.get("colorSat")), 0.0), 100.0) / 100.0
        if cs:
            ca, sa = co.wheel_dir(_num(adj.get("colorHue")))
            r[L_TA], r[L_TB] = cs * co.TINT_LOCAL * ca, cs * co.TINT_LOCAL * sa
        wb = co.local_wb(_num(adj.get("temp")) / 100.0, _num(adj.get("tint")) / 100.0)
        crv = adj.get("curve") if isinstance(adj.get("curve"), dict) else {}
        luts = [cv.point_lut(crv.get(ch)) for ch in S.CURVE_CHANNELS]
        pts = co.point_table(adj.get("pointColors"))
        if not np.any(r) and wb is None and all(x is None for x in luts) and pts is None:
            continue
        rows.append(r)
        wbs.append(np.zeros((3, 3)) if wb is None else wb - np.eye(3))
        a = np.asarray(alpha, np.float32)
        alphas.append(a if amt == 1.0 else a * np.float32(amt))
        curves.append(luts)
        points.append(pts)
    return rows, wbs, alphas, curves, points


def prepare(lin: np.ndarray, planes: dict, dev: dict, frame, info: dict, out_w: int, out_h: int, ppl: float, evaluated: list,
            space: str = "srgb", region=(0, 0)) -> Plan:
    from app.develop import profiles
    info = info or {}
    dev = dev or {}
    planes = planes if isinstance(planes, dict) else {}
    space = space if space in SPACES else "srgb"
    h, w = lin.shape[:2]
    p = Plan()
    p.space = space
    p.h, p.w = h, w
    raw = bool(info.get("raw"))
    knots, look = base_knots(dev, info)
    p.tone_e, p.tone_g = cv.tone_lut(knots, raw)
    p.sat_gain = SAT_GAIN if raw else 1.0
    p.sat_lut = _mantiuk(p.tone_g.astype(np.float64), p.sat_gain).astype(np.float32)
    p.v_hl, p.v_sh = _v_at(p.tone_e, E_HL), _v_at(p.tone_e, E_SH)
    p.v_wh, p.v_bl = _v_at(p.tone_e, E_WH), _v_at(p.tone_e, E_BL)
    p.v_mid, p.v_air = _v_at(p.tone_e, E_MID), _v_at(p.tone_e, E_AIR)
    g = lambda cid: S.get(dev, cid)
    p.ev = g("light.exposure")
    p.con = g("light.contrast") / 100.0
    p.hl, p.sh = g("light.highlights") / 100.0, g("light.shadows") / 100.0
    p.wh, p.bl = g("light.whites") / 100.0, g("light.blacks") / 100.0
    p.tex, p.cla, p.dhz = g("effects.texture") / 100.0, g("effects.clarity") / 100.0, g("effects.dehaze") / 100.0
    p.vib, p.sat = g("color.vibrance") / 100.0, g("color.saturation") / 100.0
    cal = co.calibration(dev)
    m0 = np.eye(3)
    if look is not None:
        m0 = look @ m0
    if cal is not None:
        m0 = cal @ m0
    p.m0 = m0
    p.use_m0 = bool(not np.allclose(m0, np.eye(3), atol=1e-9))
    p.stint = co.shadow_tint(dev)
    curve_on = S.section_enabled(dev, "curve")
    crv = dev.get("curve") if isinstance(dev.get("curve"), dict) else {}
    par = cv.parametric_lut(crv) if curve_on else None
    p.par = par
    luts = [cv.point_lut(crv.get(ch)) if curve_on else None for ch in S.CURVE_CHANNELS]
    p.curves = luts
    p.ccurve = composite(luts[0], luts[1:])
    p.refine = g("curve.refineSaturation") / 100.0
    p.mixer = co.mixer_table(dev)
    mt = p.mixer
    p.mix_lut = hue_table(lambda i0, i1, w0, w1: np.stack([w0 * mt[i0, k] + w1 * mt[i1, k] for k in range(3)], axis=-1)) if mt is not None else None
    p.bw = dev.get("treatment") == "bw"
    p.bwt = co.bw_table(dev)
    bt = p.bwt
    p.bw_lut = hue_table(lambda i0, i1, w0, w1: w0 * bt[i0] + w1 * bt[i1]) if p.bw else None
    p.grade = co.grading_table(dev)
    p.gshape = co.grading_shape(dev)
    p.points = co.point_table(dev.get("pointColors")) if S.section_enabled(dev, "mixer") else None
    det_on = S.section_enabled(dev, "detail")
    full_long = float(max(_num(info.get("fullWidth"), 0.0), _num(info.get("fullHeight"), 0.0)) or ppl)
    scale = min(float(ppl) / max(full_long, 1.0), 4.0)
    p.scale = scale
    p.s_amt = g("detail.sharpenAmount") / 100.0 if det_on else 0.0
    p.s_rad = g("detail.sharpenRadius")
    p.s_det = g("detail.sharpenDetail") / 100.0
    p.s_mask = g("detail.sharpenMasking") / 100.0
    p.s_core = SHARP_CORE[0] * (1.0 - p.s_det) + SHARP_CORE[1]
    p.s_tcl = SHARP_CLAMP[0] + SHARP_CLAMP[1] * p.s_det
    p.s_thr = SHARP_MASK[0] + SHARP_MASK[1] * p.s_mask ** 2
    fx_on = S.section_enabled(dev, "effects")
    p.v_amt = g("vignette.amount") / 100.0 if fx_on else 0.0
    p.v_mid_r = 0.3 + 0.9 * g("vignette.midpoint") / 100.0
    p.v_round = g("vignette.roundness") / 100.0
    p.v_feather = g("vignette.feather") / 100.0
    p.v_hl = g("vignette.highlights") / 100.0
    p.v_style = STYLES.get(str((dev.get("vignette") or {}).get("style", "highlightPriority")), 0)
    p.v_pow = VIG_SHAPE[0] + VIG_SHAPE[1] * max(-p.v_round, 0.0) ** 1.5
    p.v_inner = p.v_mid_r * (1.0 - VIG_SHAPE[3] * p.v_feather)
    p.v_outer = p.v_mid_r + (VIG_SHAPE[2] - p.v_mid_r) * p.v_feather + VIG_SHAPE[4]
    p.g_amt = g("grain.amount") / 100.0 if fx_on else 0.0
    p.g_size = g("grain.size") / 100.0
    p.g_rough = g("grain.roughness") / 100.0
    p.out_w, p.out_h = int(out_w), int(out_h)
    p.rx, p.ry = int(region[0]), int(region[1])
    rows, wbs, alphas, mcurves, mpoints = _local_rows(evaluated)
    p.n_masks = len(rows)
    p.lrows = np.asarray(rows, np.float64).reshape(-1, NL)
    p.lwb = np.asarray(wbs, np.float64).reshape(-1, 3, 3)
    p.alphas = alphas
    p.mcurves = mcurves
    p.mccurve = [composite(c[0], c[1:]) for c in mcurves]
    p.mpoints = mpoints
    p.local_wb = bool(np.any(p.lwb))
    lr = p.lrows
    anyl = lambda k: bool(np.any(lr[:, k] != 0)) if len(lr) else False
    p.do_hl = bool(p.hl or anyl(L_HL))
    p.do_sh = bool(p.sh or anyl(L_SH))
    p.do_cla = bool(p.cla or anyl(L_CLA))
    p.do_tex = bool(p.tex or anyl(L_TEX))
    p.do_dhz = bool(p.dhz or anyl(L_DHZ))
    p.do_con = bool(p.con or anyl(L_CON))
    p.do_wh = bool(p.wh or anyl(L_WH))
    p.do_bl = bool(p.bl or anyl(L_BL))
    p.do_sat = bool(p.sat or anyl(L_SAT))
    p.do_hue = anyl(L_HUE)
    p.do_tint = anyl(L_TA) or anyl(L_TB)
    p.do_df = anyl(L_DF)
    p.do_soft = bool(len(lr) and np.any(lr[:, L_SHP] < 0))
    p.do_nz = bool(len(lr) and np.any(lr[:, L_NZ] > 0))
    p.do_ratio = anyl(L_MO) or p.do_nz
    p.do_sharp = bool((p.s_amt > 0 and det_on) or (len(lr) and np.any(lr[:, L_SHP] > 0)) or p.do_df)
    p.do_pts = p.points is not None or any(x is not None for x in mpoints)
    p.do_mcurve = any(any(x is not None for x in c) for c in mcurves)
    p.do_curve = any(x is not None for x in luts)
    p.do_lab = bool(p.mixer is not None or p.bw or p.grade is not None or p.vib or p.do_sat or p.do_hue or p.do_tint or p.do_pts or p.do_df)
    pts_hue = any(t is not None and bool(np.any(t[:, 3] != 0) or np.any(t[:, 6] != 0)) for t in [p.points, *mpoints])
    p.hue_mod = bool((p.mixer is not None and np.any(p.mixer[:, 0] != 0)) or pts_hue or p.do_hue)
    p.hs = planes.get("hs") if p.do_hl or p.do_sh else None
    p.dc = planes.get("dc") if p.do_cla else None
    p.dt = planes.get("dt") if p.do_tex else None
    p.hd = planes.get("hd") if p.do_dhz else None
    if p.do_hl or p.do_sh:
        p.hs = p.hs if p.hs is not None else pl.build(planes, lin, {"light": {"highlights": 1}}, ppl).get("hs")
    if p.do_cla and p.dc is None:
        p.dc = pl.build(planes, lin, {"effects": {"clarity": 1}}, ppl).get("dc")
    if p.do_tex and p.dt is None:
        p.dt = pl.build(planes, lin, {"effects": {"texture": 1}}, ppl).get("dt")
    if p.do_dhz and p.hd is None:
        p.hd = pl.build(planes, lin, {"effects": {"dehaze": 1}}, ppl).get("hd")
    p.ds = p.edge = None
    if p.do_sharp:
        sig = max(p.s_rad * scale * 0.85, 0.0)
        if sig >= 0.12:
            p.ds, p.edge = pl.sharp_detail(planes, lin, sig)
        else:
            p.do_sharp = p.do_df
            if p.do_df:
                p.ds, p.edge = pl.sharp_detail(planes, lin, 0.6)
    p.soft = pl.soft_detail(planes, lin, ppl) if p.do_soft else None
    p.nrd = pl.noise_detail(planes, lin, ppl) if p.do_nz else None
    p.ratio = pl.ratio_plane(planes, lin, ppl) if p.do_ratio else None
    p.air = cv.MID * 2.0 ** (p.v_air - p.ev)
    p.mout = _out_matrix(space)
    p.luma_out = colour.luma("rec2020" if space == "linear" else space).astype(np.float64)
    p.knee = KNEE if raw else 1.0
    _, i1, _, i2 = co.lab_mats()
    p.lab_out = (p.mout @ i1.astype(np.float64)).astype(np.float64)
    p.enc = cv.enc_lut("srgb")
    p.dec = cv.dec_lut("srgb")
    p.trc = trc_table(space)
    p.lut = None
    p.lut_amt = 0.0
    got = profiles.lut_of(dev, space)
    if got is not None:
        p.lut, p.lut_amt = np.ascontiguousarray(got[0], np.float32), float(got[1])
    p.do_vig = bool(p.v_amt)
    p.do_grain = p.g_amt > 0
    long_out = float(max(out_w, out_h, 1))
    cell = (0.7 + 3.2 * p.g_size ** 1.3) * long_out / GRAIN_REF
    p.g_cell = max(cell, 1.0)
    p.g_gain = GRAIN_SIGMA * p.g_amt * min(1.0, cell)
    return p


def _smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def softplus(z):
    return np.where(z > 20.0, z, np.log1p(np.exp(np.minimum(z, 20.0))))


def _mantiuk(gam, gain):
    gp = np.exp2(K2 * np.log2(np.maximum(gam, 1e-12)))
    return np.where(gam > 1e-9, (1.0 + K1) * gp / (1.0 + K1 * gp), 0.0) * gain


def composite(master, chans) -> list | None:
    if master is None and all(c is None for c in chans):
        return None
    u = np.linspace(0.0, 1.0, cv.NE)
    e = cv.srgb_enc(u ** 4)
    if master is not None:
        e = cv.lut1(e, master).astype(np.float64)
    out = []
    for c in chans:
        ec = cv.lut1(e, c).astype(np.float64) if c is not None else e
        out.append(cv.srgb_dec(ec).astype(np.float32))
    return out


def hue_table(fn) -> np.ndarray:
    h = np.linspace(0.0, 2.0 * np.pi, NH + 1)
    i0, i1, w0, w1 = co._segment(h)
    return np.asarray(fn(i0, i1, w0.astype(np.float64), w1.astype(np.float64)), np.float32)


def _hue_lut(h, tab):
    t = np.mod(h, 2.0 * np.pi) * (1.0 / (2.0 * np.pi))
    return cv.lut1(t, tab)


def _apply_comp(x, lut):
    xc = np.clip(x, 0.0, 1.0)
    return cv.lut1(np.sqrt(np.sqrt(xc)), lut) + (x - xc)


def _wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def _point_colours(sel, L, C, hh, tab, alpha):
    sL, sC, sh = sel
    for row in tab:
        hue, chroma, lum, hs, ss, ls, var, sgh, sgc, sgl = row
        dh = _wrap(sh - hue)
        d2 = (dh / sgh) ** 2 + ((sC - chroma) / sgc) ** 2 + ((sL - lum) / sgl) ** 2
        wgt = np.exp(-0.5 * d2) * np.clip(sC / 0.02, 0.0, 1.0) ** 2
        if alpha is not None:
            wgt = wgt * alpha
        hc = hue + hs
        hh = hh + wgt * hs
        if var:
            hh = hc + _wrap(hh - hc) * (1.0 + wgt * var * 0.75)
            C = chroma * (1.0 + ss) + (C - chroma * (1.0 + ss)) * (1.0 + wgt * var * 0.5)
        C = C * np.maximum(1.0 + wgt * ss, 0.0)
        L = L * np.exp2(wgt * ls)
    return L, np.maximum(C, 0.0), hh


def _in_gamut(Lc, a, b, t, i2, m):
    lms = np.stack([Lc, a * t, b * t], axis=-1) @ i2.T
    q = (lms * lms * lms) @ m.T
    return np.all((q >= -GAMUT_TOL) & (q <= 1.0 + GAMUT_TOL), axis=-1), q


def _gamut(o, rgb, p):
    luma = p.luma_out
    Y = o @ luma
    d = o - Y[..., None]
    tch = np.where(d < 0, Y[..., None] / np.minimum(d, -1e-12) * -1.0, np.where(d > 0, (1.0 - Y[..., None]) / np.maximum(d, 1e-12), 1e30))
    ulin = 1.0 / np.maximum(np.min(tch, axis=-1), 1e-30)
    bad = np.any((o < -GAMUT_TOL) | (o > 1.0 + GAMUT_TOL), axis=-1)
    cand = (ulin > PREFILTER) if p.knee < 1.0 else bad
    out = np.clip(o, 0.0, 1.0)
    if not np.any(cand):
        return out
    lab = co.to_lab(rgb[cand])
    L, a, b = lab[:, 0], lab[:, 1], lab[:, 2]
    Lc = np.clip(L, 0.0, 1.0)
    _, _, _, i2 = co.lab_mats()
    m = p.lab_out
    i2 = i2.astype(np.float64)
    top = 1.0 / p.knee
    far, _ = _in_gamut(Lc, a, b, top, i2, m)
    lo = np.zeros(len(L))
    hi = np.full(len(L), top)
    for _ in range(NG):
        t = (lo + hi) * 0.5
        ok, _ = _in_gamut(Lc, a, b, t, i2, m)
        lo = np.where(ok, t, lo)
        hi = np.where(ok, hi, t)
    u = 1.0 / np.maximum(lo, 1e-6)
    kn = p.knee
    f = np.where(u <= kn, u, kn + (1.0 - kn) * np.tanh((u - kn) / max(1.0 - p.knee, 1e-6))) if p.knee < 1.0 else np.minimum(u, 1.0)
    s = np.where(far, 1.0, f / u)
    _, q = _in_gamut(Lc, a, b, s, i2, m)
    q = np.clip(q, 0.0, 1.0)
    q = np.where((L >= 1.0)[:, None], 1.0, np.where((L <= 0.0)[:, None], 0.0, q))
    keep = far & ~bad[cand]
    q = np.where(keep[:, None], out[cand], q)
    out[cand] = q
    return out


def _hash(ix, iy):
    x = (ix.astype(np.int64) * 374761393 + iy.astype(np.int64) * 668265263) & 0xFFFFFFFF
    x = ((x ^ (x >> 13)) * 1274126177) & 0xFFFFFFFF
    x = x ^ (x >> 16)
    return (x & 0xFFFF).astype(np.float64) * (2.0 / 65535.0) - 1.0


def _value_noise(x, y, cell, seed):
    fx, fy = x / cell, y / cell
    ix, iy = np.floor(fx), np.floor(fy)
    tx, ty = fx - ix, fy - iy
    tx = tx * tx * (3.0 - 2.0 * tx)
    ty = ty * ty * (3.0 - 2.0 * ty)
    ix = ix.astype(np.int64) + seed
    iy = iy.astype(np.int64) - seed
    a, b = _hash(ix, iy), _hash(ix + 1, iy)
    c, d = _hash(ix, iy + 1), _hash(ix + 1, iy + 1)
    return (a + (b - a) * tx) + ((c + (d - c) * tx) - (a + (b - a) * tx)) * ty


def grain_field(xs, ys, p):
    n1 = _value_noise(xs, ys, p.g_cell, 17)
    n2 = _value_noise(xs, ys, p.g_cell * 0.5, 91)
    a, b, k = grain_mix(p.g_rough)
    return (n1 * a + n2 * b) * k


def grain_mix(r: float) -> tuple[float, float, float]:
    a, b = 1.0 - GRAIN_OCT[0] * r, GRAIN_OCT[1] + GRAIN_OCT[2] * r
    return a, b, 1.0 / (math.sqrt(a * a + b * b) * 0.5)


def vignette_weight(xs, ys, p):
    W, H = float(max(p.out_w, 1)), float(max(p.out_h, 1))
    X = (xs + 0.5) / W * 2.0 - 1.0
    Y = (ys + 0.5) / H * 2.0 - 1.0
    L = max(W, H)
    rho = p.v_round
    if rho > 0:
        X = X * (1.0 + (W / L - 1.0) * rho)
        Y = Y * (1.0 + (H / L - 1.0) * rho)
    pw = p.v_pow
    d = np.exp2(np.log2(np.exp2(pw * np.log2(np.abs(X) + 1e-9)) + np.exp2(pw * np.log2(np.abs(Y) + 1e-9))) / pw)
    return _smooth(p.v_inner, p.v_outer, d)


def pixels(p: Plan, lin: np.ndarray, y0: int, y1: int) -> np.ndarray:
    sl = slice(y0, y1)
    c = np.maximum(lin[sl].astype(np.float64), 0.0)
    sh = c.shape[:2]
    ft = np.float64
    luma = colour.LUMA_2020
    nm = p.n_masks
    A = [a[sl] for a in p.alphas]

    def loc(k, base):
        out = np.full(sh, ft(base), np.float64)
        for m in range(nm):
            v = p.lrows[m, k]
            if v:
                out += A[m] * ft(v)
        return out
    E = loc(L_EXP, p.ev)
    if p.do_dhz:
        D = loc(L_DHZ, p.dhz)
        air = ft(p.air)
        t = np.clip(1.0 - DH_OMEGA * p.hd[sl] / air, DH_TMIN, 1.0)
        dp = np.maximum(D, 0.0)
        tt = np.maximum(1.0 - dp * DH_K * (1.0 - t), DH_TMIN)
        Y0 = np.maximum(c @ luma, 1e-12)
        yj = np.maximum(air + (Y0 - air) / tt, Y0 * DH_FLOOR)
        sd = 1.0 + DH_SAT * dp * (1.0 - t)
        cj = (yj / Y0)[..., None] * (Y0[..., None] + sd[..., None] * (c - Y0[..., None]))
        hz = np.minimum(np.maximum(-D, 0.0) * (HAZE_ADD[0] + HAZE_ADD[1] * (1.0 - t)) * HAZE_ADD[2], 0.95)
        pos = (D > 0)[..., None]
        c = np.where(pos, np.maximum(cj, 0.0), c + hz[..., None] * (air - c))
    if p.use_m0:
        c = np.maximum(c @ p.m0.T, 0.0)
    if p.local_wb:
        acc = c.copy()
        for m in range(nm):
            wm = p.lwb[m]
            if np.any(wm):
                acc += A[m][..., None] * (c @ wm.T)
        c = np.maximum(acc, 0.0)
    c = c * np.exp2(E)[..., None]
    if p.stint:
        Yt = c @ luma
        vt = np.log2(np.maximum(Yt, 1e-12)) - cv.LOG_MID
        wt = ft(p.stint) * (1.0 - _smooth(-5.0, -1.0, vt))
        gains = np.exp2(np.stack([wt, -0.5 * wt, wt], axis=-1))
        c2 = c * gains
        c = c2 * (Yt / np.maximum(c2 @ luma, 1e-12))[..., None]
    Y = c @ luma
    Yc = np.maximum(Y, 1e-12)
    lg = np.log2(Yc)
    delta = np.zeros(sh, np.float64)
    if p.do_hl or p.do_sh:
        ub = p.hs[sl] + E - cv.LOG_MID
        if p.do_hl:
            H = loc(L_HL, p.hl)
            delta += H * HL_K * HL_W * softplus((ub - p.v_hl) / HL_W)
        if p.do_sh:
            Sh = loc(L_SH, p.sh)
            gsh = SH_W * softplus((p.v_sh - ub) / SH_W)
            delta += Sh * SH_MAX * np.tanh(SH_K * gsh / SH_MAX)
    if p.do_cla:
        Cl = loc(L_CLA, p.cla)
        ub = lg - cv.LOG_MID
        mw = np.exp(-0.5 * ((ub - p.v_mid) / CLA_W) ** 2)
        delta += np.where(Cl > 0, Cl * CLA_K, Cl * CLA_NEG) * mw * p.dc[sl]
    if p.do_tex:
        Tx = loc(L_TEX, p.tex)
        dt = p.dt[sl]
        r2 = dt * dt
        delta += np.where(Tx > 0, Tx * TEX_K * np.exp(r2 * ft(-0.5 / TEX_POS ** 2)), Tx * np.exp(r2 * ft(-0.5 / TEX_NEG ** 2))) * dt
    if p.do_sharp and p.ds is not None:
        amt = np.full(sh, ft(p.s_amt), np.float64)
        for m in range(nm):
            v = p.lrows[m, L_SHP]
            if v > 0:
                amt += A[m] * ft(v)
        d = p.ds[sl]
        core, tcl = p.s_core, p.s_tcl
        dd = d * (d * d / (d * d + core * core))
        dd = dd / np.sqrt(1.0 + (dd / tcl) ** 2)
        if p.s_mask > 0:
            thr = p.s_thr
            mk = _smooth(0.5 * thr, 1.5 * thr, p.edge[sl] * ft(p.scale))
            dd = dd * mk
        delta += amt * ft(SHARP_K) * dd
    if p.do_soft:
        sv = loc(L_SHP, 0.0)
        delta += np.minimum(sv, 0.0) * -p.soft[sl]
    if p.do_nz:
        nz = loc(L_NZ, 0.0)
        delta += np.maximum(nz, 0.0) * p.nrd[sl]
    v = lg + delta - cv.LOG_MID
    if p.do_wh:
        Wv = loc(L_WH, p.wh)
        v = v + Wv * WH_K * WH_W * softplus((v - p.v_wh) / WH_W)
    blk = None
    if p.do_bl:
        Bv = loc(L_BL, p.bl)
        v = v + Bv * BL_K * BL_W * softplus((p.v_bl - v) / BL_W)
        blk = np.maximum(-Bv, 0.0) * BL_CLIP
    e = cv.lut_v(v, p.tone_e)
    gam = cv.lut_v(v, p.tone_g)
    if blk is not None:
        e = np.maximum(e - blk, 0.0) / (1.0 - blk)
    if p.do_con or p.par is not None:
        fs = np.ones(sh, np.float64)
        if p.do_con:
            Ct = np.clip(loc(L_CON, p.con) * CON_K, -0.9, 0.9)
            e1, ds_ = cv.contrast(e, Ct)
            fs = fs * ds_ * (e + 0.055) / (e1 + 0.055)
            e = e1
        if p.par is not None:
            e1 = cv.lut1(e, p.par[0])
            fs = fs * cv.lut1(e, p.par[1]) * (e + 0.055) / (e1 + 0.055)
            e = e1
        gam = gam * np.clip(fs, cv.SAT_SLOPE[0], cv.SAT_SLOPE[1])
    Yd = cv.lut1(e, p.dec)
    q = c / Yc[..., None]
    if p.do_ratio:
        mo = np.zeros(sh, np.float64)
        for m in range(nm):
            vv = p.lrows[m, L_MO] + NZ_RATIO * max(p.lrows[m, L_NZ], 0.0)
            if vv:
                mo += A[m] * ft(vv)
        mo = np.clip(mo, 0.0, 1.0)[..., None]
        q = q + mo * (p.ratio[sl] - q)
    s = _mantiuk(gam, p.sat_gain) if (p.do_con or p.par is not None) else cv.lut_v(v, p.sat_lut)
    rgb = Yd[..., None] * (1.0 + s[..., None] * (q - 1.0))
    if p.do_lab:
        lab = co.to_lab(rgb)
        L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
        C = np.sqrt(a * a + b * b)
        hh = co.atan2f(b, a)
        C0 = C
        if p.do_df and p.edge is not None:
            df = loc(L_DF, 0.0)
            dpu = np.exp(-0.5 * (_wrap(hh - FRINGE_HUES[0]) / FRINGE_HUES[1]) ** 2)
            dgr = np.exp(-0.5 * (_wrap(hh - FRINGE_HUES[2]) / FRINGE_HUES[3]) ** 2)
            ew = _smooth(FRINGE_EDGE[0], FRINGE_EDGE[1], p.edge[sl] * ft(p.scale))
            C = C * (1.0 - np.clip(df * np.maximum(dpu, dgr) * ew, 0.0, 1.0))
        if p.mixer is not None:
            cw = C * C / (C * C + co.C0 * co.C0)
            dh, ds2, dl = (_hue_lut(hh, p.mix_lut[:, k]) for k in range(3))
            hh = hh + dh
            C = C * np.maximum(1.0 + ds2, 0.0)
            L = L * np.exp2(dl * cw)
        if p.do_pts:
            ev_sel = ft(2.0 ** p.ev)
            sel = co.to_lab(1.0 - np.exp(-np.maximum(lin[sl].astype(np.float64), 0.0) * ev_sel))
            sL = sel[..., 0]
            sC = np.sqrt(sel[..., 1] ** 2 + sel[..., 2] ** 2)
            shh = co.atan2f(sel[..., 2], sel[..., 1])
            if p.points is not None:
                L, C, hh = _point_colours((sL, sC, shh), L, C, hh, p.points, None)
            for m in range(nm):
                if p.mpoints[m] is not None:
                    L, C, hh = _point_colours((sL, sC, shh), L, C, hh, p.mpoints[m], A[m])
        if p.vib:
            vw = 1.0 - _smooth(0.0, co.VIB_CHROMA, C)
            if p.vib > 0:
                skin = np.exp(-0.5 * (_wrap(hh - co.SKIN_HUE) / co.SKIN_WIDTH) ** 2)
                vw = vw * (1.0 - VIB_SKIN * skin)
                C = C * (1.0 + ft(p.vib) * vw)
            else:
                C = C * (1.0 + ft(p.vib) * (1.0 - VIB_NEG * _smooth(0.0, co.VIB_CHROMA, C)))
        if p.do_sat:
            C = C * np.maximum(1.0 + loc(L_SAT, p.sat), 0.0)
        if p.do_hue:
            hh = hh + loc(L_HUE, 0.0)
        if p.bw:
            cw = C * C / (C * C + co.C0 * co.C0)
            L = L * np.exp2(_hue_lut(hh, p.bw_lut) * cw)
            C = np.zeros_like(C)
        if p.hue_mod:
            a, b = C * np.cos(hh), C * np.sin(hh)
        else:
            k = np.where(C0 > 1e-12, C / np.maximum(C0, 1e-12), 0.0)
            a, b = a * k, b * k
        if p.grade is not None or p.do_tint:
            env = co.tint_envelope(L)
            if p.grade is not None:
                gt = p.grade
                ws, wm, wh = co.grading_weights(L, p.gshape)
                ta = ws * gt[0, 0] + wm * gt[1, 0] + wh * gt[2, 0] + gt[3, 0]
                tb = ws * gt[0, 1] + wm * gt[1, 1] + wh * gt[2, 1] + gt[3, 1]
                L = L + ws * gt[0, 2] + wm * gt[1, 2] + wh * gt[2, 2] + gt[3, 2]
                a = a + env * ta
                b = b + env * tb
            if p.do_tint:
                a = a + env * loc(L_TA, 0.0)
                b = b + env * loc(L_TB, 0.0)
        rgb = co.from_lab(np.stack([L, a, b], axis=-1))
    if p.do_curve:
        before = rgb
        rgb = np.stack([_apply_comp(rgb[..., ch], p.ccurve[ch]) for ch in range(3)], axis=-1)
        if p.refine < 1.0:
            la, lb = co.to_lab(rgb), co.to_lab(before)
            ca, cb = np.sqrt(la[..., 1] ** 2 + la[..., 2] ** 2), np.sqrt(lb[..., 1] ** 2 + lb[..., 2] ** 2)
            k = np.where(ca > 1e-9, (cb + ft(p.refine) * (ca - cb)) / np.maximum(ca, 1e-9), 1.0)
            la[..., 1] *= k
            la[..., 2] *= k
            rgb = co.from_lab(la)
    if p.do_mcurve:
        for m in range(nm):
            lt = p.mccurve[m]
            if lt is None:
                continue
            new = np.stack([_apply_comp(rgb[..., ch], lt[ch]) for ch in range(3)], axis=-1)
            rgb = rgb + A[m][..., None] * (new - rgb)
    o = rgb @ p.mout.T
    o = _gamut(o, rgb, p)
    out = cv.lut1(np.sqrt(np.sqrt(o)), p.enc)
    if p.lut is not None and p.lut_amt > 0:
        from app.develop import profiles
        t = profiles.apply_lut(out, p.lut)
        out = out + ft(p.lut_amt) * (t - out)
    if p.do_vig or p.do_grain:
        ys, xs = np.mgrid[y0:y1, 0:p.w].astype(np.float64)
        xs += ft(p.rx)
        ys += ft(p.ry)
        if p.do_vig and p.v_amt:
            wv = vignette_weight(xs, ys, p)[..., None]
            amt = ft(p.v_amt)
            if p.v_style == 2:
                target = 0.0 if amt < 0 else 1.0
                out = out + wv * abs(amt) * VIG_PAINT * (target - out)
            else:
                lin_o = cv.lut1(np.clip(out, 0.0, 1.0), p.dec)
                gain = np.exp2(amt * VIG_STOPS * wv)
                if amt < 0:
                    if p.v_hl > 0:
                        lum = np.max(out, axis=-1, keepdims=True)
                        gain = gain + (1.0 - gain) * ft(p.v_hl) * _smooth(VIG_PROTECT, 1.0, lum)
                    lin_o = lin_o * gain
                elif p.v_style == 0:
                    lin_o = lin_o * gain / (1.0 + (gain - 1.0) * lin_o)
                else:
                    lin_o = lin_o * gain
                    mx = np.max(lin_o, axis=-1, keepdims=True)
                    lin_o = lin_o / np.maximum(mx, 1.0)
                out = np.where(wv > 0.0, cv.lut1(np.sqrt(np.sqrt(np.clip(lin_o, 0.0, 1.0))), p.enc), out)
        if p.do_grain:
            n = grain_field(xs, ys, p)
            lum = out @ np.array([0.2126, 0.7152, 0.0722])
            wgt = GRAIN_MID[0] + GRAIN_MID[1] * lum * (1.0 - lum)
            out = out + (ft(p.g_gain) * n * wgt)[..., None]
    out = np.clip(out, 0.0, 1.0)
    if p.trc is not None:
        out = cv.lut1(np.sqrt(np.sqrt(out)), p.trc)
    return out.astype(np.float32)


def finish(lin: np.ndarray, planes: dict, dev: dict, frame, info: dict, out_w: int, out_h: int, ppl: float, evaluated: list,
           space: str = "srgb", region=(0, 0)) -> np.ndarray:
    p = prepare(lin, planes, dev, frame, info, out_w, out_h, ppl, evaluated, space, region)
    out = np.empty(lin.shape[:2] + (3,), np.float32)
    for y0 in range(0, p.h, ROWS):
        y1 = min(p.h, y0 + ROWS)
        out[y0:y1] = pixels(p, lin, y0, y1)
    return out


def trc_table(space: str) -> np.ndarray | None:
    if space in ("srgb", "p3", "rec2020") or space not in SPACES:
        return None
    y = cv.srgb_dec(np.linspace(0.0, 1.0, cv.NE) ** 4)
    t = np.clip(y / TRC_TOE, 0.0, 1.0)
    return cv.trc_enc(y * t * t * (3.0 - 2.0 * t), space).astype(np.float32)


def encode_trc(e: np.ndarray, space: str) -> np.ndarray:
    if space in ("srgb", "p3", "rec2020") or space not in SPACES:
        return np.asarray(e, np.float32)
    return cv.trc_enc(cv.srgb_dec(e), space).astype(np.float32)


def decode_trc(v: np.ndarray, space: str) -> np.ndarray:
    if space in ("srgb", "p3", "rec2020") or space not in SPACES:
        return np.asarray(v, np.float32)
    return cv.srgb_enc(cv.trc_dec(v, space)).astype(np.float32)


def clipping_overlay(e: np.ndarray, shadows: bool = True, highlights: bool = True) -> np.ndarray:
    out = np.array(e, np.float32, copy=True)
    if highlights:
        hi = np.any(e >= 1.0 - 0.5 / 255.0, axis=-1)
        out[hi] = (1.0, 0.0, 0.0)
    if shadows:
        lo = np.all(e <= 0.5 / 255.0, axis=-1)
        out[lo] = (0.0, 0.3, 1.0)
    return out


def mask_overlay(e: np.ndarray, alpha: np.ndarray, color=(1.0, 0.23, 0.23), opacity: float = 0.5) -> np.ndarray:
    k = (np.clip(np.asarray(alpha, np.float32), 0.0, 1.0) * np.float32(opacity))[..., None]
    col = np.asarray(color, np.float32).reshape(1, 1, 3)
    return (e + (col - e) * k).astype(np.float32)


def spots_overlay(e: np.ndarray, level: float) -> np.ndarray:
    y = np.ascontiguousarray(e[..., :3] @ np.array([0.2126, 0.7152, 0.0722], np.float32))
    detail = np.abs(y - cv2.GaussianBlur(y, (0, 0), 2.0)) + np.abs(cv2.Laplacian(cv2.GaussianBlur(y, (0, 0), 0.8), cv2.CV_32F))
    t = 0.1 * (1.0 - min(max(float(level), 0.0), 100.0) / 100.0) ** 2 + 0.004
    v = np.clip(detail / t, 0.0, 1.0)
    return np.repeat(v[..., None], 3, axis=-1).astype(np.float32)
