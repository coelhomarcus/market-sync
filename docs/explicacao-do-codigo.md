# Comparador de Preços: o código explicado passo a passo

## 0. A ideia geral

O sistema tem **3 componentes**. Cada um roda num processo separado e eles conversam por **socket TCP**:

```
 ① CLIENTE (client/)  ──TCP:5050──▶  ② AGREGADOR (aggregator/)  ──TCP:5001..5005──▶  ③ 5 MERCADOS (markets/)
   o usuário digita       "consultar"     consulta os 5 mercados                          cada um tem seu
   "arroz"                                (sequencial OU concorrente),                   banco SQLite
                                          junta e ordena os preços
```

- **`common/`**: código que os três usam (configuração e protocolo).
- **`tools/`**: gera os bancos SQLite com produtos fictícios.
- **`start.py`**: sobe os 5 mercados e o agregador.
- **`experiments/`**: os 5 experimentos do trabalho, com CSV e gráficos.
- **`tests/`**: testes automatizados (pytest).

Vou seguir a ordem das dependências: primeiro o que é usado por todos, depois quem usa.

---

## 1. Sintaxe Python que aparece em todo o projeto

Vale entender isto antes, porque se repete em quase todos os arquivos:

| Sintaxe | O que faz | Exemplo no projeto |
|---|---|---|
| `from __future__ import annotations` | As anotações de tipo viram texto e não são avaliadas na hora. Permite escrever `str \| None` e citar classes antes de elas existirem | 1ª linha de quase todo arquivo |
| `def f(x: str) -> int:` | **Type hints**: documentam os tipos. O Python não verifica na execução | todo lugar |
| `str \| None` | "uma string ou None" | `error: str \| None = None` |
| `@dataclass` | Gera `__init__`, `__repr__` e `__eq__` a partir dos campos. `frozen=True` deixa o objeto imutável | `MarketInfo`, `MarketResult` |
| `@property` | Método que se usa como atributo, sem parênteses | `market.db_path`, `result.duration_ms` |
| `@staticmethod` | Método que não recebe `self` | `ConnectionHandler.arguments` |
| `@contextmanager` | Transforma uma função com `yield` em algo usável com `with` | `MarketDatabase._connect` |
| `with X as y:` | Garante a limpeza (fechar socket, arquivo, conexão) mesmo com erro | sockets, SQLite, `AggregatorClient` |
| f-string `f"{x:<16}"` | Formatação. `<16` alinha à esquerda em 16 colunas, `>8` à direita, `.2f` dá 2 casas, `!r` usa `repr()` | logs e terminal |
| `{**a, "k": v}` | Copia o dicionário `a` e acrescenta ou sobrescreve chaves | `{**base, "t_ms": ...}` |
| `[x for x in ...]`, `{k: v for ...}` | List e dict comprehension | `MARKETS_BY_ID = {m.id: m for m in MARKETS}` |
| `lambda p: p["order"]` | Função anônima de uma linha | chaves de ordenação |
| `def f(a, *, b=None)` | O `*` obriga os parâmetros seguintes a serem passados por nome | `query_market(..., *, t0=..., timeout=...)` |
| `raise X from exc` / `from None` | Encadeia a exceção original, ou esconde ela | `protocol.receive`, `op_configure` |
| `__main__.py` + `python -m pacote` | Rodar um pacote como programa | `python -m markets.aurora`, `python -m client` |
| `if __name__ == "__main__":` | Só executa quando o arquivo é rodado direto, não quando é importado | `start.py`, `server.py` |

---

## 2. `common/`: a base compartilhada

### [common/config.py](../common/config.py)

- `ROOT = Path(__file__).resolve().parent.parent` é a raiz do projeto. `__file__` é o caminho deste arquivo; subir duas pastas sai de `common/config.py` e chega à raiz.
- `os.environ.get("MARKET_HOST", "127.0.0.1")` lê uma variável de ambiente e usa o valor padrão quando ela não existe.
- Constantes do agregador:
  - porta **5050** (a 5000 é do AirPlay no macOS);
  - `TCP_TIMEOUT_S = 3.0`: desiste de um mercado que demora mais de 3 s;
  - `RETRIES = 3` e `RETRY_WAIT_S = 0.5`: novas tentativas com espera de 0,5 s, depois 1 s, depois 2 s.
- `MarketInfo` é uma dataclass imutável com o que o agregador sabe de cada mercado: id, nome, porta, latência, fator de preço, cor e pasta.
- `MARKETS` é a lista dos 5: Aurora (5001, 300 ms), SuperVila (5002, 500 ms), Empório Sol (5003, 700 ms), Max Atacarejo (5004, 900 ms), Ipê (5005, 1200 ms).
- `MARKETS_BY_ID` é um dicionário para buscar o mercado pelo id.

### [common/protocol.py](../common/protocol.py): o protocolo de rede

Este é o arquivo mais importante para entender a parte de **Redes**.

**O problema:** o TCP entrega um *fluxo de bytes*, sem fronteira entre mensagens. Um `recv()` pode trazer meia mensagem, ou duas de uma vez.

**A solução (framing por linha):** cada mensagem é **um JSON numa linha, terminado em `\n`**. Como o JSON gerado nunca tem quebra de linha crua dentro, o `\n` marca o fim da mensagem.

```python
def send(stream, message):
    data = (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    stream.write(data); stream.flush()
    return len(data)
```

- `ensure_ascii=False` mantém "Feijão" como está, em vez de `"Feijão"`.
- `separators=(",", ":")` gera JSON compacto, sem espaços.
- `.encode("utf-8")` transforma o texto em bytes, que é o que trafega na rede.
- `flush()` força o envio na hora, em vez de esperar o buffer encher.

```python
def receive(stream):
    line = stream.readline(MAX_LINE + 1)
    if not line: return None, 0                  # o outro lado fechou a conexão (EOF)
    if not line.endswith(b"\n"): raise ProtocolError(...)  # cortou no meio ou passou de 16 MB
    message = json.loads(line)
    ...
```

- `stream` é o socket "visto como arquivo" (`sock.makefile("rwb")`). O `readline()` junta quantos pedaços TCP forem precisos até achar o `\n`.
- O limite `MAX_LINE` (16 MB) impede que alguém mande uma "linha infinita" e esgote a memória.
- O retorno `(None, 0)` significa **conexão fechada sem mensagem**. O agregador usa isso para detectar um mercado "fora do ar".

### [common/watchdog.py](../common/watchdog.py)

O `start.py` sobe cada servidor numa *sessão* própria. Se o `start.py` morrer de repente (`kill -9`, aba fechada), os filhos ficariam órfãos segurando as portas. Esta função cria uma **thread daemon** que confere a cada segundo se `os.getppid()` (o PID do processo pai) ainda é o do `start.py`. Quando um processo perde o pai, o sistema o "adota" e o PID do pai muda. Nesse caso a thread manda `SIGINT` para o próprio processo, como se fosse um Ctrl+C.

---

## 3. `tools/`: gerar os dados

### [tools/catalog.py](../tools/catalog.py)

Monta um catálogo fictício com cerca de 1.700 produtos combinando **tipo × variante × tamanho × marca**:

- `ProductType` define cada tipo (ex.: "Arroz Branco Tipo 1", tamanhos `1 kg`/`5 kg` com preço base). A função `T(...)` é um atalho para criá-lo.
- `BRANDS` tem 10 marcas fictícias por grupo, e `BRAND_FACTORS` tem os multiplicadores de preço de cada marca (0,82 a 1,25).
- `normalize()` tira os acentos: `unicodedata.normalize("NFKD")` separa "ã" em "a" + "~", e `combining(c)` identifica o "~" para ele ser descartado.
- `slugify()` usa uma regex: `re.sub(r"[^a-z0-9]+", "-", ...)` troca tudo que não é letra ou dígito por "-". Assim, "Arroz Branco 5 kg" vira `arroz-branco-5-kg`.
- `_build_catalog()` gera os SKUs. `random.Random("marcas-arroz")` cria um gerador com **semente fixa**: sempre sai o mesmo "aleatório". No fim, intercala um SKU de cada tipo para montar a ordem de "destaques".

### [tools/seed_databases.py](../tools/seed_databases.py)

Cria um `.db` SQLite para cada mercado:

- `SCHEMA` é o `CREATE TABLE products (...)`, com índice em `price`.
- `MISSING_CHANCE`: cada mercado deixa de vender uma fração do catálogo (o Ipê, menor, deixa 22%).
- O preço é `preço base × price_factor da loja × variação de ±12%`, arredondado por `market_price()`. Ele trunca em uma casa decimal e soma 0,09, então os preços sempre terminam em ",x9".
- `fake_ean()` gera um código de barras EAN-13 válido. O prefixo 789 é o do Brasil, e o dígito verificador usa pesos 1 e 3 alternados.
- `conn.executemany("INSERT ... VALUES (?, ?, ...)", rows)`: os `?` são **parâmetros**, que evitam SQL injection.
- `is_ready()` confere se o banco existe e não está vazio. O `start.py` usa isso para gerar os bancos automaticamente.

---

## 4. `markets/`: os 5 supermercados (servidores TCP)

As cinco pastas têm **o mesmo código**, de propósito: cada uma representa um serviço independente que poderia rodar em outra máquina. Só mudam `ID`, `NAME`, `PORT`, `LATENCY_MS` e o arquivo `.db`. Vou usar o [markets/aurora/](../markets/aurora/) como exemplo.

### [markets/aurora/\_\_main\_\_.py](../markets/aurora/__main__.py)

Tem só `from .server import main; main()`. É o que permite `python -m markets.aurora`. O ponto em `.server` indica import **relativo**, ou seja, do mesmo pacote.

### [markets/aurora/database.py](../markets/aurora/database.py)

```python
@contextmanager
def _connect(self):
    conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
```

- Abre **uma conexão por consulta**, porque uma conexão SQLite não pode ser compartilhada entre threads.
- `mode=ro` abre só para leitura: se o arquivo sumir, dá erro em vez de criar um banco vazio.
- `row_factory = sqlite3.Row` permite acessar `linha["price"]` e converter com `dict(linha)`.
- O `yield` entrega a conexão para o bloco `with`, e o `finally` fecha sempre.

`search(query)`:

```python
words = normalize(query).split()            # "Arroz 5kg" → ["arroz", "5kg"]
sql += " WHERE " + " AND ".join("search_text LIKE ?" for _ in words)
sql += " ORDER BY price"
db.execute(sql, [f"%{p}%" for p in words])
```

Cada palavra vira um `LIKE '%palavra%'`, unidos por AND. O produto precisa conter **todas** as palavras.

### [markets/aurora/server.py](../markets/aurora/server.py): o servidor

**Classe `Market`** (o estado do mercado):

- `self.lock = threading.Lock()`: várias threads (uma por conexão) mexem nos contadores, então todo acesso a eles fica dentro de `with self.lock:`. Isso evita **condição de corrida**.
- `self.down = threading.Event()` é uma "bandeira" que as threads podem esperar.
- `handle_request(cmd, request)` despacha os comandos `STATUS`, `CONFIG` e `SEARCH`.
- `simulate_latency()`:

  ```python
  if self.down.wait(latency * random.uniform(0.85, 1.15) / 1000):
      raise WentDown
  ```

  `Event.wait(t)` espera até `t` segundos e devolve **True se a bandeira foi levantada** durante a espera. Por isso o código não usa `sleep`: se alguém tirar o mercado do ar no meio de uma consulta, ela é interrompida na hora, como um servidor que trava de verdade.
- `configure()` muda `latency_ms` e `online`. Ao tirar do ar, chama `down.set()`, que acorda quem estava esperando.

**Classe `ConnectionHandler(socketserver.StreamRequestHandler)`**: atende **uma conexão**.

- O `socketserver` já entrega `self.rfile` (para ler) e `self.wfile` (para escrever), que são o socket visto como arquivo.
- O fluxo de `handle()`:
  1. `protocol.receive(self.rfile)` lê o pedido;
  2. `None` significa que o cliente conectou e fechou (é o teste de porta do `start.py`);
  3. a thread é renomeada para `"conexão nº N"`;
  4. se o mercado está **fora do ar** e o comando não é administrativo, faz `return` sem responder. A conexão fecha, e é assim que o agregador percebe a queda;
  5. mede o tempo com `time.perf_counter()` (relógio de parede) e o CPU com `time.thread_time()` (só CPU desta thread, sem contar a espera);
  6. erro no pedido vira `{"ok": false, "error": ...}` e o servidor continua de pé;
  7. `protocol.send(self.wfile, response)` envia a resposta.

**Classe `MarketServer(socketserver.ThreadingTCPServer)`**:

- O `ThreadingTCPServer` faz por você `socket()` → `bind()` → `listen()` → `accept()` e **cria uma thread nova para cada conexão**.
- `daemon_threads = True`: essas threads não impedem o processo de terminar.
- `allow_reuse_address = True` liga o `SO_REUSEADDR`, para poder reabrir a porta logo depois de fechar.
- `request_queue_size = 64` é o *backlog* do `listen()`: a fila de conexões esperando o `accept()`.

**`main()`**: lê `--latency` com `argparse`, configura o `logging`, cria o `Market`, liga o watchdog e chama `server.serve_forever()`, que fica num loop de `accept()`.

---

## 5. `aggregator/`: o coração do trabalho (sequencial × concorrente)

### [aggregator/market_query.py](../aggregator/market_query.py): falar com UM mercado

**`MarketResult`** é uma dataclass com tudo que foi medido: `ok`, `data`, `error`, `attempts`, `start_ms`/`end_ms`, `connect_ms`, `wait_ms`, bytes enviados e recebidos, CPU e nomes das threads.

**`ask_once()`**: uma ida e volta TCP completa.

```python
with socket.create_connection((host, port), timeout=timeout) as sock:   # connect() = three-way handshake
    with sock.makefile("rwb") as stream:                                 # socket como arquivo binário
        protocol.send(stream, payload)
        response, n = protocol.receive(stream)                           # bloqueia até a resposta chegar
if response is None:
    raise MarketDown(...)                                                # fechou sem responder = fora do ar
```

A cada passo ele chama `emit("tcp_connect" | "tcp_send" | "tcp_recv" | "tcp_close", ...)`, e esses eventos alimentam o painel. `emit = emit or (lambda _t, _d: None)` cria uma função que não faz nada quando ninguém quer os eventos.

**`query_market()`**: o laço de **novas tentativas com backoff exponencial**.

```python
for attempt in range(1, retries + 2):        # 1, 2, 3, 4 → 1 tentativa + 3 novas
    try:
        response = ask_once(...)
        ...; break                           # deu certo: sai do laço
    except ConnectionError:                  # recusada ou fechada sem resposta: tenta de novo
        if attempt > retries: break
        time.sleep(0.5 * 2 ** (attempt - 1)) # 0,5 s → 1 s → 2 s
    except socket.timeout:                   # lento: NÃO tenta de novo (já esperou 3 s)
        break
    except (OSError, protocol.ProtocolError):
        break
```

- A **ordem dos `except` importa**. `ConnectionError` e `socket.timeout` são subclasses de `OSError`, então precisam vir antes; senão o `OSError` "engoliria" os dois.
- `MarketDown` herda de `ConnectionError`, por isso cai no primeiro `except` e é repetido.
- A função **nunca lança exceção**: falhas viram `ok=False`, e os outros mercados seguem normalmente.

### [aggregator/sequential.py](../aggregator/sequential.py): estratégia sequencial

```python
for market in markets:
    result = query_market(market, request, ...)   # bloqueia até ESTE mercado responder
    results.append(result)
```

Usa uma única thread e um mercado por vez. **Tempo total ≈ soma das latências** (300+500+700+900+1200 ≈ 3,6 s).

### [aggregator/concurrent.py](../aggregator/concurrent.py): estratégia concorrente

```python
results = [None] * len(markets)          # uma posição por mercado

def query_one(position, market):         # o que cada thread faz
    results[position] = query_market(market, request, ...)

threads = []                             # 1. criar uma thread por mercado
for position, market in enumerate(markets):
    threads.append(threading.Thread(target=query_one, args=(position, market), name=f"thread_{position + 1}"))

for thread in threads:                   # 2. start(): dispara todas, volta na hora
    thread.start()

for thread in threads:                   # 3. join(): espera todas terminarem
    thread.join()

return results
```

- `threading.Thread(target=..., args=...)` só **cria** a thread; ela ainda não roda.
- `start()` coloca a thread para rodar e **volta na hora**, sem esperar a resposta do mercado. Depois do segundo laço, as 5 consultas estão em andamento ao mesmo tempo.
- `join()` só **espera**, não dispara nada: quando o laço do `join()` começa, as 5 consultas já estão rodando juntas. O laço é em ordem, mas isso não deixa a consulta sequencial: enquanto a thread do pedido espera a `thread_1` (Aurora, 300 ms), as outras continuam consultando os seus mercados. Quando chega a vez delas, várias já terminaram e o `join()` volta na hora. A espera total é a da thread mais lenta (Ipê, ≈ 1,2 s), e não a soma.
- Cada thread escreve só na sua posição de `results`, por isso não é preciso `Lock`. A lista volta na mesma ordem de `markets`.
- Os 5 mercados são consultados ao mesmo tempo. **Tempo total ≈ a maior latência** (≈ 1,2 s).
- **Por que threads funcionam aqui, apesar do GIL?** Enquanto uma thread está bloqueada em I/O de rede (`recv`), ela **libera o GIL** e as outras rodam. O trabalho é limitado por I/O, não por CPU.
- `enumerate(markets)` produz os pares `(0, aurora), (1, supervila), ...`; o nome da thread soma 1 (`thread_1` … `thread_5`).

### [aggregator/aggregator.py](../aggregator/aggregator.py): a classe `Aggregator`

- `STRATEGIES = {"sequential": sequential.search, "concurrent": concurrent.search}` é um **dicionário de funções**: escolher o modo é só `STRATEGIES[mode](...)`.
- `execute()`:
  1. gera um `request_id` curto (`uuid.uuid4().hex[:8]`);
  2. define o `emit` como **closure**: ele "lembra" o `request_id` e o `mode` e repassa cada evento para `display.event`;
  3. mede o tempo total e monta o `record`. `sum(r.ok for r in results)` funciona porque `True` vale 1.
- `market_status()` e `configure_market()` mandam `STATUS`/`CONFIG` ao mercado, também por TCP, com `retries=0` para responder rápido.
- `markets_status()` usa `pool.map(...)` para perguntar o status aos 5 em paralelo.
- `next((m for m in ... if m.id == x), None)` acha o primeiro elemento que satisfaz a condição, ou devolve `None`.

### [aggregator/consolidation.py](../aggregator/consolidation.py): juntar os preços

Funções puras, sem rede.

- `merge_offers()`: `products.setdefault(slug, {...})` cria a entrada do produto só na primeira vez e depois reaproveita. Cada mercado acrescenta sua oferta.
- `p["offers"].sort(key=lambda o: (not o["in_stock"], o["price"]))` ordena por **tupla**. `False < True`, então quem tem estoque vem antes, e dentro disso vale o menor preço.
- `min(prices, default=None)` não dá erro com lista vazia.
- `"preco": lambda p: (p["min_price"] is None, p["min_price"] or 0)` manda os produtos sem preço para o fim.
- `-(-n // k)` é um truque de **divisão com arredondamento para cima** (número de páginas).
- `listed[start : start + page_size]` é *slicing*, para a paginação.

### [aggregator/tcp_server.py](../aggregator/tcp_server.py): o servidor que os clientes usam

Só a parte TCP. O que cada operação faz está em `operations.py`.

**`AggregatorTCPServer(ThreadingTCPServer)`**: uma thread por cliente.

- `itertools.count(1)` é um contador infinito (1, 2, 3...) usado com `next()`.
- `_in_progress` conta os pedidos em andamento. Com `threading.Condition(self._lock)`:
  - `request_finished()` decrementa e chama `notify_all()`;
  - `wait_for_requests()` usa `wait_for(lambda: self._in_progress == 0, timeout=...)`.

  É isso que permite um **desligamento gracioso**: no Ctrl+C, quem já pediu ainda recebe a resposta.

**`ClientHandler`**: diferente do mercado, aqui **uma conexão leva vários pedidos**.

- `conversation()` é um `while True`: lê um pedido, chama `operations.answer()` e responde, até `None` (o cliente fechou) ou `"encerrar"`.
- Um JSON inválido (`InvalidMessage`) recebe resposta de erro **e a conexão continua viva**.
- `handle()` concentra o que **encerra** a conversa, num único `try`:
  - `socket.timeout`: o cliente ficou 5 min parado (`timeout = 300`);
  - `ProtocolError`: a linha chegou incompleta, então não dá para continuar lendo;
  - `OSError`: o cliente sumiu no meio da conversa.

**`main()`**: `signal.signal(SIGTERM, ...)` faz o `kill` se comportar como Ctrl+C. No `finally`, ignora novos Ctrl+C, espera as pesquisas em andamento e desliga o painel.

### [aggregator/operations.py](../aggregator/operations.py): as operações do cliente

Não sabe nada de socket: recebe o pedido como dicionário e devolve a resposta como dicionário.

- `answer()` escolhe a operação por um dicionário (`"consultar": ...`) e **nunca lança exceção**: `RequestError` vira `{"status": "erro", "codigo": ...}`, e um `except Exception` garante que um bug num pedido não derrube o agregador. Se o pedido tiver `"id"`, a resposta devolve o mesmo id.
- **Validação**: `_mode`, `_product` e `_int` checam os campos e lançam `RequestError(code, message)`. Em `_int`, `isinstance(value, bool)` aparece porque em Python `True` é um `int`, e isso precisa ser rejeitado.
- As operações:
  - `search` executa e traduz para o formato do enunciado. O status sai `"sucesso"`, `"parcial"` (algum mercado falhou) ou `"erro"` (nenhum respondeu);
  - `compare` roda os dois modos alternando a ordem e calcula o **speedup** = média sequencial ÷ média concorrente;
  - `markets` e `configure` cuidam do status e da configuração dos mercados;
  - `encerrar` só responde "conexão encerrada".

### [aggregator/display.py](../aggregator/display.py): o painel no terminal

É só visualização, usando a biblioteca **Rich**.

- `CallState`/`SearchState` guardam o estado de cada barra. `field(default_factory=...)` cria um valor novo para cada instância; usar uma lista ou dict direto como padrão compartilharia o mesmo objeto entre todas.
- `bar_position()` converte milissegundos em colunas da barra.
- `GraphicDisplay` usa `rich.live.Live` e uma thread que redesenha 12 vezes por segundo. Usa `threading.RLock`, um lock *reentrante* que a mesma thread pode pegar duas vezes, porque `event()` chama `_to_history()`, que também pode usar o lock.
- `event(kind, d)` é chamado **de várias threads** e atualiza o estado conforme o tipo (`market_connect`, `market_response`, `request_end`, ...).
- `__rich__()` é o "protocolo" do Rich: o objeto diz como se desenhar.
- `RawDisplay` (`start.py --raw`) imprime uma linha por evento TCP (CONNECT, ENVIA, RECEBE, CLOSE, RETRY).
- `_display = RawDisplay() if ... else GraphicDisplay()` escolhe a implementação uma vez. As funções `start/stop/event` do módulo apenas delegam para ela.

---

## 6. `client/`: o cliente do usuário

### [client/connection.py](../client/connection.py): `AggregatorClient`

- O `__init__` abre **uma conexão** (`create_connection`, o *three-way handshake*) e a mantém aberta durante a sessão inteira.
- `request(operation, fields)` monta `{"operacao": ..., "id": next(self._ids), **fields}`, envia e espera a resposta.
- `search`, `compare`, `markets` e `configure` são atalhos para cada operação.
- `__enter__`/`__exit__` permitem usar `with AggregatorClient() as c:`. Ao sair, o `close()` envia `"encerrar"` e fecha o socket (encerramento "educado").

### [client/terminal.py](../client/terminal.py): interface de linha de comando

- `_c(code, text)` aplica **códigos ANSI** de cor (`\033[32m` é verde, `\033[0m` reseta), só quando a saída é um terminal (`isatty()`).
- `brl(v)` formata `1234.5` como `R$ 1.234,50`. A formatação americana vira `1,234.50`, e o código troca `,`→`X`, `.`→`,`, `X`→`.`.
- `interactive()` é um laço com `input()`:
  - `line.partition(" ")` separa o comando do resto;
  - `rest.rsplit(" ", 1)` separa o último número em `/compare cafe 3`;
  - `except (EOFError, KeyboardInterrupt)` trata Ctrl+D e Ctrl+C.
- `main()` usa `argparse` com `nargs="?"` (argumento opcional). Sem produto, abre o modo interativo; com produto, faz uma pesquisa e sai.

---

## 7. [start.py](../start.py): sobe tudo

1. Instala handlers de `SIGINT`/`SIGTERM`/`SIGHUP` que lançam `KeyboardInterrupt`, para tratar tudo igual.
2. Gera os bancos se faltar algum (`is_ready` / `seed_all`).
3. Para cada mercado: `subprocess.Popen([sys.executable, "-m", "markets.aurora"], ..., start_new_session=True)`.
   - `sys.executable` é o mesmo Python que rodou o `start.py` (o `python3.12`).
   - `start_new_session=True` faz o Ctrl+C do terminal chegar **só** ao `start.py`, que encerra os filhos na ordem certa.
   - Passa `LAUNCHER_PID` no ambiente, para o watchdog.
4. `wait_port()` tenta conectar até a porta abrir.
5. Sobe o agregador e entra num laço: se algum processo terminar (`p.poll() is not None`), encerra tudo.
6. No `finally`, `shutdown()` para **primeiro o agregador** (que termina as pesquisas em andamento) e **depois os mercados**. `stop()` manda o sinal, espera com `wait(timeout)` e usa `kill()` se o processo não sair.

---

## 8. `experiments/`: os 5 experimentos

- [experiments/\_\_init\_\_.py](../experiments/__init__.py): `importlib.import_module` importa os módulos pelo nome, só quando são usados.
- [experiments/shared.py](../experiments/shared.py): CSV (`csv.writer`/`DictReader`), tabelas em Markdown, gráficos com matplotlib (`matplotlib.use("Agg")` desenha sem janela) e `expected()`, o modelo teórico: sequencial = soma, concorrente = máximo, cada latência limitada ao timeout.
- Cada experimento tem `measure(client, quick)`, que mede **pelo cliente TCP real** e grava o CSV, e `analyze(md)`, que lê o CSV e gera tabela e gráfico.
  1. **exp1/exp2**: 10 rodadas sequenciais e 10 concorrentes, com o speedup.
  2. **exp3**: cenários de latência (0, 200, 500, 1000 ms, um mercado lento, um em timeout).
  3. **exp4**: de 1 a 32 clientes simultâneos. `threading.Barrier(n)` faz todos começarem juntos, e a métrica é a vazão (pesquisas/s).
  4. **exp5**: a SuperVila cai. `threading.Timer(0.3, go_down)` dispara a queda 0,3 s depois do início, por **outra conexão** de administração, enquanto a pesquisa está em andamento.

---

## 9. `tests/`: testes com pytest

- [tests/conftest.py](../tests/conftest.py) define as **fixtures**, preparações reaproveitadas pelos testes:
  - `autouse=True` aplica a fixture em todo teste. Por exemplo, `monkeypatch.setattr(config, "RETRY_WAIT_S", 0.01)` acelera as novas tentativas;
  - `market_cluster` sobe os 5 mercados **em threads**, com `port=0` (o sistema escolhe uma porta livre). `dataclasses.replace` cria uma cópia do `MarketInfo` com a porta nova;
  - `scope="session"` gera os bancos uma única vez por execução.
- Os testes verificam, por exemplo:
  - o sequencial não se sobrepõe (`nxt.start_ms >= prev.end_ms`);
  - o concorrente se sobrepõe e usa 5 threads distintas;
  - o retry funciona;
  - timeout não é repetido;
  - vários clientes ao mesmo tempo funcionam;
  - o desligamento espera as pesquisas.

`scripts/` (`build_report.py`, `diagrams.py`) só gera o relatório e as figuras, e não faz parte do sistema em execução.

---

## 10. O caminho completo de uma pesquisa

Exemplo: você digita `arroz` no cliente, no modo concorrente.

1. **Cliente**: `client.search("arroz", "concorrente", 5)` → `protocol.send` escreve `{"operacao":"consultar","id":1,"produto":"arroz","modo":"concorrente","limite":5}\n` no socket da porta 5050.
2. **Agregador**: a thread `cliente-1` (criada pelo `ThreadingTCPServer`) lê a linha em `ClientHandler.serve` → `dispatch` → `op_search` → `Aggregator.execute("concurrent", ...)`.
3. `concurrent.search` cria **5 threads**. Cada uma chama `query_market` → `ask_once`, abre um socket com o mercado e envia `{"cmd":"SEARCH","q":"arroz"}\n`.
4. **Cada mercado**: o `ThreadingTCPServer` cria a thread `conexão nº N` → `ConnectionHandler.handle` → `simulate_latency()` (espera de 300 a 1200 ms) → `database.search("arroz")` (SQL `LIKE`) → responde `{"ok":true,"data":{"items":[...]},"cpu_ms":...}\n` e fecha.
5. **Agregador**: as 5 threads terminam (a última depois de cerca de 1,2 s). `consolidation.merge_offers` agrupa por produto e ordena as ofertas por preço. `op_search` monta `resultados` com `menor_preco` e `ofertas`.
6. A resposta volta numa linha JSON. O cliente imprime com `show_search`, marcando o mais barato com ★.
7. Durante tudo isso, cada passo chamou `emit(...)` → `display.event(...)`, que desenha as barras no terminal do agregador.

---

## Restos da renomeação (já corrigidos)

Alguns nomes antigos tinham ficado para trás quando o código foi passado para inglês. Todos já foram corrigidos:

- [client/\_\_init\_\_.py](../client/__init__.py) tinha `__all__ = ["ClienteAgregador"]`, mas a classe se chama `AggregatorClient`, e por isso `from client import *` dava erro. Agora está `__all__ = ["AggregatorClient"]`.
- A docstring de [client/connection.py](../client/connection.py) mostrava `ClienteAgregador()` e `c.consultar(...)`. Agora mostra `AggregatorClient()` e `c.search(...)`.
- Os comentários de [requirements.txt](../requirements.txt) citavam `agregador/registro.py` e `scripts/gerar_relatorio.py`. Agora citam os nomes atuais, `aggregator/display.py` e `scripts/build_report.py`.
