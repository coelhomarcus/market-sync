"""Interface de terminal do cliente: lê o que o usuário digita e mostra os preços.

Toda a conversa com o agregador passa por cliente/conexao.py (socket TCP).

Uso (dentro de backend/, com o iniciar.py rodando em outro terminal):
    .venv/bin/python -m cliente                          # modo interativo
    .venv/bin/python -m cliente arroz                    # uma pesquisa e sai
    .venv/bin/python -m cliente "arroz 5 kg" --modo sequencial
    .venv/bin/python -m cliente cafe --comparar 3        # sequencial × concorrente, 3 rodadas
    .venv/bin/python -m cliente arroz --json             # mostra o JSON cru da resposta
"""

from __future__ import annotations

import argparse
import json
import socket
import sys

from comum import config, protocolo

from .conexao import ClienteAgregador


# ---------------------------------------------------------------- apresentação no terminal

COR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if COR else text


def negrito(t: str) -> str: return _c("1", t)
def verde(t: str) -> str: return _c("32", t)
def vermelho(t: str) -> str: return _c("31", t)
def cinza(t: str) -> str: return _c("2", t)


def reais(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def ms(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v / 1000:.2f} s".replace(".", ",") if v >= 1000 else f"{v:.0f} ms"


def mostrar_mercados(mercados: list[dict]) -> None:
    largura = max(len(m["fonte"]) for m in mercados)
    for m in sorted(mercados, key=lambda m: m["inicio_ms"]):
        if m["status"] == "sucesso":
            extra = f"  {cinza(str(m['tentativas']) + 'ª tentativa')}" if m["tentativas"] > 1 else ""
            print(f"    {m['fonte']:<{largura}}  {verde('✔')} {ms(m['tempo_ms']):>8}{extra}")
        else:
            print(f"    {m['fonte']:<{largura}}  {vermelho('✘')} {ms(m['tempo_ms']):>8}  {vermelho(m['erro'])}")


def mostrar_consulta(r: dict) -> None:
    ok = sum(m["status"] == "sucesso" for m in r["mercados"])
    print()
    print(f"  {negrito(repr(r['produto']))} · modo {r['modo']} · {negrito(ms(r['tempo_total_ms']))} · "
          f"{ok}/{len(r['mercados'])} mercados responderam")
    mostrar_mercados(r["mercados"])
    if r["status"] == "erro":
        print(vermelho(f"\n  {r['mensagem']}\n"))
        return
    if not r["resultados"]:
        print("\n  Nenhum produto encontrado. Tente um termo mais simples (ex.: arroz, café, leite).\n")
        return
    mostrando = "o mais barato" if len(r["resultados"]) == 1 else f"os {len(r['resultados'])} mais baratos"
    print(cinza(f"\n  {r['produtos_encontrados']} produtos, {r['ofertas_encontradas']} ofertas. Mostrando {mostrando}:\n"))
    for i, p in enumerate(r["resultados"], 1):
        print(f"  {negrito(f'{i:>2}.')} {negrito(p['produto'])} · {p['marca']} · {p['unidade']}")
        menor = p["menor_preco"]["preco"] if p["menor_preco"] else None
        for o in p["ofertas"]:
            if o["status"] != "sucesso":
                print(cinza(f"       {o['fonte']:<16} {reais(o['preco']):>10}   sem estoque"))
            elif o["preco"] == menor:
                print(verde(f"     ★ {o['fonte']:<16} {reais(o['preco']):>10}   menor preço"))
            else:
                print(f"       {o['fonte']:<16} {reais(o['preco']):>10}   {cinza('+' + reais(o['preco'] - menor))}")
    print()


def mostrar_comparacao(r: dict) -> None:
    print()
    print(f"  {negrito(repr(r['produto']))} · {r['repeticoes']} rodada(s) em cada modo")
    for nome in ("sequencial", "concorrente"):
        d = r[nome]
        print(f"\n  {negrito(nome.capitalize())}: média {negrito(ms(d['tempo_medio_ms']))} "
              f"(mín. {ms(d['tempo_min_ms'])}, máx. {ms(d['tempo_max_ms'])})")
        mostrar_mercados(d["mercados"])
    if r["speedup"]:
        vezes = f"{r['speedup']:.2f}".replace(".", ",")
        print(f"\n  Speedup: {negrito(vezes + '×')} (sequencial ÷ concorrente)\n")


def mostrar_cesta(r: dict) -> None:
    print()
    print(f"  Cesta · modo {r['modo']} · {negrito(ms(r['tempo_total_ms']))}")
    for t in r["totais"]:
        if t["status"] != "sucesso":
            print(f"    {t['fonte']:<16} {vermelho('sem resposta: ' + t['erro'])}")
            continue
        n = len(t["faltando"])
        falta = cinza(f"  {'falta 1 item' if n == 1 else f'faltam {n} itens'}") if n else ""
        marca = verde("★ ") if r["mais_barato"] and t["fonte"] == r["mais_barato"]["fonte"] else "  "
        print(f"  {marca}{t['fonte']:<16} {reais(t['total']):>10}{falta}")
    if r["mais_barato"]:
        print(verde(f"\n  Mais barato: {r['mais_barato']['fonte']} ({reais(r['mais_barato']['total'])})\n"))
    else:
        print("\n  Nenhum mercado tem todos os itens.\n")


def mostrar_status(r: dict) -> None:
    print()
    for m in r["mercados"]:
        if not m["alcancavel"]:
            estado = vermelho(f"processo inacessível ({m['erro']})")
        elif not m["online"]:
            estado = vermelho("fora do ar")
        else:
            estado = verde("no ar") + f", latência {m['latencia_ms']} ms, {m['produtos']} produtos"
        print(f"    {m['id']:<14} {m['fonte']:<16} :{m['porta']}  {estado}")
    print(cinza(f"\n  Clientes TCP conectados ao agregador agora: {r['clientes_conectados']}\n"))


AJUDA = """
  Digite o nome de um produto para pesquisar (ex.: arroz, café 500 g, leite integral).

  /modo sequencial | concorrente   troca o modo das próximas pesquisas
  /comparar <produto> [rodadas]    mesma pesquisa nos dois modos, com speedup
  /cesta 1 3x2 5                   cesta com os itens da última lista (3x2 = item 3, 2 unidades)
  /mercados                        situação de cada supermercado
  /derrubar <id>  /religar <id>    tira um mercado do ar / traz de volta
  /latencia <id> <ms>              muda a latência simulada de um mercado
  /json                            liga/desliga a exibição do JSON cru
  /sair                            encerra a conexão
"""


def interativo(cliente: ClienteAgregador, modo: str, limite: int, cru: bool) -> None:
    print(negrito("\n  Comparador de Preços — cliente TCP"))
    print(f"  Conectado ao agregador em {cliente.host}:{cliente.port}. Modo: {modo}. /ajuda para os comandos.\n")
    ultima: list[dict] = []
    while True:
        try:
            linha = input(f"{modo}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not linha:
            continue
        cmd, _, resto = linha.partition(" ")
        resto = resto.strip()
        try:
            if cmd in ("/sair", "/q", "/exit"):
                return
            if cmd in ("/ajuda", "/help", "/?"):
                print(AJUDA)
                continue
            if cmd == "/json":
                cru = not cru
                print(f"  JSON cru {'ligado' if cru else 'desligado'}.")
                continue
            if cmd == "/modo":
                escolha = {"seq": "sequencial", "sequencial": "sequencial", "conc": "concorrente", "concorrente": "concorrente"}.get(resto)
                if not escolha:
                    print("  Use /modo sequencial ou /modo concorrente.")
                else:
                    modo = escolha
                continue

            if cmd == "/comparar":
                partes = resto.rsplit(" ", 1)  # "/comparar cafe 3": o número no fim é a quantidade de rodadas
                tem_rodadas = len(partes) == 2 and partes[1].isdigit()
                rodadas = int(partes[1]) if tem_rodadas else 1
                produto = partes[0] if tem_rodadas else resto
                r, mostrar = cliente.comparar(produto, rodadas), mostrar_comparacao
            elif cmd == "/cesta":
                itens = []
                for token in resto.split():
                    num, _, qtd = token.partition("x")
                    itens.append({"produto": ultima[int(num) - 1]["slug"], "quantidade": int(qtd or 1)})
                r, mostrar = cliente.cesta(itens, modo), mostrar_cesta
            elif cmd == "/mercados":
                r, mostrar = cliente.mercados(), mostrar_status
            elif cmd in ("/derrubar", "/religar"):
                r = cliente.configurar(resto, online=cmd == "/religar")
                mostrar = lambda r: print(f"  {r['fonte']}: {'no ar' if r['online'] else 'fora do ar'}.")  # noqa: E731
            elif cmd == "/latencia":
                mercado, valor = resto.split()
                r = cliente.configurar(mercado, latencia_ms=int(valor))
                mostrar = lambda r: print(f"  {r['fonte']}: latência {r['latencia_ms']} ms.")  # noqa: E731
            elif cmd.startswith("/"):
                print("  Comando desconhecido. /ajuda mostra a lista.")
                continue
            else:
                r, mostrar = cliente.consultar(linha, modo, limite), mostrar_consulta
                if r["status"] != "erro":
                    ultima = r["resultados"]
        except (ValueError, IndexError):
            print("  Não entendi. /ajuda mostra a forma de cada comando.")
            continue
        except (ConnectionError, protocolo.ProtocolError, socket.timeout) as exc:
            print(vermelho(f"  A conexão com o agregador caiu: {exc}"))
            return

        if cru:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        if r["status"] == "erro" and "codigo" in r and r["operacao"] != "consultar":
            print(vermelho(f"  Erro {r['codigo']}: {r['mensagem']}"))
        else:
            mostrar(r)


def main() -> int:
    parser = argparse.ArgumentParser(description="Cliente TCP do comparador de preços")
    parser.add_argument("produto", nargs="?", help="pesquisa única (sem isso, abre o modo interativo)")
    parser.add_argument("--modo", choices=["sequencial", "concorrente"], default="concorrente")
    parser.add_argument("--comparar", type=int, metavar="N", help="roda a pesquisa N vezes em cada modo e mostra o speedup")
    parser.add_argument("--limite", type=int, default=5, help="quantos produtos mostrar (padrão 5)")
    parser.add_argument("--json", action="store_true", help="mostra a resposta JSON crua")
    parser.add_argument("--host", default=config.AGGREGATOR_HOST)
    parser.add_argument("--port", type=int, default=config.AGGREGATOR_TCP_PORT)
    args = parser.parse_args()

    try:
        cliente = ClienteAgregador(args.host, args.port)
    except OSError as exc:
        print(f"Não consegui conectar ao agregador em {args.host}:{args.port}: {exc}\n"
              "Ele está rodando? (cd backend && .venv/bin/python iniciar.py)", file=sys.stderr)
        return 1

    with cliente:
        try:
            if args.produto is None:
                interativo(cliente, args.modo, args.limite, args.json)
                return 0
            if args.comparar:
                r, mostrar = cliente.comparar(args.produto, args.comparar), mostrar_comparacao
            else:
                r, mostrar = cliente.consultar(args.produto, args.modo, args.limite), mostrar_consulta
        except (ConnectionError, protocolo.ProtocolError, socket.timeout) as exc:
            print(f"A conexão com o agregador falhou: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        elif r["status"] == "erro" and r.get("codigo") != "NENHUM_MERCADO_RESPONDEU":
            print(f"Erro {r['codigo']}: {r['mensagem']}", file=sys.stderr)
            return 1
        else:
            mostrar(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
