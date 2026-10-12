import asyncio
import itertools
import secrets
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

INAPP_TOKEN = secrets.token_urlsafe(24)
INAPP_CLIENT = "Claude Code in formlit"

_seen: dict[str, dict] = {}
_waiting: dict[int, dict] = {}
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


def changed(choice: str | None = None) -> None:
    events.publish("agents.changed", outsideAgents=setting(), choice=choice)


async def require(client: str, channel: str) -> None:
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
        _waiting[key] = {"client": client, "channel": channel, "since": time.time()}
    events.publish("agents.consent", client=client, channel=channel)
    try:
        deadline = time.monotonic() + WAIT_SECONDS
        while time.monotonic() < deadline:
            await asyncio.sleep(POLL_SECONDS)
            state = setting()
            if state == "allowed":
                return
            if state == "blocked":
                raise CommandError(BLOCKED, 403)
            with _lock:
                declined = _later != mark
            if declined:
                raise CommandError(LATER, 403)
    finally:
        with _lock:
            _waiting.pop(key, None)
    raise CommandError(WAITING, 403)


@command("agents.status", "Outside Agents", mutates=False,
         description="Whether outside agents such as Claude may use formlit (outsideAgents: ask, allowed or blocked), which ones have called since formlit started, and which calls are waiting for the person's answer.")
def status() -> dict:
    with _lock:
        clients = sorted((dict(v) for v in _seen.values()), key=lambda c: -c["last"])
        pending = sorted((dict(v) for v in _waiting.values()), key=lambda c: c["since"])
    return {"outsideAgents": setting(), "clients": clients, "pending": pending}


@command("agents.respond", "Answer Outside Agents", {"choice": {"type": "string", "enum": ["allow", "later", "block"]}},
         description="The person's answer to formlit asking whether an outside agent may use it: allow sets outsideAgents to allowed, block sets it to blocked, later refuses the calls waiting now and changes nothing. The formlit window sends this; agents cannot.")
def respond(choice: str) -> dict:
    global _later
    if choice == "later":
        with _lock:
            _later += 1
    else:
        prefs.update({"outsideAgents": "allowed" if choice == "allow" else "blocked"})
    changed(choice)
    return {"outsideAgents": setting(), "choice": choice}
