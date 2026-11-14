"""Sobe o sistema inteiro: 5 processos de mercado + o agregador, todos servidores TCP.

Uso (dentro de backend/):
    .venv/bin/python iniciar.py               # mostra cada pesquisa no terminal, ao vivo
    .venv/bin/python iniciar.py --raw         # versão crua: cada chamada TCP linha a linha, com as mensagens
    .venv/bin/python iniciar.py --silencioso  # sem o log das pesquisas (bom para os experimentos)
Ctrl+C encerra todos os processos.

Este terminal vira o painel ao vivo do agregador (agregador/registro.py): cada pesquisa
aparece como um quadro com uma barra por mercado. Cada mercado grava o próprio log em
logs/<mercado>.log (para ver: tail -f logs/aurora.log).
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time

from comum.config import BACKEND_DIR as BACKEND, MARKET_HOST, MARKETS
from mercados.gerar_bancos import is_ready, seed_all

LOGS = BACKEND / "logs"
ESPERA_PESQUISAS_S = 7  # no Ctrl+C, o agregador espera até isso as pesquisas em andamento (a mais longa: ~6 s)


def wait_port(port: int, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((MARKET_HOST, port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _interrupt(signum, frame):  # noqa: ARG001
    raise KeyboardInterrupt


def main() -> int:
    parser = argparse.ArgumentParser(description="Sobe os 5 mercados e o agregador")
    parser.add_argument("--raw", action="store_true", help="mostra cada chamada linha a linha, em vez do painel gráfico")
    parser.add_argument("--silencioso", action="store_true", help="não mostra o painel das pesquisas")
    args = parser.parse_args()

    # trata Ctrl+C, `kill` e fechar o terminal do mesmo jeito, mesmo se o SIGINT vier ignorado (processo em background)
    signal.signal(signal.SIGINT, _interrupt)
    signal.signal(signal.SIGTERM, _interrupt)
    signal.signal(signal.SIGHUP, _interrupt)

    if not all(is_ready(m.db_path) for m in MARKETS):
        print("Gerando bancos SQLite...")
        seed_all()

    procs: list[tuple[str, subprocess.Popen]] = []
    LOGS.mkdir(exist_ok=True)
    arquivos = []  # um log por mercado, para não misturar com o painel do agregador
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    if args.silencioso:
        env["SILENCIOSO"] = "1"
    if args.raw:
        env["PAINEL"] = "raw"
    try:
        for m in MARKETS:
            # modo gráfico: o log de cada mercado vai para um arquivo, para não bagunçar o painel;
            # modo raw: vai para este terminal, misturado ao do agregador (é o lado servidor de cada chamada)
            saida = None if args.raw else open(LOGS / f"{m.id}.log", "w", encoding="utf-8")
            if saida:
                arquivos.append(saida)
            # start_new_session: o Ctrl+C do terminal chega só ao iniciar.py, que encerra os filhos na ordem certa
            p = subprocess.Popen([sys.executable, "-m", "mercados.servidor", "--id", m.id], cwd=BACKEND, env=env,
                                 stdout=saida, stderr=subprocess.STDOUT if saida else None, start_new_session=True)
            procs.append((m.name, p))
        for m in MARKETS:
            ok = wait_port(m.port)
            print(f"  {'✔' if ok else '✘'} {m.name:<16} tcp://{MARKET_HOST}:{m.port}  latência {m.latency_ms} ms  "
                  f"(pid {dict(procs)[m.name].pid}{'' if args.raw else f', log em logs/{m.id}.log'})")

        print(f"\n  {'Painel desligado (--silencioso).' if args.silencioso else ('Modo raw: cada chamada aparece aqui embaixo, linha a linha.' if args.raw else 'As pesquisas aparecem aqui embaixo, ao vivo.')}"
              f"  Ctrl+C encerra tudo.", flush=True)
        agregador = subprocess.Popen([sys.executable, "-m", "agregador.servidor_tcp"], cwd=BACKEND, env=env,
                                     start_new_session=True)
        procs.append(("agregador", agregador))  # se não conseguir abrir a porta 5050, termina e o laço abaixo avisa

        while True:
            for name, p in procs:
                if p.poll() is not None:
                    print(f"processo '{name}' terminou com código {p.returncode}; encerrando tudo.")
                    return 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, signal.SIG_IGN)  # Ctrl+C repetido não interrompe a limpeza
        encerrar(procs)
        for log in arquivos:
            log.close()


def encerrar(procs: list[tuple[str, subprocess.Popen]]) -> None:
    """Primeiro o agregador (que termina as pesquisas em andamento), depois os mercados. Um sinal para cada."""
    agregador = [p for nome, p in procs if nome == "agregador"]
    mercados = [p for nome, p in procs if nome != "agregador"]
    if any(p.poll() is None for p in agregador):
        print("\n  Encerrando: esperando as pesquisas em andamento terminarem...", flush=True)
    parar(agregador, signal.SIGINT, ESPERA_PESQUISAS_S + 2)
    parar(mercados, signal.SIGINT, 3)
    print("  Agregador e mercados encerrados.", flush=True)


def parar(procs: list[subprocess.Popen], sig: int, espera_s: float) -> None:
    for p in procs:
        if p.poll() is None:
            p.send_signal(sig)
    for p in procs:
        try:
            p.wait(timeout=espera_s)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()


if __name__ == "__main__":
    sys.exit(main())
