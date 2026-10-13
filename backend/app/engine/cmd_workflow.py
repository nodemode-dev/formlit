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
