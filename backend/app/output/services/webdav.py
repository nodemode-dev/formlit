import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

SERVICE = {
    "kind": "webdav",
    "label": "WebDAV or Nextcloud",
    "version": "1.0.0",
    "author": "formlit",
    "description": "Publishes to any WebDAV folder: Nextcloud, ownCloud, a NAS, Apache or nginx. Comments sync both ways on Nextcloud and ownCloud.",
    "help": "Use the folder's WebDAV address. On Nextcloud that is https://host/remote.php/dav/files/USER/Photos, signed in with an app password.",
    "comments": True,
    "fields": [
        {"path": "url", "label": "Folder URL", "kind": "text", "placeholder": "https://cloud.example.com/remote.php/dav/files/me/Photos"},
        {"path": "user", "label": "Username", "kind": "text"},
        {"path": "password", "label": "Password", "kind": "password"},
    ],
}
NS = {"d": "DAV:", "oc": "http://owncloud.org/ns"}
FILEID = '<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:prop><oc:fileid/></d:prop></d:propfind>'
FILTER = '<?xml version="1.0"?><oc:filter-comments xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><oc:limit>200</oc:limit><oc:offset>0</oc:offset></oc:filter-comments>'


def _ok(r: httpx.Response, *codes: int) -> httpx.Response:
    if r.status_code not in codes:
        raise RuntimeError(f"{r.request.method} {r.request.url.path} answered {r.status_code} {r.reason_phrase}")
    return r


def _text(node: ET.Element, tag: str) -> str:
    n = node.find(f".//{tag}", NS)
    return (n.text or "").strip() if n is not None else ""


def _iso(t: str) -> str:
    try:
        return parsedate_to_datetime(t).isoformat()
    except (TypeError, ValueError):
        return t


class Client:
    def __init__(self, s: dict):
        url = str(s.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            raise RuntimeError("Set the WebDAV folder URL in the service settings")
        self.root = url.rstrip("/")
        self.http = httpx.Client(auth=(str(s.get("user") or ""), str(s.get("password") or "")), timeout=120, follow_redirects=True)
        self.made: set[str] = set()

    def _url(self, *parts: str) -> str:
        return self.root + "".join("/" + quote(p, safe="") for p in parts)

    def _mkcol(self, folders: list[str]) -> None:
        for i in range(len(folders) + 1):
            u = self._url(*folders[:i])
            if u not in self.made:
                _ok(self.http.request("MKCOL", u), 200, 201, 301, 405)
                self.made.add(u)

    def upload(self, path: Path, folders: list[str], photo: dict, old: str) -> str:
        self._mkcol(folders)
        u = self._url(*folders, path.name)
        _ok(self.http.put(u, content=path.read_bytes()), 200, 201, 204)
        return u

    def delete(self, remote: str) -> None:
        _ok(self.http.delete(remote), 200, 204, 404)

    def _thread(self, remote: str) -> str:
        parts = urlsplit(remote)
        i = parts.path.find("/remote.php/dav/")
        if i < 0:
            raise RuntimeError("Comments need a Nextcloud or ownCloud server")
        r = _ok(self.http.request("PROPFIND", remote, headers={"Depth": "0", "Content-Type": "application/xml"}, content=FILEID), 207)
        fid = _text(ET.fromstring(r.content), "oc:fileid")
        if not fid:
            raise RuntimeError("The server did not report a file id")
        return urlunsplit((parts.scheme, parts.netloc, f"{parts.path[:i]}/remote.php/dav/comments/files/{fid}", "", ""))

    def comments(self, remote: str) -> list[dict]:
        if "/remote.php/dav/" not in urlsplit(remote).path:
            return []
        r = _ok(self.http.request("REPORT", self._thread(remote), headers={"Content-Type": "application/xml"}, content=FILTER), 207)
        out = []
        for resp in ET.fromstring(r.content).findall("d:response", NS):
            msg = _text(resp, "oc:message")
            if msg:
                out.append({"id": _text(resp, "oc:id"), "author": _text(resp, "oc:actorDisplayName") or _text(resp, "oc:actorId"), "text": msg, "time": _iso(_text(resp, "oc:creationDateTime"))})
        out.sort(key=lambda c: c["time"])
        return out

    def comment(self, remote: str, text: str) -> None:
        _ok(self.http.post(self._thread(remote), json={"actorType": "users", "verb": "comment", "message": text}), 200, 201)

    def close(self) -> None:
        self.http.close()


def connect(settings: dict) -> Client:
    return Client(settings)
