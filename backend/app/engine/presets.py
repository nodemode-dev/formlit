import json
import re
from pathlib import Path
from typing import Any

from app.core import config
from app.develop import settings as S
from app.engine import catalog as catalog_mod
from app.engine.cmd_develop import after, current, store
from app.engine.commands import CommandError, command, resolve_ids

BUILTIN: list[dict] = [
    {"group": "Color", "name": "Clean Punch", "settings": {"light": {"contrast": 18, "highlights": -20, "shadows": 18, "whites": 8, "blacks": -6}, "effects": {"clarity": 8}, "color": {"vibrance": 18}}},
    {"group": "Color", "name": "Soft Bright", "settings": {"light": {"exposure": 0.25, "contrast": -12, "highlights": -30, "shadows": 30}, "color": {"vibrance": 8, "saturation": -4}}},
    {"group": "Color", "name": "Rich Shadows", "settings": {"light": {"shadows": -14, "blacks": -18, "contrast": 14}, "color": {"vibrance": 12}}},
    {"group": "Film", "name": "Golden Negative", "settings": {"profile": {"id": "fl.film.warm"}, "grain": {"amount": 18, "size": 30, "roughness": 55}}},
    {"group": "Film", "name": "Faded Print", "settings": {"profile": {"id": "fl.film.faded"}, "vignette": {"amount": -12, "midpoint": 40}}},
    {"group": "Film", "name": "Chrome Slide", "settings": {"profile": {"id": "fl.film.slide"}, "grain": {"amount": 10}}},
    {"group": "Cinematic", "name": "Teal Night", "settings": {"profile": {"id": "fl.cine.teal"}, "light": {"exposure": -0.2}, "vignette": {"amount": -18}}},
    {"group": "Cinematic", "name": "Warm Glow", "settings": {"profile": {"id": "fl.cine.golden"}, "effects": {"clarity": -10}, "light": {"highlights": -20}}},
    {"group": "B&W", "name": "Classic Grain", "settings": {"profile": {"id": "fl.monochrome"}, "grain": {"amount": 24, "size": 22, "roughness": 60}}},
    {"group": "B&W", "name": "Hard Light", "settings": {"profile": {"id": "fl.bw.punch"}, "vignette": {"amount": -20}}},
    {"group": "B&W", "name": "Sepia Tone", "settings": {"profile": {"id": "fl.bw.sepia"}}},
    {"group": "B&W", "name": "Selenium Tone", "settings": {"profile": {"id": "fl.bw.selenium"}}},
    {"group": "B&W", "name": "Infrared Dream", "settings": {"profile": {"id": "fl.bw.ir"}, "effects": {"clarity": -15}, "grain": {"amount": 12}}},
    {"group": "Portrait", "name": "Soft Skin", "settings": {"effects": {"texture": -18, "clarity": -6}, "mixer": {"orange": {"lum": 8, "sat": -6}}, "light": {"shadows": 10}}},
    {"group": "Portrait", "name": "Warm Portrait", "settings": {"profile": {"id": "fl.portrait"}, "grading": {"highlights": {"hue": 40, "sat": 12}}}},
    {"group": "Landscape", "name": "Crisp Landscape", "settings": {"profile": {"id": "fl.landscape"}, "effects": {"dehaze": 12, "clarity": 12}, "light": {"highlights": -35, "shadows": 25}}},
    {"group": "Landscape", "name": "Blue Hour", "settings": {"wb": {"mode": "custom", "temp": 4600, "tint": 6}, "grading": {"shadows": {"hue": 220, "sat": 16}}, "light": {"contrast": 10}}},
    {"group": "Landscape", "name": "Haze Cut", "settings": {"effects": {"dehaze": 30}, "light": {"blacks": -10}, "color": {"vibrance": 10}}},
    {"group": "Urban", "name": "Concrete", "settings": {"color": {"saturation": -30}, "effects": {"clarity": 22}, "light": {"contrast": 16}}},
    {"group": "Urban", "name": "Neon", "settings": {"color": {"vibrance": 30}, "mixer": {"blue": {"hue": 10, "sat": 20}, "magenta": {"sat": 20}}, "light": {"blacks": -14}}},
    {"group": "Style", "name": "Matte Fade", "settings": {"profile": {"id": "fl.film.matte"}}},
    {"group": "Style", "name": "Pastel Day", "settings": {"profile": {"id": "fl.muted.pastel"}, "light": {"exposure": 0.2}}},
    {"group": "Style", "name": "Earth Tones", "settings": {"profile": {"id": "fl.muted.earth"}}},
    {"group": "Style", "name": "Vintage Vignette", "settings": {"profile": {"id": "fl.film.faded"}, "vignette": {"amount": -35, "midpoint": 30, "feather": 70}, "grain": {"amount": 20}}},
]


def _adaptive(name: str, shapes: list[dict], adjust: dict) -> dict:
    return {"masks": [{"id": 1, "name": name, "visible": True, "components": [{"shape": s, "op": "add"} for s in shapes], "adjust": adjust}]}


SKY = {"kind": "sky", "bitmap": "adaptive-sky"}
SUBJECT = {"kind": "subject", "bitmap": "adaptive-subject"}
BACKGROUND = {"kind": "background", "bitmap": "adaptive-background"}
BUILTIN += [
    {"group": "Adaptive: Sky", "name": "Deep Blue Sky", "settings": _adaptive("Sky", [SKY], {"exposure": -0.35, "highlights": -30, "saturation": 18, "temp": -10})},
    {"group": "Adaptive: Sky", "name": "Dramatic Sky", "settings": _adaptive("Sky", [SKY], {"exposure": -0.5, "contrast": 22, "dehaze": 25, "clarity": 15})},
    {"group": "Adaptive: Sky", "name": "Golden Sky", "settings": _adaptive("Sky", [SKY], {"temp": 22, "tint": 8, "saturation": 12, "highlights": -20})},
    {"group": "Adaptive: Subject", "name": "Pop Subject", "settings": _adaptive("Subject", [SUBJECT], {"exposure": 0.25, "clarity": 12, "texture": 10, "saturation": 8})},
    {"group": "Adaptive: Subject", "name": "Darken Background", "settings": _adaptive("Background", [BACKGROUND], {"exposure": -0.6, "saturation": -15})},
    {"group": "Adaptive: Subject", "name": "Soft Background", "settings": _adaptive("Background", [BACKGROUND], {"clarity": -40, "texture": -50, "sharpness": -60})},
    {"group": "Adaptive: Portrait", "name": "Smooth Skin", "settings": _adaptive("Skin", [{"kind": "people", "part": "faceSkin", "label": "Face Skin", "bitmap": "adaptive-faceSkin"},
                                                                                     {"kind": "people", "part": "bodySkin", "label": "Body Skin", "bitmap": "adaptive-bodySkin"}], {"texture": -35, "clarity": -12})},
    {"group": "Adaptive: Portrait", "name": "Brighten Eyes", "settings": _adaptive("Eyes", [{"kind": "people", "part": "iris", "label": "Iris and Pupil", "bitmap": "adaptive-iris"},
                                                                                       {"kind": "people", "part": "sclera", "label": "Eye Sclera", "bitmap": "adaptive-sclera"}], {"exposure": 0.3, "clarity": 10, "saturation": 6})},
    {"group": "Adaptive: Portrait", "name": "Whiten Teeth", "settings": _adaptive("Teeth", [{"kind": "people", "part": "teeth", "label": "Teeth", "bitmap": "adaptive-teeth"}], {"exposure": 0.2, "saturation": -40})},
]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def user_dir() -> Path:
    d = config.presets_dir() / "Develop"
    d.mkdir(parents=True, exist_ok=True)
    return d


def all_presets() -> list[dict]:
    out = [{"id": f"builtin:{_slug(p['group'])}/{_slug(p['name'])}", "group": p["group"], "name": p["name"], "builtin": True, "settings": p["settings"]} for p in BUILTIN]
    favs = set(catalog_mod.get().get_meta("favoritePresets", []) or [])
    for f in sorted(user_dir().rglob("*.flpreset")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rel = f.relative_to(user_dir())
        out.append({"id": f"user:{rel.as_posix()}", "group": data.get("group") or (rel.parent.as_posix() if rel.parent != Path(".") else "User Presets"),
                    "name": data.get("name", f.stem), "builtin": False, "settings": data.get("settings", {}), "groups": data.get("groups")})
    for p in out:
        p["favorite"] = p["id"] in favs
    return out


def settings_of(pid: str) -> dict:
    for p in all_presets():
        if p["id"] == pid or p["name"].lower() == pid.lower():
            return p["settings"]
    raise CommandError(f"No preset {pid}")


@command("preset.list", "Presets", mutates=False)
def list_presets() -> dict:
    return {"presets": [{k: v for k, v in p.items() if k != "settings"} for p in all_presets()]}


@command("preset.get", "Preset Settings", {"id": {"type": "string"}}, mutates=False)
def get_preset(id: str) -> dict:
    return {"id": id, "settings": settings_of(id)}


@command("preset.apply", "Apply Preset", {"ids": {"type": "array"}, "preset": {"type": "string"}, "amount": {"type": "number"}})
def apply(preset: str, ids: Any = None, amount: float = 100.0) -> dict:
    pids = resolve_ids(ids)
    src = settings_of(preset)
    name = next((p["name"] for p in all_presets() if p["id"] == preset or p["name"].lower() == preset.lower()), preset)
    groups = sorted({g for g, keys in S.GROUPS.items() for k in src if k in keys}) or None
    with catalog_mod.get().change(f"Preset: {name}") as ch:
        for pid in pids:
            dev, _ = current(pid)
            new = S.apply_groups(dev, src, groups, amount / 100.0)
            if src.get("masks"):
                new["masks"] = merge_masks(dev.get("masks") or [], src["masks"], amount / 100.0)
            store(ch, pid, new, f"Preset: {name}")
    after(pids)
    return {"ids": pids, "preset": name}


def merge_masks(old: list, add: list, amount: float = 1.0) -> list:
    import copy as copy_mod
    out = copy_mod.deepcopy(old)
    keys = {c.get("shape", {}).get("bitmap") for m in out for c in m.get("components") or []}
    nid = max([int(m.get("id", 0)) for m in out] + [0])
    for m in add:
        own = {c.get("shape", {}).get("bitmap") for c in m.get("components") or []}
        if own and own <= keys and any(x.get("name") == m.get("name") for x in out):
            continue
        nid += 1
        m2 = copy_mod.deepcopy(m)
        m2["id"] = nid
        m2["adjust"] = {k: (v * amount if k != "amount" and isinstance(v, (int, float)) else v) for k, v in (m2.get("adjust") or {}).items()}
        out.append(m2)
    return out


@command("preset.create", "New Develop Preset", {"name": {"type": "string"}, "group": {"type": "string"}, "id": {"type": "integer"}, "groups": {"type": "array"}})
def create(name: str, group: str = "User Presets", id: int | None = None, groups: list[str] | None = None, settings: dict | None = None) -> dict:
    if settings is None:
        pid = int(id) if id is not None else resolve_ids("active")[0]
        dev, _ = current(pid)
        settings = S.pick_groups(dev, groups or [g for g in S.GROUPS if g not in ("crop", "masks", "spots", "redEye")])
    folder = user_dir() / _slug(group or "User Presets")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{_slug(name) or 'preset'}.flpreset"
    path.write_text(json.dumps({"name": name, "group": group, "groups": groups, "settings": settings}, indent=1), encoding="utf-8")
    return {"id": f"user:{path.relative_to(user_dir()).as_posix()}"}


@command("preset.delete", "Delete Preset", {"id": {"type": "string"}})
def delete(id: str) -> dict:
    if not id.startswith("user:"):
        raise CommandError("Built-in presets cannot be deleted")
    p = user_dir() / id[5:]
    if p.is_file():
        p.unlink()
    return {"id": id}


@command("preset.update", "Update Preset with Current Settings", {"id": {"type": "string"}, "photo": {"type": "integer"}})
def update(id: str, photo: int | None = None, name: str | None = None) -> dict:
    if not id.startswith("user:"):
        raise CommandError("Built-in presets cannot be changed")
    p = user_dir() / id[5:]
    data = json.loads(p.read_text(encoding="utf-8"))
    if photo is not None or name is None:
        dev, _ = current(int(photo) if photo is not None else resolve_ids("active")[0])
        data["settings"] = S.pick_groups(dev, data.get("groups") or [g for g in S.GROUPS if g not in ("crop", "masks", "spots", "redEye")])
    if name:
        data["name"] = name
    p.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return {"id": id}


@command("preset.favorite", "Favorite Preset", {"id": {"type": "string"}, "on": {"type": "boolean"}})
def favorite(id: str, on: bool = True) -> dict:
    c = catalog_mod.get()
    favs = set(c.get_meta("favoritePresets", []) or [])
    favs = favs | {id} if on else favs - {id}
    with c.change("Favorite Preset", undoable=False) as ch:
        ch.set_meta("favoritePresets", sorted(favs))
    return {"id": id, "favorite": on}


@command("preset.export", "Export Preset", {"id": {"type": "string"}, "folder": {"type": "string"}}, mutates=False)
def export_preset(id: str, folder: str = "") -> dict:
    import uuid
    from app.services import metadata as M
    from app.services import rename, xmp_presets
    p = next((x for x in all_presets() if x["id"] == id), None)
    if p is None:
        raise CommandError(f"No preset {id}")
    dest = Path(folder).expanduser() if folder else config.exports_dir() / "Presets"
    dest.mkdir(parents=True, exist_ok=True)
    attrs = " ".join(f'crs:{k}="{M._esc(v)}"' for k, v in xmp_presets.to_crs(p["settings"]).items())
    alt = lambda tag, v: f'<crs:{tag}><rdf:Alt><rdf:li xml:lang="x-default">{M._esc(v)}</rdf:li></rdf:Alt></crs:{tag}>'
    text = ('<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="formlit">\n <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
            f'  <rdf:Description rdf:about="" xmlns:crs="{M.NS["crs"]}" xmlns:fl="{M.NS["fl"]}" crs:PresetType="Normal" crs:Cluster="" '
            f'crs:UUID="{uuid.uuid4().hex.upper()}" crs:SupportsAmount="True" crs:SupportsColor="True" crs:SupportsMonochrome="True" '
            f'{attrs} fl:develop="{M._esc(json.dumps(p["settings"], separators=(",", ":")))}">\n'
            f'   {alt("Name", p["name"])}\n   {alt("Group", p["group"])}\n  </rdf:Description>\n </rdf:RDF>\n</x:xmpmeta>\n')
    path = rename.unique(dest / f"{_slug(p['name']) or 'preset'}.xmp")
    path.write_text(text, encoding="utf-8")
    return {"path": str(path), "name": p["name"]}


@command("preset.import", "Import Presets", {"paths": {"type": "array"}})
def import_presets(paths: list[str]) -> dict:
    from app.services import xmp_presets
    made = []
    for raw in paths:
        p = Path(raw).expanduser()
        files = [p] if p.is_file() else sorted(p.rglob("*")) if p.is_dir() else []
        for f in files:
            if f.suffix.lower() == ".flpreset":
                dst = user_dir() / "Imported" / f.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(f.read_bytes())
                made.append(dst.stem)
            elif f.suffix.lower() in (".xmp", ".lrtemplate"):
                conv = xmp_presets.convert(f)
                if conv:
                    create(conv["name"], conv.get("group") or "Imported", settings=conv["settings"])
                    made.append(conv["name"])
            elif f.suffix.lower() == ".cube":
                from app.develop.profiles import import_cube
                made.append(import_cube(f))
            elif f.suffix.lower() == ".dcp":
                from app.develop import dcp
                from app.develop.profiles import load_cube
                try:
                    dst, _ = dcp.to_cube(f, config.profiles_dir())
                except ValueError as exc:
                    raise CommandError(f"{f.name}: {exc}") from exc
                load_cube.cache_clear()
                made.append(f"lut:{dst.stem}")
    return {"imported": made}
