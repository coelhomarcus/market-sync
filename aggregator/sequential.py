"""Estratégia SEQUENCIAL: pergunta a um mercado, espera a resposta e só então passa ao próximo.

Tudo acontece numa única thread (a que está atendendo o cliente). Enquanto ela
espera o mercado 1 responder, os outros 4 ficam parados esperando a vez.

    Aurora    ███
    SuperVila    █████
    Empório         ███████
    Max                    █████████
    Ipê                             ████████████
              └──── tempo total ≈ SOMA das latências (≈ 3,6 s) ────┘
"""

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
