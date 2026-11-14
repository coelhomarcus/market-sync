"""Protocolo entre agregador e mercados: uma mensagem JSON por linha.

O TCP entrega um fluxo de bytes, sem separar mensagens. A regra aqui é simples:
cada mensagem é um objeto JSON em UTF-8 terminado por '\\n'. O JSON nunca tem
quebra de linha crua dentro dele, então a linha delimita a mensagem.

    agregador → mercado:  {"cmd": "SEARCH", "q": "arroz"}\\n
    mercado → agregador:  {"ok": true, "data": {...}, "cpu_ms": 1.2}\\n

Os dois lados usam o socket como arquivo (`sock.makefile`), e `readline()`
junta os pedaços que o TCP entregar até achar o '\\n'.
"""

from __future__ import annotations

import json
from typing import BinaryIO

MAX_LINE = 16 * 1024 * 1024  # 16 MB: protege contra uma "linha" sem fim


class ProtocolError(Exception):
    """Mensagem malformada ou conexão encerrada no meio de uma mensagem."""


def send(stream: BinaryIO, message: dict) -> int:
    """Escreve a mensagem como uma linha e devolve quantos bytes foram enviados."""
    data = (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    stream.write(data)
    stream.flush()
    return len(data)


def receive(stream: BinaryIO) -> tuple[dict | None, int]:
    """Lê uma linha e devolve (mensagem, bytes recebidos). (None, 0) = o outro lado fechou."""
    line = stream.readline(MAX_LINE + 1)
    if not line:
        return None, 0
    if not line.endswith(b"\n"):
        raise ProtocolError("mensagem incompleta ou grande demais")
    try:
        message = json.loads(line)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"JSON inválido: {exc}") from exc
    if not isinstance(message, dict):
        raise ProtocolError("a mensagem deve ser um objeto JSON")
    return message, len(line)
