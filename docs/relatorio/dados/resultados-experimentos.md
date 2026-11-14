# Resultados dos experimentos obrigatórios

Gerado por `experiments/` a partir dos CSV desta pasta (14/11/2026 16:52). Pesquisa: "arroz". Latências padrão: Aurora 300 ms, SuperVila 500 ms, Empório Sol 700 ms, Max 900 ms, Ipê 1200 ms. Timeout 3 s; novas tentativas após 0,5 s, 1 s e 2 s.

## Experimento 1 — consulta sequencial (10 rodadas, latências padrão)

| Média | Mín. | Máx. | Desvio padrão | Visto pelo cliente | Previsto (soma) |
|---|---|---|---|---|---|
| 3,65 s | 3,43 s | 3,92 s | 177 ms | 3,66 s | 3,60 s |

## Experimento 2 — consulta concorrente (10 rodadas, latências padrão)

| Média | Mín. | Máx. | Desvio padrão | Visto pelo cliente | Previsto (maior) |
|---|---|---|---|---|---|
| 1,19 s | 1,03 s | 1,32 s | 113 ms | 1,20 s | 1,20 s |

Comparando com o Experimento 1: speedup médio de **3,1×** (limite teórico com essas latências: 3,0×). "Visto pelo cliente" inclui a ida e volta TCP entre cliente e agregador.

## Experimento 3 — simulação de latência (5 rodadas por cenário)

| Cenário | Latências | Sequencial | Previsto (soma) | Concorrente | Previsto (maior) | Speedup |
|---|---|---|---|---|---|---|
| Sem atraso | 0 ms em todos | 10 ms | 0 ms | 3 ms | 0 ms | 3,0× |
| 200 ms | 200 ms em todos | 1,02 s | 1,00 s | 231 ms | 200 ms | 4,4× |
| 500 ms | 500 ms em todos | 2,48 s | 2,50 s | 562 ms | 500 ms | 4,4× |
| 1000 ms | 1000 ms em todos | 5,05 s | 5,00 s | 1,09 s | 1,00 s | 4,6× |
| Padrão | 300 a 1200 ms | 3,65 s | 3,60 s | 1,18 s | 1,20 s | 3,1× |
| Um lento | padrão, Ipê com 2500 ms | 4,87 s | 4,90 s | 2,56 s | 2,50 s | 1,9× |
| Um em timeout | padrão, Ipê com 4000 ms | 5,43 s | 5,40 s | 3,00 s | 3,00 s | 1,8× |

O previsto limita cada latência ao timeout de 3,00 s.

## Experimento 4 — múltiplos clientes simultâneos (3 pesquisas por cliente, latências padrão)

| Modo | Clientes | Pesquisas | Resposta média | Resposta máx. | Tempo total | Vazão | Falhas |
|---|---|---|---|---|---|---|---|
| Sequencial | 1 | 3 | 3,53 s | 3,64 s | 10,59 s | 0,28 pesquisas/s | 0 |
| Sequencial | 2 | 6 | 3,61 s | 3,86 s | 10,91 s | 0,55 pesquisas/s | 0 |
| Sequencial | 4 | 12 | 3,58 s | 3,91 s | 10,84 s | 1,11 pesquisas/s | 0 |
| Sequencial | 8 | 24 | 3,68 s | 3,92 s | 11,44 s | 2,10 pesquisas/s | 0 |
| Sequencial | 16 | 48 | 3,65 s | 4,00 s | 11,48 s | 4,18 pesquisas/s | 0 |
| Sequencial | 32 | 96 | 3,66 s | 4,00 s | 11,47 s | 8,37 pesquisas/s | 0 |
| Concorrente | 1 | 3 | 1,09 s | 1,12 s | 3,28 s | 0,92 pesquisas/s | 0 |
| Concorrente | 2 | 6 | 1,18 s | 1,35 s | 3,76 s | 1,60 pesquisas/s | 0 |
| Concorrente | 4 | 12 | 1,20 s | 1,31 s | 3,67 s | 3,27 pesquisas/s | 0 |
| Concorrente | 8 | 24 | 1,25 s | 1,37 s | 3,89 s | 6,18 pesquisas/s | 0 |
| Concorrente | 16 | 48 | 1,20 s | 1,38 s | 3,97 s | 12,10 pesquisas/s | 0 |
| Concorrente | 32 | 96 | 1,20 s | 1,41 s | 4,00 s | 23,97 pesquisas/s | 0 |

Cada cliente abre sua própria conexão TCP com o agregador e faz as pesquisas uma após a outra; todos começam juntos (barreira). Resposta = tempo visto pelo cliente.

## Experimento 5 — indisponibilidade de serviço, alvo SuperVila (3 rodadas por cenário)

| Cenário | O que acontece | Modo | Tempo médio | Mercados com resposta | Tentativas (SuperVila) | Erro informado |
|---|---|---|---|---|---|---|
| Todos no ar | referência | Sequencial | 3,63 s | 5 de 5 | 1 | — |
| Todos no ar | referência | Concorrente | 1,14 s | 5 de 5 | 1 | — |
| Fora do ar antes | SuperVila sai do ar antes da pesquisa | Sequencial | 6,67 s | 4 de 5 | 4 | fora do ar (4 tentativas) |
| Fora do ar antes | SuperVila sai do ar antes da pesquisa | Concorrente | 3,51 s | 4 de 5 | 4 | fora do ar (4 tentativas) |
| Cai durante | SuperVila sai do ar 0,3 s depois do início | Sequencial | 6,74 s | 4 de 5 | 4 | fora do ar (4 tentativas) |
| Cai durante | SuperVila sai do ar 0,3 s depois do início | Concorrente | 3,82 s | 4 de 5 | 4 | fora do ar (4 tentativas) |
| Cai e volta | SuperVila cai em 0,3 s e volta em 1,0 s | Sequencial | 5,25 s | 5 de 5 | 3 | — |
| Cai e volta | SuperVila cai em 0,3 s e volta em 1,0 s | Concorrente | 2,33 s | 5 de 5 | 3 | — |
