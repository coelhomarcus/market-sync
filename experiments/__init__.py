"""Os 5 experimentos obrigatórios do enunciado (seção 9), um por arquivo.

    exp1_sequential.py        Experimento 1  consulta sequencial
    exp2_concurrent.py        Experimento 2  consulta concorrente (e a comparação com o 1)
    exp3_latency.py           Experimento 3  simulação de latência
    exp4_multiple_clients.py  Experimento 4  múltiplos clientes
    exp5_unavailability.py    Experimento 5  indisponibilidade de serviço
    shared.py                 o que todos compartilham

Tudo passa pelo caminho real: cliente --TCP--> agregador --TCP--> 5 supermercados.
"""

MODULES = ["exp1_sequential", "exp2_concurrent", "exp3_latency", "exp4_multiple_clients", "exp5_unavailability"]


def all_experiments() -> list:
    """Os 5 módulos, importados só quando usados (assim cada um também roda sozinho com python -m)."""
    import importlib

    return [importlib.import_module(f"{__name__}.{name}") for name in MODULES]
