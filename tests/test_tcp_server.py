"""Cliente → agregador por TCP: protocolo do enunciado (operacao/produto), erros e vários clientes."""

import socket
import threading
import time

import pytest

from common import protocol
from aggregator.aggregator import Aggregator
from aggregator.tcp_server import AggregatorTCPServer
from client.connection import AggregatorClient


@pytest.fixture
def agg_server(market_cluster):
    servers, markets = market_cluster
    server = AggregatorTCPServer(Aggregator(markets), host="127.0.0.1", port=0)
    server.start()
    yield server, servers
    server.stop()


@pytest.fixture
def client(agg_server):
    server, _ = agg_server
    with AggregatorClient("127.0.0.1", server.port, timeout=10) as c:
        yield c


def raw_connection(server):
    sock = socket.create_connection(("127.0.0.1", server.port), timeout=5)
    return sock, sock.makefile("rwb")


@pytest.mark.parametrize("mode", ["sequencial", "concorrente"])
def test_search_returns_prices_sorted_with_cheapest(client, mode):
    r = client.search("arroz", mode, limit=8)
    assert r["status"] == "sucesso" and r["operacao"] == "consultar" and r["modo"] == mode
    assert len(r["resultados"]) == 8 and r["produtos_encontrados"] >= 8
    assert len(r["mercados"]) == 5 and all(m["status"] == "sucesso" for m in r["mercados"])
    lowest_prices = [p["menor_preco"]["preco"] for p in r["resultados"]]
    assert lowest_prices == sorted(lowest_prices)  # produtos do mais barato para o mais caro
    for p in r["resultados"]:
        prices = [o["preco"] for o in p["ofertas"] if o["status"] == "sucesso"]
        assert prices == sorted(prices)  # ofertas de cada produto, do menor para o maior
        assert p["menor_preco"]["preco"] == prices[0]
        assert {"fonte", "produto", "preco", "status"} <= set(p["ofertas"][0])  # formato do enunciado


def test_concurrent_is_faster_than_sequential_over_tcp(client):
    seq = client.search("cafe", "sequencial")["tempo_total_ms"]
    conc = client.search("cafe", "concorrente")["tempo_total_ms"]
    assert seq > 2 * conc  # latências de teste: soma 1000 ms × maior 300 ms


def test_compare_reports_speedup(client):
    r = client.compare("leite", rounds=2)
    assert r["status"] == "sucesso" and r["repeticoes"] == 2
    assert r["sequencial"]["mercados_ok"] == r["concorrente"]["mercados_ok"] == 5
    assert r["speedup"] > 2


def test_many_operations_on_one_connection_and_clean_close(agg_server):
    server, _ = agg_server
    sock, stream = raw_connection(server)
    with sock, stream:
        for i in range(3):
            protocol.send(stream, {"operacao": "mercados", "id": i})
            resp, _ = protocol.receive(stream)
            assert resp["status"] == "sucesso" and resp["id"] == i and len(resp["mercados"]) == 5
        protocol.send(stream, {"operacao": "encerrar"})
        resp, _ = protocol.receive(stream)
        assert resp == {"operacao": "encerrar", "status": "sucesso", "mensagem": "conexão encerrada"}
        assert protocol.receive(stream) == (None, 0)  # o agregador fechou o socket


@pytest.mark.parametrize("message, code", [
    ({"operacao": "dancar"}, "OPERACAO_DESCONHECIDA"),
    ({"produto": "arroz"}, "OPERACAO_DESCONHECIDA"),
    ({"operacao": "consultar"}, "PARAMETRO_INVALIDO"),
    ({"operacao": "consultar", "produto": "  "}, "PARAMETRO_INVALIDO"),
    ({"operacao": "consultar", "produto": "arroz", "modo": "paralelo"}, "PARAMETRO_INVALIDO"),
    ({"operacao": "consultar", "produto": "arroz", "limite": 0}, "PARAMETRO_INVALIDO"),
    ({"operacao": "configurar", "mercado": "nao-existe", "online": False}, "MERCADO_DESCONHECIDO"),
])
def test_invalid_requests_get_error_codes(client, message, code):
    fields = dict(message)
    r = client.request(fields.pop("operacao", ""), fields)
    assert r["status"] == "erro" and r["codigo"] == code and r["mensagem"]


def test_invalid_json_gets_error_and_connection_survives(agg_server):
    server, _ = agg_server
    sock, stream = raw_connection(server)
    with sock, stream:
        stream.write(b"isto nao e json\n")
        stream.flush()
        resp, _ = protocol.receive(stream)
        assert resp["status"] == "erro" and resp["codigo"] == "MENSAGEM_INVALIDA"
        protocol.send(stream, {"operacao": "consultar", "produto": "leite"})
        resp, _ = protocol.receive(stream)
        assert resp["status"] == "sucesso"


def test_offline_market_gives_partial_result(client):
    assert client.configure("aurora", online=False)["online"] is False
    r = client.search("arroz")
    assert r["status"] == "parcial"
    aurora = next(m for m in r["mercados"] if m["id"] == "aurora")
    assert aurora["status"] == "erro" and "fora do ar" in aurora["erro"] and aurora["tentativas"] == 4
    assert all(o["fonte"] != "Mercado Aurora" for p in r["resultados"] for o in p["ofertas"])


def test_all_markets_down_is_an_error(client):
    for m in client.markets()["mercados"]:
        client.configure(m["id"], online=False)
    r = client.search("arroz")
    assert r["status"] == "erro" and r["codigo"] == "NENHUM_MERCADO_RESPONDEU" and r["resultados"] == []


def test_market_going_down_during_search(agg_server):
    """Experimento 5: o mercado cai com a consulta já em andamento."""
    server, markets = agg_server
    supervila = markets[1].market  # latência de teste: 150 ms
    threading.Timer(0.1, supervila.configure, args=[{"online": False}]).start()
    with AggregatorClient("127.0.0.1", server.port, timeout=10) as c:
        r = c.search("arroz", "concorrente")
    down = next(m for m in r["mercados"] if m["id"] == supervila.id)
    assert r["status"] == "parcial" and down["status"] == "erro" and "fora do ar" in down["erro"]
    assert sum(m["status"] == "sucesso" for m in r["mercados"]) == 4
    assert down["fim_ms"] < 300  # a conexão caiu na hora, sem esperar a latência inteira (retry de teste: 10 ms)


def test_many_clients_at_the_same_time(agg_server):
    """Experimento 4: vários clientes pesquisando ao mesmo tempo, cada um na sua conexão."""
    server, _ = agg_server
    n = 8
    barrier = threading.Barrier(n)
    results: list[dict] = []
    lock = threading.Lock()

    def one_client():
        with AggregatorClient("127.0.0.1", server.port, timeout=10) as c:
            barrier.wait()
            r = c.search("arroz", "concorrente")
            with lock:
                results.append(r)

    t0 = time.perf_counter()
    threads = [threading.Thread(target=one_client) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall_ms = (time.perf_counter() - t0) * 1000
    assert len(results) == n and all(r["status"] == "sucesso" for r in results)
    assert wall_ms < 300 * 3  # 8 clientes juntos levam perto do tempo de um só (≈ 300 ms), não 8×
    assert server.clients_served == n


def test_abrupt_disconnect_does_not_hurt_the_server(agg_server):
    server, _ = agg_server
    sock, stream = raw_connection(server)
    stream.write(b'{"operacao": "consul')  # metade de uma mensagem e some
    stream.flush()
    stream.close()
    sock.close()
    with AggregatorClient("127.0.0.1", server.port, timeout=10) as c:
        assert c.search("leite")["status"] == "sucesso"
    deadline = time.monotonic() + 2
    while server.clients_connected and time.monotonic() < deadline:
        time.sleep(0.02)
    assert server.clients_connected == 0


def test_shutdown_waits_for_searches_in_progress(agg_server):
    """No Ctrl+C o agregador para de aceitar clientes, mas quem já pediu recebe a resposta."""
    server, _ = agg_server
    responses = []

    def run_search():
        with AggregatorClient("127.0.0.1", server.port, timeout=10) as c:
            responses.append(c.search("arroz", "sequencial"))  # ~1 s com as latências de teste

    t = threading.Thread(target=run_search)
    t.start()
    deadline = time.monotonic() + 3
    while server._in_progress == 0 and time.monotonic() < deadline:  # espera a pesquisa começar
        time.sleep(0.01)
    assert server._in_progress == 1
    start = time.monotonic()
    assert server.wait_for_requests(5) is True  # o que o main() faz no Ctrl+C
    assert 0.3 < time.monotonic() - start < 3  # esperou a pesquisa, não saiu na hora
    t.join()
    assert responses and responses[0]["status"] == "sucesso"
