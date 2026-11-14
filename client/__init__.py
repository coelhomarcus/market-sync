"""① CLIENTE — o usuário pesquisa por aqui; fala com o agregador por socket TCP (porta 5050)."""

from .connection import AggregatorClient

__all__ = ["AggregatorClient"]
