"""Estratégia SEQUENCIAL: um mercado de cada vez, numa única thread.

Tempo total ≈ a SOMA das latências (≈ 3,6 s)."""

from __future__ import annotations

import threading
import time

from common.config import MarketInfo

from .market_query import Emit, MarketResult, query_market


def search(markets: list[MarketInfo], request: dict, emit: Emit | None = None, t0: float | None = None) -> list[MarketResult]:
    """Consulta os mercados um de cada vez, na ordem da lista."""
    t0 = time.perf_counter() if t0 is None else t0
    threading.current_thread().name = "thread_1"  # a própria thread do pedido faz tudo: só existe esta
    results = []
    for market in markets:
        result = query_market(market, request, t0=t0, emit=emit)  # bloqueia até ESTE mercado responder
        results.append(result)
    return results
