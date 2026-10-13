from typing import Any

from app.engine import catalog as catalog_mod
from app.engine.commands import command, resolve_ids


@command("library.refine", "Refine Photos", {"ids": {"type": "array", "description": "the photos of the cull pass, usually a whole folder or collection"}},
         description="Lightroom's Refine Photos for a multi-pass cull: unflagged photos become rejects and picks become unflagged, so the next pass starts from the surviving picks. Rejects stay rejects. One undo step.")
def refine(ids: Any = None) -> dict:
    pids = resolve_ids(ids)
    c = catalog_mod.get()
    rejected, cleared = [], []
    with c.change("Refine Photos") as ch:
        for pid in pids:
            row = c.db.execute("SELECT flag FROM photos WHERE id=?", (pid,)).fetchone()
            if row is None:
                continue
            flag = int(row["flag"] or 0)
            if flag == 0:
                ch.update("photos", pid, flag=-1)
                rejected.append(pid)
            elif flag == 1:
                ch.update("photos", pid, flag=0)
                cleared.append(pid)
    return {"rejected": len(rejected), "unflagged": len(cleared), "kept": cleared}


ISO_BANDS = [(12800, "builtin:noise-by-iso/iso-12800"), (6400, "builtin:noise-by-iso/iso-6400"), (3200, "builtin:noise-by-iso/iso-3200"),
             (1600, "builtin:noise-by-iso/iso-1600"), (800, "builtin:noise-by-iso/iso-800")]


def iso_preset(iso: Any) -> str | None:
    try:
        value = float(iso)
    except (TypeError, ValueError):
        return None
    return next((pid for floor, pid in ISO_BANDS if value >= floor), None)


@command("develop.noiseByIso", "Noise Reduction by ISO", {"ids": {"type": "array"}, "amount": {"type": "number"}},
         description="Lightroom's ISO adaptive presets: gives each photo the Noise by ISO preset for its own ISO (800, 1600, 3200, 6400, 12800 and up), touching only Detail, in one undo step. Photos under ISO 800 or without ISO are left alone and counted.")
def noise_by_iso(ids: Any = None, amount: float = 100.0) -> dict:
    from app.engine.cmd_develop import after, current, store
    from app.engine.presets import blended
    pids = resolve_ids(ids)
    c = catalog_mod.get()
    applied: dict[str, list[int]] = {}
    low, unknown = [], []
    with c.change("Noise Reduction by ISO") as ch:
        for pid in pids:
            row = c.db.execute("SELECT iso FROM photos WHERE id=?", (pid,)).fetchone()
            if row is None:
                continue
            preset = iso_preset(row["iso"])
            if preset is None:
                (unknown if row["iso"] in (None, "", 0) else low).append(pid)
                continue
            dev, _ = current(pid)
            store(ch, pid, blended(dev, preset, amount), "Noise Reduction by ISO")
            applied.setdefault(preset.rsplit("/", 1)[1].upper().replace("ISO-", "ISO "), []).append(pid)
    touched = [p for v in applied.values() for p in v]
    if touched:
        after(touched)
    return {"applied": {k: len(v) for k, v in applied.items()}, "underIso800": len(low), "noIso": len(unknown), "ids": touched}
