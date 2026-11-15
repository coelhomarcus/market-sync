"""Experimento 4: de 1 a 32 clientes ao mesmo tempo; mede o tempo de cada pesquisa e a vazão."""

from __future__ import annotations

import threading
import time

from . import shared as c

NUMBER = 4
CSV = "exp4-multiplos-clientes.csv"


def measure(client, quick: bool = False) -> None:
    from client.connection import AggregatorClient

    levels = [1, 2, 4] if quick else [1, 2, 4, 8, 16, 32]
    per_client = 1 if quick else 3
    c.log(f"\nExperimento 4: múltiplos clientes ({per_client} pesquisas por cliente, latências padrão)")
    c.configure_all(client)
    rows = []
    for mode in c.MODES:
        for n in levels:
            barrier = threading.Barrier(n)
            lock = threading.Lock()
            failures: list[str] = []

            def one_client(idx: int) -> None:
                try:
                    with AggregatorClient(timeout=60) as conn:  # cada cliente: sua própria conexão TCP
                        barrier.wait()  # todos começam juntos
                        for k in range(per_client):
                            r = c.run_search(conn, mode)
                            with lock:
                                rows.append([mode, n, idx + 1, k + 1, r["tempo_total_ms"], r["tempo_cliente_ms"],
                                             c.ok_count(r), ""])
                except Exception as exc:  # noqa: BLE001 — conta como falha do experimento
                    with lock:
                        failures.append(f"cliente {idx + 1}: {exc}")

            threads = [threading.Thread(target=one_client, args=(i,)) for i in range(n)]
            t0 = time.perf_counter()
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            wall_ms = (time.perf_counter() - t0) * 1000
            rows.append([mode, n, 0, 0, "", round(wall_ms, 2), "", "; ".join(failures)])  # cliente 0 = tempo total do lote
            c.log(f"  {mode:<11} {n:>2} clientes: {n * per_client} pesquisas em {c.fmt_s(wall_ms)}"
                  f"{'  FALHAS: ' + '; '.join(failures) if failures else ''}")
    c.save_csv(CSV, ["modo", "clientes", "cliente", "pesquisa", "tempo_agregador_ms", "tempo_cliente_ms",
                     "mercados_ok", "falhas"], rows)


def analyze(md: list[str]) -> None:
    data = c.read_csv(CSV)
    if not data:
        return
    results = []  # (modo, clientes, pesquisas, resposta média, máx., tempo total, vazão, falhas)
    levels = sorted({int(d["clientes"]) for d in data})
    for mode in c.MODES:
        for n in levels:
            group = [d for d in data if d["modo"] == mode and int(d["clientes"]) == n]
            searches = [d for d in group if d["cliente"] != "0"]
            batch = next((d for d in group if d["cliente"] == "0"), None)
            if not searches or batch is None:
                continue
            times = [float(d["tempo_cliente_ms"]) for d in searches]
            wall_ms = float(batch["tempo_cliente_ms"])
            incomplete = sum(int(d["mercados_ok"]) < len(c.DEFAULT_LATENCIES) for d in searches)
            failures = len(batch["falhas"].split("; ")) if batch["falhas"] else 0
            results.append((mode, n, len(searches), c.mean(times), max(times), wall_ms, len(searches) / (wall_ms / 1000),
                            incomplete + failures))
    if not results:
        return
    per_client = results[0][2] // results[0][1]
    c.table(md, f"Experimento 4 — múltiplos clientes simultâneos ({per_client} pesquisas por cliente, latências padrão)",
            ["Modo", "Clientes", "Pesquisas", "Resposta média", "Resposta máx.", "Tempo total", "Vazão", "Falhas"],
            [[m.capitalize(), n, q, c.fmt_s(a), c.fmt_s(mx), c.fmt_s(w), f"{v:.2f} pesquisas/s".replace(".", ","), f]
             for m, n, q, a, mx, w, v, f in results])
    md.append("Cada cliente abre sua própria conexão TCP com o agregador e faz as pesquisas uma após a outra; "
              "todos começam juntos (barreira). Resposta = tempo visto pelo cliente.\n")

    plt = c.figure_setup()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.9))
    for mode in c.MODES:
        points = [r for r in results if r[0] == mode]
        ax1.plot([p[1] for p in points], [p[3] / 1000 for p in points], "o-", color=c.COLOR[mode], lw=2,
                 label=mode.capitalize())
        ax2.plot([p[1] for p in points], [p[6] for p in points], "o-", color=c.COLOR[mode], lw=2, label=mode.capitalize())
        last = points[-1]
        ax2.text(last[1] + 0.8, last[6], f"{last[6]:.1f}/s".replace(".", ","), va="center", fontsize=8, color=c.COLOR[mode])
    for ax in (ax1, ax2):
        ax.set_xticks(levels, [str(n) for n in levels])
        ax.set_xlabel("clientes simultâneos")
        ax.set_ylim(bottom=0)
    ax1.set_ylabel("tempo de resposta médio (s)")
    ax1.set_title("Tempo de resposta não muda com mais clientes", fontsize=11)
    ax1.set_ylim(top=max(r[3] for r in results) / 1000 * 1.25)
    ax1.legend(frameon=False, loc="center right")
    ax2.set_ylabel("pesquisas concluídas por segundo")
    ax2.set_title("Vazão cresce na proporção dos clientes", fontsize=11)
    ax2.set_xlim(right=max(levels) * 1.12)
    fig.tight_layout()
    c.save_figure(plt, fig, "fig-10-exp4-clientes.png")


if __name__ == "__main__":
    import sys

    c.run_alone(sys.modules[__name__])
