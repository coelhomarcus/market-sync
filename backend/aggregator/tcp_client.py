"""Cliente TCP do agregador: abre uma conexão com um mercado, envia um comando e
espera a resposta, medindo cada etapa (conexão, envio, espera pela resposta)."""

from __future__ import annotations

import socket
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Callable

from common.config import MARKET_HOST, TCP_TIMEOUT_S, MarketInfo
from common.protocol import ProtocolError, recv_msg_sized, send_msg

Emit = Callable[[str, dict], None]


@dataclass
class MarketResult:
    market_id: str
    market_name: str
    ok: bool
    data: dict | None = None
    error: str | None = None
    start_ms: float = 0.0  # relativo ao início da requisição do usuário
    end_ms: float = 0.0
    connect_ms: float = 0.0
    send_ms: float = 0.0
    wait_ms: float = 0.0  # do fim do envio até a resposta chegar
    bytes_sent: int = 0
    bytes_received: int = 0
    server_cpu_ms: float = 0.0  # CPU que a thread do mercado gastou nesta requisição
    thread: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        return round(self.end_ms - self.start_ms, 2)

    def timing(self) -> dict:
        d = asdict(self)
        d.pop("data")
        d.pop("extra")
        d["duration_ms"] = self.duration_ms
        return d


def _ms(start: float, now: float | None = None) -> float:
    return round(((now if now is not None else time.perf_counter()) - start) * 1000, 2)


def query_market(
    market: MarketInfo,
    payload: dict,
    *,
    t0: float | None = None,
    timeout: float = TCP_TIMEOUT_S,
    host: str = MARKET_HOST,
    port: int | None = None,
    emit: Emit | None = None,
) -> MarketResult:
    """Envia `payload` a um mercado via TCP e devolve o resultado com as medições.

    Nunca lança exceção: falhas (timeout, conexão recusada, mercado fora do ar)
    viram MarketResult(ok=False) para que a consulta agregada continue.
    """
    t0 = time.perf_counter() if t0 is None else t0
    emit = emit or (lambda _type, _data: None)

    result = MarketResult(market.id, market.name, ok=False, thread=threading.current_thread().name)
    start = time.perf_counter()
    result.start_ms = _ms(t0, start)
    emit("market_connect", {"market": market.id, "t_ms": result.start_ms, "thread": result.thread})

    try:
        # create_connection = socket() + connect(); o timeout vale para connect/recv
        with socket.create_connection((host, port or market.port), timeout=timeout) as sock:
            connected = time.perf_counter()
            result.connect_ms = _ms(start, connected)

            result.bytes_sent = send_msg(sock, payload)
            sent = time.perf_counter()
            result.send_ms = _ms(connected, sent)

            response, result.bytes_received = recv_msg_sized(sock)
            result.wait_ms = _ms(sent)

        if response is None:
            raise ConnectionError("o mercado encerrou a conexão sem responder (fora do ar?)")
        result.server_cpu_ms = float(response.get("cpu_ms", 0.0))
        if not response.get("ok"):
            raise RuntimeError(response.get("error") or "erro desconhecido")
        result.ok = True
        result.data = response.get("data")
    except socket.timeout:
        result.error = f"tempo esgotado ({timeout:.1f} s)"
    except ConnectionRefusedError:
        result.error = "conexão recusada (processo do mercado não está rodando)"
    except (ConnectionError, ProtocolError, RuntimeError, OSError) as exc:
        result.error = str(exc) or exc.__class__.__name__

    result.end_ms = _ms(t0)
    if result.ok:
        data = result.data or {}
        count = len(data.get("items", data.get("lines", data.get("points", []))))
        emit(
            "market_response",
            {
                "market": market.id,
                "t_ms": result.end_ms,
                "duration_ms": result.duration_ms,
                "connect_ms": result.connect_ms,
                "wait_ms": result.wait_ms,
                "count": count,
                "bytes": result.bytes_received,
                "thread": result.thread,
            },
        )
    else:
        emit("market_error", {"market": market.id, "t_ms": result.end_ms, "duration_ms": result.duration_ms, "error": result.error})
    return result
