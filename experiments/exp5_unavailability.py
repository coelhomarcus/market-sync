"""Experimento 5 — indisponibilidade de serviço.

Desativa a SuperVila (a segunda da lista, 500 ms) e observa o tratamento da falha, em quatro cenários:
antes da pesquisa, 0,3 s depois do início (com a consulta já em andamento) e "cai e volta".
A desativação vai por uma segunda conexão TCP ("configurar" com online=false), enquanto
a primeira espera a resposta da pesquisa. Gera a tabela e o gráfico fig-11 (barras no tempo).

Rodar sozinho:  .venv/bin/python -m experiments.exp5_unavailability   (com o start.py --quiet no ar)
"""

from __future__ import annotations

import threading

from common import config

from . import shared as c

NUMBER = 5
CSV = "exp5-indisponibilidade.csv"
CSV_TIMELINE = "exp5-gantt.csv"
TARGET = "supervila"
TARGET_NAME = c.SHORT_NAMES[TARGET]

SCENARIOS = [
    ("Todos no ar", "referência"),
    ("Fora do ar antes", f"{TARGET_NAME} sai do ar antes da pesquisa"),
    ("Cai durante", f"{TARGET_NAME} sai do ar 0,3 s depois do início"),
    ("Cai e volta", f"{TARGET_NAME} cai em 0,3 s e volta em 1,0 s"),
]


def measure(client, quick: bool = False) -> None:
    from client.connection import AggregatorClient

    rounds = 1 if quick else 3
    c.log(f"\nExperimento 5: indisponibilidade de serviço, alvo {TARGET_NAME} ({rounds} rodadas por cenário)")
    c.configure_all(client)

    def go_down(admin):
        admin.configure(TARGET, online=False)

    def come_back(admin):
        admin.configure(TARGET, online=True)

    actions = {  # o que acontece com o mercado-alvo em cada cenário
        "Todos no ar": {},
        "Fora do ar antes": {"before": True},
        "Cai durante": {"during": [(0.3, go_down)]},
        "Cai e volta": {"during": [(0.3, go_down), (1.0, come_back)]},
    }
    rows, timeline = [], []
    for scenario, _ in SCENARIOS:
        action = actions[scenario]
        for i in range(rounds):
            for mode in c.alternating(i):
                if action.get("before"):
                    client.configure(TARGET, online=False)
                if action.get("during"):
                    with AggregatorClient() as admin:  # conexão de administração, separada da pesquisa
                        timers = [threading.Timer(delay, fn, args=[admin]) for delay, fn in action["during"]]
                        for t in timers:
                            t.start()
                        r = c.run_search(client, mode)
                        for t in timers:
                            t.join()
                else:
                    r = c.run_search(client, mode)
                c.configure_all(client)  # cada rodada começa com tudo no ar

                target = next(m for m in r["mercados"] if m["id"] == TARGET)
                rows.append([scenario, mode, i + 1, r["tempo_total_ms"], c.ok_count(r), target["status"],
                             target["tentativas"], target["inicio_ms"], target["fim_ms"], target["erro"] or ""])
                if scenario == "Cai durante" and not any(t[0] == mode for t in timeline):  # uma pesquisa de cada modo
                    timeline += [[mode, m["id"], m["fonte"], m["inicio_ms"], m["fim_ms"], m["status"], m["tentativas"],
                                  m["erro"] or "", r["tempo_total_ms"]] for m in r["mercados"]]
                c.log(f"  {scenario:<16} {mode:<11} rodada {i + 1}: {c.fmt_s(r['tempo_total_ms']):>8} · "
                      f"{c.ok_count(r)}/5 mercados · {TARGET_NAME}: {target['tentativas']} tentativa(s)")
    c.configure_all(client)
    c.save_csv(CSV, ["cenario", "modo", "rodada", "tempo_ms", "mercados_ok", "status_alvo", "tentativas_alvo",
                     "inicio_alvo_ms", "fim_alvo_ms", "erro_alvo"], rows)
    c.save_csv(CSV_TIMELINE, ["modo", "mercado", "fonte", "inicio_ms", "fim_ms", "status", "tentativas", "erro",
                              "tempo_total_ms"], timeline)


def analyze(md: list[str]) -> None:
    data = c.read_csv(CSV)
    if not data:
        return
    results = []  # (cenário, descrição, modo, tempo médio, mercados com resposta, tentativas no alvo, erros, rodadas)
    for scenario, desc in SCENARIOS:
        for mode in c.MODES:
            rs = [d for d in data if d["cenario"] == scenario and d["modo"] == mode]
            if not rs:
                continue
            results.append((scenario, desc, mode, c.mean([float(d["tempo_ms"]) for d in rs]),
                            c.mean([int(d["mercados_ok"]) for d in rs]), c.mean([int(d["tentativas_alvo"]) for d in rs]),
                            sorted({d["erro_alvo"] for d in rs if d["erro_alvo"]}), len(rs)))
    if not results:
        return
    c.table(md, f"Experimento 5 — indisponibilidade de serviço, alvo {TARGET_NAME} ({results[0][7]} rodadas por cenário)",
            ["Cenário", "O que acontece", "Modo", "Tempo médio", "Mercados com resposta", f"Tentativas ({TARGET_NAME})",
             "Erro informado"],
            [[s, d, m.capitalize(), c.fmt_s(t), f"{c.fmt_num(o)} de 5", c.fmt_num(a), ", ".join(e) or "—"]
             for s, d, m, t, o, a, e, _ in results])

    timeline = c.read_csv(CSV_TIMELINE)
    if not timeline:
        return
    plt = c.figure_setup()
    fig, axes = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
    end_s = max(float(t["tempo_total_ms"]) for t in timeline) / 1000
    order = list(config.MARKETS)
    for ax, mode in zip(axes, c.MODES):
        by_market = {t["mercado"]: t for t in timeline if t["modo"] == mode}
        total_ms = float(next(iter(by_market.values()))["tempo_total_ms"])
        for y, info in enumerate(reversed(order)):
            t = by_market[info.id]
            start, end = float(t["inicio_ms"]) / 1000, float(t["fim_ms"]) / 1000
            failed = t["status"] != "sucesso"
            ax.barh(y, end - start, left=start, height=0.6,
                    color=c.ERROR_COLOR if failed else (c.SEQ_BAR_COLOR if mode == "sequencial" else c.COLOR["concorrente"]))
            ax.text(end + 0.05, y, t["erro"] if failed else c.fmt_s((end - start) * 1000), va="center", fontsize=8,
                    color=c.ERROR_COLOR if failed else "#333")
        ax.set_yticks(range(len(order)), [i.short for i in reversed(order)])
        ax.axvline(0.3, color="#333", ls="--", lw=1)
        ax.axvline(total_ms / 1000, color="#333", lw=1.5)
        ax.text(total_ms / 1000 + 0.05, len(order) - 0.45, f"resposta ao cliente: {c.fmt_s(total_ms)}", fontsize=8,
                va="bottom")
        ax.set_title(mode.capitalize(), fontsize=10)
        ax.grid(axis="y", visible=False)
        ax.set_xlim(0, end_s * 1.4)
        ax.set_ylim(-0.6, len(order) - 0.1)
    axes[0].text(0.35, len(order) - 0.45, f"{TARGET_NAME} sai do ar (0,3 s)", fontsize=8, va="bottom")
    axes[1].set_xlabel("tempo desde o início da pesquisa (s)")
    fig.suptitle(f"{TARGET_NAME} cai no meio da pesquisa: o agregador tenta de novo e responde com os outros 4",
                 x=0.01, ha="left", fontweight="bold", fontsize=11)
    fig.tight_layout()
    c.save_figure(plt, fig, "fig-11-exp5-falha.png")


if __name__ == "__main__":
    import sys

    c.run_alone(sys.modules[__name__])
