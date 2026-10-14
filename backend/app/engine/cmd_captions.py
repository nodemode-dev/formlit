from typing import Any

from app.engine.commands import CommandError, command, resolve_ids
from app.engine.records import loads
from app.engine.catalog import get as cat
from app.services import codes, metadata


def _state() -> dict:
    s = codes.settings()
    return {"sets": [{"name": n, "count": len(v)} for n, v in sorted(s["sets"].items(), key=lambda kv: kv[0].lower())], "active": s["active"],
            "delimiter": s["delimiter"], "delimiters": list(codes.DELIMITERS), "on": s["on"], "required": s["required"], "enforce": s["enforce"],
            "tokens": [f"{{{t}}}" for t in codes.TOKENS], "fields": metadata.META_FIELDS}


@command("codes.state", "Code Replacements", mutates=False,
         description="Code replacement sets (name and size), the active set, the delimiter, whether expansion is on, the required metadata fields and whether export refuses photos missing them, plus the caption variables such as {date} and {city}.")
def codes_state() -> dict:
    return _state()


@command("codes.get", "Code Replacement Set", {"name": {"type": "string"}}, mutates=False, description="A code set as tab-separated text, one code and its replacement per line.")
def codes_get(name: str = "") -> dict:
    s = codes.settings()
    key = name or s["active"]
    if key not in s["sets"]:
        raise CommandError(f"No code set {key}" if key else "No code set yet")
    return {"name": key, "text": codes.to_text(s["sets"][key]), "count": len(s["sets"][key])}


@command("codes.save", "Save Code Replacements", {"name": {"type": "string"}, "text": {"type": "string", "description": "one code per line: code, then a tab or comma, then the replacement; lines starting with # are skipped"},
                                                  "activate": {"type": "boolean"}},
         description="Creates or replaces a code replacement set from text (Photo Mechanic style: code TAB replacement) and makes it the active set unless activate is false.")
def codes_save(name: str, text: str, activate: bool = True) -> dict:
    name = name.strip()
    if not name:
        raise CommandError("A set needs a name")
    parsed = codes.parse(text)
    if not parsed:
        raise CommandError("No codes found: each line needs a code, a tab or comma, and its replacement")
    s = codes.settings()
    sets = dict(s["sets"])
    sets[name] = parsed
    codes.save(sets=sets, active=name if activate or not s["active"] else s["active"])
    return {"name": name, "count": len(parsed), **_state()}


@command("codes.importFile", "Import Code Replacements", {"path": {"type": "string"}, "name": {"type": "string"}, "activate": {"type": "boolean"}},
         description="Reads a code replacement text file (tab or comma separated, UTF-8, UTF-16 or Windows-1252) into a set named after the file unless name is given.")
def codes_import(path: str, name: str = "", activate: bool = True) -> dict:
    try:
        text = codes.read_file(path)
    except OSError as e:
        raise CommandError(f"Could not read {path}: {e.strerror or e}") from e
    from pathlib import Path
    return codes_save(name or Path(path).stem, text, activate)


@command("codes.delete", "Delete Code Replacements", {"name": {"type": "string"}})
def codes_delete(name: str) -> dict:
    s = codes.settings()
    if name not in s["sets"]:
        raise CommandError(f"No code set {name}")
    sets = {k: v for k, v in s["sets"].items() if k != name}
    codes.save(sets=sets, active=s["active"] if s["active"] != name else next(iter(sets), ""))
    return _state()


@command("codes.settings", "Caption Settings", {"active": {"type": "string"}, "delimiter": {"type": "string", "enum": list(codes.DELIMITERS)}, "on": {"type": "boolean"},
                                               "required": {"type": "array", "items": {"type": "string"}}, "enforce": {"type": "boolean"}},
         description="Chooses the active code set, the delimiter around codes (=ab= by default), turns expansion on or off, and sets the metadata fields every photo must have before export (enforce makes export refuse photos missing them).")
def codes_settings(active: str | None = None, delimiter: str | None = None, on: bool | None = None, required: list[str] | None = None, enforce: bool | None = None) -> dict:
    s = codes.settings()
    if active is not None and active and active not in s["sets"]:
        raise CommandError(f"No code set {active}")
    if required is not None:
        bad = [f for f in required if f not in metadata.META_FIELDS]
        if bad:
            raise CommandError(f"Not metadata fields: {', '.join(bad)}")
    codes.save(active=active, delimiter=delimiter, on=on, required=required, enforce=enforce)
    return _state()


@command("codes.expand", "Try Code Replacements", {"text": {"type": "string"}, "id": {"type": "integer"}}, mutates=False,
         description="Shows what a caption becomes: codes from the active set replaced and, when a photo id is given, variables such as {date}, {camera} and {city} filled from that photo.")
def codes_expand(text: str, id: int | None = None) -> dict:
    row, meta = {}, {}
    if id is not None:
        r = cat().row("SELECT * FROM photos WHERE id=?", (int(id),))
        if r is None:
            raise CommandError(f"No photo {id}")
        row, meta = dict(r), loads(r["meta"], {}) or {}
    out, unknown = codes.expand_fields({"text": text}, row, meta)
    return {"text": out["text"], "unknownCodes": sorted(set(unknown))}


def check(pids: list[int], required: list[str] | None = None) -> dict:
    req = codes.settings()["required"] if required is None else required
    missing: dict[str, list[str]] = {}
    if req:
        for i in range(0, len(pids), 500):
            chunk = pids[i:i + 500]
            for r in cat().rows(f"SELECT id, meta FROM photos WHERE id IN ({','.join('?' * len(chunk))})", tuple(chunk)):
                m = codes.missing(loads(r["meta"], {}) or {}, req)
                if m:
                    missing[str(int(r["id"]))] = m
    fields: dict[str, int] = {}
    for m in missing.values():
        for f in m:
            fields[f] = fields.get(f, 0) + 1
    return {"required": req, "missing": missing, "incomplete": len(missing), "complete": len(pids) - len(missing), "byField": fields}


@command("metadata.checkRequired", "Check Required Metadata", {"ids": {"type": "array"}, "required": {"type": "array", "items": {"type": "string"}}}, mutates=False,
         description="Which photos are missing the required metadata fields (from codes.settings, or the fields given), per photo and per field.")
def check_required(ids: Any = None, required: list[str] | None = None) -> dict:
    return check(resolve_ids(ids), required)


def require_for_export(pids: list[int]) -> None:
    s = codes.settings()
    if not s["enforce"] or not s["required"]:
        return
    r = check(pids, s["required"])
    if r["incomplete"]:
        top = ", ".join(f"{f} ({n})" for f, n in sorted(r["byField"].items(), key=lambda kv: -kv[1])[:4])
        raise CommandError(f"{r['incomplete']} of {len(pids)} photos are missing required metadata: {top}. Fill them in, or turn off Refuse Export in Metadata, Required Fields")
