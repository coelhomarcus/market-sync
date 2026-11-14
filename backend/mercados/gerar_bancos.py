"""Gera um banco SQLite independente para cada mercado (data/<id>.db).

Cada mercado recebe o catálogo comum (≈1.700 SKUs) com:
  * sortimento próprio: mercados menores deixam de vender parte dos SKUs;
  * preço = preço base da marca × perfil da loja × variação aleatória (±12%);
  * estoque aleatório (às vezes zerado) e um código de barras EAN-13 fictício.

O gerador usa semente fixa por mercado: rodar de novo produz os mesmos dados.
Uso:  python -m mercados.gerar_bancos
"""

from __future__ import annotations

import random
import sqlite3
from pathlib import Path

from comum.config import DATA_DIR, MARKETS, MarketInfo
from mercados.catalogo import CATALOG, search_text

SCHEMA = """
CREATE TABLE products (
    slug        TEXT PRIMARY KEY,
    ean         TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    brand       TEXT NOT NULL,
    category    TEXT NOT NULL,
    unit        TEXT NOT NULL,
    image       TEXT NOT NULL,
    price       REAL NOT NULL,
    stock       INTEGER NOT NULL,
    sort_order  INTEGER NOT NULL,
    search_text TEXT NOT NULL
);
CREATE INDEX idx_products_price ON products(price);
"""

# fração do catálogo que cada mercado NÃO vende (sortimento)
MISSING_CHANCE = {"aurora": 0.03, "supervila": 0.06, "emporio-sol": 0.15, "max-atacarejo": 0.10, "ipe": 0.22}


def market_price(value: float) -> float:
    """Arredonda para um preço "de mercado", terminando em ,x9."""
    return round(max(int(value * 10) / 10, 0.9) + 0.09, 2)


def fake_ean(rng: random.Random) -> str:
    digits = [7, 8, 9] + [rng.randint(0, 9) for _ in range(9)]  # 789 = prefixo GS1 Brasil
    check = (10 - sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits)) % 10) % 10
    return "".join(map(str, digits + [check]))


def is_ready(path: Path) -> bool:
    """O banco existe e não está vazio (um arquivo de 0 bytes não tem a tabela products)."""
    return path.exists() and path.stat().st_size > 0


def seed_market(market: MarketInfo, path: Path | None = None) -> int:
    """Cria o banco do mercado e devolve quantos produtos ele vende."""
    path = path or market.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)

    rng = random.Random(f"seed-{market.id}")
    eans: set[str] = set()
    rows = []
    for p in CATALOG:
        if rng.random() < MISSING_CHANCE.get(market.id, 0.1):
            continue
        price = market_price(p.base_price * market.price_factor * rng.uniform(0.88, 1.12))
        stock = 0 if rng.random() < 0.04 else rng.randint(3, 240)
        ean = fake_ean(random.Random(f"ean-{p.slug}"))
        while ean in eans:  # colisão improvável, mas o campo é UNIQUE
            ean = fake_ean(rng)
        eans.add(ean)
        rows.append((p.slug, ean, p.name, p.brand, p.category, p.unit, p.image, price, stock, p.order,
                     search_text(p.name, p.brand, p.category, p.unit, p.keywords)))

    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    conn.close()
    return len(rows)


def seed_all(data_dir: Path = DATA_DIR) -> None:
    for market in MARKETS:
        count = seed_market(market, data_dir / f"{market.id}.db")
        print(f"  {market.name:<16} {count:>5} produtos")


if __name__ == "__main__":
    print("Gerando bancos SQLite dos mercados:")
    seed_all()
