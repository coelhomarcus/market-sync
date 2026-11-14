"""O que os cinco experimentos compartilham: caminhos, formatação, CSV, gráficos e acesso ao sistema.

Cada experimento (exp1_… a exp5_…) tem duas funções:
    measure(client, quick)  mede pelo cliente TCP e grava o CSV em docs/relatorio/dados/
    analyze(md)             lê o CSV e gera a tabela (em md) e o gráfico (docs/relatorio/figuras/)
"""

from __future__ import annotations

import csv
import math
import statistics
import sys
import time

from common import config

DATA_DIR = config.ROOT / "docs" / "relatorio" / "dados"
FIGURES_DIR = config.ROOT / "docs" / "relatorio" / "figuras"

PRODUCT = "arroz"  # a pesquisa usada em todos os experimentos
MODES = ("sequencial", "concorrente")
COLOR = {"sequencial": "#8f8e80", "concorrente": "#2b7bd8"}
SEQ_BAR_COLOR = "#c5c4b7"
ERROR_COLOR = "#d64545"
DEFAULT_LATENCIES = {m.id: m.latency_ms for m in config.MARKETS}
SHORT_NAMES = {m.id: m.short for m in config.MARKETS}
TIMEOUT_MS = config.TCP_TIMEOUT_S * 1000


# ---------------------------------------------------------------- formatação (texto em português)

def log(text: str) -> None:
    print(text, flush=True)


def mean(xs: list[float]) -> float:
    return statistics.fmean(xs) if xs else math.nan


def stdev(xs: list[float]) -> float:
    return statistics.stdev(xs) if len(xs) > 1 else 0.0


def fmt_s(ms: float) -> str:
    """1234 → '1,23 s'; 456 → '456 ms'."""
    return f"{ms / 1000:.2f} s".replace(".", ",") if ms >= 1000 else f"{ms:.0f} ms"


def fmt_x(x: float) -> str:
    """3.14 → '3,1×' (speedup)."""
    return f"{x:.1f}×".replace(".", ",")


def fmt_num(x: float) -> str:
    return f"{x:.1f}".replace(".0", "").replace(".", ",")


def expected(latencies: dict[str, int]) -> tuple[float, float]:
    """Modelo: sequencial ≈ soma das latências; concorrente ≈ a maior (as duas limitadas pelo timeout)."""
    effective = [min(v, TIMEOUT_MS) for v in latencies.values()]
    return sum(effective), max(effective)


# ---------------------------------------------------------------- CSV e tabelas

def save_csv(name: str, header: list[str], rows: list[list]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / name, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    log(f"  → {(DATA_DIR / name).relative_to(config.ROOT)}")


def read_csv(name: str) -> list[dict] | None:
    path = DATA_DIR / name
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def table(md: list[str], title: str, header: list[str], rows: list[list]) -> None:
    """Acrescenta uma tabela em Markdown ao relatório de resultados."""
    md.append(f"## {title}\n")
    md.append("| " + " | ".join(header) + " |")
    md.append("|" + "---|" * len(header))
    for row in rows:
        md.append("| " + " | ".join(str(c) for c in row) + " |")
    md.append("")


# ---------------------------------------------------------------- gráficos

def figure_setup():
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


def save_figure(plt, fig, name: str) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES_DIR / name, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    log(f"  → {(FIGURES_DIR / name).relative_to(config.ROOT)}")


# ---------------------------------------------------------------- acesso ao sistema (sempre pelo cliente TCP)

def configure_all(client, latencies: dict[str, int] | None = None, online: bool = True) -> None:
    """Põe todos os mercados no ar com as latências dadas (padrão: as do config)."""
    for market_id, latency in (latencies or DEFAULT_LATENCIES).items():
        r = client.configure(market_id, latency_ms=latency, online=online)
        if r["status"] != "sucesso":
            raise RuntimeError(f"não consegui configurar {market_id}: {r.get('mensagem')}")


def run_search(client, mode: str) -> dict:
    """Uma pesquisa por PRODUCT; acrescenta o tempo visto pelo cliente (inclui o TCP até o agregador)."""
    t = time.perf_counter()
    r = client.search(PRODUCT, mode, limit=1)
    r["tempo_cliente_ms"] = round((time.perf_counter() - t) * 1000, 2)
    return r


def ok_count(r: dict) -> int:
    return sum(m["status"] == "sucesso" for m in r["mercados"])


def alternating(i: int) -> tuple[str, ...]:
    """Alterna a ordem dos modos a cada rodada: nenhum deles leva vantagem por cache ou aquecimento."""
    return MODES if i % 2 == 0 else tuple(reversed(MODES))


# ---------------------------------------------------------------- rodar

def run(experiments: list, quick: bool = False, measure: bool = True) -> int:
    """Mede os experimentos pedidos (se measure) e depois refaz a análise de todos os que têm CSV."""
    from client.connection import AggregatorClient

    from . import all_experiments

    if measure:
        try:
            client = AggregatorClient(timeout=120)
        except OSError as exc:
            print(f"Agregador inacessível ({exc}). Rode antes: .venv/bin/python start.py --quiet", file=sys.stderr)
            return 1
        with client:
            configure_all(client)
            run_search(client, "concorrente")  # aquecimento: carrega caches do SQLite antes de medir
            try:
                for exp in experiments:
                    exp.measure(client, quick)
            finally:
                configure_all(client)  # devolve os mercados ao normal mesmo se algo der errado

    log("\nAnalisando os CSV")
    md = ["# Resultados dos experimentos obrigatórios\n",
          f"Gerado por `experiments/` a partir dos CSV desta pasta ({time.strftime('%d/%m/%Y %H:%M')}). "
          f"Pesquisa: \"{PRODUCT}\". Latências padrão: "
          f"{', '.join(f'{SHORT_NAMES[k]} {v} ms' for k, v in DEFAULT_LATENCIES.items())}. "
          f"Timeout {config.TCP_TIMEOUT_S:.0f} s; novas tentativas após 0,5 s, 1 s e 2 s.\n"]
    for exp in all_experiments():
        exp.analyze(md)
    dest = DATA_DIR / "resultados-experimentos.md"
    dest.write_text("\n".join(md), encoding="utf-8")
    log(f"  → {dest.relative_to(config.ROOT)}")
    return 0


def run_alone(exp) -> None:
    """Para rodar um experimento sozinho:  python -m experiments.exp3_latency [--quick] [--analyze]"""
    quick = "--quick" in sys.argv
    measure = "--analyze" not in sys.argv
    sys.exit(run([exp], quick=quick, measure=measure))
