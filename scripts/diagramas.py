"""Desenha os diagramas de modelagem do relatório (casos de uso, arquitetura e sequência) com matplotlib.

Uso (da raiz do projeto):  backend/.venv/bin/python scripts/diagramas.py
Gera docs/relatorio/figuras/fig-01-casos-de-uso.png, fig-02-arquitetura.png e fig-12-sequencia.png.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

FIGURAS = Path(__file__).resolve().parent.parent / "docs" / "relatorio" / "figuras"
plt.rcParams["font.family"] = ["Helvetica Neue", "DejaVu Sans"]

LINHA = "#c9c8bd"
TEXTO = "#1f1f1f"
CINZA = "#5f5f5f"
AZUL = "#2b7bd8"
AZUL_CLARO = "#e8f1fb"
LARANJA = "#d9822b"
VERMELHO = "#d64545"


def caixa(ax, x, y, w, h, titulo, sub=None, destaque=False, fundo="white", tam=11):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.12",
                                fc=AZUL_CLARO if destaque else fundo, ec=AZUL if destaque else LINHA, lw=2 if destaque else 1.3))
    if sub:
        ax.text(x + 0.18, y + h * 0.64, titulo, fontsize=tam, fontweight="bold", color=TEXTO, va="center")
        ax.text(x + 0.18, y + h * 0.3, sub, fontsize=tam - 1.5, color=CINZA, va="center")
    else:
        ax.text(x + 0.18, y + h - 0.3, titulo, fontsize=tam, fontweight="bold", color=CINZA, va="center")


def seta(ax, a, b, texto=None, cor=LINHA, dx=0, dy=0.12, estilo="-|>", ls="-", tam=9, cor_texto=CINZA, conn="arc3"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=estilo, mutation_scale=12, color=cor, lw=1.4, ls=ls, connectionstyle=conn))
    if texto:
        ax.text((a[0] + b[0]) / 2 + dx, (a[1] + b[1]) / 2 + dy, texto, fontsize=tam, color=cor_texto, ha="center", va="bottom")


def arquitetura() -> None:
    fig, ax = plt.subplots(figsize=(13.5, 8.6))
    ax.set_xlim(0, 13.5)
    ax.set_ylim(0, 8.6)
    ax.axis("off")
    ax.text(0.2, 8.3, "Cliente, agregador e cinco mercados: processos separados que conversam por sockets TCP",
            fontsize=14, fontweight="bold", color=TEXTO, va="center")

    # colunas
    caixa(ax, 0.2, 0.3, 3.1, 7.5, "Clientes")
    caixa(ax, 4.3, 0.3, 4.4, 7.5, "Agregador (1 processo)")
    caixa(ax, 9.7, 0.3, 3.6, 7.5, "5 processos de mercado")

    # clientes
    caixa(ax, 0.4, 6.2, 2.7, 1.0, "Cliente de terminal", "python -m cliente", destaque=True)
    caixa(ax, 0.4, 5.05, 2.7, 1.0, "Loja web", "busca, cesta, modo")

    # terminal com o log
    ax.add_patch(FancyBboxPatch((0.4, 0.55), 2.7, 2.35, boxstyle="round,pad=0,rounding_size=0.12", fc="#1f2326", ec="#1f2326"))
    ax.text(0.55, 2.62, "Painel ao vivo (terminal)", fontsize=10, fontweight="bold", color="white", va="center")
    painel = [("╭ \"arroz\" · concorrente ──", "#7fb3ff"), ("Aurora    ███········ ✔", "#7fb3ff"),
              ("SuperVila █████······ ✔", "#7fb3ff"), ("Empório   ███████···· ✔", "#7fb3ff"),
              ("Max       █████████·· ✔", "#7fb3ff"), ("Ipê       ███████████ ✔", "#7fb3ff"),
              ("╰─ 1,18 s · 5 threads ─╯", "#c8f7c5")]
    for k, (linha, cor_linha) in enumerate(painel):
        ax.text(0.55, 2.28 - k * 0.235, linha, fontsize=7.6, color=cor_linha, family=["Menlo", "DejaVu Sans Mono"], va="center")

    # agregador
    caixa(ax, 4.5, 6.3, 4.0, 0.85, "servidor_tcp.py · porta 5050", "uma thread por cliente", destaque=True)
    caixa(ax, 4.5, 5.2, 4.0, 0.85, "api_web.py · porta 8000", "3 rotas HTTP da loja")
    caixa(ax, 4.5, 4.25, 4.0, 0.8, "agregador.py", "escolhe a estratégia e mede o tempo")
    caixa(ax, 4.5, 3.15, 1.9, 0.8, "sequencial.py", "um por vez", destaque=True, tam=10)
    caixa(ax, 6.6, 3.15, 1.9, 0.8, "concorrente.py", "5 threads", destaque=True, tam=10)
    caixa(ax, 4.5, 2.05, 4.0, 0.8, "consulta_mercado.py", "conecta, envia, espera, retry")
    caixa(ax, 4.5, 0.6, 4.0, 0.8, "registro.py", "desenha o painel (Rich)")

    # mercados
    mercados = [("Mercado Aurora", "5001", "300"), ("SuperVila", "5002", "500"), ("Empório Sol", "5003", "700"),
                ("Max Atacarejo", "5004", "900"), ("Mercadinho Ipê", "5005", "1200")]
    ys = [6.15, 4.95, 3.75, 2.55, 1.35]
    for (nome, porta, lat), y in zip(mercados, ys):
        caixa(ax, 9.9, y - 0.45, 3.2, 1.0, nome, f"porta {porta} · {lat} ms · SQLite próprio")

    # setas
    seta(ax, (3.1, 6.72), (4.5, 6.72), "TCP · JSON\npor linha", cor=AZUL, cor_texto=AZUL, dy=0.08)
    seta(ax, (3.1, 5.6), (4.5, 5.6), "HTTP", dy=0.06)
    ax.plot([8.5, 8.62, 8.62], [6.72, 6.72, 4.65], color=AZUL, lw=1.4)
    seta(ax, (8.62, 4.65), (8.5, 4.65), cor=AZUL)
    seta(ax, (6.5, 5.2), (6.5, 5.05))
    seta(ax, (5.45, 4.25), (5.45, 3.95))
    seta(ax, (7.55, 4.25), (7.55, 3.95))
    seta(ax, (5.45, 3.15), (5.45, 2.85))
    seta(ax, (7.55, 3.15), (7.55, 2.85))
    seta(ax, (6.5, 2.05), (6.5, 1.4), "eventos", dx=0.42, dy=0.15, ls="--")
    seta(ax, (4.5, 1.0), (3.1, 1.0), "12 quadros/s", dy=0.06, ls="--")
    for y in ys:
        seta(ax, (8.5, 2.45), (9.9, y + 0.05), cor=AZUL if y == ys[2] else LINHA)
    ax.text(9.15, 3.85, "TCP · JSON\npor linha", fontsize=9, color=AZUL, ha="center", va="bottom")
    ax.text(11.5, 0.42, "cada mercado grava o log em logs/<mercado>.log", fontsize=8, color=CINZA, ha="center", va="center")

    fig.savefig(FIGURAS / "fig-02-arquitetura.png", dpi=110, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def ator(ax, x, y, nome):
    """Bonequinho UML de um ator, com o nome embaixo."""
    ax.add_patch(plt.Circle((x, y + 0.55), 0.17, fill=False, ec=CINZA, lw=1.6))
    ax.plot([x, x], [y + 0.38, y - 0.05], color=CINZA, lw=1.6)
    ax.plot([x - 0.3, x + 0.3], [y + 0.22, y + 0.22], color=CINZA, lw=1.6)
    ax.plot([x, x - 0.25], [y - 0.05, y - 0.45], color=CINZA, lw=1.6)
    ax.plot([x, x + 0.25], [y - 0.05, y - 0.45], color=CINZA, lw=1.6)
    ax.text(x, y - 0.62, nome, ha="center", va="top", fontsize=11, fontweight="bold", color=TEXTO)


def casos_de_uso() -> None:
    from matplotlib.patches import Ellipse

    fig, ax = plt.subplots(figsize=(13, 9.6))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 9.6)
    ax.axis("off")
    ax.text(0.2, 9.35, "Todo caso de uso que busca preços passa pela consulta TCP aos mercados",
            fontsize=14, fontweight="bold", color=TEXTO, va="center")
    ax.add_patch(FancyBboxPatch((2.6, 0.3), 8.0, 8.6, boxstyle="round,pad=0,rounding_size=0.15", fc="white", ec=LINHA, lw=1.4))
    ax.text(2.85, 8.62, "Comparador de Preços", fontsize=11, fontweight="bold", color=CINZA, va="center")

    casos = ["UC01 Pesquisar produto", "UC02 Comparar preços de um produto", "UC03 Escolher o modo de consulta",
             "UC04 Montar e comparar cesta", "UC05 Acompanhar as consultas no terminal", "UC06 Comparar modos / experimentos",
             "UC07 Exportar resultados (CSV)", "UC08 Configurar ou derrubar mercado"]
    cx, w, h = 5.3, 4.6, 0.66
    ys = [8.0 - k * 0.98 for k in range(len(casos))]
    for nome, y in zip(casos, ys):
        ax.add_patch(Ellipse((cx, y), w, h, fc="white", ec=LINHA, lw=1.4))
        ax.text(cx, y, nome, ha="center", va="center", fontsize=10.5, color=TEXTO)
    uc9 = (9.15, 4.6)
    ax.add_patch(Ellipse(uc9, 2.5, 1.15, fc=AZUL_CLARO, ec=AZUL, lw=2))
    ax.text(*uc9, "UC09 Consultar\nmercados via TCP", ha="center", va="center", fontsize=11, fontweight="bold", color=TEXTO)

    consumidor, avaliador, servico = (1.2, 6.6), (1.2, 2.6), (12.1, 4.6)
    ator(ax, *consumidor, "Consumidor")
    ator(ax, *avaliador, "Avaliador /\nOperador")
    ator(ax, *servico, "Serviço de\nmercado")

    borda = cx - w / 2
    for k in (0, 1, 2, 3):
        ax.plot([consumidor[0] + 0.35, borda], [consumidor[1] + 0.2, ys[k]], color=LINHA, lw=1.3)
    for k in (2, 4, 5, 6, 7):
        ax.plot([avaliador[0] + 0.35, borda], [avaliador[1] + 0.2, ys[k]], color=LINHA, lw=1.3)
    ax.plot([uc9[0] + 1.25, servico[0] - 0.35], [uc9[1], servico[1] + 0.2], color=LINHA, lw=1.3)
    for k in (0, 1, 3, 5):
        inicio = (cx + w / 2 - 0.05, ys[k])
        fim = (uc9[0] - 0.9, uc9[1] + (0.45 if ys[k] > uc9[1] else -0.45))
        ax.add_patch(FancyArrowPatch(inicio, fim, arrowstyle="-|>", mutation_scale=11, color="#9a9a8f", lw=1.2, ls="--"))
    ax.text(8.15, 6.7, "«include»", fontsize=9, color=CINZA, ha="center")
    ax.text(8.15, 3.55, "«include»", fontsize=9, color=CINZA, ha="center")

    fig.savefig(FIGURAS / "fig-01-casos-de-uso.png", dpi=110, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def sequencia() -> None:
    fig, ax = plt.subplots(figsize=(13.5, 11.5))
    ax.set_xlim(0, 13.5)
    ax.set_ylim(0, 11.5)
    ax.axis("off")
    ax.text(0.2, 11.2, "Sequência de uma pesquisa concorrente (operação \"consultar\"), com um mercado fora do ar",
            fontsize=14, fontweight="bold", color=TEXTO, va="center")

    atores = [("Usuário", 0.8, 1.2), ("Cliente\n(python -m cliente)", 2.6, 1.6), ("Agregador\n(thread do cliente)", 4.8, 1.8),
              ("Threads de consulta\n(ThreadPoolExecutor)", 7.1, 2.1), ("Aurora\n:5001", 9.3, 1.1), ("Max\n:5004", 10.9, 1.1),
              ("Ipê\n:5005", 12.6, 1.1)]
    x = {nome.split("\n")[0]: px for nome, px, _ in atores}
    topo, base = 10.3, 0.3
    for nome, px, w in atores:
        ax.add_patch(FancyBboxPatch((px - w / 2, topo), w, 0.6, boxstyle="round,pad=0,rounding_size=0.08",
                                    fc="white", ec=LINHA, lw=1.3))
        ax.text(px, topo + 0.3, nome, ha="center", va="center", fontsize=9, fontweight="bold", color=TEXTO)
        ax.plot([px, px], [base, topo], color=LINHA, lw=1, ls=(0, (4, 3)), zorder=0)

    def msg(de, para, y, texto, cor=TEXTO, ls="-", retorno=False, tam=8.5, lado="centro"):
        a, b = x[de], x[para]
        seta(ax, (a, y), (b, y), cor=cor, ls="--" if retorno else ls)
        meio = (a + b) / 2 if lado == "centro" else (a + 0.1 if b > a else a - 0.1)
        ax.text(meio, y + 0.06, texto, fontsize=tam, color=cor, ha="center" if lado == "centro" else ("left" if b > a else "right"),
                va="bottom", family=["Menlo", "DejaVu Sans Mono"] if texto.startswith("{") else None, zorder=5,
                bbox=dict(fc="white", ec="none", pad=0.5) if texto else None)

    def nota(px, y, texto, w=2.0, cor=CINZA):
        ax.add_patch(Rectangle((px - w / 2, y - 0.2), w, 0.4, fc="#fbfaf3", ec=LINHA, lw=1))
        ax.text(px, y, texto, fontsize=8, ha="center", va="center", color=cor)

    def ativo(px, y0, y1, cor="#eeeeee"):
        ax.add_patch(Rectangle((px - 0.08, y1), 0.16, y0 - y1, fc=cor, ec="#999", lw=0.8, zorder=2))

    def moldura(x0, x1, y0, y1, rotulo, texto):
        ax.add_patch(Rectangle((x0, y1), x1 - x0, y0 - y1, fill=False, ec="#8a8a8a", lw=1))
        ax.add_patch(Rectangle((x0, y0 - 0.32), 0.55, 0.32, fc="#efefef", ec="#8a8a8a", lw=1))
        ax.text(x0 + 0.27, y0 - 0.16, rotulo, fontsize=8, fontweight="bold", ha="center", va="center")
        ax.text(x0 + 0.65, y0 - 0.16, texto, fontsize=8, color=CINZA, va="center")

    y = 9.9
    msg("Usuário", "Cliente", y, "digita \"arroz\"")
    y -= 0.55
    msg("Cliente", "Agregador", y, "connect() → SYN, SYN-ACK, ACK (porta 5050)", cor=CINZA)
    ativo(x["Agregador"], y, 1.65)
    y -= 0.55
    msg("Cliente", "Agregador", y, '{"operacao":"consultar","produto":"arroz","modo":"concorrente"}\\n', cor=AZUL)
    y -= 0.55
    msg("Agregador", "Threads de consulta", y, "cria 5 threads (uma por mercado)")
    ativo(x["Threads de consulta"], y, 4.35, cor=AZUL_CLARO)

    # bloco par
    y0 = y - 0.25
    moldura(5.9, 13.3, y0, 4.5, "par", "as 5 consultas acontecem ao mesmo tempo")
    y -= 0.85
    for alvo in ("Aurora", "Max", "Ipê"):
        msg("Threads de consulta", alvo, y, "", cor=AZUL)
    ax.text(x["Threads de consulta"] + 0.15, y + 0.06, '{"cmd":"SEARCH","q":"arroz"}\\n', fontsize=8, color=AZUL, va="bottom",
            family=["Menlo", "DejaVu Sans Mono"])
    ax.text(13.2, y0 - 0.16, "SuperVila e Empório Sol: igual, omitidos", fontsize=7.5, color=CINZA, ha="right", va="center")
    ativo(x["Aurora"], y, y - 0.9)
    ativo(x["Max"], y, y - 1.6)
    ativo(x["Ipê"], y, y - 0.5)
    msg("Aurora", "Threads de consulta", y - 0.9, '{"ok":true,"data":{"items":[…]}}', retorno=True, tam=8)
    ax.text(x["Aurora"] + 0.15, y - 0.9, "~300 ms", fontsize=8, color=CINZA, va="center")
    msg("Max", "Threads de consulta", y - 1.6, "itens", retorno=True, tam=8)
    ax.text(x["Max"] + 0.15, y - 1.6, "~900 ms", fontsize=8, color=CINZA, va="center")
    # Ipê fora do ar
    yi = y - 0.5
    ax.text(x["Ipê"], yi - 0.05, "✕ fecha sem responder", fontsize=8, color=VERMELHO, ha="center", va="top")
    yr = y - 2.2
    msg("Threads de consulta", "Ipê", yr, "nova tentativa após 0,5 s → 1 s → 2 s (4 no total)", cor=VERMELHO, tam=8)
    nota(x["Ipê"] - 0.2, yr - 0.45, "fora do ar: 4 tentativas", w=1.9, cor=VERMELHO)

    y = 4.1
    msg("Threads de consulta", "Agregador", y, "5 MarketResult (4 ok, 1 erro)", retorno=True)
    y -= 0.5
    nota(x["Agregador"], y, "agrupa por produto, ordena por preço, marca o menor", w=3.6)
    y -= 0.6
    msg("Agregador", "Cliente", y, '{"status":"parcial","resultados":[…],"tempo_total_ms":3520}', retorno=True, cor=AZUL, tam=8)
    y -= 0.55
    msg("Cliente", "Usuário", y, "tabela de preços, ★ menor preço, tempo de cada mercado", retorno=True)
    y -= 0.55
    msg("Cliente", "Agregador", y, '{"operacao":"encerrar"}\\n', cor=AZUL)
    y -= 0.45
    msg("Agregador", "Cliente", y, '{"status":"sucesso","mensagem":"conexão encerrada"} + FIN', retorno=True, cor=CINZA, tam=8)

    fig.savefig(FIGURAS / "fig-12-sequencia.png", dpi=110, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    FIGURAS.mkdir(parents=True, exist_ok=True)
    casos_de_uso()
    arquitetura()
    sequencia()
    print("ok: fig-01-casos-de-uso.png, fig-02-arquitetura.png, fig-12-sequencia.png")
