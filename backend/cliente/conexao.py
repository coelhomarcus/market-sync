"""Conexão do cliente com o agregador: um socket TCP e o protocolo JSON por linha.

Abre UMA conexão TCP com o agregador (porta 5050) e a mantém aberta; cada
pedido é uma linha JSON enviada e cada resposta uma linha JSON recebida
(ver docs/protocolo.md, seção 2).

    with ClienteAgregador() as c:
        r = c.consultar("arroz", modo="concorrente")

Usada pela interface de terminal (cliente/terminal.py) e pelos experimentos.
"""

from __future__ import annotations

import itertools
import socket

from comum import config, protocolo


class ClienteAgregador:
    """Uma conexão TCP com o agregador. Use com `with` para encerrar direito."""

    def __init__(self, host: str | None = None, port: int | None = None, timeout: float = 60.0) -> None:
        self.host = host or config.AGGREGATOR_HOST
        self.port = port or config.AGGREGATOR_TCP_PORT
        self.sock = socket.create_connection((self.host, self.port), timeout=timeout)  # three-way handshake
        self.stream = self.sock.makefile("rwb")
        self._ids = itertools.count(1)

    def pedir(self, operacao: str, **campos) -> dict:
        """Envia um pedido e espera a resposta correspondente."""
        pedido = {"operacao": operacao, "id": next(self._ids), **campos}
        protocolo.send(self.stream, pedido)
        resposta, _ = protocolo.receive(self.stream)
        if resposta is None:
            raise ConnectionError("o agregador fechou a conexão")
        return resposta

    def consultar(self, produto: str, modo: str = "concorrente", limite: int = 10) -> dict:
        return self.pedir("consultar", produto=produto, modo=modo, limite=limite)

    def comparar(self, produto: str, repeticoes: int = 1) -> dict:
        return self.pedir("comparar", produto=produto, repeticoes=repeticoes)

    def cesta(self, itens: list[dict], modo: str = "concorrente") -> dict:
        return self.pedir("cesta", itens=itens, modo=modo)

    def mercados(self) -> dict:
        return self.pedir("mercados")

    def configurar(self, mercado: str, latencia_ms: int | None = None, online: bool | None = None) -> dict:
        campos = {k: v for k, v in {"latencia_ms": latencia_ms, "online": online}.items() if v is not None}
        return self.pedir("configurar", mercado=mercado, **campos)

    def fechar(self) -> None:
        """Encerramento educado: avisa o agregador e fecha o socket."""
        try:
            self.pedir("encerrar")
        except (OSError, ConnectionError, protocolo.ProtocolError):
            pass
        finally:
            self.stream.close()
            self.sock.close()

    def __enter__(self) -> ClienteAgregador:
        return self

    def __exit__(self, *exc) -> None:
        self.fechar()
