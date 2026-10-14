import copy
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.core import config
from app.develop import render as render_mod
from app.develop.geometry import Frame
from app.engine import catalog as catalog_mod
from app.engine.records import detail, loads
from app.output import encode
from app.output.export_library import LIBRARY as EXPORT_LIBRARY
from app.services import previews, rename

DEFAULTS: dict = {
    "destination": {"folder": "", "subfolder": "", "useSubfolder": False, "sameAsOriginal": False, "existing": "unique", "addToCatalog": False, "stack": False},
    "naming": {"rename": False, "template": "{name}", "custom": "", "start": 1, "case": "keep"},
    "file": {"format": "jpeg", "quality": 85, "limitKB": 0, "depth": 8, "compression": "none", "space": "srgb", "hdr": False, "hdrStops": "2"},
    "size": {"resize": False, "mode": "long", "w": 2048, "h": 2048, "value": 2048, "mp": 12.0, "percent": 50, "noEnlarge": True, "ppi": 240},
    "sharpen": {"on": False, "for": "screen", "amount": "standard"},
    "metadata": {"include": "all", "removePerson": True, "removeLocation": False},
    "watermark": {"on": False, "kind": "text", "text": "{copyright}", "image": "", "size": 0.035, "opacity": 0.7, "anchor": "br", "inset": 0.025, "color": "#ffffff", "shadow": True},
    "video": {"include": True, "format": "original", "quality": "high"},
    "post": {"action": "none", "app": ""},
}
BUILTIN = [
    {"id": "builtin.web", "name": "JPEG for Web (2048 px)", "settings": {"file": {"format": "jpeg", "quality": 82, "space": "srgb"}, "size": {"resize": True, "mode": "long", "value": 2048},
                                                                         "sharpen": {"on": True, "for": "screen", "amount": "standard"}, "metadata": {"include": "copyright"}}},
    {"id": "builtin.full", "name": "Full Size JPEG", "settings": {"file": {"format": "jpeg", "quality": 92, "space": "srgb"}, "metadata": {"include": "all"}}},
    {"id": "builtin.email", "name": "For Email (1200 px)", "settings": {"file": {"format": "jpeg", "quality": 75, "space": "srgb"}, "size": {"resize": True, "mode": "long", "value": 1200},
                                                                       "sharpen": {"on": True, "for": "screen", "amount": "low"}, "metadata": {"include": "copyright"}}},
    {"id": "builtin.tiff", "name": "16-bit TIFF, ProPhoto RGB", "settings": {"file": {"format": "tiff", "depth": 16, "compression": "zip", "space": "prophoto"}, "metadata": {"include": "all"}}},
    {"id": "builtin.print", "name": "Print, 300 ppi Adobe RGB", "settings": {"file": {"format": "tiff", "depth": 16, "compression": "zip", "space": "adobergb"}, "size": {"ppi": 300},
                                                                            "sharpen": {"on": True, "for": "matte", "amount": "standard"}}},
    {"id": "builtin.original", "name": "Original Files", "settings": {"file": {"format": "original"}}},
    {"id": "builtin.dng", "name": "DNG with Edits", "settings": {"file": {"format": "dng"}}},
    {"id": "builtin.hdr", "name": "Ultra HDR JPEG (gain map)", "settings": {"file": {"format": "jpeg", "quality": 90, "space": "srgb", "hdr": True, "hdrStops": "2"},
                                                                     "size": {"resize": True, "mode": "long", "value": 3840}}},
] + EXPORT_LIBRARY
SHARPEN = {"screen": (0.6, {"low": 0.35, "standard": 0.6, "high": 0.9}), "matte": (1.0, {"low": 0.55, "standard": 0.85, "high": 1.25}),
           "glossy": (0.8, {"low": 0.4, "standard": 0.65, "high": 1.0})}
ANCHORS = {"tl": (0, 0), "t": (0.5, 0), "tr": (1, 0), "l": (0, 0.5), "c": (0.5, 0.5), "r": (1, 0.5), "bl": (0, 1), "b": (0.5, 1), "br": (1, 1)}


def merged(settings: dict | None) -> dict:
    out = copy.deepcopy(DEFAULTS)
    for k, v in (settings or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    if not out["destination"]["folder"]:
        from app.engine.cmd_sessions import output_folder
        out["destination"]["folder"] = str(output_folder() or config.exports_dir())
    return out


def presets_dir() -> Path:
    p = config.presets_dir() / "Export"
    p.mkdir(parents=True, exist_ok=True)
    return p


def list_presets() -> list[dict]:
    out = [{"group": "General", **p, "builtin": True} for p in BUILTIN]
    for f in sorted(presets_dir().glob("*.json")):
        try:
            d = json.loads(f.read_text())
            out.append({"id": f"user.{f.stem}", "name": d.get("name", f.stem), "settings": d.get("settings", {}), "builtin": False})
        except (OSError, ValueError):
            continue
    return out


def find_preset(pid: str) -> dict | None:
    return next((p for p in list_presets() if p["id"] == pid), None)


def save_preset(name: str, settings: dict) -> dict:
    stem = rename.safe(name).replace(" ", "-").lower()
    (presets_dir() / f"{stem}.json").write_text(json.dumps({"name": name, "settings": settings}, indent=1))
    return {"id": f"user.{stem}", "name": name}


def delete_preset(pid: str) -> bool:
    if not any(p["id"] == pid and not p["builtin"] for p in list_presets()):
        return False
    f = presets_dir() / f"{str(pid)[5:]}.json"
    if f.is_file():
        f.unlink()
        return True
    return False


def scale_for(nw: float, nh: float, size: dict) -> float:
    if not size.get("resize"):
        return 1.0
    mode = size.get("mode", "long")
    long_, short_ = max(nw, nh), min(nw, nh)
    if mode == "long":
        s = float(size.get("value", 2048)) / long_
    elif mode == "short":
        s = float(size.get("value", 2048)) / short_
    elif mode == "wh":
        s = min(float(size.get("w", 2048)) / nw, float(size.get("h", 2048)) / nh)
    elif mode == "dims":
        a, b = float(size.get("w", 2048)), float(size.get("h", 2048))
        s = min(max(a, b) / long_, min(a, b) / short_)
    elif mode == "mp":
        s = (float(size.get("mp", 12)) * 1e6 / max(1.0, nw * nh)) ** 0.5
    elif mode == "percent":
        s = float(size.get("percent", 100)) / 100.0
    else:
        s = 1.0
    return min(s, 1.0) if size.get("noEnlarge", True) else s


def render_photo(pid: int, size: dict, space: str, dev: dict | None = None) -> np.ndarray:
    cat = catalog_mod.get()
    if dev is None:
        dev = loads(cat.scalar("SELECT develop FROM photos WHERE id=?", (pid,)), {})
    from app.engine.cmd_ai import ensure_masks
    try:
        ensure_masks(pid, dev)
    except Exception:
        pass
    eff = render_mod.effective(dev)
    pimg, pinfo = previews.source(pid)
    ph, pw = pimg.shape[:2]
    full_long = max(int(pinfo.get("fullWidth") or pw), int(pinfo.get("fullHeight") or ph))
    ratio = max(1.0, full_long / max(pw, ph))
    nw, nh = Frame(pw, ph, eff, True).native_size()
    s = scale_for(nw * ratio, nh * ratio, size)
    tw, th = max(1, round(nw * ratio * s)), max(1, round(nh * ratio * s))
    if max(tw, th) <= max(nw, nh) * 1.001:
        return render_mod.render(pimg, pinfo, dev, size=(tw, th), space=space, photo_id=pid)
    img, info = previews.source(pid, None, full=True)
    return render_mod.render(img, info, dev, size=(tw, th), space=space, photo_id=pid, src_long=max(img.shape[:2]))


def sharpen(out: np.ndarray, opts: dict, ppi: int) -> np.ndarray:
    if not opts.get("on"):
        return out
    base, amounts = SHARPEN.get(opts.get("for", "screen"), SHARPEN["screen"])
    sigma = base if opts.get("for", "screen") == "screen" else base * max(0.5, ppi / 300.0)
    amt = amounts.get(opts.get("amount", "standard"), 0.6)
    y = out @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    blur = cv2.GaussianBlur(y, (0, 0), sigma)
    d = np.clip((y - blur) * amt, -0.25, 0.25)
    return np.clip(out + d[..., None], 0.0, 1.0)


def _tokens(text: str, rec: dict) -> str:
    meta = rec.get("meta") or {}
    year = (rec.get("captureTime") or "")[:4] or time.strftime("%Y")
    for k, v in {"copyright": meta.get("copyright") or "", "creator": meta.get("creator") or "", "title": meta.get("title") or "",
                 "name": Path(rec.get("fileName") or "").stem, "year": year, "caption": meta.get("caption") or ""}.items():
        text = text.replace("{" + k + "}", str(v))
    return text.strip()


def _hex(c: str) -> tuple[float, float, float]:
    c = c.lstrip("#")
    if len(c) != 6:
        return 1.0, 1.0, 1.0
    return tuple(int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def watermark(out: np.ndarray, wm: dict, rec: dict) -> np.ndarray:
    if not wm.get("on"):
        return out
    h, w = out.shape[:2]
    long_ = max(w, h)
    inset = int(float(wm.get("inset", 0.025)) * long_)
    opacity = float(wm.get("opacity", 0.7))
    if wm.get("kind") == "image" and wm.get("image") and Path(wm["image"]).is_file():
        src = Image.open(wm["image"]).convert("RGBA")
        tw = max(8, int(float(wm.get("size", 0.15)) * long_))
        th = max(1, round(src.height * tw / src.width))
        src = src.resize((tw, th), Image.Resampling.LANCZOS)
        rgba = np.asarray(src, np.float32) / 255.0
        color, alpha = rgba[..., :3], rgba[..., 3] * opacity
        shadow = None
    else:
        text = _tokens(str(wm.get("text", "")), rec)
        if not text:
            return out
        px = max(8, int(float(wm.get("size", 0.035)) * long_))
        font = ImageFont.load_default(size=px)
        x0, y0, x1, y1 = font.getbbox(text)
        tw, th = x1 - x0 + 4, y1 - y0 + 4
        mask = Image.new("L", (tw, th), 0)
        ImageDraw.Draw(mask).text((2 - x0, 2 - y0), text, font=font, fill=255)
        a = np.asarray(mask, np.float32) / 255.0
        color = np.broadcast_to(np.array(_hex(str(wm.get("color", "#ffffff"))), np.float32), (th, tw, 3))
        alpha = a * opacity
        shadow = cv2.GaussianBlur(a, (0, 0), max(1.0, px / 18)) * opacity * 0.55 if wm.get("shadow", True) else None
    ah, aw = alpha.shape[:2]
    fx, fy = ANCHORS.get(wm.get("anchor", "br"), (1, 1))
    x = int(round(inset + (w - aw - 2 * inset) * fx))
    y = int(round(inset + (h - ah - 2 * inset) * fy))
    x, y = max(0, min(w - aw, x)), max(0, min(h - ah, y))
    if aw > w or ah > h:
        return out
    region = out[y:y + ah, x:x + aw]
    if shadow is not None:
        off = max(1, ah // 24)
        sh = np.zeros_like(shadow)
        sh[off:, off:] = shadow[:-off, :-off]
        region = region * (1 - sh[..., None])
    out = out.copy()
    out[y:y + ah, x:x + aw] = region * (1 - alpha[..., None]) + color * alpha[..., None]
    return out


def target_name(rec: dict, s: dict, seq: int) -> str:
    n = s["naming"]
    base = rename.expand(n.get("template") or "{name}", rec, seq, n.get("custom", "")) if n.get("rename") else Path(rec["fileName"]).stem
    if rec.get("copyName") and not n.get("rename"):
        base = f"{base}-{rename.safe(rec['copyName'])}"
    case = n.get("case", "keep")
    return base.lower() if case == "lower" else base.upper() if case == "upper" else base


def folder_for(rec: dict, s: dict) -> Path:
    d = s["destination"]
    base = Path(rec["folderPath"]) if d.get("sameAsOriginal") else Path(d.get("folder") or config.exports_dir()).expanduser()
    if d.get("useSubfolder") and d.get("subfolder"):
        base = base / rename.expand(d["subfolder"], rec, 1)
    base.mkdir(parents=True, exist_ok=True)
    return base


def is_original(path: Path) -> bool:
    if not path.exists():
        return False
    cat = catalog_mod.get()
    rows = cat.rows("SELECT f.path AS folder, p.file_name AS name, p.sidecars AS sidecars FROM photos p JOIN folders f ON f.id=p.folder_id "
                    "WHERE lower(p.file_name)=lower(?) OR lower(p.file_name) LIKE lower(?) ESCAPE '\\'",
                    (path.name, path.stem.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + ".%"))
    for r in rows:
        own = Path(r["folder"]) / r["name"]
        ext = path.suffix.lower().lstrip(".")
        cands = [own] + ([own.with_suffix(path.suffix)] if ext in (loads(r["sidecars"], []) or []) or ext == "xmp" else [])
        for c in cands:
            try:
                if os.path.samefile(path, c):
                    return True
            except OSError:
                continue
    return False


def place(path: Path, existing: str) -> Path | None:
    if path.exists() and is_original(path):
        return None if existing == "skip" else rename.unique(path)
    if not path.exists() or existing == "overwrite":
        return path
    if existing == "skip":
        return None
    return rename.unique(path)


def _record(pid: int) -> dict:
    rec = detail(catalog_mod.get(), pid)
    if rec is None:
        raise FileNotFoundError(f"No photo with id {pid}")
    return rec


def _export_keywords() -> dict:
    cat = catalog_mod.get()
    rows = {int(r["id"]): r for r in cat.rows("SELECT id, name, parent_id, synonyms, export FROM keywords")}
    path: dict[int, str] = {}

    def full(kid: int) -> str:
        if kid not in path:
            r = rows[kid]
            up = r["parent_id"]
            path[kid] = (full(int(up)) + "|" if up is not None and int(up) in rows else "") + r["name"]
        return path[kid]
    extras: dict[str, list[str]] = {}
    for kid, r in rows.items():
        terms = list(loads(r["synonyms"], []))
        up = r["parent_id"]
        while up is not None and int(up) in rows:
            if int(rows[int(up)]["export"]):
                terms.append(rows[int(up)]["name"])
            up = rows[int(up)]["parent_id"]
        if terms:
            extras[full(kid)] = terms
    hidden = any(not int(r["export"]) for r in rows.values())
    return {"only": {full(k) for k, r in rows.items() if int(r["export"])} if hidden else None, "extras": extras}


def trim_args(rec: dict) -> list[str]:
    t = (rec.get("develop") or {}).get("video") or {}
    a, b = float(t.get("trimStart") or 0), float(t.get("trimEnd") or 0)
    out = ["-ss", f"{a:.3f}"] if a > 0 else []
    if b > a:
        out += ["-t", f"{b - a:.3f}"]
    return out


VIDEO_SKIP = ("video", "masks", "spots", "redEye", "lensBlur")


def _video_graded(src: Path, dev: dict, trim: list[str], out: Path, crf: str, cap: int) -> Path:
    from app.services import decode
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate", "-of", "json", str(src)],
                           capture_output=True, timeout=30)
    st = json.loads(probe.stdout or b"{}").get("streams", [{}])[0]
    w, h, rate = int(st.get("width", 0)), int(st.get("height", 0)), st.get("r_frame_rate", "30/1")
    if not w or not h:
        raise ValueError("ffprobe could not read the video size")
    info = {"raw": False, "asShotTemp": 6500.0, "asShotTint": 0.0, "relativeWb": True, "fullWidth": w, "fullHeight": h}
    eff = render_mod.effective(dev)
    fw, fh = Frame(w, h, eff, True).native_size()
    k = min(1.0, cap / max(fw, fh)) if cap else 1.0
    ow, oh = max(2, int(fw * k) // 2 * 2), max(2, int(fh * k) // 2 * 2)
    dec = subprocess.Popen(["ffmpeg", "-v", "error", *trim, "-i", str(src), "-f", "rawvideo", "-pix_fmt", "rgb48le", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ow}x{oh}", "-r", rate, "-i", "-", *trim, "-i", str(src),
                            "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-preset", "medium", "-crf", crf, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                            "-shortest", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    size = w * h * 6
    assert dec.stdout is not None and enc.stdin is not None
    try:
        while True:
            buf = dec.stdout.read(size)
            if len(buf) < size:
                break
            frame = decode.srgb_to_linear(np.frombuffer(buf, "<u2").reshape(h, w, 3).astype(np.float32) / 65535.0)
            lin = (frame.reshape(-1, 3) @ decode.SRGB_TO_2020.T).reshape(frame.shape).astype(np.float32)
            rgb = render_mod.render(lin, info, dev, size=(ow, oh), space="srgb")
            enc.stdin.write(render_mod.to_u8(rgb).tobytes())
    finally:
        enc.stdin.close()
        dec.stdout.close()
        dec.wait()
        enc.wait()
    if enc.returncode != 0 or not out.is_file():
        raise ValueError("ffmpeg could not encode the graded video")
    return out


def _video(rec: dict, s: dict, dest: Path) -> Path:
    v = s["video"]
    src = Path(rec["path"])
    trim = trim_args(rec)
    if not shutil.which("ffmpeg") or (v.get("format") == "original" and not trim):
        shutil.copy2(src, dest.with_suffix(src.suffix.lower()))
        return dest.with_suffix(src.suffix.lower())
    if v.get("format") == "original":
        out = dest.with_suffix(src.suffix.lower())
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *trim, "-i", str(src), "-c", "copy", "-map", "0", str(out)], check=True)
        return out
    out = dest.with_suffix(".mp4")
    crf = {"max": "16", "high": "20", "medium": "24", "low": "28"}.get(v.get("quality", "high"), "20")
    dev = {k: val for k, val in (rec.get("develop") or {}).items() if k not in VIDEO_SKIP}
    if dev:
        return _video_graded(src, dev, trim, out, crf, 1920 if v.get("quality") in ("medium", "low") else 0)
    scale = ["-vf", "scale='min(1920,iw)':-2"] if v.get("quality") in ("medium", "low") else []
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *trim, "-i", str(src), *scale, "-c:v", "libx264", "-preset", "medium", "-crf", crf,
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)], check=True)
    return out


def in_private_location(rec: dict) -> bool:
    lat, lon = rec.get("gpsLat"), rec.get("gpsLon")
    if lat is None or lon is None:
        return False
    for r in catalog_mod.get().rows("SELECT lat, lon, radius FROM locations WHERE private=1"):
        p1, p2 = np.radians(float(lat)), np.radians(float(r["lat"]))
        dl = np.radians(float(r["lon"]) - float(lon))
        a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
        if 2 * 6371.0088 * np.arcsin(min(1.0, float(np.sqrt(a)))) <= float(r["radius"]):
            return True
    return False


def export_one(pid: int, s: dict, seq: int, kw_filter: dict | None) -> Path | None:
    rec = _record(pid)
    f = s["file"]
    fmt = f.get("format", "jpeg")
    folder = folder_for(rec, s)
    stem = target_name(rec, s, seq)
    existing = s["destination"].get("existing", "unique")
    m = s["metadata"]
    meta_rec = {k: v for k, v in encode.filtered(rec, m.get("include", "all"), bool(m.get("removePerson")), bool(m.get("removeLocation")) or in_private_location(rec), kw_filter if kw_filter is not None else _export_keywords()).items() if k != "develop"}
    if rec.get("kind") == "video":
        if not s["video"].get("include", True):
            return None
        dest = place(folder / f"{stem}{Path(rec['fileName']).suffix.lower()}", existing)
        return None if dest is None else _video(rec, s, dest)
    if fmt == "original":
        src = Path(rec["path"])
        dest = place(folder / f"{stem}{src.suffix}", existing)
        if dest is None:
            return None
        shutil.copy2(src, dest)
        from app.services import metadata
        full = dict(meta_rec, develop=json.dumps(rec.get("develop") or {}, separators=(",", ":")))
        metadata.write_sidecar(dest, full)
        return dest
    if fmt == "dng":
        from app.ai import dng
        from app.services import metadata
        dest = place(folder / f"{stem}.dng", existing)
        if dest is None:
            return None
        src = Path(rec["path"])
        done = False
        if rec.get("kind") == "raw" and src.is_file():
            if src.suffix.lower() == ".dng":
                shutil.copy2(src, dest)
                done = True
            else:
                try:
                    done = dng.write_cfa_dng(src, dest, {**(rec.get("exif") or {}), "captureTime": rec.get("captureTime")})
                except Exception:
                    done = False
        if not done:
            img, info = previews.source(pid, None, full=True)
            make = meta_rec.get("make") or (rec.get("exif") or {}).get("make") or ""
            dng.write_linear_dng(dest, img, info, make, rec.get("camera") or "", rec.get("captureTime"))
        full = dict(meta_rec, develop=json.dumps(rec.get("develop") or {}, separators=(",", ":")), aspect=(rec.get("w") or 3) / max(1, rec.get("h") or 2))
        try:
            from app.services import xmpembed
            xmpembed.write(dest, metadata.build_xmp(full))
        except (OSError, ValueError):
            metadata.write_sidecar(dest, full)
        return dest
    ext = encode.FORMATS.get(fmt, encode.FORMATS["jpeg"])["ext"]
    dest = place(folder / f"{stem}.{ext}", existing)
    if dest is None:
        return None
    ppi = int(s["size"].get("ppi", 240))
    space = f.get("space", "srgb")
    from app.output import gainmap
    dev = rec.get("develop") or {}
    stops = gainmap.headroom(dev, float(f.get("hdrStops", 2)))
    if fmt == "jpeg" and f.get("hdr"):
        sdr, gain = gainmap.render_pair(pid, s["size"], dev, stops)
        sdr = watermark(sharpen(sdr, s["sharpen"], ppi), s["watermark"], rec)
        data = gainmap.ultrahdr(sdr, gain, int(f.get("quality", 85)), ppi, encode.exif_bytes(meta_rec, sdr.shape[1], sdr.shape[0], ppi))
        tmp = dest.with_name(dest.name + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, dest)
        return dest
    if f.get("hdr") and fmt in ("avif", "jxl", "tiff"):
        sdr, gain = gainmap.render_pair(pid, s["size"], dev, stops)
        sdr = watermark(sharpen(sdr, s["sharpen"], ppi), s["watermark"], rec)
        data = encode.encode_hdr(fmt, gainmap.hdr_linear(sdr, gain), int(f.get("quality", 85)), ppi, meta_rec)
        tmp = dest.with_name(dest.name + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, dest)
        return dest
    out = render_photo(pid, s["size"], "prophoto" if space.startswith("icc:") else space, gainmap.sdr_settings(dev) if gainmap.hdr_on(dev) else None)
    out = sharpen(out, s["sharpen"], ppi)
    out = watermark(out, s["watermark"], rec)
    if space.startswith("icc:"):
        from app.output import icc
        out = icc.convert(out, "prophoto", space[4:], f.get("intent", "relative"))
    data = encode.encode(out, fmt, space, int(f.get("quality", 85)), int(f.get("depth", 8)), ppi, meta_rec, f.get("compression", "none"), int(f.get("limitKB", 0)))
    tmp = dest.with_name(dest.name + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, dest)
    return dest


def reveal(path: Path) -> None:
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
    except OSError:
        return


def open_with(app: str, paths: list[Path]) -> bool:
    if not app or not paths:
        return False
    try:
        if sys.platform == "darwin" and app.endswith(".app"):
            subprocess.Popen(["open", "-a", app, *map(str, paths)])
        else:
            subprocess.Popen([app, *map(str, paths)])
        return True
    except OSError:
        return False


def run(pids: list[int], settings: dict, progress: Callable[..., Any] | None = None) -> dict:
    s = merged(settings)
    written: list[str] = []
    skipped: list[int] = []
    failed: list[dict] = []
    kw_filter = _export_keywords()
    start = int(s["naming"].get("start", 1))
    for i, pid in enumerate(pids):
        if progress is not None and getattr(progress, "cancelled", False):
            break
        try:
            p = export_one(pid, s, start + i, kw_filter)
            if p is None:
                skipped.append(pid)
            else:
                written.append(str(p))
        except Exception as exc:
            failed.append({"id": pid, "error": str(exc)})
        if progress is not None:
            progress(i + 1, len(pids), f"Exporting {i + 1} of {len(pids)}")
    return {"paths": written, "skipped": skipped, "failed": failed, "folder": str(Path(written[0]).parent) if written else s["destination"]["folder"], "settings": s}
