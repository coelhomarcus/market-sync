"""O agregador: recebe uma consulta, pergunta aos mercados no modo escolhido e mede tudo."""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from comum.config import MarketInfo

from . import estrategias
from .consulta_mercado import MarketResult, query_market
from .eventos import EventBus
from .metricas import MetricsStore


class MarketNotFound(KeyError):
    """Id de mercado que não existe na configuração."""


class MarketUnreachable(RuntimeError):
    """O mercado não respondeu a um comando administrativo (STATUS/CONFIG)."""


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

        results = estrategias.run(mode, self.markets, payload, emit=emit, t0=t0)

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

    # ------------------------------------------------------------ administração dos mercados
    # Usado pelo painel (HTTP) e pelo cliente TCP: STATUS e CONFIG viajam por TCP até cada mercado.

    def market_status(self, market: MarketInfo, payload: dict | None = None) -> dict:
        r = query_market(market, payload or {"cmd": "STATUS"}, timeout=1.5, retries=0)  # sem retry: resposta rápida
        info = {"id": market.id, "name": market.name, "short": market.short, "port": market.port,
                "color": market.color, "default_latency_ms": market.latency_ms}
        if not r.ok:
            return {**info, "reachable": False, "online": False, "error": r.error}
        return {**info, "reachable": True, **r.data}

    def markets_status(self) -> list[dict]:
        with ThreadPoolExecutor(max_workers=len(self.markets)) as pool:
            return list(pool.map(self.market_status, self.markets))

    def configure_market(self, market_id: str, latency_ms: int | None = None, online: bool | None = None) -> dict:
        market = next((m for m in self.markets if m.id == market_id), None)
        if market is None:
            raise MarketNotFound(market_id)
        changes = {k: v for k, v in {"latency_ms": latency_ms, "online": online}.items() if v is not None}
        status = self.market_status(market, {"cmd": "CONFIG", **changes})
        if not status["reachable"]:
            raise MarketUnreachable(f"{market.name} não respondeu: {status['error']}")
        self.events.publish("market_config", {"market": market.id, "online": status["online"], "latency_ms": status["latency_ms"]})
        return status
