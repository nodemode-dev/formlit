import html
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

NS = {
    "x": "adobe:ns:meta/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "xmp": "http://ns.adobe.com/xap/1.0/",
    "xmpRights": "http://ns.adobe.com/xap/1.0/rights/",
    "photoshop": "http://ns.adobe.com/photoshop/1.0/",
    "Iptc4xmpCore": "http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/",
    "Iptc4xmpExt": "http://iptc.org/std/Iptc4xmpExt/2008-02-29/",
    "lr": "http://ns.adobe.com/lightroom/1.0/",
    "exif": "http://ns.adobe.com/exif/1.0/",
    "tiff": "http://ns.adobe.com/tiff/1.0/",
    "crs": "http://ns.adobe.com/camera-raw-settings/1.0/",
    "fl": "https://nodemode.ai/ns/formlit/1.0/",
}
for _p, _u in NS.items():
    ET.register_namespace(_p, _u)

META_FIELDS = ["title", "caption", "headline", "altText", "extendedDescription", "creator", "creatorJob", "creatorAddress", "creatorCity",
               "creatorState", "creatorCountry", "creatorEmail", "creatorPhone", "creatorUrl", "copyright", "copyrightStatus", "rightsUsage",
               "copyrightUrl", "location", "city", "state", "country", "isoCountryCode", "sublocation", "jobId", "instructions", "credit",
               "source", "intellectualGenre", "scene", "subjectCode", "event", "personShown"]
SIMPLE = {"headline": "photoshop:Headline", "city": "photoshop:City", "state": "photoshop:State", "country": "photoshop:Country",
          "isoCountryCode": "Iptc4xmpCore:CountryCode", "sublocation": "Iptc4xmpCore:Location", "instructions": "photoshop:Instructions",
          "jobId": "photoshop:TransmissionReference", "credit": "photoshop:Credit", "source": "photoshop:Source", "creatorJob": "photoshop:AuthorsPosition",
          "intellectualGenre": "Iptc4xmpCore:IntellectualGenre", "copyrightUrl": "xmpRights:WebStatement"}
ALT = {"title": "dc:title", "caption": "dc:description", "copyright": "dc:rights", "rightsUsage": "xmpRights:UsageTerms",
       "altText": "Iptc4xmpCore:AltTextAccessibility", "extendedDescription": "Iptc4xmpCore:ExtDescrAccessibility", "event": "Iptc4xmpExt:Event"}
BAG = {"scene": "Iptc4xmpCore:Scene", "subjectCode": "Iptc4xmpCore:SubjectCode", "personShown": "Iptc4xmpExt:PersonInImage"}
CONTACT = {"creatorAddress": "CiAdrExtadr", "creatorCity": "CiAdrCity", "creatorState": "CiAdrRegion", "creatorCountry": "CiAdrCtry",
           "creatorEmail": "CiEmailWork", "creatorPhone": "CiTelWork", "creatorUrl": "CiUrlWork"}


def _num(v: Any) -> float | None:
    try:
        if hasattr(v, "values"):
            v = v.values
        if isinstance(v, (list, tuple)):
            v = v[0] if v else None
        if v is None:
            return None
        if hasattr(v, "num") and hasattr(v, "den"):
            return float(v.num) / float(v.den) if v.den else None
        return float(Fraction(str(v)))
    except (ValueError, ZeroDivisionError, TypeError):
        return None


def _text(v: Any) -> str:
    s = str(getattr(v, "printable", v) or "").strip().strip("\x00")
    return re.sub(r"\s+", " ", s)


def _gps(tags: dict, key: str, ref: str) -> float | None:
    v = tags.get(f"GPS {key}")
    if v is None:
        return None
    try:
        d, m, s = [float(x.num) / float(x.den) if x.den else 0.0 for x in v.values[:3]]
    except (AttributeError, ValueError, IndexError, TypeError):
        return None
    val = d + m / 60 + s / 3600
    if _text(tags.get(f"GPS {ref}", "")).upper() in ("S", "W"):
        val = -val
    return val


def _date(s: str, offset: str = "") -> str | None:
    s = s.strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y:%m:%d"):
        try:
            dt = datetime.strptime(s[:19], fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%S") + (offset if re.fullmatch(r"[+-]\d\d:\d\d", offset or "") else "")
        except ValueError:
            continue
    return None


def read_exif(path: Path) -> dict:
    out: dict[str, Any] = {}
    try:
        import exifread
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=False, debug=False)
    except Exception:
        tags = {}
    if not tags:
        return out
    make = _text(tags.get("Image Make", ""))
    model = _text(tags.get("Image Model", ""))
    if model and make and not model.lower().startswith(make.split(" ")[0].lower()):
        out["camera"] = f"{make.split(' ')[0].title() if make.isupper() else make} {model}".strip()
    else:
        out["camera"] = model or make
    out["make"], out["model"] = make, model
    out["lens"] = _text(tags.get("EXIF LensModel", "") or tags.get("Image LensModel", "") or tags.get("MakerNote LensModel", "") or tags.get("EXIF LensSpecification", ""))
    out["focal"] = _num(tags.get("EXIF FocalLength") or tags.get("Image FocalLength"))
    out["focal35"] = _num(tags.get("EXIF FocalLengthIn35mmFilm"))
    out["aperture"] = _num(tags.get("EXIF FNumber") or tags.get("Image FNumber"))
    out["shutter"] = _num(tags.get("EXIF ExposureTime") or tags.get("Image ExposureTime"))
    iso = tags.get("EXIF ISOSpeedRatings") or tags.get("EXIF PhotographicSensitivity") or tags.get("EXIF RecommendedExposureIndex") or tags.get("Image ISOSpeedRatings")
    out["iso"] = int(_num(iso)) if _num(iso) else None
    out["bias"] = _num(tags.get("EXIF ExposureBiasValue"))
    fl = _num(tags.get("EXIF Flash"))
    out["flash"] = int(fl) & 1 if fl is not None else None
    out["exposureProgram"] = _text(tags.get("EXIF ExposureProgram", ""))
    out["meteringMode"] = _text(tags.get("EXIF MeteringMode", ""))
    out["whiteBalance"] = _text(tags.get("EXIF WhiteBalance", ""))
    out["software"] = _text(tags.get("Image Software", ""))
    out["artist"] = _text(tags.get("Image Artist", ""))
    out["copyright"] = _text(tags.get("Image Copyright", ""))
    out["serial"] = _text(tags.get("EXIF BodySerialNumber", ""))
    o = _num(tags.get("Image Orientation"))
    out["orientation"] = int(o) if o else 1
    dt = _text(tags.get("EXIF DateTimeOriginal", "") or tags.get("Image DateTime", ""))
    off = _text(tags.get("EXIF OffsetTimeOriginal", ""))
    out["captureTime"] = _date(dt, off) if dt else None
    sub = _text(tags.get("EXIF SubSecTimeOriginal", ""))
    if sub.isdigit():
        out["subsec"] = sub
    out["gpsLat"] = _gps(tags, "GPSLatitude", "GPSLatitudeRef")
    out["gpsLon"] = _gps(tags, "GPSLongitude", "GPSLongitudeRef")
    alt = _num(tags.get("GPS GPSAltitude"))
    if alt is not None and _num(tags.get("GPS GPSAltitudeRef")) == 1:
        alt = -alt
    out["gpsAlt"] = alt
    out["gpsDir"] = _num(tags.get("GPS GPSImgDirection"))
    full = {}
    for k, v in tags.items():
        if k in ("JPEGThumbnail", "TIFFThumbnail") or k.startswith("MakerNote") or k.startswith("Thumbnail"):
            continue
        t = _text(v)
        if t and len(t) < 300:
            full[k] = t
    out["all"] = full
    return {k: v for k, v in out.items() if v not in (None, "")}


def _xmp_packet(data: bytes) -> str | None:
    i = data.find(b"<x:xmpmeta")
    if i < 0:
        i = data.find(b"<rdf:RDF")
    if i < 0:
        return None
    j = data.find(b"</x:xmpmeta>", i)
    k = len(b"</x:xmpmeta>")
    if j < 0:
        j = data.find(b"</rdf:RDF>", i)
        k = len(b"</rdf:RDF>")
    if j < 0:
        return None
    return data[i:j + k].decode("utf-8", errors="replace")


def embedded_xmp(path: Path) -> str | None:
    if path.suffix.lower() in (".tif", ".tiff", ".dng"):
        from app.services import xmpembed
        found = xmpembed.read_tiff(path)
        if found:
            return _xmp_packet(found.encode("utf-8")) or found
    try:
        with open(path, "rb") as f:
            data = f.read(4 * 1024 * 1024)
    except OSError:
        return None
    return _xmp_packet(data)


def sidecar_path(path: Path) -> Path:
    return path.with_suffix(".xmp")


def _q(prefix: str, name: str) -> str:
    return f"{{{NS[prefix]}}}{name}"


def _alt(el: ET.Element | None) -> str | None:
    if el is None:
        return None
    li = el.find(f".//{_q('rdf', 'li')}")
    return (li.text or "").strip() if li is not None else (el.text or "").strip() or None


def _bag(el: ET.Element | None) -> list[str]:
    if el is None:
        return []
    return [(li.text or "").strip() for li in el.iter(_q("rdf", "li")) if (li.text or "").strip()]


def _clark(qname: str) -> str:
    prefix, name = qname.split(":")
    return _q(prefix, name)


_SIMPLE_R = {_clark(v): k for k, v in SIMPLE.items()}
_ALT_R = {_clark(v): k for k, v in ALT.items()}
_BAG_R = {_clark(v): k for k, v in BAG.items()}
_CONTACT_R = {_q("Iptc4xmpCore", v): k for k, v in CONTACT.items()}


def parse_xmp(text: str) -> dict:
    out: dict[str, Any] = {}
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return out
    meta: dict[str, Any] = {}
    crs: dict[str, str] = {}
    for desc in root.iter(_q("rdf", "Description")):
        for k, v in desc.attrib.items():
            if k.startswith("{" + NS["crs"]):
                crs[k.split("}")[1]] = v
            elif k == _q("xmp", "Rating"):
                try:
                    out["rating"] = max(-1, min(5, int(float(v))))
                except ValueError:
                    pass
            elif k == _q("xmp", "Label"):
                out["label"] = v
            elif k in _SIMPLE_R:
                meta[_SIMPLE_R[k]] = v
            elif k == _q("xmpRights", "Marked"):
                meta["copyrightStatus"] = "Copyrighted" if v.strip().lower() == "true" else "Public Domain"
            elif k == _q("photoshop", "DateCreated") or k == _q("exif", "DateTimeOriginal"):
                out.setdefault("captureTime", v[:19])
            elif k == _q("fl", "develop"):
                out["develop"] = html.unescape(v)
        for child in desc:
            tag = child.tag
            if tag in _ALT_R:
                meta[_ALT_R[tag]] = _alt(child)
            elif tag in _BAG_R:
                meta[_BAG_R[tag]] = ", ".join(_bag(child))
            elif tag in _SIMPLE_R:
                meta[_SIMPLE_R[tag]] = (child.text or "").strip()
            elif tag == _q("xmpRights", "Marked"):
                meta["copyrightStatus"] = "Copyrighted" if (child.text or "").strip().lower() == "true" else "Public Domain"
            elif tag == _q("Iptc4xmpCore", "CreatorContactInfo"):
                for kk, vv in child.attrib.items():
                    if kk in _CONTACT_R:
                        meta[_CONTACT_R[kk]] = vv
                for sub in child.iter():
                    if sub.tag in _CONTACT_R:
                        meta[_CONTACT_R[sub.tag]] = (sub.text or "").strip()
            elif tag == _q("dc", "creator"):
                c = _bag(child)
                if c:
                    meta["creator"] = ", ".join(c)
            elif tag == _q("dc", "subject"):
                out.setdefault("keywords", _bag(child))
            elif tag == _q("lr", "hierarchicalSubject"):
                out["keywords"] = _bag(child)
            elif tag == _q("xmp", "Rating"):
                try:
                    out["rating"] = int(float(child.text or 0))
                except ValueError:
                    pass
            elif tag == _q("xmp", "Label"):
                out["label"] = (child.text or "").strip()
            elif tag == _q("fl", "develop"):
                out["develop"] = (child.text or "").strip()
            elif tag.startswith("{" + NS["crs"]):
                name = tag.split("}")[1]
                if len(child) == 0:
                    crs[name] = (child.text or "").strip()
                else:
                    crs[name] = "|".join(_bag(child))
    if meta:
        out["meta"] = {k: v for k, v in meta.items() if v}
    if crs:
        out["crs"] = crs
    return out


def read_xmp(path: Path) -> dict:
    side = sidecar_path(path)
    text = None
    if side.is_file():
        try:
            text = side.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = None
    if text is None:
        text = embedded_xmp(path)
    return parse_xmp(text) if text else {}


def _esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def build_xmp(record: dict) -> str:
    meta = record.get("meta", {}) or {}
    attrs = [f'xmp:Rating="{int(record.get("rating", 0))}"', f'xmp:MetadataDate="{time.strftime("%Y-%m-%dT%H:%M:%S")}"', 'xmp:CreatorTool="formlit"']
    if record.get("label"):
        attrs.append(f'xmp:Label="{_esc(record["label"].title())}"')
    meta = {**meta, "sublocation": meta.get("sublocation") or meta.get("location") or ""}
    for key, tag in SIMPLE.items():
        if meta.get(key):
            attrs.append(f'{tag}="{_esc(meta[key])}"')
    status = str(meta.get("copyrightStatus") or "").strip().lower()
    if status in ("copyrighted", "public domain"):
        attrs.append(f'xmpRights:Marked="{"True" if status == "copyrighted" else "False"}"')
    if record.get("captureTime"):
        attrs.append(f'photoshop:DateCreated="{_esc(record["captureTime"])}"')
    if record.get("develop"):
        attrs.append(f'fl:develop="{_esc(record["develop"])}"')
        try:
            from app.services import xmp_presets
            dev = json.loads(record["develop"]) if isinstance(record["develop"], str) else record["develop"]
            attrs.extend(f'crs:{k}="{_esc(v)}"' for k, v in xmp_presets.to_crs(dev or {}).items())
        except (ValueError, TypeError):
            pass
    children = []
    for key, tag in ALT.items():
        if meta.get(key):
            children.append(f'<{tag}><rdf:Alt><rdf:li xml:lang="x-default">{_esc(meta[key])}</rdf:li></rdf:Alt></{tag}>')
    for key, tag in BAG.items():
        items = [s.strip() for s in str(meta.get(key) or "").split(",") if s.strip()]
        if items:
            children.append(f"<{tag}><rdf:Bag>" + "".join(f"<rdf:li>{_esc(s)}</rdf:li>" for s in items) + f"</rdf:Bag></{tag}>")
    contact = "".join(f"<Iptc4xmpCore:{tag}>{_esc(meta[key])}</Iptc4xmpCore:{tag}>" for key, tag in CONTACT.items() if meta.get(key))
    if contact:
        children.append(f'<Iptc4xmpCore:CreatorContactInfo rdf:parseType="Resource">{contact}</Iptc4xmpCore:CreatorContactInfo>')
    if meta.get("creator"):
        children.append(f'<dc:creator><rdf:Seq><rdf:li>{_esc(meta["creator"])}</rdf:li></rdf:Seq></dc:creator>')
    kws = record.get("keywords") or []
    if kws:
        leaves = sorted({k.split("|")[-1] for k in kws})
        children.append("<dc:subject><rdf:Bag>" + "".join(f"<rdf:li>{_esc(k)}</rdf:li>" for k in leaves) + "</rdf:Bag></dc:subject>")
        children.append("<lr:hierarchicalSubject><rdf:Bag>" + "".join(f"<rdf:li>{_esc(k)}</rdf:li>" for k in sorted(kws)) + "</rdf:Bag></lr:hierarchicalSubject>")
    ns = " ".join(f'xmlns:{p}="{u}"' for p, u in NS.items() if p not in ("x", "rdf"))
    return ('<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
            f'<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="formlit"><rdf:RDF xmlns:rdf="{NS["rdf"]}">'
            f'<rdf:Description rdf:about="" {ns} {" ".join(attrs)}>' + "".join(children) + "</rdf:Description></rdf:RDF></x:xmpmeta>\n"
            '<?xpacket end="w"?>\n')


def write_sidecar(path: Path, record: dict) -> Path:
    side = sidecar_path(path)
    tmp = side.with_suffix(".xmp.tmp")
    tmp.write_text(build_xmp(record), encoding="utf-8")
    tmp.replace(side)
    return side


def probe(path: Path) -> dict:
    from app.services import decode
    st = path.stat()
    info: dict[str, Any] = {"kind": decode.kind_of(path), "format": path.suffix.lower().lstrip("."), "size": st.st_size, "mtime": st.st_mtime}
    exif = read_exif(path) if info["kind"] != "video" else {}
    w, h = decode.dimensions(path)
    info.update(width=w, height=h)
    info["exif"] = exif
    xmp = read_xmp(path)
    info["xmp"] = xmp
    capture = exif.get("captureTime") or xmp.get("captureTime")
    if not capture:
        capture = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime))
    info["captureTime"] = capture
    if info["kind"] == "video":
        info["duration"] = video_duration(path)
    return info


def video_duration(path: Path) -> float | None:
    import json
    import subprocess
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)], capture_output=True, timeout=30)
        return float(json.loads(out.stdout or b"{}").get("format", {}).get("duration", 0)) or None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
