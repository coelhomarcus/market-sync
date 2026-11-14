"""Eventos ao vivo para o painel (consulta começou, mercado respondeu, nova tentativa...).

As consultas rodam em threads comuns, mas os WebSockets vivem no event loop do
asyncio. `publish()` pode ser chamado de qualquer thread: ele entrega o evento na
fila de cada navegador conectado com `loop.call_soon_threadsafe`.
"""

from __future__ import annotations

import asyncio
import itertools
import threading
import time
from collections import deque


class EventBus:
    def __init__(self, history: int = 200) -> None:
        self._subscribers: dict[int, tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = {}
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._seq = itertools.count(1)
        self.recent: deque[dict] = deque(maxlen=history)  # para quem abrir o painel agora

    def subscribe(self) -> tuple[int, asyncio.Queue]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        with self._lock:
            sub_id = next(self._ids)
            self._subscribers[sub_id] = (asyncio.get_running_loop(), queue)
        return sub_id, queue

    def unsubscribe(self, sub_id: int) -> None:
        with self._lock:
            self._subscribers.pop(sub_id, None)

    def publish(self, type_: str, data: dict) -> None:
        event = {"seq": next(self._seq), "type": type_, "ts": time.time(), **data}
        with self._lock:
            self.recent.append(event)
            targets = list(self._subscribers.values())
        for loop, queue in targets:
            try:
                loop.call_soon_threadsafe(_offer, queue, event)
            except RuntimeError:
                pass  # o navegador já desconectou


def _offer(queue: asyncio.Queue, event: dict) -> None:
    if queue.full():  # navegador lento: descarta o evento mais antigo
        queue.get_nowait()
    queue.put_nowait(event)
