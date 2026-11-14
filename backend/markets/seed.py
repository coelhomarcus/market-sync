"""Gera um banco SQLite independente para cada mercado (data/<id>.db).

Cada mercado recebe o catálogo comum (≈1.700 SKUs) com:
  * sortimento próprio: mercados menores deixam de vender parte dos SKUs;
  * preço = preço base da marca × perfil da loja × variação aleatória (±12%);
  * estoque aleatório (às vezes zerado) e um código de barras EAN-13 fictício;
  * histórico diário de preços dos últimos HISTORY_DAYS dias (≈300 mil linhas por mercado).

O gerador usa semente fixa por mercado: rodar de novo produz os mesmos dados.
Uso:  python -m markets.seed
"""

from __future__ import annotations

import random
import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path

from config import DATA_DIR, MARKETS, MarketInfo
from markets.catalog import CATALOG, search_text

HISTORY_DAYS = 180
# data de referência fixa: os dados ficam iguais em qualquer dia em que o seed rodar
REFERENCE_DAY = date(2026, 11, 13)

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
CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_products_price ON products(price);

CREATE TABLE price_history (
    slug  TEXT NOT NULL REFERENCES products(slug),
    day   TEXT NOT NULL,
    price REAL NOT NULL,
    PRIMARY KEY (slug, day)
) WITHOUT ROWID;
"""

# fração do catálogo que cada mercado NÃO vende (sortimento)
MISSING_CHANCE = {"aurora": 0.03, "supervila": 0.06, "emporio-sol": 0.15, "max-atacarejo": 0.10, "ipe": 0.22}


def _market_price(value: float) -> float:
    """Arredonda para um preço "de mercado", terminando em ,x9."""
    return round(max(int(value * 10) / 10, 0.9) + 0.09, 2)


def _ean(rng: random.Random) -> str:
    digits = [7, 8, 9] + [rng.randint(0, 9) for _ in range(9)]  # 789 = prefixo GS1 Brasil
    check = (10 - sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits)) % 10) % 10
    return "".join(map(str, digits + [check]))


def _history(rng: random.Random, current: float, days: int) -> list[tuple[str, float]]:
    """Passeio aleatório que termina exatamente no preço atual."""
    price = current * rng.uniform(0.9, 1.1)
    points = []
    for offset in range(days - 1, -1, -1):
        if offset == 0:
            price = current
        elif rng.random() < 0.12:  # remarcação em ~12% dos dias
            price = price * rng.uniform(0.93, 1.07)
            price += (current - price) * 0.15  # puxa de volta para o preço atual
        points.append(((REFERENCE_DAY - timedelta(days=offset)).isoformat(), _market_price(price) if offset else current))
    return points


def seed_market(market: MarketInfo, path: Path | None = None, history_days: int = HISTORY_DAYS) -> dict:
    path = path or market.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    rng = random.Random(f"seed-{market.id}")
    eans: set[str] = set()
    products, history = [], []
    for p in CATALOG:
        if rng.random() < MISSING_CHANCE.get(market.id, 0.1):
            continue
        price = _market_price(p.base_price * market.price_factor * rng.uniform(0.88, 1.12))
        stock = 0 if rng.random() < 0.04 else rng.randint(3, 240)
        ean = _ean(random.Random(f"ean-{p.slug}"))
        while ean in eans:  # colisão improvável, mas o campo é UNIQUE
            ean = _ean(rng)
        eans.add(ean)
        products.append(
            (p.slug, ean, p.name, p.brand, p.category, p.unit, p.image, price, stock, p.order,
             search_text(p.name, p.brand, p.category, p.unit, p.keywords))
        )
        history.extend((p.slug, day, value) for day, value in _history(rng, price, history_days))

    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        with conn:
            conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", products)
            conn.executemany("INSERT INTO price_history VALUES (?, ?, ?)", history)
        conn.execute("VACUUM")
    finally:
        conn.close()
    return {"products": len(products), "history": len(history), "bytes": path.stat().st_size}


def seed_all(data_dir: Path = DATA_DIR, history_days: int = HISTORY_DAYS) -> None:
    total = {"products": 0, "history": 0, "bytes": 0}
    for market in MARKETS:
        t = time.perf_counter()
        info = seed_market(market, data_dir / f"{market.id}.db", history_days)
        for k in total:
            total[k] += info[k]
        print(
            f"  {market.name:<16} {info['products']:>5} produtos  {info['history']:>8,} preços históricos"
            f"  {info['bytes'] / 1e6:5.1f} MB  ({time.perf_counter() - t:.1f} s)"
        )
    print(f"  {'Total':<16} {total['products']:>5} produtos  {total['history']:>8,} preços históricos  {total['bytes'] / 1e6:5.1f} MB")


if __name__ == "__main__":
    print(f"Gerando bancos SQLite dos mercados ({HISTORY_DAYS} dias de histórico):")
    seed_all()
