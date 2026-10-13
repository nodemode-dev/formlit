import json

import numpy as np

from app.develop import settings as S
from app.engine import catalog as catalog_mod
from app.engine.commands import CommandError, command
from app.engine.records import loads

LONG = 640
BANDS = (("red", 345, 15), ("orange", 15, 45), ("yellow", 45, 70), ("green", 70, 160), ("aqua", 160, 200), ("blue", 200, 250), ("purple", 250, 290), ("magenta", 290, 345))
ZONES = (("blacks", 0, 10), ("shadows", 10, 30), ("midtones", 30, 70), ("highlights", 70, 90), ("whites", 90, 101))


def _settings(pid: int, values: dict | None, preset: str | None, amount: float) -> dict | None:
    if not values and not preset:
        return None
    row = catalog_mod.get().row("SELECT develop FROM photos WHERE id=?", (pid,))
    if row is None:
        raise CommandError(f"No photo with id {pid}", 404)
    dev = json.loads(json.dumps(loads(row["develop"], {})))
    if preset:
        from app.engine import presets
        dev = presets.blended(dev, preset, amount)
    for k, v in (values or {}).items():
        if k not in S.controls():
            raise CommandError(f"Unknown control {k}; list them with develop.controls")
        S.put(dev, k, float(v))
    return dev


def _hsv(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mx = rgb.max(axis=1)
    mn = rgb.min(axis=1)
    d = mx - mn
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0.0)
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    safe = np.maximum(d, 1e-6)
    h = np.where(mx == r, ((g - b) / safe) % 6, np.where(mx == g, (b - r) / safe + 2, (r - g) / safe + 4)) * 60.0
    return np.where(d > 1e-6, h, 0.0), s, mx


def measure(rgb8: np.ndarray) -> dict:
    px = rgb8.reshape(-1, 3).astype(np.float32) / 255.0
    lum = (px @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)) * 100.0
    h, s, v = _hsv(px)
    pct = {f"p{p}": round(float(np.percentile(lum, p)), 1) for p in (1, 5, 50, 95, 99)}
    zones = {name: round(float(((lum >= lo) & (lum < hi)).mean()) * 100, 1) for name, lo, hi in ZONES}
    clipped_hi = float((rgb8.reshape(-1, 3) >= 254).any(axis=1).mean()) * 100
    clipped_all = float((rgb8.reshape(-1, 3) >= 254).all(axis=1).mean()) * 100
    crushed = float((rgb8.reshape(-1, 3) <= 2).all(axis=1).mean()) * 100
    neutral = (s < 0.18) & (lum > 20) & (lum < 85)
    cast = {"warmCool": 0.0, "greenMagenta": 0.0, "neutralShare": round(float(neutral.mean()) * 100, 1)}
    if neutral.sum() > 200:
        n = px[neutral]
        r, g, b = n[:, 0].mean(), n[:, 1].mean(), n[:, 2].mean()
        cast["warmCool"] = round(float((r - b) * 100), 1)
        cast["greenMagenta"] = round(float(((r + b) / 2 - g) * 100), 1)
    colored = s > 0.15
    bands = {}
    for name, lo, hi in BANDS:
        sel = colored & ((h >= lo) & (h < hi) if lo < hi else ((h >= lo) | (h < hi)))
        share = float(sel.mean()) * 100
        if share >= 0.5:
            bands[name] = {"share": round(share, 1), "sat": round(float(s[sel].mean()) * 100, 1), "lum": round(float(lum[sel].mean()), 1)}
    return {
        "luminance": {"mean": round(float(lum.mean()), 1), **pct, "contrast": round(float(lum.std()), 1)},
        "zones": zones,
        "clipping": {"highlightsAnyChannel": round(clipped_hi, 2), "highlightsAllChannels": round(clipped_all, 2), "shadowsCrushed": round(crushed, 2)},
        "saturation": {"mean": round(float(s.mean()) * 100, 1), "nearMax": round(float(((s > 0.92) & (v > 0.25)).mean()) * 100, 2)},
        "cast": cast,
        "bands": dict(sorted(bands.items(), key=lambda kv: -kv[1]["share"])),
    }


def findings(m: dict, iso: float | None, treatment: str) -> list[dict]:
    out = []
    lum, z, c, sat, cast = m["luminance"], m["zones"], m["clipping"], m["saturation"], m["cast"]

    def say(issue: str, why: str, try_: dict) -> None:
        out.append({"issue": issue, "evidence": why, "try": try_})

    if c["highlightsAllChannels"] > 1.0:
        say("highlights clipped", f"{c['highlightsAllChannels']}% of pixels are white in every channel", {"light.highlights": -40, "light.whites": -20})
    elif c["highlightsAnyChannel"] > 3.0:
        say("a colour channel clips in the brights", f"{c['highlightsAnyChannel']}% of pixels hit 255 in at least one channel", {"light.whites": -15, "color.saturation": -5})
    if c["shadowsCrushed"] > 3.0:
        say("shadows crushed", f"{c['shadowsCrushed']}% of pixels are pure black", {"light.shadows": 25, "light.blacks": 15})
    if lum["p50"] < 25 and c["highlightsAnyChannel"] < 1.0:
        say("underexposed", f"median luminance {lum['p50']} of 100 (Adobe puts exposure in roughly the 30 to 70 band)", {"light.exposure": round(min(2.0, (40 - lum["p50"]) / 15), 2), "light.shadows": 20})
    elif lum["p50"] > 72 and c["highlightsAllChannels"] > 0.2:
        say("overexposed", f"median luminance {lum['p50']} with clipping", {"light.exposure": round(-min(2.0, (lum["p50"] - 55) / 15), 2), "light.highlights": -30})
    if lum["p99"] < 80 and c["highlightsAnyChannel"] < 0.2:
        say("no true whites, flat top end", f"99th percentile luminance is {lum['p99']}", {"light.whites": 20})
    if lum["p1"] > 12 and c["shadowsCrushed"] < 0.2:
        say("no true blacks, hazy or flat", f"1st percentile luminance is {lum['p1']}", {"light.blacks": -15, "effects.dehaze": 8})
    if lum["contrast"] < 14:
        say("low contrast", f"luminance spread (std) is {lum['contrast']}", {"light.contrast": 20, "effects.clarity": 8})
    elif lum["contrast"] > 32:
        say("very high contrast", f"luminance spread (std) is {lum['contrast']}", {"light.contrast": -15, "light.highlights": -25, "light.shadows": 25})
    if treatment != "bw" and cast["neutralShare"] > 3:
        basis = f"(from the {cast['neutralShare']}% of pixels that are near neutral; check it is not a deliberate mood)"
        if cast["warmCool"] > 6:
            say("warm cast in neutral areas", f"neutrals lean warm by {cast['warmCool']} {basis}", {"wb.temp": "lower by 300 to 800 K, or auto_white_balance"})
        elif cast["warmCool"] < -6:
            say("cool cast in neutral areas", f"neutrals lean cool by {abs(cast['warmCool'])} {basis}", {"wb.temp": "raise by 300 to 800 K, or auto_white_balance"})
        if cast["greenMagenta"] < -4:
            say("green cast", f"neutrals lean green by {abs(cast['greenMagenta'])}", {"wb.tint": 10})
        elif cast["greenMagenta"] > 4:
            say("magenta cast", f"neutrals lean magenta by {cast['greenMagenta']}", {"wb.tint": -10})
    if treatment != "bw":
        if sat["nearMax"] > 2.0:
            say("colours near clipping", f"{sat['nearMax']}% of pixels are almost fully saturated", {"color.saturation": -10, "color.vibrance": 5})
        elif sat["mean"] < 12:
            say("muted colour", f"mean saturation {sat['mean']}", {"color.vibrance": 20})
    if iso and iso >= 3200:
        say("high ISO", f"shot at ISO {int(iso)}", {"detail.nrLuminance": 25 if iso < 6400 else 40, "note": "or denoise first, before masks and retouching"})
    return out


@command("develop.analyze", "Analyze Photo", {"id": {"type": "integer"}, "values": {"type": "object"}, "preset": {"type": "string"}, "amount": {"type": "number"}}, mutates=False,
         description="Measures the photo as developed (or with proposed values or a preset, unsaved): luminance percentiles, tonal zones, clipping, saturation, colour cast in neutral areas, the share of each colour-mixer band, and findings with suggested develop values. Numbers are 0 to 100.")
def analyze(id: int, values: dict | None = None, preset: str | None = None, amount: float = 100.0) -> dict:
    from app.services import previews
    row = catalog_mod.get().row("SELECT develop, iso FROM photos WHERE id=?", (int(id),))
    if row is None:
        raise CommandError(f"No photo with id {id}", 404)
    dev = _settings(int(id), values, preset, float(amount))
    rgb = previews.render_rgb8(int(id), LONG, dev)
    m = measure(rgb)
    effective = dev if dev is not None else loads(row["develop"], {})
    treatment = (effective or {}).get("treatment", "color")
    iso = row["iso"] if "iso" in row.keys() and row["iso"] else None
    return {"id": int(id), "proposed": dev is not None, **m, "findings": findings(m, float(iso) if iso else None, treatment)}
