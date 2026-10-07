import re
from datetime import datetime
from pathlib import Path

TOKENS = {
    "name": "Original file name without its extension",
    "ext": "Original extension, lower case",
    "seq": "Sequence number; {seq:4} pads to 4 digits",
    "num": "Number found at the end of the original name",
    "date": "Capture date; {date:%Y-%m-%d} takes a strftime pattern",
    "year": "Capture year", "month": "Capture month (01 to 12)", "day": "Capture day (01 to 31)",
    "hour": "Capture hour", "minute": "Capture minute", "second": "Capture second",
    "camera": "Camera model", "lens": "Lens", "iso": "ISO", "focal": "Focal length in mm", "aperture": "Aperture",
    "rating": "Star rating", "label": "Colour label", "title": "Title", "creator": "Creator", "city": "City", "country": "Country",
    "folder": "Name of the folder the original is in", "custom": "Custom text passed with the template", "shoot": "Shoot name passed with the template",
    "copy": "Virtual copy name",
}

_TOKEN = re.compile(r"\{([a-z]+)(?::([^}]*))?\}")
_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def safe(text: str) -> str:
    return _UNSAFE.sub("-", text).strip().strip(".") or "untitled"


def expand(template: str, rec: dict, seq: int = 1, custom: str = "", shoot: str = "") -> str:
    name = Path(rec.get("fileName", "photo")).stem
    ext = Path(rec.get("fileName", "")).suffix.lower().lstrip(".")
    when = None
    try:
        when = datetime.fromisoformat((rec.get("captureTime") or "")[:19])
    except ValueError:
        when = None
    meta = rec.get("meta") or {}
    found = re.search(r"(\d+)$", name)

    def one(m: re.Match) -> str:
        key, arg = m.group(1), m.group(2)
        if key == "name":
            return name
        if key == "ext":
            return ext
        if key == "seq":
            width = int(arg) if arg and arg.isdigit() else 1
            return str(seq).zfill(width)
        if key == "num":
            return found.group(1) if found else str(seq)
        if key in ("date", "year", "month", "day", "hour", "minute", "second"):
            if when is None:
                return "undated"
            fmt = {"date": arg or "%Y%m%d", "year": "%Y", "month": "%m", "day": "%d", "hour": "%H", "minute": "%M", "second": "%S"}[key]
            return when.strftime(fmt)
        if key == "camera":
            return str(rec.get("camera") or "camera")
        if key == "lens":
            return str(rec.get("lens") or "lens")
        if key == "iso":
            return str(rec.get("iso") or "")
        if key == "focal":
            return f"{rec['focal']:.0f}mm" if rec.get("focal") else ""
        if key == "aperture":
            return f"f{rec['aperture']:.1f}" if rec.get("aperture") else ""
        if key == "rating":
            return str(rec.get("rating", 0))
        if key == "label":
            return str(rec.get("label") or "")
        if key in ("title", "creator", "city", "country"):
            return str(meta.get(key) or "")
        if key == "folder":
            return Path(rec.get("folder", "")).name
        if key == "custom":
            return custom
        if key == "shoot":
            return shoot
        if key == "copy":
            return str(rec.get("copyName") or "")
        return m.group(0)

    out = _TOKEN.sub(one, template)
    parts = [safe(p) for p in re.split(r"[\\/]", out) if p.strip()]
    return "/".join(parts) if parts else safe(name)


def unique(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    i = 1
    while True:
        cand = path.with_name(f"{stem}-{i}{suffix}")
        if not cand.exists():
            return cand
        i += 1
