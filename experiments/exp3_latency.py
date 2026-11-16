"""Experimento 3: muda a latência dos mercados e compara os dois modos em cada cenário."""

from __future__ import annotations

from collections import defaultdict

from . import shared as c

NUMBER = 3
CSV = "exp3-latencia.csv"
TARGET = "ipe"  # o supermercado que fica lento nos dois últimos cenários

# (nome, descrição, latência de cada supermercado)
SCENARIOS = [
    ("Sem atraso", "0 ms em todos", {m: 0 for m in c.DEFAULT_LATENCIES}),
    ("200 ms", "200 ms em todos", {m: 200 for m in c.DEFAULT_LATENCIES}),
    ("500 ms", "500 ms em todos", {m: 500 for m in c.DEFAULT_LATENCIES}),
    ("1000 ms", "1000 ms em todos", {m: 1000 for m in c.DEFAULT_LATENCIES}),
    ("Padrão", "300 a 1200 ms", dict(c.DEFAULT_LATENCIES)),
    ("Um lento", f"padrão, {c.SHORT_NAMES[TARGET]} com 2500 ms", {**c.DEFAULT_LATENCIES, TARGET: 2500}),
    ("Um em timeout", f"padrão, {c.SHORT_NAMES[TARGET]} com 4000 ms", {**c.DEFAULT_LATENCIES, TARGET: 4000}),
]


def measure(client, quick: bool = False) -> None:
    rounds = 2 if quick else 5
    c.header(3, "simulação de latência",
             f"{len(SCENARIOS)} cenários de latência, {rounds} rodadas de cada modo por cenário.",
             f"mais espera → mais ganho; um mercado lento limita o concorrente; timeout em {c.fmt_s(c.TIMEOUT_MS)}.")
    rows = []
    summary = []
    for name, desc, latencies in SCENARIOS:
        c.configure_all(client, latencies)
        times = defaultdict(list)
        for i in range(rounds):
            for mode in c.alternating(i):
                r = c.run_search(client, mode)
                times[mode].append(r["tempo_total_ms"])
                rows.append([name, desc, i + 1, mode, r["tempo_total_ms"], c.ok_count(r)])
        seq, conc = c.mean(times["sequencial"]), c.mean(times["concorrente"])
        c.log(f"  {name:<14} {desc:<24} sequencial {c.fmt_s(seq):>8} · concorrente {c.fmt_s(conc):>8} · "
              f"speedup {c.fmt_x(seq / conc)}")
        summary.append((name, seq, conc))
    c.configure_all(client)
    best = max(summary, key=lambda s: s[1] / s[2])
    no_delay, slow, timeout = summary[0], summary[-2], summary[-1]
    c.result(f"maior ganho: {c.fmt_x(best[1] / best[2])} no cenário '{best[0]}' (latências iguais)",
             f"'{slow[0]}': o concorrente passa a durar o tempo do mercado lento ({c.fmt_s(slow[2])})",
             f"'{timeout[0]}': o concorrente desiste do {c.SHORT_NAMES[TARGET]} em {c.fmt_s(timeout[2])} "
             f"e responde com os outros 4",
             f"'{no_delay[0]}': {c.fmt_s(no_delay[1])} × {c.fmt_s(no_delay[2])}, só milissegundos de diferença: "
             f"sem espera de rede não há o que sobrepor")
    c.save_csv(CSV, ["cenario", "descricao", "rodada", "modo", "tempo_ms", "mercados_ok"], rows)


def analyze(md: list[str]) -> None:
    data = c.read_csv(CSV)
    if not data:
        return
    results = []  # (nome, descrição, média seq, média conc, previsto soma, previsto maior, rodadas)
    for name, desc, latencies in SCENARIOS:
        times = {m: [float(d["tempo_ms"]) for d in data if d["cenario"] == name and d["modo"] == m] for m in c.MODES}
        if not times["sequencial"]:
            continue
        total, largest = c.expected(latencies)
        results.append((name, desc, c.mean(times["sequencial"]), c.mean(times["concorrente"]), total, largest,
                        len(times["sequencial"])))
    if not results:
        return
    c.table(md, f"Experimento 3 — simulação de latência ({results[0][6]} rodadas por cenário)",
            ["Cenário", "Latências", "Sequencial", "Previsto (soma)", "Concorrente", "Previsto (maior)", "Speedup"],
            [[n, d, c.fmt_s(s), c.fmt_s(sm), c.fmt_s(k), c.fmt_s(mx), c.fmt_x(s / k)] for n, d, s, k, sm, mx, _ in results])
    md.append(f"O previsto limita cada latência ao timeout de {c.fmt_s(c.TIMEOUT_MS)}.\n")

    plt = c.figure_setup()
    fig, ax = plt.subplots(figsize=(9, 5.4))
    height = 0.38
    count = len(results)
    for j, (name, desc, seq, conc, *_rest) in enumerate(results):
        y = count - 1 - j
        ax.barh(y + height / 2, seq / 1000, height, color=c.SEQ_BAR_COLOR, label="Sequencial" if j == 0 else None)
        ax.barh(y - height / 2, conc / 1000, height, color=c.COLOR["concorrente"], label="Concorrente" if j == 0 else None)
        ax.text(seq / 1000 + 0.06, y + height / 2, c.fmt_s(seq), va="center", fontsize=8, color="#555")
        ax.text(conc / 1000 + 0.06, y - height / 2, c.fmt_s(conc), va="center", fontsize=8, fontweight="bold")
        ax.text(1.02, y, c.fmt_x(seq / conc), transform=ax.get_yaxis_transform(), va="center", fontweight="bold")
    ax.text(1.02, count - 0.45, "speedup", transform=ax.get_yaxis_transform(), fontsize=8, color="#555")
    ax.set_yticks([count - 1 - j for j in range(count)], [f"{r[0]}\n{r[1]}" for r in results], fontsize=9)
    ax.set_xlim(0, max(r[2] for r in results) / 1000 * 1.12)
    ax.set_ylim(-0.7, count - 0.2)
    ax.set_xlabel("tempo médio da pesquisa (s)")
    ax.grid(axis="y", visible=False)
    best = max(r[2] / r[3] for r in results)
    ax.set_title(f"Com latências iguais o ganho chega a {c.fmt_x(best)}; um mercado lento limita o concorrente", pad=26)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, borderaxespad=0.1)
    c.save_figure(plt, fig, "fig-09-exp3-latencia.png")


if __name__ == "__main__":
    import sys

    c.run_alone(sys.modules[__name__])
