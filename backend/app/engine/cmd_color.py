import numpy as np

from app.develop import skin
from app.engine.cmd_develop import current
from app.engine.commands import command, resolve_ids
from app.services import previews

SKIN_HUES = (95.0, 165.0)


@command("develop.skinPick", "Skin Tone Selector", {"id": {"type": "integer"}, "x": {"type": "number", "minimum": 0, "maximum": 1}, "y": {"type": "number", "minimum": 0, "maximum": 1}}, mutates=False,
         description="Reads the colour at a point of the photo as it is rendered and returns its skin hue (the value for skin.hue, 0 to 360) and saturation, and whether it falls in the usual range of skin tones. Set skin.hue and the skin uniformity sliders with develop_set.")
def skin_pick(x: float, y: float, id: int | None = None) -> dict:
    from app.develop.render import effective, plan, render
    pid = int(id) if id is not None else resolve_ids("active")[0]
    dev, _ = current(pid)
    img, info = previews.source(pid)
    eff = effective(dev)
    sh, sw = img.shape[:2]
    frame, w, h, _ = plan(sw, sh, eff, 1024)
    off = {**dev, "skin": {}}
    out = render(img, info, off, 1024, photo_id=pid)
    p = frame.norm_to_out(w, h) @ np.array([float(x), float(y), 1.0])
    px, py = int(min(max(p[0], 0), out.shape[1] - 1)), int(min(max(p[1], 0), out.shape[0] - 1))
    r = max(2, int(min(out.shape[:2]) * 0.006))
    patch = out[max(0, py - r):py + r + 1, max(0, px - r):px + r + 1, :3]
    hue, sat = skin.hue_of(patch)
    return {"hue": int(round(hue)) % 360, "saturation": round(sat, 4), "skinLike": SKIN_HUES[0] <= hue <= SKIN_HUES[1] and sat > 0.02}
