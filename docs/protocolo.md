# Protocolo TCP entre agregador e mercados

## Por que é preciso um protocolo

O TCP entrega um **fluxo de bytes** confiável e ordenado, mas não preserva fronteiras de mensagem: um `send()` de 500 bytes pode chegar como dois `recv()` de 250, e duas mensagens seguidas podem chegar grudadas num único `recv()`. Por isso a aplicação define onde cada mensagem começa e termina.

## Formato: uma mensagem JSON por linha

```
{"cmd":"SEARCH","q":"arroz"}\n
```

- Cada mensagem é um objeto JSON em UTF-8 terminado por `\n`. O JSON nunca tem quebra de linha crua dentro dele (uma quebra num texto vira `\n` escapado), então a linha delimita a mensagem.
- Os dois lados usam o socket como arquivo (`sock.makefile("rwb")`); `readline()` junta os pedaços que o TCP entregar até achar o `\n`, e o que sobrar fica no buffer para a próxima leitura.
- Limite de 16 MB por linha, para que uma "linha" sem fim não esgote a memória.
- Se a conexão fecha antes do primeiro byte, `receive` devolve `(None, 0)` (fim normal). Se fecha no meio de uma linha, ou o JSON é inválido, levanta `ProtocolError`.

Cada conexão carrega **uma pergunta e uma resposta**: o agregador conecta, envia a linha, lê a linha de resposta e fecha.

## Mensagens

Toda requisição tem o campo `cmd`. Toda resposta tem `ok`; quando `ok` é verdadeiro vem `data`, senão vem `error`.

### STATUS
```json
→ {"cmd": "STATUS"}
← {"ok": true, "data": {"online": true, "latency_ms": 300, "products": 1689,
    "db_bytes": 1003520, "requests_served": 12, "thread_count": 2}, "cpu_ms": 0.2}
```
`STATUS` e `CONFIG` respondem mesmo com o mercado fora do ar (uso administrativo). Toda resposta traz `cpu_ms`, a CPU que a thread do mercado gastou.

### SEARCH
```json
→ {"cmd": "SEARCH", "q": "feijão"}
← {"ok": true, "data": {"items": [
    {"slug": "feijao-carioca-bom-campo-1-kg", "name": "Feijão Carioca", "brand": "Bom Campo",
     "category": "Mercearia", "unit": "1 kg", "image": "feijao-carioca-1kg",
     "price": 7.69, "stock": 81, "sort_order": 1203}, ...]}}
```
A busca ignora acentos e maiúsculas, exige que todas as palavras apareçam (nome, marca, categoria, tamanho ou palavras-chave) e devolve os itens ordenados por preço. `q` vazio devolve o sortimento inteiro do mercado (de 1.352 a 1.690 itens, entre 270 e 340 KB por resposta). Categoria, ordenação e paginação são feitas pelo agregador, depois de juntar as ofertas dos cinco mercados.

### BASKET
```json
→ {"cmd": "BASKET", "items": [{"slug": "arroz-branco-5kg", "qty": 1}, {"slug": "cafe-torrado-500g", "qty": 2}]}
← {"ok": true, "data": {"total": 66.77, "missing": [],
    "lines": [{"slug": "arroz-branco-5kg", "name": "Arroz Branco Tipo 1", "qty": 1, "price": 28.99, "subtotal": 28.99}, ...]}}
```
Itens que o mercado não vende ou estão sem estoque vão para `missing` e não entram no total.

### CONFIG
```json
→ {"cmd": "CONFIG", "latency_ms": 800, "online": false}
← {"ok": true, "data": { ...mesmo formato do STATUS... }}
```
Ambos os campos são opcionais. Latência limitada a 0–10 000 ms.

### Erros
```json
→ {"cmd": "DANCE"}
← {"ok": false, "error": "comando desconhecido: 'DANCE'"}
```

## Ciclo de uma consulta (lado do agregador, `aggregator/client.py`)

1. `socket.create_connection((host, porta), timeout=3)` — cria o socket e faz o *three-way handshake*. Mede `connect_ms`.
2. `protocol.send` — escreve a linha da pergunta.
3. `protocol.receive` — espera a linha da resposta. Mede `wait_ms` (latência simulada + processamento no mercado) e `bytes_received`.
4. Fecha a conexão (bloco `with`).

## Falhas e retry

| Situação | O que o cliente vê | O que o agregador faz |
|---|---|---|
| Mercado "fora do ar" | conexão aceita e fechada sem resposta (`receive` → `None`) | **tenta de novo** até 3 vezes, esperando 0,5 s, 1 s e 2 s; depois desiste: "fora do ar (4 tentativas)" |
| Processo do mercado parado | `ConnectionRefusedError` no connect | **tenta de novo** do mesmo jeito: "conexão recusada (4 tentativas)" |
| Latência acima de 3 s | `socket.timeout` no `readline` | desiste na hora: "tempo esgotado (3,0 s)". Repetir só faria esperar mais 3 s |
| Mensagem inválida | `ProtocolError` | desiste na hora |

As esperas crescem (*backoff* exponencial) para não bombardear um servidor que está com problema. Um mercado fora do ar custa cerca de 3,5 s de espera: no modo **sequencial** essa espera atrasa todos os mercados seguintes; no **concorrente** ela acontece enquanto os outros respondem, e o usuário recebe os resultados dos outros 4 mesmo assim.

## Testes do protocolo

`backend/tests/test_protocol.py` verifica: ida e volta com acentos, uma mensagem = uma linha, mensagem enviada em pedaços de 7 bytes (fragmentação), duas mensagens grudadas, fechamento limpo, fechamento no meio da linha e JSON inválido. `test_strategies.py` cobre o retry (desiste após 4 tentativas, sucesso quando o mercado volta no meio, esperas 0,1 → 0,2 → 0,4 s e o custo no sequencial).
