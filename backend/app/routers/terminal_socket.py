import asyncio
import json
import urllib.parse

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core import window_key
from app.engine import terminal

router = APIRouter(tags=["terminal"])
LOCAL = ("localhost", "127.0.0.1", "::1", "tauri.localhost")


def _local(origin: str | None) -> bool:
    if not origin:
        return True
    return (urllib.parse.urlparse(origin).hostname or "") in LOCAL or origin.startswith("tauri://")


@router.websocket("/api/terminal/{sid}")
async def attach(ws: WebSocket, sid: str, ticket: str = "", control: str = "") -> None:
    if not _local(ws.headers.get("origin")) or not window_key.spend(ticket):
        await ws.close(code=4403)
        return
    await ws.accept()
    try:
        session = terminal.get(sid)
    except KeyError:
        await ws.close(code=4404)
        return
    q: asyncio.Queue = asyncio.Queue()
    session.subscribers.add(q)
    typed = control == "binary"

    async def notice(kind: str) -> None:
        if typed:
            await ws.send_bytes(json.dumps({"type": kind}).encode("utf-8"))
        else:
            await ws.send_text(json.dumps({"type": kind}))

    async def outbound() -> None:
        backlog = session.scrollback()
        if typed:
            await notice("hello")
        if backlog:
            await ws.send_text(backlog)
        if not session.alive:
            await notice("exit")
        while True:
            text = await q.get()
            if text is None:
                await notice("exit")
            else:
                await ws.send_text(text)

    sender = asyncio.create_task(outbound())
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if msg.get("type") == "input" and session.alive:
                terminal.write(sid, str(msg.get("data", "")))
            elif msg.get("type") == "resize":
                terminal.resize(sid, int(msg.get("cols", 80)), int(msg.get("rows", 24)))
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        session.subscribers.discard(q)
