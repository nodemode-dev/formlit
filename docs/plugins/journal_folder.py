import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

SERVICE = {
    "kind": "journal-folder",
    "label": "Journal Folder (example)",
    "version": "1.0.0",
    "author": "formlit",
    "url": "https://github.com/nodemode-ai/formlit/blob/main/docs/plugins/journal_folder.py",
    "description": "Example plug-in: copies published photos into a folder, keeps an index.json of titles and keywords, and stores comments beside it.",
    "help": "Copy this file into the Plugins folder, then press Reload in the Plug-in Manager.",
    "comments": True,
    "api": 1,
    "fields": [
        {"path": "folder", "label": "Folder", "kind": "text", "placeholder": "~/Pictures/Journal"},
        {"path": "author", "label": "Comment as", "kind": "text", "placeholder": "Me"},
    ],
}


class Client:
    def __init__(self, settings: dict):
        folder = str(settings.get("folder") or "").strip()
        if not folder:
            raise RuntimeError("Choose a folder for the journal")
        self.root = Path(folder).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)
        self.author = str(settings.get("author") or "Me")
        self.index_path = self.root / "index.json"
        self.index = json.loads(self.index_path.read_text("utf-8")) if self.index_path.is_file() else {"photos": {}, "comments": {}}

    def _save(self) -> None:
        self.index_path.write_text(json.dumps(self.index, indent=2), "utf-8")

    def upload(self, path: Path, folders: list[str], photo: dict, old: str) -> str:
        dest = self.root.joinpath(*folders, path.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        key = dest.relative_to(self.root).as_posix()
        self.index["photos"][key] = {"title": photo.get("title", ""), "caption": photo.get("caption", ""), "keywords": photo.get("keywords", [])}
        if old and old != key:
            self.index["comments"][key] = self.index["comments"].pop(old, [])
        self._save()
        return key

    def delete(self, remote: str) -> None:
        (self.root / remote).unlink(missing_ok=True)
        self.index["photos"].pop(remote, None)
        self._save()

    def comments(self, remote: str) -> list[dict]:
        return list(self.index["comments"].get(remote, []))

    def comment(self, remote: str, text: str) -> None:
        self.index["comments"].setdefault(remote, []).append({"author": self.author, "text": text, "time": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        self._save()


def connect(settings: dict) -> Client:
    return Client(settings)
