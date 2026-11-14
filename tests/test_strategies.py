import dataclasses
import time

from common import config
from aggregator.market_query import query_market
from aggregator import concurrent, sequential

PAYLOAD = {"cmd": "SEARCH", "q": "arroz"}


def timed(fn, *args, **kwargs):
    t = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, (time.perf_counter() - t) * 1000


def test_concurrent_is_faster_than_sequential(market_cluster):
    _, markets = market_cluster
    seq, seq_ms = timed(sequential.search, markets, PAYLOAD)
    conc, conc_ms = timed(concurrent.search, markets, PAYLOAD)
    assert all(r.ok for r in seq + conc)
    assert seq_ms >= sum(m.latency_ms for m in markets) * 0.95  # sequencial ≈ soma (1000 ms)
    assert conc_ms < max(m.latency_ms for m in markets) + 250  # concorrente ≈ maior latência (300 ms)


def test_sequential_requests_do_not_overlap(market_cluster):
    _, markets = market_cluster
    results = sequential.search(markets, PAYLOAD)
    for prev, nxt in zip(results, results[1:]):
        assert nxt.start_ms >= prev.end_ms


def test_concurrent_requests_overlap_and_use_distinct_threads(market_cluster):
    _, markets = market_cluster
    results = concurrent.search(markets, PAYLOAD)
    assert max(r.start_ms for r in results) < min(r.end_ms for r in results)
    assert len({r.thread for r in results}) == len(markets)


def test_offline_market_is_retried_then_skipped(market_cluster):
    servers, markets = market_cluster
    servers[2].market.configure({"online": False})
    results = {r.market_id: r for r in concurrent.search(markets, PAYLOAD)}
    down = results[markets[2].id]
    assert not down.ok and down.attempts == config.RETRIES + 1 and "fora do ar" in down.error
    assert sum(r.ok for r in results.values()) == len(markets) - 1


def test_retry_succeeds_when_market_comes_back(market_cluster, monkeypatch):
    servers, markets = market_cluster
    monkeypatch.setattr(config, "RETRY_WAIT_S", 0.2)
    servers[0].market.configure({"online": False})

    def back_online(type_, data):
        if type_ == "market_retry":
            servers[0].market.configure({"online": True})

    r = query_market(markets[0], PAYLOAD, emit=back_online)
    assert r.ok and r.attempts == 2


def test_retry_waits_grow_and_cost_time_in_sequential(market_cluster, monkeypatch):
    servers, markets = market_cluster
    monkeypatch.setattr(config, "RETRY_WAIT_S", 0.1)  # 0,1 + 0,2 + 0,4 = 0,7 s de espera
    servers[0].market.configure({"online": False})
    waits = []
    _, seq_ms = timed(sequential.search, markets, PAYLOAD, emit=lambda t, d: t == "market_retry" and waits.append(d["wait_ms"]))
    _, conc_ms = timed(concurrent.search, markets, PAYLOAD)
    assert waits == [100, 200, 400]
    assert seq_ms > 700 + 900  # espera do retry + os outros 4 mercados, um depois do outro
    assert conc_ms < seq_ms / 2  # no concorrente, o retry acontece enquanto os outros respondem


def test_killed_market_gives_connection_refused(market_cluster, free_port):
    _, markets = market_cluster
    r = query_market(dataclasses.replace(markets[0], port=free_port), PAYLOAD)
    assert not r.ok and "recusada" in r.error and r.attempts == config.RETRIES + 1


def test_slow_market_times_out_without_retry(market_cluster):
    servers, markets = market_cluster
    servers[0].market.configure({"latency_ms": 1500})
    r = query_market(markets[0], PAYLOAD, timeout=0.5)
    assert not r.ok and "tempo esgotado" in r.error and r.attempts == 1
    assert r.duration_ms < 1000


def test_bytes_received_are_measured(market_cluster):
    _, markets = market_cluster
    small = query_market(markets[0], {"cmd": "SEARCH", "q": "arroz grao nobre"})
    big = query_market(markets[0], {"cmd": "SEARCH", "q": ""})
    assert 0 < small.bytes_received < big.bytes_received


def test_events_are_emitted(market_cluster):
    _, markets = market_cluster
    events = []
    concurrent.search(markets, PAYLOAD, emit=lambda t, d: events.append(t))
    assert events.count("market_connect") == len(markets)
    assert events.count("market_response") == len(markets)
