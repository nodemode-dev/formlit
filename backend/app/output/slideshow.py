import random
import shutil
import subprocess
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
    "music": {"path": "", "fit": False},
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
    return layout_mod.deep_merge(DEFAULTS, s)


def order(ids: list[int], s: dict) -> list[int]:
    out = list(ids)
    if s.get("random"):
        random.Random(len(out)).shuffle(out)
    return out


def page_layout(ids: list[int], aspects: dict[int, float], s: dict, for_pdf: bool = True) -> dict:
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
        out_pages.append({"cells": [item], "texts": [], "number": n, "cover": True})
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


class Slide:
    def __init__(self, lay: dict, page: dict, W: int, H: int, s: dict, total: int):
        self.W, self.H = W, H
        ppi = W / lay["page"]["w"]
        self.bg = np.array(pages._hex(s.get("background", "#000000")), np.float32) / 255.0
        self.zoom = float(s.get("panZoom", 0.0)) * 0.18
        self.img = None
        self.rect = (0, 0, 0, 0)
        self.drift = (0.0, 0.0)
        cell = page["cells"][0] if page["cells"] else None
        if cell and cell.get("img"):
            img = cell["img"]
            z = 1.0 + self.zoom
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

    def frame(self, t: float) -> np.ndarray:
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
    lay = page_layout(ids, aspects, s, for_pdf=False)
    n = len(lay["pages"])
    if n == 0:
        raise RuntimeError("The slideshow has no slides")
    music = (s.get("music") or {}).get("path") or ""
    duration, fade = float(s["duration"]), float(s["fade"])
    if music and (s.get("music") or {}).get("fit"):
        total = _probe_seconds(music)
        if total > 0:
            duration = max(fade + 0.5, (total + fade * (n - 1)) / n)
    D, F = max(1, round(duration * fps)), max(0, min(round(fade * fps), round(duration * fps) // 2))
    crf = {"max": "14", "high": "18", "medium": "22", "low": "27"}.get(v.get("quality", "high"), "18")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-"]
    if music and Path(music).is_file():
        cmd += ["-i", music, "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", crf, "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        cur = Slide(lay, lay["pages"][0], W, H, s, n)
        bg = cur.base * 0 + cur.bg
        for i in range(n):
            nxt = Slide(lay, lay["pages"][i + 1], W, H, s, n) if i + 1 < n else None
            start = F if i > 0 else 0
            for t in range(start, D):
                f = cur.frame(t / max(1, D - 1))
                if i == 0 and t < F:
                    k = (t + 1) / (F + 1)
                    f = bg * (1 - k) + f * k
                if t >= D - F:
                    k = (t - (D - F) + 1) / (F + 1)
                    other = nxt.frame((t - (D - F)) / max(1, D - 1)) if nxt is not None else bg
                    f = f * (1 - k) + other * k
                proc.stdin.write(to_u8(f).tobytes())
            cur = nxt if nxt is not None else cur
            if progress is not None:
                if getattr(progress, "cancelled", False):
                    break
                progress(i + 1, n, f"Slide {i + 1} of {n}")
    finally:
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
        code = proc.wait()
    if code:
        raise RuntimeError(err.strip() or "ffmpeg failed")
    return path
