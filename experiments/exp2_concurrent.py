"""Experimento 2 — consulta concorrente.

Consulta os 5 supermercados ao mesmo tempo (uma thread por supermercado) e registra
o tempo total, N vezes, com as latências padrão. Modelo: o tempo deve ficar perto da
MAIOR latência. A análise também compara com o Experimento 1 (tabela, speedup e fig-08).

Rodar sozinho:  .venv/bin/python -m experiments.exp2_concurrent   (com o start.py --quiet no ar)
"""

from __future__ import annotations

from . import shared as c
from . import exp1_sequential

NUMBER = 2
CSV = "exp2-concorrente.csv"


def measure(client, quick: bool = False) -> None:
    rounds = 3 if quick else 10
    c.log(f"\nExperimento 2: {rounds} pesquisas concorrentes por '{c.PRODUCT}', latências padrão")
    c.configure_all(client)
    rows = []
    for i in range(rounds):
        r = c.run_search(client, "concorrente")
        rows.append([i + 1, r["tempo_total_ms"], r["tempo_cliente_ms"], c.ok_count(r)])
        c.log(f"  rodada {i + 1}: {c.fmt_s(r['tempo_total_ms'])}")
    c.save_csv(CSV, ["rodada", "tempo_agregador_ms", "tempo_cliente_ms", "mercados_ok"], rows)


def analyze(md: list[str]) -> None:
    data = c.read_csv(CSV)
    if not data:
        return
    aggregator_ms = [float(d["tempo_agregador_ms"]) for d in data]
    client_ms = [float(d["tempo_cliente_ms"]) for d in data]
    total, largest = c.expected(c.DEFAULT_LATENCIES)
    c.table(md, f"Experimento 2 — consulta concorrente ({len(aggregator_ms)} rodadas, latências padrão)",
            ["Média", "Mín.", "Máx.", "Desvio padrão", "Visto pelo cliente", "Previsto (maior)"],
            [[c.fmt_s(c.mean(aggregator_ms)), c.fmt_s(min(aggregator_ms)), c.fmt_s(max(aggregator_ms)),
              c.fmt_s(c.stdev(aggregator_ms)), c.fmt_s(c.mean(client_ms)), c.fmt_s(largest)]])

    sequential = exp1_sequential.times()
    if not sequential:
        return
    seq_ms = sequential[0]
    speedup = c.mean(seq_ms) / c.mean(aggregator_ms)
    md.append(f"Comparando com o Experimento 1: speedup médio de **{c.fmt_x(speedup)}** "
              f"(limite teórico com essas latências: {c.fmt_x(total / largest)}). "
              f"\"Visto pelo cliente\" inclui a ida e volta TCP entre cliente e agregador.\n")

    plt = c.figure_setup()
    fig, ax = plt.subplots(figsize=(8, 3.8))
    for mode, values, model in (("sequencial", seq_ms, total), ("concorrente", aggregator_ms, largest)):
        x = range(1, len(values) + 1)
        ax.plot(x, [t / 1000 for t in values], "o-", color=c.COLOR[mode], lw=2, ms=6,
                label=f"{mode.capitalize()} (média {c.fmt_s(c.mean(values))})")
        ax.axhline(model / 1000, color="#333", lw=1, ls="--")
        ax.text(len(values) + 0.2, model / 1000, f"previsto\n{c.fmt_s(model)}", va="center", fontsize=8, color="#333")
    rounds = max(len(seq_ms), len(aggregator_ms))
    ax.set_xticks(list(range(1, rounds + 1)))
    ax.set_xlabel("rodada")
    ax.set_ylabel("tempo da pesquisa (s)")
    ax.set_ylim(0, max(seq_ms) / 1000 * 1.2)
    ax.set_title(f"Concorrente foi {c.fmt_x(speedup)} mais rápido que o sequencial")
    ax.legend(loc="center right", frameon=False)
    c.save_figure(plt, fig, "fig-08-exp1-exp2.png")


if __name__ == "__main__":
    import sys

    c.run_alone(sys.modules[__name__])
