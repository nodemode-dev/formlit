import io
import json
import math
import re
import tarfile
import threading
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

from app import __version__
from app.core import config

TARBALL = "https://codeload.github.com/lensfun/lensfun/tar.gz/refs/heads/master"
RAW = "https://raw.githubusercontent.com/lensfun/lensfun/master/data/db/{name}.xml"
FILES = ["6x6", "actioncams", "compact-canon", "compact-casio", "compact-fujifilm", "compact-kodak", "compact-konica-minolta", "compact-leica",
         "compact-nikon", "compact-olympus", "compact-panasonic", "compact-pentax", "compact-ricoh", "compact-samsung", "compact-sigma", "compact-sony",
         "contax", "generic", "mil-canon", "mil-fujifilm", "mil-hasselblad", "mil-leica", "mil-nikon", "mil-olympus", "mil-panasonic", "mil-pentax",
         "mil-samsung", "mil-samyang", "mil-sigma", "mil-sony", "mil-tamron", "mil-tokina", "mil-zeiss", "misc", "rf-leica", "slr-canon",
         "slr-hasselblad", "slr-konica-minolta", "slr-leica", "slr-nikon", "slr-olympus", "slr-panasonic", "slr-pentax", "slr-ricoh", "slr-samsung",
         "slr-samyang", "slr-schneider", "slr-sigma", "slr-sony", "slr-tamron", "slr-tokina", "slr-vivitar", "slr-zeiss", "slr-ussr"]
ATTRIBUTION = "Lens data from the Lensfun database (lensfun.github.io), CC BY-SA 3.0"
_lock = threading.Lock()
_index: dict | None = None
_MOUNTS: dict[str, set[str]] = {}


def folder() -> Path:
    d = config.models_dir() / "lensfun"
    d.mkdir(parents=True, exist_ok=True)
    return d


def index_path() -> Path:
    return folder() / "index.json"


def available() -> bool:
    return index_path().is_file()


def _float(v: str | None, default: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else default
    except ValueError:
        return default


def _aspect(text: str | None) -> float:
    if not text:
        return 1.5
    if ":" in text:
        a, b = text.split(":", 1)
        return max(_float(a, 3), _float(b, 2)) / max(1e-6, min(_float(a, 3), _float(b, 2)))
    return _float(text, 1.5)


def _parse(xml: bytes) -> tuple[list[dict], list[dict]]:
    root = ET.fromstring(xml)
    cams, lenses = [], []
    for m in root.iter("mount"):
        name = m.findtext("name")
        if name:
            _MOUNTS.setdefault(name.strip(), set()).update(c.text.strip() for c in m.findall("compat") if c.text)
    for c in root.iter("camera"):
        model = next((m.text for m in c.findall("model") if not m.get("lang")), None)
        if model:
            cams.append({"maker": (c.findtext("maker") or "").strip(), "model": model.strip(), "mount": (c.findtext("mount") or "").strip(),
                         "crop": _float(c.findtext("cropfactor"), 1.0)})
    for ln in root.iter("lens"):
        model = next((m.text for m in ln.findall("model") if not m.get("lang")), None)
        cal = ln.find("calibration")
        if not model or cal is None:
            continue
        dist = [{"focal": _float(d.get("focal")), "model": d.get("model"), **{k: _float(d.get(k)) for k in ("a", "b", "c", "k1", "k2")}} for d in cal.findall("distortion")]
        tca = [{"focal": _float(t.get("focal")), "model": t.get("model"), **{k: _float(t.get(k), 1.0 if k in ("vr", "vb", "kr", "kb") else 0.0) for k in ("vr", "cr", "br", "vb", "cb", "bb", "kr", "kb")}}
               for t in cal.findall("tca")]
        vig = [{"focal": _float(v.get("focal")), "aperture": _float(v.get("aperture"), 8.0), "distance": _float(v.get("distance"), 1000.0),
                "k": [_float(v.get("k1")), _float(v.get("k2")), _float(v.get("k3"))]} for v in cal.findall("vignetting") if v.get("model", "pa") == "pa"]
        if not (dist or tca or vig):
            continue
        fv = ln.find("focal")
        lenses.append({"maker": (ln.findtext("maker") or "").strip(), "model": model.strip(), "mounts": [m.text.strip() for m in ln.findall("mount") if m.text],
                       "crop": _float(ln.findtext("cropfactor"), 1.0), "aspect": _aspect(ln.findtext("aspect-ratio")),
                       "fmin": _float(fv.get("min") or fv.get("value")) if fv is not None else 0.0, "fmax": _float(fv.get("max") or fv.get("value")) if fv is not None else 0.0,
                       "dist": dist, "tca": tca, "vig": vig})
    return cams, lenses


def download(progress=None) -> dict:
    blobs: dict[str, bytes] = {}
    headers = {"User-Agent": f"formlit/{__version__} (lens profile download)"}
    with httpx.Client(headers=headers, timeout=60, follow_redirects=True) as client:
        try:
            r = client.get(TARBALL)
            r.raise_for_status()
            with tarfile.open(fileobj=io.BytesIO(r.content), mode="r:gz") as tar:
                for m in tar.getmembers():
                    if re.search(r"/data/db/[^/]+\.xml$", m.name) and m.isfile():
                        f = tar.extractfile(m)
                        if f is not None:
                            blobs[Path(m.name).name] = f.read()
        except (httpx.HTTPError, tarfile.TarError):
            blobs = {}
        if not blobs:
            for i, name in enumerate(FILES):
                if progress is not None:
                    progress(i, len(FILES), f"Downloading lens profiles {i + 1} of {len(FILES)}")
                r = client.get(RAW.format(name=name))
                if r.status_code == 200:
                    blobs[f"{name}.xml"] = r.content
    if not blobs:
        raise RuntimeError("The lens profile database could not be downloaded")
    cams: list[dict] = []
    lenses: list[dict] = []
    for name, data in sorted(blobs.items()):
        (folder() / name).write_bytes(data)
        try:
            c, ln = _parse(data)
        except ET.ParseError:
            continue
        cams += c
        lenses += ln
    tmp = index_path().with_suffix(".tmp")
    mounts = {k: sorted(v) for k, v in _MOUNTS.items()}
    tmp.write_text(json.dumps({"cameras": cams, "lenses": lenses, "mounts": mounts, "attribution": ATTRIBUTION}), encoding="utf-8")
    tmp.replace(index_path())
    global _index
    with _lock:
        _index = None
    return {"cameras": len(cams), "lenses": len(lenses)}


def index() -> dict:
    global _index
    with _lock:
        if _index is None:
            _index = json.loads(index_path().read_text(encoding="utf-8")) if available() else {"cameras": [], "lenses": []}
        return _index


def _tokens(s: str) -> set[str]:
    s = s.lower().replace("f/", " ").replace("mm", " mm ")
    return {t for t in re.split(r"[^a-z0-9.\-]+", s) if t and t not in ("mm", "lens")}


def _focal_range(name: str) -> tuple[float, float] | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*mm", name.lower()) or re.search(r"(\d+(?:\.\d+)?)\s*mm", name.lower())
    if not m:
        return None
    a = float(m.group(1))
    b = float(m.group(2)) if m.lastindex and m.lastindex >= 2 else a
    return a, b


def camera(maker: str, model: str) -> dict | None:
    mk, md = maker.lower().strip(), model.lower().strip()
    best = None
    for c in index()["cameras"]:
        cm = c["model"].lower()
        if cm == md or cm == f"{mk} {md}" or md.endswith(cm) or cm.endswith(md):
            if best is None or len(c["model"]) > len(best["model"]):
                best = c
    return best


def makers() -> list[str]:
    return sorted({ln["maker"] for ln in index()["lenses"] if ln["maker"]}, key=str.lower)


def models(maker: str) -> list[str]:
    return sorted({ln["model"] for ln in index()["lenses"] if ln["maker"].lower() == maker.lower()}, key=str.lower)


def lens(model: str) -> dict | None:
    return next((ln for ln in index()["lenses"] if ln["model"] == model), None)


def match(lens_name: str, maker: str, model: str, focal: float | None) -> tuple[dict | None, float]:
    if not lens_name.strip():
        return None, 0.0
    cam = camera(maker, model)
    mounts = {cam["mount"], *index().get("mounts", {}).get(cam["mount"], [])} if cam else set()
    want = _tokens(lens_name)
    fr = _focal_range(lens_name)
    best, score = None, 0.0
    for ln in index()["lenses"]:
        if mounts and not mounts & set(ln["mounts"]):
            continue
        if focal and ln["fmin"] and not (ln["fmin"] - 0.5 <= focal <= (ln["fmax"] or ln["fmin"]) + 0.5):
            continue
        if fr and ln["fmin"] and (abs(ln["fmin"] - fr[0]) > 0.6 or abs((ln["fmax"] or ln["fmin"]) - fr[1]) > 0.6):
            continue
        have = _tokens(ln["model"]) | _tokens(ln["maker"])
        s = len(want & have) / max(1, len(want))
        if mounts and mounts & set(ln["mounts"]):
            s += 0.5
        if cam and ln["maker"].lower() == cam["maker"].lower():
            s += 0.25
        if cam and abs(ln["crop"] - cam["crop"]) < 0.05:
            s += 0.1
        if s > score:
            best, score = ln, s
    return best, score


def _between(items: list[dict], key: str, value: float) -> tuple[dict, dict, float]:
    items = sorted(items, key=lambda d: d[key])
    if value <= items[0][key]:
        return items[0], items[0], 0.0
    if value >= items[-1][key]:
        return items[-1], items[-1], 0.0
    for a, b in zip(items, items[1:]):
        if a[key] <= value <= b[key]:
            t = 0.0 if b[key] == a[key] else (value - a[key]) / (b[key] - a[key])
            return a, b, t
    return items[-1], items[-1], 0.0


def profile_for(ln: dict, focal: float, aperture: float | None, img_crop: float | None) -> dict:
    crop = img_crop or ln["crop"]
    out: dict = {"source": "lensfun", "lens": ln["model"], "maker": ln["maker"], "attribution": ATTRIBUTION,
                 "hugin": 2.0 * math.hypot(ln["aspect"], 1.0) * ln["crop"] / crop, "pa": 2.0 * ln["crop"] / crop}
    if ln["dist"]:
        same = [d for d in ln["dist"] if d["model"] == ln["dist"][0]["model"]]
        a, b, t = _between(same, "focal", focal)
        out["dist"] = {"model": a["model"], **{k: a[k] + (b[k] - a[k]) * t for k in ("a", "b", "c", "k1", "k2")}}
    if ln["tca"]:
        same = [d for d in ln["tca"] if d["model"] == ln["tca"][0]["model"]]
        a, b, t = _between(same, "focal", focal)
        out["tca"] = {"model": a["model"], **{k: a[k] + (b[k] - a[k]) * t for k in ("vr", "cr", "br", "vb", "cb", "bb", "kr", "kb")}}
    if ln["vig"]:
        far = max(v["distance"] for v in ln["vig"])
        pool = [v for v in ln["vig"] if v["distance"] == far]
        fa, fb, ft = _between(pool, "focal", focal)
        ks = []
        for fx in (fa["focal"], fb["focal"]):
            at = [v for v in pool if v["focal"] == fx]
            ap = aperture or min(v["aperture"] for v in at)
            for v in at:
                v["_inv"] = 1.0 / max(0.5, v["aperture"])
            a, b, t = _between(at, "_inv", 1.0 / max(0.5, ap))
            ks.append([a["k"][i] + (b["k"][i] - a["k"][i]) * t for i in range(3)])
        out["vig"] = [ks[0][i] + (ks[1][i] - ks[0][i]) * ft for i in range(3)]
    return out
