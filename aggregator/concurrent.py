"""Estratégia CONCORRENTE: cria uma thread por mercado e pergunta a todos ao mesmo tempo.

Cada thread do pool abre a sua conexão TCP e fica esperando o seu mercado.
Enquanto uma thread está parada no recv(), ela libera o GIL e as outras seguem.

    Aurora    ███
    SuperVila █████
    Empório   ███████
    Max       █████████
    Ipê       ████████████
              └ tempo total ≈ a MAIOR latência (≈ 1,2 s) ┘
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from common.config import MarketInfo

from .market_query import Emit, MarketResult, query_market


def search(markets: list[MarketInfo], request: dict, emit: Emit | None = None, t0: float | None = None) -> list[MarketResult]:
    """Consulta todos os mercados ao mesmo tempo, uma thread para cada um."""
    t0 = time.perf_counter() if t0 is None else t0

    def query_one(number: int, market: MarketInfo) -> MarketResult:
        threading.current_thread().name = f"thread_{number}"  # thread_1 … thread_5, uma por mercado
        return query_market(market, request, t0=t0, emit=emit)

    with ThreadPoolExecutor(max_workers=len(markets)) as pool:
        # submit() entrega cada consulta a uma thread nova e volta na hora, sem esperar a resposta
        futures = [pool.submit(query_one, number, market) for number, market in enumerate(markets, start=1)]
        # result() faz a thread do pedido esperar cada uma terminar; o total é decidido pela mais lenta
        return [future.result() for future in futures]
