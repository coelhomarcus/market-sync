"""Executa uma pesquisa no modo escolhido (sequencial ou concorrente) e mede o tempo."""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from common.config import MarketInfo

from . import concurrent, display, sequential
from .market_query import MarketResult, query_market

STRATEGIES = {
    "sequential": sequential.search,  # um mercado de cada vez
    "concurrent": concurrent.search,  # todos ao mesmo tempo, uma thread por mercado
}


class MarketNotFound(KeyError):
    """Id de mercado que não existe na configuração."""


class MarketUnreachable(RuntimeError):
    """O mercado não respondeu a um comando administrativo (STATUS/CONFIG)."""


class Aggregator:
    def __init__(self, markets: list[MarketInfo]) -> None:
        self.markets = markets

    def execute(self, mode: str, payload: dict, query: str, source: str = "cliente_tcp") -> tuple[list[MarketResult], dict]:
        """Roda a pesquisa nos mercados (sequencial ou concorrente) e devolve os resultados e as medições."""
        request_id = uuid.uuid4().hex[:8]

        def emit(type_: str, data: dict) -> None:  # chamado pelas threads de consulta
            display.event(type_, {"request_id": request_id, "mode": mode, **data})

        emit("request_start", {"query": query, "source": source})
        t0 = time.perf_counter()

        results = STRATEGIES[mode](self.markets, payload, emit=emit, t0=t0)

        total_ms = round((time.perf_counter() - t0) * 1000, 2)
        record = {
            "request_id": request_id,
            "mode": mode,
            "source": source,  # de onde veio o pedido (cliente_tcp)
            "query": query,
            "total_ms": total_ms,
            "ok_count": sum(r.ok for r in results),
            "error_count": sum(not r.ok for r in results),
            "markets": sorted((r.timing() for r in results), key=lambda t: t["start_ms"]),
            "threads": len({r.thread for r in results}),  # threads que conversaram com os mercados
        }
        emit("request_end", {k: record[k] for k in ("total_ms", "ok_count", "error_count", "threads")})
        return results, record

    # ------------------------------------------------------------ administração dos mercados
    # STATUS e CONFIG também viajam por TCP até cada mercado.

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
        display.event("market_config", {"market": market.id, "online": status["online"], "latency_ms": status["latency_ms"]})
        return status
