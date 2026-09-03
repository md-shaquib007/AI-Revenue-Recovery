import asyncio
import json
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Set

from fastapi import Request
from starlette.responses import StreamingResponse


class EventBus:
    """In-process pub/sub used for Command Center SSE."""

    def __init__(self) -> None:
        self._subscribers: Set[asyncio.Queue] = set()
        self._history: deque = deque(maxlen=60)

    def publish(self, event: Dict[str, Any]) -> None:
        payload = dict(event)
        payload.setdefault("ts", datetime.utcnow().isoformat() + "Z")
        self._history.appendleft(payload)
        dead: List[asyncio.Queue] = []
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(queue)
        for queue in dead:
            self._subscribers.discard(queue)

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        return list(self._history)[: max(0, limit)]

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)


event_bus = EventBus()


async def sse_response(request: Request) -> StreamingResponse:
    queue = event_bus.subscribe()

    async def generator():
        try:
            yield "event: ready\ndata: {\"status\":\"connected\"}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=20)
                    yield f"event: revive\ndata: {json.dumps(item, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            event_bus.unsubscribe(queue)

    return StreamingResponse(generator(), media_type="text/event-stream")
