import re
from pathlib import Path

from app.core import prefs

DELIMITERS = ("=", "\\", "#", "~", "|")
META_TOKENS = ("city", "state", "country", "location", "sublocation", "event", "creator", "credit", "headline", "jobId", "personShown")
TOKENS = ("date", "time", "year", "month", "day", "camera", "lens", "focal", "filename", "name") + META_TOKENS
_TOKEN = re.compile(r"\{(" + "|".join(TOKENS) + r")\}")
_CODE_CHARS = r"[A-Za-z0-9_.\-]{1,40}"


def settings() -> dict:
    c = prefs.load().get("codes") or {}
    delim = c.get("delimiter") if c.get("delimiter") in DELIMITERS else "="
    return {"sets": c.get("sets") or {}, "active": c.get("active") or "", "delimiter": delim, "on": bool(c.get("on", True)),
            "required": [f for f in (c.get("required") or []) if isinstance(f, str)], "enforce": bool(c.get("enforce", False))}


def save(**changes) -> dict:
    s = settings()
    s.update({k: v for k, v in changes.items() if v is not None})
    prefs.update({"codes": s})
    return s


def parse(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        sep = "\t" if "\t" in line else "," if "," in line else None
        if sep is None:
            continue
        code, _, value = line.partition(sep)
        code = code.strip()
        if code and re.fullmatch(_CODE_CHARS, code):
            out[code] = value.strip()
    return out


def read_file(path: str) -> str:
    data = Path(path).expanduser().read_bytes()
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def to_text(codes: dict[str, str]) -> str:
    return "\n".join(f"{k}\t{v}" for k, v in codes.items())


def active_codes(s: dict | None = None) -> dict[str, str]:
    s = s or settings()
    return dict(s["sets"].get(s["active"]) or {}) if s["on"] else {}


def expand_codes(text: str, codes: dict[str, str], delim: str) -> tuple[str, list[str]]:
    if not codes or delim not in text:
        return text, []
    lower = {k.lower(): v for k, v in codes.items()}
    unknown: list[str] = []
    d = re.escape(delim)

    def sub(m: re.Match) -> str:
        code = m.group(1)
        val = codes.get(code, lower.get(code.lower()))
        if val is None:
            unknown.append(code)
            return m.group(0)
        return val
    return re.sub(d + "(" + _CODE_CHARS + ")" + d, sub, text), unknown


def token_values(row: dict, meta: dict) -> dict[str, str]:
    t = str(row.get("capture_time") or "")
    name = str(row.get("file_name") or "")
    out = {"date": t[:10], "time": t[11:16], "year": t[:4], "month": t[5:7], "day": t[8:10], "camera": str(row.get("camera") or ""),
           "lens": str(row.get("lens") or ""), "focal": f"{float(row['focal']):g} mm" if row.get("focal") else "", "filename": name,
           "name": name.rsplit(".", 1)[0]}
    for k in META_TOKENS:
        v = meta.get(k)
        out[k] = ", ".join(map(str, v)) if isinstance(v, list) else str(v or "")
    return out


def expand_tokens(text: str, values: dict[str, str]) -> str:
    if "{" not in text:
        return text
    return _TOKEN.sub(lambda m: values.get(m.group(1)) or "", text)


def expand_fields(fields: dict, row: dict, meta: dict, s: dict | None = None) -> tuple[dict, list[str]]:
    s = s or settings()
    codes = active_codes(s)
    values: dict[str, str] | None = None
    out, unknown = {}, []
    for k, v in fields.items():
        if isinstance(v, str) and v:
            v, miss = expand_codes(v, codes, s["delimiter"])
            unknown += miss
            if "{" in v:
                values = values or token_values(row, meta)
                v = expand_tokens(v, values)
        out[k] = v
    return out, unknown


def missing(meta: dict, required: list[str]) -> list[str]:
    return [f for f in required if not str(meta.get(f) or "").strip()]
