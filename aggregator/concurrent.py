"""Estratégia CONCORRENTE: uma thread por mercado, todas ao mesmo tempo.

Tempo total ≈ a MAIOR latência (≈ 1,2 s)."""

from __future__ import annotations

import threading
import time

from common.config import MarketInfo

from .market_query import Emit, MarketResult, query_market


def search(markets: list[MarketInfo], request: dict, emit: Emit | None = None, t0: float | None = None) -> list[MarketResult]:
    """Consulta todos os mercados ao mesmo tempo, uma thread para cada um."""
    t0 = time.perf_counter() if t0 is None else t0

    # uma posição por mercado; cada thread só escreve na sua, então não precisa de lock
    results = [None] * len(markets)

    def query_one(position: int, market: MarketInfo) -> None:
        """O que cada thread faz: consulta UM mercado e guarda a resposta na sua posição."""
        results[position] = query_market(market, request, t0=t0, emit=emit)

    # 1. criar uma thread por mercado (ainda não começaram a rodar)
    threads = []
    for position, market in enumerate(markets):
        thread = threading.Thread(target=query_one, args=(position, market), name=f"thread_{position + 1}")
        threads.append(thread)

    # 2. start(): dispara todas. Volta na hora, sem esperar a resposta do mercado
    for thread in threads:
        thread.start()

    # 3. join(): só espera; as 5 já rodam juntas, então o total ≈ a mais lenta
    for thread in threads:
        thread.join()

    return results
