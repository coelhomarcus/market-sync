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

**Um experimento rápido** (com `./start.py --quiet` no Terminal 1)
```bash
python3.12 -m experiments.exp2_concurrent --quick
```
Os experimentos gravam por cima dos dados do relatório; para voltar:
```bash
git checkout docs/relatorio/dados docs/relatorio/figuras
```

**Supermercado sozinho (serviço independente)** (Ctrl+C no `./start.py` antes)
```bash
python3.12 -m markets.aurora
```
```bash
python3.12 -c "import socket; s=socket.create_connection(('127.0.0.1',5001)); s.sendall(b'{\"cmd\":\"SEARCH\",\"q\":\"arroz\"}\n'); print(s.makefile().readline()[:300])"
```
