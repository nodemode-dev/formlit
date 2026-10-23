import json
import re
from pathlib import Path
from typing import Any

from app.core import config
from app.develop import settings as S
from app.engine import catalog as catalog_mod
from app.engine.cmd_develop import after, current, store
from app.engine.commands import CommandError, command, resolve_ids
from app.engine.preset_library import LIBRARY, MATTE, NOTES
from app.engine.preset_library_1 import LIBRARY_1
from app.engine.preset_library_2 import LIBRARY_2
from app.engine.preset_library_3 import LIBRARY_3

BUILTIN: list[dict] = [
    {"group": "Color", "name": "Clean Punch", "settings": {"light": {"contrast": 18, "highlights": -20, "shadows": 18, "whites": 8, "blacks": -6}, "effects": {"clarity": 8}, "color": {"vibrance": 18}}},
    {"group": "Color", "name": "Soft Bright", "settings": {"light": {"exposure": 0.25, "contrast": -12, "highlights": -30, "shadows": 30}, "color": {"vibrance": 8, "saturation": -4}}},
    {"group": "Color", "name": "Rich Shadows", "settings": {"light": {"shadows": -14, "blacks": -18, "contrast": 14}, "color": {"vibrance": 12}}},
    {"group": "Film", "name": "Golden Negative", "settings": {"profile": {"id": "fl.creative.warmfade"}, "grading": {"highlights": {"hue": 45, "sat": 12}, "shadows": {"hue": 210, "sat": 8}},
                                                                "grain": {"amount": 18, "size": 30, "roughness": 55}}},
    {"group": "Film", "name": "Faded Print", "settings": {"curve": {"master": MATTE}, "color": {"saturation": -8}, "grading": {"shadows": {"hue": 40, "sat": 20}, "blending": 75},
                                                            "vignette": {"amount": -12, "midpoint": 40}}},
    {"group": "Film", "name": "Chrome Slide", "settings": {"profile": {"id": "fl.vivid"}, "light": {"contrast": 15, "blacks": -10}, "mixer": {"blue": {"sat": 10}}, "grain": {"amount": 10}}},
    {"group": "Cinematic", "name": "Teal Night", "settings": {"profile": {"id": "fl.creative.tealorange"}, "grading": {"shadows": {"hue": 210, "sat": 18}}, "light": {"exposure": -0.2},
                                                               "vignette": {"amount": -18}}},
    {"group": "Cinematic", "name": "Warm Glow", "settings": {"profile": {"id": "fl.creative.golden"}, "effects": {"clarity": -10}, "light": {"highlights": -20}}},
    {"group": "B&W", "name": "Classic Grain", "settings": {"profile": {"id": "fl.monochrome"}, "grain": {"amount": 24, "size": 22, "roughness": 60}}},
    {"group": "B&W", "name": "Hard Light", "settings": {"profile": {"id": "fl.bw.punch"}, "vignette": {"amount": -20}}},
    {"group": "B&W", "name": "Sepia Tone", "settings": {"treatment": "bw", "grading": {"shadows": {"hue": 30, "sat": 20}, "highlights": {"hue": 45, "sat": 15}, "blending": 60}}},
    {"group": "B&W", "name": "Selenium Tone", "settings": {"treatment": "bw", "light": {"contrast": 10}, "grading": {"shadows": {"hue": 265, "sat": 14}, "highlights": {"hue": 35, "sat": 4}}}},
    {"group": "B&W", "name": "Infrared Dream", "settings": {"treatment": "bw", "bw": {"green": 60, "yellow": 40, "blue": -50, "aqua": -30}, "light": {"highlights": -20},
                                                              "effects": {"clarity": -15}, "grain": {"amount": 12}}},
    {"group": "Portrait", "name": "Soft Skin", "settings": {"effects": {"texture": -18, "clarity": -6}, "mixer": {"orange": {"lum": 8, "sat": -6}}, "light": {"shadows": 10}}},
    {"group": "Portrait", "name": "Warm Portrait", "settings": {"profile": {"id": "fl.portrait"}, "grading": {"highlights": {"hue": 40, "sat": 12}}}},
    {"group": "Landscape", "name": "Crisp Landscape", "settings": {"profile": {"id": "fl.landscape"}, "effects": {"dehaze": 12, "clarity": 12}, "light": {"highlights": -35, "shadows": 25}}},
    {"group": "Landscape", "name": "Blue Hour", "settings": {"wb": {"mode": "custom", "temp": 4600, "tint": 6}, "grading": {"shadows": {"hue": 220, "sat": 16}}, "light": {"contrast": 10}}},
    {"group": "Landscape", "name": "Haze Cut", "settings": {"effects": {"dehaze": 30}, "light": {"blacks": -10}, "color": {"vibrance": 10}}},
    {"group": "Urban", "name": "Concrete", "settings": {"color": {"saturation": -30}, "effects": {"clarity": 22}, "light": {"contrast": 16}}},
    {"group": "Urban", "name": "Neon", "settings": {"color": {"vibrance": 30}, "mixer": {"blue": {"hue": 10, "sat": 20}, "magenta": {"sat": 20}}, "light": {"blacks": -14}}},
    {"group": "Style", "name": "Matte Fade", "settings": {"curve": {"master": MATTE}, "light": {"contrast": -16, "highlights": -20, "shadows": 12, "whites": 6},
                                                           "effects": {"dehaze": -6}, "color": {"saturation": -10, "vibrance": -4}}},
    {"group": "Style", "name": "Pastel Day", "settings": {"light": {"exposure": 0.2, "contrast": -15}, "curve": {"shadows": 15}, "color": {"saturation": -12, "vibrance": 6},
                                                           "grading": {"shadows": {"hue": 270, "sat": 10}, "highlights": {"hue": 25, "sat": 8}}}},
    {"group": "Style", "name": "Earth Tones", "settings": {"color": {"saturation": -15}, "mixer": {"blue": {"sat": -30}, "green": {"hue": -20, "sat": -20}, "orange": {"sat": 5}},
                                                            "grading": {"highlights": {"hue": 40, "sat": 10}}}},
    {"group": "Style", "name": "Vintage Vignette", "settings": {"curve": {"master": MATTE}, "color": {"saturation": -10}, "vignette": {"amount": -35, "midpoint": 30, "feather": 70},
                                                                 "grain": {"amount": 20}}},
]


def _adaptive(name: str, shapes: list[dict], adjust: dict) -> dict:
    return {"masks": [{"id": 1, "name": name, "visible": True, "components": [{"shape": s, "op": "add"} for s in shapes], "adjust": adjust}]}


SKY = {"kind": "sky", "bitmap": "adaptive-sky"}
SUBJECT = {"kind": "subject", "bitmap": "adaptive-subject"}
BACKGROUND = {"kind": "background", "bitmap": "adaptive-background"}
BUILTIN += [
    {"group": "Adaptable: Sky", "name": "Deep Blue Sky", "settings": _adaptive("Sky", [SKY], {"exposure": -0.35, "highlights": -30, "saturation": 18, "temp": -10})},
    {"group": "Adaptable: Sky", "name": "Dramatic Sky", "settings": _adaptive("Sky", [SKY], {"exposure": -0.5, "contrast": 22, "dehaze": 25, "clarity": 15})},
    {"group": "Adaptable: Sky", "name": "Golden Sky", "settings": _adaptive("Sky", [SKY], {"temp": 22, "tint": 8, "saturation": 12, "highlights": -20})},
    {"group": "Adaptable: Subject", "name": "Pop Subject", "settings": _adaptive("Subject", [SUBJECT], {"exposure": 0.25, "clarity": 12, "texture": 10, "saturation": 8})},
    {"group": "Adaptable: Subject", "name": "Darken Background", "settings": _adaptive("Background", [BACKGROUND], {"exposure": -0.6, "saturation": -15})},
    {"group": "Adaptable: Subject", "name": "Soft Background", "settings": _adaptive("Background", [BACKGROUND], {"clarity": -40, "texture": -50, "sharpness": -60})},
    {"group": "Adaptable: Portrait", "name": "Smooth Skin", "settings": _adaptive("Skin", [{"kind": "people", "part": "faceSkin", "label": "Face Skin", "bitmap": "adaptive-faceSkin"},
                                                                                     {"kind": "people", "part": "bodySkin", "label": "Body Skin", "bitmap": "adaptive-bodySkin"}], {"texture": -35, "clarity": -12})},
    {"group": "Adaptable: Portrait", "name": "Brighten Eyes", "settings": _adaptive("Eyes", [{"kind": "people", "part": "iris", "label": "Iris and Pupil", "bitmap": "adaptive-iris"},
                                                                                       {"kind": "people", "part": "sclera", "label": "Eye Sclera", "bitmap": "adaptive-sclera"}], {"exposure": 0.3, "clarity": 10, "saturation": 6})},
    {"group": "Adaptable: Portrait", "name": "Whiten Teeth", "settings": _adaptive("Teeth", [{"kind": "people", "part": "teeth", "label": "Teeth", "bitmap": "adaptive-teeth"}], {"exposure": 0.2, "saturation": -40})},
]
BUILTIN += LIBRARY
BUILTIN += LIBRARY_1 + LIBRARY_2 + LIBRARY_3


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


LEGACY_SLUGS = {"sharpen-balanced-start": "sharpen-adobe-sample-balanced"}


def _id_part(s: str) -> str:
    v = _slug(s)
    if v.startswith("adaptable-"):
        v = "adaptive-" + v[len("adaptable-"):]
    return LEGACY_SLUGS.get(v, v)


def builtin_id(p: dict) -> str:
    return f"builtin:{_id_part(p['group'])}/{_id_part(p['name'])}"


def user_dir() -> Path:
    d = config.presets_dir() / "Develop"
    d.mkdir(parents=True, exist_ok=True)
    return d


def all_presets() -> list[dict]:
    out = [{"id": builtin_id(p), "group": p["group"], "name": p["name"], "builtin": True, "settings": p["settings"],
            "description": p.get("description") or NOTES.get(p["name"], ""), "tags": p.get("tags") or []} for p in BUILTIN]
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


@command("preset.list", "Presets", {"query": {"type": "string", "description": "words matched against name, group, description and tags"},
                                    "group": {"type": "string"}}, mutates=False,
         description="Develop presets with their group, a description of what each does and what it suits, and tags; query and group narrow the list.")
def list_presets(query: str | None = None, group: str | None = None) -> dict:
    items = [{k: v for k, v in p.items() if k != "settings"} for p in all_presets()]
    if group:
        items = [p for p in items if p["group"].lower() == group.lower()]
    if query:
        words = [w for w in re.split(r"\W+", query.lower()) if w]
        def hay(p: dict) -> str:
            return " ".join([p["name"], p["group"], p.get("description", ""), " ".join(p.get("tags") or [])]).lower()
        items = [p for p in items if all(w in hay(p) for w in words)] or [p for p in items if any(w in hay(p) for w in words)]
    return {"presets": items, "count": len(items), "groups": sorted({p["group"] for p in items})}


def blended(dev: dict, preset: str, amount: float = 100.0) -> dict:
    src = settings_of(preset)
    groups = sorted({g for g, keys in S.GROUPS.items() for k in src if k in keys}) or None
    new = S.apply_groups(dev, src, groups, amount / 100.0)
    if src.get("masks"):
        new["masks"] = merge_masks(dev.get("masks") or [], src["masks"], amount / 100.0)
    return new


@command("preset.get", "Preset Settings", {"id": {"type": "string"}}, mutates=False)
def get_preset(id: str) -> dict:
    return {"id": id, "settings": settings_of(id)}


@command("preset.apply", "Apply Preset", {"ids": {"type": "array"}, "preset": {"type": "string"}, "amount": {"type": "number"}})
def apply(preset: str, ids: Any = None, amount: float = 100.0) -> dict:
    pids = resolve_ids(ids)
    settings_of(preset)
    name = next((p["name"] for p in all_presets() if p["id"] == preset or p["name"].lower() == preset.lower()), preset)
    with catalog_mod.get().change(f"Preset: {name}") as ch:
        for pid in pids:
            dev, _ = current(pid)
            store(ch, pid, blended(dev, preset, amount), f"Preset: {name}")
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


def user_file(id: str) -> Path:
    root = user_dir().resolve()
    p = (root / str(id)[5:]).resolve()
    if p.suffix != ".flpreset" or not p.is_relative_to(root) or not p.is_file():
        raise CommandError(f"No user preset {id}", 404)
    return p


@command("preset.delete", "Delete Preset", {"id": {"type": "string"}})
def delete(id: str) -> dict:
    if not str(id).startswith("user:"):
        raise CommandError("Built-in presets cannot be deleted")
    user_file(id).unlink()
    return {"id": id}


@command("preset.update", "Update Preset with Current Settings", {"id": {"type": "string"}, "photo": {"type": "integer"}})
def update(id: str, photo: int | None = None, name: str | None = None) -> dict:
    if not str(id).startswith("user:"):
        raise CommandError("Built-in presets cannot be changed")
    p = user_file(id)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise CommandError(f"{p.name} is not a readable preset") from exc
    if not isinstance(data, dict):
        raise CommandError(f"{p.name} is not a readable preset")
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
            f'   {alt("Name", p["name"])}\n   {alt("Group", p["group"])}\n   {"".join(xmp_presets.crs_children(p["settings"]))}\n  </rdf:Description>\n </rdf:RDF>\n</x:xmpmeta>\n')
    path = rename.unique(dest / f"{_slug(p['name']) or 'preset'}.xmp")
    path.write_text(text, encoding="utf-8")
    return {"path": str(path), "name": p["name"]}


@command("preset.exportGroup", "Export Preset Group", {"group": {"type": "string"}, "folder": {"type": "string"}}, mutates=False,
         description="Writes every preset of a group as Lightroom-compatible XMP files into one zip, to share or to import in formlit or Lightroom.")
def export_group(group: str, folder: str = "") -> dict:
    import tempfile
    import zipfile
    from app.services import rename
    members = [p for p in all_presets() if p["group"] == group]
    if not members:
        raise CommandError(f"No presets in group {group}")
    tmp = Path(tempfile.mkdtemp(prefix="formlit-group-"))
    dest = Path(folder).expanduser() if folder else config.exports_dir() / "Presets"
    dest.mkdir(parents=True, exist_ok=True)
    path = rename.unique(dest / f"{_slug(group) or 'presets'}.zip")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in members:
            got = export_preset(p["id"], str(tmp))
            z.write(got["path"], f"{group}/{Path(got['path']).name}")
    return {"path": str(path), "group": group, "presets": len(members)}


PACK_TYPES = (".xmp", ".lrtemplate", ".flpreset", ".cube", ".dcp")


def _unzip(path: Path) -> list[Path]:
    import tempfile
    import zipfile
    out_dir = Path(tempfile.mkdtemp(prefix="formlit-presets-"))
    found = []
    with zipfile.ZipFile(path) as z:
        for i, info in enumerate(z.infolist()):
            name = Path(info.filename)
            if info.is_dir() or name.suffix.lower() not in PACK_TYPES or "__MACOSX" in name.parts or name.name.startswith("."):
                continue
            if info.file_size > 20_000_000:
                continue
            dst = out_dir / f"{i:04d}-{re.sub(r'[^A-Za-z0-9._ -]+', '_', name.name)}"
            dst.write_bytes(z.read(info))
            found.append(dst)
    return found


@command("preset.import", "Import Presets", {"paths": {"type": "array"}})
def import_presets(paths: list[str]) -> dict:
    from app.develop import adobe_profile
    from app.services import xmp_presets
    made = []
    for raw in paths:
        p = Path(raw).expanduser()
        files = [p] if p.is_file() else sorted(p.rglob("*")) if p.is_dir() else []
        files = [x for f in files for x in (_unzip(f) if f.suffix.lower() == ".zip" else [f])]
        for f in files:
            if f.suffix.lower() == ".flpreset":
                dst = user_dir() / "Imported" / f.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(f.read_bytes())
                made.append(dst.stem)
            elif f.suffix.lower() == ".xmp" and adobe_profile.is_profile(f):
                from app.develop.profiles import import_profile_xmp
                try:
                    made.append(import_profile_xmp(f))
                except ValueError as exc:
                    raise CommandError(f"{f.name}: {exc}") from exc
            elif f.suffix.lower() in (".xmp", ".lrtemplate"):
                conv = xmp_presets.convert(f)
                if conv:
                    create(conv["name"], conv.get("group") or "Imported", settings=conv["settings"])
                    made.append(conv["name"])
            elif f.suffix.lower() == ".cube":
                from app.develop.profiles import import_cube
                made.append(import_cube(f))
            elif f.suffix.lower() == ".dcp":
                from app.develop.profiles import import_dcp
                try:
                    made.append(import_dcp(f))
                except ValueError as exc:
                    raise CommandError(f"{f.name}: {exc}") from exc
    return {"imported": made}
