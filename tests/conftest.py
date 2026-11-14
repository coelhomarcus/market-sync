import dataclasses
import importlib
import socket
import threading

import pytest

from aggregator import display
from common import config
from common.config import MARKETS
from tools.seed_databases import seed_market

TEST_LATENCIES = [100, 150, 200, 250, 300]


@pytest.fixture(autouse=True)
def fast_retry(monkeypatch):
    """Nos testes, as novas tentativas esperam 10 ms em vez de 0,5 s."""
    monkeypatch.setattr(config, "RETRY_WAIT_S", 0.01)


@pytest.fixture(autouse=True)
def quiet_display(monkeypatch):
    """O log das pesquisas fica desligado nos testes (test_display.py liga quando precisa)."""
    monkeypatch.setattr(display, "ENABLED", False)


@pytest.fixture(scope="session")
def market_dbs(tmp_path_factory):
    """Gera os 5 bancos uma única vez por execução dos testes."""
    folder = tmp_path_factory.mktemp("dbs")
    for market in MARKETS:
        seed_market(market, folder / f"{market.id}.db")
    return folder


@pytest.fixture
def market_cluster(market_dbs):
    """Sobe os 5 supermercados (cada um com o código da sua pasta) em threads, em portas livres."""
    servers, infos = [], []
    for info, latency in zip(MARKETS, TEST_LATENCIES):
        module = importlib.import_module(f"markets.{info.folder}.server")
        market = module.Market(database=market_dbs / f"{info.id}.db", latency_ms=latency, jitter=0.0)
        server = module.MarketServer(market, host="127.0.0.1", port=0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        infos.append(dataclasses.replace(info, port=server.port, latency_ms=latency))
    yield servers, infos
    for s in servers:
        s.shutdown()
        s.server_close()


@pytest.fixture
def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
