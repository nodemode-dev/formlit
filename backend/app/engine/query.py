import re
import shlex
import time
from typing import Any

from app.engine.catalog import Catalog
from app.engine.records import SUMMARY_SQL, summary

RULE_FIELDS = {
    "rating": ("p.rating", "num"), "flag": ("p.flag", "flag"), "label": ("p.label", "text"), "kind": ("p.kind", "text"), "format": ("p.format", "text"),
    "edited": ("p.edited", "bool"), "camera": ("p.camera", "text"), "lens": ("p.lens", "text"), "iso": ("p.iso", "num"), "focal": ("p.focal", "num"),
    "aperture": ("p.aperture", "num"), "shutter": ("p.shutter", "num"), "captureTime": ("p.capture_time", "date"), "importTime": ("p.import_time", "date"),
    "editTime": ("p.edit_time", "date"), "fileName": ("p.file_name", "text"), "folder": ("f.path", "text"), "fileSize": ("p.file_size", "num"),
    "width": ("p.width", "num"), "height": ("p.height", "num"), "missing": ("p.missing", "bool"), "hasGps": ("(p.gps_lat IS NOT NULL)", "bool"),
    "virtualCopy": ("(p.master_id IS NOT NULL)", "bool"), "title": ("json_extract(p.meta, '$.title')", "text"),
    "caption": ("json_extract(p.meta, '$.caption')", "text"), "creator": ("json_extract(p.meta, '$.creator')", "text"),
    "city": ("json_extract(p.meta, '$.city')", "text"), "state": ("json_extract(p.meta, '$.state')", "text"),
    "country": ("json_extract(p.meta, '$.country')", "text"), "location": ("COALESCE(json_extract(p.meta, '$.sublocation'), json_extract(p.meta, '$.location'))", "text"),
    "copyright": ("json_extract(p.meta, '$.copyright')", "text"), "keyword": ("keyword", "keyword"), "collection": ("collection", "collection"),
    "person": ("person", "person"), "sharpness": ("json_extract(p.meta, '$.cull.sharpness')", "num"), "bestOfGroup": ("json_extract(p.meta, '$.cull.best')", "bool"),
    "smartPreview": ("p.smart_preview", "bool"), "duration": ("p.duration", "num"),
}

SORTS = {
    "captureTime": "p.capture_time", "importTime": "p.import_time", "editTime": "p.edit_time", "fileName": "p.file_name COLLATE NOCASE",
    "rating": "p.rating", "flag": "p.flag", "label": "p.label", "kind": "p.kind", "fileSize": "p.file_size", "camera": "p.camera",
    "aspect": "(CAST(p.width AS REAL) / MAX(p.height, 1))", "added": "p.id",
}
FLAGS = {"pick": 1, "picked": 1, "reject": -1, "rejected": -1, "unflagged": 0, "none": 0}

FACETS: dict[str, tuple[str, str]] = {
    "date": ("Date", "substr(p.capture_time, 1, 10)"),
    "year": ("Year", "substr(p.capture_time, 1, 4)"),
    "month": ("Month", "substr(p.capture_time, 1, 7)"),
    "fileType": ("File Type", "upper(p.format)"),
    "camera": ("Camera", "p.camera"),
    "serial": ("Camera Serial Number", "json_extract(p.exif, '$.serial')"),
    "lens": ("Lens", "p.lens"),
    "focal": ("Focal Length", "CASE WHEN p.focal IS NULL THEN NULL ELSE CAST(ROUND(p.focal) AS INTEGER) || ' mm' END"),
    "shutter": ("Shutter Speed", "CASE WHEN p.shutter IS NULL OR p.shutter <= 0 THEN NULL WHEN p.shutter >= 0.4 THEN printf('%g sec', ROUND(p.shutter, 1)) ELSE '1/' || CAST(ROUND(1.0 / p.shutter) AS INTEGER) || ' sec' END"),
    "aperture": ("Aperture", "CASE WHEN p.aperture IS NULL THEN NULL ELSE printf('f / %.1f', p.aperture) END"),
    "iso": ("ISO Speed", "CASE WHEN p.iso IS NULL THEN NULL ELSE 'ISO ' || p.iso END"),
    "flash": ("Flash State", "CASE WHEN p.flash IS NULL THEN NULL WHEN p.flash THEN 'Did fire' ELSE 'Did not fire' END"),
    "label": ("Label", "CASE WHEN p.label = '' THEN 'No Label' ELSE p.label END"),
    "rating": ("Rating", "CASE p.rating WHEN 0 THEN 'Unrated' WHEN 1 THEN '1 star' ELSE p.rating || ' stars' END"),
    "flag": ("Pick Flag", "CASE p.flag WHEN 1 THEN 'Flagged' WHEN -1 THEN 'Rejected' ELSE 'Unflagged' END"),
    "edited": ("Has Adjustments", "CASE WHEN p.edited THEN 'Edited' ELSE 'Unedited' END"),
    "treatment": ("Treatment", "CASE WHEN json_extract(p.develop, '$.treatment') = 'bw' THEN 'Black & White' ELSE 'Color' END"),
    "preset": ("Develop Preset", "COALESCE((SELECT substr(h.name, 9) FROM history h WHERE h.photo_id = p.id AND h.name LIKE 'Preset: %' ORDER BY h.id DESC LIMIT 1), 'Default')"),
    "aspect": ("Aspect Ratio", "CASE WHEN p.width = 0 OR p.height = 0 THEN NULL WHEN p.width > p.height * 1.02 THEN 'Landscape' WHEN p.height > p.width * 1.02 THEN 'Portrait' ELSE 'Square' END"),
    "kind": ("Media Type", "CASE p.kind WHEN 'video' THEN 'Video' ELSE 'Photo' END"),
    "smartPreview": ("Smart Preview Status", "CASE WHEN p.smart_preview THEN 'Has Smart Preview' ELSE 'No Smart Preview' END"),
    "gps": ("GPS Data", "CASE WHEN p.gps_lat IS NULL THEN 'No Coordinates' ELSE 'Coordinates' END"),
    "creator": ("Creator", "json_extract(p.meta, '$.creator')"),
    "copyrightStatus": ("Copyright Status", "COALESCE(NULLIF(json_extract(p.meta, '$.copyrightStatus'), ''), 'Unknown')"),
    "job": ("Job", "json_extract(p.meta, '$.jobId')"),
    "country": ("Country", "json_extract(p.meta, '$.country')"),
    "state": ("State / Province", "json_extract(p.meta, '$.state')"),
    "city": ("City", "json_extract(p.meta, '$.city')"),
    "location": ("Location", "COALESCE(NULLIF(json_extract(p.meta, '$.sublocation'), ''), json_extract(p.meta, '$.location'))"),
    "folder": ("Folder", "f.path"),
    "keyword": ("Keyword", ""),
    "collection": ("Collection", ""),
    "person": ("People", ""),
}
JOIN_FACETS = {
    "keyword": ("SELECT k.id AS v, k.name AS n, COUNT(DISTINCT p.id) AS c FROM photo_keywords pk JOIN keywords k ON k.id = pk.keyword_id JOIN photos p ON p.id = pk.photo_id JOIN folders f ON f.id = p.folder_id WHERE {w} GROUP BY k.id ORDER BY k.name COLLATE NOCASE",
                "EXISTS (SELECT 1 FROM photo_keywords pk WHERE pk.photo_id = p.id AND pk.keyword_id IN ({q}))"),
    "collection": ("SELECT c.id AS v, c.name AS n, COUNT(DISTINCT p.id) AS c FROM collection_photos cp JOIN collections c ON c.id = cp.collection_id JOIN photos p ON p.id = cp.photo_id JOIN folders f ON f.id = p.folder_id WHERE {w} AND c.kind = 'collection' GROUP BY c.id ORDER BY c.name COLLATE NOCASE",
                   "EXISTS (SELECT 1 FROM collection_photos cp WHERE cp.photo_id = p.id AND cp.collection_id IN ({q}))"),
    "person": ("SELECT pe.id AS v, pe.name AS n, COUNT(DISTINCT p.id) AS c FROM faces fc JOIN people pe ON pe.id = fc.person_id JOIN photos p ON p.id = fc.photo_id JOIN folders f ON f.id = p.folder_id WHERE {w} GROUP BY pe.id ORDER BY pe.name COLLATE NOCASE",
               "EXISTS (SELECT 1 FROM faces fc WHERE fc.photo_id = p.id AND fc.person_id IN ({q}))"),
}
UNKNOWN = "Unknown"


def meta_clause(meta: dict, args: list, upto: list[str] | None = None) -> str:
    parts: list[str] = []
    for name, vals in meta.items():
        if not vals or name not in FACETS or (upto is not None and name not in upto):
            continue
        if name in JOIN_FACETS:
            ids = [int(v) for v in vals]
            args.extend(ids)
            parts.append(JOIN_FACETS[name][1].format(q=",".join("?" * len(ids))))
            continue
        expr = FACETS[name][1]
        named = [v for v in vals if v != UNKNOWN]
        sub = []
        if named:
            args.extend(named)
            sub.append(f"({expr}) IN ({','.join('?' * len(named))})")
        if UNKNOWN in vals:
            sub.append(f"COALESCE(({expr}), '') = ''")
        parts.append("(" + " OR ".join(sub) + ")")
    return " AND ".join(parts) if parts else "1"


def facet_columns(cat: Catalog, source: dict | None, columns: list[str], meta: dict | None = None, flt: dict | None = None) -> dict:
    meta = meta or {}
    out: dict[str, list[dict]] = {}
    for i, name in enumerate(columns):
        if name not in FACETS:
            continue
        args: list = []
        src_sql, _ = source_clause(cat, source or {"kind": "all"}, args)
        flt_sql = filter_clause({k: v for k, v in (flt or {}).items() if k != "meta"}, args)
        left = meta_clause(meta, args, columns[:i])
        w = f"({src_sql}) AND ({flt_sql}) AND ({left})"
        if name in JOIN_FACETS:
            rows = cat.rows(JOIN_FACETS[name][0].format(w=w), tuple(args))
            out[name] = [{"value": int(r["v"]), "name": r["n"], "count": int(r["c"])} for r in rows]
            continue
        expr = FACETS[name][1]
        rows = cat.rows(f"SELECT COALESCE(NULLIF(({expr}), ''), '{UNKNOWN}') AS v, COUNT(*) AS c FROM photos p JOIN folders f ON f.id = p.folder_id WHERE {w} GROUP BY 1", tuple(args))
        items = [{"value": r["v"], "count": int(r["c"])} for r in rows]
        if name in ("date", "year", "month"):
            items.sort(key=lambda x: ("" if x["value"] == UNKNOWN else str(x["value"])), reverse=True)
        elif name in ("focal", "iso", "aperture"):
            items.sort(key=lambda x: (x["value"] == UNKNOWN, float(re.sub(r"[^0-9.]", "", str(x["value"])) or 0)))
        else:
            items.sort(key=lambda x: (x["value"] == UNKNOWN, str(x["value"]).lower()))
        out[name] = items
    return out


def _flag_value(v: Any) -> int:
    if isinstance(v, (int, float)):
        return int(v)
    return FLAGS.get(str(v).lower(), 0)


def compile_rule(rule: dict, args: list) -> str | None:
    field = rule.get("field", "")
    op = rule.get("op", "=")
    value = rule.get("value")
    if field not in RULE_FIELDS:
        return None
    col, typ = RULE_FIELDS[field]
    if typ == "keyword":
        args.append(f"%{value}%")
        sub = "EXISTS (SELECT 1 FROM photo_keywords pk JOIN keywords k ON k.id=pk.keyword_id WHERE pk.photo_id=p.id AND k.name LIKE ?)"
        if op in ("=", "is"):
            args[-1] = str(value)
            sub = sub.replace("k.name LIKE ?", "k.name = ? COLLATE NOCASE")
        return f"NOT {sub}" if op in ("!=", "notContains", "isNot") else sub
    if typ == "collection":
        args.append(int(value))
        sub = "EXISTS (SELECT 1 FROM collection_photos cp WHERE cp.photo_id=p.id AND cp.collection_id=?)"
        return f"NOT {sub}" if op in ("!=", "isNot") else sub
    if typ == "person":
        args.append(int(value))
        sub = "EXISTS (SELECT 1 FROM faces fc WHERE fc.photo_id=p.id AND fc.person_id=?)"
        return f"NOT {sub}" if op in ("!=", "isNot") else sub
    if op == "isEmpty":
        return f"({col} IS NULL OR {col} = '')"
    if op == "notEmpty":
        return f"({col} IS NOT NULL AND {col} != '')"
    if typ == "flag":
        value = _flag_value(value)
    if typ == "bool":
        truthy = value in (True, 1, "1", "true", "yes", "on")
        return col if truthy else f"NOT {col}"
    if typ == "date" and op == "inLast":
        days = float(value or 0)
        args.append(time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - days * 86400)))
        return f"{col} >= ?"
    if op == "between" and isinstance(value, (list, tuple)) and len(value) == 2:
        args.extend(value)
        return f"{col} BETWEEN ? AND ?"
    if op in ("contains", "notContains", "startsWith", "endsWith"):
        pat = {"contains": "%{}%", "notContains": "%{}%", "startsWith": "{}%", "endsWith": "%{}"}[op].format(value)
        args.append(pat)
        return f"COALESCE({col}, '') {'NOT ' if op == 'notContains' else ''}LIKE ?"
    sql_op = {"=": "=", "is": "=", "!=": "!=", "isNot": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}.get(op)
    if sql_op is None:
        return None
    if typ == "text" and sql_op in ("=", "!="):
        args.append(value)
        return f"COALESCE({col}, '') {sql_op} ? COLLATE NOCASE"
    args.append(value)
    return f"{col} {sql_op} ?"


def compile_rules(rules: dict, args: list) -> str:
    parts = [c for c in (compile_rule(r, args) for r in rules.get("rules", [])) if c]
    nested = [compile_rules(g, args) for g in rules.get("groups", [])]
    parts += [n for n in nested if n]
    if not parts:
        return "1"
    match = rules.get("match", "all")
    if match == "any":
        return "(" + " OR ".join(parts) + ")"
    if match == "none":
        return "NOT (" + " OR ".join(parts) + ")"
    return "(" + " AND ".join(parts) + ")"


TEXT_FIELDS = {"rating": "rating", "flag": "flag", "label": "label", "kind": "kind", "camera": "camera", "lens": "lens", "iso": "iso", "focal": "focal",
               "date": "captureTime", "keyword": "keyword", "edited": "edited", "folder": "folder", "city": "city", "country": "country",
               "title": "title", "file": "fileName", "name": "fileName", "aperture": "aperture", "format": "format", "gps": "hasGps"}


def parse_text(text: str) -> dict:
    rules: list[dict] = []
    free: list[str] = []
    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = text.split()
    for tok in tokens:
        m = re.fullmatch(r"([a-zA-Z]+):(>=|<=|>|<|=|!)?(.+)", tok)
        if m and m.group(1).lower() in TEXT_FIELDS:
            field = TEXT_FIELDS[m.group(1).lower()]
            op = {"!": "!=", None: "="}.get(m.group(2), m.group(2))
            val: Any = m.group(3)
            typ = RULE_FIELDS[field][1]
            if field == "captureTime":
                rules.append({"field": field, "op": "startsWith", "value": val})
                continue
            if typ in ("text", "keyword") and op == "=":
                op = "contains"
            if typ == "num":
                try:
                    val = float(val)
                except ValueError:
                    continue
            rules.append({"field": field, "op": op, "value": val})
        else:
            free.append(tok)
    return {"rules": rules, "free": free}


def _free_text(words: list[str], args: list) -> str:
    parts = []
    for w in words:
        neg = w.startswith("!")
        w = w.lstrip("!")
        if not w:
            continue
        pat = f"%{w}%"
        cols = ["p.file_name", "p.camera", "p.lens", "p.meta", "f.path"]
        clause = " OR ".join(f"COALESCE({c}, '') LIKE ?" for c in cols)
        args.extend([pat] * len(cols))
        args.append(pat)
        clause += " OR EXISTS (SELECT 1 FROM photo_keywords pk JOIN keywords k ON k.id=pk.keyword_id WHERE pk.photo_id=p.id AND k.name LIKE ?)"
        parts.append(f"NOT ({clause})" if neg else f"({clause})")
    return " AND ".join(parts) if parts else "1"


def _folder_ids(cat: Catalog, fid: int, recursive: bool) -> list[int]:
    if not recursive:
        return [fid]
    root = cat.row("SELECT path FROM folders WHERE id=?", (fid,))
    if not root:
        return [fid]
    prefix = root["path"].rstrip("/\\")
    return [int(r["id"]) for r in cat.rows("SELECT id FROM folders WHERE path=? OR path LIKE ? OR path LIKE ?", (prefix, prefix + "/%", prefix + "\\%"))]


def source_clause(cat: Catalog, source: dict, args: list) -> tuple[str, str | None]:
    kind = source.get("kind", "all")
    if kind == "all":
        return "1", None
    if kind == "folder":
        ids = _folder_ids(cat, int(source["id"]), bool(source.get("recursive", True)))
        args.extend(ids)
        return f"p.folder_id IN ({','.join('?' * len(ids))})", None
    if kind in ("collection", "quick"):
        cid = int(source["id"]) if kind == "collection" else int(cat.scalar("SELECT id FROM collections WHERE kind='quick'") or 0)
        crow = cat.row("SELECT kind, rules FROM collections WHERE id=?", (cid,))
        if crow and (crow["kind"] == "smart" or (crow["kind"] == "published" and crow["rules"])):
            import json
            return compile_rules(json.loads(crow["rules"] or "{}"), args), None
        if crow and crow["kind"] in ("set", "publishedSet"):
            import json
            kids = collection_descendants(cat, cid)
            if not kids:
                return "0", None
            smart = [(k, r["rules"]) for k in kids for r in [cat.row("SELECT kind, rules FROM collections WHERE id=?", (k,))] if r and r["rules"] and r["kind"] in ("smart", "published")]
            plain = [k for k in kids if k not in {s[0] for s in smart}]
            ors = []
            if plain:
                args.extend(plain)
                ors.append(f"EXISTS (SELECT 1 FROM collection_photos cp WHERE cp.photo_id=p.id AND cp.collection_id IN ({','.join('?' * len(plain))}))")
            for _, rules in smart:
                ors.append(compile_rules(json.loads(rules or "{}"), args))
            return "(" + " OR ".join(ors) + ")", None
        args.append(cid)
        return "EXISTS (SELECT 1 FROM collection_photos cp WHERE cp.photo_id=p.id AND cp.collection_id=?)", f"(SELECT position FROM collection_photos cp WHERE cp.photo_id=p.id AND cp.collection_id={cid})"
    if kind == "keyword":
        args.append(int(source["id"]))
        return "EXISTS (SELECT 1 FROM photo_keywords pk WHERE pk.photo_id=p.id AND pk.keyword_id IN (WITH RECURSIVE t(id) AS (SELECT ? UNION ALL SELECT k.id FROM keywords k JOIN t ON k.parent_id=t.id) SELECT id FROM t))", None
    if kind == "person":
        args.append(int(source["id"]))
        return "EXISTS (SELECT 1 FROM faces fc WHERE fc.photo_id=p.id AND fc.person_id=?)", None
    if kind == "missing":
        return "p.missing=1", None
    if kind == "previousImport":
        ids = cat.get_meta("lastImport", []) or []
        if not ids:
            return "0", None
        args.extend(ids)
        return f"p.id IN ({','.join('?' * len(ids))})", None
    if kind == "recent":
        last = cat.scalar("SELECT MAX(import_time) FROM photos")
        if not last:
            return "0", None
        days = float(source.get("days", 30))
        args.append(time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.mktime(time.strptime(last[:19], "%Y-%m-%dT%H:%M:%S")) - days * 86400)))
        return "p.import_time >= ?", None
    if kind == "date":
        args.append(str(source.get("value", "")) + "%")
        return "p.capture_time LIKE ?", None
    if kind == "ids":
        ids = [int(i) for i in source.get("ids", [])]
        if not ids:
            return "0", None
        args.extend(ids)
        return f"p.id IN ({','.join('?' * len(ids))})", None
    if kind == "rules":
        return compile_rules(source.get("rules", {}), args), None
    return "1", None


def collection_descendants(cat: Catalog, cid: int) -> list[int]:
    rows = cat.rows("WITH RECURSIVE t(id) AS (SELECT id FROM collections WHERE parent_id=? UNION ALL SELECT c.id FROM collections c JOIN t ON c.parent_id=t.id) SELECT id FROM t", (cid,))
    return [int(r["id"]) for r in rows]


def filter_clause(flt: dict, args: list) -> str:
    parts: list[str] = []
    text = (flt.get("text") or "").strip()
    if text:
        parsed = parse_text(text)
        if parsed["rules"]:
            parts.append(compile_rules({"match": "all", "rules": parsed["rules"]}, args))
        if parsed["free"]:
            parts.append(_free_text(parsed["free"], args))
    if flt.get("rating") not in (None, ""):
        op = {"gte": ">=", "eq": "=", "lte": "<=", ">=": ">=", "=": "=", "<=": "<="}.get(flt.get("ratingOp", ">="), ">=")
        args.append(int(flt["rating"]))
        parts.append(f"p.rating {op} ?")
    flags = flt.get("flags")
    if flags:
        vals = sorted({_flag_value(f) for f in flags})
        args.extend(vals)
        parts.append(f"p.flag IN ({','.join('?' * len(vals))})")
    labels = flt.get("labels")
    if labels:
        named = [l for l in labels if l != "none"]
        sub = []
        if named:
            args.extend(named)
            sub.append(f"p.label IN ({','.join('?' * len(named))})")
        if "none" in labels:
            sub.append("p.label = ''")
        parts.append("(" + " OR ".join(sub) + ")")
    kinds = flt.get("kinds")
    if kinds:
        args.extend(kinds)
        parts.append(f"p.kind IN ({','.join('?' * len(kinds))})")
    if flt.get("edited") is not None:
        parts.append("p.edited=1" if flt["edited"] else "p.edited=0")
    if flt.get("virtualCopies") is not None:
        parts.append("p.master_id IS NOT NULL" if flt["virtualCopies"] else "p.master_id IS NULL")
    for key, col in (("cameras", "p.camera"), ("lenses", "p.lens"), ("formats", "p.format")):
        vals = flt.get(key)
        if vals:
            args.extend(vals)
            parts.append(f"{col} IN ({','.join('?' * len(vals))})")
    kws = flt.get("keywords")
    if kws:
        args.extend(int(k) for k in kws)
        parts.append(f"EXISTS (SELECT 1 FROM photo_keywords pk WHERE pk.photo_id=p.id AND pk.keyword_id IN ({','.join('?' * len(kws))}))")
    dates = flt.get("dates")
    if dates:
        sub = []
        for d in dates:
            args.append(str(d) + "%")
            sub.append("p.capture_time LIKE ?")
        parts.append("(" + " OR ".join(sub) + ")")
    if flt.get("rules"):
        parts.append(compile_rules(flt["rules"], args))
    if flt.get("meta"):
        parts.append(meta_clause(flt["meta"], args))
    if flt.get("hasGps") is not None:
        parts.append("p.gps_lat IS NOT NULL" if flt["hasGps"] else "p.gps_lat IS NULL")
    box = flt.get("gpsBox")
    if isinstance(box, (list, tuple)) and len(box) == 4:
        la0, lo0, la1, lo1 = (float(v) for v in box)
        args.extend([min(la0, la1), max(la0, la1)])
        lon_sql = "p.gps_lon BETWEEN ? AND ?" if lo0 <= lo1 else "(p.gps_lon >= ? OR p.gps_lon <= ?)"
        args.extend([lo0, lo1])
        parts.append(f"(p.gps_lat BETWEEN ? AND ? AND {lon_sql})")
    return " AND ".join(parts) if parts else "1"


def query(cat: Catalog, source: dict | None = None, flt: dict | None = None, sort: dict | None = None, stacks: bool = True, limit: int | None = None) -> dict:
    source = source or {"kind": "all"}
    flt = flt or {}
    sort = sort or {}
    args: list = []
    src_sql, order_expr = source_clause(cat, source, args)
    flt_sql = filter_clause(flt, args)
    where = f"({src_sql}) AND ({flt_sql})"
    key = sort.get("by", "captureTime")
    direction = "DESC" if sort.get("desc") else "ASC"
    if key == "userOrder" and order_expr:
        order = f"{order_expr} {direction}, p.capture_time, p.id"
    else:
        order = f"{SORTS.get(key, 'p.capture_time')} {direction}, p.file_name COLLATE NOCASE {direction}, COALESCE(p.master_id, p.id), p.id"
    sql = f"{SUMMARY_SQL} JOIN folders f ON f.id=p.folder_id WHERE {where} ORDER BY {order}"
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = cat.rows(sql, tuple(args))
    collapsed = {int(r["id"]) for r in cat.rows("SELECT id FROM stacks WHERE collapsed=1")} if stacks else set()
    counts: dict[int, int] = {}
    for r in cat.rows("SELECT stack_id, COUNT(*) AS n FROM photos WHERE stack_id IS NOT NULL GROUP BY stack_id"):
        counts[int(r["stack_id"])] = int(r["n"])
    ids: list[int] = []
    photos: dict[int, dict] = {}
    for r in rows:
        s = summary(r)
        sid = r["stack_id"]
        if sid:
            s["sn"] = counts.get(int(sid), 1)
            s["sc"] = 1 if int(sid) in collapsed else 0
            if int(sid) in collapsed and r["stack_pos"] != 0:
                continue
        ids.append(int(r["id"]))
        photos[int(r["id"])] = s
    return {"ids": ids, "photos": photos, "total": len(ids)}


def facets(cat: Catalog, source: dict | None = None) -> dict:
    args: list = []
    src_sql, _ = source_clause(cat, source or {"kind": "all"}, args)
    base = f"FROM photos p JOIN folders f ON f.id=p.folder_id WHERE {src_sql}"
    out: dict[str, Any] = {}
    for name, col in (("cameras", "p.camera"), ("lenses", "p.lens"), ("formats", "p.format"), ("labels", "p.label"), ("kinds", "p.kind")):
        out[name] = [{"value": r[0], "count": r[1]} for r in cat.rows(f"SELECT {col}, COUNT(*) {base} GROUP BY {col} ORDER BY COUNT(*) DESC", tuple(args)) if r[0] not in (None, "")]
    out["ratings"] = [{"value": r[0], "count": r[1]} for r in cat.rows(f"SELECT p.rating, COUNT(*) {base} GROUP BY p.rating ORDER BY p.rating DESC", tuple(args))]
    out["flags"] = [{"value": r[0], "count": r[1]} for r in cat.rows(f"SELECT p.flag, COUNT(*) {base} GROUP BY p.flag", tuple(args))]
    out["dates"] = [{"value": r[0], "count": r[1]} for r in cat.rows(f"SELECT substr(p.capture_time, 1, 10), COUNT(*) {base} GROUP BY substr(p.capture_time, 1, 10) ORDER BY 1 DESC", tuple(args)) if r[0]]
    out["keywords"] = [{"value": r[0], "name": r[1], "count": r[2]} for r in cat.rows(f"SELECT k.id, k.name, COUNT(*) FROM photo_keywords pk JOIN keywords k ON k.id=pk.keyword_id JOIN photos p ON p.id=pk.photo_id JOIN folders f ON f.id=p.folder_id WHERE {src_sql} GROUP BY k.id ORDER BY k.name COLLATE NOCASE", tuple(args))]
    out["isos"] = [{"value": r[0], "count": r[1]} for r in cat.rows(f"SELECT p.iso, COUNT(*) {base} AND p.iso IS NOT NULL GROUP BY p.iso ORDER BY p.iso", tuple(args))]
    out["focals"] = [{"value": r[0], "count": r[1]} for r in cat.rows(f"SELECT p.focal, COUNT(*) {base} AND p.focal IS NOT NULL GROUP BY p.focal ORDER BY p.focal", tuple(args))]
    return out
