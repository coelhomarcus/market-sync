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

from comum.config import MarketInfo

from .consulta_mercado import Emit, MarketResult, query_market


def consultar(mercados: list[MarketInfo], pedido: dict, emit: Emit | None = None, t0: float | None = None) -> list[MarketResult]:
    """Consulta todos os mercados ao mesmo tempo, uma thread para cada um."""
    t0 = time.perf_counter() if t0 is None else t0

    def consultar_um(numero: int, mercado: MarketInfo) -> MarketResult:
        threading.current_thread().name = f"thread_{numero}"  # thread_1 … thread_5, uma por mercado
        return query_market(mercado, pedido, t0=t0, emit=emit)

    with ThreadPoolExecutor(max_workers=len(mercados)) as pool:
        # submit() entrega cada consulta a uma thread nova e volta na hora, sem esperar a resposta
        futuros = [pool.submit(consultar_um, numero, mercado) for numero, mercado in enumerate(mercados, start=1)]
        # result() faz a thread do pedido esperar cada uma terminar; o total é decidido pela mais lenta
        return [futuro.result() for futuro in futuros]
