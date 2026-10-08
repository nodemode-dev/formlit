import json
import time
from typing import Any

import numpy as np
from fastapi import APIRouter, Body
from fastapi.responses import FileResponse, JSONResponse, Response

from app.develop import render as render_mod
from app.develop.masks import bitmap_path
from app.engine import catalog as catalog_mod
from app.engine.records import loads
from app.services import previews

router = APIRouter(prefix="/api/photos", tags=["photos"])
IMMUTABLE = "public, max-age=31536000, immutable"


def _missing(pid: int) -> JSONResponse:
    return JSONResponse({"ok": False, "error": f"No image for photo {pid}"}, status_code=404)


def _file(path, final: bool, versioned: bool, media: str = "image/jpeg") -> FileResponse:
    return FileResponse(path, media_type=media, headers={"Cache-Control": IMMUTABLE if final and versioned else "no-store", "X-Final": "1" if final else "0"})


@router.get("/{pid}/thumb")
def thumb(pid: int, rev: int | None = None) -> Any:
    path, final = previews.best_thumb(pid)
    return _missing(pid) if path is None else _file(path, final, rev is not None)


@router.get("/{pid}/preview")
def preview(pid: int, rev: int | None = None, wait: float = 0.0) -> Any:
    try:
        path, final = previews.best_preview(pid, min(max(wait, 0.0), 30.0))
    except FileNotFoundError:
        return _missing(pid)
    return _missing(pid) if path is None else _file(path, final, rev is not None)


@router.get("/{pid}/full")
def full(pid: int, rev: int | None = None, wait: float = 60.0) -> Any:
    try:
        path = previews.request(pid, "f", foreground=True).result(timeout=min(max(wait, 0.1), 300.0))
    except FileNotFoundError:
        return _missing(pid)
    except TimeoutError:
        return JSONResponse({"ok": False, "error": "Still building the 1:1 preview"}, status_code=202)
    return _file(path, True, rev is not None)


@router.get("/{pid}/original")
def original(pid: int) -> Any:
    path = catalog_mod.get().photo_path(pid)
    if path is None or not path.is_file():
        return _missing(pid)
    return FileResponse(path, headers={"Cache-Control": "no-store"})


@router.get("/{pid}/source")
def source(pid: int, long: int = previews.PREVIEW) -> Any:
    try:
        img, info = previews.source(pid, long if long > 0 else previews.PREVIEW)
    except FileNotFoundError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=404)
    h, w = img.shape[:2]
    data = np.ascontiguousarray(img, dtype=np.float16).tobytes()
    return Response(data, media_type="application/octet-stream", headers={
        "Cache-Control": "no-store", "X-Width": str(w), "X-Height": str(h), "X-Info": json.dumps(info, separators=(",", ":")),
        "Access-Control-Expose-Headers": "X-Width, X-Height, X-Info"})


@router.get("/{pid}/masks/{key}.png")
def mask_bitmap(pid: int, key: str) -> Any:
    path = bitmap_path(pid, key)
    if not path.is_file():
        return _missing(pid)
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})


def _bad_render(body: Any) -> str:
    def num(v: Any) -> bool:
        return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")
    if not isinstance(body, dict):
        return "The render body must be an object"
    if body.get("settings") is not None and not isinstance(body["settings"], dict):
        return "settings must be an object"
    if body.get("long") is not None and not (num(body["long"]) and 16 <= body["long"] <= 30000):
        return "long must be a number of pixels between 16 and 30000"
    size = body.get("size")
    if size is not None and not (isinstance(size, list) and len(size) == 2 and all(num(v) and 1 <= v <= 30000 for v in size)):
        return "size must be [width, height] in pixels"
    region = body.get("region")
    if region is not None and not (isinstance(region, list) and len(region) == 4 and all(num(v) for v in region) and region[0] < region[2] and region[1] < region[3]):
        return "region must be [x0, y0, x1, y1] with x0 < x1 and y0 < y1"
    if body.get("quality") is not None and not (num(body["quality"]) and 1 <= body["quality"] <= 100):
        return "quality must be between 1 and 100"
    if body.get("overlay") is not None and not isinstance(body["overlay"], dict):
        return "overlay must be an object"
    for key in ("space", "view", "hdr", "preset"):
        if body.get(key) is not None and not isinstance(body[key], str):
            return f"{key} must be a string"
    if body.get("presetAmount") is not None and not num(body["presetAmount"]):
        return "presetAmount must be a number"
    return ""


@router.post("/{pid}/render")
def render(pid: int, body: dict | None = Body(default=None)) -> Any:
    body = body or {}
    bad = _bad_render(body)
    if bad:
        return JSONResponse({"ok": False, "error": bad}, status_code=400)
    started = time.perf_counter()
    cat = catalog_mod.get()
    row = cat.row("SELECT develop FROM photos WHERE id=?", (pid,))
    if row is None:
        return _missing(pid)
    dev = body.get("settings")
    if body.get("before"):
        from app.engine.cmd_develop import before_of
        dev = before_of(pid)
    elif body.get("defaults"):
        from app.develop.settings import defaults_for
        dev = defaults_for(str(cat.scalar("SELECT kind FROM photos WHERE id=?", (pid,)) or ""))
    elif dev is None:
        dev = loads(row["develop"], {})
    from app.develop.settings import sanitize
    dev = sanitize(dev)
    if body.get("preset"):
        from app.develop import settings as S
        from app.engine import presets
        try:
            src = presets.settings_of(str(body["preset"]))
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=404)
        groups = sorted({g for g, keys in S.GROUPS.items() for k in src if k in keys}) or None
        base_masks = (dev or {}).get("masks") or []
        dev = S.apply_groups(dev, src, groups, float(body.get("presetAmount", 100)) / 100.0)
        if src.get("masks"):
            from app.engine.cmd_ai import ensure_masks
            dev["masks"] = presets.merge_masks(base_masks, src["masks"], float(body.get("presetAmount", 100)) / 100.0)
            try:
                ensure_masks(pid, dev)
            except Exception:
                pass
    from app.output import gainmap
    hdr_mode = str(body.get("hdr") or "") if gainmap.hdr_on(dev) else ""
    hdr_dev = dev
    if hdr_mode == "sdr":
        dev = gainmap.sdr_settings(dev)
    long = int(body.get("long") or previews.PREVIEW)
    size = body.get("size")
    region = body.get("region")
    view = str(body.get("view") or "")
    extra: dict = {}
    full = long > previews.PREVIEW
    try:
        img, info = previews.source(pid, None if full else previews.PREVIEW, full=full)
    except FileNotFoundError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=404)
    slot = (pid, view, "full" if full else "p") if view else None
    if region:
        out, rect, dims = render_mod.render_region(img, info, dev, region, long, space=body.get("space", "srgb"), photo_id=pid, overlay=body.get("overlay"),
                                                   src_long=max(img.shape[:2]) if full else None, slot=slot)
        extra = {"X-Region": ",".join(str(v) for v in rect), "X-Full": f"{dims[0]},{dims[1]}"}
    else:
        out = render_mod.render(img, info, dev, max_long=None if size else long, size=tuple(size) if size else None, space=body.get("space", "srgb"),
                                photo_id=pid, apply_crop=bool(body.get("crop", True)), overlay=body.get("overlay"), slot=slot,
                                src_long=max(img.shape[:2]) if full else None)
    hdr_body = None
    if hdr_mode in ("display", "visualize") and not region:
        stops = gainmap.headroom(hdr_dev)
        under = render_mod.render(img, info, gainmap.under_settings(hdr_dev, stops), max_long=None if size else long, size=tuple(size) if size else None,
                                  photo_id=pid, apply_crop=bool(body.get("crop", True)), slot=(pid, view + "-under", "full" if full else "p") if view else None,
                                  src_long=max(img.shape[:2]) if full else None)
        if under.shape != out.shape:
            import cv2
            under = cv2.resize(under, (out.shape[1], out.shape[0]), interpolation=cv2.INTER_AREA)
        gain = gainmap.gain_from(out, under, stops)
        if hdr_mode == "visualize":
            out = gainmap.visualize(out, gain)
        else:
            from app.output import encode
            hdr = gainmap.hdr_linear(out, gain)
            y = np.log2(np.maximum(hdr @ np.array([0.2126, 0.7152, 0.0722], np.float32), 1e-6))
            bins, _ = np.histogram(y[y > 0.0], bins=32, range=(0.0, stops))
            extra["X-HDR-Hist"] = ",".join(str(int(b)) for b in bins)
            extra["X-HDR-Stops"] = f"{stops:.2f}"
            hdr_body = encode.encode_hdr("avif", hdr, int(body.get("quality", 85)), 72, {}, speed=10)
    rgb8 = render_mod.to_u8(out)
    eff = render_mod.effective(dev)
    sh, sw = img.shape[:2]
    if region:
        fr = render_mod.Frame(sw, sh, eff, True)
        fw, fh = fr.fit_long(long)
    else:
        fr, fw, fh, _ = render_mod.plan(sw, sh, eff, None if size else long, tuple(size) if size else None, bool(body.get("crop", True)))
    geo = {"norm": [round(float(v), 9) for v in fr.out_to_norm(fw, fh).reshape(-1)], "w": fw, "h": fh, "ow": fr.ow, "oh": fr.oh, "rect": fr.rect,
           "angle": fr.angle, "flipH": fr.flip_h, "flipV": fr.flip_v}
    headers = {"Cache-Control": "no-store", "X-Render-Ms": f"{(time.perf_counter() - started) * 1000:.0f}", "X-Width": str(rgb8.shape[1]),
               "X-Height": str(rgb8.shape[0]), "X-Geometry": json.dumps(geo, separators=(",", ":")),
               "Access-Control-Expose-Headers": "X-Render-Ms, X-Width, X-Height, X-Histogram, X-Region, X-Full, X-Geometry, X-HDR-Hist, X-HDR-Stops", **extra}
    if body.get("histogram"):
        headers["X-Histogram"] = json.dumps(render_mod.histogram(out, 64), separators=(",", ":"))
    if hdr_body is not None:
        return Response(hdr_body, media_type="image/avif", headers=headers)
    return Response(previews.encode_jpeg(rgb8, int(body.get("quality", 90))), media_type="image/jpeg", headers=headers)
