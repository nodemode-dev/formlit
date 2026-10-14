import copy
from typing import Any

from app.develop import settings as S
from app.develop.layers import MAX_LAYERS, layerable
from app.engine.cmd_develop import current
from app.engine.commands import CommandError, command, dispatch

AI = ("subject", "sky", "background", "people", "object")


def _layers(pid: int) -> tuple[dict, list[dict]]:
    dev, _ = current(pid)
    dev = dev or {}
    return dev, [copy.deepcopy(x) for x in (dev.get("layers") or []) if isinstance(x, dict)]


def _find(layers: list[dict], layer: Any) -> int:
    for i, x in enumerate(layers):
        if str(x.get("id")) == str(layer) or x.get("name") == layer:
            return i
    try:
        i = int(layer)
    except (TypeError, ValueError):
        i = -1
    if 0 <= i < len(layers) and not any(str(x.get("id")) == str(layer) for x in layers):
        return i
    raise CommandError(f"No layer {layer}; this photo has {len(layers)}")


def _values(target: dict, values: dict | None) -> list[str]:
    skipped = []
    for cid, v in (values or {}).items():
        top, _, rest = str(cid).partition(".")
        if cid not in S.controls() or not layerable(top, rest):
            skipped.append(str(cid))
            continue
        S.put(target, cid, v)
    return skipped


def _mask(pid: int, dev: dict, mask: Any, invert: bool, edges: dict) -> dict:
    if mask in (None, "", "photo", "whole"):
        return {"components": [], "invert": bool(invert)}
    if isinstance(mask, str) and mask in AI:
        shape = dict(dispatch("develop.aiMask", {"id": pid, "kind": mask})["shape"])
        shape.update({k: v for k, v in edges.items() if v is not None})
        return {"components": [{"shape": shape, "op": "add"}], "invert": bool(invert), "source": mask}
    for m in dev.get("masks") or []:
        if str(m.get("id")) == str(mask) or m.get("name") == mask:
            return {"components": copy.deepcopy(m.get("components") or []), "invert": bool(invert) != bool(m.get("invert")), "source": f"mask:{m.get('id')}"}
    raise CommandError(f"mask is one of {', '.join(AI)}, photo, or the id or name of one of this photo's masks")


def _save(pid: int, layers: list[dict], label: str) -> None:
    dispatch("develop.update", {"ids": [pid], "patch": {"layers": layers}, "label": label})


@command("develop.addLayer", "Add Layer", {"id": {"type": "integer"}, "name": {"type": "string"}, "values": {"type": "object", "description": "develop control ids to absolute values, applied to the layer only"},
                                           "mask": {"type": "string", "description": "subject, sky, background, people, object, photo (whole photo), or a mask id or name to copy"},
                                           "invert": {"type": "boolean"}, "opacity": {"type": "number", "minimum": 0, "maximum": 100},
                                           "refine": {"type": "number"}, "shift": {"type": "number"}, "feather": {"type": "number"}},
         description="Adds an adjustment layer: a copy of the photo's colour and tone settings (everything but white balance, crop, geometry, lens corrections, noise reduction and profile) that you change on their own and blend in through a mask at an opacity. values sets the layer's sliders by control id.")
def add_layer(id: int, name: str = "", values: dict | None = None, mask: Any = None, invert: bool = False, opacity: float = 100.0,
              refine: float | None = None, shift: float | None = None, feather: float | None = None) -> dict:
    pid = int(id)
    dev, layers = _layers(pid)
    if len(layers) >= MAX_LAYERS:
        raise CommandError(f"A photo holds up to {MAX_LAYERS} layers")
    settings = {k: copy.deepcopy(v) for k, v in dev.items() if layerable(k)}
    if isinstance(settings.get("detail"), dict):
        settings["detail"] = {k: v for k, v in settings["detail"].items() if layerable("detail", k)}
    skipped = _values(settings, values)
    lid = max([int(x.get("id", 0) or 0) for x in layers] + [0]) + 1
    layer = {"id": lid, "name": name.strip() or f"Layer {lid}", "visible": True, "opacity": min(max(float(opacity), 0.0), 100.0), "settings": settings,
             "mask": _mask(pid, dev, mask, invert, {"refine": refine, "shift": shift, "feather": feather})}
    layers.append(layer)
    _save(pid, layers, f"Add Layer {layer['name']}")
    return {"id": pid, "layer": lid, "name": layer["name"], "layers": len(layers), **({"skipped": skipped} if skipped else {})}


@command("develop.setLayer", "Change Layer", {"id": {"type": "integer"}, "layer": {"type": "string"}, "values": {"type": "object"}, "opacity": {"type": "number", "minimum": 0, "maximum": 100},
                                              "visible": {"type": "boolean"}, "name": {"type": "string"}, "mask": {"type": "string"}, "invert": {"type": "boolean"}, "remove": {"type": "boolean"}},
         description="Changes one adjustment layer (by id, name or position): its slider values, opacity, visibility, name, mask (as in develop.addLayer) or inversion; remove deletes it.")
def set_layer(id: int, layer: Any, values: dict | None = None, opacity: float | None = None, visible: bool | None = None, name: str | None = None,
              mask: Any = None, invert: bool | None = None, remove: bool = False) -> dict:
    pid = int(id)
    dev, layers = _layers(pid)
    i = _find(layers, layer)
    if remove:
        gone = layers.pop(i)
        _save(pid, layers, f"Delete Layer {gone.get('name', '')}")
        return {"id": pid, "removed": gone.get("id"), "layers": len(layers)}
    x = layers[i]
    skipped = _values(x.setdefault("settings", {}), values)
    if opacity is not None:
        x["opacity"] = min(max(float(opacity), 0.0), 100.0)
    if visible is not None:
        x["visible"] = bool(visible)
    if name is not None and name.strip():
        x["name"] = name.strip()
    if mask is not None:
        x["mask"] = _mask(pid, dev, mask, bool(invert), {})
    elif invert is not None:
        x.setdefault("mask", {})["invert"] = bool(invert)
    _save(pid, layers, f"Layer {x.get('name', '')}")
    return {"id": pid, "layer": x.get("id"), "layers": len(layers), **({"skipped": skipped} if skipped else {})}
