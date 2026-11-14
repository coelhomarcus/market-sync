"""As duas estratégias de consulta que o trabalho compara.

sequential(): consulta um mercado, espera a resposta, só então passa ao próximo.
              Tempo total ~= SOMA das latências.
concurrent(): dispara uma thread por mercado (ThreadPoolExecutor) e coleta as
              respostas conforme chegam (as_completed).
              Tempo total ~= MAIOR latência.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from common.config import MarketInfo

from .tcp_client import Emit, MarketResult, query_market

MODES = ("sequential", "concurrent")


def sequential(markets: list[MarketInfo], payload: dict, emit: Emit | None = None, t0: float | None = None) -> list[MarketResult]:
    t0 = time.perf_counter() if t0 is None else t0
    results = []
    for market in markets:  # um de cada vez, na thread que atende a requisição
        results.append(query_market(market, payload, t0=t0, emit=emit))
    return results


def concurrent(markets: list[MarketInfo], payload: dict, emit: Emit | None = None, t0: float | None = None) -> list[MarketResult]:
    t0 = time.perf_counter() if t0 is None else t0
    results = []
    with ThreadPoolExecutor(max_workers=max(1, len(markets)), thread_name_prefix="consulta") as pool:
        futures = [pool.submit(query_market, m, payload, t0=t0, emit=emit) for m in markets]
        for future in as_completed(futures):  # na ordem em que terminam
            results.append(future.result())
    return results


def run(mode: str, markets: list[MarketInfo], payload: dict, emit: Emit | None = None, t0: float | None = None) -> list[MarketResult]:
    if mode == "sequential":
        return sequential(markets, payload, emit, t0)
    if mode == "concurrent":
        return concurrent(markets, payload, emit, t0)
    raise ValueError(f"modo inválido: {mode}")
