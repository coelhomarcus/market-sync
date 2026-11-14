# Protocolo TCP entre agregador e mercados

## Por que é preciso um protocolo

O TCP entrega um **fluxo de bytes** confiável e ordenado, mas não preserva fronteiras de mensagem: um `send()` de 500 bytes pode chegar como dois `recv()` de 250, e duas mensagens seguidas podem chegar grudadas num único `recv()`. Por isso a aplicação define onde cada mensagem começa e termina.

## Formato do frame

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|            Tamanho N do corpo (uint32, big-endian)            |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                 Corpo: N bytes de JSON em UTF-8 ...           |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

- O cabeçalho usa ordem de rede (big-endian), `struct.Struct(">I")`.
- O receptor lê exatamente 4 bytes, depois exatamente N bytes, repetindo `recv()` até completar (`_recv_exact`).
- Limite de 8 MiB por mensagem, para que um cabeçalho corrompido não faça o servidor tentar alocar gigabytes.
- Se a conexão fechar antes do primeiro byte, `recv_msg` devolve `None` (fim normal). Se fechar no meio de um frame, levanta `ProtocolError`.

Exemplo: `{"cmd":"PING"}` tem 14 bytes, então o frame é `00 00 00 0E` seguido de `7B 22 63 6D 64 22 3A 22 50 49 4E 47 22 7D`.

## Mensagens

Toda requisição tem o campo `cmd`. Toda resposta tem `ok`; quando `ok` é verdadeiro vem `data`, senão vem `error`.

### PING / STATUS
```json
→ {"cmd": "STATUS"}
← {"ok": true, "data": {"market": {"id": "aurora", "name": "Mercado Aurora"},
    "online": true, "latency_ms": 300, "products": 33, "requests_served": 12, "thread_count": 2}}
```
`PING` é recusado quando o mercado está fora do ar; `STATUS` responde sempre (uso administrativo) e informa também `history_rows` e `db_bytes`, o tamanho do banco.

### SEARCH
```json
→ {"cmd": "SEARCH", "q": "feijão"}
← {"ok": true, "data": {"market": {"id": "aurora", "name": "Mercado Aurora"}, "items": [
    {"slug": "feijao-carioca-bom-campo-1-kg", "name": "Feijão Carioca", "brand": "Bom Campo",
     "category": "Mercearia", "unit": "1 kg", "image": "feijao-carioca-1kg",
     "price": 7.69, "stock": 81, "sort_order": 1203}, ...]}}
```
A busca ignora acentos e maiúsculas, exige que todas as palavras apareçam (nome, marca, categoria, tamanho ou palavras-chave) e devolve os itens ordenados por preço. `q` vazio devolve o sortimento inteiro do mercado (de 1.352 a 1.690 itens, entre 270 e 340 KB por resposta). Categoria, ordenação e paginação são feitas pelo agregador, depois de juntar as ofertas dos cinco mercados.

### HISTORY
```json
→ {"cmd": "HISTORY", "slug": "feijao-carioca-bom-campo-1-kg", "days": 90}
← {"ok": true, "data": {"market": {...}, "slug": "...", "points": [{"day": "2026-08-16", "price": 7.99}, ...]}}
```
Preço diário do produto nos últimos `days` dias (até 365), lido da tabela `price_history`.

### BASKET
```json
→ {"cmd": "BASKET", "items": [{"slug": "arroz-branco-5kg", "qty": 1}, {"slug": "cafe-torrado-500g", "qty": 2}]}
← {"ok": true, "data": {"market": {...}, "total": 66.77, "missing": [],
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

## Ciclo de uma consulta (lado do agregador)

1. `socket.create_connection((host, porta), timeout=3)` — cria o socket e faz o *three-way handshake*. Mede `connect_ms`.
2. `send_msg` — `sendall()` do frame. Mede `send_ms`.
3. `recv_msg_sized` — espera o frame de resposta. Mede `wait_ms` (inclui a latência simulada e o processamento no mercado) e `bytes_received`, o tamanho do frame.
4. Fecha a conexão (bloco `with`).

| Situação | O que o cliente vê | Mensagem no sistema |
|---|---|---|
| Processo do mercado parado | `ConnectionRefusedError` no connect | "conexão recusada (processo do mercado não está rodando)" |
| Mercado "fora do ar" | conexão aceita e fechada sem resposta (`recv_msg` → `None`) | "o mercado encerrou a conexão sem responder (fora do ar?)" |
| Latência acima de 3 s | `socket.timeout` no `recv` | "tempo esgotado (3,0 s)" |
| Frame inválido | `ProtocolError` | texto do erro |

## Testes do protocolo

`backend/tests/test_protocol.py` verifica: ida e volta com acentos, prefixo de tamanho correto, mensagem enviada em pedaços de 7 bytes (fragmentação), duas mensagens grudadas, fechamento limpo, fechamento no meio do frame e tamanho absurdo.
