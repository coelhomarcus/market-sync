"""As duas formas de consultar os mercados que o trabalho compara.

sequential(): pergunta a um mercado, espera a resposta, só então passa ao próximo.
              Tempo total ≈ SOMA dos tempos de cada mercado.

concurrent(): cria uma thread por mercado e pergunta a todos ao mesmo tempo.
              Tempo total ≈ o tempo do mercado MAIS LENTO.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from comum.config import MarketInfo

from .consulta_mercado import Emit, MarketResult, query_market

MODES = ("sequential", "concurrent")


def sequential(markets: list[MarketInfo], payload: dict, emit: Emit | None = None, t0: float | None = None) -> list[MarketResult]:
    t0 = time.perf_counter() if t0 is None else t0
    return [query_market(m, payload, t0=t0, emit=emit) for m in markets]  # um de cada vez


def concurrent(markets: list[MarketInfo], payload: dict, emit: Emit | None = None, t0: float | None = None) -> list[MarketResult]:
    t0 = time.perf_counter() if t0 is None else t0
    with ThreadPoolExecutor(max_workers=len(markets), thread_name_prefix="consulta") as pool:  # uma thread por mercado
        return list(pool.map(lambda m: query_market(m, payload, t0=t0, emit=emit), markets))


def run(mode: str, markets: list[MarketInfo], payload: dict, emit: Emit | None = None, t0: float | None = None) -> list[MarketResult]:
    strategy = {"sequential": sequential, "concurrent": concurrent}[mode]
    return strategy(markets, payload, emit, t0)
