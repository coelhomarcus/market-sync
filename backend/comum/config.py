"""Configuração do sistema: quais mercados existem, onde escutam e como o agregador se comporta."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent  # comum/ fica dentro de backend/
DATA_DIR = BACKEND_DIR / "data"

MARKET_HOST = os.environ.get("MARKET_HOST", "127.0.0.1")

# Agregador: porta TCP onde os clientes (pacotes cliente/ e experimentos/) fazem as pesquisas.
# A 5000 fica de fora porque no macOS ela é do AirPlay Receiver.
AGGREGATOR_HOST = os.environ.get("AGGREGATOR_HOST", "127.0.0.1")
AGGREGATOR_TCP_PORT = int(os.environ.get("AGGREGATOR_TCP_PORT", "5050"))
CLIENT_IDLE_TIMEOUT_S = 300.0  # o agregador encerra a conexão de um cliente parado há 5 min

# Cliente TCP do agregador
TCP_TIMEOUT_S = 3.0  # desiste de um mercado que demora mais de 3 s para responder
RETRIES = 3  # novas tentativas quando o mercado está fora do ar
RETRY_WAIT_S = 0.5  # espera antes da 1ª nova tentativa; dobra a cada vez (0,5 → 1 → 2 s)


@dataclass(frozen=True)
class MarketInfo:
    id: str
    name: str
    short: str  # nome curto, para gráficos
    port: int
    latency_ms: int  # latência simulada inicial
    price_factor: float  # perfil de preço da loja (atacarejo mais barato etc.)
    color: str

    @property
    def db_path(self) -> Path:
        return DATA_DIR / f"{self.id}.db"


MARKETS: list[MarketInfo] = [
    MarketInfo("aurora", "Mercado Aurora", "Aurora", 5001, 300, 1.00, "#16a34a"),
    MarketInfo("supervila", "SuperVila", "SuperVila", 5002, 500, 0.97, "#2563eb"),
    MarketInfo("emporio-sol", "Empório Sol", "Empório Sol", 5003, 700, 1.10, "#ea580c"),
    MarketInfo("max-atacarejo", "Max Atacarejo", "Max", 5004, 900, 0.88, "#9333ea"),
    MarketInfo("ipe", "Mercadinho Ipê", "Ipê", 5005, 1200, 1.04, "#db2777"),
]

MARKETS_BY_ID = {m.id: m for m in MARKETS}
