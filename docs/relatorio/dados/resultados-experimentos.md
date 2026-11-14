# Resultados dos experimentos obrigatórios

Gerado por `backend/experimentos/executar.py` a partir dos CSV desta pasta (14/11/2026 11:11). Pesquisa: "arroz". Latências padrão: Aurora 300 ms, SuperVila 500 ms, Empório Sol 700 ms, Max 900 ms, Ipê 1200 ms. Timeout 3 s; novas tentativas após 0,5 s, 1 s e 2 s.

## Experimentos 1 e 2 — sequencial × concorrente (10 rodadas, latências padrão)

| Experimento | Modo | Média | Mín. | Máx. | Desvio padrão | Visto pelo cliente | Previsto |
|---|---|---|---|---|---|---|---|
| 1 | Sequencial | 3,71 s | 3,39 s | 3,94 s | 149 ms | 3,72 s | 3,60 s (soma) |
| 2 | Concorrente | 1,16 s | 1,04 s | 1,35 s | 107 ms | 1,17 s | 1,20 s (maior) |

Speedup médio: **3,2×** (limite teórico com essas latências: 3,0×). "Visto pelo cliente" inclui a ida e volta TCP entre cliente e agregador.

## Experimento 3 — simulação de latência (5 rodadas por cenário)

| Cenário | Latências | Sequencial | Previsto (soma) | Concorrente | Previsto (maior) | Speedup |
|---|---|---|---|---|---|---|
| Sem atraso | 0 ms em todos | 13 ms | 0 ms | 8 ms | 0 ms | 1,6× |
| 200 ms | 200 ms em todos | 1,04 s | 1,00 s | 233 ms | 200 ms | 4,5× |
| 500 ms | 500 ms em todos | 2,57 s | 2,50 s | 565 ms | 500 ms | 4,6× |
| 1000 ms | 1000 ms em todos | 4,98 s | 5,00 s | 1,13 s | 1,00 s | 4,4× |
| Padrão | 300 a 1200 ms | 3,62 s | 3,60 s | 1,15 s | 1,20 s | 3,1× |
| Um lento | padrão, Ipê com 2500 ms | 5,14 s | 4,90 s | 2,50 s | 2,50 s | 2,1× |
| Um em timeout | padrão, Ipê com 4000 ms | 5,49 s | 5,40 s | 3,01 s | 3,00 s | 1,8× |

O previsto limita cada latência ao timeout de 3,00 s.

## Experimento 4 — múltiplos clientes simultâneos (3 pesquisas por cliente, latências padrão)

| Modo | Clientes | Pesquisas | Resposta média | Resposta máx. | Tempo total | Vazão | Falhas |
|---|---|---|---|---|---|---|---|
| Sequencial | 1 | 3 | 3,64 s | 3,76 s | 10,93 s | 0,27 pesquisas/s | 0 |
| Sequencial | 2 | 6 | 3,60 s | 3,82 s | 10,85 s | 0,55 pesquisas/s | 0 |
| Sequencial | 4 | 12 | 3,65 s | 3,92 s | 11,27 s | 1,06 pesquisas/s | 0 |
| Sequencial | 8 | 24 | 3,61 s | 3,96 s | 11,30 s | 2,12 pesquisas/s | 0 |
| Sequencial | 16 | 48 | 3,59 s | 3,93 s | 11,28 s | 4,25 pesquisas/s | 0 |
| Sequencial | 32 | 96 | 3,66 s | 3,99 s | 11,52 s | 8,33 pesquisas/s | 0 |
| Concorrente | 1 | 3 | 1,22 s | 1,32 s | 3,67 s | 0,82 pesquisas/s | 0 |
| Concorrente | 2 | 6 | 1,23 s | 1,38 s | 3,77 s | 1,59 pesquisas/s | 0 |
| Concorrente | 4 | 12 | 1,23 s | 1,39 s | 3,80 s | 3,16 pesquisas/s | 0 |
| Concorrente | 8 | 24 | 1,25 s | 1,39 s | 3,91 s | 6,15 pesquisas/s | 0 |
| Concorrente | 16 | 48 | 1,22 s | 1,44 s | 4,10 s | 11,70 pesquisas/s | 0 |
| Concorrente | 32 | 96 | 1,25 s | 1,47 s | 4,06 s | 23,66 pesquisas/s | 0 |

Cada cliente abre sua própria conexão TCP com o agregador e faz as pesquisas uma após a outra; todos começam juntos (barreira). Resposta = tempo visto pelo cliente.

## Experimento 5 — indisponibilidade do Ipê (3 rodadas por cenário)

| Cenário | O que acontece | Modo | Tempo médio | Mercados com resposta | Tentativas no Ipê | Erro informado |
|---|---|---|---|---|---|---|
| Todos no ar | referência | Sequencial | 3,59 s | 5 de 5 | 1 | — |
| Todos no ar | referência | Concorrente | 1,24 s | 5 de 5 | 1 | — |
| Fora do ar antes | Ipê desativado antes da pesquisa | Sequencial | 6,00 s | 4 de 5 | 4 | fora do ar (4 tentativas) |
| Fora do ar antes | Ipê desativado antes da pesquisa | Concorrente | 3,52 s | 4 de 5 | 4 | fora do ar (4 tentativas) |
| Cai durante | Ipê desativado 0,3 s depois do início | Sequencial | 5,97 s | 4 de 5 | 4 | fora do ar (4 tentativas) |
| Cai durante | Ipê desativado 0,3 s depois do início | Concorrente | 3,82 s | 4 de 5 | 4 | fora do ar (4 tentativas) |
| Cai e volta | Ipê cai em 0,3 s e volta em 1,0 s | Sequencial | 3,68 s | 5 de 5 | 1 | — |
| Cai e volta | Ipê cai em 0,3 s e volta em 1,0 s | Concorrente | 3,04 s | 5 de 5 | 3 | — |
