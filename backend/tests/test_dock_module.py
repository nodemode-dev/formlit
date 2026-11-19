import importlib.util
import json
import os
import shutil
import stat

import pytest

from conftest import INAPP_HEADER, MCP_PATH, READ_TOOL, REPO, set_policy

STAND_IN = """#!/bin/sh
case "$1" in
  --version) echo "9.9.9 (stand-in)"; exit 0;;
  auth) echo '{"loggedIn": true}'; exit 0;;
esac
echo "stand-in started"
read line
"""


def sync_script():
    spec = importlib.util.spec_from_file_location("formlit_agents_sync", REPO / "setup" / "agents.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call(client, headers):
    hdrs = dict(headers)
    init = client.post(MCP_PATH, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}}}, headers=hdrs)
    if init.headers.get("mcp-session-id"):
        hdrs["mcp-session-id"] = init.headers["mcp-session-id"]
    r = client.post(MCP_PATH, json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": READ_TOOL[0], "arguments": READ_TOOL[1]}}, headers=hdrs)
    return r.json()["result"]


def test_the_shared_dock_folder_is_the_one_its_manifest_describes():
    sync = sync_script()
    assert sync.dock_module_drift() == []
    held = json.loads((sync.DOCK_MODULE / "MANIFEST.json").read_text(encoding="utf-8"))
    assert held["module"] == "dock" and held["version"] == "2.1.0"


def test_a_changed_or_foreign_file_in_the_dock_folder_is_named(tmp_path, monkeypatch):
    sync = sync_script()
    copy = tmp_path / "frontend" / "src" / "dock"
    shutil.copytree(sync.DOCK_MODULE, copy)
    monkeypatch.setattr(sync, "ROOT", tmp_path)
    monkeypatch.setattr(sync, "DOCK_MODULE", copy)
    assert sync.dock_module_drift() == []
    with open(copy / "keys.ts", "a", encoding="utf-8") as f:
        f.write("\n")
    assert sync.dock_module_drift() == ["frontend/src/dock/keys.ts"]
    shutil.copyfile(sync_script().DOCK_MODULE / "keys.ts", copy / "keys.ts")
    (copy / "extra.ts").write_text("import { q } from '../ui/dom';\n", encoding="utf-8")
    assert sync.dock_module_drift() == ["frontend/src/dock/extra.ts"]
    (copy / "extra.ts").unlink()
    (copy / "tour.ts").unlink()
    assert sync.dock_module_drift() == ["frontend/src/dock/tour.ts"]


def test_the_manifest_says_where_the_dock_sits_and_what_it_offers():
    dock = json.loads((REPO / "agents" / "manifest.json").read_text(encoding="utf-8"))["dock"]
    assert dock == {"present": True, "positions": ["bottom", "right"], "tabs": ["chat", "terminal", "claude-code", "codex", "cursor"]}


def test_a_caller_that_hangs_up_takes_its_question_with_it(client, monkeypatch):
    import asyncio

    from app.engine import agents, events
    from app.engine.commands import CommandError

    monkeypatch.setattr(agents, "POLL_SECONDS", 0.05)
    set_policy("ask")

    async def gone():
        return True

    with pytest.raises(CommandError):
        asyncio.run(agents.require("hanging agent", "http", {"tool": "get_catalog", "what": "use the tool get_catalog"}, gone))
    assert agents.status()["pending"] == []
    ended = [e for e in map(json.loads, events.recent()) if e["type"] == "agents.withdrawn"]
    assert ended[-1]["reason"] == "closed"


@pytest.mark.skipif(os.name == "nt", reason="the stand-in is a shell script")
def test_a_claude_code_tab_has_its_own_entry_and_its_token_ends_with_the_tab(client, tmp_path, monkeypatch):
    from app.engine import agents, claude_code, terminal

    script = tmp_path / "claude"
    script.write_text(STAND_IN)
    script.chmod(0o755)
    monkeypatch.setenv("FORMLIT_CLAUDE_BIN", str(script))
    monkeypatch.setattr(agents, "WAIT_SECONDS", 1)
    monkeypatch.setattr(agents, "POLL_SECONDS", 0.05)
    set_policy("ask")
    before = set(claude_code.TOKENS)
    reply = client.post("/api/commands/claudecode.open", json={"cols": 80, "rows": 20})
    assert reply.status_code == 200 and reply.json()["result"]["kind"] == "claude"
    tab = reply.json()["result"]["id"]
    (token,) = set(claude_code.TOKENS) - before
    held = claude_code.TOKENS[token]
    assert stat.S_IMODE(os.stat(held).st_mode) == 0o600
    assert list(json.loads(held.read_text(encoding="utf-8"))["mcpServers"]) == ["formlit_tab"]
    assert all(token not in part for part in terminal.SESSIONS[tab].argv)
    assert "mcp__formlit_tab" in " ".join(terminal.SESSIONS[tab].argv)
    assert not call(client, {INAPP_HEADER: token}).get("isError")
    set_policy("blocked")
    assert agents.BLOCKED in call(client, {INAPP_HEADER: token})["content"][0]["text"]
    set_policy("ask")
    assert client.post("/api/commands/terminal.close", json={"id": tab}).status_code == 200
    assert not claude_code.is_inapp(token) and not held.exists()
    assert call(client, {INAPP_HEADER: token}).get("isError")
