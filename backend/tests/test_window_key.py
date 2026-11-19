import json
import re

import pytest
from starlette.websockets import WebSocketDisconnect

from conftest import ENGINE_PORT, WS_PATH

READS = {"GET", "HEAD", "OPTIONS"}
OPEN = {("POST", "/mcp"), ("POST", "/api/window/key")}
REFUSED = {"detail": "Only the formlit window can do this"}


def write_operations(app):
    return [(m.upper(), path) for path, item in app.openapi()["paths"].items() for m in item if m.upper() not in READS]


def test_the_open_list_is_short_and_named():
    from app.core import window_key

    assert set(window_key.OPEN) == {"/mcp", "/api/window/key"}


def test_every_write_route_needs_the_window_key(app, bare):
    ops = write_operations(app)
    assert len(ops) >= 6
    answered = []
    for method, path in ops:
        if (method, path) in OPEN:
            continue
        url = re.sub(r"\{[^}]+\}", "x", path)
        for headers in ({}, {"x-formlit-window-key": "x" * 43}):
            r = bare.request(method, url, json={}, headers=headers)
            if r.status_code != 403 or r.json() != REFUSED:
                answered.append(f"{method} {path} {r.status_code}")
    assert not answered, "write routes that answer without the window key (add the key, or name the route in window_key.OPEN with its caller): " + ", ".join(answered)


@pytest.mark.parametrize("cid,params", [("agents.respond", {"choice": "allow"}), ("prefs.set", {"values": {"outsideAgents": "allowed"}}), ("terminal.open", {}), ("library.tree", {})])
def test_commands_and_batch_refuse_without_the_key(bare, cid, params):
    assert bare.post(f"/api/commands/{cid}", json=params).status_code == 403
    assert bare.post("/api/batch", json=[{"id": cid, "params": params}]).status_code == 403


def test_the_window_runs_commands_with_the_key(client):
    r = client.post("/api/commands/agents.status", json={})
    assert r.status_code == 200 and r.json()["ok"]


@pytest.mark.parametrize("cid,params", [("agents.respond", {"choice": "allow"}), ("terminal.open", {}), ("claudecode.status", {}), ("chat.reset", {}), ("prefs.set", {"values": {"claudeBin": "/x"}})])
def test_dispatch_refuses_window_only_commands_outside_the_window(commands, cid, params):
    from app.engine.commands import CommandError

    with pytest.raises(CommandError) as refused:
        commands(cid, params)
    assert refused.value.status == 403


def test_the_development_bootstrap_answers_once(bare, monkeypatch):
    from app.core import window_key

    monkeypatch.setitem(window_key.STATE, "claimed", False)
    first = bare.post("/api/window/key")
    assert first.status_code == 200 and first.json()["key"] == window_key.KEY
    assert bare.post("/api/window/key").status_code == 409
    assert bare.get("/api/window/state").json()["secondClaim"] is True


def test_the_bootstrap_does_not_exist_when_the_shell_takes_the_key(bare, monkeypatch):
    monkeypatch.setenv("FORMLIT_WINDOW_KEY_STDOUT", "1")
    assert bare.post("/api/window/key").status_code == 404


@pytest.mark.parametrize("query", ["", "?ticket=", "?ticket=made-up"])
def test_terminal_socket_needs_a_ticket(bare, query):
    with pytest.raises(WebSocketDisconnect) as refused:
        with bare.websocket_connect(f"{WS_PATH}{query}", headers={"host": f"127.0.0.1:{ENGINE_PORT}"}) as ws:
            ws.receive()
    assert refused.value.code == 4403


def test_a_ticket_is_spent_once(client):
    ticket = client.post("/api/window/ticket").json()["ticket"]
    host = {"host": f"127.0.0.1:{ENGINE_PORT}"}
    with client.websocket_connect(f"{WS_PATH}?ticket={ticket}", headers=host) as ws:
        assert ws.receive()["code"] == 4404
    with pytest.raises(WebSocketDisconnect) as refused:
        with client.websocket_connect(f"{WS_PATH}?ticket={ticket}", headers=host) as ws:
            ws.receive()
    assert refused.value.code == 4403


def test_inapp_tokens_live_in_a_private_file_and_die_on_revoke():
    import os
    import stat

    from app.engine import claude_code

    token, path = claude_code.issue()
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert json.loads(open(path, encoding="utf-8").read())["mcpServers"]["formlit"]["headers"]["x-formlit-inapp"] == token
    assert not any(token in part for part in claude_code.argv("/usr/bin/claude", "hi", None, path))
    assert claude_code.is_inapp(token)
    claude_code.revoke(token)
    assert not os.path.exists(path) and not claude_code.is_inapp(token)


@pytest.fixture
def stand_in_keyring(monkeypatch):
    import keyring
    from keyring.backend import KeyringBackend

    from app.core import seal

    class Stand(KeyringBackend):
        priority = 0
        store: dict = {}

        def get_password(self, service, username):
            return self.store.get((service, username))

        def set_password(self, service, username, password):
            self.store[(service, username)] = password

        def delete_password(self, service, username):
            self.store.pop((service, username), None)

    before = keyring.get_keyring()
    keyring.set_keyring(Stand())
    seal.reset()
    yield
    keyring.set_keyring(before)
    seal.reset()


def test_a_hand_edit_of_agent_access_is_caught(client, stand_in_keyring):
    from app.core import config, prefs

    prefs.update({"outsideAgents": "allowed"})
    assert prefs.load()["seal"] == "ok" and prefs.load()["outsideAgents"] == "allowed"
    path = config.data_dir() / "preferences.json"
    raw = json.loads(path.read_text())
    raw["claudeBin"] = "/somewhere/else"
    path.write_text(json.dumps(raw))
    seen = prefs.load()
    assert seen["sealBroken"] is True and seen["outsideAgents"] == "ask" and seen["claudeBin"] == ""
    prefs.update({"outsideAgents": "ask", "claudeBin": ""})
    assert prefs.load()["seal"] == "ok"


def test_without_a_keychain_the_stored_choice_stands(client, monkeypatch):
    import sys

    from app.core import prefs, seal

    monkeypatch.setitem(sys.modules, "keyring", None)
    seal.reset()
    try:
        prefs.update({"outsideAgents": "blocked"})
        seen = prefs.load()
        assert seen["seal"] == "unavailable" and seen["outsideAgents"] == "blocked"
    finally:
        prefs.update({"outsideAgents": "ask"})
        seal.reset()
