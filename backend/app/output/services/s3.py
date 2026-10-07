import datetime
import hashlib
import hmac
import mimetypes
import posixpath
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx

SERVICE = {
    "kind": "s3",
    "label": "S3-Compatible Storage",
    "version": "1.0.0",
    "author": "formlit",
    "description": "Publishes to Amazon S3 or any S3-compatible store: Cloudflare R2, Backblaze B2, Wasabi, MinIO. Requests are signed with AWS Signature Version 4.",
    "help": "Give the endpoint and region of the bucket and an access key that may put and delete objects under the prefix.",
    "comments": False,
    "fields": [
        {"path": "endpoint", "label": "Endpoint", "kind": "text", "placeholder": "https://s3.us-east-1.amazonaws.com"},
        {"path": "region", "label": "Region", "kind": "text", "placeholder": "us-east-1"},
        {"path": "bucket", "label": "Bucket", "kind": "text"},
        {"path": "prefix", "label": "Key prefix", "kind": "text", "placeholder": "photos/"},
        {"path": "accessKey", "label": "Access key", "kind": "text"},
        {"path": "secretKey", "label": "Secret key", "kind": "password"},
        {"path": "style", "label": "Addressing", "kind": "seg", "options": [["path", "Path"], ["virtual", "Virtual host"]]},
        {"path": "publicRead", "label": "Public read", "kind": "check"},
    ],
}


def _h(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


class Client:
    def __init__(self, s: dict):
        self.endpoint = str(s.get("endpoint") or "").strip().rstrip("/")
        self.bucket = str(s.get("bucket") or "").strip()
        if not self.endpoint.startswith(("http://", "https://")) or not self.bucket:
            raise RuntimeError("Set the endpoint and bucket in the service settings")
        self.region = str(s.get("region") or "us-east-1").strip()
        self.prefix = str(s.get("prefix") or "").strip().strip("/")
        self.access = str(s.get("accessKey") or "")
        self.secret = str(s.get("secretKey") or "")
        self.virtual = s.get("style") == "virtual"
        self.public = bool(s.get("publicRead"))
        self.http = httpx.Client(timeout=120)

    def _loc(self, key: str) -> tuple[str, str]:
        u = urlsplit(self.endpoint)
        base = u.path.rstrip("/")
        if self.virtual:
            return f"{self.bucket}.{u.netloc}", f"{base}/{quote(key, safe='/~')}"
        return u.netloc, f"{base}/{quote(self.bucket, safe='')}/{quote(key, safe='/~')}"

    def _send(self, method: str, key: str, body: bytes = b"", extra: dict | None = None) -> httpx.Response:
        host, path = self._loc(key)
        amz = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        payload = hashlib.sha256(body).hexdigest()
        headers = {"host": host, "x-amz-content-sha256": payload, "x-amz-date": amz, **{k.lower(): str(v) for k, v in (extra or {}).items()}}
        names = sorted(headers)
        signed = ";".join(names)
        canon = "\n".join([method, path, "", "".join(f"{k}:{headers[k].strip()}\n" for k in names), signed, payload])
        scope = f"{amz[:8]}/{self.region}/s3/aws4_request"
        sts = "\n".join(["AWS4-HMAC-SHA256", amz, scope, hashlib.sha256(canon.encode()).hexdigest()])
        k = _h(_h(_h(_h(f"AWS4{self.secret}".encode(), amz[:8]), self.region), "s3"), "aws4_request")
        headers["authorization"] = f"AWS4-HMAC-SHA256 Credential={self.access}/{scope}, SignedHeaders={signed}, Signature={hmac.new(k, sts.encode(), hashlib.sha256).hexdigest()}"
        scheme = urlsplit(self.endpoint).scheme
        r = self.http.request(method, f"{scheme}://{host}{path}", content=body, headers=headers)
        if r.status_code >= 300 and not (method == "DELETE" and r.status_code == 404):
            raise RuntimeError(f"{method} {key} answered {r.status_code}: {r.text[:200]}")
        return r

    def upload(self, path: Path, folders: list[str], photo: dict, old: str) -> str:
        key = posixpath.join(*([self.prefix] if self.prefix else []), *folders, path.name)
        extra = {"content-type": mimetypes.guess_type(path.name)[0] or "application/octet-stream"}
        if self.public:
            extra["x-amz-acl"] = "public-read"
        self._send("PUT", key, path.read_bytes(), extra)
        return key

    def delete(self, remote: str) -> None:
        self._send("DELETE", remote)

    def close(self) -> None:
        self.http.close()


def connect(settings: dict) -> Client:
    return Client(settings)
