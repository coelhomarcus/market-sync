# Resultados dos experimentos obrigatórios

Gerado por `backend/experimentos/executar.py` a partir dos CSV desta pasta (14/11/2026 11:24). Pesquisa: "arroz". Latências padrão: Aurora 300 ms, SuperVila 500 ms, Empório Sol 700 ms, Max 900 ms, Ipê 1200 ms. Timeout 3 s; novas tentativas após 0,5 s, 1 s e 2 s.

## Experimentos 1 e 2 — sequencial × concorrente (10 rodadas, latências padrão)

| Experimento | Modo | Média | Mín. | Máx. | Desvio padrão | Visto pelo cliente | Previsto |
|---|---|---|---|---|---|---|---|
| 1 | Sequencial | 3,65 s | 3,56 s | 3,79 s | 75 ms | 3,66 s | 3,60 s (soma) |
| 2 | Concorrente | 1,20 s | 1,07 s | 1,37 s | 123 ms | 1,20 s | 1,20 s (maior) |

Speedup médio: **3,1×** (limite teórico com essas latências: 3,0×). "Visto pelo cliente" inclui a ida e volta TCP entre cliente e agregador.

## Experimento 3 — simulação de latência (5 rodadas por cenário)

| Cenário | Latências | Sequencial | Previsto (soma) | Concorrente | Previsto (maior) | Speedup |
|---|---|---|---|---|---|---|
| Sem atraso | 0 ms em todos | 45 ms | 0 ms | 7 ms | 0 ms | 6,0× |
| 200 ms | 200 ms em todos | 1,04 s | 1,00 s | 229 ms | 200 ms | 4,5× |
| 500 ms | 500 ms em todos | 2,60 s | 2,50 s | 569 ms | 500 ms | 4,6× |
| 1000 ms | 1000 ms em todos | 5,01 s | 5,00 s | 1,13 s | 1,00 s | 4,4× |
| Padrão | 300 a 1200 ms | 3,59 s | 3,60 s | 1,16 s | 1,20 s | 3,1× |
| Um lento | padrão, Ipê com 2500 ms | 4,91 s | 4,90 s | 2,68 s | 2,50 s | 1,8× |
| Um em timeout | padrão, Ipê com 4000 ms | 5,50 s | 5,40 s | 3,01 s | 3,00 s | 1,8× |

O previsto limita cada latência ao timeout de 3,00 s.

## Experimento 4 — múltiplos clientes simultâneos (3 pesquisas por cliente, latências padrão)

| Modo | Clientes | Pesquisas | Resposta média | Resposta máx. | Tempo total | Vazão | Falhas |
|---|---|---|---|---|---|---|---|
| Sequencial | 1 | 3 | 3,65 s | 3,86 s | 10,94 s | 0,27 pesquisas/s | 0 |
| Sequencial | 2 | 6 | 3,73 s | 3,92 s | 11,38 s | 0,53 pesquisas/s | 0 |
| Sequencial | 4 | 12 | 3,60 s | 3,93 s | 10,87 s | 1,10 pesquisas/s | 0 |
| Sequencial | 8 | 24 | 3,65 s | 3,93 s | 11,45 s | 2,10 pesquisas/s | 0 |
| Sequencial | 16 | 48 | 3,65 s | 3,99 s | 11,66 s | 4,12 pesquisas/s | 0 |
| Sequencial | 32 | 96 | 3,66 s | 4,03 s | 11,60 s | 8,28 pesquisas/s | 0 |
| Concorrente | 1 | 3 | 1,23 s | 1,33 s | 3,69 s | 0,81 pesquisas/s | 0 |
| Concorrente | 2 | 6 | 1,22 s | 1,37 s | 3,70 s | 1,62 pesquisas/s | 0 |
| Concorrente | 4 | 12 | 1,20 s | 1,34 s | 3,86 s | 3,11 pesquisas/s | 0 |
| Concorrente | 8 | 24 | 1,24 s | 1,45 s | 4,03 s | 5,96 pesquisas/s | 0 |
| Concorrente | 16 | 48 | 1,28 s | 1,62 s | 4,31 s | 11,13 pesquisas/s | 0 |
| Concorrente | 32 | 96 | 1,24 s | 1,45 s | 4,03 s | 23,83 pesquisas/s | 0 |

Cada cliente abre sua própria conexão TCP com o agregador e faz as pesquisas uma após a outra; todos começam juntos (barreira). Resposta = tempo visto pelo cliente.

## Experimento 5 — indisponibilidade do Ipê (3 rodadas por cenário)

| Cenário | O que acontece | Modo | Tempo médio | Mercados com resposta | Tentativas no Ipê | Erro informado |
|---|---|---|---|---|---|---|
| Todos no ar | referência | Sequencial | 3,69 s | 5 de 5 | 1 | — |
| Todos no ar | referência | Concorrente | 1,21 s | 5 de 5 | 1 | — |
| Fora do ar antes | Ipê desativado antes da pesquisa | Sequencial | 5,97 s | 4 de 5 | 4 | fora do ar (4 tentativas) |
| Fora do ar antes | Ipê desativado antes da pesquisa | Concorrente | 3,52 s | 4 de 5 | 4 | fora do ar (4 tentativas) |
| Cai durante | Ipê desativado 0,3 s depois do início | Sequencial | 5,85 s | 4 de 5 | 4 | fora do ar (4 tentativas) |
| Cai durante | Ipê desativado 0,3 s depois do início | Concorrente | 3,83 s | 4 de 5 | 4 | fora do ar (4 tentativas) |
| Cai e volta | Ipê cai em 0,3 s e volta em 1,0 s | Sequencial | 3,78 s | 5 de 5 | 1 | — |
| Cai e volta | Ipê cai em 0,3 s e volta em 1,0 s | Concorrente | 3,03 s | 5 de 5 | 3 | — |
