"""Desenha os diagramas de modelagem do relatório (arquitetura e sequência) com matplotlib.

Uso (da raiz do projeto):  backend/.venv/bin/python scripts/diagramas.py
Gera docs/relatorio/figuras/fig-02-arquitetura.png e fig-12-sequencia.png.
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
    caixa(ax, 0.4, 5.9, 2.7, 1.1, "Cliente de terminal", "pacotes cliente/ e experimentos/", destaque=True)
    caixa(ax, 0.4, 3.9, 2.7, 1.1, "Loja (navegador)", "busca e cesta")
    caixa(ax, 0.4, 1.0, 2.7, 1.1, "Painel (navegador)", "comparar modos, eventos")

    # agregador
    caixa(ax, 4.5, 5.9, 4.0, 1.1, "Servidor TCP · porta 5050", "uma thread por cliente conectado", destaque=True)
    caixa(ax, 4.5, 4.6, 4.0, 1.0, "Rotas HTTP · porta 8000", "FastAPI, uma thread por requisição")
    caixa(ax, 4.5, 3.3, 4.0, 1.0, "Estratégias de consulta", "sequencial: for · concorrente: 5 threads", destaque=True)
    caixa(ax, 4.5, 2.0, 4.0, 1.0, "Cliente TCP dos mercados", "conecta, envia, espera, mede, retry")
    caixa(ax, 4.5, 0.6, 4.0, 1.0, "EventBus + MetricsStore", "eventos ao vivo, histórico, CSV")

    # mercados
    mercados = [("Mercado Aurora", "5001", "300"), ("SuperVila", "5002", "500"), ("Empório Sol", "5003", "700"),
                ("Max Atacarejo", "5004", "900"), ("Mercadinho Ipê", "5005", "1200")]
    ys = [6.15, 4.95, 3.75, 2.55, 1.35]
    for (nome, porta, lat), y in zip(mercados, ys):
        caixa(ax, 9.9, y - 0.45, 3.2, 1.0, nome, f"porta {porta} · {lat} ms · SQLite próprio")

    # setas
    seta(ax, (3.1, 6.45), (4.5, 6.45), "TCP · JSON\npor linha", cor=AZUL, cor_texto=AZUL, dy=0.08)
    seta(ax, (3.1, 4.45), (4.5, 5.1), "HTTP/JSON", dx=-0.1, dy=0.05)
    seta(ax, (4.5, 1.1), (3.1, 1.55), "WebSocket", dx=0.1, dy=0.05)
    ax.plot([8.5, 8.62, 8.62], [6.45, 6.45, 3.8], color=AZUL, lw=1.4)
    seta(ax, (8.62, 3.8), (8.5, 3.8), cor=AZUL)
    seta(ax, (6.5, 4.6), (6.5, 4.3))
    seta(ax, (6.5, 3.3), (6.5, 3.0))
    seta(ax, (6.5, 2.0), (6.5, 1.6), "eventos", dx=0.45, dy=-0.05)
    for y in ys:
        seta(ax, (8.5, 2.5), (9.9, y + 0.05), cor=AZUL if y == ys[2] else LINHA)
    ax.text(9.15, 3.85, "TCP · JSON\npor linha", fontsize=9, color=AZUL, ha="center", va="bottom")

    fig.savefig(FIGURAS / "fig-02-arquitetura.png", dpi=110, bbox_inches="tight", facecolor="white")
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
    arquitetura()
    sequencia()
    print("ok:", FIGURAS / "fig-02-arquitetura.png", FIGURAS / "fig-12-sequencia.png")
