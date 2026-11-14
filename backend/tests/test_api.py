import pytest
from fastapi.testclient import TestClient

from aggregator.main import create_app


@pytest.fixture
def client(market_cluster):
    _, markets = market_cluster
    with TestClient(create_app(markets)) as c:
        yield c


@pytest.mark.parametrize("mode", ["sequential", "concurrent"])
def test_search_orders_by_price_and_marks_cheapest(client, mode):
    data = client.get(f"/api/search/{mode}", params={"q": "arroz"}).json()
    assert data["mode"] == mode and data["ok_count"] == 5
    for p in data["products"]:
        prices = [o["price"] for o in p["offers"] if o["in_stock"]]
        assert prices == sorted(prices)
        assert p["cheapest"]["price"] == min(prices)
    mins = [p["min_price"] for p in data["products"]]
    assert mins == sorted(mins)


def test_invalid_mode_is_rejected(client):
    assert client.get("/api/search/paralelo?q=arroz").status_code == 422


def test_pagination_and_categories(client):
    first = client.get("/api/search/concurrent", params={"q": "", "page_size": 30}).json()
    assert len(first["products"]) == 30 and first["pages"] > 10
    assert sum(c["count"] for c in first["categories"]) == first["total_products"]
    second = client.get("/api/search/concurrent", params={"q": "", "page_size": 30, "page": 2}).json()
    assert {p["slug"] for p in first["products"]}.isdisjoint(p["slug"] for p in second["products"])
    bebidas = client.get("/api/search/concurrent", params={"q": "", "category": "Bebidas"}).json()
    assert bebidas["total_products"] == next(c["count"] for c in first["categories"] if c["name"] == "Bebidas")
    assert all(p["category"] == "Bebidas" for p in bebidas["products"])


def test_price_history_route(client):
    slug = client.get("/api/search/concurrent?q=feijao").json()["products"][0]["slug"]
    data = client.get(f"/api/history/{slug}", params={"days": 7}).json()
    assert len(data["markets"]) == 5
    assert any(len(m["points"]) == 7 for m in data["markets"])


def test_basket_finds_cheapest_market(client):
    search = client.get("/api/search/concurrent?q=arroz&sort=economia").json()["products"]
    body = {"items": [{"slug": search[0]["slug"], "qty": 1}, {"slug": search[1]["slug"], "qty": 2}]}
    data = client.post("/api/basket/concurrent", json=body).json()
    complete = [m for m in data["markets"] if m.get("complete")]
    assert data["cheapest"]["total"] == min(m["total"] for m in complete)
    assert data["best_mix"]["total"] <= data["cheapest"]["total"]


def test_market_config_and_metrics(client):
    r = client.post("/api/markets/aurora/config", json={"online": False}).json()
    assert r["online"] is False
    data = client.get("/api/search/concurrent?q=leite").json()
    assert data["error_count"] == 1
    hist = client.get("/api/metrics/history").json()
    assert hist["summary"]["requests"] == 1
    csv = client.get("/api/metrics/export.csv").text
    assert csv.splitlines()[0].startswith("id,timestamp,modo")
    assert len(csv.splitlines()) == 1 + 5
    assert "bytes_recebidos" in csv.splitlines()[0]


def test_benchmark_reports_speedup(client):
    data = client.post("/api/benchmark", json={"runs": 2, "q": "cafe"}).json()
    assert data["sequential"]["count"] == 2 and data["concurrent"]["count"] == 2
    assert data["speedup"] > 2


def test_websocket_streams_events(client):
    with client.websocket_connect("/ws/events") as ws:
        assert ws.receive_json()["type"] == "hello"
        client.get("/api/search/concurrent?q=arroz")
        types = []
        while not types or types[-1] != "request_end":
            types.append(ws.receive_json()["type"])
        assert types[0] == "request_start"
        assert types.count("market_response") == 5


def test_resources_are_measured(client):
    seq = client.get("/api/search/sequential?q=arroz")
    conc = client.get("/api/search/concurrent?q=arroz")
    assert seq.status_code == conc.status_code == 200
    records = client.get("/api/metrics/history").json()["records"]
    by_mode = {r["mode"]: r["resources"] for r in records}
    assert by_mode["concurrent"]["threads_extra"] >= 5  # uma thread por mercado
    assert by_mode["sequential"]["threads_extra"] <= 1  # a própria thread da rota
    for res in by_mode.values():
        assert res["server_cpu_ms"] > 0 and res["agg_cpu_ms"] >= 0 and res["rss_mb"] > 0
    assert all(m["server_cpu_ms"] > 0 for r in records for m in r["markets"])
