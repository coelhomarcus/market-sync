"""API HTTP do agregador (FastAPI).

As rotas de consulta são funções `def` (síncronas): o FastAPI as executa num pool
de threads, então as esperas de socket não travam o event loop que atende os
WebSockets do dashboard.

Rodar:  uvicorn aggregator.main:app --port 8000   (dentro de backend/)
"""

from __future__ import annotations

import asyncio
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, Field

from common.config import BACKEND_DIR, MARKETS, MarketInfo
from markets.catalog import CATALOG

CATALOG_ORDER = {p.slug: i for i, p in enumerate(CATALOG)}

from . import strategies
from .events import EventBus
from .metrics import MetricsStore, summarize
from .tcp_client import MarketResult, query_market

Mode = Literal["sequential", "concurrent"]
MODE_LABEL = {"sequential": "Sequencial", "concurrent": "Concorrente"}


class BasketItem(BaseModel):
    slug: str
    qty: int = Field(1, ge=1, le=99)


class BasketRequest(BaseModel):
    items: list[BasketItem] = Field(min_length=1, max_length=60)


class BenchmarkRequest(BaseModel):
    runs: int = Field(5, ge=1, le=30)
    q: str = "arroz"


class MarketConfig(BaseModel):
    latency_ms: int | None = Field(None, ge=0, le=10_000)
    online: bool | None = None


class Aggregator:
    """Estado da aplicação: mercados conhecidos, barramento de eventos e métricas."""

    def __init__(self, markets: list[MarketInfo]) -> None:
        self.markets = markets
        self.bus = EventBus()
        self.metrics = MetricsStore()

    def market(self, market_id: str) -> MarketInfo:
        for m in self.markets:
            if m.id == market_id:
                return m
        raise HTTPException(404, f"mercado desconhecido: {market_id}")

    def execute(self, mode: str, kind: str, payload: dict, query: str, source: str = "loja") -> tuple[list[MarketResult], float, dict]:
        request_id = uuid.uuid4().hex[:8]

        def emit(type_: str, data: dict) -> None:
            self.bus.publish(type_, {"request_id": request_id, "mode": mode, "kind": kind, **data})

        emit("request_start", {"query": query, "source": source, "markets": [m.id for m in self.markets]})
        t0 = time.perf_counter()
        results = strategies.run(mode, self.markets, payload, emit=emit, t0=t0)
        total_ms = (time.perf_counter() - t0) * 1000
        record = self.metrics.record(mode=mode, kind=kind, query=query, total_ms=total_ms, results=results, source=source)
        record["request_id"] = request_id
        emit("request_end", {"total_ms": record["total_ms"], "ok_count": record["ok_count"], "error_count": record["error_count"], "record": record})
        return results, total_ms, record


# ----------------------------------------------------------------- respostas

SORTS = ("destaques", "preco", "economia", "nome")
PAGE_SIZE = 40


def build_search_response(
    mode: str,
    query: str,
    results: list[MarketResult],
    total_ms: float,
    record: dict,
    category: str = "",
    sort: str = "preco",
    page: int = 1,
    page_size: int = PAGE_SIZE,
) -> dict:
    """Junta as ofertas de todos os mercados por produto, ordena e pagina.

    Os mercados devolvem TODOS os itens que casam com a busca; categoria, ordenação
    e paginação são feitas aqui, depois de conhecer o menor preço de cada produto.
    """
    products: dict[str, dict] = {}
    for r in results:
        if not r.ok:
            continue
        for item in r.data["items"]:
            p = products.setdefault(
                item["slug"],
                {
                    "slug": item["slug"],
                    "name": item["name"],
                    "brand": item.get("brand", ""),
                    "category": item["category"],
                    "unit": item["unit"],
                    "image": f"/products/{item.get('image', item['slug'])}.jpg",
                    "order": item.get("sort_order", CATALOG_ORDER.get(item["slug"], 999_999)),
                    "offers": [],
                },
            )
            p["offers"].append(
                {
                    "market_id": r.market_id,
                    "market_name": r.market_name,
                    "price": item["price"],
                    "stock": item["stock"],
                    "in_stock": item["stock"] > 0,
                }
            )

    for p in products.values():
        p["offers"].sort(key=lambda o: (not o["in_stock"], o["price"]))  # ordenação por preço
        available = [o for o in p["offers"] if o["in_stock"]]
        p["cheapest"] = available[0] if available else None  # menor preço
        prices = [o["price"] for o in available]
        p["min_price"] = min(prices) if prices else None
        p["max_price"] = max(prices) if prices else None
        p["savings"] = round(max(prices) - min(prices), 2) if len(prices) > 1 else 0.0

    counts: dict[str, int] = {}
    for p in products.values():
        counts[p["category"]] = counts.get(p["category"], 0) + 1
    categories = [{"name": name, "count": n} for name, n in sorted(counts.items(), key=lambda kv: -kv[1])]

    listed = [p for p in products.values() if not category or p["category"] == category]
    if sort == "destaques":
        listed.sort(key=lambda p: p["order"])
    elif sort == "economia":
        listed.sort(key=lambda p: -p["savings"])
    elif sort == "nome":
        listed.sort(key=lambda p: (p["name"], p["brand"], p["unit"]))
    else:  # preco
        listed.sort(key=lambda p: (p["min_price"] is None, p["min_price"] or 0))

    pages = max(1, -(-len(listed) // page_size))
    page = max(1, min(page, pages))
    start = (page - 1) * page_size
    return {
        "request_id": record["request_id"],
        "mode": mode,
        "query": query,
        "category": category,
        "sort": sort,
        "total_ms": round(total_ms, 2),
        "products": listed[start : start + page_size],
        "total_products": len(listed),
        "total_offers": sum(len(p["offers"]) for p in products.values()),
        "page": page,
        "pages": pages,
        "page_size": page_size,
        "categories": categories,
        "markets": record["markets"],
        "ok_count": record["ok_count"],
        "error_count": record["error_count"],
    }


def build_basket_response(mode: str, request: BasketRequest, results: list[MarketResult], total_ms: float, record: dict) -> dict:
    wanted = {i.slug: i.qty for i in request.items}
    per_market = []
    best_line: dict[str, dict] = {}
    for r in results:
        if not r.ok:
            per_market.append({"market_id": r.market_id, "market_name": r.market_name, "ok": False, "error": r.error})
            continue
        data = r.data
        per_market.append(
            {
                "market_id": r.market_id,
                "market_name": r.market_name,
                "ok": True,
                "total": data["total"],
                "lines": data["lines"],
                "missing": data["missing"],
                "complete": not data["missing"],
            }
        )
        for line in data["lines"]:
            current = best_line.get(line["slug"])
            if current is None or line["price"] < current["price"]:
                best_line[line["slug"]] = {**line, "market_id": r.market_id, "market_name": r.market_name}

    per_market.sort(key=lambda m: (not m["ok"], not m.get("complete", False), m.get("total", 0)))
    complete = [m for m in per_market if m.get("complete")]
    cheapest = complete[0] if complete else None
    mix_total = round(sum(line["subtotal"] for line in best_line.values()), 2)
    return {
        "request_id": record["request_id"],
        "mode": mode,
        "total_ms": round(total_ms, 2),
        "items": wanted,
        "markets": per_market,
        "cheapest": cheapest,
        "best_mix": {
            "total": mix_total,
            "lines": list(best_line.values()),
            "missing": [slug for slug in wanted if slug not in best_line],
            "savings_vs_cheapest": round(cheapest["total"] - mix_total, 2) if cheapest else None,
        },
        "timings": record["markets"],
    }


# ----------------------------------------------------------------------- app

class SPAStaticFiles(StaticFiles):
    """Serve o build do React; rotas do client-side router caem no index.html."""

    async def get_response(self, path: str, scope):  # type: ignore[override]
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or path.startswith(("api", "ws")):
                raise
            return await super().get_response("index.html", scope)


def create_app(markets: list[MarketInfo] | None = None) -> FastAPI:
    agg = Aggregator(list(markets or MARKETS))
    app = FastAPI(title="Comparador de Preços — Agregador", version="1.0.0")
    app.state.agg = agg
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/products")
    def list_catalog() -> list[dict]:
        return [
            {"slug": p.slug, "name": p.name, "brand": p.brand, "category": p.category, "unit": p.unit,
             "image": f"/products/{p.image}.jpg"}
            for p in CATALOG
        ]

    @app.get("/api/search/{mode}")
    def search(
        mode: Mode,
        q: str = "",
        category: str = "",
        sort: Literal["destaques", "preco", "economia", "nome"] = "preco",
        page: int = Query(1, ge=1),
        page_size: int = Query(PAGE_SIZE, ge=1, le=200),
    ) -> dict:
        query = q.strip()[:80]
        results, total_ms, record = agg.execute(mode, "search", {"cmd": "SEARCH", "q": query}, query)
        return build_search_response(mode, query, results, total_ms, record, category, sort, page, page_size)

    @app.get("/api/history/{slug}")
    def price_history(slug: str, days: int = Query(90, ge=7, le=180)) -> dict:
        """Histórico de preço de um produto em todos os mercados (consulta concorrente)."""
        payload = {"cmd": "HISTORY", "slug": slug, "days": days}
        results = strategies.concurrent(agg.markets, payload)
        return {
            "slug": slug,
            "days": days,
            "markets": [
                {"market_id": r.market_id, "market_name": r.market_name, "ok": r.ok, "error": r.error,
                 "points": (r.data or {}).get("points", []), "duration_ms": r.duration_ms}
                for r in sorted(results, key=lambda r: r.market_id)
            ],
        }

    @app.post("/api/basket/{mode}")
    def basket(mode: Mode, body: BasketRequest) -> dict:
        payload = {"cmd": "BASKET", "items": [i.model_dump() for i in body.items]}
        label = f"cesta ({len(body.items)} itens)"
        results, total_ms, record = agg.execute(mode, "basket", payload, label)
        return build_basket_response(mode, body, results, total_ms, record)

    @app.post("/api/benchmark")
    def benchmark(body: BenchmarkRequest) -> dict:
        query = body.q.strip()[:80]
        agg.bus.publish("benchmark_start", {"runs": body.runs, "query": query})
        records = []
        for i in range(body.runs):
            # alterna a ordem para não favorecer um modo (cache, aquecimento)
            order = strategies.MODES if i % 2 == 0 else tuple(reversed(strategies.MODES))
            for mode in order:
                _, _, record = agg.execute(mode, "search", {"cmd": "SEARCH", "q": query}, query, source="benchmark")
                records.append(record)
            agg.bus.publish("benchmark_progress", {"done": i + 1, "runs": body.runs})
        result = summarize(records)
        result["runs"] = body.runs
        result["query"] = query
        result["samples"] = [{"mode": r["mode"], "total_ms": r["total_ms"]} for r in records]
        agg.bus.publish("benchmark_end", {"result": result})
        return result

    def _status(market: MarketInfo, payload: dict) -> dict:
        r = query_market(market, payload, timeout=1.5)
        base = {"id": market.id, "name": market.name, "port": market.port, "color": market.color}
        if not r.ok:
            return {**base, "reachable": False, "online": False, "error": r.error, "rtt_ms": r.duration_ms}
        d = r.data
        return {
            **base,
            "reachable": True,
            "online": d["online"],
            "latency_ms": d["latency_ms"],
            "products": d["products"],
            "history_rows": d.get("history_rows", 0),
            "db_bytes": d.get("db_bytes", 0),
            "requests_served": d["requests_served"],
            "thread_count": d["thread_count"],
            "rtt_ms": r.duration_ms,
        }

    @app.get("/api/markets")
    def markets_status() -> list[dict]:
        with ThreadPoolExecutor(max_workers=len(agg.markets)) as pool:
            return list(pool.map(lambda m: _status(m, {"cmd": "STATUS"}), agg.markets))

    @app.post("/api/markets/{market_id}/config")
    def configure_market(market_id: str, body: MarketConfig) -> dict:
        market = agg.market(market_id)
        payload = {"cmd": "CONFIG", **body.model_dump(exclude_none=True)}
        status = _status(market, payload)
        if not status["reachable"]:
            raise HTTPException(502, f"{market.name} não respondeu: {status['error']}")
        agg.bus.publish("market_config", {"market": market.id, "online": status["online"], "latency_ms": status["latency_ms"]})
        return status

    @app.get("/api/metrics/history")
    def metrics_history(limit: int = 300) -> dict:
        records = agg.metrics.records(limit)
        return {"records": records, "summary": summarize(records)}

    @app.delete("/api/metrics")
    def metrics_reset() -> dict:
        agg.metrics.clear()
        agg.bus.publish("metrics_reset", {})
        return {"ok": True}

    @app.get("/api/metrics/export.csv", response_class=PlainTextResponse)
    def metrics_csv() -> PlainTextResponse:
        return PlainTextResponse(
            agg.metrics.to_csv(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="metricas-comparador.csv"'},
        )

    @app.websocket("/ws/events")
    async def events(ws: WebSocket) -> None:
        await ws.accept()
        sub_id, queue = agg.bus.subscribe()
        await ws.send_json({"type": "hello", "recent": list(agg.bus.recent)[-60:]})

        async def pump() -> None:
            while True:
                await ws.send_json(await queue.get())

        async def watch_disconnect() -> None:
            while True:
                await ws.receive_text()  # levanta WebSocketDisconnect quando o cliente sai

        tasks = [asyncio.create_task(pump()), asyncio.create_task(watch_disconnect())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except WebSocketDisconnect:
            pass
        finally:
            for t in tasks:
                t.cancel()
            agg.bus.unsubscribe(sub_id)

    # se o front já foi compilado (npm run build), o próprio agregador o serve
    dist = BACKEND_DIR.parent / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/", SPAStaticFiles(directory=dist, html=True), name="frontend")

    return app


app = create_app()
