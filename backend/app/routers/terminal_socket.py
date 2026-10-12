import asyncio
import json
import urllib.parse

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.engine import terminal

router = APIRouter(tags=["terminal"])
LOCAL = ("localhost", "127.0.0.1", "::1", "tauri.localhost")


def _local(origin: str | None) -> bool:
    if not origin:
        return True
    return (urllib.parse.urlparse(origin).hostname or "") in LOCAL or origin.startswith("tauri://")


@router.websocket("/api/terminal/{sid}")
async def attach(ws: WebSocket, sid: str) -> None:
    if not _local(ws.headers.get("origin")):
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

    async def outbound() -> None:
        backlog = session.scrollback()
        if backlog:
            await ws.send_text(backlog)
        if not session.alive:
            await ws.send_text(json.dumps({"type": "exit"}))
        while True:
            text = await q.get()
            await ws.send_text(json.dumps({"type": "exit"}) if text is None else text)

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
