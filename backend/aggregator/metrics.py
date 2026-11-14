"""Guarda cada consulta feita (em memória), resume as médias e exporta CSV."""

from __future__ import annotations

import csv
import io
import statistics
import threading
import time
from collections import deque

MODES = ("sequential", "concurrent")


class MetricsStore:
    def __init__(self, maxlen: int = 1000) -> None:
        self._records: deque[dict] = deque(maxlen=maxlen)
        self._lock = threading.Lock()  # várias consultas terminam ao mesmo tempo
        self._next_id = 1

    def add(self, record: dict) -> dict:
        with self._lock:
            record["id"] = self._next_id
            self._next_id += 1
            self._records.append(record)
        return record

    def records(self, limit: int | None = None) -> list[dict]:
        with self._lock:
            data = list(self._records)
        return data[-limit:] if limit else data

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    def to_csv(self) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "timestamp", "modo", "tipo", "origem", "consulta", "tempo_total_ms", "mercados_ok", "mercados_erro",
                         "mercado", "inicio_ms", "fim_ms", "duracao_ms", "tentativas", "bytes_recebidos", "thread", "erro",
                         "cpu_ms", "threads"])
        for rec in self.records():
            stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(rec["ts"]))
            res = rec["resources"]
            for m in rec["markets"]:
                writer.writerow([rec["id"], stamp, rec["mode"], rec["kind"], rec["source"], rec["query"], rec["total_ms"],
                                 rec["ok_count"], rec["error_count"], m["market_id"], m["start_ms"], m["end_ms"], m["duration_ms"],
                                 m["attempts"], m["bytes_received"], m["thread"], m["error"] or "", m["cpu_ms"], res["threads"]])
        return buf.getvalue()


def stats(values: list[float]) -> dict:
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
    """Média de tempo por modo, speedup (sequencial ÷ concorrente) e média de CPU/threads."""
    by_mode = {mode: [r for r in records if r["mode"] == mode] for mode in MODES}
    summary = {mode: stats([r["total_ms"] for r in recs]) for mode, recs in by_mode.items()}
    seq, conc = summary["sequential"]["avg"], summary["concurrent"]["avg"]
    summary["speedup"] = round(seq / conc, 2) if seq and conc else None
    summary["requests"] = len(records)
    summary["resources"] = {
        mode: {key: round(statistics.fmean(r["resources"][key] for r in recs), 3) if recs else None
               for key in ("cpu_ms", "cpu_util", "threads")}
        for mode, recs in by_mode.items()
    }
    return summary
