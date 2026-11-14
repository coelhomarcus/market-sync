"""Consultas ao banco SQLite de um mercado. Nada de rede aqui."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from markets.catalog import normalize


class MarketDatabase:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        # uma conexão por consulta: uma conexão SQLite não pode ser dividida entre threads
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def counts(self) -> tuple[int, int]:
        """(produtos, registros de preço histórico)."""
        with self._connect() as db:
            products = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            history = db.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
        return products, history

    def search(self, query: str) -> list[dict]:
        """Produtos cujo texto contém todas as palavras da busca, do mais barato ao mais caro."""
        words = normalize(query).split()
        sql = "SELECT slug, name, brand, category, unit, image, price, stock, sort_order FROM products"
        if words:
            sql += " WHERE " + " AND ".join("search_text LIKE ?" for _ in words)
        sql += " ORDER BY price"
        with self._connect() as db:
            return [dict(row) for row in db.execute(sql, [f"%{w}%" for w in words])]

    def basket(self, items: list[dict]) -> dict:
        """Preço de uma cesta: linhas com subtotal, itens que faltam e total."""
        lines, missing, total = [], [], 0.0
        with self._connect() as db:
            for item in items:
                slug, qty = str(item.get("slug", "")), max(1, int(item.get("qty", 1)))
                row = db.execute("SELECT name, brand, unit, price, stock FROM products WHERE slug = ?", (slug,)).fetchone()
                if row is None or row["stock"] <= 0:
                    missing.append(slug)
                    continue
                subtotal = round(row["price"] * qty, 2)
                total += subtotal
                lines.append({"slug": slug, "name": row["name"], "brand": row["brand"], "unit": row["unit"],
                              "qty": qty, "price": row["price"], "subtotal": subtotal})
        return {"lines": lines, "missing": missing, "total": round(total, 2)}

    def history(self, slug: str, days: int) -> list[dict]:
        """Preço diário dos últimos `days` dias, do mais antigo ao mais novo."""
        with self._connect() as db:
            rows = db.execute(
                "SELECT day, price FROM price_history WHERE slug = ? ORDER BY day DESC LIMIT ?",
                (slug, max(1, min(days, 365))),
            ).fetchall()
        return [{"day": r["day"], "price": r["price"]} for r in reversed(rows)]
