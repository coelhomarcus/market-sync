# Roteiro da apresentação

Todos os comandos são rodados na raiz do projeto.

## 1. Testes automatizados

```bash
python3.12 -m pytest -v
```

## 2. Subir o sistema (Terminal 1)

```bash
./start.py
```

## 3. Cliente (Terminal 2)

```bash
./client.py
```

Dentro do cliente:

**Concorrente (padrão)**
```
arroz
```

**Sequencial**
```
/seq
```
```
arroz
```
```
/con
```

**Comparar os dois modos**
```
/compare arroz 3
```

**Situação dos mercados**
```
/markets
```

**Latência**
```
/latency ipe 2500
```
```
arroz
```
```
/latency ipe 1200
```

**Timeout (acima de 3000 ms)**
```
/latency ipe 4000
```
```
arroz
```
```
/latency ipe 1200
```

**Mercado fora do ar**
```
/down supervila
```
```
arroz
```
```
/up supervila
```

**JSON do protocolo**
```
/json
```
```
cafe
```
```
/json
```

**Sair**
```
/exit
```

## 4. Vários clientes ao mesmo tempo (Terminal 2)

```bash
./client.py arroz --limit 1 & ./client.py cafe --limit 1 & ./client.py leite --limit 1 & wait
```

## 5. Pesquisa única pela linha de comando (Terminal 2)

```bash
./client.py "arroz branco 5 kg" --mode seq
```

```bash
./client.py cafe --compare 3
```

## 6. Modo raw: cada chamada TCP linha a linha

Terminal 1 (Ctrl+C no anterior):
```bash
./start.py --raw
```

Terminal 2:
```bash
./client.py arroz
```

## 7. Experimentos

Terminal 1 (Ctrl+C no anterior):
```bash
./start.py --quiet
```

Terminal 2, um de cada vez:
```bash
python3.12 -m experiments.exp1_sequential --quick
```

```bash
python3.12 -m experiments.exp2_concurrent --quick
```

```bash
python3.12 -m experiments.exp3_latency --quick
```

```bash
python3.12 -m experiments.exp4_multiple_clients --quick
```

```bash
python3.12 -m experiments.exp5_unavailability --quick
```

Ou todos juntos (cerca de 6 minutos):
```bash
python3.12 -m experiments
```

Tabelas e gráficos:
```bash
open docs/relatorio/dados/resultados-experimentos.md docs/relatorio/figuras
```

Depois, voltar os dados originais do relatório (os experimentos gravam por cima):
```bash
git checkout docs/relatorio/dados docs/relatorio/figuras
```

## 8. Supermercado sozinho (serviço independente)

Terminal 1 (Ctrl+C no anterior):
```bash
python3.12 -m markets.aurora
```

Terminal 2:
```bash
python3.12 -c "import socket; s=socket.create_connection(('127.0.0.1',5001)); s.sendall(b'{\"cmd\":\"SEARCH\",\"q\":\"arroz\"}\n'); print(s.makefile().readline()[:300])"
```
