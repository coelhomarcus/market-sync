"""O agregador: recebe uma consulta, pergunta aos mercados no modo escolhido e mede tudo."""

from __future__ import annotations

import time
import uuid

from config import MarketInfo

from . import strategies
from .client import MarketResult
from .events import EventBus
from .metrics import MetricsStore


class Aggregator:
    def __init__(self, markets: list[MarketInfo]) -> None:
        self.markets = markets
        self.events = EventBus()  # alimenta o painel ao vivo
        self.metrics = MetricsStore()  # histórico de tempos

    def execute(self, mode: str, kind: str, payload: dict, query: str, source: str = "loja") -> tuple[list[MarketResult], dict]:
        """Roda a consulta nos mercados (sequencial ou concorrente) e registra as métricas."""
        request_id = uuid.uuid4().hex[:8]

        def emit(type_: str, data: dict) -> None:
            self.events.publish(type_, {"request_id": request_id, "mode": mode, "kind": kind, **data})

        emit("request_start", {"query": query, "source": source})
        t0 = time.perf_counter()

        results = strategies.run(mode, self.markets, payload, emit=emit, t0=t0)

        total_ms = round((time.perf_counter() - t0) * 1000, 2)
        cpu_ms = sum(r.cpu_ms for r in results)  # CPU de verdade, somando agregador e mercados
        record = self.metrics.add({
            "request_id": request_id,
            "ts": time.time(),
            "mode": mode,
            "kind": kind,  # search | basket
            "source": source,  # loja | benchmark
            "query": query,
            "total_ms": total_ms,
            "ok_count": sum(r.ok for r in results),
            "error_count": sum(not r.ok for r in results),
            "markets": sorted((r.timing() for r in results), key=lambda t: t["start_ms"]),
            "resources": {
                "cpu_ms": round(cpu_ms, 2),
                "cpu_util": round(cpu_ms / total_ms, 4) if total_ms else 0,  # fração do tempo em que houve CPU trabalhando
                "threads": len({r.thread for r in results}),  # threads que conversaram com os mercados
            },
        })
        emit("request_end", {"total_ms": total_ms, "ok_count": record["ok_count"], "error_count": record["error_count"], "record": record})
        return results, record
