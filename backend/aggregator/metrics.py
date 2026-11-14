"""Histórico de métricas em memória + resumo estatístico + exportação CSV."""

from __future__ import annotations

import csv
import io
import itertools
import statistics
import threading
import time
from collections import deque

from .tcp_client import MarketResult


class MetricsStore:
    def __init__(self, maxlen: int = 1000) -> None:
        self._records: deque[dict] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._ids = itertools.count(1)

    def record(self, *, mode: str, kind: str, query: str, total_ms: float, results: list[MarketResult], source: str = "loja") -> dict:
        markets = sorted((r.timing() for r in results), key=lambda t: t["start_ms"])
        rec = {
            "id": next(self._ids),
            "ts": time.time(),
            "mode": mode,
            "kind": kind,  # search | basket
            "source": source,  # loja | benchmark
            "query": query,
            "total_ms": round(total_ms, 2),
            "ok_count": sum(1 for r in results if r.ok),
            "error_count": sum(1 for r in results if not r.ok),
            "markets": markets,
        }
        with self._lock:
            self._records.append(rec)
        return rec

    def records(self, limit: int | None = None) -> list[dict]:
        with self._lock:
            data = list(self._records)
        return data[-limit:] if limit else data

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    def summary(self) -> dict:
        return summarize(self.records())

    def to_csv(self) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            ["id", "timestamp", "modo", "tipo", "origem", "consulta", "tempo_total_ms", "mercados_ok", "mercados_erro",
             "mercado", "inicio_ms", "fim_ms", "duracao_ms", "conexao_ms", "espera_ms", "bytes_recebidos", "thread", "erro"]
        )
        for rec in self.records():
            stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(rec["ts"]))
            for m in rec["markets"]:
                writer.writerow(
                    [rec["id"], stamp, rec["mode"], rec["kind"], rec["source"], rec["query"], rec["total_ms"],
                     rec["ok_count"], rec["error_count"], m["market_id"], m["start_ms"], m["end_ms"],
                     m["duration_ms"], m["connect_ms"], m["wait_ms"], m["bytes_received"], m["thread"], m["error"] or ""]
                )
        return buf.getvalue()


def _stats(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "avg": None, "min": None, "max": None, "stdev": None}
    return {
        "count": len(values),
        "avg": round(statistics.fmean(values), 2),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "stdev": round(statistics.stdev(values), 2) if len(values) > 1 else 0.0,
    }


def summarize(records: list[dict]) -> dict:
    by_mode = {mode: _stats([r["total_ms"] for r in records if r["mode"] == mode]) for mode in ("sequential", "concurrent")}
    seq, conc = by_mode["sequential"]["avg"], by_mode["concurrent"]["avg"]
    per_market: dict[str, list[float]] = {}
    errors: dict[str, int] = {}
    for r in records:
        for m in r["markets"]:
            if m["ok"]:
                per_market.setdefault(m["market_id"], []).append(m["duration_ms"])
            else:
                errors[m["market_id"]] = errors.get(m["market_id"], 0) + 1
    return {
        "requests": len(records),
        "sequential": by_mode["sequential"],
        "concurrent": by_mode["concurrent"],
        "speedup": round(seq / conc, 2) if seq and conc else None,
        "markets": {
            mid: {**_stats(vals), "errors": errors.get(mid, 0)} for mid, vals in per_market.items()
        } | {mid: {**_stats([]), "errors": n} for mid, n in errors.items() if mid not in per_market},
    }
