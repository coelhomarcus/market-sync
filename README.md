# Comparador de Preços de Supermercados

Trabalho 1 de Sistemas Distribuídos (Tema 1). Um **cliente** pesquisa um produto, um **agregador** consulta **5 supermercados independentes** e devolve os preços ordenados, com o menor destacado. Toda a comunicação é feita com **sockets TCP** programados com a biblioteca padrão do Python, e o agregador pode consultar os supermercados de dois jeitos:

- **sequencial**: um supermercado de cada vez, numa thread só. O tempo é a **soma** das latências (≈ 3,6 s).
- **concorrente**: os 5 ao mesmo tempo, uma thread por supermercado. O tempo é a **maior** latência (≈ 1,2 s).

```
                         porta 5050                          portas 5001–5005
 cliente (terminal) ──── TCP / JSON ────▶ agregador ──── TCP / JSON ────▶ Mercado Aurora   (processo próprio, aurora.db)
 python -m client                        1 thread por       (sequencial   SuperVila        (processo próprio, supervila.db)
                                          cliente            ou 5 threads) Empório Sol      (...)
                                              │                            Max Atacarejo
                                              ▼                            Mercadinho Ipê
                               painel no terminal do start.py
                               (gráfico ou --raw, linha a linha)
```

Cada componente é um processo separado: 1 agregador + 5 supermercados, mais quantos clientes quiser.

## Instalação

Precisa de **Python 3.12**. O LibreOffice só é necessário para gerar o relatório em DOCX/PDF.

```bash
python3.12 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements.txt
```

Todos os comandos abaixo são rodados **da raiz do projeto**.

## Comandos

### Subir o sistema

```bash
.venv/bin/python start.py
```

Sobe os 5 supermercados e o agregador. Na primeira vez, gera os bancos SQLite. O terminal vira o **painel gráfico** em tela cheia, e **Ctrl+C** encerra tudo: o agregador espera as pesquisas em andamento terminarem e depois fecha os mercados.

| Opção | O que faz |
|---|---|
| *(nenhuma)* | Painel gráfico: um quadro por pesquisa, com uma barra por supermercado crescendo ao vivo |
| `--raw` | Modo cru: cada chamada TCP linha a linha (connect, mensagem enviada, resposta, close), dos dois lados |
| `--silencioso` | Sem painel. Use durante os experimentos |

### Pesquisar (cliente TCP)

Em outro terminal:

```bash
.venv/bin/python -m client
```

Abre o modo interativo: o cliente conecta na porta 5050 e mantém a conexão aberta. Digite um produto (`arroz`, `café 500 g`, `leite integral`) ou um comando:

| Comando | O que faz |
|---|---|
| `arroz branco 5 kg` | Pesquisa nos 5 supermercados (no modo atual) |
| `/modo sequencial` · `/modo concorrente` | Troca o modo das próximas pesquisas |
| `/comparar arroz 3` | Mesma pesquisa nos dois modos, 3 rodadas cada, e mostra o speedup |
| `/cesta 1 3x2 5` | Cesta com os itens da última lista (`3x2` = item 3, 2 unidades) e o supermercado mais barato |
| `/mercados` | Situação de cada supermercado e quantos clientes estão conectados |
| `/derrubar ipe` · `/religar ipe` | Tira um supermercado do ar e traz de volta (ids: `aurora`, `supervila`, `emporio-sol`, `max-atacarejo`, `ipe`) |
| `/latencia ipe 2500` | Muda a latência simulada de um supermercado (acima de 3000 ms vira timeout) |
| `/json` | Liga/desliga a exibição da resposta JSON crua do protocolo |
| `/ajuda` · `/sair` | Ajuda · encerra a conexão |

Também dá para fazer uma pesquisa só e sair:

```bash
.venv/bin/python -m client "arroz branco 5 kg" --modo sequencial
```

```bash
.venv/bin/python -m client cafe --comparar 3
```

Opções: `--modo sequencial|concorrente`, `--comparar N`, `--limite N` (produtos mostrados, padrão 5), `--json`, `--host`, `--port`.

### Rodar uma peça sozinha

Cada supermercado é um serviço independente e pode subir sozinho:

```bash
.venv/bin/python -m markets.aurora
```

Os outros: `markets.supervila`, `markets.emporio_sol`, `markets.max_atacarejo` e `markets.ipe`. Opção: `--latencia 800`.

O agregador sozinho (precisa dos supermercados no ar):

```bash
.venv/bin/python -m aggregator.tcp_server
```

### Experimentos obrigatórios

Com o sistema no ar em modo silencioso (`.venv/bin/python start.py --silencioso`), em outro terminal:

```bash
.venv/bin/python -m experiments
```

Roda os 5 experimentos do enunciado pelo cliente TCP, em cerca de 6 minutos. Grava os CSV em `docs/relatorio/dados/`, as tabelas em `docs/relatorio/dados/resultados-experimentos.md` e os gráficos `fig-08` a `fig-11` em `docs/relatorio/figuras/` (CSV: `exp1-sequencial.csv` … `exp5-indisponibilidade.csv`).

| Opção | O que faz |
|---|---|
| `--so 4 5` | Mede só alguns experimentos |
| `--analisar` | Não mede nada: refaz tabelas e gráficos a partir dos CSV |
| `--rapido` | Poucas rodadas, só para testar o script |

Cada experimento também roda sozinho (aceita `--rapido` e `--analisar`):

```bash
.venv/bin/python -m experiments.exp3_latency
```

Os outros: `experiments.exp1_sequential`, `experiments.exp2_concurrent`, `experiments.exp4_multiple_clients` e `experiments.exp5_unavailability`.

### Testes

```bash
.venv/bin/python -m pytest
```

52 testes, com conexões TCP reais. Eles sobem os 5 supermercados em portas livres, então não precisam do sistema rodando.

### Outros

| Comando | O que faz |
|---|---|
| `.venv/bin/python -m tools.seed_databases` | Gera de novo os bancos SQLite dos supermercados (semente fixa: sempre os mesmos dados) |
| `tail -f logs/aurora.log` | Log de um supermercado no modo gráfico (no `--raw` ele aparece no próprio terminal) |
| `lsof -nP -iTCP:5001-5005 -iTCP:5050 -sTCP:LISTEN` | Prova que são 6 processos, cada um escutando na sua porta TCP |
| `.venv/bin/python scripts/diagrams.py` | Redesenha os diagramas de casos de uso, arquitetura e sequência |
| `.venv/bin/python scripts/build_report.py` | Gera `relatorio.docx` e `relatorio.pdf` a partir do `relatorio.md`, com o LibreOffice (capa em `docs/relatorio/capa.json`) |

## Estrutura

Organizada pelos três componentes do enunciado (seção 6). Nomes de pastas, arquivos e código em inglês; comentários, mensagens e documentação em português.

```
├── start.py                   sobe os 5 supermercados e o agregador; Ctrl+C encerra tudo
├── common/                    o que todos compartilham
│   ├── config.py              portas, latências, timeout e retry
│   ├── protocol.py            o protocolo TCP: uma mensagem JSON por linha
│   └── watchdog.py            encerra o servidor se o start.py morrer (sem processos órfãos)
│
├── client/                    ① CLIENTE  ·  python -m client
│   ├── connection.py          AggregatorClient: o socket TCP com o agregador
│   └── terminal.py            a interface no terminal
│
├── aggregator/                ② AGREGADOR  ·  porta 5050
│   ├── tcp_server.py          recebe os clientes: uma thread por cliente
│   ├── aggregator.py          escolhe a estratégia e mede o tempo
│   ├── sequential.py          ★ um supermercado de cada vez (thread_1)
│   ├── concurrent.py          ★ todos ao mesmo tempo (thread_1 … thread_5)
│   ├── market_query.py        uma ida e volta TCP a um supermercado, com timeout e retry
│   ├── consolidation.py       junta as ofertas, ordena por preço, menor preço, cesta mais barata
│   └── display.py             o painel no terminal (gráfico e --raw)
│
├── markets/                   ③ SERVIÇOS INDEPENDENTES  ·  um processo e uma porta cada
│   ├── aurora/                porta 5001 · server.py · database.py · aurora.db
│   ├── supervila/             porta 5002
│   ├── emporio_sol/           porta 5003
│   ├── max_atacarejo/         porta 5004
│   └── ipe/                   porta 5005
│
├── experiments/               os 5 experimentos obrigatórios, um por arquivo
│   ├── exp1_sequential.py     Experimento 1: consulta sequencial
│   ├── exp2_concurrent.py     Experimento 2: consulta concorrente (e a comparação com o 1)
│   ├── exp3_latency.py        Experimento 3: simulação de latência
│   ├── exp4_multiple_clients.py  Experimento 4: múltiplos clientes
│   ├── exp5_unavailability.py    Experimento 5: indisponibilidade de serviço
│   └── shared.py              o que todos compartilham (CSV, gráficos, configurar mercados)
│
├── tools/                     catálogo de produtos e gerador dos bancos (usados uma vez)
├── tests/                     52 testes (pytest)
├── scripts/                   diagramas e geração do relatório
└── docs/                      enunciado, requisitos, arquitetura, protocolo, experimentos e relatório
```

O código das cinco pastas de `markets/` é o mesmo, **de propósito**: cada supermercado é um serviço com código, porta e banco próprios, que poderia rodar em outra máquina. Só mudam os dados no topo de `server.py` (nome, porta, latência) e o arquivo `.db`.

**Para explicar o código, siga uma pesquisa:** `client/terminal.py` → `client/connection.py` (envia a linha JSON) → `aggregator/tcp_server.py` (thread do cliente) → `aggregator/aggregator.py` → `aggregator/sequential.py` ou `aggregator/concurrent.py` → `aggregator/market_query.py` (TCP) → `markets/aurora/server.py` (thread da conexão, SQLite) → volta por `aggregator/consolidation.py` (ordena e marca o menor preço) → resposta ao cliente.

## As duas visualizações do terminal

**Gráfico** (`start.py`): painel em tela cheia, como o `htop`, que se redesenha ao redimensionar. Em cima ficam os supermercados, os clientes conectados e os últimos avisos; embaixo, as pesquisas, a mais recente em cima, todas na mesma régua de tempo:

```
╭─ #8f8e "arroz branco 5 kg" · concorrente · cliente TCP ──────────────────────────────╮
│ Mercado Aurora  ███······················· ✔  318 ms · 10 itens  thread_1 → conexão nº 2 │
│ SuperVila       ████······················ ✔  475 ms · 10 itens  thread_2 → conexão nº 2 │
│ Empório Sol     █████····················· ✔  632 ms · 8 itens   thread_3 → conexão nº 2 │
│ Max Atacarejo   █████████················· ✔  1,02 s · 8 itens   thread_4 → conexão nº 2 │
│ Mercadinho Ipê  ███████████··············· ✔  1,28 s · 10 itens  thread_5 → conexão nº 2 │
╰──────────────────────────── 1,28 s · 5 de 5 mercados · 5 threads novas; o pedido só espera ─╯
```

- **Sequencial:** as barras formam uma **escada** e todas as linhas mostram `thread_1`.
- **Concorrente:** as barras saem **juntas**, de `thread_1` a `thread_5`.
- **Coluna da direita:** a thread do agregador → a conexão (e a thread) que atendeu do lado do supermercado.
- **Falhas:** fora do ar, a barra fica amarela nas novas tentativas e vermelha na desistência.

**Raw** (`start.py --raw`): cada passo de cada chamada numa linha. As linhas com `┃` vêm dos processos dos supermercados (o lado do servidor), e dá para cruzar os dois lados pela porta:

```
 ▶ #dfd7 "arroz branco 5 kg" · sequencial · cliente TCP ─────────────────────────────────
15:38:13.981  #dfd7  +    0 ms  thread_1  CONNECT  → Aurora      :5001 · porta local 62455 · 0,2 ms
15:38:13.981  #dfd7  +    1 ms  thread_1  ENVIA    → Aurora      {"cmd":"SEARCH","q":"arroz branco 5 kg"} · 41 B
15:38:13.982         ┃ Aurora      conexão nº 1   ← recebeu SEARCH "arroz branco 5 kg"  de :62455
15:38:14.306         ┃ Aurora      conexão nº 1   → respondeu 10 itens · 1789 B · 324 ms
15:38:14.307  #dfd7  +  326 ms  thread_1  RECEBE   ← Aurora      {"ok":true,"data":{"items":[…]}} · 1,7 KB · esperou 324 ms
15:38:14.308  #dfd7  +  327 ms  thread_1  CLOSE    ✕ Aurora
...
 ■ #dfd7 3,71 s · 5 de 5 mercados · 1 thread: a do próprio pedido ─────────────────────────
```

## Sequencial, concorrente e vários clientes

Existem dois níveis de concorrência, e só um deles muda com o modo:

| | Sequencial | Concorrente |
|---|---|---|
| **Dentro de uma pesquisa** (agregador → 5 supermercados) | 1 thread, um supermercado de cada vez | 5 threads novas, todos juntos |
| **Entre clientes** (cliente → agregador) | uma thread por cliente | uma thread por cliente |
| **Em cada supermercado** | uma thread por conexão | uma thread por conexão |

Por isso, **mesmo no modo sequencial, dois clientes são atendidos ao mesmo tempo**: cada cliente tem a sua thread no agregador, e cada uma faz a sua pesquisa sequencial em paralelo com a outra. O que é sequencial é a ordem dos supermercados *dentro* de cada pesquisa. O Experimento 4 mede isso: com 32 clientes, cada pesquisa leva o mesmo tempo que com 1.

## Protocolo

Mensagens JSON em UTF-8, uma por linha (`\n`), nos dois trechos TCP:

```
cliente → agregador     {"operacao": "consultar", "produto": "arroz", "modo": "concorrente"}
agregador → cliente     {"operacao": "consultar", "status": "sucesso", "resultados": [{"produto": ..., "menor_preco": {...},
                         "ofertas": [{"fonte": "Max Atacarejo", "preco": 24.9, "status": "sucesso"}, ...]}], ...}

agregador → mercado     {"cmd": "SEARCH", "q": "arroz"}
mercado → agregador     {"ok": true, "data": {"items": [...]}, "cpu_ms": 1.2, "thread": "conexão nº 3"}
```

- **Operações do cliente:** `consultar`, `comparar`, `cesta`, `mercados`, `configurar`, `encerrar`.
- **Erros:** vêm com um `codigo`, por exemplo `PARAMETRO_INVALIDO` ou `NENHUM_MERCADO_RESPONDEU`.
- **Supermercado que não responde:** gera `status: "parcial"` com o motivo, e os outros resultados chegam normalmente.

Detalhes em [docs/protocolo.md](docs/protocolo.md).

## Roteiro para a apresentação

Deixe dois terminais lado a lado: à esquerda o `start.py` (o painel), à direita o cliente.

1. **Processos e portas:** `lsof -nP -iTCP:5001-5005 -iTCP:5050 -sTCP:LISTEN` mostra os 6 processos, cada um na sua porta.
2. **Concorrente:** `python -m client`, pesquise `arroz branco 5 kg`. No painel, as 5 barras saem juntas, em 5 threads.
3. **Sequencial:** `/modo sequencial` e a mesma pesquisa. No painel, uma escada, numa thread só.
4. **Speedup:** `/comparar arroz 3`.
5. **Vários clientes:** abra um segundo cliente e pesquise nos dois ao mesmo tempo. São dois quadros em andamento juntos, mesmo no sequencial.
6. **Falha:** `/derrubar ipe` e pesquise. A resposta vem dos outros 4, com o motivo, e no painel aparecem as novas tentativas. Depois, `/religar ipe`.
7. **Protocolo:** `/json` mostra a mensagem crua. Ou suba com `start.py --raw` para ver cada connect, envio, resposta e close, dos dois lados.
8. **Experimentos:** gráficos `fig-08` a `fig-11` em `docs/relatorio/figuras/`.

## Documentação

- [Enunciado do trabalho](docs/01_TRABALHO.md)
- [Documento de requisitos](docs/requisitos.md): problema, objetivo, escopo, atores, RF, RNF, restrições, critérios de aceitação e casos de uso
- [Arquitetura](docs/arquitetura.md), [Protocolo](docs/protocolo.md) e [Experimentos](docs/experimentos.md)
- [Relatório técnico](docs/relatorio/) em Markdown, DOCX e PDF, com os dados de cada gráfico em `docs/relatorio/dados/`

Os supermercados, marcas, preços e estoques são fictícios.
