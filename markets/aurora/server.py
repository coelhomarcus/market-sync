"""Servidor TCP do supermercado Mercado Aurora: uma thread por conexão (ThreadingTCPServer).

Pedidos: SEARCH, STATUS e CONFIG. Rodar sozinho: .venv/bin/python -m markets.aurora"""

from __future__ import annotations

import argparse
import logging
import os
import random
import socketserver
import sys
import threading
import time
from pathlib import Path

from common import protocol
from common.watchdog import watch_launcher

from .database import MarketDatabase

# ---------------------------------------------------------------- dados deste supermercado
ID = "aurora"
NAME = "Mercado Aurora"
SHORT_NAME = "Aurora"
HOST = os.environ.get("MARKET_HOST", "127.0.0.1")
PORT = 5001
LATENCY_MS = 300  # latência simulada inicial (o mercado "finge" estar longe)
DATABASE = Path(__file__).resolve().parent / "aurora.db"  # gerado por: python -m tools.seed_databases

log = logging.getLogger(ID)

ADMIN_COMMANDS = {"STATUS", "CONFIG"}  # continuam respondendo com o mercado "fora do ar"


class WentDown(Exception):
    """O mercado saiu do ar enquanto uma consulta esperava: a conexão cai sem resposta."""


class Market:
    """O mercado em si: o banco de dados mais a simulação de lentidão e de queda."""

    def __init__(self, database: Path | None = None, latency_ms: int | None = None, jitter: float = 0.15) -> None:
        self.id, self.name = ID, NAME
        self.database = MarketDatabase(database or DATABASE)
        if not self.database.path.exists():
            raise SystemExit(f"{NAME}: banco {self.database.path} não existe. Gere com: python -m tools.seed_databases")
        self.products = self.database.count_products()
        self.latency_ms = LATENCY_MS if latency_ms is None else latency_ms
        self.jitter = jitter  # variação aleatória da latência (±15%)
        self.online = True
        self.down = threading.Event()  # sinalizado quando o mercado sai do ar: acorda quem está esperando
        self.requests_served = 0
        self.connections = 0  # conexões recebidas até agora; cada uma é atendida por uma thread nova
        self.lock = threading.Lock()  # várias threads de conexão mexem nos campos acima

    def handle_request(self, cmd: str, request: dict) -> dict:
        if cmd == "STATUS":
            return self.status()
        if cmd == "CONFIG":
            return self.configure(request)
        if cmd == "SEARCH":
            self.simulate_latency()
            return {"items": self.database.search(str(request.get("q", "")))}
        raise ValueError(f"comando desconhecido: {cmd!r}")

    def new_connection(self) -> int:
        """Conta mais uma conexão e devolve o número dela (1, 2, 3...)."""
        with self.lock:
            self.connections += 1
            return self.connections

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
                "db_bytes": self.database.path.stat().st_size,
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


class ConnectionHandler(socketserver.StreamRequestHandler):
    """Atende UMA conexão do agregador, numa thread própria: lê um pedido e responde."""

    def handle(self) -> None:
        market: Market = self.server.market  # type: ignore[attr-defined]
        try:
            request, _ = protocol.receive(self.rfile)
        except protocol.ProtocolError as exc:
            log.warning("mensagem inválida de %s: %s", self.client_address, exc)
            return
        if request is None:  # conectou e fechou sem pedir nada (o teste de porta do start.py)
            return

        cmd = str(request.get("cmd", "")).upper()
        # o ThreadingTCPServer criou uma thread nova para esta conexão; ela ganha o nome da conexão
        number = market.new_connection()
        thread = f"conexão nº {number}"
        threading.current_thread().name = thread
        if cmd != "STATUS":  # STATUS é só verificação (operação "mercados" do cliente); não polui o log
            log.info("%-14s ← recebeu %s %s  de :%d", thread, cmd, self.arguments(cmd, request), self.client_address[1])
        if not market.online and cmd not in ADMIN_COMMANDS:
            log.info("%-14s ✕ fora do ar: fechou a conexão sem responder", thread)
            return  # "fora do ar": fecha a conexão sem responder

        start = time.perf_counter()
        cpu_start = time.thread_time()  # CPU só desta thread (a espera da latência não conta)
        try:
            response = {"ok": True, "data": market.handle_request(cmd, request)}
        except WentDown:
            log.info("%-14s ✕ saiu do ar no meio da consulta: conexão fechada", thread)
            return  # caiu durante a consulta: fecha a conexão sem responder
        except Exception as exc:  # erro no pedido vira resposta de erro, o servidor segue de pé
            response = {"ok": False, "error": str(exc)}
        response["cpu_ms"] = round((time.thread_time() - cpu_start) * 1000, 3)
        response["thread"] = thread  # qual conexão (= qual thread) deste mercado atendeu; o agregador mostra
        nbytes = protocol.send(self.wfile, response)
        self.log_reply(cmd, response, nbytes, (time.perf_counter() - start) * 1000, thread)

    @staticmethod
    def arguments(cmd: str, request: dict) -> str:
        if cmd == "SEARCH":
            return f'"{request.get("q", "")}"'
        if cmd == "CONFIG":
            return " ".join(f"{k}={v}" for k, v in request.items() if k != "cmd")
        return ""

    @staticmethod
    def log_reply(cmd: str, response: dict, nbytes: int, ms: float, thread: str) -> None:
        """Uma linha por resposta enviada (STATUS fica de fora: é só verificação)."""
        if cmd == "STATUS":
            return
        if not response["ok"]:
            summary = f"erro: {response['error']}"
        elif cmd == "SEARCH":
            summary = f"{len(response['data']['items'])} itens"
        else:
            d = response["data"]
            summary = f"agora {'no ar' if d.get('online') else 'FORA DO AR'}, latência {d.get('latency_ms')} ms"
        log.info("%-14s → respondeu %s · %d B · %.0f ms", thread, summary, nbytes, ms)


class MarketServer(socketserver.ThreadingTCPServer):
    daemon_threads = True  # as threads de conexão não seguram o processo ao encerrar
    allow_reuse_address = True
    request_queue_size = 64  # tamanho da fila do listen()

    def __init__(self, market: Market, host: str = HOST, port: int = PORT) -> None:
        self.market = market
        super().__init__((host, port), ConnectionHandler)

    @property
    def port(self) -> int:
        return self.server_address[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Servidor TCP do supermercado {NAME} (porta {PORT})")
    parser.add_argument("--latency", type=int, help=f"latência simulada em ms (padrão {LATENCY_MS})")
    args = parser.parse_args()

    quiet = os.environ.get("QUIET", "") in ("1", "true", "sim")
    # no modo raw do start.py (--raw) este log vai para o mesmo terminal do agregador, recuado
    # depois de "┃" e em cinza (é o lado servidor de cada chamada); no gráfico vai para logs/aurora.log
    fmt = f"%(asctime)s.%(msecs)03d         ┃ {SHORT_NAME:<11} %(message)s"
    if sys.stdout.isatty():
        fmt = f"\033[2m{fmt}\033[0m"
    logging.basicConfig(level=logging.WARNING if quiet else logging.INFO, format=fmt, datefmt="%H:%M:%S",
                        stream=sys.stdout)
    market = Market(latency_ms=args.latency)
    watch_launcher()  # se o start.py morrer, este mercado se encerra junto
    with MarketServer(market) as server:
        log.info("%s escutando em %s:%d (latência %d ms, %d produtos)", NAME, HOST, server.port,
                 market.latency_ms, market.products)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
