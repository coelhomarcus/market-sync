"""Servidor TCP do agregador (porta 5050): uma thread por cliente, uma mensagem JSON por linha.

O que cada operação faz está em operations.py; aqui fica só a parte TCP."""

from __future__ import annotations

import itertools
import logging
import signal
import socket
import socketserver
import threading

from common import config, protocol
from common.watchdog import watch_launcher
from common.config import MARKETS

from . import display, operations
from .aggregator import Aggregator

SHUTDOWN_WAIT_S = 7.0  # tempo máximo para as pesquisas em andamento terminarem (a mais longa: ~6 s)


class AggregatorTCPServer(socketserver.ThreadingTCPServer):
    daemon_threads = True  # threads de cliente não seguram o processo ao encerrar
    allow_reuse_address = True
    request_queue_size = 64  # fila do listen(): clientes esperando o accept()

    def __init__(self, aggregator: Aggregator, host: str | None = None, port: int | None = None) -> None:
        self.aggregator = aggregator
        self.clients_connected = 0
        self.clients_served = 0
        self._numbers = itertools.count(1)
        self._lock = threading.Lock()
        self._in_progress = 0  # pedidos sendo atendidos agora (para encerrar sem cortar ninguém)
        self._no_requests = threading.Condition(self._lock)
        self._thread: threading.Thread | None = None
        super().__init__((host or config.AGGREGATOR_HOST, config.AGGREGATOR_TCP_PORT if port is None else port), ClientHandler)

    @property
    def port(self) -> int:
        return self.server_address[1]

    def start(self) -> None:
        """Atende os clientes numa thread de fundo (usado nos testes)."""
        self._thread = threading.Thread(target=self.serve_forever, name="agregador-tcp-accept", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.shutdown()
        self.server_close()

    def client_joined(self) -> int:
        with self._lock:
            self.clients_connected += 1
            self.clients_served += 1
        return next(self._numbers)

    def client_left(self) -> None:
        with self._lock:
            self.clients_connected -= 1

    def request_started(self) -> None:
        with self._lock:
            self._in_progress += 1

    def request_finished(self) -> None:
        with self._lock:
            self._in_progress -= 1
            self._no_requests.notify_all()

    def wait_for_requests(self, limit_s: float) -> bool:
        """Espera os pedidos em andamento terminarem (até limit_s). True se todos terminaram."""
        with self._no_requests:
            return self._no_requests.wait_for(lambda: self._in_progress == 0, timeout=limit_s)


class ClientHandler(socketserver.StreamRequestHandler):
    """Atende UM cliente, numa thread própria, até ele encerrar a conexão."""

    timeout = config.CLIENT_IDLE_TIMEOUT_S  # aplicado ao socket: readline() desiste após esse tempo parado

    def handle(self) -> None:
        server: AggregatorTCPServer = self.server  # type: ignore[assignment]
        self.number = server.client_joined()
        threading.current_thread().name = f"cliente-{self.number}"
        peer = "%s:%d" % self.client_address[:2]
        display.event("client_connect", {"client": self.number, "peer": peer, "connected": server.clients_connected})
        try:
            self.conversation(server)
        except socket.timeout:  # cliente parado tempo demais
            self.reply(operations.error("TEMPO_ESGOTADO", "conexão encerrada por inatividade"))
        except protocol.ProtocolError as exc:  # linha incompleta: não dá para continuar lendo
            self.reply(operations.error("MENSAGEM_INVALIDA", str(exc)))
        except OSError as exc:  # o cliente sumiu no meio da conversa
            display.event("client_drop", {"client": self.number, "error": str(exc)})
        finally:
            server.client_left()
            display.event("client_disconnect", {"client": self.number, "connected": server.clients_connected})

    def conversation(self, server: AggregatorTCPServer) -> None:
        """Lê um pedido, responde e repete, até o cliente fechar o socket ou pedir 'encerrar'."""
        while True:
            try:
                request, nbytes = protocol.receive(self.rfile)  # espera uma linha JSON
            except protocol.InvalidMessage as exc:  # JSON quebrado: avisa e lê o próximo
                self.reply(operations.error("MENSAGEM_INVALIDA", str(exc)))
                continue
            if request is None:  # o cliente fechou o socket
                return
            display.event("client_request", {"client": self.number, "bytes": nbytes, "message": request})

            server.request_started()
            response = operations.answer(request, server.aggregator, server.clients_connected)
            server.request_finished()

            self.reply(response)
            if response["operacao"] == "encerrar":
                return

    def reply(self, message: dict) -> None:
        nbytes = protocol.send(self.wfile, message)
        display.event("client_reply", {"client": self.number, "bytes": nbytes, "message": message})


def _interrupt_signal(signum, frame):  # noqa: ARG001
    raise KeyboardInterrupt


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Agregador: servidor TCP dos clientes (porta 5050)")
    parser.add_argument("--port", type=int, default=config.AGGREGATOR_TCP_PORT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="[agregador] %(message)s")  # só erros inesperados
    signal.signal(signal.SIGTERM, _interrupt_signal)  # `kill` encerra igual ao Ctrl+C
    watch_launcher()  # se o start.py morrer, o agregador se encerra junto

    with AggregatorTCPServer(Aggregator(list(MARKETS)), port=args.port) as server:
        print(f"  Agregador em tcp://{config.AGGREGATOR_HOST}:{server.port}   ·   "
              f"cliente: ./client.py\n", flush=True)
        display.start()
        try:
            server.serve_forever()  # thread principal: só faz accept(); cada cliente ganha uma thread
        except KeyboardInterrupt:
            pass
        finally:
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, signal.SIG_IGN)  # Ctrl+C repetido não interrompe a espera
            display.shutting_down()
            server.wait_for_requests(SHUTDOWN_WAIT_S)  # quem já pediu recebe a resposta
            display.stop()


if __name__ == "__main__":
    main()
