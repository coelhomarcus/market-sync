#!/usr/bin/env python3.12
"""Sobe o sistema inteiro: 5 supermercados + o agregador, cada um no seu processo.

Uso: ./start.py [--raw | --quiet]   (ou: python3.12 start.py)"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time

from common.config import MARKET_HOST, MARKETS, ROOT
from tools.seed_databases import is_ready, seed_all

LOGS_DIR = ROOT / "logs"
SEARCH_WAIT_S = 7  # no Ctrl+C, o agregador espera até isso as pesquisas em andamento (a mais longa: ~6 s)


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
    parser = argparse.ArgumentParser(description="Sobe os 5 supermercados e o agregador")
    parser.add_argument("--raw", action="store_true", help="mostra cada chamada linha a linha, em vez do painel gráfico")
    parser.add_argument("--quiet", action="store_true", help="não mostra o painel das pesquisas")
    args = parser.parse_args()

    # trata Ctrl+C, `kill` e fechar o terminal do mesmo jeito, mesmo se o SIGINT vier ignorado (processo em background)
    signal.signal(signal.SIGINT, _interrupt)
    signal.signal(signal.SIGTERM, _interrupt)
    signal.signal(signal.SIGHUP, _interrupt)

    if not all(is_ready(m.db_path) for m in MARKETS):
        print("Gerando os bancos SQLite dos markets...")
        seed_all()

    procs: list[tuple[str, subprocess.Popen]] = []
    LOGS_DIR.mkdir(exist_ok=True)
    log_files = []  # um log por mercado, para não misturar com o painel do agregador
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "LAUNCHER_PID": str(os.getpid())}  # common/watchdog.py
    if args.quiet:
        env["QUIET"] = "1"
    if args.raw:
        env["DISPLAY"] = "raw"
    try:
        for m in MARKETS:
            # modo gráfico: o log de cada mercado vai para um arquivo, para não bagunçar o painel;
            # modo raw: vai para este terminal, misturado ao do agregador (é o lado servidor de cada chamada)
            log_out = None if args.raw else open(LOGS_DIR / f"{m.id}.log", "w", encoding="utf-8")
            if log_out:
                log_files.append(log_out)
            # start_new_session: o Ctrl+C do terminal chega só ao start.py, que encerra os filhos na ordem certa
            p = subprocess.Popen([sys.executable, "-m", f"markets.{m.folder}"], cwd=ROOT, env=env,
                                 stdout=log_out, stderr=subprocess.STDOUT if log_out else None, start_new_session=True)
            procs.append((m.name, p))
        for m in MARKETS:
            ok = wait_port(m.port)
            print(f"  {'✔' if ok else '✘'} {m.name:<16} tcp://{MARKET_HOST}:{m.port}  latência {m.latency_ms} ms  "
                  f"(pid {dict(procs)[m.name].pid}{'' if args.raw else f', log em logs/{m.id}.log'})")

        print(f"\n  {'Painel desligado (--quiet).' if args.quiet else ('Modo raw: cada chamada aparece aqui embaixo, linha a linha.' if args.raw else 'As pesquisas aparecem aqui embaixo, ao vivo.')}"
              f"  Ctrl+C encerra tudo.", flush=True)
        aggregator = subprocess.Popen([sys.executable, "-m", "aggregator.tcp_server"], cwd=ROOT, env=env,
                                     start_new_session=True)
        procs.append(("agregador", aggregator))  # se não conseguir abrir a porta 5050, termina e o laço abaixo avisa

        while True:
            for name, p in procs:
                if p.poll() is not None:
                    notify(f"processo '{name}' terminou com código {p.returncode}; encerrando tudo.")
                    return 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, signal.SIG_IGN)  # Ctrl+C repetido não interrompe a limpeza
        # no painel gráfico quem avisa da espera é o próprio painel (um print aqui cairia no meio dele)
        shutdown(procs, announce=args.raw or args.quiet or not sys.stdout.isatty())
        for log in log_files:
            log.close()


def shutdown(procs: list[tuple[str, subprocess.Popen]], announce: bool = True) -> None:
    """Primeiro o agregador (que termina as pesquisas em andamento), depois os mercados. Um sinal para cada."""
    aggregator = [p for name, p in procs if name == "agregador"]
    markets = [p for name, p in procs if name != "agregador"]
    if announce and any(p.poll() is None for p in aggregator):
        notify("\n  Encerrando: esperando as pesquisas em andamento terminarem...")
    stop(aggregator, signal.SIGINT, SEARCH_WAIT_S + 2)
    stop(markets, signal.SIGINT, 3)
    notify("  Agregador e mercados encerrados.")


def notify(text: str) -> None:
    """print que não falha se o terminal já foi fechado (senão a limpeza pararia no meio)."""
    try:
        print(text, flush=True)
    except OSError:
        pass


def stop(procs: list[subprocess.Popen], sig: int, wait_s: float) -> None:
    for p in procs:
        if p.poll() is None:
            p.send_signal(sig)
    for p in procs:
        try:
            p.wait(timeout=wait_s)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()


if __name__ == "__main__":
    sys.exit(main())
