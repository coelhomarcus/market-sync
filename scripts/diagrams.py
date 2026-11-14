"""Desenha os diagramas de modelagem do relatório (casos de uso, arquitetura e sequência) com matplotlib.

Uso (da raiz do projeto):  .venv/bin/python scripts/diagrams.py
Gera docs/relatorio/figuras/fig-01-casos-de-uso.png, fig-02-arquitetura.png e fig-12-sequencia.png.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

FIGURES_DIR = Path(__file__).resolve().parent.parent / "docs" / "relatorio" / "figuras"
plt.rcParams["font.family"] = ["Helvetica Neue", "DejaVu Sans"]

LINE_COLOR = "#c9c8bd"
TEXT_COLOR = "#1f1f1f"
GRAY = "#5f5f5f"
BLUE = "#2b7bd8"
LIGHT_BLUE = "#e8f1fb"
ORANGE = "#d9822b"
RED = "#d64545"


def box(ax, x, y, w, h, title, sub=None, highlight=False, bg="white", size=11):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.12",
                                fc=LIGHT_BLUE if highlight else bg, ec=BLUE if highlight else LINE_COLOR, lw=2 if highlight else 1.3))
    if sub:
        ax.text(x + 0.18, y + h * 0.64, title, fontsize=size, fontweight="bold", color=TEXT_COLOR, va="center")
        ax.text(x + 0.18, y + h * 0.3, sub, fontsize=size - 1.5, color=GRAY, va="center")
    else:
        ax.text(x + 0.18, y + h - 0.3, title, fontsize=size, fontweight="bold", color=GRAY, va="center")


def arrow(ax, a, b, text=None, color=LINE_COLOR, dx=0, dy=0.12, style="-|>", ls="-", size=9, text_color=GRAY, conn="arc3"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=12, color=color, lw=1.4, ls=ls, connectionstyle=conn))
    if text:
        ax.text((a[0] + b[0]) / 2 + dx, (a[1] + b[1]) / 2 + dy, text, fontsize=size, color=text_color, ha="center", va="bottom")


def architecture() -> None:
    fig, ax = plt.subplots(figsize=(13.5, 8.6))
    ax.set_xlim(0, 13.5)
    ax.set_ylim(0, 8.6)
    ax.axis("off")
    ax.text(0.2, 8.3, "Cliente, agregador e cinco mercados: processos separados que conversam por sockets TCP",
            fontsize=14, fontweight="bold", color=TEXT_COLOR, va="center")

    # colunas
    box(ax, 0.2, 0.3, 3.1, 7.5, "Clientes")
    box(ax, 4.3, 0.3, 4.4, 7.5, "Agregador (1 processo)")
    box(ax, 9.7, 0.3, 3.6, 7.5, "5 processos de mercado")

    # clientes
    box(ax, 0.4, 6.2, 2.7, 1.0, "Cliente de terminal", "python -m client", highlight=True)
    box(ax, 0.4, 5.05, 2.7, 1.0, "Loja web", "busca, cesta, modo")

    # terminal com o log
    ax.add_patch(FancyBboxPatch((0.4, 0.55), 2.7, 2.35, boxstyle="round,pad=0,rounding_size=0.12", fc="#1f2326", ec="#1f2326"))
    ax.text(0.55, 2.62, "Painel ao vivo (terminal)", fontsize=10, fontweight="bold", color="white", va="center")
    panel_lines = [("╭ \"arroz\" · concorrente ──", "#7fb3ff"), ("Aurora    ███········ ✔", "#7fb3ff"),
              ("SuperVila █████······ ✔", "#7fb3ff"), ("Empório   ███████···· ✔", "#7fb3ff"),
              ("Max       █████████·· ✔", "#7fb3ff"), ("Ipê       ███████████ ✔", "#7fb3ff"),
              ("╰─ 1,18 s · 5 threads ─╯", "#c8f7c5")]
    for k, (line, line_color) in enumerate(panel_lines):
        ax.text(0.55, 2.28 - k * 0.235, line, fontsize=7.6, color=line_color, family=["Menlo", "DejaVu Sans Mono"], va="center")

    # agregador
    box(ax, 4.5, 6.3, 4.0, 0.85, "tcp_server.py · porta 5050", "uma thread por cliente", highlight=True)
    box(ax, 4.5, 5.2, 4.0, 0.85, "api_web.py · porta 8000", "3 rotas HTTP da loja")
    box(ax, 4.5, 4.25, 4.0, 0.8, "aggregator.py", "escolhe a estratégia e mede o tempo")
    box(ax, 4.5, 3.15, 1.9, 0.8, "sequential.py", "um por vez", highlight=True, size=10)
    box(ax, 6.6, 3.15, 1.9, 0.8, "concurrent.py", "5 threads", highlight=True, size=10)
    box(ax, 4.5, 2.05, 4.0, 0.8, "market_query.py", "conecta, envia, espera, retry")
    box(ax, 4.5, 0.6, 4.0, 0.8, "display.py", "desenha o painel (Rich)")

    # mercados
    markets = [("Mercado Aurora", "5001", "300"), ("SuperVila", "5002", "500"), ("Empório Sol", "5003", "700"),
                ("Max Atacarejo", "5004", "900"), ("Mercadinho Ipê", "5005", "1200")]
    ys = [6.15, 4.95, 3.75, 2.55, 1.35]
    for (name, port, lat), y in zip(markets, ys):
        box(ax, 9.9, y - 0.45, 3.2, 1.0, name, f"porta {port} · {lat} ms · SQLite próprio")

    # setas
    arrow(ax, (3.1, 6.72), (4.5, 6.72), "TCP · JSON\npor linha", color=BLUE, text_color=BLUE, dy=0.08)
    arrow(ax, (3.1, 5.6), (4.5, 5.6), "HTTP", dy=0.06)
    ax.plot([8.5, 8.62, 8.62], [6.72, 6.72, 4.65], color=BLUE, lw=1.4)
    arrow(ax, (8.62, 4.65), (8.5, 4.65), color=BLUE)
    arrow(ax, (6.5, 5.2), (6.5, 5.05))
    arrow(ax, (5.45, 4.25), (5.45, 3.95))
    arrow(ax, (7.55, 4.25), (7.55, 3.95))
    arrow(ax, (5.45, 3.15), (5.45, 2.85))
    arrow(ax, (7.55, 3.15), (7.55, 2.85))
    arrow(ax, (6.5, 2.05), (6.5, 1.4), "eventos", dx=0.42, dy=0.15, ls="--")
    arrow(ax, (4.5, 1.0), (3.1, 1.0), "12 quadros/s", dy=0.06, ls="--")
    for y in ys:
        arrow(ax, (8.5, 2.45), (9.9, y + 0.05), color=BLUE if y == ys[2] else LINE_COLOR)
    ax.text(9.15, 3.85, "TCP · JSON\npor linha", fontsize=9, color=BLUE, ha="center", va="bottom")
    ax.text(11.5, 0.42, "cada mercado grava o log em logs/<mercado>.log", fontsize=8, color=GRAY, ha="center", va="center")

    fig.savefig(FIGURES_DIR / "fig-02-arquitetura.png", dpi=110, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def actor(ax, x, y, name):
    """Bonequinho UML de um ator, com o nome embaixo."""
    ax.add_patch(plt.Circle((x, y + 0.55), 0.17, fill=False, ec=GRAY, lw=1.6))
    ax.plot([x, x], [y + 0.38, y - 0.05], color=GRAY, lw=1.6)
    ax.plot([x - 0.3, x + 0.3], [y + 0.22, y + 0.22], color=GRAY, lw=1.6)
    ax.plot([x, x - 0.25], [y - 0.05, y - 0.45], color=GRAY, lw=1.6)
    ax.plot([x, x + 0.25], [y - 0.05, y - 0.45], color=GRAY, lw=1.6)
    ax.text(x, y - 0.62, name, ha="center", va="top", fontsize=11, fontweight="bold", color=TEXT_COLOR)


def use_cases() -> None:
    from matplotlib.patches import Ellipse

    fig, ax = plt.subplots(figsize=(13, 9.6))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 9.6)
    ax.axis("off")
    ax.text(0.2, 9.35, "Todo caso de uso que busca preços passa pela consulta TCP aos mercados",
            fontsize=14, fontweight="bold", color=TEXT_COLOR, va="center")
    ax.add_patch(FancyBboxPatch((2.6, 0.3), 8.0, 8.6, boxstyle="round,pad=0,rounding_size=0.15", fc="white", ec=LINE_COLOR, lw=1.4))
    ax.text(2.85, 8.62, "Comparador de Preços", fontsize=11, fontweight="bold", color=GRAY, va="center")

    cases = ["UC01 Pesquisar produto", "UC02 Comparar preços de um produto", "UC03 Escolher o modo de consulta",
             "UC04 Montar e comparar cesta", "UC05 Acompanhar as consultas no terminal", "UC06 Comparar modos / experimentos",
             "UC07 Exportar resultados (CSV)", "UC08 Configurar ou derrubar mercado"]
    cx, w, h = 5.3, 4.6, 0.66
    ys = [8.0 - k * 0.98 for k in range(len(cases))]
    for name, y in zip(cases, ys):
        ax.add_patch(Ellipse((cx, y), w, h, fc="white", ec=LINE_COLOR, lw=1.4))
        ax.text(cx, y, name, ha="center", va="center", fontsize=10.5, color=TEXT_COLOR)
    uc9 = (9.15, 4.6)
    ax.add_patch(Ellipse(uc9, 2.5, 1.15, fc=LIGHT_BLUE, ec=BLUE, lw=2))
    ax.text(*uc9, "UC09 Consultar\nmercados via TCP", ha="center", va="center", fontsize=11, fontweight="bold", color=TEXT_COLOR)

    consumer, evaluator, service = (1.2, 6.6), (1.2, 2.6), (12.1, 4.6)
    actor(ax, *consumer, "Consumidor")
    actor(ax, *evaluator, "Avaliador /\nOperador")
    actor(ax, *service, "Serviço de\nmercado")

    edge = cx - w / 2
    for k in (0, 1, 2, 3):
        ax.plot([consumer[0] + 0.35, edge], [consumer[1] + 0.2, ys[k]], color=LINE_COLOR, lw=1.3)
    for k in (2, 4, 5, 6, 7):
        ax.plot([evaluator[0] + 0.35, edge], [evaluator[1] + 0.2, ys[k]], color=LINE_COLOR, lw=1.3)
    ax.plot([uc9[0] + 1.25, service[0] - 0.35], [uc9[1], service[1] + 0.2], color=LINE_COLOR, lw=1.3)
    for k in (0, 1, 3, 5):
        start = (cx + w / 2 - 0.05, ys[k])
        end = (uc9[0] - 0.9, uc9[1] + (0.45 if ys[k] > uc9[1] else -0.45))
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=11, color="#9a9a8f", lw=1.2, ls="--"))
    ax.text(8.15, 6.7, "«include»", fontsize=9, color=GRAY, ha="center")
    ax.text(8.15, 3.55, "«include»", fontsize=9, color=GRAY, ha="center")

    fig.savefig(FIGURES_DIR / "fig-01-casos-de-uso.png", dpi=110, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def sequence() -> None:
    fig, ax = plt.subplots(figsize=(13.5, 11.5))
    ax.set_xlim(0, 13.5)
    ax.set_ylim(0, 11.5)
    ax.axis("off")
    ax.text(0.2, 11.2, "Sequência de uma pesquisa concorrente (operação \"consultar\"), com um mercado fora do ar",
            fontsize=14, fontweight="bold", color=TEXT_COLOR, va="center")

    actors = [("Usuário", 0.8, 1.2), ("Cliente\n(python -m client)", 2.6, 1.6), ("Agregador\n(thread do cliente)", 4.8, 1.8),
              ("Threads de consulta\n(ThreadPoolExecutor)", 7.1, 2.1), ("Aurora\n:5001", 9.3, 1.1), ("Max\n:5004", 10.9, 1.1),
              ("Ipê\n:5005", 12.6, 1.1)]
    x = {name.split("\n")[0]: px for name, px, _ in actors}
    top, base = 10.3, 0.3
    for name, px, w in actors:
        ax.add_patch(FancyBboxPatch((px - w / 2, top), w, 0.6, boxstyle="round,pad=0,rounding_size=0.08",
                                    fc="white", ec=LINE_COLOR, lw=1.3))
        ax.text(px, top + 0.3, name, ha="center", va="center", fontsize=9, fontweight="bold", color=TEXT_COLOR)
        ax.plot([px, px], [base, top], color=LINE_COLOR, lw=1, ls=(0, (4, 3)), zorder=0)

    def message_arrow(src, dst, y, text, color=TEXT_COLOR, ls="-", is_return=False, size=8.5, side="centro"):
        a, b = x[src], x[dst]
        arrow(ax, (a, y), (b, y), color=color, ls="--" if is_return else ls)
        middle = (a + b) / 2 if side == "centro" else (a + 0.1 if b > a else a - 0.1)
        ax.text(middle, y + 0.06, text, fontsize=size, color=color, ha="center" if side == "centro" else ("left" if b > a else "right"),
                va="bottom", family=["Menlo", "DejaVu Sans Mono"] if text.startswith("{") else None, zorder=5,
                bbox=dict(fc="white", ec="none", pad=0.5) if text else None)

    def note(px, y, text, w=2.0, color=GRAY):
        ax.add_patch(Rectangle((px - w / 2, y - 0.2), w, 0.4, fc="#fbfaf3", ec=LINE_COLOR, lw=1))
        ax.text(px, y, text, fontsize=8, ha="center", va="center", color=color)

    def activation(px, y0, y1, color="#eeeeee"):
        ax.add_patch(Rectangle((px - 0.08, y1), 0.16, y0 - y1, fc=color, ec="#999", lw=0.8, zorder=2))

    def frame_box(x0, x1, y0, y1, label, text):
        ax.add_patch(Rectangle((x0, y1), x1 - x0, y0 - y1, fill=False, ec="#8a8a8a", lw=1))
        ax.add_patch(Rectangle((x0, y0 - 0.32), 0.55, 0.32, fc="#efefef", ec="#8a8a8a", lw=1))
        ax.text(x0 + 0.27, y0 - 0.16, label, fontsize=8, fontweight="bold", ha="center", va="center")
        ax.text(x0 + 0.65, y0 - 0.16, text, fontsize=8, color=GRAY, va="center")

    y = 9.9
    message_arrow("Usuário", "Cliente", y, "digita \"arroz\"")
    y -= 0.55
    message_arrow("Cliente", "Agregador", y, "connect() → SYN, SYN-ACK, ACK (porta 5050)", color=GRAY)
    activation(x["Agregador"], y, 1.65)
    y -= 0.55
    message_arrow("Cliente", "Agregador", y, '{"operacao":"consultar","produto":"arroz","modo":"concorrente"}\\n', color=BLUE)
    y -= 0.55
    message_arrow("Agregador", "Threads de consulta", y, "cria 5 threads (uma por mercado)")
    activation(x["Threads de consulta"], y, 4.35, color=LIGHT_BLUE)

    # bloco par
    y0 = y - 0.25
    frame_box(5.9, 13.3, y0, 4.5, "par", "as 5 consultas acontecem ao mesmo tempo")
    y -= 0.85
    for target in ("Aurora", "Max", "Ipê"):
        message_arrow("Threads de consulta", target, y, "", color=BLUE)
    ax.text(x["Threads de consulta"] + 0.15, y + 0.06, '{"cmd":"SEARCH","q":"arroz"}\\n', fontsize=8, color=BLUE, va="bottom",
            family=["Menlo", "DejaVu Sans Mono"])
    ax.text(13.2, y0 - 0.16, "SuperVila e Empório Sol: igual, omitidos", fontsize=7.5, color=GRAY, ha="right", va="center")
    activation(x["Aurora"], y, y - 0.9)
    activation(x["Max"], y, y - 1.6)
    activation(x["Ipê"], y, y - 0.5)
    message_arrow("Aurora", "Threads de consulta", y - 0.9, '{"ok":true,"data":{"items":[…]}}', is_return=True, size=8)
    ax.text(x["Aurora"] + 0.15, y - 0.9, "~300 ms", fontsize=8, color=GRAY, va="center")
    message_arrow("Max", "Threads de consulta", y - 1.6, "itens", is_return=True, size=8)
    ax.text(x["Max"] + 0.15, y - 1.6, "~900 ms", fontsize=8, color=GRAY, va="center")
    # Ipê fora do ar
    yi = y - 0.5
    ax.text(x["Ipê"], yi - 0.05, "✕ fecha sem responder", fontsize=8, color=RED, ha="center", va="top")
    yr = y - 2.2
    message_arrow("Threads de consulta", "Ipê", yr, "nova tentativa após 0,5 s → 1 s → 2 s (4 no total)", color=RED, size=8)
    note(x["Ipê"] - 0.2, yr - 0.45, "fora do ar: 4 tentativas", w=1.9, color=RED)

    y = 4.1
    message_arrow("Threads de consulta", "Agregador", y, "5 MarketResult (4 ok, 1 erro)", is_return=True)
    y -= 0.5
    note(x["Agregador"], y, "agrupa por produto, ordena por preço, marca o menor", w=3.6)
    y -= 0.6
    message_arrow("Agregador", "Cliente", y, '{"status":"parcial","resultados":[…],"tempo_total_ms":3520}', is_return=True, color=BLUE, size=8)
    y -= 0.55
    message_arrow("Cliente", "Usuário", y, "tabela de preços, ★ menor preço, tempo de cada mercado", is_return=True)
    y -= 0.55
    message_arrow("Cliente", "Agregador", y, '{"operacao":"encerrar"}\\n', color=BLUE)
    y -= 0.45
    message_arrow("Agregador", "Cliente", y, '{"status":"sucesso","mensagem":"conexão encerrada"} + FIN', is_return=True, color=GRAY, size=8)

    fig.savefig(FIGURES_DIR / "fig-12-sequencia.png", dpi=110, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    use_cases()
    architecture()
    sequence()
    print("ok: fig-01-casos-de-uso.png, fig-02-arquitetura.png, fig-12-sequencia.png")
