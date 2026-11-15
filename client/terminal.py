"""Interface de terminal do cliente: lê a pesquisa e mostra os preços.

Uso: .venv/bin/python -m client [produto] [--mode seq|con] [--compare N] [--json]"""

from __future__ import annotations

import argparse
import json
import socket
import sys

from common import config, protocol

from .connection import AggregatorClient


# ---------------------------------------------------------------- apresentação no terminal

USE_COLOR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


def bold(t: str) -> str: return _c("1", t)
def green(t: str) -> str: return _c("32", t)
def red(t: str) -> str: return _c("31", t)
def gray(t: str) -> str: return _c("2", t)


def brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def ms(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v / 1000:.2f} s".replace(".", ",") if v >= 1000 else f"{v:.0f} ms"


def show_markets(markets: list[dict]) -> None:
    width = max(len(m["fonte"]) for m in markets)
    for m in sorted(markets, key=lambda m: m["inicio_ms"]):
        if m["status"] == "sucesso":
            extra = f"  {gray(str(m['tentativas']) + 'ª tentativa')}" if m["tentativas"] > 1 else ""
            print(f"    {m['fonte']:<{width}}  {green('✔')} {ms(m['tempo_ms']):>8}{extra}")
        else:
            print(f"    {m['fonte']:<{width}}  {red('✘')} {ms(m['tempo_ms']):>8}  {red(m['erro'])}")


def show_search(r: dict) -> None:
    ok = sum(m["status"] == "sucesso" for m in r["mercados"])
    print()
    print(f"  {bold(repr(r['produto']))} · modo {r['modo']} · {bold(ms(r['tempo_total_ms']))} · "
          f"{ok}/{len(r['mercados'])} mercados responderam")
    show_markets(r["mercados"])
    if r["status"] == "erro":
        print(red(f"\n  {r['mensagem']}\n"))
        return
    if not r["resultados"]:
        print("\n  Nenhum produto encontrado. Tente um termo mais simples (ex.: arroz, café, leite).\n")
        return
    showing = "o mais barato" if len(r["resultados"]) == 1 else f"os {len(r['resultados'])} mais baratos"
    print(gray(f"\n  {r['produtos_encontrados']} produtos, {r['ofertas_encontradas']} ofertas. Mostrando {showing}:\n"))
    for i, p in enumerate(r["resultados"], 1):
        print(f"  {bold(f'{i:>2}.')} {bold(p['produto'])} · {p['marca']} · {p['unidade']}")
        lowest = p["menor_preco"]["preco"] if p["menor_preco"] else None
        for o in p["ofertas"]:
            if o["status"] != "sucesso":
                print(gray(f"       {o['fonte']:<16} {brl(o['preco']):>10}   sem estoque"))
            elif o["preco"] == lowest:
                print(green(f"     ★ {o['fonte']:<16} {brl(o['preco']):>10}   menor preço"))
            else:
                print(f"       {o['fonte']:<16} {brl(o['preco']):>10}   {gray('+' + brl(o['preco'] - lowest))}")
    print()


def show_comparison(r: dict) -> None:
    print()
    print(f"  {bold(repr(r['produto']))} · {r['repeticoes']} rodada(s) em cada modo")
    for name in ("sequencial", "concorrente"):
        d = r[name]
        print(f"\n  {bold(name.capitalize())}: média {bold(ms(d['tempo_medio_ms']))} "
              f"(mín. {ms(d['tempo_min_ms'])}, máx. {ms(d['tempo_max_ms'])})")
        show_markets(d["mercados"])
    if r["speedup"]:
        times_fmt = f"{r['speedup']:.2f}".replace(".", ",")
        print(f"\n  Speedup: {bold(times_fmt + '×')} (sequencial ÷ concorrente)\n")


def show_status(r: dict) -> None:
    print()
    for m in r["mercados"]:
        if not m["alcancavel"]:
            state = red(f"processo inacessível ({m['erro']})")
        elif not m["online"]:
            state = red("fora do ar")
        else:
            state = green("no ar") + f", latência {m['latencia_ms']} ms, {m['produtos']} produtos"
        print(f"    {m['id']:<14} {m['fonte']:<16} :{m['porta']}  {state}")
    print(gray(f"\n  Clientes TCP conectados ao agregador agora: {r['clientes_conectados']}\n"))


HELP = """
  Digite o nome de um produto para pesquisar (ex.: arroz, café 500 g, leite integral).

  /seq                             próximas pesquisas no modo sequencial
  /con                             próximas pesquisas no modo concorrente
  /compare <produto> [rodadas]     mesma pesquisa nos dois modos, com speedup
  /markets                         situação de cada supermercado
  /down <id>   /up <id>            tira um mercado do ar / traz de volta
  /latency <id> <ms>               muda a latência simulada de um mercado
  /json                            liga/desliga a exibição do JSON cru
  /help                            mostra esta lista
  /exit                            encerra a conexão
"""

MODES = {"seq": "sequencial", "con": "concorrente"}  # comando / flag → valor do campo "modo" do protocolo


def interactive(client: AggregatorClient, mode: str, limit: int, raw: bool) -> None:
    print(bold("\n  Comparador de Preços — cliente TCP"))
    print(f"  Conectado ao agregador em {client.host}:{client.port}. Modo: {mode}. /help para os comandos.\n")
    while True:
        try:
            line = input(f"{mode}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue
        cmd, _, rest = line.partition(" ")
        rest = rest.strip()
        try:
            if cmd in ("/exit", "/quit", "/q"):
                return
            if cmd in ("/help", "/?"):
                print(HELP)
                continue
            if cmd == "/json":
                raw = not raw
                print(f"  JSON cru {'ligado' if raw else 'desligado'}.")
                continue
            if cmd in ("/seq", "/con"):
                mode = MODES[cmd[1:]]
                print(f"  Modo {mode}.")
                continue

            if cmd == "/compare":
                parts = rest.rsplit(" ", 1)  # "/compare cafe 3": o número no fim é a quantidade de rodadas
                has_rounds = len(parts) == 2 and parts[1].isdigit()
                rounds = int(parts[1]) if has_rounds else 1
                product = parts[0] if has_rounds else rest
                r, show = client.compare(product, rounds), show_comparison
            elif cmd == "/markets":
                r, show = client.markets(), show_status
            elif cmd in ("/down", "/up"):
                r = client.configure(rest, online=cmd == "/up")
                show = lambda r: print(f"  {r['fonte']}: {'no ar' if r['online'] else 'fora do ar'}.")  # noqa: E731
            elif cmd == "/latency":
                market, value = rest.split()
                r = client.configure(market, latency_ms=int(value))
                show = lambda r: print(f"  {r['fonte']}: latência {r['latencia_ms']} ms.")  # noqa: E731
            elif cmd.startswith("/"):
                print("  Comando desconhecido. /help mostra a lista.")
                continue
            else:
                r, show = client.search(line, mode, limit), show_search
        except (ValueError, IndexError):
            print("  Não entendi. /help mostra a forma de cada comando.")
            continue
        except (ConnectionError, protocol.ProtocolError, socket.timeout) as exc:
            print(red(f"  A conexão com o agregador caiu: {exc}"))
            return

        if raw:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        if r["status"] == "erro" and "codigo" in r and r["operacao"] != "consultar":
            print(red(f"  Erro {r['codigo']}: {r['mensagem']}"))
        else:
            show(r)


def main() -> int:
    parser = argparse.ArgumentParser(description="Cliente TCP do comparador de preços")
    parser.add_argument("product", nargs="?", metavar="produto", help="pesquisa única (sem isso, abre o modo interativo)")
    parser.add_argument("--mode", choices=list(MODES), default="con", help="seq = sequencial, con = concorrente (padrão)")
    parser.add_argument("--compare", type=int, metavar="N", help="roda a pesquisa N vezes em cada modo e mostra o speedup")
    parser.add_argument("--limit", type=int, default=5, help="quantos produtos mostrar (padrão 5)")
    parser.add_argument("--json", action="store_true", help="mostra a resposta JSON crua")
    parser.add_argument("--host", default=config.AGGREGATOR_HOST)
    parser.add_argument("--port", type=int, default=config.AGGREGATOR_TCP_PORT)
    args = parser.parse_args()
    mode = MODES[args.mode]

    try:
        client = AggregatorClient(args.host, args.port)
    except OSError as exc:
        print(f"Não consegui conectar ao agregador em {args.host}:{args.port}: {exc}\n"
              "Ele está rodando? (.venv/bin/python start.py)", file=sys.stderr)
        return 1

    with client:
        try:
            if args.product is None:
                interactive(client, mode, args.limit, args.json)
                return 0
            if args.compare:
                r, show = client.compare(args.product, args.compare), show_comparison
            else:
                r, show = client.search(args.product, mode, args.limit), show_search
        except (ConnectionError, protocol.ProtocolError, socket.timeout) as exc:
            print(f"A conexão com o agregador falhou: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        elif r["status"] == "erro" and r.get("codigo") != "NENHUM_MERCADO_RESPONDEU":
            print(f"Erro {r['codigo']}: {r['mensagem']}", file=sys.stderr)
            return 1
        else:
            show(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
