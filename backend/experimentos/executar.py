"""Os 5 experimentos obrigatórios do enunciado, feitos de ponta a ponta pelo cliente TCP.

    Experimento 1  Consulta sequencial            N pesquisas, um mercado depois do outro
    Experimento 2  Consulta concorrente           N pesquisas, uma thread por mercado
    Experimento 3  Simulação de latência          vários atrasos artificiais nos mercados
    Experimento 4  Múltiplos clientes             1 a 32 clientes TCP pesquisando ao mesmo tempo
    Experimento 5  Indisponibilidade de serviço   um mercado sai do ar antes / durante a pesquisa

Tudo passa pelo caminho real: cliente --TCP--> agregador --TCP--> 5 mercados.
A latência e a queda dos mercados são configuradas pela operação "configurar",
também por TCP. No fim, os mercados voltam para a configuração padrão.

Duas etapas:
    1. medir    → docs/relatorio/dados/07..11-*.csv                 (medições brutas)
    2. analisar → docs/relatorio/dados/resultados-experimentos.md   (tabelas)
                  docs/relatorio/figuras/fig-08..11-*.png            (gráficos)

Uso (dentro de backend/, com o iniciar.py rodando em outro terminal):
    .venv/bin/python -m experimentos             # mede tudo (cerca de 6 minutos) e analisa
    .venv/bin/python -m experimentos --so 4 5    # mede só alguns e refaz a análise de todos
    .venv/bin/python -m experimentos --analisar  # só refaz tabelas e gráficos a partir dos CSV
    .venv/bin/python -m experimentos --rapido    # poucas rodadas, para testar o script
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
import threading
import time
from collections import defaultdict

from comum import config

ROOT = config.BACKEND_DIR.parent
DADOS = ROOT / "docs" / "relatorio" / "dados"
FIGURAS = ROOT / "docs" / "relatorio" / "figuras"

CSV_EXP12 = "07-exp1-exp2-sequencial-concorrente.csv"
CSV_EXP3 = "08-exp3-latencia.csv"
CSV_EXP4 = "09-exp4-multiplos-clientes.csv"
CSV_EXP5 = "10-exp5-indisponibilidade.csv"
CSV_EXP5_GANTT = "11-exp5-gantt.csv"

PRODUTO = "arroz"
MODOS = ("sequencial", "concorrente")
COR = {"sequencial": "#8f8e80", "concorrente": "#2b7bd8"}
COR_BARRA_SEQ = "#c5c4b7"
COR_ERRO = "#d64545"
PADRAO = {m.id: m.latency_ms for m in config.MARKETS}
NOMES = {m.id: m.short for m in config.MARKETS}
ALVO = "ipe"  # o mercado mais lento é o que derrubamos no experimento 5
TIMEOUT_MS = config.TCP_TIMEOUT_S * 1000

CENARIOS_LATENCIA = [
    ("Sem atraso", "0 ms em todos", {m: 0 for m in PADRAO}),
    ("200 ms", "200 ms em todos", {m: 200 for m in PADRAO}),
    ("500 ms", "500 ms em todos", {m: 500 for m in PADRAO}),
    ("1000 ms", "1000 ms em todos", {m: 1000 for m in PADRAO}),
    ("Padrão", "300 a 1200 ms", dict(PADRAO)),
    ("Um lento", f"padrão, {NOMES[ALVO]} com 2500 ms", {**PADRAO, ALVO: 2500}),
    ("Um em timeout", f"padrão, {NOMES[ALVO]} com 4000 ms", {**PADRAO, ALVO: 4000}),
]

CENARIOS_FALHA = [
    ("Todos no ar", "referência"),
    ("Fora do ar antes", f"{NOMES[ALVO]} desativado antes da pesquisa"),
    ("Cai durante", f"{NOMES[ALVO]} desativado 0,3 s depois do início"),
    ("Cai e volta", f"{NOMES[ALVO]} cai em 0,3 s e volta em 1,0 s"),
]


# ---------------------------------------------------------------- utilidades

def log(msg: str) -> None:
    print(msg, flush=True)


def media(xs: list[float]) -> float:
    return statistics.fmean(xs) if xs else float("nan")


def desvio(xs: list[float]) -> float:
    return statistics.stdev(xs) if len(xs) > 1 else 0.0


def seg(ms: float) -> str:
    return f"{ms / 1000:.2f} s".replace(".", ",") if ms >= 1000 else f"{ms:.0f} ms"


def vezes(x: float) -> str:
    return f"{x:.1f}×".replace(".", ",")


def num(x: float) -> str:
    return f"{x:.1f}".replace(".0", "").replace(".", ",")


def salvar_csv(nome: str, cabecalho: list[str], linhas: list[list]) -> None:
    DADOS.mkdir(parents=True, exist_ok=True)
    with open(DADOS / nome, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cabecalho)
        w.writerows(linhas)
    log(f"  → {DADOS.relative_to(ROOT) / nome}")


def ler_csv(nome: str) -> list[dict] | None:
    caminho = DADOS / nome
    if not caminho.exists():
        return None
    with open(caminho, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def tabela(md: list[str], titulo: str, cabecalho: list[str], linhas: list[list]) -> None:
    md.append(f"## {titulo}\n")
    md.append("| " + " | ".join(cabecalho) + " |")
    md.append("|" + "---|" * len(cabecalho))
    for linha in linhas:
        md.append("| " + " | ".join(str(c) for c in linha) + " |")
    md.append("")


def previsto(lat: dict[str, int]) -> tuple[float, float]:
    """Modelo: sequencial ≈ soma das latências; concorrente ≈ a maior (as duas limitadas pelo timeout)."""
    efetivas = [min(v, TIMEOUT_MS) for v in lat.values()]
    return sum(efetivas), max(efetivas)


# ---------------------------------------------------------------- medição (precisa do sistema no ar)

def configurar_todos(c, latencias: dict[str, int] | None = None, online: bool = True) -> None:
    for mid, lat in (latencias or PADRAO).items():
        r = c.configurar(mid, latencia_ms=lat, online=online)
        if r["status"] != "sucesso":
            raise RuntimeError(f"não consegui configurar {mid}: {r.get('mensagem')}")


def pesquisar(c, modo: str) -> dict:
    t = time.perf_counter()
    r = c.consultar(PRODUTO, modo, limite=1)
    r["tempo_cliente_ms"] = round((time.perf_counter() - t) * 1000, 2)  # visto pelo cliente: inclui o TCP até o agregador
    return r


def ok(r: dict) -> int:
    return sum(m["status"] == "sucesso" for m in r["mercados"])


def alternado(i: int) -> tuple[str, ...]:
    """Alterna a ordem dos modos a cada rodada: nenhum deles leva vantagem por cache ou aquecimento."""
    return MODOS if i % 2 == 0 else tuple(reversed(MODOS))


def medir_exp1_e_2(c, rodadas: int) -> None:
    log(f"\nExperimentos 1 e 2: {rodadas} pesquisas por '{PRODUTO}' em cada modo, latências padrão")
    configurar_todos(c)
    linhas = []
    for i in range(rodadas):
        tempos = {}
        for modo in alternado(i):
            r = pesquisar(c, modo)
            tempos[modo] = r["tempo_total_ms"]
            linhas.append([i + 1, modo, r["tempo_total_ms"], r["tempo_cliente_ms"], ok(r)])
        log(f"  rodada {i + 1}: sequencial {seg(tempos['sequencial'])} · concorrente {seg(tempos['concorrente'])}")
    salvar_csv(CSV_EXP12, ["rodada", "modo", "tempo_agregador_ms", "tempo_cliente_ms", "mercados_ok"], linhas)


def medir_exp3(c, rodadas: int) -> None:
    log(f"\nExperimento 3: simulação de latência ({rodadas} rodadas por cenário)")
    linhas = []
    for nome, desc, lat in CENARIOS_LATENCIA:
        configurar_todos(c, lat)
        tempos = defaultdict(list)
        for i in range(rodadas):
            for modo in alternado(i):
                r = pesquisar(c, modo)
                tempos[modo].append(r["tempo_total_ms"])
                linhas.append([nome, desc, i + 1, modo, r["tempo_total_ms"], ok(r)])
        s, k = media(tempos["sequencial"]), media(tempos["concorrente"])
        log(f"  {nome:<14} sequencial {seg(s):>8} · concorrente {seg(k):>8} · speedup {vezes(s / k)}")
    configurar_todos(c)
    salvar_csv(CSV_EXP3, ["cenario", "descricao", "rodada", "modo", "tempo_ms", "mercados_ok"], linhas)


def medir_exp4(c, niveis: list[int], por_cliente: int) -> None:
    from cliente.conexao import ClienteAgregador

    log(f"\nExperimento 4: múltiplos clientes ({por_cliente} pesquisas por cliente, latências padrão)")
    configurar_todos(c)
    linhas = []
    for modo in MODOS:
        for n in niveis:
            barreira = threading.Barrier(n)
            trava = threading.Lock()
            falhas: list[str] = []

            def cliente(idx: int) -> None:
                try:
                    with ClienteAgregador(timeout=60) as cli:  # cada cliente: sua própria conexão TCP
                        barreira.wait()  # todos começam juntos
                        for k in range(por_cliente):
                            r = pesquisar(cli, modo)
                            with trava:
                                linhas.append([modo, n, idx + 1, k + 1, r["tempo_total_ms"], r["tempo_cliente_ms"], ok(r), ""])
                except Exception as exc:  # noqa: BLE001 — conta como falha do experimento
                    with trava:
                        falhas.append(f"cliente {idx + 1}: {exc}")

            threads = [threading.Thread(target=cliente, args=(i,)) for i in range(n)]
            t0 = time.perf_counter()
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            parede = (time.perf_counter() - t0) * 1000
            linhas.append([modo, n, 0, 0, "", round(parede, 2), "", "; ".join(falhas)])  # cliente 0 = tempo total do lote
            log(f"  {modo:<11} {n:>2} clientes: {n * por_cliente} pesquisas em {seg(parede)}"
                f"{'  FALHAS: ' + '; '.join(falhas) if falhas else ''}")
    salvar_csv(CSV_EXP4, ["modo", "clientes", "cliente", "pesquisa", "tempo_agregador_ms", "tempo_cliente_ms",
                          "mercados_ok", "falhas"], linhas)


def medir_exp5(c, rodadas: int) -> None:
    from cliente.conexao import ClienteAgregador

    log(f"\nExperimento 5: indisponibilidade do {NOMES[ALVO]} ({rodadas} rodadas por cenário)")
    configurar_todos(c)
    cair = lambda adm: adm.configurar(ALVO, online=False)  # noqa: E731
    voltar = lambda adm: adm.configurar(ALVO, online=True)  # noqa: E731
    acoes = {
        "Todos no ar": {},
        "Fora do ar antes": {"antes": True},
        "Cai durante": {"durante": [(0.3, cair)]},
        "Cai e volta": {"durante": [(0.3, cair), (1.0, voltar)]},
    }
    linhas, gantt = [], []
    for cenario, _ in CENARIOS_FALHA:
        acao = acoes[cenario]
        for i in range(rodadas):
            for modo in alternado(i):
                if acao.get("antes"):
                    c.configurar(ALVO, online=False)
                if acao.get("durante"):
                    with ClienteAgregador() as admin:  # conexão de administração, separada da pesquisa
                        timers = [threading.Timer(atraso, f, args=[admin]) for atraso, f in acao["durante"]]
                        for t in timers:
                            t.start()
                        r = pesquisar(c, modo)
                        for t in timers:
                            t.join()
                else:
                    r = pesquisar(c, modo)
                configurar_todos(c)  # cada rodada começa com tudo no ar

                alvo = next(m for m in r["mercados"] if m["id"] == ALVO)
                linhas.append([cenario, modo, i + 1, r["tempo_total_ms"], ok(r), alvo["status"], alvo["tentativas"],
                               alvo["inicio_ms"], alvo["fim_ms"], alvo["erro"] or ""])
                if cenario == "Cai durante" and not any(g[0] == modo for g in gantt):  # uma pesquisa de cada modo
                    gantt += [[modo, m["id"], m["fonte"], m["inicio_ms"], m["fim_ms"], m["status"], m["tentativas"],
                               m["erro"] or "", r["tempo_total_ms"]] for m in r["mercados"]]
                log(f"  {cenario:<16} {modo:<11} rodada {i + 1}: {seg(r['tempo_total_ms']):>8} · {ok(r)}/5 mercados · "
                    f"{NOMES[ALVO]}: {alvo['tentativas']} tentativa(s)")
    configurar_todos(c)
    salvar_csv(CSV_EXP5, ["cenario", "modo", "rodada", "tempo_ms", "mercados_ok", "status_alvo", "tentativas_alvo",
                          "inicio_alvo_ms", "fim_alvo_ms", "erro_alvo"], linhas)
    salvar_csv(CSV_EXP5_GANTT, ["modo", "mercado", "fonte", "inicio_ms", "fim_ms", "status", "tentativas", "erro",
                                "tempo_total_ms"], gantt)


# ---------------------------------------------------------------- análise (só precisa dos CSV)

def figura():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.family": ["Helvetica Neue", "DejaVu Sans"], "font.size": 10,
        "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#888",
        "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlelocation": "left",
        "axes.grid": True, "grid.color": "#e6e6e6", "axes.axisbelow": True,
    })
    return plt


def salvar_figura(plt, fig, nome: str) -> None:
    FIGURAS.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURAS / nome, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    log(f"  → {FIGURAS.relative_to(ROOT) / nome}")


def analisar_exp1_e_2(md: list[str]) -> None:
    dados = ler_csv(CSV_EXP12)
    if not dados:
        return
    tempos = {m: [float(d["tempo_agregador_ms"]) for d in dados if d["modo"] == m] for m in MODOS}
    cliente = {m: [float(d["tempo_cliente_ms"]) for d in dados if d["modo"] == m] for m in MODOS}
    rodadas = len(tempos["sequencial"])
    soma, maior = previsto(PADRAO)
    s, k = media(tempos["sequencial"]), media(tempos["concorrente"])
    tabela(md, f"Experimentos 1 e 2 — sequencial × concorrente ({rodadas} rodadas, latências padrão)",
           ["Experimento", "Modo", "Média", "Mín.", "Máx.", "Desvio padrão", "Visto pelo cliente", "Previsto"],
           [[n, m.capitalize(), seg(media(tempos[m])), seg(min(tempos[m])), seg(max(tempos[m])), seg(desvio(tempos[m])),
             seg(media(cliente[m])), f"{seg(p)} ({'soma' if m == 'sequencial' else 'maior'})"]
            for n, m, p in (("1", "sequencial", soma), ("2", "concorrente", maior))])
    md.append(f"Speedup médio: **{vezes(s / k)}** (limite teórico com essas latências: {vezes(soma / maior)}). "
              f"\"Visto pelo cliente\" inclui a ida e volta TCP entre cliente e agregador.\n")

    plt = figura()
    fig, ax = plt.subplots(figsize=(8, 3.8))
    x = range(1, rodadas + 1)
    for modo, prev in (("sequencial", soma), ("concorrente", maior)):
        ax.plot(x, [t / 1000 for t in tempos[modo]], "o-", color=COR[modo], lw=2, ms=6,
                label=f"{modo.capitalize()} (média {seg(media(tempos[modo]))})")
        ax.axhline(prev / 1000, color="#333", lw=1, ls="--")
        ax.text(rodadas + 0.2, prev / 1000, f"previsto\n{seg(prev)}", va="center", fontsize=8, color="#333")
    ax.set_xticks(list(x))
    ax.set_xlabel("rodada")
    ax.set_ylabel("tempo da pesquisa (s)")
    ax.set_ylim(0, max(tempos["sequencial"]) / 1000 * 1.2)
    ax.set_title(f"Concorrente foi {vezes(s / k)} mais rápido, em todas as {rodadas} rodadas")
    ax.legend(loc="center right", frameon=False)
    salvar_figura(plt, fig, "fig-08-exp1-exp2.png")


def analisar_exp3(md: list[str]) -> None:
    dados = ler_csv(CSV_EXP3)
    if not dados:
        return
    resultado = []
    for nome, desc, lat in CENARIOS_LATENCIA:
        t = {m: [float(d["tempo_ms"]) for d in dados if d["cenario"] == nome and d["modo"] == m] for m in MODOS}
        if not t["sequencial"]:
            continue
        soma, maior = previsto(lat)
        resultado.append((nome, desc, media(t["sequencial"]), media(t["concorrente"]), soma, maior, len(t["sequencial"])))
    rodadas = resultado[0][6]
    tabela(md, f"Experimento 3 — simulação de latência ({rodadas} rodadas por cenário)",
           ["Cenário", "Latências", "Sequencial", "Previsto (soma)", "Concorrente", "Previsto (maior)", "Speedup"],
           [[n, d, seg(s), seg(sm), seg(k), seg(mx), vezes(s / k)] for n, d, s, k, sm, mx, _ in resultado])
    md.append(f"O previsto limita cada latência ao timeout de {seg(TIMEOUT_MS)}.\n")

    plt = figura()
    fig, ax = plt.subplots(figsize=(9, 5.4))
    h = 0.38
    total = len(resultado)
    for j, (n, d, s, k, sm, mx, _) in enumerate(resultado):
        y = total - 1 - j
        ax.barh(y + h / 2, s / 1000, h, color=COR_BARRA_SEQ, label="Sequencial" if j == 0 else None)
        ax.barh(y - h / 2, k / 1000, h, color=COR["concorrente"], label="Concorrente" if j == 0 else None)
        ax.text(s / 1000 + 0.06, y + h / 2, seg(s), va="center", fontsize=8, color="#555")
        ax.text(k / 1000 + 0.06, y - h / 2, seg(k), va="center", fontsize=8, fontweight="bold")
        ax.text(1.02, y, vezes(s / k), transform=ax.get_yaxis_transform(), va="center", fontweight="bold")
    ax.text(1.02, total - 0.45, "speedup", transform=ax.get_yaxis_transform(), fontsize=8, color="#555")
    ax.set_yticks([total - 1 - j for j in range(total)], [f"{r[0]}\n{r[1]}" for r in resultado], fontsize=9)
    ax.set_xlim(0, max(r[2] for r in resultado) / 1000 * 1.12)
    ax.set_ylim(-0.7, total - 0.2)
    ax.set_xlabel("tempo médio da pesquisa (s)")
    ax.grid(axis="y", visible=False)
    melhor = max(r[2] / r[3] for r in resultado)
    ax.set_title(f"Com latências iguais o ganho chega a {vezes(melhor)}; um mercado lento limita o concorrente", pad=26)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, borderaxespad=0.1)
    salvar_figura(plt, fig, "fig-09-exp3-latencia.png")


def analisar_exp4(md: list[str]) -> None:
    dados = ler_csv(CSV_EXP4)
    if not dados:
        return
    resultado = []
    niveis = sorted({int(d["clientes"]) for d in dados})
    for modo in MODOS:
        for n in niveis:
            grupo = [d for d in dados if d["modo"] == modo and int(d["clientes"]) == n]
            reqs = [d for d in grupo if d["cliente"] != "0"]
            lote = next((d for d in grupo if d["cliente"] == "0"), None)
            if not reqs or lote is None:
                continue
            tempos = [float(d["tempo_cliente_ms"]) for d in reqs]
            parede = float(lote["tempo_cliente_ms"])
            incompletas = sum(int(d["mercados_ok"]) < len(PADRAO) for d in reqs)
            falhas = len(lote["falhas"].split("; ")) if lote["falhas"] else 0
            resultado.append((modo, n, len(reqs), media(tempos), max(tempos), parede, len(reqs) / (parede / 1000),
                              incompletas + falhas))
    if not resultado:
        return
    por_cliente = resultado[0][2] // resultado[0][1]
    tabela(md, f"Experimento 4 — múltiplos clientes simultâneos ({por_cliente} pesquisas por cliente, latências padrão)",
           ["Modo", "Clientes", "Pesquisas", "Resposta média", "Resposta máx.", "Tempo total", "Vazão", "Falhas"],
           [[m.capitalize(), n, q, seg(a), seg(mx), seg(p), f"{v:.2f} pesquisas/s".replace(".", ","), f]
            for m, n, q, a, mx, p, v, f in resultado])
    md.append("Cada cliente abre sua própria conexão TCP com o agregador e faz as pesquisas uma após a outra; "
              "todos começam juntos (barreira). Resposta = tempo visto pelo cliente.\n")

    plt = figura()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.9))
    for modo in MODOS:
        pts = [r for r in resultado if r[0] == modo]
        a1.plot([p[1] for p in pts], [p[3] / 1000 for p in pts], "o-", color=COR[modo], lw=2, label=modo.capitalize())
        a2.plot([p[1] for p in pts], [p[6] for p in pts], "o-", color=COR[modo], lw=2, label=modo.capitalize())
        ult = pts[-1]
        a2.text(ult[1] + 0.8, ult[6], f"{ult[6]:.1f}/s".replace(".", ","), va="center", fontsize=8, color=COR[modo])
    for a in (a1, a2):
        a.set_xticks(niveis, [str(n) for n in niveis])
        a.set_xlabel("clientes simultâneos")
        a.set_ylim(bottom=0)
    a1.set_ylabel("tempo de resposta médio (s)")
    a1.set_title("Tempo de resposta não muda com mais clientes", fontsize=11)
    a1.set_ylim(top=max(r[3] for r in resultado) / 1000 * 1.25)
    a1.legend(frameon=False, loc="center right")
    a2.set_ylabel("pesquisas concluídas por segundo")
    a2.set_title("Vazão cresce na proporção dos clientes", fontsize=11)
    a2.set_xlim(right=max(niveis) * 1.12)
    fig.tight_layout()
    salvar_figura(plt, fig, "fig-10-exp4-clientes.png")


def analisar_exp5(md: list[str]) -> None:
    dados = ler_csv(CSV_EXP5)
    if not dados:
        return
    resultado = []
    for cenario, desc in CENARIOS_FALHA:
        for modo in MODOS:
            rs = [d for d in dados if d["cenario"] == cenario and d["modo"] == modo]
            if not rs:
                continue
            resultado.append((cenario, desc, modo, media([float(d["tempo_ms"]) for d in rs]),
                              media([int(d["mercados_ok"]) for d in rs]), media([int(d["tentativas_alvo"]) for d in rs]),
                              sorted({d["erro_alvo"] for d in rs if d["erro_alvo"]}), len(rs)))
    rodadas = resultado[0][7]
    tabela(md, f"Experimento 5 — indisponibilidade do {NOMES[ALVO]} ({rodadas} rodadas por cenário)",
           ["Cenário", "O que acontece", "Modo", "Tempo médio", "Mercados com resposta", f"Tentativas no {NOMES[ALVO]}",
            "Erro informado"],
           [[c, d, m.capitalize(), seg(t), f"{num(o)} de 5", num(a), ", ".join(e) or "—"]
            for c, d, m, t, o, a, e, _ in resultado])

    gantt = ler_csv(CSV_EXP5_GANTT)
    if not gantt:
        return
    plt = figura()
    fig, axes = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
    fim = max(float(g["tempo_total_ms"]) for g in gantt) / 1000
    ordem = list(config.MARKETS)
    for ax, modo in zip(axes, MODOS):
        linhas = {g["mercado"]: g for g in gantt if g["modo"] == modo}
        total = float(next(iter(linhas.values()))["tempo_total_ms"])
        for y, info in enumerate(reversed(ordem)):
            g = linhas[info.id]
            ini, fim_m = float(g["inicio_ms"]) / 1000, float(g["fim_ms"]) / 1000
            falhou = g["status"] != "sucesso"
            ax.barh(y, fim_m - ini, left=ini, height=0.6,
                    color=COR_ERRO if falhou else (COR_BARRA_SEQ if modo == "sequencial" else COR["concorrente"]))
            ax.text(fim_m + 0.05, y, g["erro"] if falhou else seg((fim_m - ini) * 1000), va="center", fontsize=8,
                    color=COR_ERRO if falhou else "#333")
        ax.set_yticks(range(len(ordem)), [i.short for i in reversed(ordem)])
        ax.axvline(0.3, color="#333", ls="--", lw=1)
        ax.axvline(total / 1000, color="#333", lw=1.5)
        ax.text(total / 1000 + 0.05, len(ordem) - 0.45, f"resposta ao cliente: {seg(total)}", fontsize=8, va="bottom")
        ax.set_title(modo.capitalize(), fontsize=10)
        ax.grid(axis="y", visible=False)
        ax.set_xlim(0, fim * 1.4)
        ax.set_ylim(-0.6, len(ordem) - 0.1)
    axes[0].text(0.35, len(ordem) - 0.45, f"{NOMES[ALVO]} sai do ar (0,3 s)", fontsize=8, va="bottom")
    axes[1].set_xlabel("tempo desde o início da pesquisa (s)")
    fig.suptitle(f"{NOMES[ALVO]} cai no meio da pesquisa: o agregador tenta de novo e responde com os outros 4",
                 x=0.01, ha="left", fontweight="bold", fontsize=11)
    fig.tight_layout()
    salvar_figura(plt, fig, "fig-11-exp5-falha.png")


def analisar() -> None:
    log("\nAnalisando os CSV")
    md = ["# Resultados dos experimentos obrigatórios\n",
          f"Gerado por `backend/experimentos/executar.py` a partir dos CSV desta pasta ({time.strftime('%d/%m/%Y %H:%M')}). "
          f"Pesquisa: \"{PRODUTO}\". Latências padrão: {', '.join(f'{NOMES[k]} {v} ms' for k, v in PADRAO.items())}. "
          f"Timeout {config.TCP_TIMEOUT_S:.0f} s; novas tentativas após 0,5 s, 1 s e 2 s.\n"]
    analisar_exp1_e_2(md)
    analisar_exp3(md)
    analisar_exp4(md)
    analisar_exp5(md)
    destino = DADOS / "resultados-experimentos.md"
    destino.write_text("\n".join(md), encoding="utf-8")
    log(f"  → {destino.relative_to(ROOT)}")


# ---------------------------------------------------------------- principal

def main() -> int:
    parser = argparse.ArgumentParser(description="Experimentos obrigatórios do trabalho")
    parser.add_argument("--so", nargs="+", type=int, choices=[1, 2, 3, 4, 5], help="mede só esses experimentos")
    parser.add_argument("--rapido", action="store_true", help="menos rodadas, só para testar o script")
    parser.add_argument("--analisar", action="store_true", help="não mede nada: só refaz tabelas e gráficos dos CSV")
    args = parser.parse_args()

    if not args.analisar:
        from cliente.conexao import ClienteAgregador

        escolhidos = set(args.so or [1, 2, 3, 4, 5])
        rapido = args.rapido
        try:
            c = ClienteAgregador(timeout=120)
        except OSError as exc:
            print(f"Agregador inacessível ({exc}). Rode antes: .venv/bin/python iniciar.py", file=sys.stderr)
            return 1
        with c:
            configurar_todos(c)
            pesquisar(c, "concorrente")  # aquecimento: carrega caches do SQLite antes de medir
            try:
                if escolhidos & {1, 2}:
                    medir_exp1_e_2(c, 3 if rapido else 10)
                if 3 in escolhidos:
                    medir_exp3(c, 2 if rapido else 5)
                if 4 in escolhidos:
                    medir_exp4(c, [1, 2, 4] if rapido else [1, 2, 4, 8, 16, 32], 1 if rapido else 3)
                if 5 in escolhidos:
                    medir_exp5(c, 1 if rapido else 3)
            finally:
                configurar_todos(c)  # devolve os mercados ao normal mesmo se algo der errado

    analisar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
