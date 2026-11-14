"""Barramento de eventos thread-safe -> WebSocket.

As consultas TCP rodam em threads comuns (pool do FastAPI e ThreadPoolExecutor),
mas os WebSockets vivem no event loop do asyncio. `publish()` pode ser chamado de
qualquer thread: ele agenda a entrega na fila de cada cliente com
`loop.call_soon_threadsafe`, a forma segura de falar com o loop de outra thread.
"""

from __future__ import annotations

import asyncio
import itertools
import threading
import time
from collections import deque


class EventBus:
    def __init__(self, history: int = 200, queue_size: int = 1000) -> None:
        self._subscribers: dict[int, tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = {}
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._seq = itertools.count(1)
        self._queue_size = queue_size
        self.recent: deque[dict] = deque(maxlen=history)

    def subscribe(self) -> tuple[int, asyncio.Queue]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._queue_size)
        with self._lock:
            sub_id = next(self._ids)
            self._subscribers[sub_id] = (loop, queue)
        return sub_id, queue

    def unsubscribe(self, sub_id: int) -> None:
        with self._lock:
            self._subscribers.pop(sub_id, None)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    def publish(self, type_: str, data: dict) -> dict:
        event = {"seq": next(self._seq), "type": type_, "ts": time.time(), **data}
        with self._lock:
            self.recent.append(event)
            targets = list(self._subscribers.values())
        for loop, queue in targets:
            try:
                loop.call_soon_threadsafe(_offer, queue, event)
            except RuntimeError:
                pass  # loop já encerrado
        return event


def _offer(queue: asyncio.Queue, event: dict) -> None:
    if queue.full():  # cliente lento: descarta o mais antigo
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    queue.put_nowait(event)
