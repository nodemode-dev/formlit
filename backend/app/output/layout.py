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
    "job": {"output": "pdf", "ppi": 300, "sharpen": {"on": True, "for": "matte", "amount": "standard"}, "space": "srgb", "printer": "", "copies": 1, "quality": 92,
            "bits": "16", "profile": "", "intent": "perceptual", "adjust": {"on": False, "brightness": 0, "contrast": 0}},
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
    "two-h-caption": {"name": "Two Side by Side with Captions", "cells": [[0.06, 0.18, 0.425, 0.56], [0.515, 0.18, 0.425, 0.56]], "texts": [[0.06, 0.77, 0.425, 0.08], [0.515, 0.77, 0.425, 0.08]]},
    "two-big-small": {"name": "One Large One Small", "cells": [[0.05, 0.08, 0.6, 0.84], [0.68, 0.36, 0.27, 0.3]], "texts": [[0.68, 0.7, 0.27, 0.12]]},
    "three-row": {"name": "Three in a Row", "cells": [[0.04, 0.3, 0.3, 0.4], [0.35, 0.3, 0.3, 0.4], [0.66, 0.3, 0.3, 0.4]], "texts": []},
    "three-left": {"name": "One Tall Two Stacked", "cells": [[0.05, 0.06, 0.5, 0.88], [0.57, 0.06, 0.38, 0.43], [0.57, 0.51, 0.38, 0.43]], "texts": []},
    "three-stack": {"name": "Three Stacked", "cells": [[0.2, 0.04, 0.6, 0.29], [0.2, 0.355, 0.6, 0.29], [0.2, 0.67, 0.6, 0.29]], "texts": []},
    "four-row": {"name": "Four in a Row", "cells": [[0.04, 0.34, 0.215, 0.32], [0.27, 0.34, 0.215, 0.32], [0.5, 0.34, 0.215, 0.32], [0.73, 0.34, 0.215, 0.32]], "texts": []},
    "four-feature": {"name": "One Large Three Small", "cells": [[0.05, 0.06, 0.62, 0.88], [0.7, 0.06, 0.25, 0.28], [0.7, 0.36, 0.25, 0.28], [0.7, 0.66, 0.25, 0.28]], "texts": []},
    "four-caption": {"name": "Four Grid with Caption", "cells": [[0.08, 0.05, 0.41, 0.37], [0.51, 0.05, 0.41, 0.37], [0.08, 0.44, 0.41, 0.37], [0.51, 0.44, 0.41, 0.37]], "texts": [[0.08, 0.85, 0.84, 0.08]]},
    "five": {"name": "Five Mosaic", "cells": [[0.04, 0.05, 0.56, 0.58], [0.62, 0.05, 0.34, 0.28], [0.62, 0.35, 0.34, 0.28], [0.04, 0.66, 0.45, 0.29], [0.51, 0.66, 0.45, 0.29]], "texts": []},
    "six": {"name": "Six Grid", "cells": [[0.04 + c * 0.31, 0.12 + r * 0.39, 0.3, 0.37] for r in range(2) for c in range(3)], "texts": []},
    "nine": {"name": "Nine Grid", "cells": [[0.05 + c * 0.305, 0.05 + r * 0.305, 0.29, 0.29] for r in range(3) for c in range(3)], "texts": []},
    "twelve": {"name": "Contact Sheet", "cells": [[0.04 + c * 0.235, 0.06 + r * 0.31, 0.22, 0.28] for r in range(3) for c in range(4)], "texts": []},
    "photo-text-right": {"name": "Photo with Text Beside", "cells": [[0.05, 0.08, 0.55, 0.84]], "texts": [[0.64, 0.3, 0.31, 0.08], [0.64, 0.4, 0.31, 0.3]]},
    "photo-text-left": {"name": "Text Beside Photo", "cells": [[0.4, 0.08, 0.55, 0.84]], "texts": [[0.05, 0.3, 0.31, 0.08], [0.05, 0.4, 0.31, 0.3]]},
    "full-caption": {"name": "Full Bleed with Caption", "cells": [[0, 0, 1, 0.86]], "texts": [[0.08, 0.89, 0.84, 0.07]]},
    "title-photo": {"name": "Title over Photo", "cells": [[0.08, 0.24, 0.84, 0.7]], "texts": [[0.08, 0.06, 0.84, 0.1], [0.08, 0.16, 0.84, 0.05]]},
    "quote": {"name": "Quote Page", "cells": [], "texts": [[0.18, 0.36, 0.64, 0.2], [0.18, 0.6, 0.64, 0.06]]},
    "text": {"name": "Text Page", "cells": [], "texts": [[0.15, 0.3, 0.7, 0.4]]},
    "blank": {"name": "Blank", "cells": [], "texts": []},
    "cover": {"name": "Cover", "cells": [[0.0, 0.0, 1.0, 0.72]], "texts": [[0.08, 0.76, 0.84, 0.1], [0.08, 0.87, 0.84, 0.06]]},
    "spread": {"name": "Two-Page Spread", "spread": True, "cells": [[0, 0, 2, 1]], "texts": []},
    "spread-caption": {"name": "Spread with Caption", "spread": True, "cells": [[0, 0, 2, 0.86]], "texts": [[1.08, 0.89, 0.84, 0.07]]},
    "spread-text": {"name": "Spread with Text Left", "spread": True, "cells": [[0.62, 0, 1.38, 1]], "texts": [[0.08, 0.32, 0.46, 0.08], [0.08, 0.42, 0.46, 0.3]]},
    "spread-two": {"name": "Two Facing Bleeds", "spread": True, "cells": [[0, 0, 1, 1], [1, 0, 1, 1]], "texts": []},
    "spread-cont": {"name": "Spread (right page)", "hidden": True, "cells": [], "texts": []},
    "wrap": {"name": "Wrap Photo", "wrap": True, "cells": [[0, 0, 1, 1]], "texts": [[0.56, 0.08, 0.4, 0.1], [0.56, 0.18, 0.4, 0.06], [0.05, 0.7, 0.38, 0.2]]},
    "wrap-front": {"name": "Front Photo, Text Back", "wrap": True, "cells": [[0.52, 0, 0.48, 1]], "texts": [[0.56, 0.06, 0.4, 0.1], [0.56, 0.16, 0.4, 0.06], [0.05, 0.3, 0.38, 0.4]]},
    "wrap-both": {"name": "Front and Back Photos", "wrap": True, "cells": [[0, 0, 0.48, 1], [0.52, 0, 0.48, 1]], "texts": [[0.56, 0.08, 0.4, 0.1], [0.56, 0.18, 0.4, 0.06], [0.05, 0.82, 0.38, 0.1]]},
}
SPINE_PER_PAGE = 0.0025
SPINE_BOARD = 0.25
BLEED = 0.125


def templates() -> dict:
    from app.core import prefs
    user = prefs.load().get("bookTemplates") or {}
    return {**BOOK_TEMPLATES, **{k: v for k, v in user.items() if isinstance(v, dict) and "cells" in v}}


def spine_width(pages: int) -> float:
    return round(SPINE_BOARD + SPINE_PER_PAGE * max(20, pages), 3)


def _padded(x: float, y: float, w: float, h: float, pad: float) -> tuple[float, float, float, float]:
    p = max(0.0, min(0.45, pad)) * min(w, h)
    return x + p, y + p, w - 2 * p, h - 2 * p
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


TEXT_STYLES = {
    "title": {"font": "sans", "bold": True, "size": 30, "align": "center"},
    "heading": {"font": "sans", "bold": True, "size": 18, "align": "left"},
    "body": {"font": "serif", "bold": False, "size": 11, "align": "left"},
    "caption": {"font": "sans", "bold": False, "italic": True, "size": 9, "align": "center"},
    "quote": {"font": "serif", "bold": False, "italic": True, "size": 20, "align": "center"},
    "mono": {"font": "mono", "bold": False, "size": 10, "align": "left"},
}


def pan_zoom(cell: dict, img: dict, z: float, x: float, y: float) -> dict:
    z = max(1.0, min(4.0, z))
    x, y = max(-1.0, min(1.0, x)), max(-1.0, min(1.0, y))
    iw, ih = img["w"] * z, img["h"] * z
    sx, sy = max(0.0, iw - cell["w"]), max(0.0, ih - cell["h"])
    return {"x": cell["x"] - sx * (0.5 + 0.5 * x) + min(0.0, iw - cell["w"]) * -0.5, "y": cell["y"] - sy * (0.5 + 0.5 * y) + min(0.0, ih - cell["h"]) * -0.5, "w": iw, "h": ih}


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
        rows, cols = max(1, min(15, int(s["rows"]))), max(1, min(15, int(s["cols"])))
        gx = max(0.0, min(float(s["gapX"]), area_w / max(1, cols - 1) * 0.9 if cols > 1 else 0.0))
        gy = max(0.0, min(float(s["gapY"]), area_h / max(1, rows - 1) * 0.9 if rows > 1 else 0.0))
        cw = max(0.05, float(s["cellW"])) if s.get("cellW") else (area_w - gx * (cols - 1)) / cols
        chh = max(0.05, float(s["cellH"])) if s.get("cellH") else (area_h - gy * (rows - 1)) / rows
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


def _book_items(page: dict, t: dict, photos: dict[int, float], W: float, H: float, title: bool, bleed: float = 0.0, span: float = 0.0) -> tuple[list, list]:
    ids = list(page.get("photos") or [])
    crops = list(page.get("crops") or [])
    pads = list(page.get("pads") or [])
    cells = []
    for i, (x, y, w, h) in enumerate(t["cells"]):
        pid = ids[i] if i < len(ids) else None
        x, y, w, h = _padded(x * W, y * H, w * W, h * H, float(pads[i]) if i < len(pads) and pads[i] else 0.0)
        if bleed:
            right = span or W
            x0 = x - bleed if x <= 1e-6 else x
            y0 = y - bleed if y <= 1e-6 else y
            x1 = x + w + bleed if x + w >= right - 1e-6 else x + w
            y1 = y + h + bleed if y + h >= H - 1e-6 else y + h
            x, y, w, h = x0 + bleed, y0 + bleed, x1 - x0, y1 - y0
        c = {"x": x, "y": y, "w": w, "h": h}
        item = place(c, photos.get(int(pid)) if pid is not None else None, True, False)
        item["photo"] = pid
        adj = crops[i] if i < len(crops) and isinstance(crops[i], dict) else None
        if adj and item.get("img"):
            item["img"] = pan_zoom(c, item["img"], float(adj.get("z", 1)), float(adj.get("x", 0)), float(adj.get("y", 0)))
            item["crop"] = {"z": float(adj.get("z", 1)), "x": float(adj.get("x", 0)), "y": float(adj.get("y", 0))}
        cells.append(item)
    texts = []
    values = list(page.get("texts") or [])
    styles = list(page.get("styles") or [])
    for i, (x, y, w, h) in enumerate(t["texts"]):
        frame = {"x": x * W + bleed, "y": y * H + bleed, "w": w * W, "h": h * H, "text": values[i] if i < len(values) else "", "title": title and i == 0}
        st = styles[i] if i < len(styles) and isinstance(styles[i], dict) else None
        if st:
            base = TEXT_STYLES.get(str(st.get("style", "")), {})
            frame.update({k: v for k, v in {**base, **st}.items() if k in ("font", "bold", "italic", "size", "align", "color")})
        texts.append(frame)
    return cells, texts


def _half(items: list, x0: float, x1: float, shift: float, key: str = "cells") -> list:
    out = []
    for it in items:
        if key == "cells":
            a, b = max(x0, it["x"]), min(x1, it["x"] + it["w"])
            if b - a <= 1e-6:
                continue
            c = dict(it, x=a - shift, w=b - a)
            if it.get("img"):
                c["img"] = dict(it["img"], x=it["img"]["x"] - shift)
            out.append(c)
        elif x0 - 1e-6 <= it["x"] < x1:
            out.append(dict(it, x=it["x"] - shift))
    return out


def book_pages(settings: dict, photos: dict[int, float]) -> dict:
    s = deep_merge(BOOK_DEFAULTS, settings)
    _, pw, ph = BOOK_SIZES.get(s.get("size", ""), BOOK_SIZES["standard-landscape"])
    tpl = templates()
    b = BLEED if (s.get("job") or {}).get("bleed") or (s.get("job") or {}).get("output") == "blurb" else 0.0
    src = [s["cover"]] + list(s["pages"])
    spine = spine_width(len(src) - 1)
    out = []
    carry: dict | None = None
    for idx, page in enumerate(src):
        t = tpl.get(page.get("template", "single"), BOOK_TEMPLATES["single"])
        base = {"template": page.get("template", "single"), "cover": idx == 0, "number": idx}
        if idx == 0 and t.get("wrap"):
            W = 2 * pw + spine
            cells, texts = _book_items(page, t, photos, W, ph, True, b)
            spine_text = str(page.get("spine") if page.get("spine") is not None else (page.get("texts") or ["Untitled"])[0])
            if spine_text:
                texts.append({"x": pw + b, "y": b, "w": spine, "h": ph, "text": spine_text, "rotate": 90, "size": max(7.0, min(18.0, spine * 72 * 0.45))})
            out.append({**base, "cells": cells, "texts": texts, "w": W + 2 * b, "h": ph + 2 * b, "spine": [pw + b, spine]})
            continue
        if t.get("spread") and idx > 0:
            cells, texts = _book_items(page, t, photos, pw, ph, False, b, span=2 * pw)
            out.append({**base, "cells": _half(cells, 0, pw + b, 0), "texts": _half(texts, 0, pw + b, 0, "texts"), "w": pw + 2 * b, "h": ph + 2 * b, "spreadLeft": True})
            carry = {"cells": _half(cells, pw + b, 2 * pw + 2 * b, pw), "texts": _half(texts, pw + b, 2 * pw + 2 * b, pw, "texts")}
            continue
        if page.get("template") == "spread-cont" and carry is not None:
            out.append({**base, **carry, "w": pw + 2 * b, "h": ph + 2 * b, "spreadRight": True})
            carry = None
            continue
        carry = None
        cells, texts = _book_items(page, t, photos, pw, ph, idx == 0, b)
        out.append({**base, "cells": cells, "texts": texts, "w": pw + 2 * b, "h": ph + 2 * b})
    return {"page": {"w": pw + 2 * b, "h": ph + 2 * b}, "pages": out, "settings": s, "bleed": b, "spine": spine}


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
