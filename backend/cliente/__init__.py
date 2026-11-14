"""① CLIENTE — o usuário pesquisa por aqui; fala com o agregador por socket TCP (porta 5050)."""

from .conexao import ClienteAgregador

__all__ = ["ClienteAgregador"]
