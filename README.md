# market-sync — Comparador de Preços de Supermercados

Trabalho 1 de Sistemas Distribuídos (Tema 1): um agregador que consulta **5 supermercados independentes por sockets TCP** (cada um com seu banco SQLite de ~1.500 produtos), compara os preços e mostra a diferença entre consultar os mercados **um por vez (sequencial)** e **todos ao mesmo tempo (concorrente, com threads)**.

```
cliente de terminal ──TCP :5050──▶ ┐
                                    ├─▶ agregador (1 processo) ──TCP──▶ 5 processos "mercado" (:5001–5005, SQLite próprio)
loja web (navegador) ─HTTP :8000──▶ ┘          │
                                               └─▶ terminal: painel ao vivo de cada pesquisa
```

Cliente, agregador e cada supermercado são processos separados. O cliente de terminal e o agregador conversam por socket TCP com mensagens JSON no formato do enunciado (`{"operacao": "consultar", "produto": "arroz"}`); o agregador fala com os supermercados também por TCP. A loja web é só uma vitrine: busca, produto, cesta e o seletor **Sequencial / Concorrente**. Todo o "por trás" (conexões, threads, tempos, falhas) aparece no **painel ao vivo do terminal** do `iniciar.py`.

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

Esse terminal vira um painel ao vivo (biblioteca [Rich](https://github.com/Textualize/rich)). Cada pesquisa, da loja ou do cliente, é um quadro com uma barra por mercado que cresce enquanto a resposta não chega. A régua é a mesma em todos os quadros (no mínimo 4 s), então dá para comparar um com o outro:

```
╭─ #6a7b "arroz" · sequencial · loja web (HTTP) ───────────────────────────────────────────────────────────────────╮
│ Mercado Aurora  ████···································· ✔  359 ms · 48 itens · 9,5 KB  pedido-http → Thread-7  │
│ SuperVila       ····█████······························· ✔  501 ms · 49 itens · 9,7 KB  pedido-http → Thread-8  │
│ Empório Sol     ·········███████························ ✔  736 ms · 39 itens · 7,7 KB  pedido-http → Thread-9  │
│ Max Atacarejo   ················█████████··············· ✔  882 ms · 43 itens · 8,5 KB  pedido-http → Thread-10 │
│ Mercadinho Ipê  ·························███████████···· ✔  1,16 s · 41 itens · 8,1 KB  pedido-http → Thread-11 │
│                 0 s       1 s       2 s       3 s    4 s                                agregador → mercado     │
╰─────────────────────────────────────────────────────────── 3,64 s · 5 de 5 mercados · 1 thread (a do pedido) ──╯
╭─ #af49 "arroz" · concorrente · cliente TCP ──────────────────────────────────────────────────────────────────────╮
│ Mercado Aurora  ███····································· ✔  345 ms · 48 itens · 9,5 KB  consulta_0 → Thread-12  │
│ SuperVila       ███████································· ✔  730 ms · 49 itens · 9,7 KB  consulta_1 → Thread-13  │
│ Empório Sol     ████████································ ✔  758 ms · 39 itens · 7,7 KB  consulta_2 → Thread-14  │
│ Max Atacarejo   ██████████······························ ✔  970 ms · 43 itens · 8,5 KB  consulta_3 → Thread-15  │
│ Mercadinho Ipê  ██████████████·························· ✔  1,42 s · 41 itens · 8,1 KB  consulta_4 → Thread-16  │
│                 0 s       1 s       2 s       3 s    4 s                                agregador → mercado     │
╰──────────────────────────────────────────────────────────── 1,43 s · 5 de 5 mercados · 5 threads de consulta ──╯
 mercados   ● Aurora :5001 300ms  ● SuperVila :5002 500ms  ● Empório Sol :5003 700ms  ● Max :5004 900ms  ● Ipê :5005 1200ms   clientes TCP: 1
```

- **Sequencial:** as barras formam uma **escada**, sempre a mesma thread (`pedido-http` ou `cliente-1`), e o tempo é a soma.
- **Concorrente:** as barras saem **juntas**, uma thread por mercado (`consulta_0`…`consulta_4`), e o tempo é o do mais lento.
- **Threads:** a coluna da direita mostra a thread do agregador e a thread do mercado que atendeu (`Thread-12`): uma por conexão nos dois lados.
- **Falhas:** fora do ar, a barra fica amarela durante as novas tentativas (`↻`) e vermelha na desistência (`✘`).
- **Linha de baixo:** situação de cada mercado e quantos clientes TCP estão conectados; conexões de clientes e `/derrubar` aparecem como linhas `⇄` e `⚙`.
- **Logs dos mercados:** cada mercado grava o seu log em `backend/logs/<mercado>.log` (`tail -f logs/aurora.log`), para não bagunçar o painel.
- **`--silencioso`:** desliga o painel (bom para os experimentos).

**3. Cliente de terminal (TCP)**, em outro terminal:

```bash
cd backend && .venv/bin/python -m cliente
```

Digite um produto (`arroz`, `café 500 g`, `leite integral`). Comandos: `/modo sequencial`, `/comparar arroz 3`, `/cesta 1 3x2`, `/mercados`, `/derrubar ipe`, `/religar ipe`, `/latencia ipe 2500`, `/json`, `/sair`. Também dá para fazer uma pesquisa só: `.venv/bin/python -m cliente arroz --modo sequencial`.

**4. Experimentos obrigatórios** (com o `iniciar.py --silencioso` rodando, sem o painel; cerca de 6 minutos):

```bash
cd backend && .venv/bin/python -m experimentos
```

Gera os CSV em `docs/relatorio/dados/`, os gráficos em `docs/relatorio/figuras/` e as tabelas em `docs/relatorio/dados/resultados-experimentos.md`. `--so 4 5` roda só alguns; `--rapido` testa o script com poucas rodadas.

**5. Loja web.** Já vem servida pelo agregador em http://localhost:8000 depois de um `cd frontend && npm install && npm run build` (uma vez). Para mexer no front, o modo de desenvolvimento:

```bash
cd frontend && npm install && npm run dev
```

e abra http://localhost:5173.

## O que mostrar na apresentação

Deixe dois terminais lado a lado: à esquerda o `iniciar.py` (o painel), à direita o cliente.

1. **Cliente TCP:** `python -m cliente`, pesquise `arroz branco 5 kg`. No painel, as 5 barras saem juntas, em 5 threads. `/modo sequencial` e a mesma pesquisa: no painel, uma escada, numa thread só. `/comparar arroz 3` mostra o speedup. `/json` mostra a mensagem crua do protocolo.
2. **Vários clientes:** abra um segundo e um terceiro terminal com o cliente; o painel mostra `⇄ cliente-2 conectou` e um quadro para cada pesquisa em andamento, cada um com seu `#id`. `/mercados` mostra quantos estão conectados.
3. **Falha:** `/derrubar ipe` e pesquise. No painel, a barra do Ipê fica amarela (`↻`, novas tentativas após 0,5 s, 1 s e 2 s) e depois vermelha (`✘`); a resposta vem dos outros 4. No sequencial a espera trava a fila; no concorrente ela corre junto com os outros. `/religar ipe`.
4. **Loja web:** busque "arroz" e troque Sequencial / Concorrente no topo; o tempo aparece na página e o passo a passo no painel. Abra um produto (mercados do mais barato ao mais caro, selo "Menor preço") e monte uma cesta ("Comparar nos 5 mercados").
5. **Prova de que é TCP de verdade:** `lsof -nP -iTCP:5001-5005 -iTCP:5050 -sTCP:LISTEN` lista os 5 mercados e o agregador escutando, cada mercado num processo (PID) diferente.
6. **Experimentos:** gráficos `fig-08` a `fig-11` em `docs/relatorio/figuras/` (sequencial × concorrente, latência, múltiplos clientes, falha durante a pesquisa).

## Testes

```bash
cd backend && .venv/bin/python -m pytest
```

58 testes: protocolo (inclusive mensagem fragmentada), comandos do servidor (busca, cesta), concorrente mais rápido que sequencial, consultas sobrepostas em threads distintas, retry de mercado fora do ar (espera crescente, volta no meio, custo no sequencial), conexão recusada, timeout, rotas da loja, o painel do terminal (escada no sequencial, barras juntas no concorrente) e o protocolo cliente ↔ agregador (cada operação e código de erro, JSON inválido, desconexão abrupta, mercado caindo durante a pesquisa, 8 clientes simultâneos).

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
│   ├── sequencial.py          ★ um mercado de cada vez (um laço for)
│   ├── concorrente.py         ★ todos ao mesmo tempo (ThreadPoolExecutor, uma thread por mercado)
│   ├── consulta_mercado.py    uma ida e volta TCP a um mercado, com timeout e retry
│   ├── agregador.py           escolhe a estratégia, mede o tempo
│   ├── consolidacao.py        junta as ofertas, ordena por preço, menor preço, cesta mais barata
│   ├── registro.py            painel ao vivo no terminal (Rich): um quadro por pesquisa
│   └── api_web.py             as 3 rotas HTTP da loja web
│
├── mercados/                  ③ SERVIÇOS INDEPENDENTES  ·  5 processos, portas 5001–5005
│   ├── servidor.py            servidor TCP de um mercado: uma thread por conexão, latência e queda simuladas (log em logs/<mercado>.log)
│   ├── banco.py               consultas ao SQLite do mercado
│   ├── catalogo.py            95 tipos × marcas × tamanhos = 1.740 itens
│   └── gerar_bancos.py        gera data/<mercado>.db
│
├── experimentos/              os 5 experimentos obrigatórios  ·  python -m experimentos
│   └── executar.py            mede pelo cliente TCP → CSV, tabelas e gráficos
│
└── tests/                     58 testes (pytest), um arquivo por parte
frontend/                      loja web: Vite + React + TypeScript + Tailwind
scripts/
├── gerar_relatorio.py         relatorio.md → DOCX e PDF (LibreOffice)
├── diagramas.py               diagramas de arquitetura e sequência do relatório
└── fetch_images.py            baixa as fotos dos produtos (Open Food Facts)
docs/                          requisitos, arquitetura, protocolo, experimentos e relatório
```

**Para explicar o código, siga uma pesquisa:** `cliente/terminal.py` → `cliente/conexao.py` (envia a linha JSON) → `agregador/servidor_tcp.py` (thread do cliente) → `agregador/agregador.py` → `agregador/sequencial.py` ou `agregador/concorrente.py` (uma thread ou cinco) → `agregador/consulta_mercado.py` (TCP) → `mercados/servidor.py` (thread da conexão, SQLite) → volta por `agregador/consolidacao.py` (ordena e marca o menor preço) → resposta ao cliente.

## Documentação

- [Enunciado do trabalho](docs/CONTEXTO_TRABALHO.md)
- [Documento de requisitos](docs/requisitos.md): problema, objetivo, escopo, atores, RF, RNF, restrições, critérios de aceitação e casos de uso
- [Arquitetura, modelo de threads e diagramas de sequência](docs/arquitetura.md)
- [Protocolo de aplicação](docs/protocolo.md): mensagens, operações, códigos de erro e encerramento das conexões
- [Experimentos](docs/experimentos.md): os 5 obrigatórios e os complementares
- [Relatório técnico](docs/relatorio/) em DOCX, PDF e Markdown, com os dados de cada gráfico em `docs/relatorio/dados/`. O DOCX e o PDF são gerados do Markdown com `backend/.venv/bin/python scripts/gerar_relatorio.py` (precisa do LibreOffice); a capa fica em `docs/relatorio/capa.json`.

## API da loja web

| Rota | Descrição |
|---|---|
| `GET /api/search/{modo}?q=&category=&sort=&page=` | Pesquisa nos 5 mercados (`modo` = `sequential` ou `concurrent`), com filtro, ordenação e paginação |
| `POST /api/basket/{modo}` | Total de uma cesta em cada mercado |
| `GET /api/markets` | Nome e situação de cada mercado (comando STATUS por TCP) |

Comparar modos, mudar latência e derrubar mercados é feito pelo cliente de terminal (protocolo TCP, `docs/protocolo.md`).

## Créditos

Fotos dos produtos (uma por tipo, ilustrativa): Open Food Facts, Open Beauty Facts, Open Products Facts e Open Pet Food Facts (CC BY-SA), listadas em `frontend/public/products/CREDITS.md`. Os mercados, marcas, preços e estoques são fictícios.
