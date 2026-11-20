import json
import os
import re
import subprocess
import time
from pathlib import Path

from app.core import config
from app.engine import agent_lookup, claude_code, terminal
from app.engine.commands import CommandError, command

PROGRAMS = {
    "codex": {"bin": "codex", "title": "Codex", "install": "npm install -g @openai/codex", "keys": ("OPENAI_API_KEY", "CODEX_API_KEY"), "ask": ("login", "status")},
    "cursor": {"bin": "cursor-agent", "title": "Cursor", "install": "curl https://cursor.com/install -fsS | bash", "keys": ("CURSOR_API_KEY",), "ask": ("status",)},
    "antigravity": {"bin": "agy", "title": "Antigravity", "install": agent_lookup.install("antigravity"), "keys": (), "ask": ()},
}
TABS = ("codex", "cursor", "antigravity")
CLAUDE_KEYS = ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")
TAB_SERVER = "formlit_tab"
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_cache: dict = {"at": 0.0, "value": None}


def find(kind: str) -> str | None:
    return claude_code.located(kind).path


def _say(path: str, args: tuple) -> tuple[int, str]:
    try:
        out = agent_lookup.run([path, *args], claude_code.child_env(path), 10)
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return out.returncode, _ANSI.sub("", out.stdout)


def _signed_in(kind: str, path: str) -> bool | None:
    p = PROGRAMS[kind]
    if not p["ask"]:
        return None
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
    out = {"claude": found | {"signedIn": _claude_signed_in(found["path"]) if found["installed"] else None, "install": claude_code.INSTALL_LINE, "title": "Claude Code"}}
    for kind, p in PROGRAMS.items():
        got = claude_code.located(kind, fresh)
        out[kind] = agent_lookup.answer(got, p["install"], claude_code.otherwise(kind)) | {
            "signedIn": _signed_in(kind, got.path) if got.state == "runs" else None, "install": p["install"], "title": p["title"]}
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


def tab_folder(kind: str) -> Path:
    folder = config.data_dir() / "agent-tabs" / kind
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _tab_file(folder: Path) -> Path:
    return folder / ".agents" / "mcp_config.json"


def _tab_servers(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8") or "{}") if path.exists() else {}
    if not isinstance(data, dict) or not isinstance(data.get("mcpServers", {}), dict):
        raise OSError(f"{path} is not an MCP servers file formlit can read, so it was left alone")
    return data


def _tab_replace(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + f".part-{os.getpid()}")
    with os.fdopen(os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=2) + "\n")
    os.replace(part, path)


def write_tab_entry(folder: Path, token: str) -> None:
    path = _tab_file(folder)
    data = _tab_servers(path)
    data.setdefault("mcpServers", {})[TAB_SERVER] = {"serverUrl": config.engine_url() + "/mcp", "headers": {claude_code.INAPP_HEADER: token}}
    _tab_replace(path, data)


def remove_tab_entry(folder: Path, token: str) -> None:
    path = _tab_file(folder)
    try:
        data = _tab_servers(path)
        entry = data.get("mcpServers", {}).get(TAB_SERVER)
        if not isinstance(entry, dict) or (entry.get("headers") or {}).get(claude_code.INAPP_HEADER) != token:
            return
        del data["mcpServers"][TAB_SERVER]
        _tab_replace(path, data)
    except (OSError, ValueError):
        return


@command("terminal.agents", "Agent Programs", {"fresh": {"type": "boolean", "description": "look again instead of using the answer from the last minute"}}, mutates=False,
         description="Which agent programs formlit's dock can start (claude, codex, cursor, antigravity): installed or not, the path, the version, signed in or not (null when formlit cannot tell) and the install line to paste. The window only.")
def agents_(fresh: bool | None = None) -> dict:
    return report(bool(fresh))


@command("terminal.openAgent", "Open an Agent Program", {"kind": {"type": "string", "enum": ["codex", "cursor", "antigravity"]}, "cols": {"type": "integer"}, "rows": {"type": "integer"}}, mutates=False,
         description="Starts Codex, Cursor's agent or Antigravity in a terminal tab of formlit's dock, connected to formlit's MCP tools without the outside-agent prompt through a token of its own that ends when the tab closes. The window only.")
def open_agent(kind: str, cols: int | None = None, rows: int | None = None) -> dict:
    if kind not in TABS:
        raise CommandError(f"No agent program called {kind}", 400)
    p = PROGRAMS[kind]
    found = claude_code.usable(kind)
    if found.state != "runs":
        raise CommandError(claude_code.said(found), 400)
    path = found.path
    own = tab_folder(kind) if kind == "antigravity" else None
    folder = str(own or claude_code.workdir())
    argv = agent_lookup.start_argv(tab_command(kind, path))
    if kind == "cursor":
        cursor_config(folder)
    token = claude_code.issue_env()
    try:
        if own:
            write_tab_entry(own, token)
        session = terminal.open_session(folder, cols or 100, rows or 30, p["title"], argv, claude_code.child_env(path) | {claude_code.INAPP_VAR: token}, kind)
    except BaseException:
        claude_code.revoke(token)
        if own:
            remove_tab_entry(own, token)
        raise
    session.on_close.append(lambda: claude_code.revoke(token))
    if own:
        session.on_close.append(lambda: remove_tab_entry(own, token))
    return session.describe()
