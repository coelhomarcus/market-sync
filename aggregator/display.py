"""Painel ao vivo do agregador no terminal: um quadro por pesquisa, uma barra por mercado.

Modos: gráfico (padrão) ou raw (start.py --raw, uma linha por evento). Silenciar: start.py --quiet."""

from __future__ import annotations

import json
import math
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from common.config import MARKETS, MARKETS_BY_ID

ENABLED = os.environ.get("QUIET", "") not in ("1", "true", "sim")
DISPLAY_MODE = os.environ.get("DISPLAY", "graphic")  # graphic | raw

MODE_LABELS = {"sequential": "sequencial", "concurrent": "concorrente"}
SOURCES = {"cliente_tcp": "cliente TCP"}
MODE_COLOR = {"sequential": "dark_orange", "concurrent": "dodger_blue1"}
BAR_WIDTH = 40  # máxima; num terminal estreito a barra encolhe (bar_width)
FIXED_COLUMNS = 86  # nome + situação + threads + bordas: o que sobra da largura do terminal vai para a barra
MIN_SCALE_MS = 4000  # escala fixa mínima: quadros sequenciais e concorrentes ficam na mesma régua


def _ms(v: float) -> str:
    return f"{v / 1000:.2f} s".replace(".", ",") if v >= 999.5 else f"{v:.0f} ms"


def _kb(n: int) -> str:
    return f"{n / 1024:.0f} KB" if n >= 10 * 1024 else f"{n / 1024:.1f} KB".replace(".", ",")


# ---------------------------------------------------------------- estado

@dataclass
class CallState:
    """Uma linha do quadro: a consulta a UM mercado dentro de uma pesquisa."""
    market: str
    start: float | None = None  # ms desde o início da pesquisa
    end: float | None = None
    state: str = "fila"  # fila | esperando | tentando | ok | erro
    attempts: int = 1
    wait_ms: int = 0
    items: int = 0
    bytes: int = 0
    thread: str = ""
    market_thread: str = ""
    error: str = ""


@dataclass
class SearchState:
    rid: str
    mode: str
    query: str
    source: str
    t0: float = field(default_factory=time.perf_counter)
    rows: dict[str, CallState] = field(default_factory=lambda: {m.id: CallState(m.id) for m in MARKETS})
    total_ms: float | None = None
    ok: int = 0
    errors: int = 0
    threads: int = 0

    def now_ms(self) -> float:
        return self.total_ms if self.total_ms is not None else (time.perf_counter() - self.t0) * 1000


def bar_position(start: float, end: float, scale_ms: float, width: int = BAR_WIDTH) -> tuple[int, int]:
    """(coluna inicial, comprimento) de uma barra na régua. Toda barra iniciada tem pelo menos 1 caractere."""
    col = min(width - 1, round(start / scale_ms * width))
    length = max(1, round(end / scale_ms * width) - col)
    return col, min(length, width - col)


def scale_for(ms: float) -> float:
    return max(MIN_SCALE_MS, math.ceil(ms / 1000) * 1000)


def bar_width(terminal_columns: int) -> int:
    return max(16, min(BAR_WIDTH, terminal_columns - FIXED_COLUMNS))


# ---------------------------------------------------------------- desenho

def _bar(c: CallState, p: SearchState, scale: float, width: int) -> Text:
    if c.start is None:
        return Text("·" * width, style="grey30")
    end = c.end if c.end is not None else p.now_ms()
    col, comp = bar_position(c.start, end, scale, width)
    color = {"erro": "red3", "tentando": "yellow3"}.get(c.state, MODE_COLOR[p.mode])
    text = Text("·" * col, style="grey30")
    text.append("█" * comp, style=f"{color} dim" if c.state == "esperando" else color)
    text.append("·" * (width - col - comp), style="grey30")
    return text


def _ruler(scale: float, width: int) -> Text:
    """0 s     1 s     2 s ... embaixo das barras (o último rótulo termina na ponta da régua)."""
    chars = [" "] * width
    for s in range(0, int(scale // 1000) + 1):
        label = f"{s} s"
        col = min(round(s * 1000 / scale * width), width - len(label))
        free = all(ch == " " for ch in chars[max(0, col - 1):col + len(label)])  # não encosta no rótulo anterior
        if free:
            chars[col:col + len(label)] = label
    return Text("".join(chars), style="grey50")


def _call_status(c: CallState, p: SearchState) -> Text:
    if c.state == "fila":
        return Text("na fila", style="grey50")
    if c.state == "esperando":
        return Text(f"esperando… {_ms(p.now_ms() - (c.start or 0))}", style="grey62")
    if c.state == "tentando":
        return Text(f"↻ fora do ar · tentativa {c.attempts + 1} em {_ms(c.wait_ms)}", style="yellow3")
    if c.state == "erro":
        return Text(f"✘ {c.error} · {_ms((c.end or 0) - (c.start or 0))}", style="red3")  # ex.: fora do ar (4 tentativas)
    t = Text("✔ ", style="green3")
    t.append(f"{_ms((c.end or 0) - (c.start or 0)):>7}", style="bold")
    t.append(f" · {c.items} itens · {_kb(c.bytes)}", style="grey70")
    if c.attempts > 1:
        t.append(f" · {c.attempts}ª tentativa", style="yellow3")
    return t


def search_panel(p: SearchState, width: int = BAR_WIDTH) -> Panel:
    """O quadro de uma pesquisa: uma linha por mercado, com barra, situação e threads."""
    scale = scale_for(p.now_ms())
    color = MODE_COLOR[p.mode]
    table = Table.grid(padding=(0, 1))
    table.add_column(no_wrap=True, min_width=15)
    table.add_column(no_wrap=True, min_width=width)
    table.add_column(no_wrap=True, min_width=30)
    table.add_column(no_wrap=True, style="grey50")
    for mid, c in p.rows.items():
        info = MARKETS_BY_ID[mid]
        name = Text(f"{info.name:<15}", style="bold" if c.state != "fila" else "grey62")
        threads = (c.thread + (f" → {c.market_thread}" if c.market_thread else "")) if c.thread else ""
        table.add_row(name, _bar(c, p, scale, width), _call_status(c, p), threads)
    table.add_row(Text(""), _ruler(scale, width), Text(""), Text("agregador → mercado", style="grey30"))

    what = f'"{p.query}"' if p.query else "(catálogo inteiro)"
    title = Text.assemble((f" #{p.rid[:4]} ", "grey50"), (what, "bold"), " · ", (MODE_LABELS[p.mode], f"bold {color}"),
                           " · ", (SOURCES.get(p.source, p.source), "grey62"), " ")
    if p.total_ms is None:
        footer = Text(f" ⏱ {_ms(p.now_ms())} ", style=f"bold {color}")
    else:
        total = p.ok + p.errors
        threads = "1 thread: a do próprio pedido" if p.threads == 1 else f"{p.threads} threads novas; o pedido só espera"
        footer = Text.assemble((f" {_ms(p.total_ms)} ", f"bold {color}"), "· ",
                               (f"{p.ok} de {total} mercados", "green3" if p.errors == 0 else "yellow3"),
                               f" · {threads} ")
    return Panel(table, title=title, title_align="left", subtitle=footer, subtitle_align="right",
                 border_style=color, padding=(0, 1), expand=False)


# ---------------------------------------------------------------- painel

class GraphicDisplay:
    """Modo gráfico: histórico rolável + barra ao vivo embaixo.

    Tudo o que já terminou (pesquisas de todos os clientes e avisos) vai para o histórico
    normal do terminal, em ordem de chegada: a mais recente embaixo, e dá para rolar com o
    mouse/trackpad até a primeira. Embaixo de tudo fica a parte ao vivo: o cabeçalho, os
    mercados e as pesquisas em andamento, redesenhadas 12 vezes por segundo.

    Ao redimensionar a janela o terminal re-quebra as linhas antigas e o desenho ao vivo
    deixaria cópias para trás; por isso, quando o tamanho muda, a tela e o histórico são
    limpos e tudo é redesenhado na largura nova.
    Fora de um terminal (testes, saída redirecionada) cada quadro final é só impresso.
    """

    LOG_LIMIT = 1000  # quantos itens do histórico são redesenhados depois de um redimensionamento
    RESIZE_SETTLE_S = 0.25  # espera a janela parar de mudar de tamanho antes de redesenhar

    def __init__(self) -> None:
        self.console = Console(highlight=False)
        self.lock = threading.RLock()  # threads de consulta e a de desenho mexem no mesmo estado
        self.active: dict[str, SearchState] = {}
        self.log: deque[Text | SearchState] = deque(maxlen=self.LOG_LIMIT)  # avisos e pesquisas terminadas
        self.markets = {m.id: {"online": True, "latencia": m.latency_ms} for m in MARKETS}
        self.clients = 0
        self.served = 0
        self.closing = False
        self.live: Live | None = None
        self._running = False
        self._size = None

    # -- ciclo de vida
    def start(self) -> None:
        """Liga a parte ao vivo (só num terminal de verdade)."""
        if ENABLED and self.console.is_terminal and self.live is None:
            # auto_refresh=False: quem redesenha é a thread abaixo, sempre com self.lock,
            # para nenhum print do histórico se misturar com um quadro pela metade
            self.live = Live(self, console=self.console, auto_refresh=False, transient=True,
                             redirect_stdout=False, redirect_stderr=False)
            self._size = self.console.size
            self._running = True
            self.live.start()
            threading.Thread(target=self._refresh_loop, name="painel", daemon=True).start()

    def stop(self) -> None:
        if self.live is not None:
            self._running = False
            with self.lock:
                self.live.stop()  # apaga a parte ao vivo; o histórico fica no terminal
                self.live = None
            Console(highlight=False).print(f"  Agregador: {self.served} pesquisa(s) atendida(s).", style="grey62")

    def shutting_down(self) -> None:
        with self.lock:
            self.closing = True

    def _refresh_loop(self) -> None:
        changed_at = None
        while self._running:
            time.sleep(1 / 12)
            size = self.console.size
            if size != self._size:  # a janela está mudando de tamanho: espera parar
                self._size, changed_at = size, time.monotonic()
                continue
            with self.lock:
                if self.live is None:
                    return
                if changed_at is not None:
                    if time.monotonic() - changed_at < self.RESIZE_SETTLE_S:
                        continue
                    changed_at = None
                    self._redraw_everything()
                else:
                    self.live.refresh()

    def _redraw_everything(self) -> None:
        """Limpa a tela e o histórico do terminal e reimprime tudo na largura nova."""
        self.console.file.write("\x1b[H\x1b[2J\x1b[3J")  # cursor no topo · limpa a tela · limpa o histórico
        self.console.file.flush()
        self.live._live_render._shape = None  # a parte ao vivo some junto: não há o que apagar antes de desenhar
        if self.log:
            self.console.print(Group(*(self._render_log_item(item) for item in self.log)))
        else:
            self.live.refresh()

    def _render_log_item(self, item: Text | SearchState):
        return search_panel(item, bar_width(self.console.width)) if isinstance(item, SearchState) else item

    def _to_history(self, item: Text | SearchState) -> None:
        """Manda um aviso ou uma pesquisa terminada para o histórico (acima da parte ao vivo)."""
        if self.live:
            self.log.append(item)
            self.console.print(self._render_log_item(item))  # o Rich imprime acima e redesenha a parte ao vivo
        else:
            Console(highlight=False, width=150).print(search_panel(item, BAR_WIDTH) if isinstance(item, SearchState)
                                                      else item)

    def _notice(self, text: Text) -> None:
        line = Text(time.strftime("%H:%M:%S  "), style="grey42")
        line.append_text(text)
        self._to_history(line)

    # -- a parte ao vivo, embaixo de tudo
    def __rich__(self):
        with self.lock:
            width = bar_width(self.console.width)
            parts = [search_panel(p, width) for p in self.active.values()]
            if not parts and not self.log:
                parts.append(Text("  aguardando pesquisas…  (em outro terminal: ./client.py)",
                                  style="grey50", no_wrap=True, overflow="ellipsis"))
            parts += [self._header(self.console.width - 1), self._status(self.console.width - 1)]
        return Group(*parts)

    def _header(self, max_width: int) -> Text:
        """Título + porta + contadores (+ o aviso de encerramento depois do Ctrl+C).

        Num terminal estreito o título encurta para "Comparador"; o que ainda não couber é cortado com …"""
        def plural(n: int, word: str) -> str:
            return f"{n} {word}" if n == 1 else f"{n} {word}s"

        for title in (" Comparador de Preços ", " Comparador "):
            line = Text(title, style="bold reverse", no_wrap=True, overflow="ellipsis")
            line.append(f"  :5050 · {plural(self.clients, 'cliente')} · {plural(self.served, 'pesquisa')}", style="grey62")
            if self.active:
                line.append(f" · {len(self.active)} em andamento", style="grey62")
            if self.closing:
                line.append(f"  encerrando: aguardando {len(self.active)} pesquisa(s)", style="bold yellow3")
            if line.cell_len <= max_width:
                break
        return line

    def _status(self, max_width: int) -> Text:
        """Uma linha com os mercados, no nível de detalhe que couber na largura:
            ● Aurora 300  ● SuperVila 500  …  ● Ipê 1200 ms     (nome + latência)
            ● Aurora  ● SuperVila  …  ● Ipê                      (só o nome)
            ● A  ● S  ● E  ● M  ● I                              (só a inicial)
        """
        def build(detail: str) -> Text:
            t = Text(no_wrap=True, overflow="ellipsis")
            for i, (mid, m) in enumerate(self.markets.items()):
                info = MARKETS_BY_ID[mid]
                online = m["online"]
                name = info.short if detail != "initial" else info.short[0]
                t.append(" " if i == 0 else "  ")
                t.append("● " if online else "○ ", style="green3" if online else "red3")
                t.append(name, style="" if online else "red3")
                if detail == "full":
                    t.append(f" {m['latencia']}" if online else " fora", style="grey50" if online else "red3")
            if detail == "full":
                t.append(" ms", style="grey42")
            return t

        for detail in ("full", "name"):
            line = build(detail)
            if line.cell_len <= max_width:
                return line
        return build("initial")

    # -- eventos (chamados de qualquer thread)
    def event(self, kind: str, d: dict) -> None:
        with self.lock:
            p = self.active.get(d.get("request_id", ""))
            c = p.rows.get(d.get("market", "")) if p else None

            if kind == "request_start":
                self.active[d["request_id"]] = SearchState(d["request_id"], d["mode"],
                                                        d.get("query", ""), d.get("source", ""))
            elif kind == "market_connect" and c:
                c.start, c.state, c.thread = d["t_ms"], "esperando", d.get("thread", "")
            elif kind == "market_retry" and c:
                c.state, c.attempts, c.wait_ms = "tentando", d["attempt"], d["wait_ms"]
            elif kind == "market_response" and c:
                c.end, c.state, c.items, c.bytes = d["t_ms"], "ok", d["count"], d["bytes"]
                c.attempts, c.market_thread = d.get("attempts", 1), d.get("server_thread", "")
            elif kind == "market_error" and c:
                c.end, c.state, c.error, c.attempts = d["t_ms"], "erro", d["error"], d.get("attempts", 1)
            elif kind == "request_end" and p:
                p.total_ms, p.ok, p.errors, p.threads = d["total_ms"], d["ok_count"], d["error_count"], d.get("threads", 1)
                del self.active[p.rid]
                self.served += 1
                self._to_history(p)
            elif kind == "market_config":
                self.markets[d["market"]] = {"online": d["online"], "latencia": d["latency_ms"]}
                state = Text("no ar", style="green3") if d["online"] else Text("FORA DO AR", style="bold red3")
                self._notice(Text.assemble(("⚙ ", "magenta"), (MARKETS_BY_ID[d["market"]].name, "bold"), ": ", state,
                                          (f" · latência {d['latency_ms']} ms", "grey62")))
            elif kind == "client_connect":
                self.clients = d["connected"]
                self._notice(Text.assemble(("⇄ ", "cyan"), (f"cliente-{d['client']}", "bold"),
                                          f" conectou de {d['peer']}", (f" · {d['connected']} conectado(s)", "grey62")))
            elif kind == "client_disconnect":
                self.clients = d["connected"]
                self._notice(Text.assemble(("⇠ ", "cyan"), (f"cliente-{d['client']}", "bold"), " encerrou a conexão",
                                          (f" · {d['connected']} conectado(s)", "grey62")))
            elif kind == "client_drop":
                self._notice(Text.assemble(("⇠ ", "red3"), (f"cliente-{d['client']}", "bold"), f" caiu: {d['error']}"))


# ---------------------------------------------------------------- modo raw: uma linha por acontecimento

THREAD_COLOR = ["", "dodger_blue1", "green3", "dark_orange", "magenta", "turquoise2"]  # thread_1 … thread_5


def summarize_json(obj, limit: int = 110) -> str:
    """O JSON como trafegou, encurtado: listas grandes mostram o 1º item e quantos faltam."""
    def shorten(x):
        if isinstance(x, dict):
            return {k: shorten(v) for k, v in x.items()}
        if isinstance(x, list) and len(x) > 1:
            return [shorten(x[0]), f"… +{len(x) - 1}"]
        return x
    text = json.dumps(shorten(obj), ensure_ascii=False, separators=(",", ":"))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _bytes(n: int) -> str:
    return f"{n} B" if n < 1024 else _kb(n)


class RawDisplay:
    """Modo raw: cada passo de cada chamada numa linha, em colunas fixas.

        hora          pesquisa  tempo    thread    ação     mercado      detalhe
        12:07:59.105  #e5cf  +   0 ms  thread_1  CONNECT  → Aurora      :5001 · porta local 58957 · 0,1 ms
        12:07:59.105  #e5cf  +   0 ms  thread_1  ENVIA    → Aurora      {"cmd":"SEARCH","q":"arroz"} · 41 B
        12:07:59.105           ┃ Aurora      conexão nº 2   ← recebeu SEARCH "arroz"  de :58957   (lado do servidor)
        12:07:59.408  #e5cf  + 303 ms  thread_1  RECEBE   ← Aurora      {"ok":true,...} · 2,0 KB · esperou 302 ms
        12:07:59.409  #e5cf  + 305 ms  thread_1  CLOSE    ✕ Aurora

    As linhas com ┃ são escritas pelos processos dos supermercados no mesmo terminal.
    """

    ACTIONS = {"CONNECT": "yellow3", "ENVIA": "yellow3", "RECEBE": "yellow3", "CLOSE": "grey50",
             "RETRY": "dark_orange", "ERRO": "red3"}

    def __init__(self) -> None:
        self.lock = threading.Lock()

    def start(self) -> None:
        self._print(Text("modo raw: cada chamada linha a linha · as linhas com ┃ são dos supermercados (lado do servidor)",
                            style="grey50"))

    def stop(self) -> None:
        pass

    def _console(self) -> Console:
        console = Console(highlight=False)
        return console if console.is_terminal else Console(highlight=False, width=220)  # redirecionado: não corta

    def _print(self, renderable) -> None:
        self._console().print(renderable, no_wrap=True, overflow="ellipsis")

    def _line(self, text: Text) -> None:
        clock = time.strftime("%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}"
        line = Text(clock + "  ", style="grey42", no_wrap=True, overflow="ellipsis")
        line.append_text(text)
        self._print(line)

    def _call(self, d: dict, action: str, arrow: str, detail: Text) -> None:
        """Uma linha de chamada do agregador a um supermercado, em colunas."""
        thread = d.get("thread", "")
        number = thread.split("_")[1] if thread.startswith("thread_") else ""
        color = THREAD_COLOR[int(number)] if number.isdigit() and int(number) < len(THREAD_COLOR) else "white"
        name = MARKETS_BY_ID[d["market"]].short if d.get("market") in MARKETS_BY_ID else ""
        t = Text.assemble((f"#{d.get('request_id', '????')[:4]}  ", "grey50"), (f"+{d.get('t_ms', 0):>5.0f} ms  ", "grey50"),
                          (f"{thread:<9} ", f"bold {color}"), (f"{action:<8} ", self.ACTIONS.get(action, "")),
                          (f"{arrow} {name:<11} ", "bold"))
        t.append_text(detail)
        self._line(t)

    def event(self, kind: str, d: dict) -> None:
        with self.lock:
            if kind == "client_request":
                self._line(Text.assemble((f"⇢ cliente-{d['client']} → agregador   ", "cyan"), (summarize_json(d["message"]), "bold"),
                                          (f" · {_bytes(d['bytes'])}", "grey50")))
            elif kind == "client_reply":
                self._line(Text.assemble((f"⇠ agregador → cliente-{d['client']}   ", "cyan"), summarize_json(d["message"]),
                                          (f" · {_bytes(d['bytes'])}", "grey50")))
            elif kind == "request_start":
                what = f'"{d.get("query", "")}"'
                color = MODE_COLOR[d["mode"]]
                title = Text.assemble(" ▶ ", (f"#{d['request_id'][:4]} ", "grey62"), (what, "bold"), " · ",
                                       (MODE_LABELS[d["mode"]], f"bold {color}"), " · ", (SOURCES.get(d.get("source"), ""), "grey62"), " ")
                self._print(Rule(title, style=color, align="left"))
            elif kind == "tcp_connect":
                attempt = f" · tentativa {d['attempt']}" if d.get("attempt", 1) > 1 else ""
                self._call(d, "CONNECT", "→", Text(f":{d['port']} · porta local {d['local_port']} · "
                                                      f"{d['connect_ms']:.1f} ms{attempt}".replace(".", ","), style="grey62"))
            elif kind == "tcp_send":
                self._call(d, "ENVIA", "→", Text.assemble((summarize_json(d["message"]), "bold"),
                                                             (f" · {_bytes(d['bytes'])}", "grey50")))
            elif kind == "tcp_recv":
                if d["message"] is None:
                    self._call(d, "RECEBE", "←", Text("nada: o mercado fechou a conexão sem responder", style="red3"))
                else:
                    self._call(d, "RECEBE", "←", Text.assemble(summarize_json(d["message"], 90),
                                                                  (f" · {_bytes(d['bytes'])} · esperou {_ms(d['wait_ms'])}", "grey50")))
            elif kind == "tcp_close":
                self._call(d, "CLOSE", "✕", Text(""))
            elif kind == "market_retry":
                self._call(d, "RETRY", "↻", Text(f"{d.get('reason', 'fora do ar')}: nova tentativa em {_ms(d['wait_ms'])}",
                                                    style="dark_orange"))
            elif kind == "market_error":
                self._call(d, "ERRO", "✘", Text(d["error"], style="red3"))
            elif kind == "request_end":
                total = d["ok_count"] + d["error_count"]
                threads = "1 thread: a do próprio pedido" if d.get("threads", 1) == 1 else f"{d['threads']} threads novas"
                color = MODE_COLOR[d["mode"]]
                end = Text.assemble(" ■ ", (f"#{d['request_id'][:4]} ", "grey62"), (_ms(d["total_ms"]), f"bold {color}"),
                                    f" · {d['ok_count']} de {total} mercados · {threads} ")
                self._print(Rule(end, style=color, align="left"))
            elif kind == "market_config":
                state = "no ar" if d["online"] else "FORA DO AR"
                self._line(Text.assemble(("⚙ ", "magenta"), f"{MARKETS_BY_ID[d['market']].name}: {state} · latência {d['latency_ms']} ms"))
            elif kind == "client_connect":
                self._line(Text.assemble(("⇄ ", "cyan"), f"cliente-{d['client']} conectou de {d['peer']} · {d['connected']} conectado(s)"))
            elif kind == "client_disconnect":
                self._line(Text.assemble(("⇠ ", "cyan"), f"cliente-{d['client']} encerrou a conexão · {d['connected']} conectado(s)"))
            elif kind == "client_drop":
                self._line(Text.assemble(("⇠ ", "red3"), f"cliente-{d['client']} caiu: {d['error']}"))


_display = RawDisplay() if DISPLAY_MODE == "raw" else GraphicDisplay()


def start() -> None:
    """Chamado quando o agregador sobe (tcp_server.py)."""
    _display.start()


def stop() -> None:
    _display.stop()


def shutting_down() -> None:
    """Ctrl+C recebido: o painel avisa que está esperando as pesquisas em andamento."""
    if hasattr(_display, "shutting_down"):
        _display.shutting_down()


def event(kind: str, data: dict) -> None:
    """Recebe um evento de qualquer thread e atualiza o painel."""
    if ENABLED:
        _display.event(kind, data)
