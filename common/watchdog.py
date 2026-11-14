"""Encerra este processo se o start.py morrer, para não sobrar servidor órfão segurando a porta.

O start.py sobe cada servidor numa sessão própria (assim o Ctrl+C do terminal chega só
a ele, que encerra tudo na ordem certa). O efeito colateral: se o start.py morrer sem
conseguir limpar (aba do terminal fechada, kill -9), os filhos continuariam rodando.
Esta thread confere a cada segundo se o pai ainda é o start.py; se não for, encerra o
processo como num Ctrl+C. Rodando um servidor sozinho (sem o start.py), não faz nada.
"""

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
