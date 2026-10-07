import numpy as np
from numba import njit, prange


@njit(cache=True, inline="always")
def _enc(v):
    v = min(max(v, 0.0), 1.0)
    return v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1.0 / 2.4) - 0.055


@njit(cache=True, inline="always")
def _dec(v):
    v = min(max(v, 0.0), 1.0)
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


@njit(cache=True, parallel=True)
def table(rgb, deltas, srgb, vscale):
    n = rgb.shape[0]
    vd, hd, sd = deltas.shape[0], deltas.shape[1], deltas.shape[2]
    out = np.empty_like(rgb)
    for i in prange(n):
        r = max(rgb[i, 0], 0.0)
        g = max(rgb[i, 1], 0.0)
        b = max(rgb[i, 2], 0.0)
        v = max(r, max(g, b))
        mn = min(r, min(g, b))
        d = v - mn
        s = d / max(v, 1e-12) if v > 0.0 else 0.0
        sd_ = max(d, 1e-12)
        if d > 0.0:
            if r == v:
                h = (g - b) / sd_
            elif g == v:
                h = 2.0 + (b - r) / sd_
            else:
                h = 4.0 + (r - g) / sd_
            h = h % 6.0
        else:
            h = 0.0
        vs = min(v * vscale, 1.0)
        vv = _enc(vs) if srgb else vs
        hf = h * hd / 6.0
        fl = np.floor(hf)
        h0 = int(fl) % hd
        h1 = (h0 + 1) % hd
        fh = hf - fl
        sf = min(max(s, 0.0), 1.0) * (sd - 1)
        s0 = min(int(np.floor(sf)), max(0, sd - 2))
        s1 = min(s0 + 1, sd - 1)
        fs = sf - s0
        if vd > 1:
            vf = min(max(vv, 0.0), 1.0) * (vd - 1)
            v0 = min(int(np.floor(vf)), vd - 2)
            v1 = v0 + 1
            fv = vf - v0
        else:
            v0 = 0
            v1 = 0
            fv = 0.0
        a0 = 0.0
        a1 = 0.0
        a2 = 0.0
        for k in range(8):
            vi = v1 if k & 4 else v0
            wv = fv if k & 4 else 1.0 - fv
            hi = h1 if k & 2 else h0
            wh = fh if k & 2 else 1.0 - fh
            si = s1 if k & 1 else s0
            ws = fs if k & 1 else 1.0 - fs
            w = wv * wh * ws
            a0 += deltas[vi, hi, si, 0] * w
            a1 += deltas[vi, hi, si, 1] * w
            a2 += deltas[vi, hi, si, 2] * w
        h2 = (h + a0 * 6.0 / 360.0) % 6.0
        s2 = min(max(s * a1, 0.0), 1.0)
        if srgb:
            v2 = v * _dec(vv * a2) / max(vs, 1e-12)
        else:
            v2 = v * a2
        sec = np.floor(h2)
        f = h2 - sec
        p = v2 * (1.0 - s2)
        q = v2 * (1.0 - s2 * f)
        t = v2 * (1.0 - s2 * (1.0 - f))
        j = int(sec)
        if j == 0:
            out[i, 0], out[i, 1], out[i, 2] = v2, t, p
        elif j == 1:
            out[i, 0], out[i, 1], out[i, 2] = q, v2, p
        elif j == 2:
            out[i, 0], out[i, 1], out[i, 2] = p, v2, t
        elif j == 3:
            out[i, 0], out[i, 1], out[i, 2] = p, q, v2
        elif j == 4:
            out[i, 0], out[i, 1], out[i, 2] = t, p, v2
        else:
            out[i, 0], out[i, 1], out[i, 2] = v2, p, q
    return out
