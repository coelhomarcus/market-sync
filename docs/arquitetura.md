# Arquitetura

## Visão geral

Figura: `docs/relatorio/figuras/fig-02-arquitetura.png` (gerada por `scripts/diagramas.py`).

Os três componentes pedidos na seção 6 do enunciado:

| Componente | Processo | Porta |
|---|---|---|
| **Cliente** | `cliente/` (terminal, TCP) ou a interface web (loja e painel) | — |
| **Agregador** | `agregador.api_web` (FastAPI + servidor TCP no mesmo processo) | 5050 (TCP), 8000 (HTTP/WebSocket) |
| **Serviços independentes** | 5 × `mercados.servidor`, um processo por supermercado | 5001–5005 (TCP) |

```mermaid
flowchart LR
    CLI[cliente<br/>terminal]
    subgraph Navegador
        L[Loja /]
        P[Painel /painel]
    end
    subgraph Agregador["Agregador (1 processo)"]
        TS[Servidor TCP :5050<br/>uma thread por cliente]
        R[Rotas HTTP :8000]
        S[estrategias.py<br/>sequential / concurrent]
        T[consulta_mercado.py<br/>com retry]
        E[EventBus]
        MS[MetricsStore]
    end
    subgraph Mercados["5 processos independentes"]
        M1[Mercado Aurora :5001<br/>aurora.db]
        M2[SuperVila :5002<br/>supervila.db]
        M3[Empório Sol :5003<br/>emporio-sol.db]
        M4[Max Atacarejo :5004<br/>max-atacarejo.db]
        M5[Mercadinho Ipê :5005<br/>ipe.db]
    end

    CLI -- TCP / JSON por linha --> TS
    L -- HTTP/JSON --> R
    P -- HTTP/JSON --> R
    TS --> S
    R --> S --> T
    T -- TCP --> M1 & M2 & M3 & M4 & M5
    T -. eventos .-> E
    S -. registro .-> MS
    E -- WebSocket --> P
    E -- WebSocket --> L
```

Os protocolos do sistema:

| Trecho | Protocolo | Por quê |
|---|---|---|
| Cliente de terminal → agregador | **TCP puro**, uma mensagem JSON por linha (`operacao`, `produto`...) | Requisito do trabalho: cliente e agregador são processos distintos que conversam por socket. Formato do enunciado (seção 8). |
| Navegador → agregador | HTTP/1.1 + JSON | Rotas REST simples, fáceis de testar no navegador e no `/docs` do FastAPI. |
| Agregador → mercados | **TCP puro**, uma mensagem JSON por linha | Requisito do trabalho; mostra o que o HTTP esconde (fronteiras de mensagem, timeouts, conexão recusada). |
| Agregador → painel | WebSocket | Empurra eventos assim que acontecem, sem o navegador ficar perguntando. |

## Componentes

| Arquivo | Responsabilidade |
|---|---|
| `comum/config.py` | Lista dos mercados (id, nome, porta, latência inicial, perfil de preço), timeout e retry. |
| `comum/protocolo.py` | Protocolo: cada mensagem é um JSON numa linha. `send` / `receive`. |
| `mercados/catalogo.py` | Catálogo gerado: 95 tipos × 10 marcas fictícias × sabores × tamanhos = 1.740 SKUs. |
| `mercados/gerar_bancos.py` | Gera um SQLite por mercado (sortimento próprio, preço, estoque e EAN). |
| `mercados/banco.py` | Consultas SQL de um mercado (busca e cesta). |
| `mercados/servidor.py` | Servidor TCP de um mercado (`socketserver.ThreadingTCPServer`): uma thread por conexão. Simula latência e queda. |
| `agregador/consulta_mercado.py` | `query_market`: conecta, envia, espera a resposta e mede. Se o mercado está fora do ar, tenta de novo (0,5 s → 1 s → 2 s). Nunca lança exceção. |
| `agregador/estrategias.py` | `sequential()` (um por vez) e `concurrent()` (`ThreadPoolExecutor`, uma thread por mercado). |
| `agregador/agregador.py` | `Aggregator.execute`: roda a estratégia, mede tempo/CPU/threads e publica os eventos. Também `markets_status` e `configure_market` (STATUS/CONFIG por TCP), usados pelo HTTP e pelo TCP. |
| `agregador/servidor_tcp.py` | Servidor TCP do agregador (porta 5050): operações `consultar`, `comparar`, `cesta`, `mercados`, `configurar`, `encerrar`. Uma thread por cliente. |
| `agregador/consolidacao.py` | Junta as ofertas: menor preço, ordenação, paginação, cesta mais barata. |
| `agregador/eventos.py` | Entrega os eventos das threads de consulta aos WebSockets (asyncio). |
| `agregador/metricas.py` | Histórico em memória, médias e CSV. |
| `agregador/api_web.py` | Rotas FastAPI; ao iniciar, liga o servidor TCP da porta 5050 no mesmo processo, compartilhando o agregador (as pesquisas do terminal aparecem no painel). |
| `iniciar.py` | Sobe os 5 mercados e o agregador como subprocessos e encerra tudo no Ctrl+C. |
| `cliente/` | Cliente de terminal: abre uma conexão TCP com o agregador e a mantém durante a sessão. Classe `ClienteAgregador` reaproveitada pelos experimentos. |
| `experimentos/` | Executa os 5 experimentos obrigatórios pelo cliente TCP e gera CSV, tabelas e gráficos. |
| `frontend/` | React + TypeScript + Tailwind. Loja, cesta e página "Comparar modos" (corrida, cenários dos mercados, eventos). Nomes e cores dos mercados vêm de `/api/markets`. |

## Modelo de threads

```mermaid
flowchart TB
    subgraph Agregador
        EL[Event loop asyncio<br/>WebSockets]
        AP[Pool de threads do FastAPI<br/>executa as rotas def]
        TA[Servidor TCP :5050<br/>thread accept + uma thread por cliente]
        TP[ThreadPoolExecutor<br/>consulta_0 … consulta_4]
    end
    subgraph "Cada mercado"
        AC[Thread principal<br/>accept()]
        H1[Thread da conexão 1]
        H2[Thread da conexão 2]
    end
    AP -- modo concorrente --> TP
    TA -- modo concorrente --> TP
    TP -- connect --> AC
    AC -- cria --> H1 & H2
    TP -. call_soon_threadsafe .-> EL
```

- As rotas de consulta são funções `def` (não `async`). O FastAPI as roda num pool de threads, e as esperas de socket não travam o event loop que serve os WebSockets.
- O servidor TCP do agregador roda numa thread própria (`serve_forever`), que só faz `accept()`. Cada cliente conectado ganha uma thread (`ThreadingTCPServer`), que lê os pedidos daquele cliente, um por vez, até ele encerrar. Com 8 clientes conectados há 8 dessas threads, e cada uma pode criar mais 5 no modo concorrente (Experimento 4).
- No **modo sequencial**, a própria thread da rota (ou do cliente TCP) faz as 5 consultas em sequência (o painel mostra "Threads usadas: 1").
- No **modo concorrente**, a rota cria um `ThreadPoolExecutor` com 5 workers; cada um faz uma consulta, e `as_completed` recolhe as respostas na ordem em que chegam ("Threads usadas: 5").
- Os eventos são gerados nessas threads e entregues ao event loop com `loop.call_soon_threadsafe`, a forma segura de falar com o asyncio a partir de outra thread.
- No mercado, o `accept()` roda na thread principal e cada conexão ganha uma `threading.Thread`. Assim, o mercado atende consultas simultâneas (por exemplo, duas abas fazendo busca ao mesmo tempo). O SQLite abre uma conexão por requisição, porque o objeto de conexão não pode ser compartilhado entre threads.

## Sequência de uma pesquisa (cliente de terminal, modo concorrente)

Figura: `docs/relatorio/figuras/fig-12-sequencia.png`.

```mermaid
sequenceDiagram
    actor U as Usuário
    participant C as Cliente (terminal)
    participant A as Agregador (thread do cliente)
    participant T as Threads de consulta
    participant M1 as Aurora :5001
    participant M5 as Ipê :5005 (fora do ar)

    U->>C: digita "arroz"
    C->>A: connect() porta 5050
    C->>A: {"operacao":"consultar","produto":"arroz","modo":"concorrente"}
    A->>T: cria 5 threads
    par uma thread por supermercado
        T->>M1: {"cmd":"SEARCH","q":"arroz"}
        M1-->>T: {"ok":true,"data":{"items":[...]}} (~300 ms)
    and
        T->>M5: {"cmd":"SEARCH","q":"arroz"}
        M5--xT: fecha sem responder
        T->>M5: novas tentativas após 0,5 s, 1 s, 2 s
    end
    T-->>A: 5 resultados (4 ok, 1 erro)
    A->>A: agrupa, ordena por preço, marca o menor
    A-->>C: {"status":"parcial","resultados":[...],"tempo_total_ms":...}
    C-->>U: tabela com ★ no menor preço
    C->>A: {"operacao":"encerrar"}
    A-->>C: {"status":"sucesso"} e fecha a conexão
```

## Sequência: sequencial × concorrente

```mermaid
sequenceDiagram
    participant U as Cliente
    participant A as Agregador
    participant M1 as Aurora (300 ms)
    participant M2 as SuperVila (500 ms)
    participant M5 as Ipê (1200 ms)

    Note over U,M5: consultar "arroz", modo sequencial
    U->>A: {"operacao":"consultar",...,"modo":"sequencial"}
    A->>M1: SEARCH
    M1-->>A: itens (após 300 ms)
    A->>M2: SEARCH
    M2-->>A: itens (após 500 ms)
    A->>M5: SEARCH
    M5-->>A: itens (após 1200 ms)
    A-->>U: resposta (≈ soma das latências)

    Note over U,M5: consultar "arroz", modo concorrente
    U->>A: {"operacao":"consultar",...,"modo":"concorrente"}
    par thread consulta_0
        A->>M1: SEARCH
    and thread consulta_1
        A->>M2: SEARCH
    and thread consulta_4
        A->>M5: SEARCH
    end
    M1-->>A: itens (300 ms)
    M2-->>A: itens (500 ms)
    M5-->>A: itens (1200 ms)
    A-->>U: resposta (≈ maior latência)
```

## Decisões de projeto

- **Latência simulada.** Em `localhost`, uma consulta TCP leva menos de 1 ms e a diferença entre os modos desapareceria no ruído. Cada mercado dorme um tempo configurável (±15% de variação) antes de responder, imitando servidores remotos. A latência pode ser alterada em tempo de execução pelo comando `CONFIG`.
- **Uma conexão por consulta.** O cliente abre, usa e fecha a conexão. É simples, deixa explícito o custo do `connect` e evita compartilhar sockets entre threads. O servidor aceita várias mensagens na mesma conexão, então uma evolução com pool de conexões é possível.
- **Erros como dados.** `query_market` nunca levanta exceção: timeout, conexão recusada e mercado fora do ar viram `MarketResult(ok=False, error=...)`. A estratégia concorrente nunca perde as respostas boas por causa de uma ruim.
- **Servidor TCP e HTTP no mesmo processo.** O agregador é um processo só, com as duas portas. Assim o cliente de terminal, a loja e o painel compartilham o mesmo histórico de métricas e os mesmos eventos: uma pesquisa feita no terminal aparece ao vivo no painel. O servidor TCP também roda sozinho (`python -m agregador.servidor_tcp`), sem a parte web.
- **Conexão persistente no cliente, curta nos mercados.** O cliente de terminal mantém uma conexão durante a sessão (evita um handshake por pesquisa e mostra o servidor atendendo vários pedidos na mesma conexão). Do agregador para os mercados é uma conexão por consulta, como descrito acima.
- **"Fora do ar" sem matar o processo.** O mercado continua aceitando conexões, mas fecha as de consulta sem responder, inclusive as que estavam esperando a latência quando ele caiu (a espera é um `threading.Event`, acordado na hora da queda); os comandos administrativos (`CONFIG`, `STATUS`) continuam funcionando para trazê-lo de volta. Para simular o processo morto de verdade, basta encerrar o processo: o agregador recebe "conexão recusada".
- **Bancos de tamanho realista.** Cada mercado guarda de 1.369 a 1.689 produtos. Uma busca pelo catálogo inteiro trafega cerca de 1,5 MB pelos cinco sockets, e o agregador junta perto de 7.700 ofertas antes de paginar.
- **Medição de recursos.** Cada mercado devolve, junto com a resposta, a CPU gasta pela thread que a atendeu (`time.thread_time()`, que não conta o sleep da latência). O agregador soma a CPU das próprias threads de consulta (também `time.thread_time()`) e conta quantas threads distintas conversaram com os mercados (1 no sequencial, 5 no concorrente), e grava tudo no registro da requisição.
- **Métricas em memória.** Suficiente para a demonstração; o CSV preserva os dados para o relatório.
- **Sem ORM no front.** Quem acessa o SQLite é o Python de cada mercado; o navegador só conversa com o agregador por HTTP e WebSocket.
