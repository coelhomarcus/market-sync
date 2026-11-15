"""Os 5 experimentos do enunciado (seção 9), um por arquivo: exp1_… a exp5_…."""

MODULES = ["exp1_sequential", "exp2_concurrent", "exp3_latency", "exp4_multiple_clients", "exp5_unavailability"]


def all_experiments() -> list:
    """Os 5 módulos, importados só quando usados (assim cada um também roda sozinho com python -m)."""
    import importlib

    return [importlib.import_module(f"{__name__}.{name}") for name in MODULES]
