"""Faz UMA consulta TCP a UM mercado e mede o tempo.

Fora do ar? Tenta de novo (0,5 s → 1 s → 2 s). Nunca lança exceção: a falha vira ok=False."""

from __future__ import annotations

import socket
import threading
import time
from dataclasses import asdict, dataclass
from typing import Callable

from common import config, protocol
from common.config import MarketInfo

Emit = Callable[[str, dict], None]  # avisa um passo da consulta (o display.py escreve no terminal)


class MarketDown(ConnectionError):
    """O mercado aceitou a conexão mas fechou sem responder (está "fora do ar")."""


@dataclass
class MarketResult:
    market_id: str
    market_name: str
    ok: bool = False
    data: dict | None = None
    error: str | None = None
    attempts: int = 1
    start_ms: float = 0.0  # em relação ao início da consulta do usuário
    end_ms: float = 0.0
    connect_ms: float = 0.0  # quanto levou o connect() da última tentativa
    wait_ms: float = 0.0  # do envio da pergunta até a resposta chegar
    bytes_sent: int = 0
    bytes_received: int = 0
    cpu_ms: float = 0.0  # CPU gasta nesta consulta: nossa thread + a thread do mercado
    thread: str = ""  # thread do agregador que fez a consulta
    server_thread: str = ""  # thread do mercado que atendeu a conexão

    @property
    def duration_ms(self) -> float:
        return round(self.end_ms - self.start_ms, 2)

    def timing(self) -> dict:
        """As medições, sem os dados (é o que vai para as métricas e para a linha do tempo)."""
        d = asdict(self)
        del d["data"]
        d["duration_ms"] = self.duration_ms
        return d


def elapsed_ms(since: float) -> float:
    return round((time.perf_counter() - since) * 1000, 2)


def ask_once(market: MarketInfo, payload: dict, timeout: float, result: MarketResult,
             emit: Emit | None = None, t0: float | None = None) -> dict:
    """Uma ida e volta TCP: conecta, envia a pergunta, espera a resposta, fecha.

    Cada passo vira um evento (tcp_connect, tcp_send, tcp_recv, tcp_close), que o modo
    raw do terminal (start.py --raw) mostra linha a linha.
    """
    emit = emit or (lambda _type, _data: None)
    t0 = time.perf_counter() if t0 is None else t0
    base = {"market": market.id, "thread": result.thread, "attempt": result.attempts}
    start = time.perf_counter()
    with socket.create_connection((config.MARKET_HOST, market.port), timeout=timeout) as sock:
        result.connect_ms = elapsed_ms(start)
        emit("tcp_connect", {**base, "t_ms": elapsed_ms(t0), "connect_ms": result.connect_ms,
                             "local_port": sock.getsockname()[1], "port": market.port})
        with sock.makefile("rwb") as stream:
            result.bytes_sent = protocol.send(stream, payload)
            emit("tcp_send", {**base, "t_ms": elapsed_ms(t0), "bytes": result.bytes_sent, "message": payload})
            sent = time.perf_counter()
            response, result.bytes_received = protocol.receive(stream)
            result.wait_ms = elapsed_ms(sent)
            emit("tcp_recv", {**base, "t_ms": elapsed_ms(t0), "bytes": result.bytes_received, "wait_ms": result.wait_ms,
                              "message": response})
    emit("tcp_close", {**base, "t_ms": elapsed_ms(t0)})
    if response is None:
        raise MarketDown("fechou a conexão sem responder")
    return response


def query_market(
    market: MarketInfo,
    payload: dict,
    *,
    t0: float | None = None,
    timeout: float | None = None,
    retries: int | None = None,
    emit: Emit | None = None,
) -> MarketResult:
    t0 = time.perf_counter() if t0 is None else t0
    timeout = config.TCP_TIMEOUT_S if timeout is None else timeout
    retries = config.RETRIES if retries is None else retries
    emit = emit or (lambda _type, _data: None)

    result = MarketResult(market.id, market.name, thread=threading.current_thread().name)
    result.start_ms = elapsed_ms(t0)
    cpu_start = time.thread_time()  # CPU só desta thread: esperar a rede ou dormir não conta
    emit("market_connect", {"market": market.id, "t_ms": result.start_ms, "thread": result.thread})

    server_cpu_ms = 0.0
    for attempt in range(1, retries + 2):
        result.attempts = attempt
        try:
            response = ask_once(market, payload, timeout, result, emit, t0)
            server_cpu_ms = float(response.get("cpu_ms", 0.0))
            result.server_thread = str(response.get("thread", ""))
            result.ok = bool(response.get("ok"))
            result.data = response.get("data")
            result.error = None if result.ok else response.get("error", "erro desconhecido")
            break
        except ConnectionError as exc:  # recusada / fechada sem resposta: vale tentar de novo
            reason = "conexão recusada" if isinstance(exc, ConnectionRefusedError) else "fora do ar"
            result.error = f"{reason} ({attempt} {'tentativa' if attempt == 1 else 'tentativas'})"
            if attempt > retries:
                break
            wait_s = config.RETRY_WAIT_S * 2 ** (attempt - 1)
            emit("market_retry", {"market": market.id, "t_ms": elapsed_ms(t0), "attempt": attempt, "wait_ms": round(wait_s * 1000),
                                  "thread": result.thread, "reason": reason})
            time.sleep(wait_s)
        except socket.timeout:
            result.error = f"tempo esgotado ({timeout:.1f} s)"
            break
        except (OSError, protocol.ProtocolError) as exc:
            result.error = str(exc) or exc.__class__.__name__
            break

    result.end_ms = elapsed_ms(t0)
    result.cpu_ms = round((time.thread_time() - cpu_start) * 1000 + (server_cpu_ms if result.ok else 0.0), 3)
    if result.ok:
        data = result.data or {}
        count = len(data.get("items", data.get("lines", data.get("points", []))))
        emit("market_response", {"market": market.id, "t_ms": result.end_ms, "duration_ms": result.duration_ms,
                                 "count": count, "bytes": result.bytes_received, "attempts": result.attempts, "thread": result.thread, "server_thread": result.server_thread})
    else:
        emit("market_error", {"market": market.id, "t_ms": result.end_ms, "duration_ms": result.duration_ms,
                              "error": result.error, "attempts": result.attempts, "thread": result.thread})
    return result
