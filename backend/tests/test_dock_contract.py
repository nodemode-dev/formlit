import json
import os
import stat
import threading
import time

import pytest

from conftest import ENGINE_PORT, INAPP_HEADER, MCP_PATH, READ_TOOL, set_policy

HOST = {"host": f"127.0.0.1:{ENGINE_PORT}"}
STAND_IN = """#!/bin/sh
case "$1" in
  --version) echo "9.9.9 (stand-in)"; exit 0;;
  auth) echo '{"loggedIn": true}'; exit 0;;
  login) echo "Logged in using ChatGPT"; exit 0;;
  status) echo "Not logged in"; exit 0;;
esac
echo "stand-in started"
read line
"""


def agents():
    from app.engine import agents as mod

    return mod


def call(client, tool, name="family-test-agent", headers=None):
    hdrs = dict(headers or {})
    init = client.post(MCP_PATH, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": name, "version": "1"}}}, headers=hdrs)
    if init.headers.get("mcp-session-id"):
        hdrs["mcp-session-id"] = init.headers["mcp-session-id"]
    r = client.post(MCP_PATH, json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool[0], "arguments": tool[1]}}, headers=hdrs)
    assert r.status_code == 200, r.text
    return r.json()["result"]


def text_of(result):
    return " ".join(c.get("text", "") for c in result.get("content", []) if isinstance(c, dict))


def waiting_call(client, tool=READ_TOOL, name="family-test-agent", count=1):
    out = {}
    t = threading.Thread(target=lambda: out.update(result=call(client, tool, name)))
    t.start()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and len(agents().status()["pending"]) < count:
        time.sleep(0.05)
    assert len(agents().status()["pending"]) == count
    return t, out


def run(client, cid, params=None):
    return client.post(f"/api/commands/{cid}", json=params or {})


def seen(kind):
    from app.engine import events

    return [e for e in map(json.loads, events.recent()) if e["type"] == kind]


@pytest.fixture(autouse=True)
def fast_and_reset(monkeypatch):
    a = agents()
    monkeypatch.setattr(a, "WAIT_SECONDS", 20)
    monkeypatch.setattr(a, "POLL_SECONDS", 0.05)
    set_policy("ask")
    yield
    set_policy("ask")


@pytest.fixture
def stand_ins(tmp_path, monkeypatch):
    folder = tmp_path / "bin"
    folder.mkdir()
    for name in ("claude", "codex", "cursor-agent"):
        script = folder / name
        script.write_text(STAND_IN)
        script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.delenv("FORMLIT_CLAUDE_BIN", raising=False)
    for key in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "OPENAI_API_KEY", "CODEX_API_KEY", "CURSOR_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    return folder


@pytest.fixture
def none_found(monkeypatch):
    from app.engine import agent_programs

    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setattr(agent_programs.terminal, "login_shell", lambda: ["/bin/sh", "-c", "exit 1", "--"])


def test_the_question_says_who_asks_for_what_and_which_answers_it_takes(client):
    t, out = waiting_call(client, ("run_command", {"command": "library.tree"}))
    item = agents().status()["pending"][0]
    event = seen("agents.consent")[-1]
    run(client, "agents.respond", {"choice": "later", "request": item["request"]})
    t.join(15)
    for asked in (item, event):
        assert asked["client"] == asked["agent"] == "family-test-agent" and asked["channel"] == "http"
        assert asked["request"] == item["request"] and asked["tool"] == "run_command" and asked["command"] == "library.tree"
        assert asked["what"].startswith("run the command ") and asked["answers"] == ["deny", "once", "always"] and asked["alwaysCovers"] == "all"
        assert asked["expiresIn"] == 20 and asked["expiresAt"] == pytest.approx(asked["since"] + 20)
    assert agents().LATER in text_of(out["result"])


def test_once_runs_this_call_and_the_next_one_asks_again(client):
    a = agents()
    t, out = waiting_call(client)
    first = a.status()["pending"][0]["request"]
    assert first and a.status()["pending"][0]["what"] == f"use the tool {READ_TOOL[0]}"
    reply = run(client, "agents.respond", {"choice": "once", "request": first})
    assert reply.status_code == 200 and reply.json()["result"] == {"outsideAgents": "ask", "choice": "once"}
    t.join(15)
    assert not out["result"].get("isError") and a.setting() == "ask"
    assert run(client, "agents.respond", {"choice": "once", "request": first}).status_code == 409
    t, out = waiting_call(client)
    second = a.status()["pending"][0]["request"]
    assert second != first
    run(client, "agents.respond", {"choice": "later", "request": second})
    t.join(15)
    assert a.LATER in text_of(out["result"])


def test_once_needs_the_request_it_answers(client):
    reply = run(client, "agents.respond", {"choice": "once"})
    assert reply.status_code == 400 and reply.json()["error"] == agents().ONCE_NEEDS
    assert run(client, "agents.respond", {"choice": "once", "request": "r0"}).status_code == 409
    assert agents().setting() == "ask"


def test_an_answer_with_a_request_leaves_the_other_waiting_call_alone(client):
    a = agents()
    t1, out1 = waiting_call(client, name="first-agent")
    t2, out2 = waiting_call(client, name="second-agent", count=2)
    pending = a.status()["pending"]
    assert [p["agent"] for p in pending] == ["first-agent", "second-agent"]
    run(client, "agents.respond", {"choice": "once", "request": pending[0]["request"]})
    t1.join(15)
    assert not out1["result"].get("isError")
    assert [p["request"] for p in a.status()["pending"]] == [pending[1]["request"]]
    run(client, "agents.respond", {"choice": "later"})
    t2.join(15)
    assert a.LATER in text_of(out2["result"])


def test_every_window_is_told_when_a_question_ends(client, monkeypatch):
    a = agents()
    t, _ = waiting_call(client)
    answered = a.status()["pending"][0]["request"]
    run(client, "agents.respond", {"choice": "later"})
    t.join(15)
    assert {"request": answered, "reason": "answered"}.items() <= seen("agents.withdrawn")[-1].items()
    monkeypatch.setattr(a, "WAIT_SECONDS", 0.6)
    t, out = waiting_call(client)
    expired = a.status()["pending"][0]["request"]
    t.join(15)
    assert a.WAITING in text_of(out["result"])
    assert {"request": expired, "reason": "expired"}.items() <= seen("agents.withdrawn")[-1].items()


@pytest.mark.skipif(os.name == "nt", reason="the stand-ins are shell scripts")
def test_one_call_reports_the_three_agent_programs(client, stand_ins):
    found = run(client, "terminal.agents", {"fresh": True}).json()["result"]
    assert set(found) == {"claude", "codex", "cursor"}
    for kind, binary, signed in (("claude", "claude", True), ("codex", "codex", True), ("cursor", "cursor-agent", False)):
        assert found[kind] == found[kind] | {"installed": True, "path": str(stand_ins / binary), "version": "9.9.9", "signedIn": signed}
        assert found[kind]["install"] and found[kind]["title"]


def test_a_missing_program_comes_with_its_install_line(client, none_found):
    found = run(client, "terminal.agents", {"fresh": True}).json()["result"]
    for kind in ("codex", "cursor"):
        assert found[kind] == found[kind] | {"installed": False, "path": None, "version": None, "signedIn": None}
        assert found[kind]["install"]
    reply = run(client, "terminal.openAgent", {"kind": "codex"})
    assert reply.status_code == 400 and "not installed" in reply.json()["error"]
    assert run(client, "terminal.openAgent", {"kind": "vim"}).status_code == 400


@pytest.mark.skipif(os.name == "nt", reason="the stand-ins are shell scripts")
@pytest.mark.parametrize("kind", ["codex", "cursor"])
def test_a_program_tab_has_a_token_of_its_own_that_ends_with_the_tab(client, stand_ins, kind):
    from app.engine import agent_programs, claude_code, terminal

    reply = run(client, "terminal.openAgent", {"kind": kind, "cols": 80, "rows": 20})
    assert reply.status_code == 200 and reply.json()["result"]["kind"] == kind
    session = terminal.SESSIONS[reply.json()["result"]["id"]]
    token = session.env[claude_code.INAPP_VAR]
    assert claude_code.is_inapp(token) and all(token not in part for part in session.argv)
    if kind == "codex":
        assert claude_code.INAPP_VAR in session.argv[-1] and agent_programs.TAB_SERVER in session.argv[-1]
    else:
        held = os.path.join(session.cwd, ".cursor", "mcp.json")
        assert stat.S_IMODE(os.stat(held).st_mode) == 0o600
        entry = json.loads(open(held, encoding="utf-8").read())["mcpServers"][agent_programs.TAB_SERVER]
        assert entry["headers"] == {INAPP_HEADER: "${env:" + claude_code.INAPP_VAR + "}"} and token not in open(held, encoding="utf-8").read()
    assert not call(client, READ_TOOL, headers={INAPP_HEADER: token}).get("isError")
    set_policy("blocked")
    assert agents().BLOCKED in text_of(call(client, READ_TOOL, headers={INAPP_HEADER: token}))
    set_policy("ask")
    shell = run(client, "terminal.open", {"cols": 80, "rows": 20}).json()["result"]["id"]
    assert claude_code.INAPP_VAR not in terminal.SESSIONS[shell].env
    run(client, "terminal.close", {"id": shell})
    assert run(client, "terminal.close", {"id": session.id}).status_code == 200
    assert not claude_code.is_inapp(token)


@pytest.mark.parametrize("cid,params", [("terminal.agents", {}), ("terminal.openAgent", {"kind": "codex"})])
def test_the_agent_program_commands_are_the_windows(client, bare, cid, params):
    assert bare.post(f"/api/commands/{cid}", json=params).status_code == 403
    set_policy("allowed")
    result = call(client, ("run_command", {"command": cid, "params": params}))
    assert result["isError"] and "only available in the formlit window" in text_of(result)


@pytest.mark.skipif(os.name == "nt", reason="the tab runs /bin/sh")
def test_the_exit_notice_is_a_typed_frame_when_the_window_asks_for_one(client):
    from app.engine import terminal

    session = terminal.open_session(argv=["/bin/sh", "-c", "exit 0"])
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and session.alive:
        time.sleep(0.05)
    assert not session.alive
    try:
        ticket = client.post("/api/window/ticket").json()["ticket"]
        with client.websocket_connect(f"/api/terminal/{session.id}?ticket={ticket}&control=binary", headers=HOST) as ws:
            assert json.loads(ws.receive_bytes()) == {"type": "hello"}
            assert json.loads(ws.receive_bytes()) == {"type": "exit"}
        ticket = client.post("/api/window/ticket").json()["ticket"]
        with client.websocket_connect(f"/api/terminal/{session.id}?ticket={ticket}", headers=HOST) as ws:
            assert ws.receive_text() == '{"type": "exit"}'
    finally:
        terminal.close(session.id)
