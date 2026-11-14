"""Junta as respostas dos mercados: menor preço, ordenação e cesta mais barata.

Funções puras (sem rede): recebem a lista de MarketResult e montam o JSON da API.
"""

from __future__ import annotations

from markets.catalog import CATALOG

from .client import MarketResult

CATALOG_ORDER = {p.slug: i for i, p in enumerate(CATALOG)}
PAGE_SIZE = 40

SORT_KEYS = {
    "destaques": lambda p: p["order"],
    "preco": lambda p: (p["min_price"] is None, p["min_price"] or 0),
    "economia": lambda p: -p["savings"],
    "nome": lambda p: (p["name"], p["brand"], p["unit"]),
}


def merge_offers(results: list[MarketResult]) -> list[dict]:
    """Um produto por slug, com a oferta de cada mercado ordenada do menor ao maior preço."""
    products: dict[str, dict] = {}
    for r in results:
        if not r.ok:
            continue
        for item in r.data["items"]:
            p = products.setdefault(item["slug"], {
                "slug": item["slug"],
                "name": item["name"],
                "brand": item["brand"],
                "category": item["category"],
                "unit": item["unit"],
                "image": f"/products/{item['image']}.jpg",
                "order": item.get("sort_order", CATALOG_ORDER.get(item["slug"], 999_999)),
                "offers": [],
            })
            p["offers"].append({"market_id": r.market_id, "market_name": r.market_name, "price": item["price"],
                                "stock": item["stock"], "in_stock": item["stock"] > 0})

    for p in products.values():
        p["offers"].sort(key=lambda o: (not o["in_stock"], o["price"]))  # com estoque primeiro, depois por preço
        prices = [o["price"] for o in p["offers"] if o["in_stock"]]
        p["cheapest"] = p["offers"][0] if prices else None  # menor preço
        p["min_price"] = min(prices, default=None)
        p["max_price"] = max(prices, default=None)
        p["savings"] = round(max(prices) - min(prices), 2) if len(prices) > 1 else 0.0
    return list(products.values())


def search_response(results: list[MarketResult], record: dict, category: str, sort: str, page: int, page_size: int) -> dict:
    products = merge_offers(results)

    counts: dict[str, int] = {}
    for p in products:
        counts[p["category"]] = counts.get(p["category"], 0) + 1
    categories = [{"name": name, "count": n} for name, n in sorted(counts.items(), key=lambda kv: -kv[1])]

    listed = sorted((p for p in products if not category or p["category"] == category), key=SORT_KEYS[sort])
    pages = max(1, -(-len(listed) // page_size))
    page = max(1, min(page, pages))
    start = (page - 1) * page_size
    return {
        "request_id": record["request_id"],
        "mode": record["mode"],
        "query": record["query"],
        "category": category,
        "sort": sort,
        "total_ms": record["total_ms"],
        "products": listed[start : start + page_size],
        "total_products": len(listed),
        "total_offers": sum(len(p["offers"]) for p in products),
        "page": page,
        "pages": pages,
        "page_size": page_size,
        "categories": categories,
        "markets": record["markets"],
        "ok_count": record["ok_count"],
        "error_count": record["error_count"],
    }


def basket_response(wanted: dict[str, int], results: list[MarketResult], record: dict) -> dict:
    """Total da cesta em cada mercado; o mais barato é o de menor total entre os que têm tudo."""
    per_market = []
    for r in results:
        if r.ok:
            per_market.append({"market_id": r.market_id, "market_name": r.market_name, "ok": True,
                               "total": r.data["total"], "missing": r.data["missing"], "complete": not r.data["missing"]})
        else:
            per_market.append({"market_id": r.market_id, "market_name": r.market_name, "ok": False, "error": r.error})

    # primeiro quem respondeu e tem tudo, do menor total ao maior
    per_market.sort(key=lambda m: (not m["ok"], not m.get("complete"), m.get("total", 0)))
    cheapest = per_market[0] if per_market and per_market[0].get("complete") else None
    return {
        "request_id": record["request_id"],
        "mode": record["mode"],
        "total_ms": record["total_ms"],
        "items": wanted,
        "markets": per_market,
        "cheapest": cheapest,
        "timings": record["markets"],
    }
