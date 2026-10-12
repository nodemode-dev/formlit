#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get("FORMLIT_MCP_URL", "http://127.0.0.1:8390/mcp")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_started = False
_agent = ""


def forward(line: str) -> str | None:
    global _agent
    try:
        msg = json.loads(line)
    except ValueError:
        return json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
    params = msg.get("params") or {}
    version = (params.get("_meta") or {}).get("io.modelcontextprotocol/protocolVersion") or params.get("protocolVersion") or "2025-11-25"
    info = params.get("clientInfo") if msg.get("method") == "initialize" else None
    if isinstance(info, dict) and (info.get("title") or info.get("name")):
        _agent = str(info.get("title") or info.get("name")).encode("ascii", "ignore").decode().strip()[:80]
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": version}
    if _agent:
        headers["x-formlit-agent"] = _agent
    req = urllib.request.Request(URL, data=line.encode(), method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=7200) as r:
            body = r.read().decode()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() or ""
    except (urllib.error.URLError, OSError) as exc:
        print(f"[formlit mcp] the engine is not answering at {URL}: {exc}", file=sys.stderr, flush=True)
        if start_engine():
            return forward(line)
        if msg.get("id") is None:
            return None
        return json.dumps({"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32000, "message": "The formlit engine is not running and could not be started: run ./formlit boot in the formlit folder, then retry."}})
    if msg.get("id") is None:
        return None
    return body.strip() or None


def start_engine() -> bool:
    global _started
    if _started or os.environ.get("FORMLIT_MCP_AUTOSTART", "1") == "0" or os.environ.get("FORMLIT_MCP_URL"):
        return False
    _started = True
    import subprocess
    import tempfile
    import time
    command = "serve" if os.path.isfile(os.path.join(ROOT, "frontend", "dist", "index.html")) else "backend"
    launcher = os.path.join(ROOT, "formlit.bat" if os.name == "nt" else "formlit")
    log = open(os.path.join(tempfile.gettempdir(), "formlit-engine.log"), "ab")
    print(f"[formlit mcp] starting the engine (formlit {command}); its log: {log.name}", file=sys.stderr, flush=True)
    kw = {"creationflags": 0x00000008} if os.name == "nt" else {"start_new_session": True}
    subprocess.Popen([launcher, command], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log, **kw)
    for _ in range(180):
        time.sleep(0.5)
        try:
            with urllib.request.urlopen(URL.rsplit("/mcp", 1)[0] + "/api/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            continue
    return False


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        out = forward(line)
        if out:
            sys.stdout.write(out + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
