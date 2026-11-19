import json
import os
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from app.core import config
from app.engine import claude_code, terminal
from app.engine.commands import CommandError, command

PROGRAMS = {
    "codex": {"bin": "codex", "title": "Codex", "install": "npm install -g @openai/codex", "keys": ("OPENAI_API_KEY", "CODEX_API_KEY"), "ask": ("login", "status")},
    "cursor": {"bin": "cursor-agent", "title": "Cursor", "install": "curl https://cursor.com/install -fsS | bash", "keys": ("CURSOR_API_KEY",), "ask": ("status",)},
}
CLAUDE_KEYS = ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")
TAB_SERVER = "formlit_tab"
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_cache: dict = {"at": 0.0, "value": None}


def find(kind: str) -> str | None:
    binary = PROGRAMS[kind]["bin"]
    found = shutil.which(binary, path=terminal.base_env().get("PATH"))
    if found or os.name == "nt":
        return found
    try:
        out = subprocess.run(terminal.login_shell() + ["-c", f"command -v {shlex.quote(binary)}"], capture_output=True, text=True, timeout=10,
                             env=claude_code.child_env(), stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = out.stdout.strip().splitlines()[-1:] if out.returncode == 0 else []
    return lines[0] if lines and os.path.isabs(lines[0]) and os.access(lines[0], os.X_OK) else None


def _say(path: str, args: tuple) -> tuple[int, str]:
    try:
        out = subprocess.run([path, *args], capture_output=True, text=True, timeout=10, env=claude_code.child_env(), stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return out.returncode, _ANSI.sub("", out.stdout)


def _version(path: str) -> str | None:
    code, said = _say(path, ("--version",))
    return next((w for w in said.split() if w[:1].isdigit()), None) if code == 0 else None


def _signed_in(kind: str, path: str) -> bool | None:
    p = PROGRAMS[kind]
    if any(os.environ.get(k) for k in p["keys"]):
        return True
    said = _say(path, p["ask"])[1].lower()
    if "not logged in" in said or "not signed in" in said:
        return False
    return True if "logged in" in said or "signed in" in said else None


def _claude_signed_in(path: str) -> bool | None:
    if any(os.environ.get(k) for k in CLAUDE_KEYS):
        return True
    try:
        data = json.loads(_say(path, ("auth", "status"))[1])
    except ValueError:
        return None
    return bool(data.get("loggedIn")) if isinstance(data, dict) and "loggedIn" in data else None


def report(fresh: bool = False) -> dict:
    if not fresh and _cache["value"] is not None and time.time() - _cache["at"] < 60:
        return _cache["value"]
    found = claude_code.info(fresh=fresh)
    out = {"claude": {"installed": found["installed"], "path": found["path"], "version": found["version"],
                      "signedIn": _claude_signed_in(found["path"]) if found["installed"] else None, "install": claude_code.INSTALL_LINE, "title": "Claude Code"}}
    for kind, p in PROGRAMS.items():
        path = find(kind)
        out[kind] = {"installed": path is not None, "path": path, "version": _version(path) if path else None,
                     "signedIn": _signed_in(kind, path) if path else None, "install": p["install"], "title": p["title"]}
    _cache["value"], _cache["at"] = out, time.time()
    return out


def tab_command(kind: str, path: str) -> list[str]:
    if kind != "codex":
        return [path]
    return [path, "-c", f'mcp_servers.{TAB_SERVER}.url="{config.engine_url()}/mcp"',
            "-c", f'mcp_servers.{TAB_SERVER}.env_http_headers={{"{claude_code.INAPP_HEADER}"="{claude_code.INAPP_VAR}"}}']


def cursor_config(folder: str) -> None:
    path = Path(folder) / ".cursor" / "mcp.json"
    try:
        held = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        servers = held.get("mcpServers", {}) if isinstance(held, dict) else None
        if not isinstance(servers, dict):
            return
        held["mcpServers"] = servers | {TAB_SERVER: {"url": config.engine_url() + "/mcp", "headers": {claude_code.INAPP_HEADER: "${env:" + claude_code.INAPP_VAR + "}"}}}
        path.parent.mkdir(exist_ok=True)
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
            json.dump(held, f, indent=2)
        os.chmod(path, 0o600)
    except (OSError, ValueError):
        return


@command("terminal.agents", "Agent Programs", {"fresh": {"type": "boolean", "description": "look again instead of using the answer from the last minute"}}, mutates=False,
         description="Which agent programs formlit's dock can start (claude, codex, cursor): installed or not, the path, the version, signed in or not (null when formlit cannot tell) and the install line to paste. The window only.")
def agents_(fresh: bool | None = None) -> dict:
    return report(bool(fresh))


@command("terminal.openAgent", "Open an Agent Program", {"kind": {"type": "string", "enum": ["codex", "cursor"]}, "cols": {"type": "integer"}, "rows": {"type": "integer"}}, mutates=False,
         description="Starts Codex or Cursor's agent in a terminal tab of formlit's dock, connected to formlit's MCP tools without the outside-agent prompt through a token of its own that ends when the tab closes. The window only.")
def open_agent(kind: str, cols: int | None = None, rows: int | None = None) -> dict:
    p = PROGRAMS[kind]
    path = find(kind)
    if path is None:
        raise CommandError(f"{p['title']} is not installed. Install it with: {p['install']}", 400)
    folder = str(claude_code.workdir())
    line = tab_command(kind, path)
    argv = line if os.name == "nt" else terminal.login_shell() + ["-c", "exec " + shlex.join(line)]
    if kind == "cursor":
        cursor_config(folder)
    token = claude_code.issue_env()
    try:
        session = terminal.open_session(folder, cols or 100, rows or 30, p["title"], argv, terminal.base_env() | {claude_code.INAPP_VAR: token}, kind)
    except BaseException:
        claude_code.revoke(token)
        raise
    session.on_close.append(lambda: claude_code.revoke(token))
    return session.describe()
