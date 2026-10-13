import json
from typing import Any

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


def summary(m: dict, found: list[dict]) -> dict:
    lum, c = m["luminance"], m["clipping"]
    return {"median": lum["p50"], "p1": lum["p1"], "p99": lum["p99"], "contrast": lum["contrast"], "clipHighlights": c["highlightsAllChannels"], "clipAnyChannel": c["highlightsAnyChannel"],
            "crushed": c["shadowsCrushed"], "saturation": m["saturation"]["mean"], "warmCool": m["cast"]["warmCool"], "greenMagenta": m["cast"]["greenMagenta"],
            "issues": [f["issue"] for f in found]}


def quick(pid: int, rgb8: np.ndarray | None = None) -> dict:
    from app.services import previews
    row = catalog_mod.get().row("SELECT develop, iso FROM photos WHERE id=?", (int(pid),))
    if row is None:
        raise CommandError(f"No photo with id {pid}", 404)
    m = measure(rgb8 if rgb8 is not None else previews.render_rgb8(int(pid), 384, None))
    treatment = (loads(row["develop"], {}) or {}).get("treatment", "color")
    return {"id": int(pid), **summary(m, findings(m, float(row["iso"]) if row["iso"] else None, treatment))}


MATCH_LONG = 384
MATCH_ROUNDS = 6
LIMITS = {"light.exposure": 1.5, "light.contrast": 60, "light.whites": 60, "light.blacks": 60, "light.highlights": 60, "light.shadows": 60, "color.saturation": 60, "color.vibrance": 40,
          "wb.temp": 3000, "wb.tint": 40, **{f"mixer.{b}.{k}": 50 for b, _, _ in BANDS for k in ("sat", "lum")}}


def _look(rgb8: np.ndarray) -> dict:
    m = measure(rgb8)
    px = rgb8.reshape(-1, 3).astype(np.float32) / 255.0
    m["tone"] = {"warm": float((px[:, 0] - px[:, 2]).mean() * 100), "green": float(((px[:, 0] + px[:, 2]) / 2 - px[:, 1]).mean() * 100)}
    return m


def _distance(a: dict, b: dict) -> float:
    la, lb = a["luminance"], b["luminance"]
    d = abs(la["p50"] - lb["p50"]) * 1.0 + abs(la["contrast"] - lb["contrast"]) * 1.2 + abs(la["p5"] - lb["p5"]) * 0.6 + abs(la["p95"] - lb["p95"]) * 0.6
    d += abs(a["saturation"]["mean"] - b["saturation"]["mean"]) * 1.2
    d += abs(a["tone"]["warm"] - b["tone"]["warm"]) * 1.0 + abs(a["tone"]["green"] - b["tone"]["green"]) * 1.5
    for band, r in b["bands"].items():
        c = a["bands"].get(band)
        if c and r["share"] >= 1.0:
            d += (abs(r["sat"] - c["sat"]) * 0.25 + abs(r["lum"] - c["lum"]) * 0.15) * min(1.0, r["share"] / 20.0)
    return round(d, 2)


def _step(dev: dict, cur: dict, ref: dict, base: dict, tone: bool, color: bool) -> dict:
    out = json.loads(json.dumps(dev))
    lc, lr = cur["luminance"], ref["luminance"]

    def nudge(cid: str, delta: float) -> None:
        now = S.get(out, cid)
        lim = LIMITS.get(cid)
        start = S.get(base, cid)
        val = now + delta
        if lim is not None:
            val = max(start - lim, min(start + lim, val))
        S.put(out, cid, val)

    if tone:
        nudge("light.exposure", (lr["p50"] - lc["p50"]) / 22.0)
        nudge("light.contrast", (lr["contrast"] - lc["contrast"]) * 2.2)
        nudge("light.highlights", (lr["p95"] - lc["p95"]) * 1.2)
        nudge("light.shadows", (lr["p5"] - lc["p5"]) * 1.2)
        nudge("light.whites", (lr["p99"] - lc["p99"]) * 0.8)
        nudge("light.blacks", (lr["p1"] - lc["p1"]) * 0.8)
    if color:
        nudge("color.saturation", (ref["saturation"]["mean"] - cur["saturation"]["mean"]) * 1.6)
        nudge("wb.temp", (ref["tone"]["warm"] - cur["tone"]["warm"]) * 45.0)
        nudge("wb.tint", (ref["tone"]["green"] - cur["tone"]["green"]) * 2.0)
        for band, r in ref["bands"].items():
            c = cur["bands"].get(band)
            if c and r["share"] >= 1.0 and c["share"] >= 1.0:
                nudge(f"mixer.{band}.sat", (r["sat"] - c["sat"]) * 0.9)
                nudge(f"mixer.{band}.lum", (r["lum"] - c["lum"]) * 0.7)
    return out


@command("develop.match", "Match Look", {"ids": {"type": "array"}, "reference": {"type": "integer"}, "strength": {"type": "number"},
                                         "tone": {"type": "boolean"}, "color": {"type": "boolean"}, "apply": {"type": "boolean"}},
         description="Matches photos to a reference photo's look as developed: measures the reference, then adjusts each target's exposure, contrast, highlights, shadows, whites, blacks, saturation and white balance over several internal render and measure rounds until their tone and colour statistics converge. strength 0 to 100 scales the result; tone or color false leaves that part alone; apply false returns the proposal without saving.")
def match(reference: int, ids: Any = None, strength: float = 100.0, tone: bool = True, color: bool = True, apply: bool = True) -> dict:
    from app.engine.cmd_develop import after, current, seed_wb, store
    from app.engine.commands import resolve_ids
    from app.services import previews
    pids = [p for p in resolve_ids(ids) if p != int(reference)]
    if not pids:
        raise CommandError("ids must name at least one photo other than the reference")
    ref = _look(previews.render_rgb8(int(reference), MATCH_LONG, None))
    results, staged = [], []
    for pid in pids:
        dev, _ = current(pid)
        if color:
            dev = seed_wb(pid, dev)
        base = json.loads(json.dumps(dev))
        cur = _look(previews.render_rgb8(pid, MATCH_LONG, dev))
        start_d = _distance(cur, ref)
        best, best_d = dev, start_d
        for _ in range(MATCH_ROUNDS):
            dev = _step(dev, cur, ref, base, tone, color)
            cur = _look(previews.render_rgb8(pid, MATCH_LONG, dev))
            d = _distance(cur, ref)
            if d < best_d:
                best, best_d = dev, d
            elif d > best_d * 1.15:
                break
        k = max(0.0, min(1.0, float(strength) / 100.0))
        final = json.loads(json.dumps(base))
        changed = {}
        for cid in LIMITS:
            a, b = S.get(base, cid), S.get(best, cid)
            if abs(b - a) > 1e-6:
                S.put(final, cid, a + (b - a) * k)
                changed[cid] = round(S.get(final, cid) - a, 3)
        end = _look(previews.render_rgb8(pid, MATCH_LONG, final))
        staged.append((pid, final))
        results.append({"id": pid, "changes": changed, "distanceBefore": start_d, "distanceAfter": _distance(end, ref),
                        "after": {"median": end["luminance"]["p50"], "contrast": end["luminance"]["contrast"], "saturation": end["saturation"]["mean"]},
                        "reference": {"median": ref["luminance"]["p50"], "contrast": ref["luminance"]["contrast"], "saturation": ref["saturation"]["mean"]}})
    if apply:
        with catalog_mod.get().change("Match Look") as ch:
            for pid, final in staged:
                store(ch, pid, final, "Match Look")
        after([p for p, _ in staged])
    return {"reference": int(reference), "applied": bool(apply), "results": results,
            "note": "distance is a weighted gap in median, contrast, end points, saturation and colour balance; lower is closer. Grading, masks and creative colour are not copied: add them with presets or develop_set."}


@command("develop.analyze", "Analyze Photo", {"id": {"type": "integer"}, "ids": {"type": "array"}, "values": {"type": "object"}, "preset": {"type": "string"}, "amount": {"type": "number"}}, mutates=False,
         description="Measures the photo as developed (or with proposed values or a preset, unsaved): luminance percentiles, tonal zones, clipping, saturation, colour cast in neutral areas, the share of each colour-mixer band, and findings with suggested develop values. Numbers are 0 to 100. With ids instead of id, returns a compact line per photo (up to 60) for checking a set at once.")
def analyze(id: int | None = None, ids: Any = None, values: dict | None = None, preset: str | None = None, amount: float = 100.0) -> dict:
    from app.services import previews
    if id is None:
        from app.engine.commands import resolve_ids
        pids = resolve_ids(ids)[:60]
        rows = [quick(p) for p in pids]
        med = [r["median"] for r in rows]
        return {"photos": rows, "count": len(rows), "spread": {"median": round(max(med) - min(med), 1) if med else 0.0,
                                                               "contrast": round(max(r["contrast"] for r in rows) - min(r["contrast"] for r in rows), 1) if rows else 0.0}}
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
