"""Encerra este processo se o start.py morrer, para não sobrar servidor órfão segurando a porta."""

from __future__ import annotations

import os
import signal
import threading
import time


def watch_launcher() -> None:
    parent_pid = os.environ.get("LAUNCHER_PID")
    if not parent_pid or not parent_pid.isdigit():
        return  # rodando sozinho: não há quem vigiar

    def watch() -> None:
        while os.getppid() == int(parent_pid):
            time.sleep(1)
        os.kill(os.getpid(), signal.SIGINT)  # o pai sumiu: encerra como num Ctrl+C

    threading.Thread(target=watch, name="vigia-do-iniciar", daemon=True).start()
