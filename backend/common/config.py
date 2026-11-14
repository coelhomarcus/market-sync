"""Configuração compartilhada: quais mercados existem e onde escutam."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"

MARKET_HOST = os.environ.get("MARKET_HOST", "127.0.0.1")
TCP_TIMEOUT_S = float(os.environ.get("TCP_TIMEOUT_S", "3.0"))


@dataclass(frozen=True)
class MarketInfo:
    id: str
    name: str
    port: int
    latency_ms: int  # latência simulada inicial
    price_factor: float  # perfil de preço da loja (atacarejo mais barato etc.)
    color: str

    @property
    def db_path(self) -> Path:
        return DATA_DIR / f"{self.id}.db"


MARKETS: list[MarketInfo] = [
    MarketInfo("aurora", "Mercado Aurora", 5001, 300, 1.00, "#16a34a"),
    MarketInfo("supervila", "SuperVila", 5002, 500, 0.97, "#2563eb"),
    MarketInfo("emporio-sol", "Empório Sol", 5003, 700, 1.10, "#ea580c"),
    MarketInfo("max-atacarejo", "Max Atacarejo", 5004, 900, 0.88, "#9333ea"),
    MarketInfo("ipe", "Mercadinho Ipê", 5005, 1200, 1.04, "#db2777"),
]

MARKETS_BY_ID = {m.id: m for m in MARKETS}
