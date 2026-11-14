"""API HTTP do agregador (FastAPI): as rotas que o site chama.

Cada rota é uma função `def` comum: o FastAPI a executa numa thread própria, então
uma consulta lenta não trava as outras nem o WebSocket do painel.

Rodar:  uvicorn aggregator.main:app --port 8000   (dentro de backend/)
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import BACKEND_DIR, MARKETS, MarketInfo
from markets.catalog import CATALOG

from . import compare, strategies
from .client import query_market
from .core import Aggregator
from .metrics import summarize

Mode = Literal["sequential", "concurrent"]
Sort = Literal["destaques", "preco", "economia", "nome"]


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


def create_app(markets: list[MarketInfo] | None = None) -> FastAPI:
    agg = Aggregator(list(markets or MARKETS))
    app = FastAPI(title="Comparador de Preços — Agregador")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["*"], allow_headers=["*"])

    # ------------------------------------------------------------ loja

    @app.get("/api/search/{mode}")
    def search(mode: Mode, q: str = "", category: str = "", sort: Sort = "preco",
               page: int = Query(1, ge=1), page_size: int = Query(compare.PAGE_SIZE, ge=1, le=200)) -> dict:
        query = q.strip()[:80]
        results, record = agg.execute(mode, "search", {"cmd": "SEARCH", "q": query}, query)
        return compare.search_response(results, record, category, sort, page, page_size)

    @app.post("/api/basket/{mode}")
    def basket(mode: Mode, body: BasketRequest) -> dict:
        wanted = {i.slug: i.qty for i in body.items}
        payload = {"cmd": "BASKET", "items": [{"slug": s, "qty": q} for s, q in wanted.items()]}
        results, record = agg.execute(mode, "basket", payload, f"cesta ({len(wanted)} itens)")
        return compare.basket_response(wanted, results, record)

    @app.get("/api/history/{slug}")
    def price_history(slug: str, days: int = Query(90, ge=7, le=180)) -> dict:
        results = strategies.concurrent(agg.markets, {"cmd": "HISTORY", "slug": slug, "days": days})
        return {"slug": slug, "days": days, "markets": [
            {"market_id": r.market_id, "market_name": r.market_name, "ok": r.ok, "error": r.error,
             "points": (r.data or {}).get("points", [])}
            for r in results
        ]}

    @app.get("/api/products")
    def catalog() -> list[dict]:
        return [{"slug": p.slug, "name": p.name, "brand": p.brand, "category": p.category, "unit": p.unit,
                 "image": f"/products/{p.image}.jpg"} for p in CATALOG]

    # ------------------------------------------------------------ painel

    def market_status(market: MarketInfo, payload: dict) -> dict:
        r = query_market(market, payload, timeout=1.5, retries=0)  # o painel não espera retry
        info = {"id": market.id, "name": market.name, "port": market.port, "color": market.color}
        if not r.ok:
            return {**info, "reachable": False, "online": False, "error": r.error}
        return {**info, "reachable": True, **r.data}

    @app.get("/api/markets")
    def markets_status() -> list[dict]:
        with ThreadPoolExecutor(max_workers=len(agg.markets)) as pool:
            return list(pool.map(lambda m: market_status(m, {"cmd": "STATUS"}), agg.markets))

    @app.post("/api/markets/{market_id}/config")
    def configure_market(market_id: str, body: MarketConfig) -> dict:
        market = next((m for m in agg.markets if m.id == market_id), None)
        if market is None:
            raise HTTPException(404, f"mercado desconhecido: {market_id}")
        status = market_status(market, {"cmd": "CONFIG", **body.model_dump(exclude_none=True)})
        if not status["reachable"]:
            raise HTTPException(502, f"{market.name} não respondeu: {status['error']}")
        agg.events.publish("market_config", {"market": market.id, "online": status["online"], "latency_ms": status["latency_ms"]})
        return status

    @app.post("/api/benchmark")
    def benchmark(body: BenchmarkRequest) -> dict:
        """Repete a mesma busca nos dois modos, alternando a ordem a cada rodada."""
        query = body.q.strip()[:80]
        agg.events.publish("benchmark_start", {"runs": body.runs, "query": query})
        records = []
        for i in range(body.runs):
            for mode in strategies.MODES if i % 2 == 0 else reversed(strategies.MODES):
                records.append(agg.execute(mode, "search", {"cmd": "SEARCH", "q": query}, query, source="benchmark")[1])
            agg.events.publish("benchmark_progress", {"done": i + 1, "runs": body.runs})
        result = {**summarize(records), "runs": body.runs, "query": query}
        agg.events.publish("benchmark_end", {"result": result})
        return result

    @app.get("/api/metrics/history")
    def metrics_history(limit: int = 300) -> dict:
        records = agg.metrics.records(limit)
        return {"records": records, "summary": summarize(records)}

    @app.delete("/api/metrics")
    def metrics_reset() -> dict:
        agg.metrics.clear()
        agg.events.publish("metrics_reset", {})
        return {"ok": True}

    @app.get("/api/metrics/export.csv", response_class=PlainTextResponse)
    def metrics_csv() -> PlainTextResponse:
        return PlainTextResponse(agg.metrics.to_csv(), media_type="text/csv; charset=utf-8",
                                 headers={"Content-Disposition": 'attachment; filename="metricas-comparador.csv"'})

    @app.websocket("/ws/events")
    async def events(ws: WebSocket) -> None:
        """Empurra cada evento das consultas para o navegador, em tempo real."""
        await ws.accept()
        sub_id, queue = agg.events.subscribe()
        await ws.send_json({"type": "hello", "recent": list(agg.events.recent)[-60:]})

        async def forward() -> None:
            while True:
                await ws.send_json(await queue.get())

        async def wait_disconnect() -> None:
            while True:
                await ws.receive_text()  # levanta WebSocketDisconnect quando o navegador sai

        tasks = [asyncio.create_task(forward()), asyncio.create_task(wait_disconnect())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except WebSocketDisconnect:
            pass
        finally:
            for t in tasks:
                t.cancel()
            agg.events.unsubscribe(sub_id)

    # se o front já foi compilado (npm run build), o próprio agregador serve o site
    dist = BACKEND_DIR.parent / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/", SPAStaticFiles(directory=dist, html=True), name="frontend")
    return app


class SPAStaticFiles(StaticFiles):
    """Serve o build do React; endereços do roteador do site caem no index.html."""

    async def get_response(self, path: str, scope):  # type: ignore[override]
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or path.startswith(("api", "ws")):
                raise
            return await super().get_response("index.html", scope)


app = create_app()
