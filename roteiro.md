# Roteiro da apresentação

Demonstração de ~5 minutos com 3 terminais abertos lado a lado, todos na raiz do projeto.

## Preparação

**Terminal 1 — servidor (agregador + 5 mercados)**
```bash
./start.py
```

**Terminal 2 — cliente concorrente**
```bash
./client.py
```

**Terminal 3 — cliente sequencial**
```bash
./client.py --mode seq
```

Os dois clientes ficam conectados ao mesmo tempo: o agregador atende cada um numa thread própria.

## 1. Sequencial × concorrente

Digitar nos dois clientes (Terminal 3 e Terminal 2):
```
arroz
```

- Sequencial: ~3,6 s, a soma das latências (300 + 500 + 700 + 900 + 1200 ms).
- Concorrente: ~1,2 s, a latência do mercado mais lento.
- No Terminal 1 aparece "cliente-N conectou" para cada cliente e um painel por pesquisa: no concorrente as
  barras dos 5 mercados começam juntas (5 threads); no sequencial formam uma escada (1 thread).

## 2. Speedup em números (Terminal 2)

```
/compare arroz 3
```

## 3. Timeout (Terminal 2)

O Ipê passa do limite de 3 s, fica como indisponível e o restante da resposta chega normalmente.
```
/latency ipe 4000
```
```
arroz
```
```
/latency ipe 1200
```

## 4. Mercado fora do ar (Terminal 2)

```
/down supervila
```
```
arroz
```
```
/up supervila
```

## 5. JSON do protocolo (opcional, Terminal 2)

```
/json
```
```
cafe
```
```
/json
```

Para sair de cada cliente: `/exit`.

## Experimentos

Cada experimento mostra no terminal o **objetivo**, o **esperado**, as medições e um **resultado** resumido.
Com `--quick` rodam menos rodadas (números um pouco diferentes do relatório, que usa a versão completa).

**Terminal 1** (Ctrl+C no `./start.py` anterior): sistema sem o painel, para não poluir a tela
```bash
./start.py --quiet
```

### Experimento 1 — consulta sequencial (~10 s)
Consulta os 5 mercados um de cada vez, numa única thread. Esperado: tempo ≈ **soma** das latências (3,60 s).
```bash
python3.12 -m experiments.exp1_sequential --quick
```

### Experimento 2 — consulta concorrente (~5 s)
Uma thread por mercado, todas ao mesmo tempo. Esperado: tempo ≈ **maior** latência (1,20 s). Compara com o
Experimento 1 e mostra o speedup (~3×).
```bash
python3.12 -m experiments.exp2_concurrent --quick
```

### Experimento 3 — simulação de latência (~1 min)
Muda a latência dos mercados em 7 cenários (0, 200, 500 e 1000 ms em todos, padrão, um lento, um em timeout)
e compara os dois modos em cada um. Mostra que o ganho cresce com a espera (até ~4,6× com latências iguais),
que um mercado lento limita o concorrente e que o timeout de 3 s corta a espera.
```bash
python3.12 -m experiments.exp3_latency --quick
```

### Experimento 4 — múltiplos clientes (~20 s)
1, 2 e 4 clientes ao mesmo tempo, cada um com sua própria conexão TCP. Mostra que o tempo de cada pesquisa
quase não muda e a vazão cresce: o agregador atende cada cliente numa thread própria.
```bash
python3.12 -m experiments.exp4_multiple_clients --quick
```

### Experimento 5 — indisponibilidade de serviço (~35 s)
Tira a SuperVila do ar em 4 cenários (todos no ar, fora antes, cai durante, cai e volta). Mostra que a pesquisa
nunca falha: o agregador tenta de novo (0,5 s, 1 s, 2 s) e responde com os outros 4 mercados.
```bash
python3.12 -m experiments.exp5_unavailability --quick
```

### Todos de uma vez
```bash
python3.12 -m experiments --quick
```
(Versão completa, a do relatório: `python3.12 -m experiments`, cerca de 6 minutos.)

**Depois:** os experimentos gravam por cima dos dados e gráficos do relatório; para voltar aos originais:
```bash
git checkout docs/relatorio/dados docs/relatorio/figuras
```

---

## Reserva (se perguntarem)

**Testes automatizados**
```bash
python3.12 -m pytest -v
```

**Situação dos mercados** (dentro do cliente)
```
/markets
```

**Vários clientes de uma vez**
```bash
./client.py arroz --limit 1 & ./client.py cafe --limit 1 & ./client.py leite --limit 1 & wait
```

**Modo raw: cada chamada TCP linha a linha** (Ctrl+C no `./start.py` antes)
```bash
./start.py --raw
```

**Supermercado sozinho (serviço independente)** (Ctrl+C no `./start.py` antes)
```bash
python3.12 -m markets.aurora
```
```bash
python3.12 -c "import socket; s=socket.create_connection(('127.0.0.1',5001)); s.sendall(b'{\"cmd\":\"SEARCH\",\"q\":\"arroz\"}\n'); print(s.makefile().readline()[:300])"
```
