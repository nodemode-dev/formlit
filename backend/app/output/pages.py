import io
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.develop.output import to_u8
from app.engine import catalog as catalog_mod
from app.engine.records import detail
from app.output import export

MAX_LONG_PX = 7200


def _hex(c: str) -> tuple[int, int, int]:
    c = (c or "#ffffff").lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)) if len(c) == 6 else (255, 255, 255)


def _shutter(v: float | None) -> str:
    if not v:
        return ""
    return f"1/{round(1 / v)} s" if v < 1 else f"{v:g} s"


def caption(pid: int | None, field: str, custom: str = "") -> str:
    if pid is None:
        return ""
    r = detail(catalog_mod.get(), int(pid)) or {}
    meta = r.get("meta") or {}
    if field == "fileName":
        return r.get("fileName") or ""
    if field == "exposure":
        parts = [_shutter(r.get("shutter")), f"f/{r['aperture']:g}" if r.get("aperture") else "", f"ISO {r['iso']}" if r.get("iso") else "",
                 f"{r['focal']:g} mm" if r.get("focal") else ""]
        return ", ".join(p for p in parts if p)
    if field == "date":
        return (r.get("captureTime") or "")[:10]
    if field == "custom":
        return export._tokens(custom, r)
    if field == "titleCaption":
        return " · ".join(x for x in (meta.get("title"), meta.get("caption")) if x)
    return str(meta.get(field) or "")


def print_adjust(arr: np.ndarray, job: dict) -> np.ndarray:
    adj = job.get("adjust") or {}
    if not adj.get("on"):
        return arr
    b = max(-100.0, min(100.0, float(adj.get("brightness", 0)))) / 100.0
    c = max(-100.0, min(100.0, float(adj.get("contrast", 0)))) / 100.0
    x = np.clip(arr, 0.0, 1.0)
    if b:
        x = np.power(x, 2.0 ** (-b * 0.6))
    if c:
        x = np.clip(x - c * 0.08 * np.sin(2.0 * np.pi * x), 0.0, 1.0)
    return x.astype(np.float32)


def managed(job: dict) -> str:
    prof = str(job.get("profile") or "")
    return prof if prof and Path(prof).is_file() else ""


def finish_print(arr: np.ndarray, job: dict) -> np.ndarray:
    arr = print_adjust(arr, job)
    prof = managed(job)
    if prof:
        from app.output import icc
        arr = icc.to_printer(arr, prof, str(job.get("intent", "perceptual")), bool(job.get("bpc", True)))
    return arr


def cell_image(pid: int, cell: dict, ppi: float, space: str, sharpen: dict, job: dict | None = None) -> tuple[np.ndarray, tuple[float, float, float, float]] | None:
    img = cell.get("img")
    if not img:
        return None
    w_px, h_px = img["w"] * ppi, img["h"] * ppi
    k = min(1.0, MAX_LONG_PX / max(w_px, h_px, 1))
    w_px, h_px = max(2, round(w_px * k)), max(2, round(h_px * k))
    rot = bool(cell.get("rot"))
    size = {"resize": True, "mode": "wh", "w": h_px if rot else w_px, "h": w_px if rot else h_px, "noEnlarge": False}
    job = job or {}
    out = export.render_photo(int(pid), size, "srgb" if managed(job) else space)
    if rot:
        out = np.ascontiguousarray(np.rot90(out, -1))
    out = export.sharpen(out, sharpen, int(ppi))
    out = finish_print(out, job)
    H, W = out.shape[:2]
    x0, y0 = max(cell["x"], img["x"]), max(cell["y"], img["y"])
    x1, y1 = min(cell["x"] + cell["w"], img["x"] + img["w"]), min(cell["y"] + cell["h"], img["y"] + img["h"])
    if x1 <= x0 or y1 <= y0:
        return None
    px0 = int(round((x0 - img["x"]) / img["w"] * W))
    py0 = int(round((y0 - img["y"]) / img["h"] * H))
    px1 = max(px0 + 1, int(round((x1 - img["x"]) / img["w"] * W)))
    py1 = max(py0 + 1, int(round((y1 - img["y"]) / img["h"] * H)))
    return out[py0:py1, px0:px1], (x0, y0, x1 - x0, y1 - y0)


def _jpeg(arr: np.ndarray, quality: int) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(to_u8(arr), "RGB").save(buf, "JPEG", quality=quality, subsampling=0)
    return buf.getvalue()


def _overlays(page: dict, layout: dict, s: dict, total: int) -> list[dict]:
    out: list[dict] = []
    pw, ph = layout["page"]["w"], layout["page"]["h"]
    ident = s.get("identity") or {}
    if ident.get("on") and ident.get("text"):
        out.append({"x": float(ident.get("x", 0.5)) * pw, "y": float(ident.get("y", 0.05)) * ph, "size": float(ident.get("size", 18)), "text": ident["text"],
                    "align": "center", "color": ident.get("color", "#333333")})
    if s.get("pageNumbers") and not page.get("cover"):
        out.append({"x": pw / 2, "y": ph - 0.3, "size": 8, "text": str(page["number"]), "align": "center", "color": "#555555"})
    if s.get("pageInfo"):
        job = s.get("job") or {}
        out.append({"x": 0.3, "y": ph - 0.3, "size": 7, "text": f"Page {page['number']} of {total} · {job.get('ppi', 300)} ppi · sharpening {('on' if (job.get('sharpen') or {}).get('on') else 'off')} · formlit",
                    "align": "left", "color": "#777777"})
    cap = s.get("caption") or {}
    if cap.get("on"):
        for c in page["cells"]:
            text = caption(c.get("photo"), cap.get("field", "title"), cap.get("custom", ""))
            if text:
                out.append({"x": c["x"] + c["w"] / 2, "y": c["y"] + c["h"] + float(cap.get("size", 9)) / 72 * 1.3, "size": float(cap.get("size", 9)), "text": text, "align": "center", "color": "#333333"})
    for t in page.get("texts") or []:
        if t.get("text"):
            size = float(t.get("size") or (s.get("titleSize", 28) if t.get("title") else s.get("textSize", 11)))
            align = str(t.get("align") or "center")
            x = t["x"] if align == "left" else t["x"] + t["w"] if align == "right" else t["x"] + t["w"] / 2
            out.append({"x": x, "y": t["y"] + size / 72, "size": size, "text": t["text"], "align": align, "color": t.get("color") or s.get("textColor", "#222222"), "wrap": t["w"],
                        "font": t.get("font", "sans"), "bold": t.get("bold", size >= 20), "italic": bool(t.get("italic"))})
    if s.get("captions") and "captionField" in s:
        for c in page["cells"]:
            text = caption(c.get("photo"), s.get("captionField", "title"))
            if text:
                out.append({"x": c["x"] + c["w"] / 2, "y": c["y"] + c["h"] + 0.18, "size": 9, "text": text, "align": "center", "color": s.get("textColor", "#222222")})
    return out


PDF_FONTS = {"sans": ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique"),
             "serif": ("Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic"),
             "mono": ("Courier", "Courier-Bold", "Courier-Oblique", "Courier-BoldOblique")}


def pdf_font(family: str, bold: bool, italic: bool) -> str:
    f = PDF_FONTS.get(family, PDF_FONTS["sans"])
    return f[(1 if bold else 0) + (2 if italic else 0)]


def write_pdf(layout: dict, path: Path, progress: Callable[..., Any] | None = None) -> Path:
    from reportlab.lib.utils import ImageReader, simpleSplit
    from reportlab.pdfgen import canvas as rl_canvas
    s = layout["settings"]
    job = s.get("job") or {}
    ppi, space, quality = float(job.get("ppi", 300)), job.get("space", "srgb"), int(job.get("quality", 92))
    sharpen = job.get("sharpen") or {}
    pw, ph = layout["page"]["w"], layout["page"]["h"]
    c = rl_canvas.Canvas(str(path), pagesize=(pw * 72, ph * 72))
    c.setTitle(path.stem)
    c.setCreator("formlit")
    total = len(layout["pages"])
    bg = _hex(s.get("background", "#ffffff"))
    for n, page in enumerate(layout["pages"]):
        if bg != (255, 255, 255):
            c.setFillColorRGB(*(v / 255 for v in bg))
            c.rect(0, 0, pw * 72, ph * 72, stroke=0, fill=1)
        for cell in page["cells"]:
            if cell.get("photo") is None:
                continue
            got = cell_image(int(cell["photo"]), cell, ppi, space, sharpen, job)
            if got is None:
                continue
            arr, (x, y, w, h) = got
            c.drawImage(ImageReader(io.BytesIO(_jpeg(arr, quality))), x * 72, (ph - y - h) * 72, w * 72, h * 72)
            stroke = float(s.get("stroke") or 0)
            if stroke > 0:
                c.setStrokeColorRGB(*(v / 255 for v in _hex(s.get("strokeColor", "#000000"))))
                c.setLineWidth(stroke)
                c.rect(x * 72 + stroke / 2, (ph - y - h) * 72 + stroke / 2, w * 72 - stroke, h * 72 - stroke, stroke=1, fill=0)
            if s.get("cropMarks"):
                c.setStrokeColorRGB(0, 0, 0)
                c.setLineWidth(0.4)
                L, G = 14, 4
                for cx, cy in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
                    X, Y = cx * 72, (ph - cy) * 72
                    sx = -1 if cx == x else 1
                    sy = 1 if cy == y else -1
                    c.line(X + sx * G, Y, X + sx * (G + L), Y)
                    c.line(X, Y + sy * G, X, Y + sy * (G + L))
        for t in _overlays(page, layout, s, total):
            c.setFillColorRGB(*(v / 255 for v in _hex(t["color"])))
            font = pdf_font(t.get("font", "sans"), bool(t.get("bold", t["size"] >= 20)), bool(t.get("italic")))
            c.setFont(font, t["size"])
            lines = simpleSplit(t["text"], font, t["size"], t["wrap"] * 72) if t.get("wrap") else [t["text"]]
            for i, line in enumerate(lines):
                X, Y = t["x"] * 72, (ph - t["y"]) * 72 - i * t["size"] * 1.3
                if t["align"] == "center":
                    c.drawCentredString(X, Y, line)
                elif t["align"] == "right":
                    c.drawRightString(X, Y, line)
                else:
                    c.drawString(X, Y, line)
        c.showPage()
        if progress is not None:
            progress(n + 1, total, f"Page {n + 1} of {total}")
    c.save()
    return path


def raster(layout: dict, page: dict, ppi: float | None = None, bits: int = 8) -> np.ndarray:
    s = layout["settings"]
    job = s.get("job") or {}
    ppi = float(ppi or job.get("ppi", 300))
    pw, ph = layout["page"]["w"], layout["page"]["h"]
    k = min(1.0, MAX_LONG_PX / max(pw * ppi, ph * ppi))
    ppi *= k
    W, H = max(1, round(pw * ppi)), max(1, round(ph * ppi))
    canvas = np.empty((H, W, 3), np.float32)
    canvas[:] = np.array(_hex(s.get("background", "#ffffff")), np.float32) / 255.0
    for cell in page["cells"]:
        if cell.get("photo") is None:
            continue
        got = cell_image(int(cell["photo"]), cell, ppi, job.get("space", "srgb"), job.get("sharpen") or {}, job)
        if got is None:
            continue
        arr, (x, y, w, h) = got
        X0, Y0 = round(x * ppi), round(y * ppi)
        X1, Y1 = min(W, round((x + w) * ppi)), min(H, round((y + h) * ppi))
        if X1 - X0 < 1 or Y1 - Y0 < 1:
            continue
        canvas[Y0:Y1, X0:X1] = cv2.resize(arr, (X1 - X0, Y1 - Y0), interpolation=cv2.INTER_AREA)
        stroke = float(s.get("stroke") or 0)
        if stroke > 0:
            sp = max(1, round(stroke / 72 * ppi))
            col = np.array(_hex(s.get("strokeColor", "#000000")), np.float32) / 255
            canvas[Y0:Y0 + sp, X0:X1] = col
            canvas[Y1 - sp:Y1, X0:X1] = col
            canvas[Y0:Y1, X0:X0 + sp] = col
            canvas[Y0:Y1, X1 - sp:X1] = col
    ink = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ink)
    for t in _overlays(page, layout, s, len(layout["pages"])):
        font = ImageFont.load_default(size=max(6, round(t["size"] / 72 * ppi)))
        X, Y = t["x"] * ppi, t["y"] * ppi
        draw.text((X, Y), t["text"], font=font, fill=(*_hex(t["color"]), 255), anchor={"center": "ms", "right": "rs"}.get(t["align"], "ls"))
    layer = np.asarray(ink, np.float32) / 255.0
    a = layer[..., 3:4]
    if np.any(a > 0):
        canvas = canvas * (1.0 - a) + layer[..., :3] * a
    if bits == 16:
        return (np.clip(canvas, 0.0, 1.0) * 65535.0 + 0.5).astype(np.uint16)
    return to_u8(canvas)


def write_jpegs(layout: dict, folder: Path, stem: str, progress: Callable[..., Any] | None = None) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    total = len(layout["pages"])
    job = layout["settings"].get("job") or {}
    q = int(job.get("quality", 92))
    ppi = int(job.get("ppi", 300))
    prof = managed(job)
    icc_data = Path(prof).read_bytes() if prof else None
    for i, page in enumerate(layout["pages"]):
        arr = raster(layout, page)
        p = folder / f"{stem}-{i + 1:02d}.jpg"
        extra = {"icc_profile": icc_data} if icc_data else {}
        Image.fromarray(arr, "RGB").save(p, "JPEG", quality=q, dpi=(ppi, ppi), **extra)
        out.append(p)
        if progress is not None:
            progress(i + 1, total, f"Page {i + 1} of {total}")
    return out


def write_tiffs(layout: dict, folder: Path, stem: str, progress: Callable[..., Any] | None = None) -> list[Path]:
    import tifffile
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    total = len(layout["pages"])
    job = layout["settings"].get("job") or {}
    ppi = int(job.get("ppi", 300))
    bits = 16 if int(job.get("bits", 16)) == 16 else 8
    prof = managed(job)
    icc_data = Path(prof).read_bytes() if prof else None
    for i, page in enumerate(layout["pages"]):
        arr = raster(layout, page, bits=bits)
        p = folder / f"{stem}-{i + 1:02d}.tif"
        tags = [(34675, "B", len(icc_data), icc_data, False)] if icc_data else []
        tifffile.imwrite(str(p), arr, photometric="rgb", compression="zlib", resolution=(ppi, ppi), resolutionunit="INCH", software="formlit", extratags=tags)
        out.append(p)
        if progress is not None:
            progress(i + 1, total, f"Page {i + 1} of {total}")
    return out


def printers() -> list[dict]:
    out: list[dict] = []
    try:
        if sys.platform == "win32":
            r = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Printer | Select-Object -ExpandProperty Name"], capture_output=True, text=True, timeout=10)
            out = [{"name": n.strip(), "default": False} for n in r.stdout.splitlines() if n.strip()]
        elif shutil.which("lpstat"):
            r = subprocess.run(["lpstat", "-e"], capture_output=True, text=True, timeout=10)
            d = subprocess.run(["lpstat", "-d"], capture_output=True, text=True, timeout=10).stdout
            default = d.split(":")[-1].strip() if ":" in d else ""
            out = [{"name": n.strip(), "default": n.strip() == default} for n in r.stdout.splitlines() if n.strip()]
    except (OSError, subprocess.SubprocessError):
        return []
    return out


def send_to_printer(path: Path, printer: str = "", copies: int = 1) -> str:
    if sys.platform == "win32":
        import os
        for _ in range(max(1, copies)):
            os.startfile(str(path), "print")
        return "Sent to the default printer"
    if not shutil.which("lp"):
        raise RuntimeError("No print system found (CUPS lp is not installed)")
    cmd = ["lp", "-n", str(max(1, copies))]
    if printer:
        cmd += ["-d", printer]
    r = subprocess.run(cmd + [str(path)], capture_output=True, text=True, timeout=30)
    if r.returncode:
        raise RuntimeError(r.stderr.strip() or "The printer refused the job")
    return r.stdout.strip() or "Sent"
