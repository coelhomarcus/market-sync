"""O painel do terminal mostra a diferença entre os modos: escada no sequencial, barras juntas no concorrente."""

import pytest

from aggregator import display
from aggregator.aggregator import Aggregator

PAYLOAD = {"cmd": "SEARCH", "q": "arroz"}


@pytest.fixture
def panels(monkeypatch):
    """Liga o painel e guarda cada pesquisa terminada (o que seria desenhado no terminal)."""
    monkeypatch.setattr(display, "ENABLED", True)
    monkeypatch.setattr(display, "_display", display.GraphicDisplay())
    stored = []
    draw = display.search_panel

    def store(p, *args):
        stored.append(p)
        return draw(p, *args)

    monkeypatch.setattr(display, "search_panel", store)
    return stored


def columns(p):
    """Coluna onde começa a barra de cada mercado, na régua do quadro."""
    scale = display.scale_for(p.total_ms)
    return [display.bar_position(c.start, c.end, scale)[0] for c in p.rows.values()]


def test_sequential_bars_form_a_staircase(market_cluster, panels, capsys):
    _, markets = market_cluster
    Aggregator(markets).execute("sequential", "search", PAYLOAD, "arroz")
    (p,) = panels
    rows = list(p.rows.values())
    for before, after in zip(rows, rows[1:]):
        assert after.start >= before.end  # cada mercado só começa quando o anterior termina
    assert columns(p) == sorted(columns(p)) and columns(p)[-1] > columns(p)[0]
    assert {c.thread for c in rows} == {"thread_1"} and p.threads == 1
    log_out = capsys.readouterr().out
    assert "sequencial" in log_out and "1 thread: a do próprio pedido" in log_out and "5 de 5 mercados" in log_out


def test_concurrent_bars_start_together(market_cluster, panels, capsys):
    _, markets = market_cluster
    Aggregator(markets).execute("concurrent", "search", PAYLOAD, "arroz")
    (p,) = panels
    assert columns(p) == [0] * 5  # todas as conexões abrem juntas
    assert [c.thread for c in p.rows.values()] == [f"thread_{n}" for n in range(1, 6)] and p.threads == 5
    assert all(c.market_thread.startswith("conexão nº ") for c in p.rows.values())  # a thread que atendeu, do lado do mercado
    log_out = capsys.readouterr().out
    assert "5 threads novas" in log_out and "thread_5" in log_out


def test_failure_and_retry_show_in_the_panel(market_cluster, panels, capsys):
    servers, markets = market_cluster
    servers[0].market.configure({"online": False})
    Aggregator(markets).execute("concurrent", "search", PAYLOAD, "arroz")
    (p,) = panels
    aurora = p.rows[markets[0].id]
    assert aurora.state == "erro" and aurora.attempts == 4 and "fora do ar" in aurora.error
    assert p.ok == 4 and p.errors == 1
    assert "4 de 5 mercados" in capsys.readouterr().out


def test_silent_mode_prints_nothing(market_cluster, monkeypatch, capsys):
    monkeypatch.setattr(display, "ENABLED", False)
    _, markets = market_cluster
    Aggregator(markets).execute("concurrent", "search", PAYLOAD, "arroz")
    assert capsys.readouterr().out == ""


@pytest.fixture
def raw(monkeypatch):
    monkeypatch.setattr(display, "ENABLED", True)
    monkeypatch.setattr(display, "_display", display.RawDisplay())


def test_raw_mode_shows_every_step_of_every_call(market_cluster, raw, capsys):
    _, markets = market_cluster
    Aggregator(markets).execute("concurrent", "search", PAYLOAD, "arroz")
    log_out = capsys.readouterr().out
    for step in ("CONNECT", "ENVIA", "RECEBE", "CLOSE"):
        assert log_out.count(step) == 5, step  # cada passo, uma vez por mercado
    assert log_out.count('{"cmd":"SEARCH","q":"arroz"}') == 5  # a mensagem exata que foi pelo socket
    assert "porta local" in log_out and '"ok":true' in log_out and "esperou" in log_out
    assert all(f"thread_{n}" in log_out for n in range(1, 6))


def test_raw_mode_shows_retries_and_empty_answer(market_cluster, raw, capsys):
    servers, markets = market_cluster
    servers[0].market.configure({"online": False})
    Aggregator(markets).execute("sequential", "search", PAYLOAD, "arroz")
    log_out = capsys.readouterr().out
    assert "fechou a conexão sem responder" in log_out
    assert log_out.count("nova tentativa em") == 3 and "fora do ar (4 tentativas)" in log_out
