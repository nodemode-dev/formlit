import random
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.develop.output import to_u8
from app.output import export, layout as layout_mod, pages

SIZES = {"480p": (854, 480), "720p": (1280, 720), "1080p": (1920, 1080), "4k": (3840, 2160)}
DEFAULTS: dict = {
    "fill": False, "background": "#0d0d0f", "margin": 0.05, "stroke": 0.0, "strokeColor": "#ffffff", "shadow": True,
    "duration": 4.0, "fade": 1.0, "panZoom": 0.0, "random": False, "repeat": True,
    "caption": {"on": False, "field": "title", "size": 9, "custom": "", "color": "#e8e8e8"},
    "identity": {"on": False, "text": "", "size": 18, "x": 0.5, "y": 0.06, "color": "#ffffff"},
    "intro": {"on": False, "text": "", "seconds": 3.0}, "ending": {"on": False, "text": "", "seconds": 3.0},
    "music": {"path": "", "fit": False, "balance": 50},
    "video": {"size": "1080p", "fps": 30, "quality": "high"},
}
TEMPLATES = [
    {"id": "default", "name": "Default", "settings": {}},
    {"id": "widescreen", "name": "Widescreen Fill", "settings": {"fill": True, "margin": 0.0, "shadow": False}},
    {"id": "captions", "name": "Caption and Exposure", "settings": {"caption": {"on": True, "field": "exposure", "size": 9}, "margin": 0.08}},
    {"id": "gallery", "name": "Gallery White", "settings": {"background": "#f2f0ec", "margin": 0.09, "stroke": 2.0, "strokeColor": "#ffffff", "shadow": True,
                                                              "caption": {"on": True, "field": "title", "size": 9, "color": "#333333"}}},
    {"id": "kenburns", "name": "Pan and Zoom", "settings": {"fill": True, "margin": 0.0, "panZoom": 0.6, "shadow": False, "duration": 5.0, "fade": 1.5}},
]


def merged(s: dict | None) -> dict:
    out = layout_mod.deep_merge(DEFAULTS, s if isinstance(s, dict) else {})
    for key, lo, hi in (("duration", 0.5, 600.0), ("fade", 0.0, 30.0), ("panZoom", 0.0, 1.0)):
        try:
            out[key] = min(hi, max(lo, float(out.get(key, DEFAULTS[key]))))
        except (TypeError, ValueError):
            out[key] = DEFAULTS[key]
    return out


AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".oga", ".opus", ".aif", ".aiff"}


def tracks(s: dict) -> list[str]:
    m = s.get("music") or {}
    raw = [*(m.get("tracks") or []), *str(m.get("path") or "").splitlines()]
    out: list[str] = []
    for p in raw:
        p = str(Path(str(p).strip()).expanduser()) if str(p).strip() else ""
        if p and p not in out and Path(p).suffix.lower() in AUDIO_EXTS and Path(p).is_file():
            out.append(p)
    return out[:10]


def still_seconds(page_list: list[dict], s: dict, music: list[str]) -> float:
    duration, fade = float(s["duration"]), float(s["fade"])
    stills = sum(1 for p in page_list if not p.get("seconds"))
    if not music or not (s.get("music") or {}).get("fit") or not stills:
        return duration
    total = sum(_probe_seconds(m) for m in music)
    if total <= 0:
        return duration
    clip_secs = sum(float(p["seconds"]) for p in page_list if p.get("seconds"))
    return max(fade + 0.5, (total - clip_secs + fade * (len(page_list) - 1)) / stills)


def music_in(folder: str) -> list[dict]:
    p = Path(folder).expanduser()
    if not p.is_dir():
        raise RuntimeError(f"Not a folder: {folder}")
    files = sorted((f for f in p.iterdir() if f.is_file() and f.suffix.lower() in AUDIO_EXTS), key=lambda f: f.name.lower())
    return [{"path": str(f), "name": f.name, "seconds": round(_probe_seconds(str(f)), 2)} for f in files[:50]]


def gains(s: dict) -> tuple[float, float]:
    b = max(0.0, min(100.0, float((s.get("music") or {}).get("balance", 50))))
    return min(1.0, (100.0 - b) / 50.0), min(1.0, b / 50.0)


@lru_cache(maxsize=512)
def _has_audio(path: str) -> bool:
    if not shutil.which("ffprobe"):
        return False
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path], capture_output=True, text=True, timeout=20)
    return bool(r.stdout.strip())


def clips(ids: list[int]) -> dict[int, dict]:
    from app.engine import catalog as catalog_mod
    from app.engine.records import loads
    cat = catalog_mod.get()
    out: dict[int, dict] = {}
    for r in cat.rows(f"SELECT id, duration, develop FROM photos WHERE kind='video' AND id IN ({','.join('?' * len(ids))})", tuple(ids)) if ids else []:
        path = cat.photo_path(int(r["id"]))
        if path is None or not path.is_file():
            continue
        t = (loads(r["develop"], {}) or {}).get("video") or {}
        a, b, dur = float(t.get("trimStart") or 0), float(t.get("trimEnd") or 0), float(r["duration"] or 0) or _probe_seconds(str(path))
        end = b if b > a else dur
        if end - a > 0.2:
            out[int(r["id"])] = {"path": str(path), "start": round(a, 3), "len": round(end - a, 3), "audio": _has_audio(str(path))}
    return out


def order(ids: list[int], s: dict) -> list[int]:
    out = list(ids)
    if s.get("random"):
        random.Random(len(out)).shuffle(out)
    return out


def page_layout(ids: list[int], aspects: dict[int, float], s: dict, for_pdf: bool = True, clip_info: dict[int, dict] | None = None) -> dict:
    fw, fh = SIZES.get((s.get("video") or {}).get("size", "1080p"), SIZES["1080p"])
    pw, ph = 10.0, 10.0 * fh / fw
    m = float(s.get("margin", 0.05)) * pw
    cell = {"x": m, "y": m, "w": pw - 2 * m, "h": ph - 2 * m}
    out_pages = []
    n = 0
    if s["intro"].get("on") and s["intro"].get("text"):
        n += 1
        out_pages.append({"cells": [], "texts": [{"x": 0.5, "y": ph / 2 - 0.2, "w": pw - 1, "h": 1, "text": s["intro"]["text"], "title": True}], "number": n, "cover": True})
    for pid in order(ids, s):
        n += 1
        item = layout_mod.place(cell, aspects.get(pid), bool(s.get("fill")), False)
        item["photo"] = pid
        page = {"cells": [item], "texts": [], "number": n, "cover": True}
        if clip_info and pid in clip_info:
            c = clip_info[pid]
            page.update(clip={"start": c["start"], "len": c["len"], "audio": c["audio"]}, seconds=c["len"])
        out_pages.append(page)
    if s["ending"].get("on") and s["ending"].get("text"):
        n += 1
        out_pages.append({"cells": [], "texts": [{"x": 0.5, "y": ph / 2 - 0.2, "w": pw - 1, "h": 1, "text": s["ending"]["text"], "title": True}], "number": n, "cover": True})
    cap = dict(s.get("caption") or {})
    settings = {"background": s.get("background"), "stroke": s.get("stroke", 0), "strokeColor": s.get("strokeColor"), "identity": s.get("identity"), "caption": cap,
                "textColor": cap.get("color", "#e8e8e8"), "titleSize": 30, "textSize": 14,
                "job": {"ppi": fw / pw if not for_pdf else 150, "space": "srgb", "quality": 90, "sharpen": {"on": True, "for": "screen", "amount": "standard"}}}
    return {"page": {"w": pw, "h": ph}, "pages": out_pages, "settings": settings}


def _probe_seconds(path: str) -> float:
    if not shutil.which("ffprobe"):
        return 0.0
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", path], capture_output=True, text=True, timeout=20)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _text_layer(W: int, H: int, items: list[dict], ppi: float) -> tuple[np.ndarray, np.ndarray] | None:
    if not items:
        return None
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for t in items:
        font = ImageFont.load_default(size=max(8, round(t["size"] / 72 * ppi)))
        col = pages._hex(t["color"]) + (255,)
        d.text((t["x"] * ppi, t["y"] * ppi), t["text"], font=font, fill=col, anchor="ms" if t["align"] == "center" else "ls")
    a = np.asarray(im, np.float32) / 255.0
    return a[..., :3], a[..., 3:4]


class Clip:
    def __init__(self, c: dict, w: int, h: int, fps: int, pid: int):
        from app.develop import render as render_mod
        from app.engine import catalog as catalog_mod
        from app.engine.records import loads
        self.w, self.h = max(2, w // 2 * 2), max(2, h // 2 * 2)
        dev = loads(catalog_mod.get().scalar("SELECT develop FROM photos WHERE id=?", (pid,)), {}) or {}
        self.dev = {k: v for k, v in dev.items() if k not in export.VIDEO_SKIP}
        self.render = render_mod
        self.proc = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{c['start']:.3f}", "-t", f"{c['len']:.3f}", "-i", c["path"], "-an",
                                      "-vf", f"scale={self.w}:{self.h}:flags=area,fps={fps}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        self.k = -1
        self.last = np.zeros((self.h, self.w, 3), np.float32)

    def frame(self, k: int) -> np.ndarray:
        from app.services import decode
        while self.k < k and self.proc.stdout is not None:
            buf = self.proc.stdout.read(self.w * self.h * 3)
            if len(buf) < self.w * self.h * 3:
                self.close()
                break
            self.k += 1
            if self.k == k:
                f = np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 3).astype(np.float32) / 255.0
                if self.dev:
                    lin = (decode.srgb_to_linear(f).reshape(-1, 3) @ decode.SRGB_TO_2020.T).reshape(f.shape).astype(np.float32)
                    info = {"raw": False, "asShotTemp": 6500.0, "asShotTint": 0.0, "relativeWb": True, "fullWidth": self.w, "fullHeight": self.h}
                    f = self.render.render(lin, info, self.dev, size=(self.w, self.h), space="srgb")
                self.last = f
        return self.last

    def close(self) -> None:
        if self.proc.stdout is not None:
            self.proc.stdout.close()
            self.proc.stdout = None
            self.proc.kill()
            self.proc.wait()


class Slide:
    def __init__(self, lay: dict, page: dict, W: int, H: int, s: dict, total: int, clip: dict | None = None, fps: int = 30):
        self.W, self.H = W, H
        ppi = W / lay["page"]["w"]
        self.bg = np.array(pages._hex(s.get("background", "#000000")), np.float32) / 255.0
        self.zoom = float(s.get("panZoom", 0.0)) * 0.18 if clip is None else 0.0
        self.img = None
        self.clip: Clip | None = None
        self.D = 1
        self.rect = (0, 0, 0, 0)
        self.drift = (0.0, 0.0)
        cell = page["cells"][0] if page["cells"] else None
        if cell and cell.get("img"):
            img = cell["img"]
            z = 1.0 + self.zoom
            if clip is not None:
                self.clip = Clip(clip, round(img["w"] * ppi), round(img["h"] * ppi), fps, int(cell["photo"]))
                self.img = self.clip.last
            else:
                size = {"resize": True, "mode": "wh", "w": round(img["w"] * ppi * z), "h": round(img["h"] * ppi * z), "noEnlarge": False}
                arr = export.render_photo(int(cell["photo"]), size, "srgb")
                arr = export.sharpen(arr, {"on": True, "for": "screen", "amount": "low"}, 96)
                self.img = arr
            x0, y0 = max(cell["x"], img["x"]), max(cell["y"], img["y"])
            x1, y1 = min(cell["x"] + cell["w"], img["x"] + img["w"]), min(cell["y"] + cell["h"], img["y"] + img["h"])
            self.rect = (round(x0 * ppi), round(y0 * ppi), round((x1 - x0) * ppi), round((y1 - y0) * ppi))
            self.full = (img["w"] * ppi, img["h"] * ppi, (x0 - img["x"]) * ppi, (y0 - img["y"]) * ppi)
            rng = random.Random(int(cell["photo"]))
            self.drift = (rng.uniform(-1, 1), rng.uniform(-1, 1))
        self.base = np.empty((H, W, 3), np.float32)
        self.base[:] = self.bg
        if self.img is not None and s.get("shadow") and not s.get("fill"):
            x, y, w, h = self.rect
            sh = np.zeros((H, W), np.float32)
            off = max(2, W // 300)
            sh[max(0, y + off):y + h + off, max(0, x + off):x + w + off] = 0.55
            sh = cv2.GaussianBlur(sh, (0, 0), max(2.0, W / 160))
            self.base = self.base * (1 - sh[..., None])
        self.text = _text_layer(W, H, pages._overlays(page, lay, lay["settings"], total), ppi)
        self.stroke = (max(1, round(float(s.get("stroke") or 0) / 72 * ppi)), np.array(pages._hex(s.get("strokeColor", "#ffffff")), np.float32) / 255) if float(s.get("stroke") or 0) > 0 else None

    def frame(self, k: int) -> np.ndarray:
        t = k / max(1, self.D - 1)
        if self.clip is not None:
            self.img = self.clip.frame(k)
        out = self.base.copy()
        if self.img is not None:
            x, y, w, h = self.rect
            fw, fh, ox, oy = self.full
            Hs, Ws = self.img.shape[:2]
            if self.zoom > 0:
                z = 1.0 + self.zoom * ((1 - t) if self.drift[0] > 0 else t)
                big = Ws / fw
                ww, wh = w / z, h / z
                cx = ox + w / 2 + self.drift[0] * (w - ww) / 2 * (2 * t - 1)
                cy = oy + h / 2 + self.drift[1] * (h - wh) / 2 * (2 * t - 1)
                M = np.float32([[ww * big / w, 0, (cx - ww / 2) * big], [0, wh * big / h, (cy - wh / 2) * big]])
                crop = cv2.warpAffine(self.img, M, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT)
            else:
                sx, sy = Ws / fw, Hs / fh
                crop = self.img[int(oy * sy):int(oy * sy) + max(1, round(h * sy)), int(ox * sx):int(ox * sx) + max(1, round(w * sx))]
                if crop.shape[1] != w or crop.shape[0] != h:
                    crop = cv2.resize(crop, (w, h), interpolation=cv2.INTER_AREA)
            out[y:y + h, x:x + w] = crop[:min(h, self.H - y), :min(w, self.W - x)]
            if self.stroke:
                sp, col = self.stroke
                out[y:y + sp, x:x + w] = col
                out[y + h - sp:y + h, x:x + w] = col
                out[y:y + h, x:x + sp] = col
                out[y:y + h, x + w - sp:x + w] = col
        if self.text is not None:
            rgb, a = self.text
            out = out * (1 - a) + rgb * a
        return out


def write_video(ids: list[int], aspects: dict[int, float], settings: dict, path: Path, progress: Callable[..., Any] | None = None) -> Path:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("Video export needs ffmpeg on this computer")
    s = merged(settings)
    v = s["video"]
    W, H = SIZES.get(v.get("size", "1080p"), SIZES["1080p"])
    fps = int(v.get("fps", 30))
    info = clips(ids)
    lay = page_layout(ids, aspects, s, for_pdf=False, clip_info=info)
    n = len(lay["pages"])
    if n == 0:
        raise RuntimeError("The slideshow has no slides")
    music = tracks(s)
    duration, fade = still_seconds(lay["pages"], s, music), float(s["fade"])
    lens = [max(2, round(float(p.get("seconds") or duration) * fps)) for p in lay["pages"]]
    F = max(0, round(fade * fps))
    xf = [min(F, lens[i] // 2, lens[i + 1] // 2) for i in range(n - 1)] + [min(F, lens[-1] // 2)]
    starts, off = [], 0
    for i in range(n):
        starts.append(off)
        off += lens[i] - (xf[i] if i < n - 1 else 0)
    secs = off / fps
    vg, mg = gains(s)
    crf = {"max": "14", "high": "18", "medium": "22", "low": "27"}.get(v.get("quality", "high"), "18")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-"]
    parts: list[str] = []
    labels: list[str] = []
    idx = 1
    if music and mg > 0:
        for m in music:
            cmd += ["-i", m]
        chain = "".join(f"[{idx + j}:a]aresample=48000,aformat=channel_layouts=stereo[m{j}];" for j in range(len(music)))
        parts.append(chain + "".join(f"[m{j}]" for j in range(len(music))) + f"concat=n={len(music)}:v=0:a=1,volume={mg:.3f}[mus]")
        labels.append("[mus]")
        idx += len(music)
    if vg > 0:
        for i, p in enumerate(lay["pages"]):
            c = p.get("clip")
            pid = p["cells"][0]["photo"] if p.get("cells") else None
            if not c or not c.get("audio") or pid not in info:
                continue
            cmd += ["-ss", f"{c['start']:.3f}", "-t", f"{c['len']:.3f}", "-i", info[pid]["path"]]
            ms = round(starts[i] / fps * 1000)
            parts.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms},volume={vg:.3f}[c{idx}]")
            labels.append(f"[c{idx}]")
            idx += 1
    if labels:
        mix = f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0," if len(labels) > 1 else f"{labels[0]}anull,"
        parts.append(f"{mix}apad,atrim=0:{secs:.3f},afade=t=out:st={max(0.0, secs - 2.0):.3f}:d={min(2.0, secs):.3f}[aout]")
        cmd += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", crf, "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None

    def make(i: int) -> Slide:
        p = lay["pages"][i]
        pid = p["cells"][0]["photo"] if p.get("cells") else None
        sl = Slide(lay, p, W, H, s, n, info.get(pid) if p.get("clip") else None, fps)
        sl.D = lens[i]
        return sl

    cur = nxt = None
    try:
        cur = make(0)
        bg = cur.base * 0 + cur.bg
        fin = min(F, lens[0] // 2)
        for i in range(n):
            nxt = make(i + 1) if i + 1 < n else None
            D, X = lens[i], xf[i]
            for t in range(xf[i - 1] if i > 0 else 0, D):
                f = cur.frame(t)
                if i == 0 and t < fin:
                    k = (t + 1) / (fin + 1)
                    f = bg * (1 - k) + f * k
                if X and t >= D - X:
                    k = (t - (D - X) + 1) / (X + 1)
                    other = nxt.frame(t - (D - X)) if nxt is not None else bg
                    f = f * (1 - k) + other * k
                proc.stdin.write(to_u8(f).tobytes())
            if cur.clip is not None:
                cur.clip.close()
            cur = nxt if nxt is not None else cur
            if progress is not None:
                if getattr(progress, "cancelled", False):
                    break
                progress(i + 1, n, f"Slide {i + 1} of {n}")
    finally:
        for sl in (cur, nxt):
            if sl is not None and sl.clip is not None:
                sl.clip.close()
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
        code = proc.wait()
    if code:
        raise RuntimeError(err.strip() or "ffmpeg failed")
    return path
