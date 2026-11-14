"""Servidor TCP de um supermercado (um processo por mercado).

Usa o `socketserver` da biblioteca padrão, que cuida do ciclo
socket() → bind() → listen() → accept():

  * MarketServer (ThreadingTCPServer) aceita as conexões e cria UMA THREAD POR CONEXÃO;
  * MarketHandler.handle() roda dentro dessa thread: lê a pergunta, responde e fecha.

Comandos (uma linha JSON cada, ver comum/protocolo.py):
    SEARCH  {"q": "arroz"}                         produtos que casam com a busca
    BASKET  {"items": [{"slug": "...", "qty": 2}]} preço da cesta neste mercado
    STATUS                                         situação do mercado (responde mesmo fora do ar)
    CONFIG  {"latency_ms": 800, "online": false}   muda a simulação (usado pelo painel)

Uso:  python -m mercados.servidor --id aurora
"""

from __future__ import annotations

import argparse
import logging
import random
import socketserver
import threading
import time
from pathlib import Path

from comum import protocolo
from comum.config import MARKET_HOST, MARKETS_BY_ID, MarketInfo
from mercados.banco import MarketDatabase
from mercados.gerar_bancos import is_ready, seed_market

log = logging.getLogger("market")

ADMIN_COMMANDS = {"STATUS", "CONFIG"}  # continuam respondendo com o mercado "fora do ar"


class WentDown(Exception):
    """O mercado saiu do ar enquanto uma consulta esperava: a conexão cai sem resposta."""


class Market:
    """O mercado em si: o banco de dados mais a simulação de lentidão e de queda."""

    def __init__(self, info: MarketInfo, db_path: Path | None = None, latency_ms: int | None = None, jitter: float = 0.15):
        self.info = info
        self.db = MarketDatabase(db_path or info.db_path)
        if not is_ready(self.db.path):
            seed_market(info, self.db.path)
        self.products = self.db.count()
        self.latency_ms = info.latency_ms if latency_ms is None else latency_ms
        self.jitter = jitter  # variação aleatória da latência (±15%)
        self.online = True
        self.down = threading.Event()  # sinalizado quando o mercado sai do ar: acorda quem está esperando
        self.requests_served = 0
        self.lock = threading.Lock()  # várias threads de conexão mexem nos campos acima

    def handle(self, cmd: str, request: dict) -> dict:
        if cmd == "STATUS":
            return self.status()
        if cmd == "CONFIG":
            return self.configure(request)
        if cmd == "SEARCH":
            self.simulate_latency()
            return {"items": self.db.search(str(request.get("q", "")))}
        if cmd == "BASKET":
            self.simulate_latency()
            return self.db.basket(request.get("items") or [])
        raise ValueError(f"comando desconhecido: {cmd!r}")

    def simulate_latency(self) -> None:
        """Finge que o mercado está longe/lento: espera a latência configurada.

        A espera é num Event, não num sleep: se o mercado sair do ar no meio dela,
        a consulta em andamento também cai (como um servidor que trava de verdade).
        """
        with self.lock:
            self.requests_served += 1
            latency = self.latency_ms
        if self.down.wait(latency * random.uniform(1 - self.jitter, 1 + self.jitter) / 1000):
            raise WentDown

    def status(self) -> dict:
        with self.lock:
            return {
                "online": self.online,
                "latency_ms": self.latency_ms,
                "products": self.products,
                "db_bytes": self.db.path.stat().st_size,
                "requests_served": self.requests_served,
                "thread_count": threading.active_count(),
            }

    def configure(self, request: dict) -> dict:
        with self.lock:
            if "latency_ms" in request:
                self.latency_ms = max(0, min(10_000, int(request["latency_ms"])))
            if "online" in request:
                self.online = bool(request["online"])
                if self.online:
                    self.down.clear()
                else:
                    self.down.set()
        return self.status()


class MarketHandler(socketserver.StreamRequestHandler):
    """Atende UMA conexão do agregador, numa thread própria: lê uma pergunta e responde."""

    def handle(self) -> None:
        market: Market = self.server.market  # type: ignore[attr-defined]
        try:
            request, _ = protocolo.receive(self.rfile)
        except protocolo.ProtocolError as exc:
            log.warning("mensagem inválida de %s: %s", self.client_address, exc)
            return
        if request is None:  # o agregador fechou sem perguntar nada
            return

        cmd = str(request.get("cmd", "")).upper()
        if not market.online and cmd not in ADMIN_COMMANDS:
            return  # "fora do ar": fecha a conexão sem responder

        cpu_start = time.thread_time()  # CPU só desta thread (o sleep da latência não conta)
        try:
            response = {"ok": True, "data": market.handle(cmd, request)}
        except WentDown:
            return  # caiu durante a consulta: fecha a conexão sem responder
        except Exception as exc:  # erro na pergunta vira resposta de erro, o servidor segue de pé
            response = {"ok": False, "error": str(exc)}
        response["cpu_ms"] = round((time.thread_time() - cpu_start) * 1000, 3)
        protocolo.send(self.wfile, response)


class MarketServer(socketserver.ThreadingTCPServer):
    daemon_threads = True  # as threads de conexão não seguram o processo ao encerrar
    allow_reuse_address = True
    request_queue_size = 64  # tamanho da fila do listen()

    def __init__(self, market: Market, host: str = MARKET_HOST, port: int | None = None) -> None:
        self.market = market
        super().__init__((host, market.info.port if port is None else port), MarketHandler)

    @property
    def port(self) -> int:
        return self.server_address[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor TCP de um supermercado")
    parser.add_argument("--id", required=True, choices=sorted(MARKETS_BY_ID))
    parser.add_argument("--latency", type=int, help="latência simulada em ms")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format=f"[{args.id}] %(message)s")
    market = Market(MARKETS_BY_ID[args.id], latency_ms=args.latency)
    with MarketServer(market) as server:
        log.info("%s escutando em %s:%d (latência %d ms)", market.info.name, MARKET_HOST, server.port, market.latency_ms)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
