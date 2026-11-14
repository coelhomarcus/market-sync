"""Conexão do cliente com o agregador: um socket TCP e o protocolo JSON por linha.

Abre UMA conexão TCP com o agregador (porta 5050) e a mantém aberta; cada
pedido é uma linha JSON enviada e cada resposta uma linha JSON recebida
(ver docs/protocolo.md, seção 2).

    with ClienteAgregador() as c:
        r = c.consultar("arroz", modo="concorrente")

Usada pela interface de terminal (client/terminal.py) e pelos experimentos.
"""

from __future__ import annotations

import itertools
import socket

from common import config, protocol


class AggregatorClient:
    """Uma conexão TCP com o agregador. Use com `with` para encerrar direito."""

    def __init__(self, host: str | None = None, port: int | None = None, timeout: float = 60.0) -> None:
        self.host = host or config.AGGREGATOR_HOST
        self.port = port or config.AGGREGATOR_TCP_PORT
        self.sock = socket.create_connection((self.host, self.port), timeout=timeout)  # three-way handshake
        self.stream = self.sock.makefile("rwb")
        self._ids = itertools.count(1)

    def request(self, operation: str, fields: dict | None = None) -> dict:
        """Envia um pedido e espera a resposta correspondente.

        Os nomes dos campos são os do protocolo (docs/protocolo.md), em português,
        como no exemplo do enunciado: {"operacao": "consultar", "produto": "arroz"}.
        """
        request = {"operacao": operation, "id": next(self._ids), **(fields or {})}
        protocol.send(self.stream, request)
        response, _ = protocol.receive(self.stream)
        if response is None:
            raise ConnectionError("o agregador fechou a conexão")
        return response

    def search(self, product: str, mode: str = "concorrente", limit: int = 10) -> dict:
        return self.request("consultar", {"produto": product, "modo": mode, "limite": limit})

    def compare(self, product: str, rounds: int = 1) -> dict:
        return self.request("comparar", {"produto": product, "repeticoes": rounds})

    def basket(self, items: list[dict], mode: str = "concorrente") -> dict:
        """items: [{"produto": slug, "quantidade": 2}, ...]"""
        return self.request("cesta", {"itens": items, "modo": mode})

    def markets(self) -> dict:
        return self.request("mercados")

    def configure(self, market: str, latency_ms: int | None = None, online: bool | None = None) -> dict:
        fields = {"mercado": market}
        if latency_ms is not None:
            fields["latencia_ms"] = latency_ms
        if online is not None:
            fields["online"] = online
        return self.request("configurar", fields)

    def close(self) -> None:
        """Encerramento educado: avisa o agregador e fecha o socket."""
        try:
            self.request("encerrar")
        except (OSError, ConnectionError, protocol.ProtocolError):
            pass
        finally:
            self.stream.close()
            self.sock.close()

    def __enter__(self) -> AggregatorClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
