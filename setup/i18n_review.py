import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "frontend" / "src" / "i18n"
PLAIN = ["keys.json", "keys2.json", "keys3.json", "keys5.json", "keys6.json", "keys10.json", "keys11.json", "keys12.json", "keys13.json"]
FIXES = ["keys7.json", "keys8.json", "keys9.json"]


def _pairs(keys: str, lang: str) -> dict[str, str]:
    kf = ROOT / keys
    folder = "locales" if keys == "keys.json" else f"locales{keys[4:-5]}"
    lf = ROOT / folder / f"{lang}.json"
    if not kf.is_file() or not lf.is_file():
        return {}
    k, tr = json.loads(kf.read_text(encoding="utf-8")), json.loads(lf.read_text(encoding="utf-8"))
    return {en: tr[str(i)] for i, en in enumerate(k) if tr.get(str(i))}


def effective(lang: str) -> dict[str, str]:
    out: dict[str, str] = {}
    templ = lambda s: bool(re.search(r"\{\d+\}", s))
    for name in PLAIN:
        for en, t in _pairs(name, lang).items():
            if templ(en):
                out.setdefault(en, t)
            else:
                out[en] = t
    for en, t in _pairs("keys4.json", lang).items():
        out[en] = t
    for name in FIXES:
        out.update(_pairs(name, lang))
    return out


def export(lang: str, path: str) -> None:
    eff = effective(lang)
    if not eff:
        raise SystemExit(f"No translations for {lang}")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["english", "current", "corrected", "note"])
        for en in sorted(eff, key=str.lower):
            w.writerow([en, eff[en], "", ""])
    print(f"{len(eff)} strings for {lang} written to {path}; fill the corrected column and run: ./formlit i18n import {lang} {path}")


def load(lang: str, path: str) -> None:
    eff = effective(lang)
    with open(path, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if (r.get("corrected") or "").strip()]
    kf = ROOT / "keys9.json"
    keys = json.loads(kf.read_text(encoding="utf-8")) if kf.is_file() else []
    lf = ROOT / "locales9" / f"{lang}.json"
    tr = json.loads(lf.read_text(encoding="utf-8")) if lf.is_file() else {}
    bad = []
    for r in rows:
        en, new = r["english"], r["corrected"].strip()
        if en not in eff:
            bad.append(f"not an app string: {en[:60]}")
            continue
        missing = [p for p in sorted(set(re.findall(r"\{\d+\}", en))) if p not in new and not re.search(r"[A-Za-z]" + re.escape(p), en) and f"{{{p[1:-1]}:" not in new]
        if missing:
            bad.append(f"placeholder {', '.join(missing)} missing: {en[:60]}")
            continue
        if en not in keys:
            keys.append(en)
        tr[str(keys.index(en))] = new
    lf.parent.mkdir(exist_ok=True)
    kf.write_text(json.dumps(keys, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    lf.write_text(json.dumps(tr, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(rows) - len(bad)} corrections saved for {lang}; rebuild the window to use them")
    for b in bad:
        print("  skipped,", b)


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in ("export", "import"):
        raise SystemExit("usage: ./formlit i18n export LANG FILE.csv | ./formlit i18n import LANG FILE.csv")
    (export if sys.argv[1] == "export" else load)(sys.argv[2], sys.argv[3])
