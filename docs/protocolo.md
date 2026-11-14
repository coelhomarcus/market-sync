# Protocolo de aplicação

O sistema tem dois trechos em TCP puro, e os dois usam o mesmo enquadramento (*framing*) de mensagens:

| Trecho | Porta | Quem abre a conexão | Mensagens |
|---|---|---|---|
| Cliente → agregador | 5050 | `cliente/`, `experimentos/` | `{"operacao": ...}` no formato sugerido pelo enunciado (seção 2) |
| Agregador → supermercados | 5001–5005 | `agregador/consulta_mercado.py` | `{"cmd": ...}`, comandos internos curtos (seção 3) |

A loja web conversa com o agregador por HTTP (três rotas, ver `arquitetura.md`); por trás, as consultas aos supermercados são as mesmas.

## 1. Enquadramento: uma mensagem JSON por linha

### Por que é preciso

O TCP entrega um **fluxo de bytes** confiável e ordenado, mas não preserva fronteiras de mensagem: um `send()` de 500 bytes pode chegar como dois `recv()` de 250, e duas mensagens seguidas podem chegar grudadas num único `recv()`. Por isso a aplicação define onde cada mensagem começa e termina.

### Formato

```
{"operacao":"consultar","produto":"arroz"}\n
```

- Cada mensagem é um objeto JSON em UTF-8 terminado por `\n`. O JSON nunca tem quebra de linha crua dentro dele (uma quebra num texto vira `\n` escapado), então a linha delimita a mensagem.
- Os dois lados usam o socket como arquivo (`sock.makefile("rwb")`); `readline()` junta os pedaços que o TCP entregar até achar o `\n`, e o que sobrar fica no buffer para a próxima leitura.
- Limite de 16 MB por linha, para que uma "linha" sem fim não esgote a memória.
- Se a conexão fecha antes do primeiro byte, `receive` devolve `(None, 0)` (fim normal). Se fecha no meio de uma linha, ou o JSON é inválido, levanta `ProtocolError`.

Implementação: `backend/comum/protocolo.py` (`send` e `receive`, usados pelos quatro lados).

## 2. Cliente ↔ agregador (porta 5050)

Servidor: `agregador/servidor_tcp.py`. Cliente: `backend/cliente/` (classe `ClienteAgregador`).

### Regras gerais

- Toda requisição tem o campo `operacao`. Pode ter também um `id` (qualquer valor JSON), que o agregador devolve na resposta para o cliente casar pedido e resposta.
- Toda resposta tem `operacao` (repetida do pedido) e `status`:
  - `"sucesso"`: tudo certo;
  - `"parcial"`: a pesquisa foi feita, mas algum supermercado não respondeu (os outros resultados vêm normalmente);
  - `"erro"`: o pedido não pôde ser atendido; vêm também `codigo` e `mensagem`.
- Uma conexão pode levar **várias operações seguidas**, sempre uma pergunta e uma resposta por vez. O cliente de terminal abre a conexão no início da sessão e só a encerra ao sair.
- Modos aceitos: `"sequencial"` e `"concorrente"` (padrão `"concorrente"`).

### consultar — pesquisar um produto

```json
→ {"operacao": "consultar", "produto": "arroz branco 5 kg", "modo": "concorrente", "limite": 2, "id": 1}
← {"operacao": "consultar", "id": 1, "status": "sucesso",
   "produto": "arroz branco 5 kg", "modo": "concorrente", "tempo_total_ms": 1072.4,
   "produtos_encontrados": 10, "ofertas_encontradas": 46,
   "resultados": [
     {"produto": "Arroz Branco Tipo 1", "marca": "Sabor da Terra", "unidade": "5 kg", "categoria": "Mercearia",
      "slug": "arroz-branco-sabor-da-terra-5-kg",
      "menor_preco": {"fonte": "Mercado Aurora", "preco": 20.19}, "maior_preco": 26.59, "economia": 6.4,
      "ofertas": [
        {"fonte": "Mercado Aurora", "produto": "Arroz Branco Tipo 1 Sabor da Terra 5 kg", "preco": 20.19, "status": "sucesso"},
        {"fonte": "Max Atacarejo",  "produto": "Arroz Branco Tipo 1 Sabor da Terra 5 kg", "preco": 22.49, "status": "sucesso"},
        ...]},
     ...],
   "mercados": [
     {"id": "aurora", "fonte": "Mercado Aurora", "status": "sucesso", "inicio_ms": 0.4, "fim_ms": 351.2,
      "tempo_ms": 350.8, "tentativas": 1, "bytes_recebidos": 9312, "erro": null},
     ...]}
```

- `produto` é obrigatório (até 80 caracteres); a busca ignora acentos e maiúsculas e exige que todas as palavras apareçam.
- `limite` (1–100, padrão 10): quantos produtos devolver. Os produtos vêm do menor para o maior preço; as ofertas de cada produto também.
- Cada oferta segue o formato do exemplo do enunciado (`fonte`, `produto`, `preco`, `status`); `status` é `"sem_estoque"` quando o supermercado tem o produto mas sem estoque.
- `mercados` diz o que aconteceu com cada supermercado: tempo, tentativas, bytes e o erro, se houve.

### comparar — mesma pesquisa nos dois modos

```json
→ {"operacao": "comparar", "produto": "cafe", "repeticoes": 3}
← {"operacao": "comparar", "status": "sucesso", "produto": "cafe", "repeticoes": 3,
   "sequencial":  {"tempo_medio_ms": 3581.2, "tempo_min_ms": 3502.0, "tempo_max_ms": 3660.1, "mercados_ok": 5, "mercados": [...]},
   "concorrente": {"tempo_medio_ms": 1104.9, "tempo_min_ms": 1049.3, "tempo_max_ms": 1161.0, "mercados_ok": 5, "mercados": [...]},
   "speedup": 3.24}
```

`repeticoes` vai de 1 a 10. A ordem dos modos alterna a cada rodada para nenhum deles levar vantagem.

### cesta — total de uma cesta em cada supermercado

```json
→ {"operacao": "cesta", "modo": "concorrente",
   "itens": [{"produto": "leite-integral-pasto-alto-1-l", "quantidade": 2}, {"produto": "cafe-torrado-...", "quantidade": 1}]}
← {"operacao": "cesta", "status": "sucesso", "modo": "concorrente", "tempo_total_ms": 1230.5,
   "totais": [{"fonte": "SuperVila", "status": "sucesso", "total": 12.67, "completa": true, "faltando": [], "erro": null}, ...],
   "mais_barato": {"fonte": "SuperVila", "total": 12.67},
   "mercados": [...]}
```

`produto` aqui é o `slug` devolvido pela operação `consultar`. `totais` vem do menor para o maior, primeiro as cestas completas; `mais_barato` só considera cestas completas (é `null` se nenhum supermercado tem tudo).

### mercados — situação de cada supermercado

```json
→ {"operacao": "mercados"}
← {"operacao": "mercados", "status": "sucesso", "clientes_conectados": 1,
   "mercados": [{"id": "aurora", "fonte": "Mercado Aurora", "porta": 5001, "alcancavel": true, "online": true,
                 "latencia_ms": 300, "produtos": 1689, "erro": null}, ...]}
```

### configurar — latência e disponibilidade (experimentos)

```json
→ {"operacao": "configurar", "mercado": "ipe", "latencia_ms": 2500}
→ {"operacao": "configurar", "mercado": "ipe", "online": false}
← {"operacao": "configurar", "status": "sucesso", "mercado": "ipe", "fonte": "Mercadinho Ipê", "online": false, "latencia_ms": 2500}
```

O agregador repassa a mudança ao supermercado com o comando `CONFIG` (seção 3). `latencia_ms` vai de 0 a 10 000.

### encerrar — fim da conversa

```json
→ {"operacao": "encerrar"}
← {"operacao": "encerrar", "status": "sucesso", "mensagem": "conexão encerrada"}
```

Depois de responder, o agregador fecha o socket.

### Códigos de erro

| Código | Quando acontece | A conexão continua? |
|---|---|---|
| `MENSAGEM_INVALIDA` | A linha não é JSON válido ou não é um objeto. | Sim |
| `MENSAGEM_INVALIDA` | A conexão fechou no meio de uma linha, ou a linha passou de 16 MB. | Não (o agregador fecha) |
| `OPERACAO_DESCONHECIDA` | `operacao` ausente ou desconhecida. | Sim |
| `PARAMETRO_INVALIDO` | Falta `produto`, `modo` inválido, `limite`/`repeticoes`/`quantidade` fora da faixa, `itens` vazio. | Sim |
| `MERCADO_DESCONHECIDO` | `configurar` com um id de supermercado que não existe. | Sim |
| `MERCADO_INDISPONIVEL` | `configurar` num supermercado cujo processo não responde. | Sim |
| `NENHUM_MERCADO_RESPONDEU` | `consultar` sem nenhum supermercado respondendo. Vem com `mercados` explicando cada falha. | Sim |
| `TEMPO_ESGOTADO` | O cliente ficou 5 minutos sem enviar nada. | Não (o agregador fecha) |
| `ERRO_INTERNO` | Exceção inesperada no agregador. A thread do cliente sobrevive. | Sim |

Exemplo:

```json
→ {"operacao": "consultar", "produto": "arroz", "modo": "paralelo"}
← {"operacao": "consultar", "status": "erro", "codigo": "PARAMETRO_INVALIDO",
   "mensagem": "modo inválido: 'paralelo' (use 'sequencial' ou 'concorrente')"}
```

Falhas de um supermercado **não** são erros do pedido: viram `status: "parcial"` com o motivo em `mercados[].erro` (ver seção 4).

## 3. Agregador ↔ supermercados (portas 5001–5005)

Cada conexão carrega **uma pergunta e uma resposta**: o agregador conecta, envia a linha, lê a linha de resposta e fecha.

Toda requisição tem o campo `cmd`. Toda resposta tem `ok`; quando `ok` é verdadeiro vem `data`, senão vem `error`.

### STATUS
```json
→ {"cmd": "STATUS"}
← {"ok": true, "data": {"online": true, "latency_ms": 300, "products": 1689,
    "db_bytes": 1003520, "requests_served": 12, "thread_count": 2}, "cpu_ms": 0.2}
```
`STATUS` e `CONFIG` respondem mesmo com o mercado fora do ar (uso administrativo). Toda resposta traz `cpu_ms`, a CPU que a thread do mercado gastou, e `thread`, o nome da thread do mercado que atendeu a conexão (por exemplo `"Thread-7"`; o painel do agregador mostra).

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

### Ciclo de uma consulta (lado do agregador, `agregador/consulta_mercado.py`)

1. `socket.create_connection((host, porta), timeout=3)` — cria o socket e faz o *three-way handshake*. Mede `connect_ms`.
2. `protocol.send` — escreve a linha da pergunta.
3. `protocol.receive` — espera a linha da resposta. Mede `wait_ms` (latência simulada + processamento no mercado) e `bytes_received`.
4. Fecha a conexão (bloco `with`).

## 4. Falhas e retry

| Situação | O que o cliente vê | O que o agregador faz |
|---|---|---|
| Mercado "fora do ar" (antes ou durante a consulta) | conexão aceita e fechada sem resposta (`receive` → `None`) | **tenta de novo** até 3 vezes, esperando 0,5 s, 1 s e 2 s; depois desiste: "fora do ar (4 tentativas)" |
| Processo do mercado parado | `ConnectionRefusedError` no connect | **tenta de novo** do mesmo jeito: "conexão recusada (4 tentativas)" |
| Latência acima de 3 s | `socket.timeout` no `readline` | desiste na hora: "tempo esgotado (3,0 s)". Repetir só faria esperar mais 3 s |
| Mensagem inválida | `ProtocolError` | desiste na hora |

As esperas crescem (*backoff* exponencial) para não bombardear um servidor que está com problema. Um mercado fora do ar custa cerca de 3,5 s de espera: no modo **sequencial** essa espera atrasa todos os mercados seguintes; no **concorrente** ela acontece enquanto os outros respondem, e o usuário recebe os resultados dos outros 4 mesmo assim.

## 5. Encerramento das conexões

| Trecho | Quem encerra | Como |
|---|---|---|
| Cliente → agregador | o cliente, normalmente | envia `{"operacao": "encerrar"}`, recebe a confirmação e o agregador fecha o socket (FIN). `ClienteAgregador` faz isso ao sair do `with`. |
| Cliente → agregador | o cliente, abruptamente | fecha o socket sem avisar (Ctrl+C, processo morto). O `readline()` do agregador recebe fim de arquivo, a thread do cliente termina e o contador de clientes conectados volta. Se a conexão cai no meio de uma linha, o agregador descarta o pedaço. |
| Cliente → agregador | o agregador | depois de 5 minutos sem nenhuma mensagem, envia `TEMPO_ESGOTADO` e fecha. Ao desligar o agregador (Ctrl+C), as threads de cliente são *daemon* e o socket de escuta é fechado. |
| Agregador → supermercado | o agregador | uma conexão por consulta: lê a resposta e fecha (bloco `with`). Se passar de 3 s sem resposta, fecha por timeout. |
| Agregador → supermercado | o supermercado | quando está "fora do ar", fecha a conexão sem responder; se cai durante a espera de uma consulta, a conexão em andamento também é fechada. O agregador trata isso como falha e tenta de novo. |

Os comandos administrativos (`STATUS`, `CONFIG`) continuam respondendo com o supermercado fora do ar, para que ele possa ser trazido de volta.

## 6. Testes do protocolo

`backend/tests/test_protocolo.py` verifica: ida e volta com acentos, uma mensagem = uma linha, mensagem enviada em pedaços de 7 bytes (fragmentação), duas mensagens grudadas, fechamento limpo, fechamento no meio da linha e JSON inválido. `test_estrategias.py` cobre o retry (desiste após 4 tentativas, sucesso quando o mercado volta no meio, esperas 0,1 → 0,2 → 0,4 s e o custo no sequencial). `test_servidor_tcp.py` cobre o trecho cliente ↔ agregador: formato das respostas, ordenação, várias operações na mesma conexão, cada código de erro, JSON inválido sem perder a conexão, desconexão abrupta, supermercado caindo durante a pesquisa e 8 clientes simultâneos.
