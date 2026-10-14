import ftplib
import html
import json
import posixpath
from pathlib import Path
from typing import Any, Callable

from app.engine import catalog as catalog_mod
from app.engine.records import detail
from app.output import encode, export, layout as layout_mod, pages

DEFAULTS: dict = {
    "layout": "grid",
    "site": {"title": "Photographs", "collection": "", "description": "", "contact": "", "link": ""},
    "colors": {"background": "#111113", "text": "#e9e9ea", "muted": "#8b8b90", "cell": "#1b1b1e", "accent": "#ff7a1a"},
    "thumbSize": 480, "largeSize": 2048, "quality": 82, "rowHeight": 240, "gap": 8,
    "captions": {"field": "title", "lightbox": "titleCaption", "exposure": False},
    "watermark": {"on": False, "text": "{copyright}", "size": 0.025, "opacity": 0.6, "anchor": "br"},
    "metadata": "copyright", "sharpen": True,
    "upload": {"host": "", "port": 21, "user": "", "password": "", "path": "/", "tls": True},
}
TEMPLATES = [
    {"id": "studio", "name": "Studio Dark Grid", "settings": {}},
    {"id": "paper", "name": "Paper Light Grid", "settings": {"colors": {"background": "#f6f4ef", "text": "#1d1d1f", "muted": "#6d6d72", "cell": "#ebe8e1", "accent": "#b5531b"}}},
    {"id": "track", "name": "Justified Track", "settings": {"layout": "justified", "rowHeight": 280, "gap": 6}},
    {"id": "square", "name": "Square Thumbnails", "settings": {"layout": "square", "thumbSize": 360, "gap": 4}},
    {"id": "folio", "name": "Folio Single Column", "settings": {"layout": "column", "thumbSize": 1600, "gap": 48}},
]


def merged(s: dict | None) -> dict:
    return layout_mod.deep_merge(DEFAULTS, s)


def items(ids: list[int], s: dict) -> list[dict]:
    cat = catalog_mod.get()
    out = []
    for i, pid in enumerate(ids):
        r = detail(cat, pid)
        if not r:
            continue
        cap = s["captions"]
        out.append({"id": pid, "n": i + 1, "aspect": float(r.get("a") or 1.5), "title": pages.caption(pid, cap.get("field", "title")),
                    "long": pages.caption(pid, cap.get("lightbox", "titleCaption")), "exif": pages.caption(pid, "exposure") if cap.get("exposure") else "",
                    "name": Path(r.get("fileName") or "").stem})
    return out


def _css(s: dict) -> str:
    c = s["colors"]
    gap = int(s.get("gap", 8))
    lay = s.get("layout", "grid")
    thumb = int(s.get("thumbSize", 480))
    grid = {
        "grid": f".g{{display:grid;grid-template-columns:repeat(auto-fill,minmax({max(140, thumb // 2)}px,1fr));gap:{gap}px}}.c{{aspect-ratio:3/2}}.c img{{object-fit:contain}}",
        "square": f".g{{display:grid;grid-template-columns:repeat(auto-fill,minmax({max(110, thumb // 2)}px,1fr));gap:{gap}px}}.c{{aspect-ratio:1}}.c img{{object-fit:cover}}",
        "justified": f".g{{display:flex;flex-wrap:wrap;gap:{gap}px}}.g::after{{content:'';flex-grow:999}}.c{{height:{int(s.get('rowHeight', 240))}px;flex-grow:calc(var(--a)*100);flex-basis:calc(var(--a)*{int(s.get('rowHeight', 240))}px)}}.c img{{object-fit:cover}}",
        "column": f".g{{display:flex;flex-direction:column;gap:{gap}px;max-width:1100px;margin:0 auto}}.c{{aspect-ratio:var(--a);background:none}}.c img{{object-fit:contain}}",
    }.get(lay, "")
    return (f"*{{box-sizing:border-box}}html,body{{margin:0;background:{c['background']};color:{c['text']};font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}"
            f"header{{padding:40px 28px 18px}}h1{{margin:0;font-size:26px;font-weight:600;letter-spacing:-.01em}}h2{{margin:4px 0 0;font-size:15px;font-weight:500;color:{c['muted']}}}"
            f"header p{{max-width:720px;color:{c['muted']}}}main{{padding:0 28px 40px}}"
            f".c{{position:relative;display:block;overflow:hidden;border-radius:6px;background:{c['cell']};cursor:zoom-in}}.c img{{display:block;width:100%;height:100%}}"
            f".c span{{position:absolute;left:0;right:0;bottom:0;padding:18px 10px 8px;background:linear-gradient(transparent,rgba(0,0,0,.6));color:#fff;font-size:12px;opacity:0;transition:opacity .2s}}"
            f".c:hover span,.c:focus span{{opacity:1}}{grid}"
            f"footer{{padding:20px 28px 40px;color:{c['muted']};font-size:13px}}footer a{{color:{c['accent']}}}"
            f"#lb{{position:fixed;inset:0;display:none;grid-template-rows:1fr auto;background:rgba(8,8,10,.96);z-index:1}}#lb.on{{display:grid}}"
            f"#lb img{{max-width:100%;max-height:100%;margin:auto;object-fit:contain;align-self:center;justify-self:center;width:auto;height:auto;padding:24px}}"
            f"#lb .meta{{padding:10px 24px 18px;color:#ddd;font-size:13px;text-align:center;min-height:44px}}"
            f"#lb button{{position:absolute;top:50%;width:52px;height:72px;margin-top:-36px;border:0;background:none;color:#fff;font-size:30px;cursor:pointer;opacity:.6}}"
            f"#lb button:hover{{opacity:1}}#lb .p{{left:4px}}#lb .n{{right:4px}}#lb .x{{top:28px;right:4px;margin:0;height:52px;font-size:24px}}")


JS = ("const L=document.getElementById('lb'),I=L.querySelector('img'),M=L.querySelector('.meta'),A=[...document.querySelectorAll('.c')];let k=0;"
      "function show(i){k=(i+A.length)%A.length;const a=A[k];I.src=a.href;I.alt=a.dataset.t||'';M.textContent=a.dataset.l||'';L.classList.add('on');}"
      "A.forEach((a,i)=>a.addEventListener('click',e=>{e.preventDefault();show(i);}));"
      "L.querySelector('.p').onclick=()=>show(k-1);L.querySelector('.n').onclick=()=>show(k+1);L.querySelector('.x').onclick=()=>L.classList.remove('on');"
      "document.addEventListener('keydown',e=>{if(!L.classList.contains('on'))return;if(e.key==='ArrowLeft')show(k-1);else if(e.key==='ArrowRight')show(k+1);else if(e.key==='Escape')L.classList.remove('on');});"
      "let sx=0;L.addEventListener('touchstart',e=>{sx=e.touches[0].clientX},{passive:true});L.addEventListener('touchend',e=>{const d=e.changedTouches[0].clientX-sx;if(Math.abs(d)>40)show(k+(d<0?1:-1));});")


def build_html(entries: list[dict], s: dict, thumb_url: Callable[[dict], str], large_url: Callable[[dict], str]) -> str:
    site = s["site"]
    e = html.escape
    cells = "".join(
        f'<a class="c" href="{e(large_url(it))}" style="--a:{it["aspect"]:.4f}" data-t="{e(it["title"])}" data-l="{e(" · ".join(x for x in (it["long"], it["exif"]) if x))}">'
        f'<img src="{e(thumb_url(it))}" alt="{e(it["title"] or it["name"])}" loading="lazy" decoding="async">{f"<span>{e(it["title"])}</span>" if it["title"] else ""}</a>'
        for it in entries)
    contact = ""
    if site.get("contact"):
        link = site.get("link") or ""
        href = link if link.startswith(("http://", "https://")) else f"mailto:{link}" if "@" in link else ""
        contact = f'<a href="{e(href)}">{e(site["contact"])}</a>' if href else e(site["contact"])
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<meta name=\"generator\" content=\"formlit\"><title>{e(site.get('title') or 'Photographs')}</title><style>{_css(s)}</style></head><body>"
            f"<header><h1>{e(site.get('title') or '')}</h1>{f'<h2>{e(site['collection'])}</h2>' if site.get('collection') else ''}"
            f"{f'<p>{e(site['description'])}</p>' if site.get('description') else ''}</header><main><div class=\"g\">{cells}</div></main>"
            f"<footer>{contact}</footer><div id=\"lb\" role=\"dialog\" aria-modal=\"true\"><img alt=\"\"><div class=\"meta\"></div>"
            "<button class=\"p\" aria-label=\"Previous\">&#8249;</button><button class=\"n\" aria-label=\"Next\">&#8250;</button><button class=\"x\" aria-label=\"Close\">&#215;</button></div>"
            f"<script>{JS}</script></body></html>")


def preview_html(ids: list[int], settings: dict, base: str = "") -> str:
    s = merged(settings)
    entries = items(ids, s)
    return build_html(entries, s, lambda it: f"{base}/api/photos/{it['id']}/preview", lambda it: f"{base}/api/photos/{it['id']}/preview")


def write_site(ids: list[int], settings: dict, folder: Path, progress: Callable[..., Any] | None = None) -> Path:
    s = merged(settings)
    entries = items(ids, s)
    (folder / "images" / "thumb").mkdir(parents=True, exist_ok=True)
    (folder / "images" / "large").mkdir(parents=True, exist_ok=True)
    cat = catalog_mod.get()
    wm = dict(export.DEFAULTS["watermark"], **(s.get("watermark") or {}))
    for i, it in enumerate(entries):
        rec = detail(cat, it["id"]) or {}
        meta = encode.filtered(rec, s.get("metadata", "copyright"), True, True)
        for kind, size in (("thumb", int(s["thumbSize"])), ("large", int(s["largeSize"]))):
            out = export.render_photo(it["id"], {"resize": True, "mode": "long", "value": size}, "srgb")
            if s.get("sharpen"):
                out = export.sharpen(out, {"on": True, "for": "screen", "amount": "standard"}, 96)
            if kind == "large":
                out = export.watermark(out, wm, rec)
            data = encode.encode(out, "jpeg", "srgb", int(s.get("quality", 82)), 8, 72, meta)
            (folder / "images" / kind / f"{it['n']:04d}.jpg").write_bytes(data)
        if progress is not None:
            if getattr(progress, "cancelled", False):
                break
            progress(i + 1, len(entries), f"Image {i + 1} of {len(entries)}")
    page = build_html(entries, s, lambda it: f"images/thumb/{it['n']:04d}.jpg", lambda it: f"images/large/{it['n']:04d}.jpg")
    (folder / "index.html").write_text(page, encoding="utf-8")
    (folder / "gallery.json").write_text(json.dumps({"generator": "formlit", "items": [{k: it[k] for k in ("n", "title", "long", "aspect")} for it in entries]}, indent=1))
    return folder / "index.html"


def _ftp(up: dict) -> ftplib.FTP:
    cls = ftplib.FTP_TLS if up.get("tls", True) else ftplib.FTP
    f = cls()
    f.connect(up["host"], int(up.get("port") or 21), timeout=30)
    f.login(up.get("user") or "anonymous", up.get("password") or "")
    if isinstance(f, ftplib.FTP_TLS):
        f.prot_p()
    return f


def _mkdirs(f: ftplib.FTP, path: str) -> None:
    cur = ""
    for part in [p for p in path.split("/") if p]:
        cur = f"{cur}/{part}"
        try:
            f.mkd(cur)
        except ftplib.error_perm:
            continue


def send_files(paths: list[Path], up: dict, progress: Callable[..., Any] | None = None) -> int:
    if not up.get("host"):
        raise RuntimeError("Set an FTP host first")
    f = _ftp(up)
    root = up.get("path") or "/"
    try:
        _mkdirs(f, root)
        for i, p in enumerate(paths):
            with p.open("rb") as fh:
                f.storbinary(f"STOR {posixpath.join(root, p.name)}", fh)
            if progress is not None:
                progress(i + 1, len(paths), f"Sending {i + 1} of {len(paths)}")
    finally:
        try:
            f.quit()
        except ftplib.all_errors:
            f.close()
    return len(paths)


def upload(folder: Path, up: dict, progress: Callable[..., Any] | None = None) -> int:
    if not up.get("host"):
        raise RuntimeError("Set an FTP host first")
    f = _ftp(up)
    files = [p for p in folder.rglob("*") if p.is_file()]
    root = up.get("path") or "/"
    try:
        for i, p in enumerate(files):
            remote = posixpath.join(root, p.relative_to(folder).as_posix())
            _mkdirs(f, posixpath.dirname(remote))
            with p.open("rb") as fh:
                f.storbinary(f"STOR {remote}", fh)
            if progress is not None:
                progress(i + 1, len(files), f"Uploading {i + 1} of {len(files)}")
    finally:
        try:
            f.quit()
        except ftplib.all_errors:
            f.close()
    return len(files)
