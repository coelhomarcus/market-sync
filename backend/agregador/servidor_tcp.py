"""Servidor TCP do agregador: é por aqui que o cliente (pacote cliente/) faz as pesquisas.

Usa o mesmo framing do protocolo com os mercados (uma mensagem JSON por linha,
ver comum/protocolo.py), com as mensagens no formato sugerido pelo enunciado:

    cliente → agregador:  {"operacao": "consultar", "produto": "arroz", "modo": "concorrente"}
    agregador → cliente:  {"status": "sucesso", "operacao": "consultar", "produto": "arroz",
                           "resultados": [{"produto": "Arroz Branco", "menor_preco": {...},
                                           "ofertas": [{"fonte": "Max Atacarejo", "preco": 24.9, ...}]}], ...}

Operações: consultar, comparar, cesta, mercados, configurar, encerrar (docs/protocolo.md).

Uma conexão pode levar várias operações seguidas: o cliente de terminal mantém a
conexão aberta durante a sessão. Ela termina quando o cliente envia
{"operacao": "encerrar"}, quando fecha o socket ou depois de CLIENT_IDLE_TIMEOUT_S
sem receber nada.

ThreadingTCPServer: uma thread por cliente conectado, então vários clientes são
atendidos ao mesmo tempo, e cada um deles ainda pode disparar 5 threads de consulta
aos mercados (modo concorrente).

Rodar sozinho, sem a parte web:  python -m agregador.servidor_tcp   (dentro de backend/)
"""

from __future__ import annotations

import logging
import socket
import socketserver
import threading

from comum import config, protocolo
from comum.config import MARKETS, MarketInfo

from . import consolidacao
from .agregador import Aggregator, MarketNotFound, MarketUnreachable
from .metricas import summarize

log = logging.getLogger("agregador.tcp")

MODES = {"sequencial": "sequential", "concorrente": "concurrent", "sequential": "sequential", "concurrent": "concurrent"}
MODE_NAMES = {"sequential": "sequencial", "concurrent": "concorrente"}
MAX_QUERY = 80
MAX_LIMIT = 100


class RequestError(Exception):
    """Pedido inválido: vira uma resposta {"status": "erro", "codigo": ..., "mensagem": ...}."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


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


class AggregatorTCPServer(socketserver.ThreadingTCPServer):
    daemon_threads = True  # threads de cliente não seguram o processo ao encerrar
    allow_reuse_address = True
    request_queue_size = 64  # fila do listen(): clientes esperando o accept()

    def __init__(self, aggregator: Aggregator, host: str | None = None, port: int | None = None) -> None:
        self.aggregator = aggregator
        self.clients_connected = 0
        self.clients_served = 0
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        super().__init__((host or config.AGGREGATOR_HOST, config.AGGREGATOR_TCP_PORT if port is None else port), ClientHandler)

    @property
    def port(self) -> int:
        return self.server_address[1]

    def start(self) -> None:
        """Atende os clientes numa thread de fundo (usado quando roda junto com o FastAPI)."""
        self._thread = threading.Thread(target=self.serve_forever, name="agregador-tcp-accept", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.shutdown()
        self.server_close()

    def client_joined(self) -> None:
        with self._lock:
            self.clients_connected += 1
            self.clients_served += 1

    def client_left(self) -> None:
        with self._lock:
            self.clients_connected -= 1

    # ------------------------------------------------------------ operações

    def dispatch(self, request: dict) -> dict:
        op = str(request.get("operacao", "")).strip().lower()
        handler = getattr(self, f"op_{op}", None) if op.isidentifier() else None
        if handler is None:
            raise RequestError("OPERACAO_DESCONHECIDA", f"operação desconhecida: {op!r}")
        return handler(request)

    def op_consultar(self, request: dict) -> dict:
        query, mode = _product(request), _mode(request)
        limit = _int(request, "limite", 10, 1, MAX_LIMIT)
        results, record = self.aggregator.execute(mode, "search", {"cmd": "SEARCH", "q": query}, query, source="cliente_tcp")
        data = consolidacao.search_response(results, record, category="", sort="preco", page=1, page_size=limit)
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
            response.update(codigo="NENHUM_MERCADO_RESPONDEU", mensagem="nenhum supermercado respondeu à pesquisa")
        return response

    def op_comparar(self, request: dict) -> dict:
        """Roda a mesma pesquisa nos dois modos e devolve os tempos (demonstração / experimentos)."""
        query = _product(request)
        runs = _int(request, "repeticoes", 1, 1, 10)
        records = []
        for i in range(runs):  # alterna a ordem para nenhum modo levar vantagem
            for mode in ("sequential", "concurrent") if i % 2 == 0 else ("concurrent", "sequential"):
                records.append(self.aggregator.execute(mode, "search", {"cmd": "SEARCH", "q": query}, query, source="cliente_tcp")[1])
        summary = summarize(records)
        last = {r["mode"]: r for r in records}
        return {
            "status": "sucesso",
            "produto": query,
            "repeticoes": runs,
            **{MODE_NAMES[m]: {
                "tempo_medio_ms": summary[m]["avg"],
                "tempo_min_ms": summary[m]["min"],
                "tempo_max_ms": summary[m]["max"],
                "mercados_ok": last[m]["ok_count"],
                "mercados": _markets_summary(last[m]),
            } for m in ("sequential", "concurrent")},
            "speedup": summary["speedup"],
        }

    def op_cesta(self, request: dict) -> dict:
        mode = _mode(request)
        items = request.get("itens")
        if not isinstance(items, list) or not 1 <= len(items) <= 60:
            raise RequestError("PARAMETRO_INVALIDO", "'itens' deve ser uma lista com 1 a 60 itens")
        wanted: dict[str, int] = {}
        for item in items:
            slug = item.get("produto") if isinstance(item, dict) else None
            qty = item.get("quantidade", 1) if isinstance(item, dict) else None
            if not isinstance(slug, str) or not slug or isinstance(qty, bool) or not isinstance(qty, int) or not 1 <= qty <= 99:
                raise RequestError("PARAMETRO_INVALIDO", "cada item precisa de 'produto' (slug) e 'quantidade' entre 1 e 99")
            wanted[slug] = qty
        payload = {"cmd": "BASKET", "items": [{"slug": s, "qty": q} for s, q in wanted.items()]}
        results, record = self.aggregator.execute(mode, "basket", payload, f"cesta ({len(wanted)} itens)", source="cliente_tcp")
        data = consolidacao.basket_response(wanted, results, record)
        totals = [{
            "fonte": m["market_name"],
            "status": "sucesso" if m["ok"] else "erro",
            "total": m.get("total"),
            "completa": m.get("complete", False),
            "faltando": m.get("missing", []),
            "erro": m.get("error"),
        } for m in data["markets"]]
        cheapest = data["cheapest"]
        return {
            "status": _overall_status(record),
            "modo": MODE_NAMES[mode],
            "tempo_total_ms": record["total_ms"],
            "totais": totals,  # do menor total (cesta completa) para o maior
            "mais_barato": {"fonte": cheapest["market_name"], "total": cheapest["total"]} if cheapest else None,
            "mercados": _markets_summary(record),
        }

    def op_mercados(self, request: dict) -> dict:  # noqa: ARG002
        return {
            "status": "sucesso",
            "clientes_conectados": self.clients_connected,
            "mercados": [{
                "id": s["id"],
                "fonte": s["name"],
                "porta": s["port"],
                "alcancavel": s["reachable"],
                "online": s["online"],
                "latencia_ms": s.get("latency_ms"),
                "produtos": s.get("products"),
                "erro": s.get("error"),
            } for s in self.aggregator.markets_status()],
        }

    def op_configurar(self, request: dict) -> dict:
        market_id = request.get("mercado")
        latency = request.get("latencia_ms")
        online = request.get("online")
        if latency is not None:
            latency = _int(request, "latencia_ms", 0, 0, 10_000)
        if online is not None and not isinstance(online, bool):
            raise RequestError("PARAMETRO_INVALIDO", "'online' deve ser true ou false")
        try:
            s = self.aggregator.configure_market(str(market_id), latency, online)
        except MarketNotFound:
            raise RequestError("MERCADO_DESCONHECIDO", f"mercado desconhecido: {market_id!r}") from None
        except MarketUnreachable as exc:
            raise RequestError("MERCADO_INDISPONIVEL", str(exc)) from None
        return {"status": "sucesso", "mercado": s["id"], "fonte": s["name"], "online": s["online"], "latencia_ms": s["latency_ms"]}

    def op_encerrar(self, request: dict) -> dict:  # noqa: ARG002
        return {"status": "sucesso", "mensagem": "conexão encerrada"}


class ClientHandler(socketserver.StreamRequestHandler):
    """Atende UM cliente, numa thread própria, até ele encerrar a conexão."""

    timeout = config.CLIENT_IDLE_TIMEOUT_S  # aplicado ao socket: readline() desiste após esse tempo parado

    def handle(self) -> None:
        server: AggregatorTCPServer = self.server  # type: ignore[assignment]
        server.client_joined()
        peer = "%s:%d" % self.client_address[:2]
        log.info("cliente %s conectou", peer)
        try:
            self.serve(server)
        except (ConnectionError, OSError) as exc:  # o cliente sumiu no meio da conversa
            log.info("cliente %s caiu: %s", peer, exc)
        finally:
            server.client_left()
            log.info("cliente %s desconectou", peer)

    def serve(self, server: AggregatorTCPServer) -> None:
        while True:
            try:
                request, _ = protocolo.receive(self.rfile)
            except socket.timeout:
                self.reply({"status": "erro", "codigo": "TEMPO_ESGOTADO", "mensagem": "conexão encerrada por inatividade"})
                return
            except protocolo.ProtocolError as exc:
                self.reply({"status": "erro", "codigo": "MENSAGEM_INVALIDA", "mensagem": str(exc)})
                if str(exc).startswith("mensagem incompleta"):
                    return  # a linha não terminou (ou é grande demais): não dá para continuar lendo
                continue
            if request is None:  # o cliente fechou o socket
                return

            op = str(request.get("operacao", "")).strip().lower()
            try:
                response = {"operacao": op, **server.dispatch(request)}
            except RequestError as exc:
                response = {"operacao": op, "status": "erro", "codigo": exc.code, "mensagem": str(exc)}
            except Exception as exc:  # noqa: BLE001 — um erro interno não derruba o agregador
                log.exception("erro ao atender %s", request)
                response = {"operacao": op, "status": "erro", "codigo": "ERRO_INTERNO", "mensagem": str(exc)}
            if "id" in request:  # o cliente pode numerar os pedidos para casar com as respostas
                response["id"] = request["id"]
            self.reply(response)
            if op == "encerrar":
                return

    def reply(self, message: dict) -> None:
        protocolo.send(self.wfile, message)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Agregador (somente TCP, sem a parte web)")
    parser.add_argument("--port", type=int, default=config.AGGREGATOR_TCP_PORT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="[agregador] %(message)s")
    markets: list[MarketInfo] = list(MARKETS)
    with AggregatorTCPServer(Aggregator(markets), port=args.port) as server:
        log.info("escutando em tcp://%s:%d", config.AGGREGATOR_HOST, server.port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
