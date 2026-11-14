# Comparador de Preços de Supermercados — Relatório Técnico

Trabalho 1 de Sistemas Distribuídos — Engenharia de Requisitos e Desenvolvimento de um Agregador Concorrente (Tema 1)

14/11/2026

## Resumo

Consultar cinco supermercados ao mesmo tempo, com uma thread por supermercado, reduziu o tempo de uma pesquisa de 3,71 s para 1,16 s: um speedup de 3,2×.

Este relatório descreve um comparador de preços cliente-servidor desenvolvido em Python. Um **cliente de terminal** envia pesquisas a um **agregador** por socket TCP, com mensagens JSON no formato `{"operacao": "consultar", "produto": "arroz"}`. O agregador consulta cinco **supermercados**, cada um um processo independente com porta TCP e base SQLite próprias, de forma sequencial (um de cada vez) ou concorrente (`ThreadPoolExecutor`, uma thread por supermercado), consolida as ofertas, ordena por preço e aponta o menor. Uma interface web (loja e painel) usa o mesmo agregador por HTTP e WebSocket.

Os cinco experimentos obrigatórios, feitos de ponta a ponta pelo cliente TCP, confirmam o modelo esperado: o tempo sequencial se aproxima da soma das latências dos supermercados, e o concorrente, da maior delas. Com latências iguais o ganho chegou a 4,6×. Trinta e dois clientes simultâneos foram atendidos no mesmo tempo que um só, e um supermercado que cai durante a pesquisa não impede a resposta com os outros quatro.

**Palavras-chave:** sockets TCP, multithreading, sistemas distribuídos, agregador, comparação de preços.

## 1. Introdução

Comparadores de preço, buscadores de passagens e agregadores em geral precisam consultar várias fontes independentes antes de responder ao usuário. Quando essas consultas são feitas uma após a outra, o tempo de resposta cresce com o número de fontes. Quando são feitas ao mesmo tempo, ele passa a depender apenas da fonte mais lenta.

Este trabalho implementa o Tema 1, o comparador de preços de supermercados, para estudar esse efeito com comunicação real por sockets TCP entre processos e com threads.

### 1.1 Objetivo geral

Desenvolver uma aplicação cliente-servidor que realize consultas sequenciais e concorrentes a diferentes serviços independentes, utilizando sockets TCP e multithreading.

### 1.2 Objetivos específicos

1. Especificar a aplicação com técnicas de Engenharia de Software: problema, escopo, atores, requisitos funcionais e não funcionais, restrições e critérios de aceitação (seção 2).
2. Modelar casos de uso, arquitetura, sequência de uma operação e protocolo de aplicação (seção 3).
3. Implementar a comunicação entre processos com sockets TCP e um agregador com consultas sequenciais e concorrentes (seção 4).
4. Testar o sistema de forma automatizada (seção 5).
5. Realizar os cinco experimentos obrigatórios e analisar o impacto da concorrência no desempenho (seções 6 e 7).

### 1.3 Organização

A seção 2 resume os requisitos (o documento completo está em `docs/requisitos.md`). A seção 3 apresenta a modelagem e o protocolo. A seção 4 descreve a implementação, a seção 5 os testes, a seção 6 os experimentos e a seção 7 discute os resultados. A seção 8 conclui. Os apêndices trazem as instruções de execução e o roteiro da demonstração.

## 2. Requisitos

### 2.1 Problema, objetivo e escopo

**Problema.** Para saber onde um produto é mais barato, o consumidor precisa pesquisar em cada supermercado e comparar os preços. Cada supermercado é um sistema independente, com catálogo, preços e tempo de resposta próprios. Um comparador que consulta um supermercado de cada vez faz o usuário esperar a soma dos tempos de todos; como as consultas são independentes, elas podem ser feitas ao mesmo tempo.

**Objetivo do sistema.** Permitir que o usuário informe um produto e receba, numa única resposta, os preços em pelo menos quatro supermercados independentes, ordenados do menor para o maior e com o menor preço identificado, consultando os supermercados por TCP nos modos sequencial e concorrente e medindo o tempo de cada um.

**Escopo.** Cinco supermercados simulados (processos TCP com base SQLite própria), um agregador, um cliente de terminal (TCP) e uma interface web; pesquisa, comparação de preços, menor preço, comparação de cestas (evolução sugerida), medição de tempos, tratamento de falhas e um script com os cinco experimentos. Ficam de fora preços reais, login, pagamento e distribuição em várias máquinas.

### 2.2 Atores

| Ator | Tipo | Descrição |
| --- | --- | --- |
| Consumidor | Principal | Pesquisa produtos, compara preços e monta cestas, pelo cliente de terminal ou pela loja web. |
| Avaliador / Operador | Principal | Compara os modos, roda os experimentos, altera latências e derruba supermercados para observar o sistema. |
| Serviço de supermercado | Secundário | Cada um dos cinco processos servidores TCP, que respondem com dados da própria base. |

### 2.3 Requisitos funcionais

| ID | Requisito |
| --- | --- |
| RF01 | Permitir que o usuário informe o produto a pesquisar e o modo de consulta. |
| RF02 | Consultar pelo menos quatro supermercados independentes (são cinco). |
| RF03 | Permitir consultas sequenciais: um supermercado de cada vez. |
| RF04 | Permitir consultas concorrentes: todos ao mesmo tempo, uma thread por supermercado. |
| RF05 | Apresentar o preço de cada produto encontrado em cada supermercado. |
| RF06 | Ordenar os resultados por preço (produtos pelo menor preço; ofertas de cada produto do mais barato ao mais caro). |
| RF07 | Identificar o supermercado com o menor preço de cada produto. |
| RF08 | Registrar o tempo de execução de cada pesquisa, total e por supermercado. |
| RF09 | Comparar as duas estratégias para a mesma pesquisa, informando o speedup. |
| RF10 | Informar quais supermercados não responderam e o motivo, sem descartar os resultados dos demais. |
| RF11 | Comparar uma cesta de compras e identificar o supermercado de menor custo total (evolução sugerida). |
| RF12 | Permitir alterar a latência simulada e a disponibilidade de cada supermercado durante a execução. |
| RF13 | Executar os experimentos obrigatórios automaticamente, salvando CSV e gráficos. |
| RF14 | Exibir em tempo real os eventos de cada conexão TCP (painel web). |
| RF15 | Exportar o histórico de métricas em CSV. |
| RF16 | Medir o consumo de CPU e threads de cada modo. |

### 2.4 Requisitos não funcionais

| ID | Requisito | Como é atendido |
| --- | --- | --- |
| RNF01 | A comunicação entre os componentes deverá usar sockets TCP. | Cliente → agregador na porta 5050; agregador → supermercados nas portas 5001–5005. |
| RNF02 | A estratégia concorrente deverá usar threads. | `ThreadPoolExecutor` com uma thread por supermercado. |
| RNF03 | Os servidores deverão atender múltiplas conexões simultaneamente. | Agregador e supermercados com uma thread por conexão (`ThreadingTCPServer`). Experimento 4. |
| RNF04 | O sistema deverá tratar falhas de comunicação. | Timeout de 3 s, até 3 novas tentativas com espera crescente, resultado parcial. Experimento 5. |
| RNF05 | A aplicação deverá permitir experimentos de desempenho. | Latência configurável em tempo de execução; `experimentos/`. |
| RNF06 | O protocolo deverá ser documentado e robusto à fragmentação do TCP. | JSON por linha, testado com envio em pedaços de 7 bytes. |
| RNF07 | Cada supermercado deverá ser um processo independente. | 5 processos, portas e bases próprias. |
| RNF08 | Com as latências padrão, a pesquisa concorrente deverá levar perto da maior latência e a sequencial perto da soma. | Experimentos 1 e 2. |
| RNF09 | O sistema deverá ter testes automatizados. | 55 testes `pytest`. |
| RNF10 | As interfaces deverão estar em português e destacar o menor preço e o tempo gasto. | Terminal com ★ e cores; loja responsiva. |

### 2.5 Restrições

- Python 3.12; a comunicação TCP usa só a biblioteca padrão (`socket`, `socketserver`, `threading`, `concurrent.futures`).
- Comunicação real por sockets: nenhuma consulta é simulada sem rede.
- Supermercados, marcas, preços e estoques fictícios, gerados com semente fixa.
- Latência de rede simulada por uma espera configurável (em `localhost` a rede responde em menos de 1 ms).
- Todos os processos na mesma máquina, em portas distintas; endereços configuráveis por variáveis de ambiente.
- Trabalho em dupla, apresentação de 15 a 20 minutos em 16/11/2026.

### 2.6 Critérios de aceitação

| ID | Critério | Verificação |
| --- | --- | --- |
| CA01 | Ao pesquisar "arroz" no cliente de terminal, o usuário recebe os preços dos 5 supermercados numa única resposta. | Demonstração; teste automatizado |
| CA02 | Produtos e ofertas aparecem do menor para o maior preço, com o mais barato destacado. | Teste automatizado |
| CA03 | Com as latências padrão, sequencial ≥ 95% da soma das latências; concorrente abaixo da maior latência + 250 ms. | Teste automatizado; Exp. 1 e 2 |
| CA04 | Toda resposta informa o tempo total e o de cada supermercado. | Formato da resposta |
| CA05 | Com um supermercado fora do ar (antes ou durante a pesquisa), o usuário recebe os outros 4 com `status: "parcial"` e o motivo. | Testes automatizados; Exp. 5 |
| CA06 | Oito clientes simultâneos são atendidos, e o tempo total fica próximo ao de um cliente. | Teste automatizado; Exp. 4 |
| CA07 | Pedidos inválidos recebem erro com código, e a conexão continua utilizável. | Testes automatizados |
| CA08 | `lsof` mostra o agregador (5050) e os cinco supermercados (5001–5005) escutando, em processos distintos. | Demonstração |
| CA09 | `python -m experimentos` executa os cinco experimentos e gera tabelas e gráficos sem intervenção. | Execução do script |

Todos os critérios foram verificados (seções 5 e 6).

## 3. Modelagem

### 3.1 Casos de uso

![Figura 1. Diagrama de casos de uso](figuras/fig-01-casos-de-uso.png)

*Figura 1. Diagrama de casos de uso.*

O consumidor pesquisa (UC01), compara os preços de um produto (UC02), escolhe o modo (UC03) e monta cestas (UC04), pelo cliente de terminal ou pela loja. O avaliador acompanha as métricas (UC05), compara os modos e roda os experimentos (UC06), exporta métricas (UC07) e configura ou derruba supermercados (UC08). Pesquisa, cesta e comparação incluem o UC09, a consulta TCP aos supermercados, único caso que conversa com o ator secundário.

| Caso | Fluxo principal | Fluxos alternativos |
| --- | --- | --- |
| UC01 Pesquisar produto | O consumidor informa o produto; o cliente envia `consultar` ao agregador; o agregador consulta os supermercados (UC09), agrupa as ofertas por produto, ordena por preço e marca o menor; o cliente mostra os preços e os tempos. | Um supermercado não responde: novas tentativas, depois resultado parcial com o motivo. Nenhum responde: erro `NENHUM_MERCADO_RESPONDEU`. Nenhum produto: sugestão de termos mais simples. Pedido inválido: erro `PARAMETRO_INVALIDO`, conexão continua. |
| UC02 Comparar preços de um produto | Supermercados do menor para o maior preço, mais barato destacado, diferença de cada um. | Sem o produto, sem estoque ou sem resposta: aparecem separados. |
| UC03 Escolher o modo | `/modo sequencial` no terminal ou alternador na loja; as próximas pesquisas usam esse modo. | — |
| UC04 Montar e comparar cesta | O agregador envia `BASKET` a cada supermercado e aponta a cesta completa mais barata. | Nenhum tem todos os itens: totais parciais com o que falta. |
| UC06 Comparar modos / experimentos | A mesma pesquisa nos dois modos, alternando a ordem; média, mínimo, máximo e speedup. | — |
| UC08 Configurar / derrubar supermercado | O agregador envia `CONFIG` por TCP; o supermercado muda a latência ou passa a fechar as conexões de consulta, inclusive as em andamento. | Processo inacessível: erro `MERCADO_INDISPONIVEL`. |
| UC09 Consultar supermercados via TCP | Conectar, enviar a linha JSON, esperar a resposta, fechar, publicar eventos com os tempos. | Recusa ou fechamento sem resposta: novas tentativas (0,5 s, 1 s, 2 s). Mais de 3 s sem resposta: timeout. |

### 3.2 Arquitetura

O sistema tem os três componentes pedidos: o **cliente**, o **agregador** e os **serviços independentes**. São sete processos: cinco supermercados, o agregador e o cliente.

![Figura 2. Arquitetura do sistema](figuras/fig-02-arquitetura.png)

*Figura 2. Arquitetura do sistema.*

| Trecho | Protocolo | Por quê |
| --- | --- | --- |
| Cliente de terminal → agregador (porta 5050) | TCP puro, uma mensagem JSON por linha | Requisito do trabalho; formato sugerido no enunciado. |
| Navegador → agregador (porta 8000) | HTTP/1.1 com JSON | Interface web; rotas testáveis no navegador. |
| Agregador → supermercados (portas 5001–5005) | TCP puro, uma mensagem JSON por linha | Requisito do trabalho; expõe o que o HTTP esconde: fronteiras de mensagem, timeouts, conexão recusada. |
| Agregador → navegador | WebSocket | Envia cada evento das consultas assim que acontece. |

O agregador é um único processo com as duas portas. O servidor TCP (porta 5050) e as rotas HTTP chamam as mesmas estratégias de consulta e compartilham o histórico de métricas e os eventos: uma pesquisa feita no terminal aparece ao vivo no painel web.

**Processos e threads.**

- **Supermercado:** a thread principal fica em `accept()`; cada conexão aceita ganha uma thread, que lê a pergunta, consulta o SQLite e responde.
- **Agregador, lado dos clientes:** uma thread só faz `accept()` na porta 5050; cada cliente conectado ganha uma thread, que atende os pedidos dele um de cada vez até ele encerrar. As rotas HTTP rodam no pool de threads do FastAPI.
- **Agregador, modo sequencial:** a própria thread do cliente faz as cinco consultas, uma após a outra (1 thread).
- **Agregador, modo concorrente:** a thread do cliente cria um `ThreadPoolExecutor` com cinco workers, um por supermercado (1 + 5 threads).
- **Eventos:** as consultas rodam em threads comuns, mas os WebSockets vivem no event loop do asyncio; o EventBus entrega cada evento com `loop.call_soon_threadsafe`.

### 3.3 Diagrama de sequência

A Figura 3 mostra a operação principal: uma pesquisa concorrente feita pelo cliente de terminal, com um supermercado fora do ar.

![Figura 3. Sequência de uma pesquisa concorrente](figuras/fig-12-sequencia.png)

*Figura 3. Sequência de uma pesquisa concorrente, do cliente aos supermercados e de volta.*

O cliente abre uma conexão TCP com o agregador e envia o pedido. A thread do agregador que atende esse cliente cria cinco threads de consulta; cada uma abre sua conexão com um supermercado e envia `SEARCH`. As respostas chegam em tempos diferentes. O Mercadinho Ipê, fora do ar, fecha a conexão sem responder; a thread dele tenta de novo três vezes e desiste. Com os cinco resultados (quatro bons e um erro), o agregador agrupa, ordena, marca o menor preço e responde ao cliente com `status: "parcial"`. No fim da sessão, o cliente envia `encerrar` e o agregador fecha a conexão.

### 3.4 Protocolo de aplicação

O protocolo completo, com exemplos de cada operação, está em `docs/protocolo.md`.

**Enquadramento.** O TCP entrega um fluxo de bytes e não preserva as fronteiras entre mensagens: um envio pode chegar em várias leituras, e duas mensagens podem chegar juntas. Por isso cada mensagem é um objeto JSON em UTF-8 numa linha, terminada por `\n`. Como o JSON nunca tem quebra de linha crua, a linha delimita a mensagem. Os dois lados usam o socket como arquivo (`sock.makefile`), e `readline()` junta os pedaços até achar o `\n`. Linhas acima de 16 MB são rejeitadas.

**Cliente ↔ agregador.** Toda requisição tem `operacao` (e um `id` opcional, devolvido na resposta); toda resposta tem `status` (`sucesso`, `parcial` ou `erro`).

| Operação | Parâmetros | Resposta |
| --- | --- | --- |
| `consultar` | `produto`, `modo` (`sequencial`/`concorrente`), `limite` | `resultados` (produtos com `menor_preco` e `ofertas` de cada `fonte`, ordenados), `tempo_total_ms`, `mercados` (tempo, tentativas e erro de cada um) |
| `comparar` | `produto`, `repeticoes` | tempo médio, mínimo e máximo de cada modo e `speedup` |
| `cesta` | `itens` (`produto`, `quantidade`), `modo` | total em cada supermercado e `mais_barato` |
| `mercados` | — | situação de cada supermercado e clientes conectados |
| `configurar` | `mercado`, `latencia_ms`, `online` | nova configuração do supermercado |
| `encerrar` | — | confirmação; o agregador fecha a conexão |

```json
→ {"operacao": "consultar", "produto": "arroz branco 5 kg", "modo": "concorrente"}
← {"operacao": "consultar", "status": "sucesso", "produto": "arroz branco 5 kg", "tempo_total_ms": 1072.4,
   "resultados": [{"produto": "Arroz Branco Tipo 1", "marca": "Sabor da Terra", "unidade": "5 kg",
                   "menor_preco": {"fonte": "Mercado Aurora", "preco": 20.19},
                   "ofertas": [{"fonte": "Mercado Aurora", "produto": "Arroz Branco Tipo 1 Sabor da Terra 5 kg",
                                "preco": 20.19, "status": "sucesso"}, ...]}, ...],
   "mercados": [{"fonte": "Mercado Aurora", "status": "sucesso", "tempo_ms": 350.8, "tentativas": 1, "erro": null}, ...]}
```

**Agregador ↔ supermercados.** Comandos curtos: `SEARCH` (busca), `BASKET` (cesta), `STATUS` e `CONFIG` (administração, respondem mesmo fora do ar). Toda resposta tem `ok`, com `data` ou `error`, e `cpu_ms`. Uma conexão por consulta: o agregador conecta, envia, lê a resposta e fecha.

**Tratamento de erros.** Um pedido inválido recebe `status: "erro"` com um código: `MENSAGEM_INVALIDA` (JSON quebrado), `OPERACAO_DESCONHECIDA`, `PARAMETRO_INVALIDO`, `MERCADO_DESCONHECIDO`, `MERCADO_INDISPONIVEL`, `NENHUM_MERCADO_RESPONDEU`, `TEMPO_ESGOTADO` (cliente inativo) e `ERRO_INTERNO`. Exceto JSON truncado e inatividade, a conexão continua utilizável. Falhas de um supermercado não são erros do pedido: viram `status: "parcial"` com o motivo em `mercados[].erro`.

| Falha de um supermercado | O que o agregador vê | O que faz |
| --- | --- | --- |
| Fora do ar (antes ou durante a consulta) | conexão fechada sem resposta | tenta de novo após 0,5 s, 1 s e 2 s; depois "fora do ar (4 tentativas)" |
| Processo parado | conexão recusada | o mesmo: "conexão recusada (4 tentativas)" |
| Mais de 3 s sem resposta | timeout na leitura | desiste na hora: "tempo esgotado (3,0 s)" |
| Resposta malformada | erro de protocolo | desiste na hora |

**Encerramento das conexões.** O cliente encerra enviando `encerrar`; o agregador confirma e fecha o socket. Se o cliente some sem avisar, o `readline()` do agregador recebe fim de arquivo e a thread do cliente termina; se a conexão cai no meio de uma linha, o pedaço é descartado. Depois de 5 minutos sem mensagens, o agregador envia `TEMPO_ESGOTADO` e fecha. Do agregador para os supermercados, cada conexão é fechada logo após a resposta (ou no timeout).

## 4. Implementação

A diferença entre os dois modos de consulta cabe em poucas linhas: uma compreensão de lista no sequencial e um `ThreadPoolExecutor` no concorrente.

### 4.1 Tecnologias

| Camada | Tecnologia | Responsabilidade |
| --- | --- | --- |
| Supermercados | Python 3.12, `socketserver`, `threading`, SQLite | Servidor TCP de cada supermercado e sua base |
| Agregador | Python 3.12, `socketserver`, FastAPI, Uvicorn | Servidor TCP dos clientes, rotas HTTP, consultas, eventos e métricas |
| Concorrência | `concurrent.futures.ThreadPoolExecutor` | Uma thread por supermercado no modo concorrente |
| Cliente | Python 3.12, `socket` | Cliente de terminal e experimentos |
| Interface web | React, TypeScript, Tailwind CSS | Loja, cesta e painel |
| Experimentos | matplotlib | Gráficos |
| Testes | pytest, httpx | Protocolo, servidores, estratégias, API e cliente TCP |

O código do backend está organizado pelos três componentes do enunciado, mais uma pasta com o que eles compartilham:

| Pasta | Componente | Arquivos principais |
| --- | --- | --- |
| `comum/` | compartilhado | `config.py` (portas, latências, timeout, retry); `protocolo.py` (`send`/`receive`: uma mensagem JSON por linha) |
| `cliente/` | ① Cliente | `conexao.py` (socket TCP com o agregador); `terminal.py` (interface) |
| `agregador/` | ② Agregador | `servidor_tcp.py` (recebe os clientes); `estrategias.py` (sequencial e concorrente); `consulta_mercado.py` (uma consulta TCP, com timeout e retry); `agregador.py` (executa e mede); `consolidacao.py` (ordena, menor preço, cesta); `eventos.py`, `metricas.py`; `api_web.py` (HTTP e WebSocket da interface web) |
| `mercados/` | ③ Serviços independentes | `servidor.py` (servidor TCP de um supermercado); `banco.py`; `catalogo.py`; `gerar_bancos.py` |
| `experimentos/` | — | `executar.py` (os cinco experimentos) |
| `tests/` | — | um arquivo de testes por parte |

`iniciar.py` sobe os cinco supermercados e o agregador. Uma pesquisa percorre, nesta ordem: `cliente/terminal.py` → `cliente/conexao.py` → `agregador/servidor_tcp.py` → `agregador/agregador.py` → `agregador/estrategias.py` → `agregador/consulta_mercado.py` → `mercados/servidor.py`, e volta por `agregador/consolidacao.py`.

### 4.2 Estratégias de consulta

As duas funções recebem a mesma lista de supermercados e o mesmo comando; só muda a forma de disparar as consultas.

```python
def sequential(markets, payload, emit=None, t0=None):
    return [query_market(m, payload, t0=t0, emit=emit) for m in markets]  # um de cada vez

def concurrent(markets, payload, emit=None, t0=None):
    with ThreadPoolExecutor(max_workers=len(markets), thread_name_prefix="consulta") as pool:  # uma thread por mercado
        return list(pool.map(lambda m: query_market(m, payload, t0=t0, emit=emit), markets))
```

`query_market` nunca lança exceção: timeout, conexão recusada e supermercado fora do ar viram um resultado com `ok = False` e o motivo. Assim, uma falha num supermercado não descarta as respostas dos outros.

### 4.3 Servidor de supermercado

Cada supermercado é um processo que usa `socketserver.ThreadingTCPServer`: o servidor faz `bind`, `listen` e `accept` na sua porta, e cada conexão ganha uma thread. A conexão SQLite é aberta por requisição, porque um objeto de conexão não pode ser compartilhado entre threads.

Antes de responder a `SEARCH` e `BASKET`, o supermercado espera a latência configurada, com variação de ±15%. A espera é feita num `threading.Event` e não num `sleep`: quando o supermercado é tirado do ar, o evento é sinalizado, as consultas que estavam esperando acordam na hora e a conexão é fechada sem resposta, como num servidor que trava de verdade. É isso que permite o Experimento 5 desativar um serviço **durante** a pesquisa.

| Supermercado | Porta | Latência | Produtos | Perfil de preço |
| --- | --- | --- | --- | --- |
| Mercado Aurora | 5001 | 300 ms | 1.689 | referência |
| SuperVila | 5002 | 500 ms | 1.639 | 3% mais barato |
| Empório Sol | 5003 | 700 ms | 1.489 | 10% mais caro |
| Max Atacarejo | 5004 | 900 ms | 1.544 | 12% mais barato |
| Mercadinho Ipê | 5005 | 1200 ms | 1.369 | 4% mais caro |

As bases são geradas por `mercados/gerar_bancos.py` a partir de um catálogo de 1.740 itens (95 tipos de produto, marcas fictícias, sabores e tamanhos). Cada supermercado vende parte do catálogo, aplica seu perfil de preço e uma variação de ±12%; somadas, as bases têm 7.730 produtos. O gerador usa semente fixa, então os dados são sempre os mesmos.

### 4.4 Agregador TCP e cliente de terminal

O servidor TCP do agregador (`agregador/servidor_tcp.py`) também é um `ThreadingTCPServer`. A thread de cada cliente lê uma linha, valida os parâmetros, chama a operação e responde, em laço, até o cliente enviar `encerrar` ou fechar o socket. Parâmetros inválidos levantam um `RequestError` com o código, que vira a resposta de erro; uma exceção inesperada vira `ERRO_INTERNO` sem derrubar a thread.

O cliente de terminal (`cliente/terminal.py`, que usa `cliente/conexao.py`) abre uma conexão no início da sessão e a mantém. Cada linha digitada vira uma pesquisa; comandos como `/modo`, `/comparar`, `/cesta`, `/derrubar` e `/json` chamam as demais operações. A saída mostra o tempo de cada supermercado, os produtos do mais barato para o mais caro e uma ★ no menor preço:

```
concorrente> arroz branco 5 kg

  'arroz branco 5 kg' · modo concorrente · 1,07 s · 5/5 mercados responderam
    Mercado Aurora  ✔   351 ms
    SuperVila       ✔   522 ms
    Empório Sol     ✔   800 ms
    Max Atacarejo   ✔   845 ms
    Mercadinho Ipê  ✔   1,07 s

   1. Arroz Branco Tipo 1 · Sabor da Terra · 5 kg
     ★ Mercado Aurora     R$ 20,19   menor preço
       Max Atacarejo      R$ 22,49   +R$ 2,30
       Empório Sol        R$ 23,49   +R$ 3,30
       SuperVila          R$ 23,99   +R$ 3,80
       Mercadinho Ipê     R$ 26,59   +R$ 6,40
```

A classe `ClienteAgregador` é reaproveitada pelos experimentos (`experimentos/executar.py`), de modo que os experimentos passam pelo mesmo caminho que o usuário.

### 4.5 Interface web

A loja exibe os produtos com o menor preço em destaque, um alternador de modo e, abaixo da busca, a linha do tempo das cinco conexões TCP desenhada ao vivo. Ao abrir um produto, os supermercados aparecem do menor para o maior preço. A cesta mostra o total em cada supermercado e a cesta completa mais barata. O painel compara os modos lado a lado, permite deixar cada supermercado lento, em timeout ou fora do ar, mostra os eventos ao vivo (inclusive das pesquisas feitas pelo cliente de terminal) e exporta as métricas em CSV.

## 5. Testes

Os 55 testes automatizados passam (`pytest`). Eles sobem os cinco supermercados em threads, em portas livres, com bancos temporários e latências reduzidas (100 a 300 ms, sem variação), e usam conexões TCP reais.

| Grupo | Testes | O que verificam |
| --- | --- | --- |
| Protocolo (`test_protocolo.py`) | 7 | Ida e volta com acentos; uma mensagem por linha; mensagem enviada em pedaços de 7 bytes; duas mensagens grudadas; fechamento limpo; fechamento no meio da linha; JSON inválido |
| Supermercado (`test_mercados.py`) | 8 | Busca ordenada por preço; sem acento; por marca e tamanho; sortimento inteiro; total da cesta; comando desconhecido; fora do ar com `STATUS` respondendo; preços diferentes entre supermercados |
| Estratégias (`test_estrategias.py`) | 10 | Concorrente mais rápido; sequencial sem sobreposição; concorrente sobreposto em 5 threads; retry e desistência; sucesso quando o supermercado volta; esperas crescentes; conexão recusada; timeout sem retry; bytes medidos; eventos |
| API HTTP (`test_api_web.py`) | 10 | Busca nos dois modos; modo inválido; paginação; cesta; configuração e CSV; benchmark; WebSocket; recursos; situação dos supermercados |
| Cliente ↔ agregador TCP (`test_servidor_tcp.py`) | 20 | `consultar` nos dois modos (ordenação, menor preço, formato `fonte`/`produto`/`preco`/`status`); concorrente mais rápido por TCP; `comparar`; várias operações na mesma conexão e `encerrar`; 8 pedidos inválidos com o código certo; JSON inválido sem perder a conexão; `cesta`; supermercado fora do ar (`parcial`); todos fora do ar (`NENHUM_MERCADO_RESPONDEU`); supermercado caindo durante a pesquisa; 8 clientes simultâneos; desconexão abrupta |

Além dos testes automatizados, o sistema foi verificado com os sete processos no ar: pesquisas pelo cliente de terminal nos dois modos, cesta, `/derrubar` e `/religar`, três clientes conectados ao mesmo tempo, as pesquisas do terminal aparecendo no painel web e `lsof -nP -iTCP -sTCP:LISTEN` mostrando as portas 5050 e 5001–5005.

## 6. Experimentos

### 6.1 Metodologia

- **Ambiente:** Apple M1 (8 núcleos), macOS, Python 3.12, todos os processos em `127.0.0.1`. Medições de 14/11/2026.
- **Caminho medido:** `python -m experimentos` faz tudo pelo cliente TCP: cliente → agregador → supermercados. Latência e disponibilidade são alteradas com a operação `configurar`.
- **Pesquisa:** "arroz", que devolve 217 ofertas (cerca de 44 KB) somando os cinco supermercados.
- **Medição:** o agregador mede cada pesquisa com `time.perf_counter()`, do início da primeira consulta até a última resposta. O cliente também mede o tempo que viu; a diferença ficou abaixo de 10 ms.
- **Latência:** cada supermercado espera o tempo configurado com variação de ±15%. Latências padrão: 300, 500, 700, 900 e 1200 ms.
- **Ordem alternada:** a ordem dos modos alterna a cada rodada, para que nenhum seja favorecido por cache ou aquecimento.
- **Modelo esperado:** com latências l₁ … lₙ, o sequencial deve levar cerca de l₁ + … + lₙ e o concorrente cerca de max(l₁ … lₙ).

Todos os números estão em `docs/relatorio/dados/` (um CSV por experimento) e podem ser refeitos com o script.

![Figura 4. Linha do tempo de uma consulta em cada modo](figuras/fig-03-gantt-consulta.png)

*Figura 4. Uma pesquisa em detalhe: no sequencial as conexões formam uma escada; no concorrente abrem juntas e o total é decidido pelo supermercado mais lento.*

### 6.2 Experimentos 1 e 2 — consulta sequencial e concorrente

Dez pesquisas em cada modo, latências padrão.

| Experimento | Modo | Média | Mín. | Máx. | Desvio padrão | Previsto |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Sequencial | 3,71 s | 3,39 s | 3,94 s | 149 ms | 3,60 s (soma) |
| 2 | Concorrente | 1,16 s | 1,04 s | 1,35 s | 107 ms | 1,20 s (maior) |

![Figura 5. Experimentos 1 e 2](figuras/fig-08-exp1-exp2.png)

*Figura 5. Tempo de cada rodada nos dois modos, com o previsto pelo modelo.*

O speedup médio foi de 3,2×, contra 3,0× do modelo (3,6 s ÷ 1,2 s). O concorrente foi mais rápido em todas as rodadas, sem sobreposição entre as faixas: o pior concorrente (1,35 s) levou menos da metade do melhor sequencial (3,39 s).

### 6.3 Experimento 3 — simulação de latência

Sete configurações de atraso, cinco rodadas cada.

| Cenário | Latências | Sequencial | Previsto | Concorrente | Previsto | Speedup |
| --- | --- | --- | --- | --- | --- | --- |
| Sem atraso | 0 ms em todos | 13 ms | 0 ms | 8 ms | 0 ms | 1,6× |
| 200 ms | 200 ms em todos | 1,04 s | 1,00 s | 233 ms | 200 ms | 4,5× |
| 500 ms | 500 ms em todos | 2,57 s | 2,50 s | 565 ms | 500 ms | 4,6× |
| 1000 ms | 1000 ms em todos | 4,98 s | 5,00 s | 1,13 s | 1,00 s | 4,4× |
| Padrão | 300 a 1200 ms | 3,62 s | 3,60 s | 1,15 s | 1,20 s | 3,1× |
| Um lento | padrão, Ipê com 2500 ms | 5,14 s | 4,90 s | 2,50 s | 2,50 s | 2,1× |
| Um em timeout | padrão, Ipê com 4000 ms | 5,49 s | 5,40 s | 3,01 s | 3,00 s | 1,8× |

![Figura 6. Experimento 3](figuras/fig-09-exp3-latencia.png)

*Figura 6. Tempo médio por cenário de latência.*

Com latências iguais o ganho ficou entre 4,4× e 4,6×, perto do limite teórico de 5×. Com latências diferentes, o ganho é a soma dividida pela maior. Um supermercado lento passa a decidir o tempo do concorrente (2,50 s com o Ipê em 2500 ms), e o timeout de 3 s limita o estrago quando ele não responde. Sem atraso, o ganho cai para 1,6×.

### 6.4 Experimento 4 — múltiplos clientes

De 1 a 32 clientes, cada um com sua conexão TCP, começando juntos; cada cliente faz 3 pesquisas seguidas.

| Clientes | Sequencial: resposta média | Sequencial: vazão | Concorrente: resposta média | Concorrente: vazão |
| --- | --- | --- | --- | --- |
| 1 | 3,64 s | 0,27 pesquisas/s | 1,22 s | 0,82 pesquisas/s |
| 2 | 3,60 s | 0,55 pesquisas/s | 1,23 s | 1,59 pesquisas/s |
| 4 | 3,65 s | 1,06 pesquisas/s | 1,23 s | 3,16 pesquisas/s |
| 8 | 3,61 s | 2,12 pesquisas/s | 1,25 s | 6,15 pesquisas/s |
| 16 | 3,59 s | 4,25 pesquisas/s | 1,22 s | 11,70 pesquisas/s |
| 32 | 3,66 s | 8,33 pesquisas/s | 1,25 s | 23,66 pesquisas/s |

![Figura 7. Experimento 4](figuras/fig-10-exp4-clientes.png)

*Figura 7. Tempo de resposta e vazão conforme o número de clientes simultâneos.*

O tempo de cada pesquisa não mudou com mais clientes, e a vazão cresceu na proporção dos clientes: 32 clientes fizeram 96 pesquisas concorrentes em 4,06 s, 29 vezes a vazão de um só. Nenhuma pesquisa falhou. Com 32 clientes no modo concorrente, o agregador tinha 32 threads de cliente, cada uma com 5 threads de consulta (160 conexões simultâneas com os supermercados), e cada supermercado atendia 32 consultas ao mesmo tempo, cada uma na sua thread.

### 6.5 Experimento 5 — indisponibilidade de serviço

O Mercadinho Ipê foi desativado (operação `configurar` com `online: false`, por uma segunda conexão TCP) antes da pesquisa, 0,3 s depois do início, ou 0,3 s depois do início e reativado em 1,0 s. Três rodadas por cenário.

| Cenário | Modo | Tempo médio | Supermercados com resposta | Tentativas no Ipê |
| --- | --- | --- | --- | --- |
| Todos no ar | Sequencial | 3,59 s | 5 de 5 | 1 |
| | Concorrente | 1,24 s | 5 de 5 | 1 |
| Fora do ar antes | Sequencial | 6,00 s | 4 de 5 | 4 |
| | Concorrente | 3,52 s | 4 de 5 | 4 |
| Cai durante | Sequencial | 5,97 s | 4 de 5 | 4 |
| | Concorrente | 3,82 s | 4 de 5 | 4 |
| Cai e volta | Sequencial | 3,68 s | 5 de 5 | 1 |
| | Concorrente | 3,04 s | 5 de 5 | 3 |

![Figura 8. Experimento 5](figuras/fig-11-exp5-falha.png)

*Figura 8. O Ipê cai 0,3 s depois do início da pesquisa. Barras: início e fim da consulta a cada supermercado.*

Em todos os cenários o cliente recebeu os preços dos outros quatro, com `status: "parcial"` e o motivo `fora do ar (4 tentativas)`. No concorrente, a consulta ao Ipê já estava em andamento quando ele caiu: a conexão foi fechada na hora e as três novas tentativas levaram a resposta a 0,3 + 0,5 + 1 + 2 = 3,8 s, exatamente o medido. No sequencial, quando a vez do Ipê chegou (aos 2,4 s) ele já estava fora do ar, e a pesquisa somou os 3,5 s das tentativas. No cenário "cai e volta", a terceira tentativa do concorrente encontrou o Ipê de volta e a pesquisa terminou com os cinco supermercados; o sequencial nem percebeu a queda, porque só chegou ao Ipê depois que ele voltou.

Encerrar o processo do supermercado produz conexão recusada, tratada da mesma forma ("conexão recusada (4 tentativas)"), o que é coberto por teste automatizado.

### 6.6 Experimentos complementares

Antes dos obrigatórios foram medidos, pelo painel web, o efeito do número de supermercados, do número de threads do pool e do volume de dados, e o consumo de CPU. Os números completos estão em `docs/experimentos.md`.

![Figura 9. Tempo pelo número de supermercados](figuras/fig-05-por-mercados.png)

*Figura 9. Com um supermercado os modos empatam; o speedup cresce a cada fonte acrescentada (1,0× a 2,9×).*

![Figura 10. Tempo pelo número de threads do pool](figuras/fig-06-por-threads.png)

*Figura 10. Com menos threads que supermercados, as consultas esperam na fila do pool; com uma thread o concorrente vira sequencial.*

![Figura 11. Consumo de CPU por requisição](figuras/fig-07-recursos.png)

*Figura 11. A concorrência não economiza CPU: o mesmo trabalho é feito, mas sobreposto.*

Trazer 300 vezes mais dados (o catálogo inteiro, 1,5 MB) custou poucos milissegundos em `localhost`; com as latências padrão, a diferença sumiu na variação.

## 7. Resultados e discussão

### 7.1 Comparação entre as estratégias

| Aspecto | Sequencial | Concorrente |
| --- | --- | --- |
| Tempo de uma pesquisa (padrão) | soma das latências: 3,71 s | maior latência: 1,16 s |
| Ganho | — | 3,2× no padrão; até 4,6× com latências iguais; 1,6× sem latência |
| Threads por pesquisa no agregador | 1 | 1 + 5 |
| Supermercado em timeout | soma dos outros + 3 s: 5,49 s | 3 s: 3,01 s |
| Supermercado fora do ar | soma dos outros + 3,5 s de retry: 6,00 s | 3,5 s de retry: 3,52 s |
| 32 clientes simultâneos | 8,3 pesquisas/s | 23,7 pesquisas/s |
| CPU por pesquisa | a mesma | a mesma, concentrada numa janela menor |

### 7.2 Conclusões sobre multithreading

- **Threads compensam quando a tarefa espera E/S.** Cada consulta passa quase todo o tempo esperando a rede. Uma thread bloqueada em `recv()` libera o GIL do Python, e as outras seguem. Por isso cinco threads reduziram o tempo a cerca de um terço, como o modelo `soma ÷ máximo` previa.
- **O ganho tem teto: a fonte mais lenta.** Nenhuma quantidade de threads torna a pesquisa mais rápida que o supermercado mais lento (Exp. 3, "Um lento").
- **Sem espera, o ganho é pequeno.** Sem latência, o speedup cai para 1,6×: criar threads e abrir conexões tem custo fixo, e trabalho de CPU em Python não se paraleliza dentro de um processo, por causa do GIL. O ganho que sobra vem dos cinco processos de supermercado, que trabalham em paralelo de verdade.
- **A concorrência no servidor é o que permite vários clientes.** Com uma thread por conexão, 32 clientes foram atendidos no mesmo tempo que um (Exp. 4). Os dois níveis se somam: concorrência entre clientes (threads do servidor) e dentro de cada pesquisa (threads de consulta).
- **Timeouts e retries fazem parte da concorrência.** Sem timeout, um supermercado travado seguraria a resposta para sempre. O retry recupera falhas curtas (Exp. 5, "cai e volta"), mas custa 3,5 s quando a falha persiste. Os valores de timeout e de espera são um compromisso entre não perder supermercados e não fazer o usuário esperar.
- **Concorrência não economiza trabalho.** A CPU por pesquisa é a mesma nos dois modos; a concorrência troca espera por paralelismo, ao custo de mais threads.

### 7.3 Limitações

- Todos os processos rodam na mesma máquina, e a latência de rede é simulada com uma espera. Não há perda de pacotes, variação real de rota nem limite de banda.
- De 3 a 10 rodadas por cenário; mais repetições dariam intervalos de confiança mais estreitos.
- No Experimento 4, os 32 clientes são threads de um mesmo processo Python; com espera dominante isso não interfere, mas numa carga de CPU eles disputariam o GIL.
- Uma thread por cliente e uma por consulta é simples, mas não escala para milhares de conexões; nesse caso, um pool limitado ou `asyncio` seria mais adequado.

## 8. Conclusão

O comparador atende às funcionalidades mínimas do Tema 1 e à evolução sugerida (comparação de cestas), com cliente, agregador e cinco supermercados como processos separados que conversam por sockets TCP, usando um protocolo de aplicação documentado em JSON. O agregador consulta os supermercados de forma sequencial ou concorrente, atende vários clientes ao mesmo tempo, registra o tempo de cada pesquisa e trata lentidão, queda e processo parado sem perder os resultados dos demais.

O trabalho percorreu as etapas pedidas: análise de requisitos com atores, requisitos funcionais e não funcionais, restrições e critérios de aceitação; diagramas de casos de uso, arquitetura e sequência; implementação; 55 testes automatizados; e os cinco experimentos obrigatórios. A consulta concorrente reduziu o tempo de resposta a cerca de um terço (3,2×), chegando a 4,6× com latências iguais. O ganho depende de quanto tempo as consultas passam esperando a rede, de quantas fontes são consultadas e de haver threads suficientes para todas; a fonte mais lenta é o limite.

### 8.1 Trabalhos futuros

- Rodar os supermercados em outras máquinas da rede, para medir latência real em vez de simulada.
- Cache das respostas no agregador, para não esperar o supermercado mais lento em pesquisas repetidas.
- Responder com os supermercados que já responderam após um prazo, completando depois (resposta parcial antecipada).
- Comparar a versão com threads a uma versão com `asyncio`.
- Manter um pool de conexões TCP abertas com cada supermercado, eliminando o handshake a cada consulta.

## Apêndice A. Como executar

Requisitos: Python 3.12 (e Node.js 20 ou superior, só para a interface web em modo de desenvolvimento).

1. Instalar o backend, uma vez: `cd backend`, `python3.12 -m venv .venv` e `.venv/bin/pip install -r requirements.txt`.
2. Subir os cinco supermercados e o agregador: `cd backend && .venv/bin/python iniciar.py`. Na primeira execução as bases SQLite são geradas.
3. Em outro terminal, o cliente: `cd backend && .venv/bin/python -m cliente`. Uma pesquisa só: `.venv/bin/python -m cliente arroz --modo sequencial`.
4. Os experimentos: `cd backend && .venv/bin/python -m experimentos` (cerca de 6 minutos).
5. Os testes: `cd backend && .venv/bin/python -m pytest`.
6. Conferir os processos TCP: `lsof -nP -iTCP:5001-5005 -iTCP:5050 -sTCP:LISTEN`.
7. Interface web (opcional): `cd frontend && npm install && npm run dev`, e abrir `http://localhost:5173`. Com `npm run build`, o próprio agregador serve a interface em `http://localhost:8000`.

## Apêndice B. Roteiro da demonstração

1. `iniciar.py` sobe os seis processos de servidor; `lsof` mostra as portas 5050 e 5001–5005, cada supermercado com seu PID.
2. No cliente de terminal: `arroz branco 5 kg` no modo concorrente; `/modo sequencial` e a mesma pesquisa; `/comparar arroz 3` mostra o speedup; `/json` mostra a mensagem do protocolo.
3. Dois ou três terminais com o cliente ao mesmo tempo; `/mercados` mostra quantos clientes estão conectados.
4. `/derrubar ipe` e pesquisar: a resposta vem dos outros quatro, com o motivo; `/religar ipe`.
5. No painel web, as pesquisas do terminal aparecem ao vivo, com a linha do tempo das cinco conexões.
6. Gráficos dos experimentos (Figuras 5 a 8).

## Referências

- TANENBAUM, Andrew S.; VAN STEEN, Maarten. *Distributed Systems: Principles and Paradigms*. 2. ed. Prentice Hall, 2007.
- SOMMERVILLE, Ian. *Software Engineering*. 10. ed. Pearson, 2015.
- KUROSE, James F.; ROSS, Keith W. *Redes de computadores e a Internet: uma abordagem top-down*. Pearson.
- PYTHON SOFTWARE FOUNDATION. *socket — Low-level networking interface*. Disponível em: https://docs.python.org/3/library/socket.html.
- PYTHON SOFTWARE FOUNDATION. *socketserver — A framework for network servers*. Disponível em: https://docs.python.org/3/library/socketserver.html.
- PYTHON SOFTWARE FOUNDATION. *threading — Thread-based parallelism*. Disponível em: https://docs.python.org/3/library/threading.html.
- PYTHON SOFTWARE FOUNDATION. *concurrent.futures — Launching parallel tasks*. Disponível em: https://docs.python.org/3/library/concurrent.futures.html.
- Open Food Facts, fonte das fotos dos produtos da interface web (licença CC BY-SA). Disponível em: https://world.openfoodfacts.org/.
