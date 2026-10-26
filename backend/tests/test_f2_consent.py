import threading
import time

import pytest

from conftest import CHANGING_TOOL, INAPP_HEADER, MCP_PATH, READ_TOOL, inapp_token, set_policy


def agents():
    from app.engine import agents as mod

    return mod


def rpc(client, method, params=None, headers=None, rid=1):
    r = client.post(MCP_PATH, json={"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}, headers=headers or {})
    assert r.status_code == 200, r.text
    return r.json()


def call(client, tool, headers=None):
    name, args = tool
    init = client.post(MCP_PATH, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "family-test-agent", "version": "1"}}}, headers=headers or {})
    hdrs = dict(headers or {})
    if init.headers.get("mcp-session-id"):
        hdrs["mcp-session-id"] = init.headers["mcp-session-id"]
    return rpc(client, "tools/call", {"name": name, "arguments": args}, hdrs, rid=2)


def text_of(reply):
    return " ".join(c.get("text", "") for c in (reply.get("result") or {}).get("content", []) if isinstance(c, dict))


def kind(reply):
    text = text_of(reply)
    a = agents()
    for name in ("BLOCKED", "LATER", "WAITING"):
        if getattr(a, name) in text:
            return name
    return "through"


@pytest.fixture(autouse=True)
def fast_and_reset(monkeypatch):
    a = agents()
    monkeypatch.setattr(a, "WAIT_SECONDS", 1.2)
    monkeypatch.setattr(a, "POLL_SECONDS", 0.05)
    set_policy("ask")
    yield
    set_policy("ask")


def test_ask_with_nobody_answering_refuses_a_changing_tool(client):
    reply = call(client, CHANGING_TOOL)
    assert kind(reply) == "WAITING"
    assert reply["result"]["isError"]


def test_ask_also_holds_a_read_only_tool(client):
    assert kind(call(client, READ_TOOL)) == "WAITING"


def test_blocked_policy_refuses_every_tool(client):
    set_policy("blocked")
    assert kind(call(client, CHANGING_TOOL)) == "BLOCKED"
    assert kind(call(client, READ_TOOL)) == "BLOCKED"


def test_handshake_and_tool_listing_stay_open_while_blocked(client):
    set_policy("blocked")
    assert "result" in rpc(client, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {}})
    assert rpc(client, "tools/list")["result"]["tools"]


def test_allowed_policy_lets_a_tool_through(client):
    set_policy("allowed")
    assert kind(call(client, CHANGING_TOOL)) == "through"
    assert kind(call(client, READ_TOOL)) == "through"


def test_allowing_while_a_call_waits_lets_it_through(client):
    a = agents()
    a.WAIT_SECONDS = 20
    out = {}

    def run():
        out["reply"] = call(client, READ_TOOL)

    t = threading.Thread(target=run)
    t.start()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not a.status()["pending"]:
        time.sleep(0.05)
    assert a.status()["pending"]
    a.respond("allow")
    t.join(15)
    assert kind(out["reply"]) == "through"
    assert a.setting() == "allowed"


def test_a_decline_refuses_the_waiting_call_and_changes_nothing(client):
    a = agents()
    a.WAIT_SECONDS = 20
    out = {}
    t = threading.Thread(target=lambda: out.update(reply=call(client, READ_TOOL)))
    t.start()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not a.status()["pending"]:
        time.sleep(0.05)
    a.respond("later")
    t.join(15)
    assert kind(out["reply"]) == "LATER"
    assert a.setting() == "ask"


def test_blocking_while_a_call_waits_refuses_it(client):
    a = agents()
    a.WAIT_SECONDS = 20
    out = {}
    t = threading.Thread(target=lambda: out.update(reply=call(client, READ_TOOL)))
    t.start()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not a.status()["pending"]:
        time.sleep(0.05)
    a.respond("block")
    t.join(15)
    assert kind(out["reply"]) == "BLOCKED"


def test_inapp_token_skips_the_ask(client):
    assert kind(call(client, CHANGING_TOOL, {INAPP_HEADER: inapp_token()})) == "through"


def test_inapp_token_does_not_skip_a_block(client):
    set_policy("blocked")
    assert kind(call(client, CHANGING_TOOL, {INAPP_HEADER: inapp_token()})) == "BLOCKED"


@pytest.mark.parametrize("token", ["", "wrong-token", "x" * 64])
def test_wrong_inapp_token_does_not_skip_the_ask(client, token):
    assert kind(call(client, CHANGING_TOOL, {INAPP_HEADER: token})) == "WAITING"


def test_an_agent_cannot_answer_its_own_prompt(client):
    set_policy("allowed")
    reply = call(client, ("run_command", {"command": "agents.respond", "params": {"choice": "allow"}}))
    assert reply["result"]["isError"]
    set_policy("ask")
    assert agents().setting() == "ask"
