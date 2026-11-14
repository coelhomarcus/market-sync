import dataclasses
import time

from aggregator.strategies import concurrent, sequential
from aggregator.tcp_client import query_market

PAYLOAD = {"cmd": "SEARCH", "q": "arroz"}


def test_concurrent_is_faster_than_sequential(market_cluster):
    _, markets = market_cluster
    t = time.perf_counter()
    seq = sequential(markets, PAYLOAD)
    seq_ms = (time.perf_counter() - t) * 1000

    t = time.perf_counter()
    conc = concurrent(markets, PAYLOAD)
    conc_ms = (time.perf_counter() - t) * 1000

    assert all(r.ok for r in seq + conc)
    total_latency = sum(m.latency_ms for m in markets)  # 1000 ms
    max_latency = max(m.latency_ms for m in markets)  # 300 ms
    assert seq_ms >= total_latency * 0.95  # sequencial ~ soma
    assert conc_ms < max_latency + 250  # concorrente ~ maior latência
    assert conc_ms < seq_ms / 2


def test_sequential_requests_do_not_overlap(market_cluster):
    _, markets = market_cluster
    results = sequential(markets, PAYLOAD)
    for prev, nxt in zip(results, results[1:]):
        assert nxt.start_ms >= prev.end_ms


def test_concurrent_requests_overlap_and_use_distinct_threads(market_cluster):
    _, markets = market_cluster
    results = concurrent(markets, PAYLOAD)
    assert max(r.start_ms for r in results) < min(r.end_ms for r in results)
    assert len({r.thread for r in results}) == len(markets)


def test_offline_market_does_not_break_concurrent_query(market_cluster):
    servers, markets = market_cluster
    servers[2].configure({"online": False})
    results = concurrent(markets, PAYLOAD)
    by_id = {r.market_id: r for r in results}
    assert not by_id[markets[2].id].ok
    assert sum(r.ok for r in results) == len(markets) - 1


def test_killed_market_gives_connection_refused(market_cluster, free_port):
    _, markets = market_cluster
    dead = dataclasses.replace(markets[0], port=free_port)
    r = query_market(dead, PAYLOAD)
    assert not r.ok and "recusada" in r.error


def test_slow_market_times_out(market_cluster):
    servers, markets = market_cluster
    servers[0].configure({"latency_ms": 1500})
    r = query_market(markets[0], PAYLOAD, timeout=0.5)
    assert not r.ok and "tempo esgotado" in r.error
    assert r.duration_ms < 1000


def test_bytes_received_are_measured(market_cluster):
    _, markets = market_cluster
    small = query_market(markets[0], {"cmd": "SEARCH", "q": "arroz grao nobre"})
    big = query_market(markets[0], {"cmd": "SEARCH", "q": ""})
    assert 0 < small.bytes_received < big.bytes_received


def test_events_are_emitted(market_cluster):
    _, markets = market_cluster
    events = []
    concurrent(markets, PAYLOAD, emit=lambda t, d: events.append((t, d["market"])))
    assert sum(1 for t, _ in events if t == "market_connect") == len(markets)
    assert sum(1 for t, _ in events if t == "market_response") == len(markets)
