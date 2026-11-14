# Experimentos de desempenho

## Objetivo

Medir o impacto da concorrência no tempo de resposta do agregador, verificar o comportamento com falhas e o efeito do volume de dados.

## Ambiente

- macOS (Apple Silicon), Python 3.12, todos os processos em `127.0.0.1`.
- 5 mercados, cada um em seu processo, com latência simulada de ±15% em torno do valor configurado.
- Bancos gerados por `markets/seed.py`: 1.369 a 1.689 produtos por mercado, 7.730 no total.
- Timeout do cliente TCP: 3 s.
- Medições feitas pelo agregador com `time.perf_counter()`; cada requisição gera um registro exportável em CSV (inclui bytes recebidos por mercado).

## Como reproduzir

1. `cd backend && .venv/bin/python run_all.py`
2. Em `/painel`, clique em "Zerar".
3. Escolha o cenário de cada mercado na seção "Mercados" (ou mude a latência com `curl -X POST localhost:8000/api/markets/aurora/config -H 'content-type: application/json' -d '{"latency_ms":800}'`).
4. Rode o benchmark com o número de rodadas indicado (ou `curl -X POST localhost:8000/api/benchmark -H 'content-type: application/json' -d '{"runs":10,"q":"arroz"}'`).
5. Exporte o CSV para gráficos e tabelas do relatório.

O benchmark alterna a ordem dos modos a cada rodada (sequencial→concorrente, depois concorrente→sequencial) para que nenhum modo seja favorecido por cache ou aquecimento. A busca usada é "arroz": 217 ofertas, 44 KB somando os cinco mercados.

## Resultados (13/11/2026, bancos grandes)

| Cenário | Configuração | Rodadas | Sequencial | Concorrente | Speedup |
|---|---|---|---|---|---|
| E1 | Latências padrão: 300, 500, 700, 900, 1200 ms | 10 | 3,74 s (3,43–3,97, desvio 150 ms) | 1,22 s (1,03–1,35, desvio 103 ms) | 3,1× |
| E2 | Todos com 800 ms | 5 | 4,10 s | 871 ms | 4,7× |
| E3 | Todos com 0 ms | 20 | 17,7 ms | 7,4 ms | 2,4× |
| E4 | Padrão, Mercadinho Ipê com 4000 ms (timeout) | 3 | 5,47 s | 3,00 s | 1,8× |
| E5 | Padrão, Mercadinho Ipê fora do ar | 5 | — | 911 ms (4 de 5 mercados) | — |

- **E1:** o sequencial ficou perto da soma das latências (3,6 s) e o concorrente perto da maior (1,2 s): `T_seq ≈ Σ lᵢ`, `T_conc ≈ max(lᵢ)`.
- **E2:** perto do limite teórico de 5×; o concorrente espera o mais lento de cinco sorteios de ±15%, por isso fica acima de 800 ms.
- **E3:** sem espera de rede sobra o trabalho real de cada mercado (SQLite + JSON), feito em paralelo pelos cinco processos. Com os bancos pequenos da primeira versão (33 produtos), esse ganho era de só 1,4×.
- **E4:** o Ipê esgotou o timeout nas 6 consultas; o sequencial soma 2,4 s dos outros + 3 s, o concorrente espera só o timeout. Os dois devolvem os preços dos outros quatro mercados.
- **E5:** o mercado fecha a conexão em 1,4 ms; o concorrente passa a esperar o Max Atacarejo (900 ms).

### E6 — Número de mercados (latências padrão, adicionados do mais rápido ao mais lento), 5 buscas por ponto

| Mercados | Sequencial | Concorrente | Speedup |
|---|---|---|---|
| 1 | 309 ms | 316 ms | 1,0× |
| 2 | 819 ms | 488 ms | 1,7× |
| 3 | 1,48 s | 729 ms | 2,0× |
| 4 | 2,44 s | 939 ms | 2,6× |
| 5 | 3,53 s | 1,21 s | 2,9× |

### E7 — Número de threads do pool (`max_workers`), 5 mercados, 5 buscas por ponto

| Threads | Média | Mín. | Máx. | Previsto pela fila do pool |
|---|---|---|---|---|
| 1 | 3,70 s | 3,58 s | 3,78 s | 3,6 s |
| 2 | 2,31 s | 2,16 s | 2,41 s | 2,2 s |
| 3 | 1,68 s | 1,54 s | 1,81 s | 1,7 s |
| 4 | 1,55 s | 1,41 s | 1,69 s | 1,5 s |
| 5 | 1,27 s | 1,18 s | 1,33 s | 1,2 s |

Previsto = cada consulta, na ordem de envio, vai para a primeira thread livre. Numa rodada anterior, com bancos pequenos, 3 e 4 threads ficaram 120–160 ms acima do previsto; refeito, o desvio ficou abaixo de 50 ms, dentro da variação esperada para 5 buscas por ponto.

### E8 — Volume de dados, 5 buscas por célula

| Busca | Ofertas | Recebido | Sem latência: seq. | Sem latência: conc. | Padrão: seq. | Padrão: conc. |
|---|---|---|---|---|---|---|
| "arroz grao nobre" | 23 | 5 KB | 9,4 ms | 5,1 ms | 3,61 s | 1,20 s |
| "arroz" | 217 | 44 KB | 18,2 ms | 9,5 ms | 3,81 s | 1,19 s |
| catálogo inteiro | 7.692 | 1,53 MB | 66,6 ms | 31,3 ms | 3,77 s | 1,25 s |

Trazer 300 vezes mais dados custa poucos milissegundos em `localhost`; com as latências padrão, a diferença some na variação.

### E9 — Consumo de recursos (CPU, threads, memória)

Cada mercado informa a CPU da thread que atendeu a consulta (`time.thread_time()`, sem contar o sleep da latência); o agregador soma a CPU das próprias threads de consulta (também `time.thread_time()`) e conta quantas threads distintas conversaram com os mercados.

| Cenário | Modo | Tempo | CPU agregador | CPU mercados | CPU total | Ocupação | Threads extras |
|---|---|---|---|---|---|---|---|
| Padrão, "arroz" (10) | Sequencial | 3,80 s | 21,6 ms | 19,7 ms | 41,3 ms | 1,1% | 0 |
| | Concorrente | 1,24 s | 15,6 ms | 19,3 ms | 35,0 ms | 2,9% | 5 |
| Padrão, catálogo (5) | Sequencial | 4,16 s | 30,5 ms | 48,7 ms | 79,2 ms | 1,9% | 0 |
| | Concorrente | 1,24 s | 26,4 ms | 51,6 ms | 78,0 ms | 6,3% | 5 |
| Sem latência, "arroz" (20) | Sequencial | 6,4 ms | 1,1 ms | 4,3 ms | 5,4 ms | 84% | 0 |
| | Concorrente | 2,8 ms | 2,9 ms | 4,9 ms | 7,8 ms | 280% | 5 |
| Sem latência, catálogo (10) | Sequencial | 42,8 ms | 11,8 ms | 18,4 ms | 30,2 ms | 71% | 0 |
| | Concorrente | 18,3 ms | 13,7 ms | 22,6 ms | 36,4 ms | 199% | 5 |

- Com espera de rede, a CPU dos mercados é a mesma nos dois modos; a do agregador parece maior no sequencial porque a janela de medição é 3× mais longa e inclui tarefas de fundo.
- Sem espera, o concorrente gasta 20–43% mais CPU (criar threads, trocar de contexto), mas ocupa 2 a 2,8 núcleos ao mesmo tempo: é esse paralelismo que dá o ganho de ~2,3× sem latência.
- Memória residente: cerca de 18 MB por processo de mercado e 30–50 MB no agregador.
- Os tempos sem latência variam entre rodadas (E3: 17,7 ms; E9: 6,4 ms na busca "arroz") conforme a carga do computador; o speedup ficou em 2,3–2,4× nas duas.

## Discussão

- O modelo de custo se confirmou: **sequencial ≈ soma, concorrente ≈ máximo**. O speedup máximo é `Σ lᵢ / max(lᵢ)`; com as latências padrão, 3,6 / 1,2 = 3,0 (medido: 3,1).
- O GIL do Python não atrapalha aqui: enquanto uma thread espera em `recv()`, ela libera o GIL e as outras seguem. O trabalho pesado (SQLite, montar o JSON) acontece nos processos dos mercados, em paralelo de verdade.
- Timeouts são essenciais na versão concorrente: sem eles, um único mercado travado seguraria a resposta inteira.
- Com menos threads que mercados, as consultas esperam na fila do pool; o ganho máximo exige uma thread por mercado.
- Concorrência não economiza CPU: o mesmo trabalho é feito, só que sobreposto. O custo extra é de threads (5 por requisição) e, sem espera de rede, de 20–43% de CPU.

## Ideias de experimentos adicionais

- Rodar os mercados em outras máquinas da rede (latência real em vez de simulada).
- Disparar várias buscas simultâneas (várias abas ou um script) para medir o atendimento concorrente dentro de cada mercado.
- Comparar com uma versão `asyncio`.
