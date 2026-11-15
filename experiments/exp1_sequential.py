"""Experimento 1: consulta sequencial. Esperado: tempo ≈ SOMA das latências."""

from __future__ import annotations

from . import shared as c

NUMBER = 1
CSV = "exp1-sequencial.csv"


def measure(client, quick: bool = False) -> None:
    rounds = 3 if quick else 10
    c.log(f"\nExperimento 1: {rounds} pesquisas sequenciais por '{c.PRODUCT}', latências padrão")
    c.configure_all(client)
    rows = []
    for i in range(rounds):
        r = c.run_search(client, "sequencial")
        rows.append([i + 1, r["tempo_total_ms"], r["tempo_cliente_ms"], c.ok_count(r)])
        c.log(f"  rodada {i + 1}: {c.fmt_s(r['tempo_total_ms'])}")
    c.save_csv(CSV, ["rodada", "tempo_agregador_ms", "tempo_cliente_ms", "mercados_ok"], rows)


def times() -> tuple[list[float], list[float]] | None:
    """(tempos medidos pelo agregador, tempos vistos pelo cliente), ou None se ainda não mediu."""
    data = c.read_csv(CSV)
    if not data:
        return None
    return [float(d["tempo_agregador_ms"]) for d in data], [float(d["tempo_cliente_ms"]) for d in data]


def analyze(md: list[str]) -> None:
    measured = times()
    if not measured:
        return
    aggregator_ms, client_ms = measured
    total, _ = c.expected(c.DEFAULT_LATENCIES)
    c.table(md, f"Experimento 1 — consulta sequencial ({len(aggregator_ms)} rodadas, latências padrão)",
            ["Média", "Mín.", "Máx.", "Desvio padrão", "Visto pelo cliente", "Previsto (soma)"],
            [[c.fmt_s(c.mean(aggregator_ms)), c.fmt_s(min(aggregator_ms)), c.fmt_s(max(aggregator_ms)),
              c.fmt_s(c.stdev(aggregator_ms)), c.fmt_s(c.mean(client_ms)), c.fmt_s(total)]])


if __name__ == "__main__":
    import sys

    c.run_alone(sys.modules[__name__])
