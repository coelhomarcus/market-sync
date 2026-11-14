"""Painel ao vivo no terminal do agregador: cada pesquisa vira um quadro com uma barra por mercado.

As consultas rodam em threads diferentes; cada uma chama `evento()` quando conecta,
recebe a resposta, tenta de novo ou desiste. O painel (biblioteca Rich) redesenha
as barras 12 vezes por segundo, então dá para VER a diferença entre os modos:

    sequencial                                    concorrente
    Aurora     ███                                Aurora     ███
    SuperVila     █████                           SuperVila  █████
    Empório            ███████                    Empório    ███████
    Max                       █████████           Max        █████████
    Ipê                                ████████   Ipê        ████████████
               └ escada: tempo ≈ soma ┘                      └ juntas: tempo ≈ maior ┘

Todas as barras usam a mesma escala (no mínimo 4 s), para os quadros serem comparáveis.
Quando a pesquisa termina, o quadro fica no histórico do terminal; embaixo fica uma
linha de status com os mercados e os clientes TCP conectados.

Fora de um terminal (testes, logs redirecionados) só os quadros finais são impressos.

Dois modos (iniciar.py escolhe):
    gráfico (padrão)      o painel acima, com barras
    raw (iniciar.py --raw)  uma linha por acontecimento: pedido do cliente, connect TCP
                          (com a porta local), mensagem enviada, resposta recebida, close,
                          novas tentativas e a resposta devolvida ao cliente

Silenciar (por exemplo, durante os experimentos):  SILENCIOSO=1 ou  iniciar.py --silencioso
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
from dataclasses import dataclass, field

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from comum.config import MARKETS, MARKETS_BY_ID

ATIVO = os.environ.get("SILENCIOSO", "") not in ("1", "true", "sim")
MODO = os.environ.get("PAINEL", "grafico")  # grafico | raw

MODOS = {"sequential": "sequencial", "concurrent": "concorrente"}
ORIGENS = {"cliente_tcp": "cliente TCP"}
COR_MODO = {"sequential": "dark_orange", "concurrent": "dodger_blue1"}
LARGURA_BARRA = 40  # máxima; num terminal estreito a barra encolhe (largura_barra)
COLUNAS_FIXAS = 86  # nome + situação + threads + bordas: o que sobra da largura do terminal vai para a barra
ESCALA_MIN_MS = 4000  # escala fixa mínima: quadros sequenciais e concorrentes ficam na mesma régua
MAX_QUADROS_ATIVOS = 4  # com muitos clientes ao mesmo tempo, mostra os 4 mais recentes e conta o resto


def _ms(v: float) -> str:
    return f"{v / 1000:.2f} s".replace(".", ",") if v >= 999.5 else f"{v:.0f} ms"


def _kb(n: int) -> str:
    return f"{n / 1024:.0f} KB" if n >= 10 * 1024 else f"{n / 1024:.1f} KB".replace(".", ",")


# ---------------------------------------------------------------- estado

@dataclass
class Consulta:
    """Uma linha do quadro: a consulta a UM mercado dentro de uma pesquisa."""
    mercado: str
    inicio: float | None = None  # ms desde o início da pesquisa
    fim: float | None = None
    estado: str = "fila"  # fila | esperando | tentando | ok | erro
    tentativas: int = 1
    espera_ms: int = 0
    itens: int = 0
    bytes: int = 0
    thread: str = ""
    thread_mercado: str = ""
    erro: str = ""


@dataclass
class Pesquisa:
    rid: str
    modo: str
    tipo: str
    consulta: str
    origem: str
    t0: float = field(default_factory=time.perf_counter)
    linhas: dict[str, Consulta] = field(default_factory=lambda: {m.id: Consulta(m.id) for m in MARKETS})
    total_ms: float | None = None
    ok: int = 0
    erros: int = 0
    threads: int = 0

    def agora_ms(self) -> float:
        return self.total_ms if self.total_ms is not None else (time.perf_counter() - self.t0) * 1000


def posicao_barra(inicio: float, fim: float, escala_ms: float, largura: int = LARGURA_BARRA) -> tuple[int, int]:
    """(coluna inicial, comprimento) de uma barra na régua. Toda barra iniciada tem pelo menos 1 caractere."""
    col = min(largura - 1, round(inicio / escala_ms * largura))
    comprimento = max(1, round(fim / escala_ms * largura) - col)
    return col, min(comprimento, largura - col)


def escala_de(ms: float) -> float:
    return max(ESCALA_MIN_MS, math.ceil(ms / 1000) * 1000)


def largura_barra(colunas_terminal: int) -> int:
    return max(16, min(LARGURA_BARRA, colunas_terminal - COLUNAS_FIXAS))


# ---------------------------------------------------------------- desenho

def _barra(c: Consulta, p: Pesquisa, escala: float, largura: int) -> Text:
    if c.inicio is None:
        return Text("·" * largura, style="grey30")
    fim = c.fim if c.fim is not None else p.agora_ms()
    col, comp = posicao_barra(c.inicio, fim, escala, largura)
    cor = {"erro": "red3", "tentando": "yellow3"}.get(c.estado, COR_MODO[p.modo])
    texto = Text("·" * col, style="grey30")
    texto.append("█" * comp, style=f"{cor} dim" if c.estado == "esperando" else cor)
    texto.append("·" * (largura - col - comp), style="grey30")
    return texto


def _regua(escala: float, largura: int) -> Text:
    """0 s     1 s     2 s ... embaixo das barras (o último rótulo termina na ponta da régua)."""
    chars = [" "] * largura
    for s in range(0, int(escala // 1000) + 1):
        rotulo = f"{s} s"
        col = min(round(s * 1000 / escala * largura), largura - len(rotulo))
        livre = all(ch == " " for ch in chars[max(0, col - 1):col + len(rotulo)])  # não encosta no rótulo anterior
        if livre:
            chars[col:col + len(rotulo)] = rotulo
    return Text("".join(chars), style="grey50")


def _situacao(c: Consulta, p: Pesquisa) -> Text:
    if c.estado == "fila":
        return Text("na fila", style="grey50")
    if c.estado == "esperando":
        return Text(f"esperando… {_ms(p.agora_ms() - (c.inicio or 0))}", style="grey62")
    if c.estado == "tentando":
        return Text(f"↻ fora do ar · tentativa {c.tentativas + 1} em {_ms(c.espera_ms)}", style="yellow3")
    if c.estado == "erro":
        return Text(f"✘ {c.erro} · {_ms((c.fim or 0) - (c.inicio or 0))}", style="red3")  # ex.: fora do ar (4 tentativas)
    t = Text("✔ ", style="green3")
    t.append(f"{_ms((c.fim or 0) - (c.inicio or 0)):>7}", style="bold")
    t.append(f" · {c.itens} itens · {_kb(c.bytes)}", style="grey70")
    if c.tentativas > 1:
        t.append(f" · {c.tentativas}ª tentativa", style="yellow3")
    return t


def quadro(p: Pesquisa, largura: int = LARGURA_BARRA) -> Panel:
    """O quadro de uma pesquisa: uma linha por mercado, com barra, situação e threads."""
    escala = escala_de(p.agora_ms())
    cor = COR_MODO[p.modo]
    tabela = Table.grid(padding=(0, 1))
    tabela.add_column(no_wrap=True, min_width=15)
    tabela.add_column(no_wrap=True, min_width=largura)
    tabela.add_column(no_wrap=True, min_width=30)
    tabela.add_column(no_wrap=True, style="grey50")
    for mid, c in p.linhas.items():
        info = MARKETS_BY_ID[mid]
        nome = Text(f"{info.name:<15}", style="bold" if c.estado != "fila" else "grey62")
        threads = (c.thread + (f" → {c.thread_mercado}" if c.thread_mercado else "")) if c.thread else ""
        tabela.add_row(nome, _barra(c, p, escala, largura), _situacao(c, p), threads)
    tabela.add_row(Text(""), _regua(escala, largura), Text(""), Text("agregador → mercado", style="grey30"))

    o_que = "cesta" if p.tipo == "basket" else (f'"{p.consulta}"' if p.consulta else "(catálogo inteiro)")
    titulo = Text.assemble((f" #{p.rid[:4]} ", "grey50"), (o_que, "bold"), " · ", (MODOS[p.modo], f"bold {cor}"),
                           " · ", (ORIGENS.get(p.origem, p.origem), "grey62"), " ")
    if p.total_ms is None:
        rodape = Text(f" ⏱ {_ms(p.agora_ms())} ", style=f"bold {cor}")
    else:
        total = p.ok + p.erros
        threads = "1 thread: a do próprio pedido" if p.threads == 1 else f"{p.threads} threads novas; o pedido só espera"
        rodape = Text.assemble((f" {_ms(p.total_ms)} ", f"bold {cor}"), "· ",
                               (f"{p.ok} de {total} mercados", "green3" if p.erros == 0 else "yellow3"),
                               f" · {threads} ")
    return Panel(tabela, title=titulo, title_align="left", subtitle=rodape, subtitle_align="right",
                 border_style=cor, padding=(0, 1), expand=False)


# ---------------------------------------------------------------- painel

class Painel:
    def __init__(self) -> None:
        self.console = Console(highlight=False)
        self.trava = threading.RLock()  # threads de consulta e a de desenho mexem no mesmo estado
        self.ativas: dict[str, Pesquisa] = {}
        self.mercados = {m.id: {"online": True, "latencia": m.latency_ms} for m in MARKETS}
        self.clientes = 0
        self.live: Live | None = None

    # -- ciclo de vida
    def iniciar(self) -> None:
        """Liga o desenho ao vivo (só num terminal de verdade)."""
        if ATIVO and self.console.is_terminal and self.live is None:
            self.live = Live(self, console=self.console, refresh_per_second=12, transient=True, redirect_stdout=False)
            self.live.start()

    def parar(self) -> None:
        if self.live is not None:
            self.live.stop()
            self.live = None

    # -- saída permanente (fica no histórico do terminal, acima da área ao vivo)
    def imprimir(self, coisa) -> None:
        (self.live.console if self.live else Console(highlight=False, width=150)).print(coisa)

    # -- o que o Live redesenha: quadros em andamento + linha de status
    def __rich__(self):
        with self.trava:
            ativas = list(self.ativas.values())
            largura = largura_barra(self.console.width)
            partes = [quadro(p, largura) for p in ativas[-MAX_QUADROS_ATIVOS:]]
            if len(ativas) > MAX_QUADROS_ATIVOS:
                partes.append(Text(f"  + {len(ativas) - MAX_QUADROS_ATIVOS} pesquisas em andamento", style="grey62"))
            partes.append(self._status())
        return Group(*partes)

    def _status(self) -> Text:
        t = Text(" mercados ", style="reverse")
        for mid, m in self.mercados.items():
            info = MARKETS_BY_ID[mid]
            t.append("  ● " if m["online"] else "  ○ ", style="green3" if m["online"] else "red3")
            t.append(info.short, style="" if m["online"] else "red3")
            t.append(f" {m['latencia']}ms" if m["online"] else " fora do ar", style="grey50" if m["online"] else "red3")
        t.append("   clientes TCP: ", style="grey50")
        t.append(str(self.clientes), style="bold")
        return t

    # -- eventos (chamados de qualquer thread)
    def evento(self, tipo: str, d: dict) -> None:
        with self.trava:
            p = self.ativas.get(d.get("request_id", ""))
            c = p.linhas.get(d.get("market", "")) if p else None

            if tipo == "request_start":
                self.ativas[d["request_id"]] = Pesquisa(d["request_id"], d["mode"], d.get("kind", "search"),
                                                        d.get("query", ""), d.get("source", ""))
            elif tipo == "market_connect" and c:
                c.inicio, c.estado, c.thread = d["t_ms"], "esperando", d.get("thread", "")
            elif tipo == "market_retry" and c:
                c.estado, c.tentativas, c.espera_ms = "tentando", d["attempt"], d["wait_ms"]
            elif tipo == "market_response" and c:
                c.fim, c.estado, c.itens, c.bytes = d["t_ms"], "ok", d["count"], d["bytes"]
                c.tentativas, c.thread_mercado = d.get("attempts", 1), d.get("server_thread", "")
            elif tipo == "market_error" and c:
                c.fim, c.estado, c.erro, c.tentativas = d["t_ms"], "erro", d["error"], d.get("attempts", 1)
            elif tipo == "request_end" and p:
                p.total_ms, p.ok, p.erros, p.threads = d["total_ms"], d["ok_count"], d["error_count"], d.get("threads", 1)
                del self.ativas[p.rid]
                self.imprimir(quadro(p, largura_barra(self.console.width)))  # o quadro final fica no histórico
            elif tipo == "market_config":
                self.mercados[d["market"]] = {"online": d["online"], "latencia": d["latency_ms"]}
                estado = Text("no ar", style="green3") if d["online"] else Text("FORA DO AR", style="bold red3")
                self.imprimir(Text.assemble(("⚙ ", "magenta"), (MARKETS_BY_ID[d["market"]].name, "bold"), ": ", estado,
                                            (f" · latência {d['latency_ms']} ms", "grey62")))
            elif tipo == "client_connect":
                self.clientes = d["connected"]
                self.imprimir(Text.assemble(("⇄ ", "cyan"), (f"cliente-{d['client']}", "bold"),
                                            f" conectou de {d['peer']} (porta 5050)", (f" · {d['connected']} conectado(s)", "grey62")))
            elif tipo == "client_disconnect":
                self.clientes = d["connected"]
                self.imprimir(Text.assemble(("⇠ ", "cyan"), (f"cliente-{d['client']}", "bold"), " encerrou a conexão",
                                            (f" · {d['connected']} conectado(s)", "grey62")))
            elif tipo == "client_drop":
                self.imprimir(Text.assemble(("⇠ ", "red3"), (f"cliente-{d['client']}", "bold"), f" caiu: {d['error']}"))


# ---------------------------------------------------------------- modo raw: uma linha por acontecimento

COR_THREAD = ["", "dodger_blue1", "green3", "dark_orange", "magenta", "turquoise2"]  # thread_1 … thread_5


def resumo_json(obj, limite: int = 110) -> str:
    """O JSON como trafegou, encurtado: listas grandes mostram o 1º item e quantos faltam."""
    def encurtar(x):
        if isinstance(x, dict):
            return {k: encurtar(v) for k, v in x.items()}
        if isinstance(x, list) and len(x) > 1:
            return [encurtar(x[0]), f"… +{len(x) - 1}"]
        return x
    texto = json.dumps(encurtar(obj), ensure_ascii=False, separators=(",", ":"))
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def _bytes(n: int) -> str:
    return f"{n} B" if n < 1024 else _kb(n)


class Cru:
    """Modo raw: escreve cada passo de cada chamada, com horário em milissegundos."""

    def __init__(self) -> None:
        self.trava = threading.Lock()
        self.inicio_pesquisa: dict[str, float] = {}

    def iniciar(self) -> None:
        self._linha(Text("modo raw: cada chamada aparece linha a linha (os mercados escrevem com [nome])", style="grey50"))

    def parar(self) -> None:
        pass

    def _linha(self, texto: Text) -> None:
        hora = time.strftime("%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}"
        linha = Text(hora + "  ", style="grey42")
        linha.append_text(texto)
        console = Console(highlight=False)
        if not console.is_terminal:  # saída redirecionada (arquivo, testes): não corta em 80 colunas
            console = Console(highlight=False, width=220)
        console.print(linha, no_wrap=True, overflow="ellipsis")

    def _prefixo(self, d: dict) -> Text:
        thread = d.get("thread", "")
        numero = int(thread.split("_")[1]) if thread.startswith("thread_") and thread.split("_")[1].isdigit() else 0
        cor = COR_THREAD[numero] if 0 < numero < len(COR_THREAD) else "white"
        t = Text(f"#{d.get('request_id', '????')[:4]} ", style="grey50")
        t.append(f"+{d.get('t_ms', 0):>5.0f} ms ", style="grey50")
        t.append(f"{thread:<9}", style=f"bold {cor}")
        return t

    def evento(self, tipo: str, d: dict) -> None:
        with self.trava:
            nome = MARKETS_BY_ID[d["market"]].short if d.get("market") in MARKETS_BY_ID else ""
            if tipo == "client_request":
                self._linha(Text.assemble((f"⇢ cliente-{d['client']} → agregador  ", "cyan"), (resumo_json(d["message"]), "bold"),
                                          (f"  {_bytes(d['bytes'])}", "grey50")))
            elif tipo == "client_reply":
                self._linha(Text.assemble((f"⇠ agregador → cliente-{d['client']}  ", "cyan"), resumo_json(d["message"]),
                                          (f"  {_bytes(d['bytes'])}", "grey50")))
            elif tipo == "request_start":
                o_que = "cesta" if d.get("kind") == "basket" else f'"{d.get("query", "")}"'
                print()
                self._linha(Text.assemble(("▶ ", "bold"), (f"#{d['request_id'][:4]} ", "grey50"), (o_que, "bold"), " · ",
                                          (MODOS[d["mode"]], f"bold {COR_MODO[d['mode']]}"), " · ",
                                          (ORIGENS.get(d.get("source"), d.get("source", "")), "grey62")))
            elif tipo == "tcp_connect":
                tentativa = f" (tentativa {d['attempt']})" if d.get("attempt", 1) > 1 else ""
                t = self._prefixo(d)
                t.append_text(Text.assemble(("connect  ", "yellow3"), f"→ {nome:<11} :{d['port']}  ",
                                            (f"ok em {d['connect_ms']:.1f} ms · porta local {d['local_port']}{tentativa}".replace(".", ","), "grey62")))
                self._linha(t)
            elif tipo == "tcp_send":
                t = self._prefixo(d)
                t.append_text(Text.assemble(("envia    ", "yellow3"), f"→ {nome:<11} ", (resumo_json(d["message"]), "bold"),
                                            (f"  {_bytes(d['bytes'])}", "grey50")))
                self._linha(t)
            elif tipo == "tcp_recv":
                t = self._prefixo(d)
                if d["message"] is None:
                    t.append_text(Text.assemble(("recebe   ", "yellow3"), f"← {nome:<11} ",
                                                ("nada: o mercado fechou a conexão sem responder", "red3")))
                else:
                    t.append_text(Text.assemble(("recebe   ", "yellow3"), f"← {nome:<11} ", resumo_json(d["message"], 90),
                                                (f"  {_bytes(d['bytes'])} · esperou {_ms(d['wait_ms'])}", "grey50")))
                self._linha(t)
            elif tipo == "tcp_close":
                t = self._prefixo(d)
                t.append_text(Text.assemble(("close    ", "yellow3"), (f"✕ {nome}", "grey62")))
                self._linha(t)
            elif tipo == "market_retry":
                t = self._prefixo(d)
                t.append_text(Text.assemble(("↻ ", "yellow3"), f"{nome}: {d.get('reason', 'fora do ar')}; ",
                                            (f"nova tentativa em {_ms(d['wait_ms'])}", "yellow3")))
                self._linha(t)
            elif tipo == "market_error":
                t = self._prefixo(d)
                t.append_text(Text.assemble(("✘ ", "red3"), f"{nome}: ", (d["error"], "red3")))
                self._linha(t)
            elif tipo == "request_end":
                total = d["ok_count"] + d["error_count"]
                threads = "1 thread: a do próprio pedido" if d.get("threads", 1) == 1 else f"{d['threads']} threads novas"
                self._linha(Text.assemble(("■ ", "bold"), (f"#{d['request_id'][:4]} ", "grey50"),
                                          (_ms(d["total_ms"]), f"bold {COR_MODO[d['mode']]}"),
                                          f" · {d['ok_count']} de {total} mercados · {threads}"))
            elif tipo == "market_config":
                estado = "no ar" if d["online"] else "FORA DO AR"
                self._linha(Text.assemble(("⚙ ", "magenta"), f"{MARKETS_BY_ID[d['market']].name}: {estado} · latência {d['latency_ms']} ms"))
            elif tipo == "client_connect":
                self._linha(Text.assemble(("⇄ ", "cyan"), f"cliente-{d['client']} conectou de {d['peer']} · {d['connected']} conectado(s)"))
            elif tipo == "client_disconnect":
                self._linha(Text.assemble(("⇠ ", "cyan"), f"cliente-{d['client']} encerrou a conexão · {d['connected']} conectado(s)"))
            elif tipo == "client_drop":
                self._linha(Text.assemble(("⇠ ", "red3"), f"cliente-{d['client']} caiu: {d['error']}"))


_painel = Cru() if MODO == "raw" else Painel()


def iniciar() -> None:
    """Chamado quando o agregador sobe (servidor_tcp.py)."""
    _painel.iniciar()


def parar() -> None:
    _painel.parar()


def evento(tipo: str, dados: dict) -> None:
    """Recebe um evento de qualquer thread e atualiza o painel."""
    if ATIVO:
        _painel.evento(tipo, dados)
