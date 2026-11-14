# market-sync — Comparador de Preços de Supermercados

Trabalho 1 de Sistemas Distribuídos (Tema 1): um agregador que consulta **5 supermercados independentes por sockets TCP** (cada um com seu banco SQLite de ~1.500 produtos), compara os preços e mostra a diferença entre consultar os mercados **um por vez (sequencial)** e **todos ao mesmo tempo (concorrente, com threads)**.

```
cliente (terminal)    ──TCP :5050──▶ ┐
                                      ├─ agregador (1 processo) ──TCP──▶ 5 processos "mercado" (:5001–5005, SQLite próprio)
React (loja + painel) ──HTTP :8000──▶ ┘        │
        ▲                                       │
        └──────────── WebSocket ◀── eventos e métricas
```

Cliente, agregador e cada supermercado são processos separados. O cliente de terminal e o agregador conversam por socket TCP com mensagens JSON no formato do enunciado (`{"operacao": "consultar", "produto": "arroz"}`); o agregador fala com os supermercados também por TCP.

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

**2. Subir os 5 mercados + o agregador** (gera os bancos SQLite na primeira vez, cerca de 4 s; para regerar: `.venv/bin/python -m mercados.gerar_bancos`):

```bash
cd backend && .venv/bin/python iniciar.py
```

**3. Cliente de terminal (TCP)**, em outro terminal:

```bash
cd backend && .venv/bin/python -m cliente
```

Digite um produto (`arroz`, `café 500 g`, `leite integral`). Comandos: `/modo sequencial`, `/comparar arroz 3`, `/cesta 1 3x2`, `/mercados`, `/derrubar ipe`, `/religar ipe`, `/latencia ipe 2500`, `/json`, `/sair`. Também dá para fazer uma pesquisa só: `.venv/bin/python -m cliente arroz --modo sequencial`.

**4. Experimentos obrigatórios** (com o `iniciar.py` rodando; cerca de 6 minutos):

```bash
cd backend && .venv/bin/python -m experimentos
```

Gera os CSV em `docs/relatorio/dados/`, os gráficos em `docs/relatorio/figuras/` e as tabelas em `docs/relatorio/dados/resultados-experimentos.md`. `--so 4 5` roda só alguns; `--rapido` testa o script com poucas rodadas.

**5. Frontend em modo de desenvolvimento** (opcional), em outro terminal:

```bash
cd frontend && npm install && npm run dev
```

Abra http://localhost:5173. A documentação interativa da API fica em http://localhost:8000/docs.

**Alternativa sem Vite:** `cd frontend && npm run build` e reinicie o `iniciar.py`; o agregador passa a servir o site em http://localhost:8000.

## O que mostrar na apresentação

0. **Cliente TCP:** `python -m cliente`, pesquise `arroz branco 5 kg`, troque com `/modo sequencial` e pesquise de novo; `/comparar arroz 3` mostra o speedup. `/json` mostra a mensagem crua do protocolo. Abra um segundo e um terceiro terminal com o cliente para mostrar vários clientes ao mesmo tempo (`/mercados` mostra quantos estão conectados). `/derrubar ipe` e pesquise: a resposta vem dos outros 4, com o motivo da falha.
1. **Loja:** busque "arroz" no modo Sequencial e depois no Concorrente (alternador no topo). A faixa abaixo da busca mostra o tempo e as barras de cada conexão TCP: escada no sequencial, barras paralelas no concorrente.
2. **Produto:** clique num produto para ver os mercados ordenados por preço e o selo "Menor preço".
3. **Cesta:** adicione itens e clique em "Comparar nos 5 mercados".
4. **Comparar modos** (`/painel`): clique em "Comparar os dois modos". A mesma busca roda nos dois modos ao mesmo tempo, com as linhas do tempo na mesma escala: escada laranja (sequencial) × bloco azul (concorrente). "Repetir 5×" faz a média; abaixo ficam speedup, CPU e threads.
5. **Falhas e retry:** na seção "Mercados", cada mercado tem os cenários Normal · Lento (2 s) · Timeout (5 s) · Fora do ar. Tire um do ar e compare de novo. O agregador tenta de novo 3 vezes (esperando 0,5 s, 1 s e 2 s) antes de desistir: no sequencial essa espera trava a fila inteira (~3,5 s a mais); no concorrente ela acontece enquanto os outros mercados respondem. Latência acima de 3 s vira timeout (sem retry).
6. **Eventos:** cada consulta chega ao vivo pelo WebSocket; abra um cartão para ver os eventos TCP. "Exportar CSV" baixa as métricas.
7. **Prova de que é TCP de verdade:** `lsof -nP -iTCP:5001-5005 -iTCP:5050 -sTCP:LISTEN` lista os 5 mercados e o agregador escutando, cada mercado num processo (PID) diferente.
8. **Experimentos:** gráficos `fig-08` a `fig-11` em `docs/relatorio/figuras/` (sequencial × concorrente, latência, múltiplos clientes, falha durante a pesquisa).

## Testes

```bash
cd backend && .venv/bin/python -m pytest
```

55 testes: protocolo (inclusive mensagem fragmentada), comandos do servidor (busca, cesta), concorrente mais rápido que sequencial, consultas sobrepostas em threads distintas, retry de mercado fora do ar (espera crescente, volta no meio, custo no sequencial), conexão recusada, timeout, rotas da API, WebSocket, medição de recursos e o protocolo cliente ↔ agregador (cada operação e código de erro, JSON inválido, desconexão abrupta, mercado caindo durante a pesquisa, 8 clientes simultâneos).

## Estrutura

O backend está dividido pelos três componentes do enunciado (seção 6), mais o código que eles compartilham:

```
backend/
├── iniciar.py                 sobe os 5 mercados e o agregador (Ctrl+C encerra tudo)
│
├── comum/                     usado pelos três componentes
│   ├── config.py              mercados, portas, latências, timeout e retry
│   └── protocolo.py           protocolo TCP: uma mensagem JSON por linha
│
├── cliente/                   ① CLIENTE  ·  python -m cliente
│   ├── conexao.py             ClienteAgregador: socket TCP → agregador :5050
│   └── terminal.py            interface de terminal (pesquisa, /modo, /comparar, /cesta...)
│
├── agregador/                 ② AGREGADOR  ·  um processo, portas 5050 (TCP) e 8000 (HTTP)
│   ├── servidor_tcp.py        recebe os clientes: uma thread por cliente; operações do protocolo
│   ├── estrategias.py         ★ sequential() e concurrent(): o coração do trabalho
│   ├── consulta_mercado.py    uma ida e volta TCP a um mercado, com timeout e retry
│   ├── agregador.py           executa a estratégia escolhida e mede o tempo
│   ├── consolidacao.py        junta as ofertas, ordena por preço, menor preço, cesta mais barata
│   ├── eventos.py             eventos ao vivo (de qualquer thread para o WebSocket)
│   ├── metricas.py            histórico de tempos, médias e CSV
│   └── api_web.py             extra: rotas HTTP e WebSocket da interface web
│
├── mercados/                  ③ SERVIÇOS INDEPENDENTES  ·  5 processos, portas 5001–5005
│   ├── servidor.py            servidor TCP de um mercado: uma thread por conexão, latência e queda simuladas
│   ├── banco.py               consultas ao SQLite do mercado
│   ├── catalogo.py            95 tipos × marcas × tamanhos = 1.740 itens
│   └── gerar_bancos.py        gera data/<mercado>.db
│
├── experimentos/              os 5 experimentos obrigatórios  ·  python -m experimentos
│   └── executar.py            mede pelo cliente TCP → CSV, tabelas e gráficos
│
└── tests/                     55 testes (pytest), um arquivo por parte
frontend/                      interface web: Vite + React + TypeScript + Tailwind
scripts/
├── gerar_relatorio.py         relatorio.md → DOCX e PDF (LibreOffice)
├── diagramas.py               diagramas de arquitetura e sequência do relatório
└── fetch_images.py            baixa as fotos dos produtos (Open Food Facts)
docs/                          requisitos, arquitetura, protocolo, experimentos e relatório
```

**Para explicar o código, siga uma pesquisa:** `cliente/terminal.py` → `cliente/conexao.py` (envia a linha JSON) → `agregador/servidor_tcp.py` (thread do cliente) → `agregador/agregador.py` → `agregador/estrategias.py` (sequencial ou 5 threads) → `agregador/consulta_mercado.py` (TCP) → `mercados/servidor.py` (thread da conexão, SQLite) → volta por `agregador/consolidacao.py` (ordena e marca o menor preço) → resposta ao cliente.

## Documentação

- [Enunciado do trabalho](docs/CONTEXTO_TRABALHO.md)
- [Documento de requisitos](docs/requisitos.md): problema, objetivo, escopo, atores, RF, RNF, restrições, critérios de aceitação e casos de uso
- [Arquitetura, modelo de threads e diagramas de sequência](docs/arquitetura.md)
- [Protocolo de aplicação](docs/protocolo.md): mensagens, operações, códigos de erro e encerramento das conexões
- [Experimentos](docs/experimentos.md): os 5 obrigatórios e os complementares
- [Relatório técnico](docs/relatorio/) em DOCX, PDF e Markdown, com os dados de cada gráfico em `docs/relatorio/dados/`. O DOCX e o PDF são gerados do Markdown com `backend/.venv/bin/python scripts/gerar_relatorio.py` (precisa do LibreOffice); a capa fica em `docs/relatorio/capa.json`.

## API

| Rota | Descrição |
|---|---|
| `GET /api/search/sequential?q=` | Consulta os mercados um de cada vez |
| `GET /api/search/concurrent?q=` | Consulta todos ao mesmo tempo |
| `GET /api/search/{mode}?q=&category=&sort=&page=` | Busca com filtro, ordenação e paginação |
| `POST /api/basket/{mode}` | Total de uma cesta em cada mercado |
| `POST /api/benchmark` | Roda N vezes cada modo e devolve estatísticas |
| `GET /api/markets` | Nome, cor e estado de cada mercado (via comando STATUS por TCP) |
| `POST /api/markets/{id}/config` | Altera latência / online (comando CONFIG por TCP) |
| `GET /api/metrics/history` | Histórico de requisições |
| `GET /api/metrics/export.csv` | Histórico em CSV |
| `DELETE /api/metrics` | Zera as métricas |
| `WS /ws/events` | Eventos ao vivo |

## Créditos

Fotos dos produtos (uma por tipo, ilustrativa): Open Food Facts, Open Beauty Facts, Open Products Facts e Open Pet Food Facts (CC BY-SA), listadas em `frontend/public/products/CREDITS.md`. Os mercados, marcas, preços e estoques são fictícios.
