import re
from datetime import date
from typing import Any

from app.core import prefs
from app.engine import catalog as catalog_mod
from app.engine import query
from app.engine.commands import CommandError, command, dispatch, resolve_ids
from app.engine.template_library import FILENAME, FOLDER, KEYWORDS, METADATA, SHOOTS, SMART, STAGES

KINDS = {"filename": FILENAME, "folder": FOLDER, "metadata": METADATA, "keywordSet": KEYWORDS, "smartCollection": SMART, "shoot": SHOOTS}
IDENTITY = ("creator", "email", "url")
_HOLE = re.compile(r"\{([a-z]+)\}")


def find(kind: str, ref: str) -> dict:
    items = KINDS.get(kind)
    if items is None:
        raise CommandError(f"kind is one of {', '.join(KINDS)}")
    key = str(ref or "").strip().lower()
    for t in items:
        if t["id"] == key or t["name"].lower() == key:
            return t
    raise CommandError(f"No {kind} template {ref}; template.list with kind {kind} lists them")


def identity(values: dict | None = None) -> dict:
    out = {k: v for k, v in (prefs.load().get("identity") or {}).items() if v}
    out.update({k: str(v).strip() for k, v in (values or {}).items() if str(v or "").strip()})
    out.setdefault("year", str(date.today().year))
    return out


def fill(fields: dict, values: dict) -> tuple[dict, list[str]]:
    out, skipped = {}, []
    for k, v in fields.items():
        if not isinstance(v, str) or not v:
            out[k] = v
            continue
        missing = [h for h in _HOLE.findall(v) if not values.get(h)]
        if missing:
            skipped.append(f"{k} (needs {', '.join(missing)})")
            continue
        out[k] = _HOLE.sub(lambda m: str(values[m.group(1)]), v)
    return out, skipped


def keep_identity(values: dict | None) -> None:
    keep = {k: str(values[k]).strip() for k in IDENTITY if values and str(values.get(k) or "").strip()}
    if keep:
        prefs.update({"identity": {**(prefs.load().get("identity") or {}), **keep}})


def _brief(t: dict) -> dict:
    return {k: t[k] for k in ("id", "name", "description", "tags") if k in t} | {"value": t["value"]}


@command("template.list", "Templates", {"kind": {"type": "string", "enum": list(KINDS) + ["export"]}, "query": {"type": "string"}}, mutates=False,
         description="Built-in templates: filename (rename patterns), folder (import folder patterns), metadata (copyright and licence presets with {creator} {year} {email} {url} {client} {event} {job} placeholders), keywordSet, smartCollection (rules), shoot (whole-job recipes) and export presets. query matches name, description and tags.")
def template_list(kind: str | None = None, query: str | None = None) -> dict:
    from app.output import export
    out: dict[str, list] = {k: [_brief(t) for t in v] for k, v in KINDS.items() if not kind or kind == k}
    if not kind or kind == "export":
        out["export"] = [{"id": p["id"], "name": p["name"], "group": p.get("group", "User"), "description": p.get("description", "")} for p in export.list_presets()]
    if query:
        words = [w for w in re.split(r"\W+", query.lower()) if w]
        def hay(t: dict) -> str:
            return " ".join([t["name"], t.get("description", ""), t.get("group", ""), " ".join(t.get("tags") or [])]).lower()
        out = {k: [t for t in v if all(w in hay(t) for w in words)] or [t for t in v if any(w in hay(t) for w in words)] for k, v in out.items()}
    return {"templates": out, "identity": {k: v for k, v in identity().items() if k in IDENTITY}, "count": sum(len(v) for v in out.values())}


@command("template.applyMetadata", "Apply Metadata Template", {"ids": {"type": "array"}, "template": {"type": "string"}, "values": {"type": "object"}, "remember": {"type": "boolean"}},
         description="Writes a metadata template's IPTC fields to photos in one undo step. values fills placeholders (creator, email, url, client, event, job); creator, email and url are remembered for next time unless remember is false. Fields whose placeholder has no value are skipped and reported.")
def apply_metadata(template: str, ids: Any = None, values: dict | None = None, remember: bool = True) -> dict:
    pids = resolve_ids(ids)
    t = find("metadata", template)
    if remember:
        keep_identity(values)
    fields, skipped = fill(t["value"], identity(values))
    core = [s for s in skipped if s.split(" ")[0] in ("creator", "copyright", "rightsUsage")]
    if core or not fields:
        raise CommandError(f"{t['name']} needs values for {', '.join(core or skipped)}; pass values, for example {{\"creator\": \"Name\"}}")
    dispatch("photo.setMeta", {"ids": pids, "fields": fields})
    return {"ids": pids, "template": t["name"], "fields": fields, "skipped": skipped}


@command("template.applyKeywords", "Apply Keyword Set", {"ids": {"type": "array"}, "set": {"type": "string"}, "keywords": {"type": "array", "description": "a subset of the set's keywords; all of them when left out"}},
         description="Adds keywords from a keyword set (or the chosen subset of it) to photos in one undo step.")
def apply_keywords(set: str, ids: Any = None, keywords: list[str] | None = None) -> dict:
    pids = resolve_ids(ids)
    t = find("keywordSet", set)
    pick = [k for k in t["value"] if not keywords or k.lower() in {str(x).lower() for x in keywords}]
    if not pick:
        raise CommandError(f"None of those are in {t['name']}: {', '.join(t['value'])}")
    dispatch("photo.addKeywords", {"ids": pids, "keywords": pick})
    return {"ids": pids, "set": t["name"], "keywords": pick}


@command("template.rename", "Rename with Template", {"ids": {"type": "array"}, "template": {"type": "string", "description": "a filename template id or name, or a pattern with tokens"},
                                                     "custom": {"type": "string"}, "start": {"type": "integer"}, "preview": {"type": "boolean"}},
         description="Renames photo files on disk with a filename template (or a raw pattern); preview true returns the new names without renaming.")
def rename_with(template: str, ids: Any = None, custom: str = "", start: int = 1, preview: bool = False) -> dict:
    pattern = template if "{" in template else find("filename", template)["value"]
    if "{custom}" in pattern and not custom.strip():
        raise CommandError("This template uses {custom}; pass custom (the shoot, client, listing or SKU)")
    return dispatch("photo.rename", {"ids": resolve_ids(ids), "template": pattern, "custom": custom, "start": start, "preview": preview})


def _insert_collection(c, ch, name: str, kind: str, parent: int | None, rules: dict | None = None) -> int:
    pos = int(c.db.execute("SELECT COALESCE(MAX(position), 0) FROM collections").fetchone()[0]) + 1
    return int(ch.insert("collections", name=name, kind=kind, parent_id=parent, rules=rules, position=pos, settings=None, service_id=None))


def _scoped(rules: dict, within: int | None) -> dict:
    if within is None:
        return rules
    return {"match": "all", "rules": [{"field": "collection", "op": "=", "value": int(within)}], "groups": [rules]}


@command("template.smartCollection", "New Intelligent Collection from Template", {"template": {"type": "string"}, "name": {"type": "string"}, "parent": {"type": "integer"},
                                                                             "within": {"type": "integer", "description": "limit it to photos in this collection id"}},
         description="Creates an intelligent collection from a template's rules, optionally inside a collection set (parent) and limited to one collection's photos (within).")
def smart_from(template: str, name: str = "", parent: int | None = None, within: int | None = None) -> dict:
    t = find("smartCollection", template)
    c = catalog_mod.get()
    for ref in (parent, within):
        if ref is not None and c.row("SELECT 1 FROM collections WHERE id=?", (int(ref),)) is None:
            raise CommandError(f"No collection {ref}", 404)
    rules = _scoped(t["value"], within)
    query.validate_rules(rules)
    with c.change("New Intelligent Collection") as ch:
        cid = _insert_collection(c, ch, name.strip() or t["name"], "smart", parent, rules)
    return {"id": cid, "name": name.strip() or t["name"], "rules": rules}


@command("workflow.setupShoot", "New Shoot from Template", {"recipe": {"type": "string"}, "name": {"type": "string"}, "values": {"type": "object"},
                                                             "paths": {"type": "array", "description": "card or folder paths to import into the shoot now"},
                                                             "mode": {"type": "string", "enum": ["add", "copy", "move", "dng"]}, "destination": {"type": "string"}, "backup": {"type": "string"}},
         description="Sets up a whole job the way working photographers do: a collection set named for the shoot holding All Photos and intelligent collections for each stage (Picks, To Edit, Edited, Portfolio, Rejects) limited to the shoot, all in one undo step. With paths it also imports with the recipe's folder and file naming, metadata template, keyword set and previews, puts the photos in All Photos and applies noise reduction by ISO when the recipe calls for it. Returns the ids, the import settings and the recipe's export presets and workflow prompt.")
def setup_shoot(recipe: str, name: str, values: dict | None = None, paths: list[str] | None = None, mode: str = "copy", destination: str = "", backup: str = "",
                skipDuplicates: bool = True) -> dict:
    r = find("shoot", recipe)
    v = r["value"]
    name = str(name or "").strip()
    if not name:
        raise CommandError("A shoot needs a name, for example the client or event")
    keep_identity(values)
    vals = identity({"client": name, "event": name, "job": name, **(values or {})})
    meta, skipped = fill(find("metadata", v["metadata"])["value"], vals)
    keywords = find("keywordSet", v["keywords"])["value"]
    folder = find("folder", v["folder"])["value"]
    rename = find("filename", v["rename"])["value"]
    c = catalog_mod.get()
    with c.change(f"New Shoot: {name}") as ch:
        set_id = _insert_collection(c, ch, name, "set", None)
        all_id = _insert_collection(c, ch, "All Photos", "collection", set_id)
        stages = {label: _insert_collection(c, ch, label, "smart", set_id, _scoped({"match": "all", "rules": rules}, all_id)) for label, rules in STAGES}
    settings = {"mode": mode, "destination": destination, "folderTemplate": folder, "renameTemplate": rename, "custom": name, "metadata": meta, "keywords": keywords,
                "collection": all_id, "buildPreviews": v["previews"], "smartPreviews": v["smartPreviews"], "backup": backup, "skipDuplicates": skipDuplicates}
    if v["develop"]:
        settings["develop"] = v["develop"]
    out = {"recipe": r["name"], "set": set_id, "allPhotos": all_id, "stages": stages, "import": settings, "metadataSkipped": skipped,
           "exports": v["exports"], "workflow": v["workflow"], "isoNoise": v["isoNoise"]}
    if paths:
        if mode in ("copy", "move", "dng") and not destination:
            raise CommandError("Copy, move and DNG imports need a destination folder")
        res = dispatch("library.import", {"paths": paths, "wait": True, **settings})
        ids = [int(i) for i in res.get("ids", [])]
        out["imported"] = len(ids)
        out["ids"] = ids
        out["skippedFiles"] = res.get("skipped") or []
        out["failedFiles"] = res.get("failed") or []
        if v["isoNoise"] and ids:
            out["noise"] = dispatch("develop.noiseByIso", {"ids": ids})
    return out
