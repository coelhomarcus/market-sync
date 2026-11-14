"""Consultas ao banco SQLite do supermercado Mercado Aurora. Nada de rede aqui."""

from __future__ import annotations

import sqlite3
import unicodedata
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


def normalize(text: str) -> str:
    """Minúsculas e sem acento: "Feijão" e "feijao" casam na busca."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()


class MarketDatabase:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        # uma conexão por consulta: uma conexão SQLite não pode ser dividida entre threads.
        # Só leitura (mode=ro): se o arquivo sumir, dá erro em vez de criar um banco vazio.
        conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def count_products(self) -> int:
        """Quantos produtos o mercado vende."""
        with self._connect() as db:
            return db.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    def search(self, query: str) -> list[dict]:
        """Produtos cujo texto contém todas as palavras da busca, do mais barato ao mais caro."""
        words = normalize(query).split()
        sql = "SELECT slug, name, brand, category, unit, price, stock, sort_order FROM products"
        if words:
            sql += " WHERE " + " AND ".join("search_text LIKE ?" for _ in words)
        sql += " ORDER BY price"
        with self._connect() as db:
            return [dict(line) for line in db.execute(sql, [f"%{p}%" for p in words])]

    def basket(self, items: list[dict]) -> dict:
        """Preço de uma cesta: linhas com subtotal, itens que faltam e total."""
        rows, missing, total = [], [], 0.0
        with self._connect() as db:
            for item in items:
                slug, qty = str(item.get("slug", "")), max(1, int(item.get("qty", 1)))
                row = db.execute("SELECT name, brand, unit, price, stock FROM products WHERE slug = ?", (slug,)).fetchone()
                if row is None or row["stock"] <= 0:
                    missing.append(slug)
                    continue
                subtotal = round(row["price"] * qty, 2)
                total += subtotal
                rows.append({"slug": slug, "name": row["name"], "brand": row["brand"], "unit": row["unit"],
                               "qty": qty, "price": row["price"], "subtotal": subtotal})
        return {"lines": rows, "missing": missing, "total": round(total, 2)}
