import hmac
import json
import os
import secrets
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from app.core import config
from app.engine import terminal
from app.engine.commands import CommandError, command

TOKENS: dict[str, Path | None] = {}
INAPP_HEADER = "x-formlit-inapp"
INAPP_VAR = "FORMLIT_INAPP_TOKEN"
INSTALL_LINE = "irm https://claude.ai/install.ps1 | iex" if os.name == "nt" else "curl -fsSL https://claude.ai/install.sh | bash"

KEEP_ENV = {"CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CONFIG_DIR"}
CANDIDATES = (".claude/local/claude", ".local/bin/claude", ".npm-global/bin/claude", ".bun/bin/claude", ".volta/bin/claude")
SYSTEM_PATHS = ("/opt/homebrew/bin/claude", "/usr/local/bin/claude", "/usr/bin/claude")
INSTALL = "Claude Code is not installed: install it from https://claude.com/claude-code, run claude once in a terminal to sign in, then open it here again"
NOTE = ("You are Claude Code running in the terminal dock inside formlit, the photo library and raw developer open on this computer. "
        "Work on photos with the formlit MCP server's tools: start with get_catalog, then find_photos for ids, and look with get_preview before and after a change. "
        "They act on the catalog open in the window, the person sees every change happen, and each change is one undo step. "
        "Use the formlit-driving skill when it is available.")
_cache: dict = {"at": 0.0, "value": None}


def child_env() -> dict:
    return {k: v for k, v in terminal.base_env().items() if not k.startswith("CLAUDE") or k in KEEP_ENV}


def _from_login_shell() -> str | None:
    if os.name == "nt":
        return None
    shell = terminal.login_shell()
    try:
        out = subprocess.run(shell + ["-c", "command -v claude"], capture_output=True, text=True, timeout=10, env=child_env())
    except (OSError, subprocess.SubprocessError):
        return None
    found = out.stdout.strip().splitlines()[-1:] if out.returncode == 0 else []
    return found[0] if found and os.path.isabs(found[0]) else None


def _pref(key: str) -> str:
    from app.core import prefs
    value = prefs.load().get(key)
    return value.strip() if isinstance(value, str) else ""


def _runnable(path: str) -> bool:
    p = Path(path).expanduser()
    return p.is_file() and os.access(p, os.X_OK)


def cli() -> str | None:
    chosen = _pref("claudeBin")
    if chosen and _runnable(chosen):
        return str(Path(chosen).expanduser())
    found = os.environ.get("FORMLIT_CLAUDE_BIN") or shutil.which("claude")
    if found:
        return found
    home = Path.home()
    for p in [home / c for c in CANDIDATES] + [Path(s) for s in SYSTEM_PATHS]:
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    return _from_login_shell()


def info(fresh: bool = False) -> dict:
    if not fresh and _cache["value"] is not None and time.time() - _cache["at"] < 60:
        return _cache["value"]
    path, version = cli(), None
    if path:
        try:
            out = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=15, env=child_env())
            version = (out.stdout.strip().split() or [None])[0]
        except (OSError, subprocess.SubprocessError):
            path = None
    _cache["value"], _cache["at"] = {"installed": bool(path), "path": path, "version": version}, time.time()
    return _cache["value"]


def issue() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    folder = config.data_dir() / "AgentTokens"
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = folder / f"mcp-{secrets.token_hex(8)}.json"
    body = json.dumps({"mcpServers": {"formlit_tab": {"type": "http", "url": config.engine_url() + "/mcp", "headers": {"x-formlit-inapp": token}}}})
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(body)
    TOKENS[token] = path
    return token, str(path)


def issue_env() -> str:
    token = secrets.token_urlsafe(32)
    TOKENS[token] = None
    return token


def revoke(token: str) -> None:
    path = TOKENS.pop(token, None)
    if path is not None:
        try:
            path.unlink()
        except OSError:
            pass


def is_inapp(value) -> bool:
    if not isinstance(value, str) or not value:
        return False
    return any(hmac.compare_digest(value.encode("utf-8"), t.encode("utf-8")) for t in list(TOKENS))


def workdir() -> Path:
    raw = _pref("claudeFolder") or os.environ.get("FORMLIT_AGENT_DIR", "").strip()
    folder = Path(raw).expanduser() if raw else config.data_dir() / "Agent"
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise CommandError(f"Claude Code cannot start in {folder}: {e.strerror or e}; choose another folder in Preferences, AI agents", 400) from None
    return folder


def argv(path: str, prompt: str | None, resume: str | None, mcp_file: str) -> list[str]:
    cmd = [path, "--mcp-config", mcp_file, "--allowedTools", "mcp__formlit_tab", "--append-system-prompt", NOTE]
    if resume:
        cmd += ["--resume", resume]
    if prompt:
        cmd += ["--", prompt]
    if os.name == "nt":
        return cmd
    return terminal.login_shell() + ["-c", "exec " + shlex.join(cmd)]


@command("claudecode.status", "Claude Code", mutates=False,
         description="Whether the Claude Code CLI is installed (its path and version), the folder it starts in, and the terminal tab it runs in when open.")
def status() -> dict:
    tab = next((s.describe() for s in terminal.SESSIONS.values() if s.kind == "claude"), None)
    chosen = _pref("claudeBin")
    note = f"{chosen} is not a program formlit can run, so it uses the one found on this computer" if chosen and not _runnable(chosen) else ""
    return info(fresh=True) | {"folder": str(workdir()), "terminal": tab, "binNote": note, "firstMessage": _pref("claudeFirstMessage")}


@command("claudecode.open", "Open Claude Code", {"prompt": {"type": "string", "description": "a first message to start the session with"},
                                                  "cols": {"type": "integer"}, "rows": {"type": "integer"}, "fresh": {"type": "boolean"},
                                                  "resume": {"type": "string", "description": "a Claude Code session id to continue, such as the Chat tab's"}}, mutates=False,
         description="Starts the person's own Claude Code sign-in in a terminal tab of formlit's dock, connected to formlit's MCP tools without the outside-agent prompt. Reuses the running tab unless fresh is true or resume names a conversation to continue. The window only.")
def open_(prompt: str | None = None, cols: int | None = None, rows: int | None = None, fresh: bool | None = None, resume: str | None = None) -> dict:
    running = next((s for s in terminal.SESSIONS.values() if s.kind == "claude" and s.alive), None)
    if running is not None and not fresh and not resume:
        if prompt:
            terminal.write(running.id, prompt + "\r")
        return running.describe()
    found = info(fresh=True)
    if not found["installed"]:
        raise CommandError(INSTALL, 400)
    prompt = prompt or _pref("claudeFirstMessage") or None
    token, mcp_file = issue()
    try:
        session = terminal.open_session(str(workdir()), cols or 100, rows or 30, "Claude Code (from Chat)" if resume else "Claude Code", argv(found["path"], prompt, resume, mcp_file), child_env(), "claude")
    except BaseException:
        revoke(token)
        raise
    session.on_close.append(lambda: revoke(token))
    return session.describe()
