#!/usr/bin/env python3
"""./formlit cli: the engine's commands from a terminal.

  list [group]                 every command id, or one group (library, develop, photo, ai, export, print, ...)
  describe <id>                a command's parameters
  run <id> [key=value ...]     runs a command; values are JSON when they parse (ids=[1,2] rating=5 flag=pick)
  <id> [key=value ...]         the same, without the word run
  --json '{...}'               passes the parameters as one JSON object instead
"""

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("FORMLIT_URL", "http://127.0.0.1:8390")


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=7200) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode() or "{}")
        except ValueError:
            return exc.code, {"ok": False, "error": str(exc)}
    except (urllib.error.URLError, OSError) as exc:
        print(f"formlit: the engine is not answering at {BASE} ({exc}). Start it with ./formlit backend or ./formlit boot.", file=sys.stderr)
        sys.exit(3)


def parse(args: list[str]) -> dict:
    if "--json" in args:
        i = args.index("--json")
        return json.loads(args[i + 1])
    out: dict = {}
    for a in args:
        if "=" not in a:
            raise SystemExit(f"formlit: expected key=value, got {a}")
        k, v = a.split("=", 1)
        try:
            out[k] = json.loads(v)
        except ValueError:
            out[k] = v
    return out


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if argv[0] == "list":
        _, body = call("GET", "/api/commands" + (f"?group={argv[1]}" if len(argv) > 1 else ""))
        for c in body.get("commands", []):
            print(f"{c['id']:<28} {c['label']}{'' if c['mutates'] else '  (read only)'}")
        print(f"\n{body.get('count', 0)} commands")
        return 0
    if argv[0] == "describe" and len(argv) > 1:
        status, body = call("GET", f"/api/commands/{argv[1]}")
        print(json.dumps(body, indent=2))
        return 0 if status == 200 else 1
    if argv[0] == "run":
        argv = argv[1:]
    if not argv:
        print(__doc__)
        return 2
    status, body = call("POST", f"/api/commands/{argv[0]}", parse(argv[1:]))
    print(json.dumps(body.get("result", body) if body.get("ok") else body, indent=2, default=str))
    return 0 if status == 200 and body.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
