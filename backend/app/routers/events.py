import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.engine import catalog as catalog_mod
from app.engine import events

router = APIRouter(prefix="/api", tags=["events"])


@router.get("/events")
async def stream(request: Request) -> StreamingResponse:
    queue = events.subscribe()

    async def gen():
        try:
            hello = {"type": "hello", "revision": catalog_mod.get().revision}
            yield f"retry: 1500\ndata: {json.dumps(hello)}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield f"data: {message}\n\n"
        finally:
            events.unsubscribe(queue)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.get("/events/recent")
def recent() -> dict:
    return {"events": [json.loads(m) for m in events.recent()]}
