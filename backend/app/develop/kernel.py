import math
import threading

import numba
import numpy as np
from numba import njit, prange

from app.develop import colorops as co, curves as cv, finish as F, pool

NP_ = 56
(P_EV, P_CON, P_HL, P_SH, P_WH, P_BL, P_TEX, P_CLA, P_DHZ, P_SAT, P_VIB, P_VHL, P_VSH, P_VWH, P_VBL, P_VMID, P_AIR, P_STINT, P_SATG, P_SAMT,
 P_SCORE, P_STCL, P_SMASK, P_STHR, P_SCALE, P_REFINE, P_KNEE, P_LUTAMT, P_VAMT, P_VROUND, P_VPOW, P_VIN, P_VOUT, P_VHLV, P_VSTYLE,
 P_GGAIN, P_GCELL, P_GA, P_GB, P_GK, P_OUTW, P_OUTH, P_RX, P_RY, P_GTS, P_GTH, P_GWD, P_EVSEL, P_GE) = range(49)
NF = 40
(F_HL, F_SH, F_CLA, F_TEX, F_DHZ, F_CON, F_WH, F_BL, F_SAT, F_HUE, F_TINT, F_DF, F_SOFT, F_NZ, F_RATIO, F_SHARP, F_PTS, F_MCURVE, F_CURVE, F_LAB,
 F_HUEMOD, F_PAR, F_M0, F_LWB, F_STINT, F_MIXER, F_BW, F_GRADE, F_VIB, F_LUT, F_VIG, F_GRAIN, F_TRC, F_NM, F_REFINE, F_GLOBPTS, F_NG) = range(37)
NK = 72
(K_LOGMID, K_VMIN, K_VSPAN, K_PIVOT, K_SLO, K_SHI, K_K1, K_K2, K_HLK, K_HLW, K_SHK, K_SHW, K_SHMAX, K_WHK, K_WHW, K_BLK, K_BLW, K_BLCLIP,
 K_CONK, K_CLAK, K_CLAW, K_CLANEG, K_TEXK, K_TEXPN, K_TEXNN, K_SHARPK, K_DHOM, K_DHTMIN, K_DHK, K_DHSAT, K_DHFLOOR, K_HZ0, K_HZ1, K_HZ2,
 K_VIGSTOPS, K_PREF, K_GTOL, K_C0, K_VIBC, K_SKINH, K_SKINW, K_GEDGE, K_A0, K_A1, K_A2, K_A3, K_A4, K_A5, K_PUR, K_PURW, K_GRN, K_GRNW,
 K_NZR, K_FE0, K_FE1, K_VIBSKIN, K_VIBNEG, K_VPAINT, K_VPROT, K_GM0, K_GM1) = range(61)
L_EXP, L_CON, L_HL, L_SH, L_WH, L_BL, L_TEX, L_CLA, L_DHZ, L_SAT, L_HUE, L_SHP, L_NZ, L_MO, L_DF, L_TA, L_TB = range(F.NL)
NB = 72
(B_R, B_G, B_B, B_E, B_CON, B_HL, B_SH, B_WH, B_BL, B_TEX, B_CLA, B_DHZ, B_SAT, B_HUE, B_SP, B_SA, B_NZ, B_MO, B_DF, B_TA, B_TB,
 B_W0, B_W1, B_W2, B_W3, B_W4, B_W5, B_W6, B_W7, B_W8, B_Y, B_LG, B_DL, B_V, B_E1, B_GM, B_S, B_L, B_A, B_BB, B_C, B_H, B_C0,
 B_T0, B_T1, B_T2, B_T3, B_T4, B_T5, B_T6, B_T7, B_SL, B_SC, B_SH2, B_O0, B_O1, B_O2, B_Q0, B_Q1, B_Q2, B_X0, B_X1, B_X2, B_TV) = range(64)
ROW_FLAG = (F_CON, F_HL, F_SH, F_WH, F_BL, F_TEX, F_CLA, F_DHZ, F_SAT)
TWO_PI = 2.0 * math.pi
LOG2E = 1.0 / math.log(2.0)
LN2 = math.log(2.0)
SQRT2 = math.sqrt(2.0)
MANT = 0x000FFFFFFFFFFFFF
ONE = 0x3FF0000000000000
(E0, E1, E2, E3, E4, E5, E6, E7, E8, E9, E10) = (LN2 ** k / math.factorial(k) for k in range(11))
(G0, G1, G2, G3, G4, G5) = (2.0 / LN2 / (2 * k + 1) for k in range(6))
(S0, S1, S2, S3, S4, S5, S6, S7) = ((-1) ** k / math.factorial(2 * k + 1) for k in range(8))
(C0_, C1_, C2_, C3_, C4_, C5_, C6_, C7_) = ((-1) ** k / math.factorial(2 * k) for k in range(8))


def constants() -> np.ndarray:
    k = np.zeros(NK, np.float64)
    k[K_LOGMID], k[K_VMIN], k[K_VSPAN], k[K_PIVOT] = cv.LOG_MID, cv.VMIN, 1.0 / (cv.VMAX - cv.VMIN), cv.PIVOT
    k[K_SLO], k[K_SHI], k[K_K1], k[K_K2] = cv.SAT_SLOPE[0], cv.SAT_SLOPE[1], F.K1, F.K2
    k[K_HLK], k[K_HLW], k[K_SHK], k[K_SHW], k[K_SHMAX] = F.HL_K, F.HL_W, F.SH_K, F.SH_W, F.SH_MAX
    k[K_WHK], k[K_WHW], k[K_BLK], k[K_BLW], k[K_BLCLIP], k[K_CONK] = F.WH_K, F.WH_W, F.BL_K, F.BL_W, F.BL_CLIP, F.CON_K
    k[K_CLAK], k[K_CLAW], k[K_CLANEG] = F.CLA_K, F.CLA_W, F.CLA_NEG
    k[K_TEXK], k[K_TEXPN], k[K_TEXNN], k[K_SHARPK] = F.TEX_K, -0.5 / F.TEX_POS ** 2, -0.5 / F.TEX_NEG ** 2, F.SHARP_K
    k[K_DHOM], k[K_DHTMIN], k[K_DHK], k[K_DHSAT], k[K_DHFLOOR] = F.DH_OMEGA, F.DH_TMIN, F.DH_K, F.DH_SAT, F.DH_FLOOR
    k[K_HZ0], k[K_HZ1], k[K_HZ2] = F.HAZE_ADD
    k[K_VIGSTOPS], k[K_PREF], k[K_GTOL] = F.VIG_STOPS, F.PREFILTER, F.GAMUT_TOL
    k[K_C0], k[K_VIBC], k[K_SKINH], k[K_SKINW], k[K_GEDGE] = co.C0, co.VIB_CHROMA, co.SKIN_HUE, co.SKIN_WIDTH, co.GRADE_EDGE
    k[K_A0:K_A5 + 1] = co.ATAN
    k[K_PUR], k[K_PURW], k[K_GRN], k[K_GRNW] = F.FRINGE_HUES
    k[K_NZR], k[K_FE0], k[K_FE1] = F.NZ_RATIO, F.FRINGE_EDGE[0], F.FRINGE_EDGE[1]
    k[K_VIBSKIN], k[K_VIBNEG], k[K_VPAINT], k[K_VPROT] = F.VIB_SKIN, F.VIB_NEG, F.VIG_PAINT, F.VIG_PROTECT
    k[K_GM0], k[K_GM1] = F.GRAIN_MID
    return k


@njit(cache=True, fastmath=True, inline="always")
def _lut1(t, lut):
    n = lut.shape[0] - 1
    f = min(max(t, 0.0), 1.0) * n
    i = min(int(f), n - 1)
    f -= i
    lo = lut[i]
    return lo + (lut[i + 1] - lo) * f


@njit(cache=True, fastmath=True, inline="always")
def _hue_lut(h, lut):
    return _lut1((h - TWO_PI * math.floor(h / TWO_PI)) * (1.0 / TWO_PI), lut)


@njit(cache=True, fastmath=True, inline="always")
def _smooth(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


@njit(cache=True, fastmath=True, inline="always")
def _wrap(a):
    u = a + math.pi
    return u - TWO_PI * math.floor(u / TWO_PI) - math.pi


@njit(cache=True, fastmath=True, inline="always")
def _sincos(h):
    a = _wrap(h)
    flip = abs(a) > 0.5 * math.pi
    z = (math.pi - a if a > 0.0 else -math.pi - a) if flip else a
    z2 = z * z
    s = z * (S0 + z2 * (S1 + z2 * (S2 + z2 * (S3 + z2 * (S4 + z2 * (S5 + z2 * (S6 + z2 * S7)))))))
    c = C0_ + z2 * (C1_ + z2 * (C2_ + z2 * (C3_ + z2 * (C4_ + z2 * (C5_ + z2 * (C6_ + z2 * C7_))))))
    return s, -c if flip else c


@njit(cache=True, fastmath=True, inline="always")
def _atan2f(y, x, K):
    ax, ay = abs(x), abs(y)
    a = min(ax, ay) / max(max(ax, ay), 1e-30)
    s = a * a
    r = a * (K[K_A0] + s * (K[K_A1] + s * (K[K_A2] + s * (K[K_A3] + s * (K[K_A4] + s * K[K_A5])))))
    r = math.pi / 2 - r if ay > ax else r
    r = math.pi - r if x < 0 else r
    return -r if y < 0 else r


@njit(cache=True, fastmath=True, inline="always")
def _exp2_poly(f):
    return E0 + f * (E1 + f * (E2 + f * (E3 + f * (E4 + f * (E5 + f * (E6 + f * (E7 + f * (E8 + f * (E9 + f * E10)))))))))


@njit(cache=True, fastmath=True, inline="always")
def _log2_mant(e, m):
    big = m > SQRT2
    m = m * 0.5 if big else m
    s = (m - 1.0) / (m + 1.0)
    s2 = s * s
    return e + (1.0 if big else 0.0) + s * (G0 + s2 * (G1 + s2 * (G2 + s2 * (G3 + s2 * (G4 + s2 * G5)))))


@njit(cache=True, fastmath=True)
def _exp2(src, dst, ti, n):
    for k in range(n):
        x = min(max(src[k], -1000.0), 1000.0)
        fl = math.floor(x)
        ti[k] = int(fl)
        dst[k] = _exp2_poly(x - fl)
    di = dst.view(np.int64)
    for k in range(n):
        di[k] = di[k] + (ti[k] << 52)


@njit(cache=True, fastmath=True)
def _log2(src, dst, tf, ti, n):
    si = src.view(np.int64)
    tfi = tf.view(np.int64)
    for k in range(n):
        bits = si[k]
        ti[k] = ((bits >> 52) & 0x7FF) - 1023
        tfi[k] = (bits & MANT) | ONE
    for k in range(n):
        dst[k] = _log2_mant(ti[k], tf[k])


@njit(cache=True, fastmath=True)
def _softplus(z, out, t, ti, n):
    for k in range(n):
        t[k] = -abs(z[k]) * LOG2E
    _exp2(t, out, ti, n)
    for k in range(n):
        t[k] = 1.0 + out[k]
    _log2(t, out, t, ti, n)
    for k in range(n):
        out[k] = max(z[k], 0.0) + LN2 * out[k]


@njit(cache=True, fastmath=True)
def _cbrt(src, tf, ti, n):
    tfi = tf.view(np.int64)
    for k in range(n):
        tf[k] = max(abs(src[k]), 1e-30)
    for k in range(n):
        bits = tfi[k]
        ti[k] = ((bits >> 52) & 0x7FF) - 1023
        tfi[k] = (bits & MANT) | ONE
    for k in range(n):
        yv = _log2_mant(ti[k], tf[k]) * (1.0 / 3.0)
        fl = math.floor(yv)
        ti[k] = int(fl)
        tf[k] = _exp2_poly(yv - fl)
    for k in range(n):
        tfi[k] = tfi[k] + (ti[k] << 52)
    for k in range(n):
        x = src[k]
        v = tf[k]
        src[k] = 0.0 if abs(x) < 1e-30 else (v if x >= 0.0 else -v)


@njit(cache=True, fastmath=True)
def _to_lab(B, r, g, b, oL, oa, ob, m1, m2, ti, n):
    x0, x1, x2 = B[B_X0], B[B_X1], B[B_X2]
    for k in range(n):
        rr, gg, bb = r[k], g[k], b[k]
        x0[k] = m1[0, 0] * rr + m1[0, 1] * gg + m1[0, 2] * bb
        x1[k] = m1[1, 0] * rr + m1[1, 1] * gg + m1[1, 2] * bb
        x2[k] = m1[2, 0] * rr + m1[2, 1] * gg + m1[2, 2] * bb
    _cbrt(x0, B[B_T7], ti, n)
    _cbrt(x1, B[B_T7], ti, n)
    _cbrt(x2, B[B_T7], ti, n)
    for k in range(n):
        l_, m_, s_ = x0[k], x1[k], x2[k]
        oL[k] = m2[0, 0] * l_ + m2[0, 1] * m_ + m2[0, 2] * s_
        oa[k] = m2[1, 0] * l_ + m2[1, 1] * m_ + m2[1, 2] * s_
        ob[k] = m2[2, 0] * l_ + m2[2, 1] * m_ + m2[2, 2] * s_


@njit(cache=True, fastmath=True, inline="always")
def _from_lab(L, a, b, i2, om):
    l_ = i2[0, 0] * L + i2[0, 1] * a + i2[0, 2] * b
    m_ = i2[1, 0] * L + i2[1, 1] * a + i2[1, 2] * b
    s_ = i2[2, 0] * L + i2[2, 1] * a + i2[2, 2] * b
    l3, m3, s3 = l_ * l_ * l_, m_ * m_ * m_, s_ * s_ * s_
    return (om[0, 0] * l3 + om[0, 1] * m3 + om[0, 2] * s3, om[1, 0] * l3 + om[1, 1] * m3 + om[1, 2] * s3,
            om[2, 0] * l3 + om[2, 1] * m3 + om[2, 2] * s3)


@njit(cache=True, fastmath=True, inline="always")
def _comp(x, lut):
    xc = min(max(x, 0.0), 1.0)
    return _lut1(math.sqrt(math.sqrt(xc)), lut) + (x - xc)


@njit(cache=True, fastmath=True, inline="always")
def _hash(ix, iy):
    x = (ix * 374761393 + iy * 668265263) & 0xFFFFFFFF
    x = ((x ^ (x >> 13)) * 1274126177) & 0xFFFFFFFF
    x = x ^ (x >> 16)
    return (x & 0xFFFF) * (2.0 / 65535.0) - 1.0


@njit(cache=True, fastmath=True, inline="always")
def _vnoise(x, y, cell, seed):
    fx, fy = x / cell, y / cell
    flx, fly = math.floor(fx), math.floor(fy)
    tx, ty = fx - flx, fy - fly
    tx = tx * tx * (3.0 - 2.0 * tx)
    ty = ty * ty * (3.0 - 2.0 * ty)
    ix = int(flx) + seed
    iy = int(fly) - seed
    a, b = _hash(ix, iy), _hash(ix + 1, iy)
    c, d = _hash(ix, iy + 1), _hash(ix + 1, iy + 1)
    top = a + (b - a) * tx
    return top + ((c + (d - c) * tx) - top) * ty


@njit(cache=True, fastmath=True)
def _gauss_into(B, dst, center, width, src, ti, n):
    t = B[B_T5]
    for k in range(n):
        d = _wrap(src[k] - center) / width
        t[k] = -0.5 * d * d * LOG2E
    _exp2(t, dst, ti, n)


@njit(cache=True, fastmath=True)
def _points(B, tab, npt, alpha, use_alpha, ti, n):
    L, C, H = B[B_L], B[B_C], B[B_H]
    sL, sC, sh = B[B_SL], B[B_SC], B[B_SH2]
    wgt, t, t5 = B[B_T3], B[B_T4], B[B_T5]
    for j in range(npt):
        hue, chroma, lum, hs, ss, ls, var = tab[j, 0], tab[j, 1], tab[j, 2], tab[j, 3], tab[j, 4], tab[j, 5], tab[j, 6]
        sgh, sgc, sgl = tab[j, 7], tab[j, 8], tab[j, 9]
        for k in range(n):
            dh = _wrap(sh[k] - hue) / sgh
            dc = (sC[k] - chroma) / sgc
            dl = (sL[k] - lum) / sgl
            t[k] = -0.5 * (dh * dh + dc * dc + dl * dl) * LOG2E
        _exp2(t, wgt, ti, n)
        for k in range(n):
            gate = min(max(sC[k] / 0.02, 0.0), 1.0)
            wv = wgt[k] * gate * gate * (alpha[k] if use_alpha else 1.0)
            hc = hue + hs
            hh = H[k] + wv * hs
            cc = C[k]
            if var != 0.0:
                hh = hc + _wrap(hh - hc) * (1.0 + wv * var * 0.75)
                c1 = chroma * (1.0 + ss)
                cc = c1 + (cc - c1) * (1.0 + wv * var * 0.5)
            H[k] = hh
            C[k] = cc * max(1.0 + wv * ss, 0.0)
            t[k] = wv * ls
        _exp2(t, t5, ti, n)
        for k in range(n):
            L[k] = L[k] * t5[k]
            C[k] = max(C[k], 0.0)


@njit(cache=True, fastmath=True)
def _fill(row, v, n):
    for x in range(n):
        row[x] = v


@njit(cache=True, fastmath=True)
def _accum(row, a, v, n):
    for x in range(n):
        row[x] += a[x] * v


@njit(cache=True, fastmath=True)
def _row(y, B, BI, lin, out, P, FL, K, tone_e, tone_g, sat_lut, par_y, par_d, enc, dec, trc, ccurve, m0, m1, m2, i1, i2, labout, mout,
         luma, luma_o, mixl, bwl, grade, pts, npts, alphas, lrows, lwb, mpts, mnpts, mccurve, mcflag, hs, dc, dt, hd, ds, edge, soft, nrd, ratio,
         lut):
    n = lin.shape[1]
    nm = FL[F_NM]
    ti = BI[0]
    log_mid = K[K_LOGMID]
    R, G, Bc, E = B[B_R], B[B_G], B[B_B], B[B_E]
    ev = P[P_EV]
    for x in range(n):
        R[x] = max(lin[y, x, 0], 0.0)
        G[x] = max(lin[y, x, 1], 0.0)
        Bc[x] = max(lin[y, x, 2], 0.0)
        E[x] = ev
    for j in range(9):
        if FL[ROW_FLAG[j]]:
            _fill(B[B_CON + j], P[P_CON + j], n)
    shp = FL[F_SHARP] or FL[F_SOFT]
    if FL[F_HUE]:
        _fill(B[B_HUE], 0.0, n)
    if shp:
        _fill(B[B_SP], 0.0, n)
        _fill(B[B_SA], 0.0, n)
    if FL[F_NZ]:
        _fill(B[B_NZ], 0.0, n)
    if FL[F_RATIO]:
        _fill(B[B_MO], 0.0, n)
    if FL[F_DF]:
        _fill(B[B_DF], 0.0, n)
    if FL[F_TINT]:
        _fill(B[B_TA], 0.0, n)
        _fill(B[B_TB], 0.0, n)
    if FL[F_LWB]:
        for j in range(9):
            _fill(B[B_W0 + j], 0.0, n)
    edit_e = False
    for m in range(nm):
        a = alphas[m, y]
        for j in range(L_TB + 1):
            v = lrows[m, j]
            if v == 0.0:
                continue
            if j == L_EXP:
                edit_e = True
                _accum(E, a, v, n)
            elif j <= L_SAT:
                if FL[ROW_FLAG[j - 1]]:
                    _accum(B[B_CON + j - 1], a, v, n)
            elif j == L_HUE:
                if FL[F_HUE]:
                    _accum(B[B_HUE], a, v, n)
            elif j == L_SHP:
                if shp:
                    _accum(B[B_SA], a, v, n)
                    if v > 0.0:
                        _accum(B[B_SP], a, v, n)
            elif j == L_NZ:
                if FL[F_NZ]:
                    _accum(B[B_NZ], a, v, n)
            elif j == L_MO:
                if FL[F_RATIO]:
                    _accum(B[B_MO], a, v, n)
            elif j == L_DF:
                if FL[F_DF]:
                    _accum(B[B_DF], a, v, n)
            elif j == L_TA:
                if FL[F_TINT]:
                    _accum(B[B_TA], a, v, n)
            elif FL[F_TINT]:
                _accum(B[B_TB], a, v, n)
        vnz = K[K_NZR] * max(lrows[m, L_NZ], 0.0)
        if vnz != 0.0 and FL[F_RATIO]:
            _accum(B[B_MO], a, vnz, n)
        if FL[F_LWB]:
            for j in range(9):
                v = lwb[m, j // 3, j % 3]
                if v != 0.0:
                    _accum(B[B_W0 + j], a, v, n)
    if FL[F_DHZ]:
        D = B[B_DHZ]
        air = P[P_AIR]
        for x in range(n):
            t = min(max(1.0 - K[K_DHOM] * hd[y, x] / air, K[K_DHTMIN]), 1.0)
            d = D[x]
            r, g, b = R[x], G[x], Bc[x]
            dp = max(d, 0.0)
            tt = max(1.0 - dp * K[K_DHK] * (1.0 - t), K[K_DHTMIN])
            y0 = max(luma[0] * r + luma[1] * g + luma[2] * b, 1e-12)
            yj = max(air + (y0 - air) / tt, y0 * K[K_DHFLOOR])
            sd = 1.0 + K[K_DHSAT] * dp * (1.0 - t)
            k = yj / y0
            hz = min(max(-d, 0.0) * (K[K_HZ0] + K[K_HZ1] * (1.0 - t)) * K[K_HZ2], 0.95)
            pos = d > 0.0
            R[x] = max(k * (y0 + sd * (r - y0)), 0.0) if pos else r + hz * (air - r)
            G[x] = max(k * (y0 + sd * (g - y0)), 0.0) if pos else g + hz * (air - g)
            Bc[x] = max(k * (y0 + sd * (b - y0)), 0.0) if pos else b + hz * (air - b)
    if FL[F_M0]:
        for x in range(n):
            r, g, b = R[x], G[x], Bc[x]
            R[x] = max(m0[0, 0] * r + m0[0, 1] * g + m0[0, 2] * b, 0.0)
            G[x] = max(m0[1, 0] * r + m0[1, 1] * g + m0[1, 2] * b, 0.0)
            Bc[x] = max(m0[2, 0] * r + m0[2, 1] * g + m0[2, 2] * b, 0.0)
    if FL[F_LWB]:
        W0, W1, W2, W3, W4, W5, W6, W7, W8 = B[B_W0], B[B_W1], B[B_W2], B[B_W3], B[B_W4], B[B_W5], B[B_W6], B[B_W7], B[B_W8]
        for x in range(n):
            r, g, b = R[x], G[x], Bc[x]
            R[x] = max(r + W0[x] * r + W1[x] * g + W2[x] * b, 0.0)
            G[x] = max(g + W3[x] * r + W4[x] * g + W5[x] * b, 0.0)
            Bc[x] = max(b + W6[x] * r + W7[x] * g + W8[x] * b, 0.0)
    if edit_e:
        gain = B[B_T0]
        _exp2(E, gain, ti, n)
        for x in range(n):
            R[x] *= gain[x]
            G[x] *= gain[x]
            Bc[x] *= gain[x]
    else:
        ge = P[P_GE]
        for x in range(n):
            R[x] *= ge
            G[x] *= ge
            Bc[x] *= ge
    if FL[F_STINT]:
        yt, t0, t1, t2 = B[B_T0], B[B_T1], B[B_T2], B[B_T3]
        for x in range(n):
            yt[x] = max(luma[0] * R[x] + luma[1] * G[x] + luma[2] * Bc[x], 1e-12)
        _log2(yt, t0, t1, ti, n)
        for x in range(n):
            wt = P[P_STINT] * (1.0 - _smooth(-5.0, -1.0, t0[x] - log_mid))
            t0[x] = wt
            t1[x] = -0.5 * wt
        _exp2(t0, t2, ti, n)
        _exp2(t1, t0, ti, n)
        for x in range(n):
            ytv = luma[0] * R[x] + luma[1] * G[x] + luma[2] * Bc[x]
            r2, g2, b2 = R[x] * t2[x], G[x] * t0[x], Bc[x] * t2[x]
            k = ytv / max(luma[0] * r2 + luma[1] * g2 + luma[2] * b2, 1e-12)
            R[x], G[x], Bc[x] = r2 * k, g2 * k, b2 * k
    Y, LG, DL = B[B_Y], B[B_LG], B[B_DL]
    for x in range(n):
        Y[x] = max(luma[0] * R[x] + luma[1] * G[x] + luma[2] * Bc[x], 1e-12)
        DL[x] = 0.0
    _log2(Y, LG, B[B_T0], ti, n)
    if FL[F_HL] or FL[F_SH]:
        ub, z, sp_ = B[B_T0], B[B_T1], B[B_T2]
        for x in range(n):
            ub[x] = hs[y, x] + E[x] - log_mid
        if FL[F_HL]:
            Hr = B[B_HL]
            for x in range(n):
                z[x] = (ub[x] - P[P_VHL]) / K[K_HLW]
            _softplus(z, sp_, B[B_T3], ti, n)
            for x in range(n):
                DL[x] += Hr[x] * K[K_HLK] * K[K_HLW] * sp_[x]
        if FL[F_SH]:
            Sr = B[B_SH]
            t4 = B[B_T4]
            for x in range(n):
                z[x] = (P[P_VSH] - ub[x]) / K[K_SHW]
            _softplus(z, sp_, B[B_T3], ti, n)
            for x in range(n):
                q = K[K_SHK] * K[K_SHW] * sp_[x] / K[K_SHMAX]
                t4[x] = -2.0 * abs(q) * LOG2E
                z[x] = q
            _exp2(t4, sp_, ti, n)
            for x in range(n):
                th = (1.0 - sp_[x]) / (1.0 + sp_[x])
                DL[x] += Sr[x] * K[K_SHMAX] * (th if z[x] >= 0.0 else -th)
    if FL[F_CLA]:
        Cl, t0, t1 = B[B_CLA], B[B_T0], B[B_T1]
        for x in range(n):
            u2 = (LG[x] - log_mid - P[P_VMID]) / K[K_CLAW]
            t0[x] = -0.5 * u2 * u2 * LOG2E
        _exp2(t0, t1, ti, n)
        for x in range(n):
            cl = Cl[x]
            DL[x] += (cl * K[K_CLAK] if cl > 0.0 else cl * K[K_CLANEG]) * t1[x] * dc[y, x]
    if FL[F_TEX]:
        Tx, t0, t1 = B[B_TEX], B[B_T0], B[B_T1]
        for x in range(n):
            d = dt[y, x]
            t0[x] = d * d * (K[K_TEXPN] if Tx[x] > 0.0 else K[K_TEXNN]) * LOG2E
        _exp2(t0, t1, ti, n)
        for x in range(n):
            tx = Tx[x]
            DL[x] += (tx * K[K_TEXK] if tx > 0.0 else tx) * t1[x] * dt[y, x]
    if FL[F_SHARP]:
        SPr = B[B_SP]
        core, tcl, thr = P[P_SCORE], P[P_STCL], P[P_STHR]
        amt0 = P[P_SAMT]
        msk = P[P_SMASK] > 0.0
        for x in range(n):
            d = ds[y, x]
            dd = d * (d * d / (d * d + core * core))
            dd = dd / math.sqrt(1.0 + (dd / tcl) * (dd / tcl))
            if msk:
                dd *= _smooth(0.5 * thr, 1.5 * thr, edge[y, x] * P[P_SCALE])
            DL[x] += (amt0 + SPr[x]) * K[K_SHARPK] * dd
    if FL[F_SOFT]:
        SAr = B[B_SA]
        for x in range(n):
            DL[x] += min(SAr[x], 0.0) * -soft[y, x]
    if FL[F_NZ]:
        NZr = B[B_NZ]
        for x in range(n):
            DL[x] += max(NZr[x], 0.0) * nrd[y, x]
    V = B[B_V]
    for x in range(n):
        V[x] = LG[x] + DL[x] - log_mid
    if FL[F_WH]:
        z, sp_ = B[B_T1], B[B_T2]
        Wr = B[B_WH]
        for x in range(n):
            z[x] = (V[x] - P[P_VWH]) / K[K_WHW]
        _softplus(z, sp_, B[B_T3], ti, n)
        for x in range(n):
            V[x] = V[x] + Wr[x] * K[K_WHK] * K[K_WHW] * sp_[x]
    if FL[F_BL]:
        z, sp_ = B[B_T1], B[B_T2]
        Br = B[B_BL]
        for x in range(n):
            z[x] = (P[P_VBL] - V[x]) / K[K_BLW]
        _softplus(z, sp_, B[B_T3], ti, n)
        for x in range(n):
            V[x] = V[x] + Br[x] * K[K_BLK] * K[K_BLW] * sp_[x]
    EE, GM, TV = B[B_E1], B[B_GM], B[B_TV]
    vmin, vspan = K[K_VMIN], K[K_VSPAN]
    for x in range(n):
        tv = (V[x] - vmin) * vspan
        TV[x] = tv
        EE[x] = _lut1(tv, tone_e)
    if FL[F_BL]:
        Br = B[B_BL]
        for x in range(n):
            blk = max(-Br[x], 0.0) * K[K_BLCLIP]
            EE[x] = max(EE[x] - blk, 0.0) / (1.0 - blk)
    S_ = B[B_S]
    if FL[F_CON] or FL[F_PAR]:
        for x in range(n):
            GM[x] = _lut1(TV[x], tone_g)
        CONr = B[B_CON]
        pv = K[K_PIVOT]
        for x in range(n):
            e = EE[x]
            fs = 1.0
            if FL[F_CON]:
                ct = min(max(CONr[x] * K[K_CONK], -0.9), 0.9)
                lo = e < pv
                u = min(max(e / pv if lo else (e - pv) / (1.0 - pv), 0.0), 1.0)
                sn, cn = _sincos(math.pi * u)
                wd = (pv if lo else 1.0 - pv) / math.pi
                e1 = e - ct * wd * sn if lo else e + ct * wd * sn
                dsl = 1.0 - ct * cn if lo else 1.0 + ct * cn
                inside = e >= 0.0 and e <= 1.0
                e1 = e1 if inside else e
                dsl = dsl if inside else 1.0
                fs *= dsl * (e + 0.055) / (e1 + 0.055)
                e = e1
            if FL[F_PAR]:
                e1 = _lut1(e, par_y)
                fs *= _lut1(e, par_d) * (e + 0.055) / (e1 + 0.055)
                e = e1
            EE[x] = e
            GM[x] = max(GM[x] * min(max(fs, K[K_SLO]), K[K_SHI]), 1e-12)
        t0, t1 = B[B_T0], B[B_T1]
        _log2(GM, t0, t1, ti, n)
        for x in range(n):
            t0[x] = K[K_K2] * t0[x]
        _exp2(t0, t1, ti, n)
        for x in range(n):
            gp = t1[x]
            S_[x] = (1.0 + K[K_K1]) * gp / (1.0 + K[K_K1] * gp) * P[P_SATG] if GM[x] > 1e-9 else 0.0
    else:
        for x in range(n):
            S_[x] = _lut1(TV[x], sat_lut)
    if FL[F_RATIO]:
        MOr = B[B_MO]
        for x in range(n):
            iy = 1.0 / Y[x]
            mc = min(max(MOr[x], 0.0), 1.0)
            qr = R[x] * iy
            qg = G[x] * iy
            qb = Bc[x] * iy
            R[x] = qr + mc * (ratio[y, x, 0] - qr)
            G[x] = qg + mc * (ratio[y, x, 1] - qg)
            Bc[x] = qb + mc * (ratio[y, x, 2] - qb)
            Y[x] = 1.0
    for x in range(n):
        yd = _lut1(EE[x], dec)
        iy = 1.0 / Y[x]
        s = S_[x]
        R[x] = yd * (1.0 + s * (R[x] * iy - 1.0))
        G[x] = yd * (1.0 + s * (G[x] * iy - 1.0))
        Bc[x] = yd * (1.0 + s * (Bc[x] * iy - 1.0))
    if FL[F_LAB]:
        L, A, Bb, C, H, Cs = B[B_L], B[B_A], B[B_BB], B[B_C], B[B_H], B[B_C0]
        _to_lab(B, R, G, Bc, L, A, Bb, m1, m2, ti, n)
        for x in range(n):
            c = math.sqrt(A[x] * A[x] + Bb[x] * Bb[x])
            C[x] = c
            Cs[x] = c
            H[x] = _atan2f(Bb[x], A[x], K)
        c0 = K[K_C0]
        if FL[F_DF]:
            DFr, t0, t1 = B[B_DF], B[B_T0], B[B_T1]
            _gauss_into(B, t0, K[K_PUR], K[K_PURW], H, ti, n)
            _gauss_into(B, t1, K[K_GRN], K[K_GRNW], H, ti, n)
            for x in range(n):
                ew = _smooth(K[K_FE0], K[K_FE1], edge[y, x] * P[P_SCALE])
                C[x] = C[x] * (1.0 - min(max(DFr[x] * max(t0[x], t1[x]) * ew, 0.0), 1.0))
        if FL[F_MIXER]:
            t0, t1 = B[B_T0], B[B_T1]
            for x in range(n):
                c = C[x]
                cw = c * c / (c * c + c0 * c0)
                h = H[x]
                H[x] = h + _hue_lut(h, mixl[0])
                C[x] = c * max(1.0 + _hue_lut(h, mixl[1]), 0.0)
                t0[x] = _hue_lut(h, mixl[2]) * cw
            _exp2(t0, t1, ti, n)
            for x in range(n):
                L[x] = L[x] * t1[x]
        if FL[F_PTS]:
            es = P[P_EVSEL] * LOG2E
            sr, sg, sb = B[B_O0], B[B_O1], B[B_O2]
            t0, t1, t2 = B[B_T0], B[B_T1], B[B_T2]
            for x in range(n):
                t0[x] = -max(lin[y, x, 0], 0.0) * es
                t1[x] = -max(lin[y, x, 1], 0.0) * es
                t2[x] = -max(lin[y, x, 2], 0.0) * es
            _exp2(t0, sr, ti, n)
            _exp2(t1, sg, ti, n)
            _exp2(t2, sb, ti, n)
            for x in range(n):
                sr[x] = 1.0 - sr[x]
                sg[x] = 1.0 - sg[x]
                sb[x] = 1.0 - sb[x]
            SL, SC, SH2 = B[B_SL], B[B_SC], B[B_SH2]
            qa, qb = B[B_Q0], B[B_Q1]
            _to_lab(B, sr, sg, sb, SL, qa, qb, m1, m2, ti, n)
            for x in range(n):
                SC[x] = math.sqrt(qa[x] * qa[x] + qb[x] * qb[x])
                SH2[x] = _atan2f(qb[x], qa[x], K)
            if FL[F_GLOBPTS]:
                _points(B, pts, npts, B[B_T6], False, ti, n)
            for m in range(nm):
                if mnpts[m] > 0:
                    _points(B, mpts[m], mnpts[m], alphas[m, y], True, ti, n)
        if FL[F_VIB]:
            vib = P[P_VIB]
            t0 = B[B_T0]
            if vib > 0.0:
                _gauss_into(B, t0, K[K_SKINH], K[K_SKINW], H, ti, n)
                for x in range(n):
                    sm = _smooth(0.0, K[K_VIBC], C[x])
                    C[x] = C[x] * (1.0 + vib * (1.0 - sm) * (1.0 - K[K_VIBSKIN] * t0[x]))
            else:
                for x in range(n):
                    sm = _smooth(0.0, K[K_VIBC], C[x])
                    C[x] = C[x] * (1.0 + vib * (1.0 - K[K_VIBNEG] * sm))
        if FL[F_SAT]:
            SATr = B[B_SAT]
            for x in range(n):
                C[x] = C[x] * max(1.0 + SATr[x], 0.0)
        if FL[F_HUE]:
            HUEr = B[B_HUE]
            for x in range(n):
                H[x] = H[x] + HUEr[x]
        if FL[F_BW]:
            t0, t1 = B[B_T0], B[B_T1]
            for x in range(n):
                c = C[x]
                t0[x] = _hue_lut(H[x], bwl) * (c * c / (c * c + c0 * c0))
                C[x] = 0.0
            _exp2(t0, t1, ti, n)
            for x in range(n):
                L[x] = L[x] * t1[x]
        if FL[F_HUEMOD]:
            for x in range(n):
                sn, cn = _sincos(H[x])
                A[x] = C[x] * cn
                Bb[x] = C[x] * sn
        else:
            for x in range(n):
                k = C[x] / max(Cs[x], 1e-12) if Cs[x] > 1e-12 else 0.0
                A[x] = A[x] * k
                Bb[x] = Bb[x] * k
        if FL[F_GRADE] or FL[F_TINT]:
            ge_ = K[K_GEDGE]
            TAr, TBr = B[B_TA], B[B_TB]
            ts, th, wd = P[P_GTS], P[P_GTH], P[P_GWD]
            for x in range(n):
                l = L[x]
                env = min(max(l / ge_, 0.0), 1.0) * min(max((1.0 - l) / ge_, 0.0), 1.0)
                if FL[F_GRADE]:
                    ws = 1.0 - _smooth(ts - wd, ts + wd, l)
                    whh = _smooth(th - wd, th + wd, l)
                    wm = max(1.0 - ws - whh, 0.0)
                    A[x] += env * (ws * grade[0, 0] + wm * grade[1, 0] + whh * grade[2, 0] + grade[3, 0])
                    Bb[x] += env * (ws * grade[0, 1] + wm * grade[1, 1] + whh * grade[2, 1] + grade[3, 1])
                    L[x] = l + ws * grade[0, 2] + wm * grade[1, 2] + whh * grade[2, 2] + grade[3, 2]
                if FL[F_TINT]:
                    A[x] += env * TAr[x]
                    Bb[x] += env * TBr[x]
        for x in range(n):
            R[x], G[x], Bc[x] = _from_lab(L[x], A[x], Bb[x], i2, i1)
    if FL[F_CURVE]:
        o0, o1, o2 = B[B_O0], B[B_O1], B[B_O2]
        c0l, c1l, c2l = ccurve[0], ccurve[1], ccurve[2]
        X0, X1, X2 = B[B_X0], B[B_X1], B[B_X2]
        for x in range(n):
            r, g, b = R[x], G[x], Bc[x]
            o0[x], o1[x], o2[x] = r, g, b
            X0[x] = math.sqrt(math.sqrt(min(max(r, 0.0), 1.0)))
            X1[x] = math.sqrt(math.sqrt(min(max(g, 0.0), 1.0)))
            X2[x] = math.sqrt(math.sqrt(min(max(b, 0.0), 1.0)))
        for x in range(n):
            r, g, b = R[x], G[x], Bc[x]
            R[x] = _lut1(X0[x], c0l) + (r - min(max(r, 0.0), 1.0))
            G[x] = _lut1(X1[x], c1l) + (g - min(max(g, 0.0), 1.0))
            Bc[x] = _lut1(X2[x], c2l) + (b - min(max(b, 0.0), 1.0))
        if FL[F_REFINE]:
            L, A, Bb = B[B_L], B[B_A], B[B_BB]
            q0, q1, q2 = B[B_Q0], B[B_Q1], B[B_Q2]
            _to_lab(B, R, G, Bc, L, A, Bb, m1, m2, ti, n)
            _to_lab(B, o0, o1, o2, q0, q1, q2, m1, m2, ti, n)
            for x in range(n):
                ca = math.sqrt(A[x] * A[x] + Bb[x] * Bb[x])
                cb = math.sqrt(q1[x] * q1[x] + q2[x] * q2[x])
                k = (cb + P[P_REFINE] * (ca - cb)) / max(ca, 1e-9) if ca > 1e-9 else 1.0
                R[x], G[x], Bc[x] = _from_lab(L[x], A[x] * k, Bb[x] * k, i2, i1)
    if FL[F_MCURVE]:
        for m in range(nm):
            if not mcflag[m]:
                continue
            a = alphas[m, y]
            c0l, c1l, c2l = mccurve[m, 0], mccurve[m, 1], mccurve[m, 2]
            for x in range(n):
                R[x] += a[x] * (_comp(R[x], c0l) - R[x])
                G[x] += a[x] * (_comp(G[x], c1l) - G[x])
                Bc[x] += a[x] * (_comp(Bc[x], c2l) - Bc[x])
    knee = P[P_KNEE]
    tol = K[K_GTOL]
    pref = K[K_PREF]
    O0, O1, O2, UL, BD = B[B_O0], B[B_O1], B[B_O2], B[B_T0], B[B_T1]
    soft_gamut = knee < 1.0
    for x in range(n):
        r, g, b = R[x], G[x], Bc[x]
        o0 = mout[0, 0] * r + mout[0, 1] * g + mout[0, 2] * b
        o1 = mout[1, 0] * r + mout[1, 1] * g + mout[1, 2] * b
        o2 = mout[2, 0] * r + mout[2, 1] * g + mout[2, 2] * b
        yo = luma_o[0] * o0 + luma_o[1] * o1 + luma_o[2] * o2
        d0, d1, d2 = o0 - yo, o1 - yo, o2 - yo
        t0 = yo / -min(d0, -1e-12) if d0 < 0.0 else ((1.0 - yo) / max(d0, 1e-12) if d0 > 0.0 else 1e30)
        t1 = yo / -min(d1, -1e-12) if d1 < 0.0 else ((1.0 - yo) / max(d1, 1e-12) if d1 > 0.0 else 1e30)
        t2 = yo / -min(d2, -1e-12) if d2 < 0.0 else ((1.0 - yo) / max(d2, 1e-12) if d2 > 0.0 else 1e30)
        UL[x] = 1.0 / max(min(t0, min(t1, t2)), 1e-30)
        BD[x] = 1.0 if (o0 < -tol or o0 > 1.0 + tol or o1 < -tol or o1 > 1.0 + tol or o2 < -tol or o2 > 1.0 + tol) else 0.0
        O0[x] = min(max(o0, 0.0), 1.0)
        O1[x] = min(max(o1, 0.0), 1.0)
        O2[x] = min(max(o2, 0.0), 1.0)
    cand = BI[1]
    bads = BI[2]
    nc = 0
    for x in range(n):
        if (UL[x] > pref) if soft_gamut else (BD[x] > 0.0):
            cand[nc] = x
            bads[nc] = 1 if BD[x] > 0.0 else 0
            nc += 1
    if nc > 0:
        cr, cg, cb_ = B[B_Q0], B[B_Q1], B[B_Q2]
        for k in range(nc):
            x = cand[k]
            cr[k], cg[k], cb_[k] = R[x], G[x], Bc[x]
        L, A, Bb = B[B_L], B[B_A], B[B_BB]
        _to_lab(B, cr, cg, cb_, L, A, Bb, m1, m2, ti, nc)
        lo_, hi_, far_, Lc_ = B[B_T0], B[B_T1], B[B_T2], B[B_T3]
        top = 1.0 / knee
        for k in range(nc):
            Lc = min(max(L[k], 0.0), 1.0)
            Lc_[k] = Lc
            q0, q1, q2 = _from_lab(Lc, A[k] * top, Bb[k] * top, i2, labout)
            far = q0 >= -tol and q0 <= 1.0 + tol and q1 >= -tol and q1 <= 1.0 + tol and q2 >= -tol and q2 <= 1.0 + tol
            far_[k] = 1.0 if far else 0.0
            lo_[k] = top if far else 0.0
            hi_[k] = top
        jl, jh = B[B_X0], B[B_X1]
        p0, p1, p2 = B[B_SL], B[B_SC], B[B_SH2]
        d0, d1, d2 = B[B_V], B[B_GM], B[B_S]
        m = 0
        for k in range(nc):
            if far_[k] == 0.0:
                BI[0, m] = k
                lc, a_, b_ = Lc_[k], A[k], Bb[k]
                p0[m], p1[m], p2[m] = i2[0, 0] * lc, i2[1, 0] * lc, i2[2, 0] * lc
                d0[m] = i2[0, 1] * a_ + i2[0, 2] * b_
                d1[m] = i2[1, 1] * a_ + i2[1, 2] * b_
                d2[m] = i2[2, 1] * a_ + i2[2, 2] * b_
                jl[m] = 0.0
                jh[m] = top
                m += 1
        o00, o01, o02 = labout[0, 0], labout[0, 1], labout[0, 2]
        o10, o11, o12 = labout[1, 0], labout[1, 1], labout[1, 2]
        o20, o21, o22 = labout[2, 0], labout[2, 1], labout[2, 2]
        lot, hit = -tol, 1.0 + tol
        for _ in range(FL[F_NG]):
            for j in range(m):
                t = (jl[j] + jh[j]) * 0.5
                l_ = p0[j] + t * d0[j]
                m_ = p1[j] + t * d1[j]
                s_ = p2[j] + t * d2[j]
                l3, m3, s3 = l_ * l_ * l_, m_ * m_ * m_, s_ * s_ * s_
                q0 = o00 * l3 + o01 * m3 + o02 * s3
                q1 = o10 * l3 + o11 * m3 + o12 * s3
                q2 = o20 * l3 + o21 * m3 + o22 * s3
                ok = (min(q0, min(q1, q2)) >= lot) & (max(q0, max(q1, q2)) <= hit)
                jl[j] = t if ok else jl[j]
                jh[j] = jh[j] if ok else t
        for j in range(m):
            lo_[BI[0, j]] = jl[j]
        uu, th_, ex = B[B_T4], B[B_T5], B[B_T6]
        for k in range(nc):
            u = 1.0 / max(lo_[k], 1e-6)
            uu[k] = u
            th_[k] = -2.0 * abs((u - knee) / max(1.0 - knee, 1e-6)) * LOG2E
        _exp2(th_, ex, ti, nc)
        for k in range(nc):
            u = uu[k]
            if soft_gamut:
                q = (u - knee) / max(1.0 - knee, 1e-6)
                tq = (1.0 - ex[k]) / (1.0 + ex[k])
                fk = u if u <= knee else knee + (1.0 - knee) * (tq if q >= 0.0 else -tq)
            else:
                fk = min(u, 1.0)
            far = far_[k] > 0.0
            sc = 1.0 if far else fk / u
            x = cand[k]
            if not (far and bads[k] == 0):
                l = L[k]
                if l >= 1.0:
                    O0[x] = 1.0
                    O1[x] = 1.0
                    O2[x] = 1.0
                elif l <= 0.0:
                    O0[x] = 0.0
                    O1[x] = 0.0
                    O2[x] = 0.0
                else:
                    g0, g1, g2 = _from_lab(Lc_[k], A[k] * sc, Bb[k] * sc, i2, labout)
                    O0[x], O1[x], O2[x] = min(max(g0, 0.0), 1.0), min(max(g1, 0.0), 1.0), min(max(g2, 0.0), 1.0)
    for x in range(n):
        O0[x] = math.sqrt(math.sqrt(O0[x]))
        O1[x] = math.sqrt(math.sqrt(O1[x]))
        O2[x] = math.sqrt(math.sqrt(O2[x]))
    for x in range(n):
        O0[x] = _lut1(O0[x], enc)
        O1[x] = _lut1(O1[x], enc)
        O2[x] = _lut1(O2[x], enc)
    if FL[F_LUT]:
        nl = lut.shape[0]
        la_ = P[P_LUTAMT]
        for x in range(n):
            e0, e1, e2 = O0[x], O1[x], O2[x]
            fr = min(max(e0, 0.0), 1.0) * (nl - 1)
            fg = min(max(e1, 0.0), 1.0) * (nl - 1)
            fb = min(max(e2, 0.0), 1.0) * (nl - 1)
            ir, ig, ib = min(int(fr), nl - 2), min(int(fg), nl - 2), min(int(fb), nl - 2)
            fr -= ir
            fg -= ig
            fb -= ib
            t0 = t1 = t2 = 0.0
            for kk in range(8):
                db, dg, dr = (kk >> 2) & 1, (kk >> 1) & 1, kk & 1
                wgt = (fb if db else 1.0 - fb) * (fg if dg else 1.0 - fg) * (fr if dr else 1.0 - fr)
                t0 += lut[ib + db, ig + dg, ir + dr, 0] * wgt
                t1 += lut[ib + db, ig + dg, ir + dr, 1] * wgt
                t2 += lut[ib + db, ig + dg, ir + dr, 2] * wgt
            O0[x] = e0 + la_ * (t0 - e0)
            O1[x] = e1 + la_ * (t1 - e1)
            O2[x] = e2 + la_ * (t2 - e2)
    if FL[F_VIG]:
        Wd, Hd = max(P[P_OUTW], 1.0), max(P[P_OUTH], 1.0)
        Lg = max(Wd, Hd)
        rho = P[P_VROUND]
        pw = P[P_VPOW]
        yg = y + P[P_RY]
        sx = 1.0 + (Wd / Lg - 1.0) * rho if rho > 0 else 1.0
        sy = 1.0 + (Hd / Lg - 1.0) * rho if rho > 0 else 1.0
        Yv = abs(((yg + 0.5) / Hd * 2.0 - 1.0) * sy) + 1e-9
        t0, t1, t2, t3 = B[B_T0], B[B_T1], B[B_T2], B[B_T3]
        if pw == 2.0:
            for x in range(n):
                X = abs(((x + P[P_RX] + 0.5) / Wd * 2.0 - 1.0) * sx) + 1e-9
                t2[x] = math.sqrt(X * X + Yv * Yv)
        else:
            for x in range(n):
                t0[x] = abs(((x + P[P_RX] + 0.5) / Wd * 2.0 - 1.0) * sx) + 1e-9
            _log2(t0, t2, t3, ti, n)
            ly = math.log2(Yv)
            for x in range(n):
                t2[x] = pw * t2[x]
                t3[x] = pw * ly
            _exp2(t2, t0, ti, n)
            _exp2(t3, t1, ti, n)
            for x in range(n):
                t2[x] = t0[x] + t1[x]
            _log2(t2, t3, t0, ti, n)
            for x in range(n):
                t3[x] = t3[x] / pw
            _exp2(t3, t2, ti, n)
        amt = P[P_VAMT]
        for x in range(n):
            wv = _smooth(P[P_VIN], P[P_VOUT], t2[x])
            t2[x] = wv
            t3[x] = amt * K[K_VIGSTOPS] * wv
        _exp2(t3, t1, ti, n)
        style = P[P_VSTYLE]
        if style == 2.0:
            tg = 0.0 if amt < 0 else 1.0
            for x in range(n):
                kk = t2[x] * abs(amt) * K[K_VPAINT]
                O0[x] += kk * (tg - O0[x])
                O1[x] += kk * (tg - O1[x])
                O2[x] += kk * (tg - O2[x])
        else:
            Q0, Q1, Q2 = B[B_Q0], B[B_Q1], B[B_Q2]
            for x in range(n):
                if t2[x] <= 0.0:
                    Q0[x] = 0.0
                    Q1[x] = 0.0
                    Q2[x] = 0.0
                    continue
                e0, e1, e2 = O0[x], O1[x], O2[x]
                l0, l1, l2 = _lut1(e0, dec), _lut1(e1, dec), _lut1(e2, dec)
                gain = t1[x]
                if amt < 0:
                    if P[P_VHLV] > 0:
                        gain = gain + (1.0 - gain) * P[P_VHLV] * _smooth(K[K_VPROT], 1.0, max(e0, max(e1, e2)))
                    l0, l1, l2 = l0 * gain, l1 * gain, l2 * gain
                elif style == 0.0:
                    l0 = l0 * gain / (1.0 + (gain - 1.0) * l0)
                    l1 = l1 * gain / (1.0 + (gain - 1.0) * l1)
                    l2 = l2 * gain / (1.0 + (gain - 1.0) * l2)
                else:
                    l0, l1, l2 = l0 * gain, l1 * gain, l2 * gain
                    mx = max(max(l0, max(l1, l2)), 1.0)
                    l0, l1, l2 = l0 / mx, l1 / mx, l2 / mx
                Q0[x] = min(max(l0, 0.0), 1.0)
                Q1[x] = min(max(l1, 0.0), 1.0)
                Q2[x] = min(max(l2, 0.0), 1.0)
            for x in range(n):
                Q0[x] = math.sqrt(math.sqrt(Q0[x]))
                Q1[x] = math.sqrt(math.sqrt(Q1[x]))
                Q2[x] = math.sqrt(math.sqrt(Q2[x]))
            for x in range(n):
                if t2[x] > 0.0:
                    O0[x] = _lut1(Q0[x], enc)
                    O1[x] = _lut1(Q1[x], enc)
                    O2[x] = _lut1(Q2[x], enc)
    if FL[F_GRAIN]:
        cell = P[P_GCELL]
        yg = y + P[P_RY]
        for x in range(n):
            xg = x + P[P_RX]
            nn = (_vnoise(xg, yg, cell, 17) * P[P_GA] + _vnoise(xg, yg, cell * 0.5, 91) * P[P_GB]) * P[P_GK]
            e0, e1, e2 = O0[x], O1[x], O2[x]
            lum = 0.2126 * e0 + 0.7152 * e1 + 0.0722 * e2
            gv = P[P_GGAIN] * nn * (K[K_GM0] + K[K_GM1] * lum * (1.0 - lum))
            O0[x], O1[x], O2[x] = e0 + gv, e1 + gv, e2 + gv
    if FL[F_TRC]:
        for x in range(n):
            O0[x] = math.sqrt(math.sqrt(min(max(O0[x], 0.0), 1.0)))
            O1[x] = math.sqrt(math.sqrt(min(max(O1[x], 0.0), 1.0)))
            O2[x] = math.sqrt(math.sqrt(min(max(O2[x], 0.0), 1.0)))
        for x in range(n):
            O0[x] = _lut1(O0[x], trc)
            O1[x] = _lut1(O1[x], trc)
            O2[x] = _lut1(O2[x], trc)
    for x in range(n):
        out[y, x, 0] = min(max(O0[x], 0.0), 1.0)
        out[y, x, 1] = min(max(O1[x], 0.0), 1.0)
        out[y, x, 2] = min(max(O2[x], 0.0), 1.0)


@njit(cache=True, parallel=True, fastmath=True)
def _run(lin, out, nch, P, FL, K, tone_e, tone_g, sat_lut, par_y, par_d, enc, dec, trc, ccurve, m0, m1, m2, i1, i2, labout, mout, luma,
         luma_o, mixl, bwl, grade, pts, npts, alphas, lrows, lwb, mpts, mnpts, mccurve, mcflag, hs, dc, dt, hd, ds, edge, soft, nrd, ratio, lut):
    h, w = lin.shape[0], lin.shape[1]
    for c in prange(nch):
        B = np.empty((NB, w))
        BI = np.empty((3, w), np.int64)
        for y in range(c, h, nch):
            _row(y, B, BI, lin, out, P, FL, K, tone_e, tone_g, sat_lut, par_y, par_d, enc, dec, trc, ccurve, m0, m1, m2, i1, i2, labout, mout,
                 luma, luma_o, mixl, bwl, grade, pts, npts, alphas, lrows, lwb, mpts, mnpts, mccurve, mcflag, hs, dc, dt, hd, ds, edge, soft,
                 nrd, ratio, lut)


_Z2 = np.zeros((1, 1), np.float32)
_Z3 = np.zeros((1, 1, 3), np.float32)


def _own(a: np.ndarray, dt) -> np.ndarray:
    b = np.ascontiguousarray(a, dt)
    return b if b.flags.writeable else b.copy()


def _f32(a, fallback=None):
    if a is None:
        return _Z2 if fallback is None else fallback
    return _own(a, np.float32)


def _f64(a) -> np.ndarray:
    return _own(a, np.float64)


def _pack(p, lin: np.ndarray) -> tuple:
    from app.develop import colour
    P = np.zeros(NP_, np.float64)
    FL = np.zeros(NF, np.int64)
    P[P_EV], P[P_CON], P[P_HL], P[P_SH], P[P_WH], P[P_BL] = p.ev, p.con, p.hl, p.sh, p.wh, p.bl
    P[P_TEX], P[P_CLA], P[P_DHZ], P[P_VIB], P[P_SAT] = p.tex, p.cla, p.dhz, p.vib, p.sat
    P[P_VHL], P[P_VSH], P[P_VWH], P[P_VBL], P[P_VMID] = p.v_hl, p.v_sh, p.v_wh, p.v_bl, p.v_mid
    P[P_AIR], P[P_STINT], P[P_SATG] = p.air, p.stint, p.sat_gain
    P[P_SAMT], P[P_SCORE], P[P_STCL], P[P_SMASK], P[P_STHR], P[P_SCALE] = p.s_amt, p.s_core, p.s_tcl, p.s_mask, p.s_thr, p.scale
    P[P_REFINE], P[P_KNEE], P[P_LUTAMT] = p.refine, p.knee, p.lut_amt
    P[P_VAMT], P[P_VROUND], P[P_VPOW], P[P_VIN], P[P_VOUT], P[P_VHLV], P[P_VSTYLE] = p.v_amt, p.v_round, p.v_pow, p.v_inner, p.v_outer, p.v_hl, p.v_style
    P[P_GGAIN], P[P_GCELL] = p.g_gain, p.g_cell
    P[P_GA], P[P_GB], P[P_GK] = F.grain_mix(p.g_rough)
    P[P_OUTW], P[P_OUTH], P[P_RX], P[P_RY] = max(p.out_w, 1), max(p.out_h, 1), p.rx, p.ry
    P[P_GTS], P[P_GTH], P[P_GWD] = p.gshape
    P[P_EVSEL] = 2.0 ** p.ev
    P[P_GE] = math.exp2(p.ev)
    FL[F_HL], FL[F_SH], FL[F_CLA], FL[F_TEX], FL[F_DHZ] = p.do_hl, p.do_sh, p.do_cla, p.do_tex, p.do_dhz
    FL[F_CON], FL[F_WH], FL[F_BL], FL[F_SAT], FL[F_HUE], FL[F_TINT] = p.do_con, p.do_wh, p.do_bl, p.do_sat, p.do_hue, p.do_tint
    FL[F_DF] = p.do_df and p.edge is not None
    FL[F_SOFT], FL[F_NZ], FL[F_RATIO] = p.do_soft, p.do_nz, p.do_ratio
    FL[F_SHARP] = p.do_sharp and p.ds is not None
    FL[F_PTS], FL[F_MCURVE], FL[F_CURVE], FL[F_LAB], FL[F_HUEMOD] = p.do_pts, p.do_mcurve, p.do_curve, p.do_lab, p.hue_mod
    FL[F_PAR] = p.par is not None
    FL[F_M0], FL[F_LWB], FL[F_STINT] = p.use_m0, p.local_wb, bool(p.stint)
    FL[F_MIXER], FL[F_BW], FL[F_GRADE], FL[F_VIB] = p.mixer is not None, p.bw, p.grade is not None, bool(p.vib)
    FL[F_LUT] = p.lut is not None and p.lut_amt > 0
    FL[F_VIG], FL[F_GRAIN], FL[F_TRC] = bool(p.do_vig and p.v_amt), p.do_grain, p.trc is not None
    FL[F_NM] = p.n_masks
    FL[F_REFINE] = p.do_curve and p.refine < 1.0
    FL[F_GLOBPTS] = p.points is not None
    FL[F_NG] = F.NG
    nm = p.n_masks
    enc = cv.enc_lut("srgb")
    par_y, par_d = p.par if p.par is not None else (enc[:2], enc[:2])
    ident = np.zeros((3, cv.NE), np.float32)
    ccurve = np.stack(p.ccurve).astype(np.float32) if p.ccurve is not None else ident
    mixl = np.ascontiguousarray(p.mix_lut.T, np.float32) if p.mix_lut is not None else np.zeros((3, 2), np.float32)
    bwl = _f32(p.bw_lut) if p.bw_lut is not None else np.zeros(2, np.float32)
    m1, i1, m2, i2 = co.lab_mats()
    pts = np.zeros((8, 10), np.float64)
    npts = 0
    if p.points is not None:
        npts = len(p.points)
        pts[:npts] = p.points
    if nm:
        alphas = np.ascontiguousarray(np.stack([np.asarray(a, np.float32) for a in p.alphas]), np.float32)
        lrows, lwb = _f64(p.lrows), _f64(p.lwb)
        mpts = np.zeros((nm, 8, 10), np.float64)
        mnpts = np.zeros(nm, np.int64)
        mccurve = np.zeros((nm, 3, cv.NE), np.float32)
        mcflag = np.zeros(nm, np.int64)
        for m in range(nm):
            if p.mpoints[m] is not None:
                mnpts[m] = len(p.mpoints[m])
                mpts[m, :mnpts[m]] = p.mpoints[m]
            if p.mccurve[m] is not None:
                mccurve[m] = np.stack(p.mccurve[m])
                mcflag[m] = 1
    else:
        alphas = np.zeros((1, 1, 1), np.float32)
        lrows, lwb = np.zeros((1, F.NL)), np.zeros((1, 3, 3))
        mpts, mnpts = np.zeros((1, 8, 10)), np.zeros(1, np.int64)
        mccurve, mcflag = np.zeros((1, 3, cv.NE), np.float32), np.zeros(1, np.int64)
    lut = _f32(p.lut) if FL[F_LUT] else np.zeros((2, 2, 2, 3), np.float32)
    trc = _f32(p.trc) if p.trc is not None else np.zeros(2, np.float32)
    grade = _f64(p.grade) if p.grade is not None else np.zeros((4, 3))
    nch = max(1, numba.get_num_threads())
    return (_f32(lin), nch, P, FL, constants(), _f32(p.tone_e), _f32(p.tone_g), _f32(p.sat_lut), _f32(par_y),
            _f32(par_d), _f32(p.enc), _f32(p.dec), trc, ccurve, _f64(p.m0), _f64(m1), _f64(m2), _f64(i1), _f64(i2), _f64(p.lab_out),
            _f64(p.mout), _f64(colour.LUMA_2020), _f64(p.luma_out), mixl, bwl, grade, pts, npts, alphas, lrows, lwb, mpts, mnpts, mccurve,
            mcflag, _f32(p.hs), _f32(p.dc), _f32(p.dt), _f32(p.hd), _f32(p.ds), _f32(p.edge), _f32(p.soft), _f32(p.nrd), _f32(p.ratio, _Z3), lut)


def finish_compiled(lin: np.ndarray, planes: dict, dev: dict, frame, info: dict, out_w: int, out_h: int, ppl: float, evaluated: list,
                    space: str = "srgb", region=(0, 0)) -> np.ndarray:
    p = F.prepare(lin, planes, dev, frame, info, out_w, out_h, ppl, evaluated, space, region)
    args = _pack(p, lin)
    out = np.empty((p.h, p.w, 3), np.float32)
    with pool.LOCK:
        _run(args[0], out, *args[1:])
    return out


_state = {"ready": False}
_lock = threading.Lock()


def best_finish():
    return finish_compiled if _state["ready"] else F.finish


def _probe() -> tuple:
    rng = np.random.default_rng(7)
    h, w = 24, 32
    lin = (rng.random((h, w, 3)) ** 2 * 1.2).astype(np.float32)
    info = {"raw": True, "fullWidth": 64, "fullHeight": 48}
    dev = {"light": {"exposure": 0.3, "contrast": 20, "highlights": -30, "shadows": 30, "whites": 10, "blacks": -10},
           "color": {"vibrance": 20, "saturation": 10}, "effects": {"clarity": 20, "texture": 20, "dehaze": 10},
           "mixer": {"blue": {"hue": 20, "sat": -10, "lum": -10}}, "grading": {"shadows": {"hue": 200, "sat": 20}},
           "curve": {"lights": 10, "master": [[0, 0], [0.5, 0.55], [1, 1]], "refineSaturation": 80},
           "detail": {"sharpenAmount": 40, "sharpenMasking": 20}, "vignette": {"amount": -20, "roundness": -30}, "grain": {"amount": 20},
           "pointColors": [{"hue": 30, "chroma": 0.05, "lum": 0.5, "hueShift": 10, "satShift": 10, "lumShift": 0, "variance": 10, "range": 50}],
           "calibration": {"redHue": 10, "shadowsTint": 10}, "treatment": "bw"}
    alpha = np.linspace(0, 1, h * w, dtype=np.float32).reshape(h, w)
    mask = {"id": 1, "adjust": {"exposure": 0.3, "clarity": 20, "temp": 20, "sharpness": -30, "noise": 20, "moire": 20, "defringe": 30, "hue": 10,
                                "colorSat": 30, "colorHue": 200, "curve": {"red": [[0, 0], [0.5, 0.6], [1, 1]]},
                                "pointColors": [{"hue": 200, "chroma": 0.05, "lum": 0.5, "satShift": 20}]}}
    return lin, info, dev, [(alpha, mask, 1)], h, w


def warm() -> None:
    from app.develop import planes as pl
    with _lock:
        if _state["ready"]:
            return
        lin, info, dev, ev, h, w = _probe()
        ok = True
        for space in ("srgb", "adobergb"):
            planes: dict = {}
            pl.build(planes, lin, dev, float(w))
            a = finish_compiled(lin, planes, dev, None, info, w, h, float(w), ev, space)
            b = F.finish(lin, planes, dev, None, info, w, h, float(w), ev, space)
            ok = ok and bool(np.all(np.isfinite(a))) and float(np.abs(a - b).max()) < 2e-4
        _state["ready"] = ok


__all__ = ["best_finish", "warm", "finish_compiled", "constants"]
