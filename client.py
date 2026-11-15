#!/usr/bin/env python3.12
"""Abre o cliente de terminal (o mesmo que python3.12 -m client).

Uso: ./client.py [produto] [--mode seq|con] [--compare N] [--json]"""

import sys

from client.terminal import main  # o pacote client/ tem prioridade sobre este arquivo no import

sys.exit(main())
