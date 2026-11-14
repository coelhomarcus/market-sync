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

from comum.config import MarketInfo

from .consulta_mercado import Emit, MarketResult, query_market


def consultar(mercados: list[MarketInfo], pedido: dict, emit: Emit | None = None, t0: float | None = None) -> list[MarketResult]:
    """Consulta os mercados um de cada vez, na ordem da lista."""
    t0 = time.perf_counter() if t0 is None else t0
    threading.current_thread().name = "thread_1"  # a própria thread do pedido faz tudo: só existe esta
    resultados = []
    for mercado in mercados:
        resultado = query_market(mercado, pedido, t0=t0, emit=emit)  # bloqueia até ESTE mercado responder
        resultados.append(resultado)
    return resultados
