import asyncio
import itertools
import threading
import time

from app.core import prefs
from app.engine import events
from app.engine.commands import CommandError, command

WAIT_SECONDS = 120
POLL_SECONDS = 0.25
MAX_SEEN = 40
BLOCKED = "Outside agents are turned off in formlit's Preferences, AI agents, so this call was refused. Tell the person where to change it and stop; do not retry."
LATER = "The person chose Not now when formlit asked to let outside agents in, so this call was refused. Do not retry in a loop; ask whether they want you to try again."
WAITING = "Still waiting for the person to allow outside agents in formlit's window. Ask them to open formlit and choose Allow, then try once more; do not retry in a loop."

GONE = "That request is no longer waiting for an answer"
ONCE_NEEDS = "agents.respond: once needs the request id from agents.consent"

INAPP_CLIENT = "Claude Code in formlit"
ANSWERS = ("deny", "once", "always")
ALWAYS_COVERS = "all"

_seen: dict[str, dict] = {}
_waiting: dict[int, dict] = {}
_answers: dict[int, str] = {}
_ids = itertools.count(1)
_later = 0
_lock = threading.Lock()


def setting() -> str:
    value = prefs.load().get("outsideAgents", "ask")
    return value if value in prefs.CHOICES["outsideAgents"] else "ask"


def note(client: str, channel: str) -> None:
    now = time.time()
    with _lock:
        if client not in _seen and len(_seen) >= MAX_SEEN:
            _seen.pop(min(_seen, key=lambda k: _seen[k]["last"]))
        entry = _seen.setdefault(client, {"name": client, "channel": channel, "first": now, "calls": 0})
        entry["last"] = now
        entry["channel"] = channel
        entry["calls"] += 1


def changed(choice: str | None = None, request: str | None = None) -> None:
    events.publish("agents.changed", outsideAgents=setting(), choice=choice, request=request)


async def require(client: str, channel: str, asked: dict | None = None, gone=None) -> None:
    client = (client or "").strip()[:80] or "an outside agent"
    note(client, channel)
    state = setting()
    if state == "allowed" or (channel == "inapp" and state != "blocked"):
        return
    if state == "blocked":
        raise CommandError(BLOCKED, 403)
    with _lock:
        key = next(_ids)
        mark = _later
        now = time.time()
        item = {"client": client, "channel": channel, "since": now, "request": f"r{key}", "agent": client,
                "tool": "", "command": "", "what": "", "label": "", **(asked or {}),
                "answers": list(ANSWERS), "alwaysCovers": ALWAYS_COVERS, "expiresIn": WAIT_SECONDS, "expiresAt": now + WAIT_SECONDS}
        _waiting[key] = item
    events.publish("agents.consent", **item)
    reason = "closed"
    try:
        deadline = time.monotonic() + WAIT_SECONDS
        while time.monotonic() < deadline:
            await asyncio.sleep(POLL_SECONDS)
            if gone is not None and await gone():
                raise CommandError(WAITING, 403)
            state = setting()
            if state == "allowed":
                reason = "answered"
                return
            if state == "blocked":
                reason = "answered"
                raise CommandError(BLOCKED, 403)
            with _lock:
                answer = _answers.get(key) or ("later" if _later != mark else "")
            if answer:
                reason = "answered"
            if answer == "once":
                return
            if answer:
                raise CommandError(LATER, 403)
        reason = "expired"
    finally:
        with _lock:
            _waiting.pop(key, None)
            _answers.pop(key, None)
        events.publish("agents.withdrawn", request=f"r{key}", reason=reason)
    raise CommandError(WAITING, 403)


@command("agents.status", "Outside Agents", mutates=False,
         description="Whether outside agents such as Claude may use formlit (outsideAgents: ask, allowed or blocked), which ones have called since formlit started, and which calls are waiting for the person's answer.")
def status() -> dict:
    with _lock:
        clients = sorted((dict(v) for v in _seen.values()), key=lambda c: -c["last"])
        pending = sorted((dict(v) for v in _waiting.values()), key=lambda c: c["since"])
    return {"outsideAgents": setting(), "clients": clients, "pending": pending}


@command("agents.respond", "Answer Outside Agents", {"choice": {"type": "string", "enum": ["allow", "once", "later", "block"]},
                                                     "request": {"type": "string", "description": "the request id from agents.consent; with it, once and later answer that one call only"}},
         description="The person's answer to formlit asking whether an outside agent may use it: allow sets outsideAgents to allowed, block sets it to blocked, later refuses the calls waiting now and changes nothing, once (with request) lets that one call run and changes nothing. The formlit window sends this; agents cannot.")
def respond(choice: str, request: str | None = None) -> dict:
    global _later
    if choice == "once" and not request:
        raise CommandError(ONCE_NEEDS, 400)
    if request and choice in ("once", "later"):
        with _lock:
            key = next((k for k, v in _waiting.items() if v["request"] == request), None)
            if key is not None:
                _answers.setdefault(key, choice)
        if key is None:
            raise CommandError(GONE, 409)
    elif choice == "later":
        with _lock:
            _later += 1
    else:
        prefs.update({"outsideAgents": "allowed" if choice == "allow" else "blocked"})
    changed(choice, request)
    return {"outsideAgents": setting(), "choice": choice}
