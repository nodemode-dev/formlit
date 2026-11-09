import json
import shutil
from pathlib import Path
from typing import Any

from app.core import config
from app.engine import catalog as catalog_mod
from app.engine import events
from app.engine.commands import CommandError, command

DEMOS = {"library": "Library and Develop", "develop": "Masks and Presets", "share": "Map, Book, Slideshow, Print and Web"}


def media_root() -> Path:
    dist = config.dist_dir()
    for base in ([dist / "demos"] if dist else []) + [config.REPO_DIR / "frontend" / "public" / "demos"]:
        if (base / "library" / "demo.json").is_file():
            return base
    raise CommandError("The demo photos are not in this build of formlit")


def _folder(name: str) -> Path:
    base = config.data_dir() / "Demos"
    n = 1
    while (base / (name if n == 1 else f"{name} {n}")).exists():
        n += 1
    return base / (name if n == 1 else f"{name} {n}")


def _build(spec: dict, root: Path, folder: Path) -> dict:
    from app.engine import cmd_develop, cmd_library, cmd_output
    photos = folder / "Photos"
    photos.mkdir(parents=True)
    for p in spec["photos"]:
        shutil.copyfile(root / spec["files"][p["file"]], photos / p["file"])
    cmd_library._switch_catalog((folder / f"{spec['name']}.fldb").resolve(), publish=False)
    c = cmd_library.cat()
    cmd_library.do_import([str(photos)], mode="add", wait=True)
    ids = {str(r["file_name"]): int(r["id"]) for r in c.rows("SELECT id, file_name FROM photos")}
    missing = [p["file"] for p in spec["photos"] if p["file"] not in ids]
    if missing:
        raise CommandError(f"The demo could not import {', '.join(missing)}")
    for key, rel in (spec.get("bitmaps") or {}).items():
        pid = ids.get(key.rsplit("_", 1)[0] + ".jpg")
        if pid is not None:
            target = config.masks_dir() / str(pid) / f"{key}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / rel, target)
    cols = {}
    for col in spec.get("collections") or []:
        members = [ids[p["file"]] for p in spec["photos"] if p.get("collection") == col["id"]]
        cols[col["id"]] = cmd_library.collection_create(col["name"], ids=members)
    flags = {1: "pick", -1: "reject"}
    for p in spec["photos"]:
        pid = [ids[p["file"]]]
        if p.get("rating"):
            cmd_library.rate(pid, rating=int(p["rating"]))
        if p.get("flag") in flags:
            cmd_library.flag(pid, flags[p["flag"]])
        if p.get("label"):
            cmd_library.label(pid, p["label"], toggle=False)
        if p.get("keywords"):
            cmd_library.set_keywords(pid, p["keywords"])
        if p.get("meta"):
            cmd_library.set_meta(pid, p["meta"])
        if p.get("gps"):
            cmd_output.photo_set_gps(pid, lat=float(p["gps"][0]), lon=float(p["gps"][1]))
        for e in p.get("edits") or []:
            cmd_develop.update(pid, e["patch"], e["label"])
    for loc in spec.get("locations") or []:
        cmd_output.location_save(loc["name"], loc["lat"], loc["lon"], loc.get("radius", 0.2), bool(loc.get("private")))
    order = [ids[p["file"]] for p in spec["photos"]]
    music = None
    if spec.get("music"):
        music = folder / "Demo Music" / Path(spec["music"]).name
        music.parent.mkdir(parents=True)
        shutil.copyfile(root / spec["music"], music)
    for out in spec.get("outputs") or []:
        pids = [order[i - 1] for i in out["photos"] if 0 < i <= len(order)]
        settings = dict(out["settings"])
        if out["kind"] == "book":
            texts = settings.pop("coverTexts", ["", ""])
            settings["cover"] = {"template": "cover", "photos": pids[:1], "texts": texts}
            settings["pages"] = cmd_output.book_auto(pids[1:])["pages"]
        if out["kind"] == "slideshow" and music is not None:
            settings["music"] = {**(settings.get("music") or {}), "path": str(music)}
        cmd_library.collection_create(out["name"], kind=out["kind"], ids=pids, settings=settings)
    c.undo_stack.clear()
    c.redo_stack.clear()
    return {"photos": len(ids), "collections": len(cols) + len(spec.get("outputs") or [])}


@command("demo.open", "Open Demo", {"id": {"type": "string", "enum": list(DEMOS)}},
         description="Opens one of formlit's demos (library, develop or share) as a new demo catalog with its sample photos, in its own folder under Demos; the person's own catalog is not changed and stays in File > Open Catalog's recent list.")
def demo_open(id: str = "library") -> dict:
    if id not in DEMOS:
        raise CommandError(f"No demo called {id}; the demos are {', '.join(DEMOS)}")
    root = media_root()
    spec = json.loads((root / id / "demo.json").read_text())
    previous = config.catalog_path()
    folder = _folder(spec["name"])
    try:
        made = _build(spec, root, folder)
    except Exception:
        from app.engine import cmd_library
        if catalog_mod.get().path != previous and previous.is_file():
            cmd_library._switch_catalog(previous, publish=False)
        shutil.rmtree(folder, ignore_errors=True)
        raise
    path = (folder / f"{spec['name']}.fldb").resolve()
    events.publish("catalog.changed", path=str(path), name=path.stem, demo=id)
    return {"demo": id, "title": DEMOS[id], "catalog": str(path), "previous": str(previous), **made}
