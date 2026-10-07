import copy
import math

PAPER = {
    "letter": ("Letter", 8.5, 11.0), "legal": ("Legal", 8.5, 14.0), "tabloid": ("Tabloid", 11.0, 17.0), "a5": ("A5", 5.83, 8.27), "a4": ("A4", 8.27, 11.69),
    "a3": ("A3", 11.69, 16.54), "a3plus": ("A3+ / Super B", 13.0, 19.0), "a2": ("A2", 16.54, 23.39), "4x6": ("4 x 6 in", 4.0, 6.0), "5x7": ("5 x 7 in", 5.0, 7.0),
    "8x10": ("8 x 10 in", 8.0, 10.0), "11x14": ("11 x 14 in", 11.0, 14.0), "13x19": ("13 x 19 in", 13.0, 19.0), "16x20": ("16 x 20 in", 16.0, 20.0),
    "17x22": ("17 x 22 in", 17.0, 22.0),
}
PACKAGE_SIZES = {"wallet": (2.5, 3.5), "2x3": (2.0, 3.0), "3x5": (3.0, 5.0), "4x6": (4.0, 6.0), "5x7": (5.0, 7.0), "8x10": (8.0, 10.0)}
PRINT_DEFAULTS: dict = {
    "style": "grid", "paper": "letter", "orientation": "portrait", "size": None,
    "margins": [0.5, 0.5, 0.5, 0.5], "rows": 1, "cols": 1, "gapX": 0.25, "gapY": 0.25, "cellW": None, "cellH": None,
    "fill": False, "rotate": True, "repeat": False, "stroke": 0.0, "strokeColor": "#000000", "background": "#ffffff",
    "package": [{"size": "5x7"}, {"size": "wallet"}, {"size": "wallet"}], "cells": [{"x": 0.5, "y": 0.5, "w": 4.0, "h": 6.0}],
    "identity": {"on": False, "text": "", "size": 18, "x": 0.5, "y": 0.035, "color": "#333333"},
    "pageNumbers": False, "pageInfo": False, "cropMarks": False,
    "caption": {"on": False, "field": "title", "size": 9, "custom": ""},
    "job": {"output": "pdf", "ppi": 300, "sharpen": {"on": True, "for": "matte", "amount": "standard"}, "space": "srgb", "printer": "", "copies": 1, "quality": 92},
}
PRINT_TEMPLATES = [
    {"id": "fine-art", "name": "Fine Art Mat", "settings": {"margins": [1.0, 1.0, 1.0, 1.75], "identity": {"on": True, "text": "", "size": 14, "x": 0.5, "y": 0.93}}},
    {"id": "maximize", "name": "Maximize Size", "settings": {"margins": [0.25, 0.25, 0.25, 0.25]}},
    {"id": "1-large", "name": "1 Large with Stroke", "settings": {"margins": [0.75, 0.75, 0.75, 0.75], "stroke": 1.0}},
    {"id": "2x2", "name": "2 x 2 Cells", "settings": {"rows": 2, "cols": 2, "gapX": 0.2, "gapY": 0.2, "margins": [0.4, 0.4, 0.4, 0.4]}},
    {"id": "4x5-contact", "name": "4 x 5 Contact Sheet", "settings": {"rows": 5, "cols": 4, "gapX": 0.12, "gapY": 0.35, "margins": [0.4, 0.4, 0.5, 0.5],
                                                                      "caption": {"on": True, "field": "fileName", "size": 7}, "pageNumbers": True}},
    {"id": "5x8-contact", "name": "5 x 8 Contact Sheet", "settings": {"rows": 8, "cols": 5, "gapX": 0.1, "gapY": 0.28, "margins": [0.35, 0.35, 0.4, 0.45],
                                                                      "caption": {"on": True, "field": "fileName", "size": 6}, "pageNumbers": True}},
    {"id": "triptych", "name": "Triptych", "settings": {"orientation": "landscape", "rows": 1, "cols": 3, "gapX": 0.15, "fill": True, "margins": [0.6, 0.6, 2.0, 2.0]}},
    {"id": "package-1-2", "name": "Picture Package 1 (5x7) 2 (wallet)", "settings": {"style": "package", "fill": True, "package": [{"size": "5x7"}, {"size": "wallet"}, {"size": "wallet"}]}},
    {"id": "package-2-5x7", "name": "Picture Package 2 (5x7)", "settings": {"style": "package", "fill": True, "package": [{"size": "5x7"}, {"size": "5x7"}]}},
    {"id": "package-4-4x6", "name": "Picture Package 4 (4x6)", "settings": {"style": "package", "fill": True, "paper": "a3plus", "package": [{"size": "4x6"}] * 4}},
    {"id": "custom-overlap", "name": "Custom Centered", "settings": {"style": "custom", "cells": [{"x": 1.25, "y": 1.5, "w": 6.0, "h": 4.0}, {"x": 1.25, "y": 6.0, "w": 2.8, "h": 3.5}, {"x": 4.45, "y": 6.0, "w": 2.8, "h": 3.5}]}},
]
BOOK_SIZES = {
    "small-square": ("Small Square 7 x 7 in", 7.0, 7.0), "standard-landscape": ("Standard Landscape 10 x 8 in", 10.0, 8.0),
    "standard-portrait": ("Standard Portrait 8 x 10 in", 8.0, 10.0), "large-landscape": ("Large Landscape 13 x 11 in", 13.0, 11.0),
    "large-square": ("Large Square 12 x 12 in", 12.0, 12.0), "letter": ("Letter 8.5 x 11 in", 8.5, 11.0), "a4": ("A4 210 x 297 mm", 8.27, 11.69),
    "a4-landscape": ("A4 Landscape", 11.69, 8.27),
}
BOOK_TEMPLATES = {
    "full": {"name": "Full Bleed", "cells": [[0, 0, 1, 1]], "texts": []},
    "single": {"name": "One Photo", "cells": [[0.08, 0.08, 0.84, 0.84]], "texts": []},
    "single-caption": {"name": "One Photo with Caption", "cells": [[0.08, 0.07, 0.84, 0.72]], "texts": [[0.08, 0.83, 0.84, 0.1]]},
    "single-small": {"name": "One Small Centred", "cells": [[0.22, 0.2, 0.56, 0.5]], "texts": [[0.22, 0.74, 0.56, 0.08]]},
    "two-h": {"name": "Two Side by Side", "cells": [[0.06, 0.2, 0.425, 0.6], [0.515, 0.2, 0.425, 0.6]], "texts": []},
    "two-v": {"name": "Two Stacked", "cells": [[0.12, 0.06, 0.76, 0.425], [0.12, 0.515, 0.76, 0.425]], "texts": []},
    "three": {"name": "One Large Two Small", "cells": [[0.06, 0.06, 0.88, 0.52], [0.06, 0.61, 0.43, 0.33], [0.51, 0.61, 0.43, 0.33]], "texts": []},
    "three-col": {"name": "Three Columns", "cells": [[0.05, 0.22, 0.28, 0.56], [0.36, 0.22, 0.28, 0.56], [0.67, 0.22, 0.28, 0.56]], "texts": []},
    "four": {"name": "Four Grid", "cells": [[0.06, 0.06, 0.43, 0.43], [0.51, 0.06, 0.43, 0.43], [0.06, 0.51, 0.43, 0.43], [0.51, 0.51, 0.43, 0.43]], "texts": []},
    "text": {"name": "Text Page", "cells": [], "texts": [[0.15, 0.3, 0.7, 0.4]]},
    "blank": {"name": "Blank", "cells": [], "texts": []},
    "cover": {"name": "Cover", "cells": [[0.0, 0.0, 1.0, 0.72]], "texts": [[0.08, 0.76, 0.84, 0.1], [0.08, 0.87, 0.84, 0.06]]},
}
BOOK_PRESETS = [
    {"id": "clean", "name": "Clean White", "settings": {"background": "#ffffff", "textColor": "#222222", "pageNumbers": True, "captions": False}},
    {"id": "gallery", "name": "Gallery Black", "settings": {"background": "#111111", "textColor": "#e6e6e6", "pageNumbers": False, "captions": True, "captionField": "title"}},
    {"id": "travel", "name": "Travel Journal", "settings": {"background": "#f4efe6", "textColor": "#3a3128", "captions": True, "captionField": "titleCaption", "autoLayout": "mixed"}},
    {"id": "portfolio", "name": "Portfolio, One per Page", "settings": {"background": "#ffffff", "textColor": "#222222", "autoLayout": "one", "size": "large-landscape", "pageNumbers": False}},
    {"id": "square", "name": "Square Keepsake", "settings": {"size": "small-square", "background": "#ffffff", "textColor": "#222222"}},
]
BOOK_DEFAULTS: dict = {
    "size": "standard-landscape", "background": "#ffffff", "textColor": "#222222", "font": "Helvetica", "titleSize": 28, "textSize": 11,
    "pageNumbers": True, "captions": False, "captionField": "title", "autoLayout": "mixed",
    "cover": {"template": "cover", "photos": [], "texts": ["Untitled", ""]}, "pages": [],
    "job": {"output": "pdf", "ppi": 300, "space": "srgb", "quality": 92, "sharpen": {"on": True, "for": "glossy", "amount": "standard"}},
}


def deep_merge(base: dict, over: dict | None) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def page_size(s: dict) -> tuple[float, float]:
    if s.get("size"):
        w, h = float(s["size"][0]), float(s["size"][1])
    else:
        _, w, h = PAPER.get(s.get("paper", "letter"), PAPER["letter"])
    if (s.get("orientation") == "landscape") != (w > h):
        w, h = h, w
    return w, h


def place(cell: dict, aspect: float | None, fill: bool, rotate: bool) -> dict:
    cx, cy, cw, ch = cell["x"], cell["y"], cell["w"], cell["h"]
    if not aspect:
        return dict(cell, rot=False, img=None)
    rot = bool(rotate and ((aspect > 1) != (cw > ch)) and abs(aspect - 1) > 0.02 and abs(cw - ch) > 0.02)
    a = 1 / aspect if rot else aspect
    if (cw / ch > a) == fill:
        iw, ih = cw, cw / a
    else:
        iw, ih = ch * a, ch
    return dict(cell, rot=rot, img={"x": cx + (cw - iw) / 2, "y": cy + (ch - ih) / 2, "w": iw, "h": ih})


def _shelf(sizes: list[tuple[float, float]], area_w: float, area_h: float, gap: float) -> list[tuple[float, float, float, float]] | None:
    out = []
    x = y = row_h = 0.0
    for w, h in sizes:
        if w > area_w and h <= area_w:
            w, h = h, w
        if x > 0 and x + w > area_w + 1e-6:
            x, y, row_h = 0.0, y + row_h + gap, 0.0
        if y + h > area_h + 1e-6:
            return None
        out.append((x, y, w, h))
        x += w + gap
        row_h = max(row_h, h)
    return out


def print_pages(settings: dict, photos: list[dict]) -> dict:
    s = deep_merge(PRINT_DEFAULTS, settings)
    pw, ph = page_size(s)
    ml, mr, mt, mb = [float(v) for v in s["margins"]]
    area_w, area_h = max(0.1, pw - ml - mr), max(0.1, ph - mt - mb)
    style = s.get("style", "grid")
    cells: list[dict] = []
    if style == "grid":
        rows, cols = max(1, int(s["rows"])), max(1, int(s["cols"]))
        gx, gy = float(s["gapX"]), float(s["gapY"])
        cw = float(s["cellW"]) if s.get("cellW") else (area_w - gx * (cols - 1)) / cols
        chh = float(s["cellH"]) if s.get("cellH") else (area_h - gy * (rows - 1)) / rows
        total_w, total_h = cw * cols + gx * (cols - 1), chh * rows + gy * (rows - 1)
        ox, oy = ml + (area_w - total_w) / 2, mt + (area_h - total_h) / 2
        cells = [{"x": ox + c * (cw + gx), "y": oy + r * (chh + gy), "w": cw, "h": chh} for r in range(rows) for c in range(cols)]
    elif style == "package":
        sizes = []
        for it in s["package"]:
            w, h = PACKAGE_SIZES.get(it.get("size", ""), (float(it.get("w", 4)), float(it.get("h", 6))))
            sizes.append((w, h))
        sizes.sort(key=lambda t: -t[0] * t[1])
        packed = _shelf(sizes, area_w, area_h, 0.125) or _shelf([(h, w) for w, h in sizes], area_w, area_h, 0.125) or []
        cells = [{"x": ml + x, "y": mt + y, "w": w, "h": h} for x, y, w, h in packed]
    else:
        cells = [{"x": float(c["x"]), "y": float(c["y"]), "w": float(c["w"]), "h": float(c["h"])} for c in s["cells"]]
    one_per_page = style == "package" or bool(s.get("repeat"))
    per = 1 if one_per_page else max(1, len(cells))
    n_pages = max(1, math.ceil(len(photos) / per)) if photos else 1
    pages = []
    for p in range(n_pages):
        chunk = photos[p * per:(p + 1) * per]
        placed = []
        for i, c in enumerate(cells):
            ph_ = chunk[0] if one_per_page and chunk else (chunk[i] if i < len(chunk) else None)
            item = place(c, ph_["aspect"] if ph_ else None, bool(s["fill"]), bool(s["rotate"]))
            item["photo"] = ph_["id"] if ph_ else None
            placed.append(item)
        pages.append({"cells": placed, "number": p + 1})
    return {"page": {"w": pw, "h": ph}, "pages": pages, "settings": s, "cellCount": len(cells), "fits": bool(cells)}


def book_pages(settings: dict, photos: dict[int, float]) -> dict:
    s = deep_merge(BOOK_DEFAULTS, settings)
    _, pw, ph = BOOK_SIZES.get(s.get("size", ""), BOOK_SIZES["standard-landscape"])
    out = []
    for idx, page in enumerate([s["cover"]] + list(s["pages"])):
        t = BOOK_TEMPLATES.get(page.get("template", "single"), BOOK_TEMPLATES["single"])
        ids = list(page.get("photos") or [])
        cells = []
        for i, (x, y, w, h) in enumerate(t["cells"]):
            pid = ids[i] if i < len(ids) else None
            c = {"x": x * pw, "y": y * ph, "w": w * pw, "h": h * ph}
            item = place(c, photos.get(int(pid)) if pid is not None else None, True, False)
            item["photo"] = pid
            cells.append(item)
        texts = []
        values = list(page.get("texts") or [])
        for i, (x, y, w, h) in enumerate(t["texts"]):
            texts.append({"x": x * pw, "y": y * ph, "w": w * pw, "h": h * ph, "text": values[i] if i < len(values) else "", "title": idx == 0 and i == 0})
        out.append({"template": page.get("template", "single"), "cells": cells, "texts": texts, "cover": idx == 0, "number": idx})
    return {"page": {"w": pw, "h": ph}, "pages": out, "settings": s}


def auto_book(ids: list[int], aspects: dict[int, float], mode: str = "mixed") -> list[dict]:
    pages = []
    i = 0
    cycle = ["single", "two-h", "full", "three", "single-caption", "four"] if mode == "mixed" else ["single"]
    k = 0
    while i < len(ids):
        t = cycle[k % len(cycle)]
        k += 1
        n = len(BOOK_TEMPLATES[t]["cells"])
        chunk = ids[i:i + n]
        if t == "two-h" and any(aspects.get(c, 1.5) > 1.2 for c in chunk):
            t = "two-v"
        if len(chunk) < n:
            t = {1: "single", 2: "two-v", 3: "three"}.get(len(chunk), "single")
            n = len(chunk)
        pages.append({"template": t, "photos": chunk, "texts": [""] * len(BOOK_TEMPLATES[t]["texts"])})
        i += n
    if len(pages) % 2:
        pages.append({"template": "blank", "photos": [], "texts": []})
    return pages
