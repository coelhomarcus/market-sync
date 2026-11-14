"""Cliente → agregador por TCP: protocolo do enunciado (operacao/produto), erros e vários clientes."""

import socket
import threading
import time

import pytest

from comum import protocolo
from agregador.agregador import Aggregator
from agregador.servidor_tcp import AggregatorTCPServer
from cliente.conexao import ClienteAgregador


@pytest.fixture
def agg_server(market_cluster):
    servers, markets = market_cluster
    server = AggregatorTCPServer(Aggregator(markets), host="127.0.0.1", port=0)
    server.start()
    yield server, servers
    server.stop()


@pytest.fixture
def cliente(agg_server):
    server, _ = agg_server
    with ClienteAgregador("127.0.0.1", server.port, timeout=10) as c:
        yield c


def raw_connection(server):
    sock = socket.create_connection(("127.0.0.1", server.port), timeout=5)
    return sock, sock.makefile("rwb")


@pytest.mark.parametrize("modo", ["sequencial", "concorrente"])
def test_consultar_returns_prices_sorted_with_cheapest(cliente, modo):
    r = cliente.consultar("arroz", modo, limite=8)
    assert r["status"] == "sucesso" and r["operacao"] == "consultar" and r["modo"] == modo
    assert len(r["resultados"]) == 8 and r["produtos_encontrados"] >= 8
    assert len(r["mercados"]) == 5 and all(m["status"] == "sucesso" for m in r["mercados"])
    menores = [p["menor_preco"]["preco"] for p in r["resultados"]]
    assert menores == sorted(menores)  # produtos do mais barato para o mais caro
    for p in r["resultados"]:
        precos = [o["preco"] for o in p["ofertas"] if o["status"] == "sucesso"]
        assert precos == sorted(precos)  # ofertas de cada produto, do menor para o maior
        assert p["menor_preco"]["preco"] == precos[0]
        assert {"fonte", "produto", "preco", "status"} <= set(p["ofertas"][0])  # formato do enunciado


def test_concurrent_is_faster_than_sequential_over_tcp(cliente):
    seq = cliente.consultar("cafe", "sequencial")["tempo_total_ms"]
    conc = cliente.consultar("cafe", "concorrente")["tempo_total_ms"]
    assert seq > 2 * conc  # latências de teste: soma 1000 ms × maior 300 ms


def test_comparar_reports_speedup(cliente):
    r = cliente.comparar("leite", repeticoes=2)
    assert r["status"] == "sucesso" and r["repeticoes"] == 2
    assert r["sequencial"]["mercados_ok"] == r["concorrente"]["mercados_ok"] == 5
    assert r["speedup"] > 2


def test_many_operations_on_one_connection_and_clean_close(agg_server):
    server, _ = agg_server
    sock, stream = raw_connection(server)
    with sock, stream:
        for i in range(3):
            protocolo.send(stream, {"operacao": "mercados", "id": i})
            resp, _ = protocolo.receive(stream)
            assert resp["status"] == "sucesso" and resp["id"] == i and len(resp["mercados"]) == 5
        protocolo.send(stream, {"operacao": "encerrar"})
        resp, _ = protocolo.receive(stream)
        assert resp == {"operacao": "encerrar", "status": "sucesso", "mensagem": "conexão encerrada"}
        assert protocolo.receive(stream) == (None, 0)  # o agregador fechou o socket


@pytest.mark.parametrize("pedido, codigo", [
    ({"operacao": "dancar"}, "OPERACAO_DESCONHECIDA"),
    ({"produto": "arroz"}, "OPERACAO_DESCONHECIDA"),
    ({"operacao": "consultar"}, "PARAMETRO_INVALIDO"),
    ({"operacao": "consultar", "produto": "  "}, "PARAMETRO_INVALIDO"),
    ({"operacao": "consultar", "produto": "arroz", "modo": "paralelo"}, "PARAMETRO_INVALIDO"),
    ({"operacao": "consultar", "produto": "arroz", "limite": 0}, "PARAMETRO_INVALIDO"),
    ({"operacao": "cesta", "itens": []}, "PARAMETRO_INVALIDO"),
    ({"operacao": "configurar", "mercado": "nao-existe", "online": False}, "MERCADO_DESCONHECIDO"),
])
def test_invalid_requests_get_error_codes(cliente, pedido, codigo):
    r = cliente.pedir(**pedido) if "operacao" in pedido else cliente.pedir("", **pedido)
    assert r["status"] == "erro" and r["codigo"] == codigo and r["mensagem"]


def test_invalid_json_gets_error_and_connection_survives(agg_server):
    server, _ = agg_server
    sock, stream = raw_connection(server)
    with sock, stream:
        stream.write(b"isto nao e json\n")
        stream.flush()
        resp, _ = protocolo.receive(stream)
        assert resp["status"] == "erro" and resp["codigo"] == "MENSAGEM_INVALIDA"
        protocolo.send(stream, {"operacao": "consultar", "produto": "leite"})
        resp, _ = protocolo.receive(stream)
        assert resp["status"] == "sucesso"


def test_cesta_finds_cheapest_market(cliente):
    produtos = cliente.consultar("arroz", limite=2)["resultados"]
    r = cliente.cesta([{"produto": produtos[0]["slug"], "quantidade": 2}, {"produto": produtos[1]["slug"]}])
    completas = [t for t in r["totais"] if t["completa"]]
    assert r["mais_barato"]["total"] == min(t["total"] for t in completas)
    assert r["totais"][0]["fonte"] == r["mais_barato"]["fonte"]


def test_offline_market_gives_partial_result(cliente):
    assert cliente.configurar("aurora", online=False)["online"] is False
    r = cliente.consultar("arroz")
    assert r["status"] == "parcial"
    aurora = next(m for m in r["mercados"] if m["id"] == "aurora")
    assert aurora["status"] == "erro" and "fora do ar" in aurora["erro"] and aurora["tentativas"] == 4
    assert all(o["fonte"] != "Mercado Aurora" for p in r["resultados"] for o in p["ofertas"])


def test_all_markets_down_is_an_error(cliente):
    for m in cliente.mercados()["mercados"]:
        cliente.configurar(m["id"], online=False)
    r = cliente.consultar("arroz")
    assert r["status"] == "erro" and r["codigo"] == "NENHUM_MERCADO_RESPONDEU" and r["resultados"] == []


def test_market_going_down_during_search(agg_server):
    """Experimento 5: o mercado cai com a consulta já em andamento."""
    server, markets = agg_server
    ipe = markets[4].market  # latência de teste: 300 ms
    threading.Timer(0.1, ipe.configure, args=[{"online": False}]).start()
    with ClienteAgregador("127.0.0.1", server.port, timeout=10) as c:
        r = c.consultar("arroz", "concorrente")
    caiu = next(m for m in r["mercados"] if m["id"] == markets[4].market.info.id)
    assert r["status"] == "parcial" and caiu["status"] == "erro" and "fora do ar" in caiu["erro"]
    assert sum(m["status"] == "sucesso" for m in r["mercados"]) == 4
    assert caiu["fim_ms"] < 300  # a conexão caiu na hora, sem esperar a latência inteira (retry de teste: 10 ms)


def test_many_clients_at_the_same_time(agg_server):
    """Experimento 4: vários clientes pesquisando ao mesmo tempo, cada um na sua conexão."""
    server, _ = agg_server
    n = 8
    barrier = threading.Barrier(n)
    results: list[dict] = []
    lock = threading.Lock()

    def one_client():
        with ClienteAgregador("127.0.0.1", server.port, timeout=10) as c:
            barrier.wait()
            r = c.consultar("arroz", "concorrente")
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
    with ClienteAgregador("127.0.0.1", server.port, timeout=10) as c:
        assert c.consultar("leite")["status"] == "sucesso"
    deadline = time.monotonic() + 2
    while server.clients_connected and time.monotonic() < deadline:
        time.sleep(0.02)
    assert server.clients_connected == 0
