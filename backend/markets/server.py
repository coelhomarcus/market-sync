"""Servidor TCP de um supermercado (um processo por mercado).

Implementado com a API de sockets "crua" do Python:
    socket() -> bind() -> listen() -> accept() -> recv()/send() -> close()

Cada conexão aceita é atendida por uma thread própria (threading.Thread), então
o mercado consegue atender várias requisições do agregador ao mesmo tempo.

Comandos (ver common/protocol.py para o formato):
    PING                                  -> estado do mercado (falha se offline)
    STATUS                                -> igual ao PING, mas responde mesmo offline
    SEARCH  {"q": "arroz"}                -> produtos que casam com a busca
    BASKET  {"items": [{"slug", "qty"}]}  -> preço da cesta neste mercado
    HISTORY {"slug": "...", "days": 90}   -> histórico diário de preço de um produto
    CONFIG  {"latency_ms": 800, "online": false} -> ajusta a simulação

Uso:  python -m markets.server --id aurora
"""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from contextlib import contextmanager
import logging
import random
import socket
import sqlite3
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import MARKET_HOST, MARKETS_BY_ID, MarketInfo  # noqa: E402
from common.protocol import ProtocolError, recv_msg, send_msg  # noqa: E402
from markets.catalog import normalize  # noqa: E402
from markets.seed import seed_market  # noqa: E402

log = logging.getLogger("market")

# comandos de administração continuam respondendo mesmo com o mercado "fora do ar"
ADMIN_COMMANDS = {"CONFIG", "STATUS"}


class MarketServer:
    def __init__(
        self,
        market: MarketInfo,
        host: str = MARKET_HOST,
        port: int | None = None,
        db_path: Path | None = None,
        latency_ms: int | None = None,
        jitter: float = 0.15,
    ) -> None:
        self.market = market
        self.host = host
        self.port = market.port if port is None else port
        self.db_path = db_path or market.db_path
        self.latency_ms = market.latency_ms if latency_ms is None else latency_ms
        self.jitter = jitter
        self.online = True
        self.requests_served = 0
        self._lock = threading.Lock()  # protege latency_ms / online / contadores
        self._sock: socket.socket | None = None
        self._stopping = threading.Event()

        if not Path(self.db_path).exists():
            seed_market(market, Path(self.db_path))
        with self._db() as db:  # números fixos do banco, lidos uma vez
            self._products = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            self._history_rows = db.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]

    # ------------------------------------------------------------------ rede
    def bind(self) -> int:
        """Cria o socket de escuta. Retorna a porta (útil com port=0 nos testes)."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(64)
        self._sock = sock
        self.port = sock.getsockname()[1]
        return self.port

    def serve_forever(self) -> None:
        if self._sock is None:
            self.bind()
        assert self._sock is not None
        log.info("%s escutando em %s:%d (latência %d ms)", self.market.name, self.host, self.port, self.latency_ms)
        while not self._stopping.is_set():
            try:
                conn, addr = self._sock.accept()  # bloqueia até chegar uma conexão
            except OSError:
                break  # socket fechado por shutdown()
            # uma thread por conexão: o accept() volta logo a esperar a próxima
            threading.Thread(target=self._handle_connection, args=(conn, addr), daemon=True).start()

    def start_in_thread(self) -> threading.Thread:
        self.bind()
        thread = threading.Thread(target=self.serve_forever, daemon=True)
        thread.start()
        return thread

    def shutdown(self) -> None:
        self._stopping.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass

    def _handle_connection(self, conn: socket.socket, addr: tuple) -> None:
        with conn:
            while True:
                try:
                    request = recv_msg(conn)
                except (ProtocolError, OSError) as exc:
                    log.warning("conexão %s: %s", addr, exc)
                    return
                if request is None:  # cliente fechou a conexão
                    return

                cmd = str(request.get("cmd", "")).upper()
                with self._lock:
                    online = self.online
                if not online and cmd not in ADMIN_COMMANDS:
                    # "fora do ar": encerra a conexão sem responder
                    log.info("offline: recusando %s de %s", cmd, addr)
                    return

                try:
                    response = {"ok": True, "data": self.dispatch(cmd, request)}
                except Exception as exc:  # erro de aplicação vira resposta de erro
                    response = {"ok": False, "error": str(exc)}
                try:
                    send_msg(conn, response)
                except OSError:
                    return

    # ------------------------------------------------------------- comandos
    def dispatch(self, cmd: str, request: dict) -> dict:
        if cmd in ("PING", "STATUS"):
            return self.status()
        if cmd == "CONFIG":
            return self.configure(request)
        if cmd == "SEARCH":
            self._simulate_latency()
            return self.search(str(request.get("q", "")))
        if cmd == "BASKET":
            self._simulate_latency()
            return self.basket(request.get("items") or [])
        if cmd == "HISTORY":
            self._simulate_latency()
            return self.history(str(request.get("slug", "")), int(request.get("days", 90)))
        raise ValueError(f"comando desconhecido: {cmd!r}")

    def _simulate_latency(self) -> None:
        with self._lock:
            base = self.latency_ms
            self.requests_served += 1
        if base > 0:
            time.sleep(base * random.uniform(1 - self.jitter, 1 + self.jitter) / 1000)

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        # uma conexão por requisição: sqlite3 não deve ser compartilhado entre threads
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def status(self) -> dict:
        with self._lock:
            return {
                "market": {"id": self.market.id, "name": self.market.name},
                "online": self.online,
                "latency_ms": self.latency_ms,
                "products": self._products,
                "history_rows": self._history_rows,
                "db_bytes": Path(self.db_path).stat().st_size,
                "requests_served": self.requests_served,
                "thread_count": threading.active_count(),
            }

    def configure(self, request: dict) -> dict:
        with self._lock:
            if "latency_ms" in request:
                self.latency_ms = max(0, min(10_000, int(request["latency_ms"])))
            if "online" in request:
                self.online = bool(request["online"])
        return self.status()

    def search(self, query: str) -> dict:
        terms = normalize(query).split()
        sql = "SELECT slug, name, brand, category, unit, image, price, stock, sort_order FROM products"
        params: list[str] = []
        if terms:
            sql += " WHERE " + " AND ".join("search_text LIKE ?" for _ in terms)
            params = [f"%{t}%" for t in terms]
        sql += " ORDER BY price"
        with self._db() as db:
            items = [dict(row) for row in db.execute(sql, params)]
        return {"market": {"id": self.market.id, "name": self.market.name}, "items": items}

    def basket(self, items: list[dict]) -> dict:
        wanted = {str(i["slug"]): max(1, int(i.get("qty", 1))) for i in items if i.get("slug")}
        lines, missing = [], []
        total = 0.0
        with self._db() as db:
            for slug, qty in wanted.items():
                row = db.execute("SELECT slug, name, brand, unit, price, stock FROM products WHERE slug = ?", (slug,)).fetchone()
                if row is None or row["stock"] <= 0:
                    missing.append(slug)
                    continue
                subtotal = round(row["price"] * qty, 2)
                total += subtotal
                lines.append({"slug": slug, "name": row["name"], "brand": row["brand"], "unit": row["unit"],
                              "qty": qty, "price": row["price"], "subtotal": subtotal})
        return {
            "market": {"id": self.market.id, "name": self.market.name},
            "lines": lines,
            "missing": missing,
            "total": round(total, 2),
        }


    def history(self, slug: str, days: int) -> dict:
        days = max(1, min(days, 365))
        with self._db() as db:
            rows = db.execute(
                "SELECT day, price FROM price_history WHERE slug = ? ORDER BY day DESC LIMIT ?", (slug, days)
            ).fetchall()
        return {
            "market": {"id": self.market.id, "name": self.market.name},
            "slug": slug,
            "points": [{"day": r["day"], "price": r["price"]} for r in reversed(rows)],
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor TCP de um supermercado")
    parser.add_argument("--id", required=True, choices=sorted(MARKETS_BY_ID))
    parser.add_argument("--host", default=MARKET_HOST)
    parser.add_argument("--port", type=int)
    parser.add_argument("--latency", type=int, help="latência simulada em ms")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format=f"[{args.id}] %(message)s")
    server = MarketServer(MARKETS_BY_ID[args.id], host=args.host, port=args.port, latency_ms=args.latency)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
