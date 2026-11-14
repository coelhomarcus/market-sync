import dataclasses
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import MARKETS  # noqa: E402
from markets.seed import seed_market  # noqa: E402
from markets.server import MarketServer  # noqa: E402

TEST_LATENCIES = [100, 150, 200, 250, 300]


@pytest.fixture(scope="session")
def market_dbs(tmp_path_factory):
    """Gera os 5 bancos uma única vez (histórico curto para a suíte ficar rápida)."""
    folder = tmp_path_factory.mktemp("dbs")
    for market in MARKETS:
        seed_market(market, folder / f"{market.id}.db", history_days=14)
    return folder


@pytest.fixture
def market_cluster(market_dbs):
    """Sobe os 5 mercados em threads, em portas livres, com os bancos de teste."""
    servers, infos = [], []
    for market, latency in zip(MARKETS, TEST_LATENCIES):
        db = market_dbs / f"{market.id}.db"
        server = MarketServer(market, port=0, db_path=db, latency_ms=latency, jitter=0.0)
        server.start_in_thread()
        servers.append(server)
        infos.append(dataclasses.replace(market, port=server.port, latency_ms=latency))
    yield servers, infos
    for s in servers:
        s.shutdown()


@pytest.fixture
def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
