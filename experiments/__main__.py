"""Roda os 5 experimentos e refaz tabelas e gráficos (com o start.py --quiet no ar).

Uso: python3.12 -m experiments [--only 4 5] [--analyze] [--quick]"""

import argparse
import sys

from . import all_experiments
from .shared import run

parser = argparse.ArgumentParser(description="Experimentos obrigatórios do trabalho")
parser.add_argument("--only", nargs="+", type=int, choices=[1, 2, 3, 4, 5], help="mede só esses experimentos")
parser.add_argument("--quick", action="store_true", help="menos rodadas, só para testar o script")
parser.add_argument("--analyze", dest="analyze_only", action="store_true",
                    help="não mede nada: só refaz tabelas e gráficos dos CSV")
args = parser.parse_args()

chosen = [exp for exp in all_experiments() if not args.only or exp.NUMBER in args.only]
sys.exit(run(chosen, quick=args.quick, measure=not args.analyze_only))
