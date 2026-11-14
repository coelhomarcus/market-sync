"""Roda os experimentos obrigatórios e refaz tabelas e gráficos.

Uso (da raiz do projeto, com o start.py --silencioso rodando em outro terminal):
    .venv/bin/python -m experiments                # mede os 5 (cerca de 6 minutos) e analisa
    .venv/bin/python -m experiments --so 4 5       # mede só alguns e refaz a análise de todos
    .venv/bin/python -m experiments --analisar     # só refaz tabelas e gráficos a partir dos CSV
    .venv/bin/python -m experiments --rapido       # poucas rodadas, para testar

Cada experimento também roda sozinho, por exemplo:  .venv/bin/python -m experiments.exp3_latency
"""

import argparse
import sys

from . import all_experiments
from .shared import run

parser = argparse.ArgumentParser(description="Experimentos obrigatórios do trabalho")
parser.add_argument("--so", dest="only", nargs="+", type=int, choices=[1, 2, 3, 4, 5], help="mede só esses experimentos")
parser.add_argument("--rapido", dest="quick", action="store_true", help="menos rodadas, só para testar o script")
parser.add_argument("--analisar", dest="analyze_only", action="store_true",
                    help="não mede nada: só refaz tabelas e gráficos dos CSV")
args = parser.parse_args()

chosen = [exp for exp in all_experiments() if not args.only or exp.NUMBER in args.only]
sys.exit(run(chosen, quick=args.quick, measure=not args.analyze_only))
