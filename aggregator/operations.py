"""As operações que o cliente pode pedir ao agregador: consultar, comparar, mercados, configurar, encerrar.

Não sabe nada de socket: recebe o pedido como dicionário e devolve a resposta como dicionário."""

from __future__ import annotations

import logging
import statistics

from . import consolidation
from .aggregator import Aggregator, MarketNotFound, MarketUnreachable

log = logging.getLogger("agregador.operacoes")

MODES = {"sequencial": "sequential", "concorrente": "concurrent", "sequential": "sequential", "concurrent": "concurrent"}
MODE_NAMES = {"sequential": "sequencial", "concurrent": "concorrente"}
MAX_QUERY = 80
MAX_LIMIT = 100


class RequestError(Exception):
    """Pedido inválido: vira uma resposta {"status": "erro", "codigo": ..., "mensagem": ...}."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def error(code: str, message: str) -> dict:
    return {"status": "erro", "codigo": code, "mensagem": message}


# ---------------------------------------------------------------- ponto de entrada

def answer(request: dict, aggregator: Aggregator, clients_connected: int) -> dict:
    """Executa o pedido e devolve a resposta. Nunca lança exceção: um erro vira {"status": "erro"}."""
    op = str(request.get("operacao", "")).strip().lower()
    operations = {
        "consultar": lambda: search(request, aggregator),
        "comparar": lambda: compare(request, aggregator),
        "mercados": lambda: markets(aggregator, clients_connected),
        "configurar": lambda: configure(request, aggregator),
        "encerrar": lambda: {"status": "sucesso", "mensagem": "conexão encerrada"},
    }
    try:
        if op not in operations:
            raise RequestError("OPERACAO_DESCONHECIDA", f"operação desconhecida: {op!r}")
        response = {"operacao": op, **operations[op]()}
    except RequestError as exc:
        response = {"operacao": op, **error(exc.code, str(exc))}
    except Exception as exc:  # noqa: BLE001 — um erro interno não derruba o agregador
        log.exception("erro ao atender %s", request)
        response = {"operacao": op, **error("ERRO_INTERNO", str(exc))}
    if "id" in request:  # o cliente pode numerar os pedidos para casar com as respostas
        response["id"] = request["id"]
    return response


# ---------------------------------------------------------------- validação dos parâmetros

def _mode(request: dict) -> str:
    raw = str(request.get("modo", "concorrente")).strip().lower()
    if raw not in MODES:
        raise RequestError("PARAMETRO_INVALIDO", f"modo inválido: {raw!r} (use 'sequencial' ou 'concorrente')")
    return MODES[raw]


def _product(request: dict) -> str:
    query = request.get("produto")
    if not isinstance(query, str) or not query.strip():
        raise RequestError("PARAMETRO_INVALIDO", "informe o produto a pesquisar no campo 'produto'")
    return query.strip()[:MAX_QUERY]


def _int(request: dict, field: str, default: int, low: int, high: int) -> int:
    value = request.get(field, default)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise RequestError("PARAMETRO_INVALIDO", f"'{field}' deve ser um inteiro entre {low} e {high}")
    return value


# ---------------------------------------------------------------- montagem das respostas

def _markets_summary(record: dict) -> list[dict]:
    """O que aconteceu com cada mercado nesta pesquisa (tempo, tentativas, erro)."""
    return [{
        "id": m["market_id"],
        "fonte": m["market_name"],
        "status": "erro" if m["error"] else "sucesso",
        "inicio_ms": m["start_ms"],
        "fim_ms": m["end_ms"],
        "tempo_ms": m["duration_ms"],
        "tentativas": m["attempts"],
        "bytes_recebidos": m["bytes_received"],
        "erro": m["error"],
    } for m in record["markets"]]


def _overall_status(record: dict) -> str:
    if record["ok_count"] == 0:
        return "erro"
    return "parcial" if record["error_count"] else "sucesso"


def _offer(product: dict, offer: dict) -> dict:
    return {
        "fonte": offer["market_name"],
        "produto": f"{product['name']} {product['brand']} {product['unit']}",
        "preco": offer["price"],
        "status": "sucesso" if offer["in_stock"] else "sem_estoque",
    }


# ---------------------------------------------------------------- operações

def search(request: dict, aggregator: Aggregator) -> dict:
    query, mode = _product(request), _mode(request)
    limit = _int(request, "limite", 10, 1, MAX_LIMIT)
    results, record = aggregator.execute(mode, {"cmd": "SEARCH", "q": query}, query, source="cliente_tcp")
    data = consolidation.search_response(results, record, category="", sort="preco", page=1, page_size=limit)
    products = [{
        "produto": p["name"],
        "marca": p["brand"],
        "unidade": p["unit"],
        "categoria": p["category"],
        "slug": p["slug"],
        "menor_preco": {"fonte": p["cheapest"]["market_name"], "preco": p["cheapest"]["price"]} if p["cheapest"] else None,
        "maior_preco": p["max_price"],
        "economia": p["savings"],
        "ofertas": [_offer(p, o) for o in p["offers"]],  # já do menor para o maior preço
    } for p in data["products"]]
    status = _overall_status(record)
    response = {
        "status": status,
        "produto": query,
        "modo": MODE_NAMES[mode],
        "tempo_total_ms": record["total_ms"],
        "produtos_encontrados": data["total_products"],
        "ofertas_encontradas": data["total_offers"],
        "resultados": products,
        "mercados": _markets_summary(record),
    }
    if status == "erro":
        response.update({"codigo": "NENHUM_MERCADO_RESPONDEU", "mensagem": "nenhum supermercado respondeu à pesquisa"})
    return response


def compare(request: dict, aggregator: Aggregator) -> dict:
    """Roda a mesma pesquisa nos dois modos e devolve os tempos (demonstração / experimentos)."""
    query = _product(request)
    runs = _int(request, "repeticoes", 1, 1, 10)
    records = []
    for i in range(runs):  # alterna a ordem para nenhum modo levar vantagem
        for mode in ("sequential", "concurrent") if i % 2 == 0 else ("concurrent", "sequential"):
            records.append(aggregator.execute(mode, {"cmd": "SEARCH", "q": query}, query, source="cliente_tcp")[1])
    times = {m: [r["total_ms"] for r in records if r["mode"] == m] for m in ("sequential", "concurrent")}
    mean = {m: round(statistics.fmean(t), 2) for m, t in times.items()}
    last = {r["mode"]: r for r in records}
    return {
        "status": "sucesso",
        "produto": query,
        "repeticoes": runs,
        **{MODE_NAMES[m]: {
            "tempo_medio_ms": mean[m],
            "tempo_min_ms": min(times[m]),
            "tempo_max_ms": max(times[m]),
            "mercados_ok": last[m]["ok_count"],
            "mercados": _markets_summary(last[m]),
        } for m in ("sequential", "concurrent")},
        "speedup": round(mean["sequential"] / mean["concurrent"], 2),
    }


def markets(aggregator: Aggregator, clients_connected: int) -> dict:
    return {
        "status": "sucesso",
        "clientes_conectados": clients_connected,
        "mercados": [{
            "id": s["id"],
            "fonte": s["name"],
            "porta": s["port"],
            "alcancavel": s["reachable"],
            "online": s["online"],
            "latencia_ms": s.get("latency_ms"),
            "produtos": s.get("products"),
            "erro": s.get("error"),
        } for s in aggregator.markets_status()],
    }


def configure(request: dict, aggregator: Aggregator) -> dict:
    market_id = request.get("mercado")
    latency = request.get("latencia_ms")
    online = request.get("online")
    if latency is not None:
        latency = _int(request, "latencia_ms", 0, 0, 10_000)
    if online is not None and not isinstance(online, bool):
        raise RequestError("PARAMETRO_INVALIDO", "'online' deve ser true ou false")
    try:
        s = aggregator.configure_market(str(market_id), latency, online)
    except MarketNotFound:
        raise RequestError("MERCADO_DESCONHECIDO", f"mercado desconhecido: {market_id!r}") from None
    except MarketUnreachable as exc:
        raise RequestError("MERCADO_INDISPONIVEL", str(exc)) from None
    return {"status": "sucesso", "mercado": s["id"], "fonte": s["name"], "online": s["online"], "latencia_ms": s["latency_ms"]}
