"""Protocolo TCP do sistema: cada mensagem é um objeto JSON numa linha."""

from __future__ import annotations

import json
from typing import BinaryIO

MAX_LINE = 16 * 1024 * 1024  # 16 MB: protege contra uma "linha" sem fim


class ProtocolError(Exception):
    """Mensagem malformada ou conexão encerrada no meio de uma mensagem."""


class InvalidMessage(ProtocolError):
    """A linha chegou inteira, mas não é um objeto JSON: dá para continuar lendo a próxima."""


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
        raise InvalidMessage(f"JSON inválido: {exc}") from exc
    if not isinstance(message, dict):
        raise InvalidMessage("a mensagem deve ser um objeto JSON")
    return message, len(line)
