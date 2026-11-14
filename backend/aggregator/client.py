"""Cliente TCP do agregador: faz UMA pergunta a UM mercado e mede quanto demorou.

Mercado fora do ar (conexão recusada ou fechada sem resposta)? Tenta de novo até
RETRIES vezes, esperando cada vez mais: 0,5 s → 1 s → 2 s. Só então desiste.
Timeout não é repetido: o mercado está lento, não caído, e já esperamos 3 s.

Nunca lança exceção: uma falha vira MarketResult(ok=False) e a consulta aos
outros mercados continua normalmente.
"""

from __future__ import annotations

import socket
import threading
import time
from dataclasses import asdict, dataclass
from typing import Callable

import config
import protocol
from config import MarketInfo

Emit = Callable[[str, dict], None]  # publica um evento para o painel ao vivo


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
    thread: str = ""

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


def ask_once(market: MarketInfo, payload: dict, timeout: float, result: MarketResult) -> dict:
    """Uma ida e volta TCP: conecta, envia a pergunta, espera a resposta."""
    start = time.perf_counter()
    with socket.create_connection((config.MARKET_HOST, market.port), timeout=timeout) as sock:
        result.connect_ms = elapsed_ms(start)
        with sock.makefile("rwb") as stream:
            result.bytes_sent = protocol.send(stream, payload)
            sent = time.perf_counter()
            response, result.bytes_received = protocol.receive(stream)
            result.wait_ms = elapsed_ms(sent)
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
            response = ask_once(market, payload, timeout, result)
            server_cpu_ms = float(response.get("cpu_ms", 0.0))
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
            emit("market_retry", {"market": market.id, "t_ms": elapsed_ms(t0), "attempt": attempt, "wait_ms": round(wait_s * 1000)})
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
                                 "count": count, "bytes": result.bytes_received, "attempts": result.attempts, "thread": result.thread})
    else:
        emit("market_error", {"market": market.id, "t_ms": result.end_ms, "duration_ms": result.duration_ms,
                              "error": result.error, "attempts": result.attempts})
    return result
