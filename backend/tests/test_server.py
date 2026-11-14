import socket

from common.protocol import recv_msg, send_msg


def ask(port, payload):
    with socket.create_connection(("127.0.0.1", port), timeout=3) as s:
        send_msg(s, payload)
        return recv_msg(s)


def test_search_returns_products_sorted_by_price(market_cluster):
    servers, _ = market_cluster
    resp = ask(servers[0].port, {"cmd": "SEARCH", "q": "arroz"})
    assert resp["ok"]
    items = resp["data"]["items"]
    assert items and all("arroz" in i["name"].lower() for i in items)
    assert [i["price"] for i in items] == sorted(i["price"] for i in items)


def test_search_ignores_accents(market_cluster):
    servers, _ = market_cluster
    with_accent = ask(servers[0].port, {"cmd": "SEARCH", "q": "Feijão"})["data"]["items"]
    without = ask(servers[0].port, {"cmd": "SEARCH", "q": "feijao"})["data"]["items"]
    assert with_accent == without and len(with_accent) >= 20


def test_search_by_brand_and_size(market_cluster):
    servers, _ = market_cluster
    items = ask(servers[0].port, {"cmd": "SEARCH", "q": "arroz grao nobre 5 kg"})["data"]["items"]
    assert items and all(i["brand"] == "Grão Nobre" and i["unit"] == "5 kg" for i in items)


def test_empty_query_returns_whole_assortment(market_cluster):
    servers, _ = market_cluster
    items = ask(servers[0].port, {"cmd": "SEARCH", "q": ""})["data"]["items"]
    assert len(items) == servers[0].status()["products"] > 1000


def test_basket_total(market_cluster):
    servers, _ = market_cluster
    slug = ask(servers[0].port, {"cmd": "SEARCH", "q": "arroz"})["data"]["items"][0]["slug"]
    resp = ask(servers[0].port, {"cmd": "BASKET", "items": [{"slug": slug, "qty": 2}, {"slug": "nao-existe", "qty": 1}]})
    data = resp["data"]
    assert data["missing"] == ["nao-existe"]
    assert data["total"] == round(data["lines"][0]["price"] * 2, 2)


def test_history_ends_at_current_price(market_cluster):
    servers, _ = market_cluster
    item = ask(servers[0].port, {"cmd": "SEARCH", "q": "cafe"})["data"]["items"][0]
    points = ask(servers[0].port, {"cmd": "HISTORY", "slug": item["slug"], "days": 7})["data"]["points"]
    assert len(points) == 7
    assert [p["day"] for p in points] == sorted(p["day"] for p in points)
    assert points[-1]["price"] == item["price"]


def test_unknown_command_returns_error(market_cluster):
    servers, _ = market_cluster
    resp = ask(servers[0].port, {"cmd": "DANCE"})
    assert resp["ok"] is False and "desconhecido" in resp["error"]


def test_offline_market_closes_connection_but_accepts_admin(market_cluster):
    servers, _ = market_cluster
    port = servers[1].port
    assert ask(port, {"cmd": "CONFIG", "online": False})["data"]["online"] is False
    assert ask(port, {"cmd": "SEARCH", "q": "arroz"}) is None  # fechou sem responder
    assert ask(port, {"cmd": "STATUS"})["data"]["online"] is False


def test_each_market_has_its_own_prices(market_cluster):
    servers, _ = market_cluster
    prices = {
        s.market.id: ask(s.port, {"cmd": "SEARCH", "q": "arroz branco"})["data"]["items"][0]["price"]
        for s in servers
        if ask(s.port, {"cmd": "SEARCH", "q": "arroz branco"})["data"]["items"]
    }
    assert len(set(prices.values())) > 1
