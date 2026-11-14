# market-sync — Comparador de Preços de Supermercados

Trabalho prático de Redes de Computadores e Sistemas Distribuídos: um agregador que consulta **5 supermercados independentes por sockets TCP** (cada um com seu banco SQLite de ~1.500 produtos e ~280 mil preços históricos), compara os preços e mostra, ao vivo, a diferença entre consultar os mercados **um por vez (sequencial)** e **todos ao mesmo tempo (concorrente, com threads)**.

```
React (loja + painel) ──HTTP──▶ FastAPI (agregador :8000) ──TCP──▶ 5 processos "mercado" (:5001–5005, SQLite próprio)
        ▲                                │
        └────────── WebSocket ◀── eventos e métricas
```

## Requisitos

- Python 3.12 (`/opt/homebrew/bin/python3.12` no macOS com Homebrew)
- Node.js 20 ou superior

## Como rodar

**1. Backend (uma vez):**

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**2. Subir os 5 mercados + o agregador** (gera os bancos SQLite na primeira vez, cerca de 4 s; para regerar: `.venv/bin/python -m markets.seed`):

```bash
cd backend && .venv/bin/python run_all.py
```

**3. Frontend em modo de desenvolvimento**, em outro terminal:

```bash
cd frontend && npm install && npm run dev
```

Abra http://localhost:5173. A documentação interativa da API fica em http://localhost:8000/docs.

**Alternativa sem Vite:** `cd frontend && npm run build` e reinicie o `run_all.py`; o agregador passa a servir o site em http://localhost:8000.

## O que mostrar na apresentação

1. **Loja:** busque "arroz" no modo Sequencial e depois no Concorrente (alternador no topo). A faixa abaixo da busca mostra o tempo e as barras de cada conexão TCP: escada no sequencial, barras paralelas no concorrente.
2. **Produto:** clique num produto para ver os mercados ordenados por preço e o selo "Menor preço".
3. **Cesta:** adicione itens e clique em "Comparar nos 5 mercados".
4. **Painel ao vivo:** speedup médio, linha do tempo da última consulta de cada modo, recursos (CPU e threads) e as consultas chegando por WebSocket.
5. **Falhas e retry:** na seção "Mercados" do painel, tire um mercado do ar. O agregador tenta de novo 3 vezes (esperando 0,5 s, 1 s e 2 s) antes de desistir: no sequencial essa espera trava a fila inteira (~3,5 s a mais); no concorrente ela acontece enquanto os outros mercados respondem. Latência acima de 3 s vira timeout (sem retry).
6. **Benchmark:** rode 5 ou 10 rodadas e exporte o CSV.
7. **Prova de que é TCP de verdade:** `lsof -nP -iTCP:5001-5005 -sTCP:LISTEN` lista os 5 processos Python escutando.

## Testes

```bash
cd backend && .venv/bin/python -m pytest
```

36 testes: protocolo (inclusive mensagem fragmentada), comandos do servidor (busca, cesta, histórico), concorrente mais rápido que sequencial, consultas sobrepostas em threads distintas, retry de mercado fora do ar (espera crescente, volta no meio, custo no sequencial), conexão recusada, timeout, rotas da API, WebSocket e medição de recursos.

## Estrutura

```
backend/
  config.py                 mercados, portas, timeout e retry
  protocol.py               protocolo TCP: uma mensagem JSON por linha
  markets/                  ── os 5 supermercados (um processo cada)
    server.py               servidor TCP: ThreadingTCPServer = uma thread por conexão
    database.py             consultas ao SQLite do mercado
    catalog.py              95 tipos × marcas × tamanhos = 1.740 SKUs
    seed.py                 gera data/<mercado>.db (produtos + 180 dias de histórico)
  aggregator/               ── o agregador (FastAPI, porta 8000)
    main.py                 rotas HTTP e WebSocket
    core.py                 executa a consulta no modo escolhido e mede
    strategies.py           sequential() e concurrent()  ← o coração do trabalho
    client.py               cliente TCP: pergunta a um mercado, com retry
    compare.py              menor preço, ordenação, cesta mais barata
    events.py, metrics.py   eventos ao vivo e histórico/CSV
  run_all.py                sobe tudo
  tests/
frontend/                   Vite + React + TypeScript + Tailwind + Recharts
scripts/fetch_images.py     baixa as fotos reais (Open Food Facts) para frontend/public/products
docs/                       requisitos, casos de uso, arquitetura, protocolo, experimentos
```

## Documentação

- [Requisitos e casos de uso](docs/requisitos.md)
- [Arquitetura e modelo de threads](docs/arquitetura.md)
- [Protocolo TCP](docs/protocolo.md)
- [Experimentos de desempenho](docs/experimentos.md)
- [Relatório técnico](docs/relatorio/) em DOCX, PDF e Markdown, com os dados de cada gráfico em `docs/relatorio/dados/`

## API

| Rota | Descrição |
|---|---|
| `GET /api/search/sequential?q=` | Consulta os mercados um de cada vez |
| `GET /api/search/concurrent?q=` | Consulta todos ao mesmo tempo |
| `GET /api/search/{mode}?q=&category=&sort=&page=` | Busca com filtro, ordenação e paginação |
| `GET /api/history/{slug}` | Histórico de preço do produto nos 5 mercados |
| `POST /api/basket/{mode}` | Total de uma cesta em cada mercado |
| `POST /api/benchmark` | Roda N vezes cada modo e devolve estatísticas |
| `GET /api/markets` | Estado de cada mercado (via comando STATUS por TCP) |
| `POST /api/markets/{id}/config` | Altera latência / online (comando CONFIG por TCP) |
| `GET /api/metrics/history` | Histórico de requisições |
| `GET /api/metrics/export.csv` | Histórico em CSV |
| `DELETE /api/metrics` | Zera as métricas |
| `WS /ws/events` | Eventos ao vivo |

## Créditos

Fotos dos produtos (uma por tipo, ilustrativa): Open Food Facts, Open Beauty Facts, Open Products Facts e Open Pet Food Facts (CC BY-SA), listadas em `frontend/public/products/CREDITS.md`. Os mercados, marcas, preços e estoques são fictícios.
