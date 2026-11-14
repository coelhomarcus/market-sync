"""Protocolo de aplicação sobre TCP usado entre o agregador e os mercados.

TCP entrega um *fluxo* de bytes, sem fronteiras de mensagem. Para saber onde
cada mensagem termina usamos *framing* por prefixo de tamanho:

    +----------------------+------------------------------+
    | 4 bytes (big-endian) |  N bytes de JSON em UTF-8    |
    |  N = tamanho do JSON |                              |
    +----------------------+------------------------------+

Requisição:  {"cmd": "SEARCH", "q": "arroz"}
Resposta:    {"ok": true, "data": {...}}  ou  {"ok": false, "error": "..."}
"""

from __future__ import annotations

import json
import socket
import struct

HEADER = struct.Struct(">I")  # unsigned int de 4 bytes, ordem de rede (big-endian)
MAX_MESSAGE_SIZE = 8 * 1024 * 1024  # 8 MiB: protege contra cabeçalhos corrompidos


class ProtocolError(Exception):
    """Mensagem malformada ou conexão encerrada no meio de um frame."""


def encode(obj: dict) -> bytes:
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_MESSAGE_SIZE:
        raise ProtocolError(f"mensagem grande demais ({len(payload)} bytes)")
    return HEADER.pack(len(payload)) + payload


def send_msg(sock: socket.socket, obj: dict) -> int:
    """Envia um objeto como um frame. Retorna o total de bytes enviados."""
    frame = encode(obj)
    sock.sendall(frame)  # sendall repete send() até todos os bytes saírem
    return len(frame)


def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
    """Lê exatamente n bytes. Retorna None se a conexão fechar antes do 1º byte."""
    chunks: list[bytes] = []
    received = 0
    while received < n:
        chunk = sock.recv(min(n - received, 65536))
        if not chunk:
            if received == 0:
                return None
            raise ProtocolError("conexão encerrada no meio de uma mensagem")
        chunks.append(chunk)
        received += len(chunk)
    return b"".join(chunks)


def recv_msg(sock: socket.socket) -> dict | None:
    """Recebe um frame e devolve o objeto. None = o outro lado fechou a conexão."""
    obj, _ = recv_msg_sized(sock)
    return obj


def recv_msg_sized(sock: socket.socket) -> tuple[dict | None, int]:
    """Como recv_msg, mas também devolve quantos bytes o frame ocupou na rede."""
    header = _recv_exact(sock, HEADER.size)
    if header is None:
        return None, 0
    (size,) = HEADER.unpack(header)
    if size > MAX_MESSAGE_SIZE:
        raise ProtocolError(f"tamanho anunciado inválido: {size}")
    payload = _recv_exact(sock, size) if size else b""
    if payload is None:
        raise ProtocolError("conexão encerrada antes do corpo da mensagem")
    try:
        obj = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"JSON inválido: {exc}") from exc
    if not isinstance(obj, dict):
        raise ProtocolError("a mensagem deve ser um objeto JSON")
    return obj, HEADER.size + size
