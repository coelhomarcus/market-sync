"""Sobe o sistema inteiro: 5 processos de mercado (TCP) + o agregador (HTTP/WS).

Uso (dentro de backend/):  .venv/bin/python run_all.py
Ctrl+C encerra todos os processos.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time

from config import BACKEND_DIR as BACKEND, MARKET_HOST, MARKETS
from markets.seed import is_ready, seed_all

API_PORT = int(os.environ.get("API_PORT", "8000"))


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
    # trata Ctrl+C e `kill` do mesmo jeito, mesmo se o SIGINT vier ignorado (processo em background)
    signal.signal(signal.SIGINT, _interrupt)
    signal.signal(signal.SIGTERM, _interrupt)

    if not all(is_ready(m.db_path) for m in MARKETS):
        print("Gerando bancos SQLite...")
        seed_all()

    procs: list[tuple[str, subprocess.Popen]] = []
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    try:
        for m in MARKETS:
            p = subprocess.Popen([sys.executable, "-m", "markets.server", "--id", m.id], cwd=BACKEND, env=env)
            procs.append((m.name, p))
        for m in MARKETS:
            ok = wait_port(m.port)
            print(f"  {'✔' if ok else '✘'} {m.name:<16} tcp://{MARKET_HOST}:{m.port}  latência {m.latency_ms} ms  (pid {dict(procs)[m.name].pid})")

        api = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "aggregator.main:app", "--host", "127.0.0.1", "--port", str(API_PORT),
             "--timeout-graceful-shutdown", "2"],
            cwd=BACKEND,
            env=env,
        )
        procs.append(("agregador", api))
        print(f"\n  Agregador em http://127.0.0.1:{API_PORT}  (docs: /docs)\n  Ctrl+C para encerrar.\n")

        while True:
            for name, p in procs:
                if p.poll() is not None:
                    print(f"processo '{name}' terminou com código {p.returncode}; encerrando tudo.")
                    return 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nEncerrando...")
        return 0
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)  # não interromper a limpeza
        for _, p in procs:
            if p.poll() is None:
                p.send_signal(signal.SIGINT)
        for _, p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    sys.exit(main())
