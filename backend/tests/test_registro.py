"""O painel do terminal mostra a diferença entre os modos: escada no sequencial, barras juntas no concorrente."""

import pytest

from agregador import registro
from agregador.agregador import Aggregator

PAYLOAD = {"cmd": "SEARCH", "q": "arroz"}


@pytest.fixture
def quadros(monkeypatch):
    """Liga o painel e guarda cada pesquisa terminada (o que seria desenhado no terminal)."""
    monkeypatch.setattr(registro, "ATIVO", True)
    monkeypatch.setattr(registro, "_painel", registro.Painel())
    guardadas = []
    desenhar = registro.quadro

    def guardar(p, *args):
        guardadas.append(p)
        return desenhar(p, *args)

    monkeypatch.setattr(registro, "quadro", guardar)
    return guardadas


def colunas(p):
    """Coluna onde começa a barra de cada mercado, na régua do quadro."""
    escala = registro.escala_de(p.total_ms)
    return [registro.posicao_barra(c.inicio, c.fim, escala)[0] for c in p.linhas.values()]


def test_sequential_bars_form_a_staircase(market_cluster, quadros, capsys):
    _, markets = market_cluster
    Aggregator(markets).execute("sequential", "search", PAYLOAD, "arroz")
    (p,) = quadros
    linhas = list(p.linhas.values())
    for antes, depois in zip(linhas, linhas[1:]):
        assert depois.inicio >= antes.fim  # cada mercado só começa quando o anterior termina
    assert colunas(p) == sorted(colunas(p)) and colunas(p)[-1] > colunas(p)[0]
    assert {c.thread for c in linhas} == {"thread_1"} and p.threads == 1
    saida = capsys.readouterr().out
    assert "sequencial" in saida and "1 thread: a do próprio pedido" in saida and "5 de 5 mercados" in saida


def test_concurrent_bars_start_together(market_cluster, quadros, capsys):
    _, markets = market_cluster
    Aggregator(markets).execute("concurrent", "search", PAYLOAD, "arroz")
    (p,) = quadros
    assert colunas(p) == [0] * 5  # todas as conexões abrem juntas
    assert [c.thread for c in p.linhas.values()] == [f"thread_{n}" for n in range(1, 6)] and p.threads == 5
    assert all(c.thread_mercado.startswith("conexão nº ") for c in p.linhas.values())  # a thread que atendeu, do lado do mercado
    saida = capsys.readouterr().out
    assert "5 threads novas" in saida and "thread_5" in saida


def test_failure_and_retry_show_in_the_panel(market_cluster, quadros, capsys):
    servers, markets = market_cluster
    servers[0].market.configure({"online": False})
    Aggregator(markets).execute("concurrent", "search", PAYLOAD, "arroz")
    (p,) = quadros
    aurora = p.linhas[markets[0].id]
    assert aurora.estado == "erro" and aurora.tentativas == 4 and "fora do ar" in aurora.erro
    assert p.ok == 4 and p.erros == 1
    assert "4 de 5 mercados" in capsys.readouterr().out


def test_silent_mode_prints_nothing(market_cluster, monkeypatch, capsys):
    monkeypatch.setattr(registro, "ATIVO", False)
    _, markets = market_cluster
    Aggregator(markets).execute("concurrent", "search", PAYLOAD, "arroz")
    assert capsys.readouterr().out == ""


@pytest.fixture
def cru(monkeypatch):
    monkeypatch.setattr(registro, "ATIVO", True)
    monkeypatch.setattr(registro, "_painel", registro.Cru())


def test_raw_mode_shows_every_step_of_every_call(market_cluster, cru, capsys):
    _, markets = market_cluster
    Aggregator(markets).execute("concurrent", "search", PAYLOAD, "arroz")
    saida = capsys.readouterr().out
    for passo in ("connect", "envia", "recebe", "close"):
        assert saida.count(passo) == 5, passo  # cada passo, uma vez por mercado
    assert saida.count('{"cmd":"SEARCH","q":"arroz"}') == 5  # a mensagem exata que foi pelo socket
    assert "porta local" in saida and '"ok":true' in saida and "esperou" in saida
    assert all(f"thread_{n}" in saida for n in range(1, 6))


def test_raw_mode_shows_retries_and_empty_answer(market_cluster, cru, capsys):
    servers, markets = market_cluster
    servers[0].market.configure({"online": False})
    Aggregator(markets).execute("sequential", "search", PAYLOAD, "arroz")
    saida = capsys.readouterr().out
    assert "fechou a conexão sem responder" in saida
    assert saida.count("nova tentativa em") == 3 and "fora do ar (4 tentativas)" in saida
