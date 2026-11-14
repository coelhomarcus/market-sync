# Relatório técnico

| Arquivo | Para que serve |
|---|---|
| `relatorio.md` | **Versão atual (14/11/2026)**, com a estrutura pedida no enunciado: introdução, requisitos, modelagem, implementação, testes, experimentos, resultados e conclusão. Aponta para as figuras em `figuras/`. |
| `relatorio.docx`, `relatorio.pdf` | Gerados do `relatorio.md` por `scripts/gerar_relatorio.py`, com capa e figuras embutidas. **Não edite à mão**: edite o `.md` (ou a capa) e gere de novo. |
| `capa.json` | Dados da capa: instituição, curso, disciplina, integrantes, professor, cidade e data. |
| `figuras/` | As figuras em PNG. |
| `dados/` | Os números de cada gráfico em CSV e as tabelas dos experimentos obrigatórios (`resultados-experimentos.md`). |

## Figuras do relatório

| Figura no texto | Arquivo | Seção | Como é gerada |
|---|---|---|---|
| 1. Casos de uso | `fig-01-casos-de-uso.png` | 3.1 | `scripts/diagramas.py` |
| 2. Arquitetura | `fig-02-arquitetura.png` | 3.2 | `scripts/diagramas.py` |
| 3. Sequência de uma pesquisa | `fig-12-sequencia.png` | 3.3 | `scripts/diagramas.py` |
| 4. Uma consulta em detalhe | `fig-03-gantt-consulta.png` | 6.1 | `dados/01-gantt-consulta.csv` |
| 5. Experimentos 1 e 2 | `fig-08-exp1-exp2.png` | 6.2 | `experimentos/` ← `dados/07-*.csv` |
| 6. Experimento 3 | `fig-09-exp3-latencia.png` | 6.3 | `experimentos/` ← `dados/08-*.csv` |
| 7. Experimento 4 | `fig-10-exp4-clientes.png` | 6.4 | `experimentos/` ← `dados/09-*.csv` |
| 8. Experimento 5 | `fig-11-exp5-falha.png` | 6.5 | `experimentos/` ← `dados/10-*.csv`, `dados/11-*.csv` |
| 9. Número de mercados | `fig-05-por-mercados.png` | 6.6 | `dados/03-por-mercados.csv` |
| 10. Número de threads | `fig-06-por-threads.png` | 6.6 | `dados/04-por-threads.csv` |
| 11. Consumo de CPU | `fig-07-recursos.png` | 6.6 | `dados/06-recursos.csv` |

`fig-04-cenarios.png` e `dados/02-cenarios.csv` são da versão anterior (cenários E1–E5 de 13/11) e foram substituídos pelo Experimento 3. `dados/05-volume-dados.csv` é a tabela de volume de dados (complementar).

## Como refazer

- Experimentos obrigatórios (com o `iniciar.py` rodando): `cd backend && .venv/bin/python -m experimentos`. Para refazer só tabelas e gráficos a partir dos CSV: `--analisar`.
- Diagramas de casos de uso, arquitetura e sequência: `backend/.venv/bin/python scripts/diagramas.py` (da raiz do projeto).
- DOCX e PDF: `backend/.venv/bin/python scripts/gerar_relatorio.py` (da raiz do projeto; precisa do LibreOffice). O caminho é Markdown → HTML com as figuras embutidas → LibreOffice → DOCX → PDF, e leva poucos segundos. `--html` guarda também o HTML intermediário.

O roteiro e a discussão de cada experimento estão em [`../experimentos.md`](../experimentos.md).

## Pendências para a entrega

- Preencher `capa.json` (instituição, curso, integrantes, professor, cidade) e gerar o DOCX/PDF de novo.
- Slides da apresentação (seção 11 do enunciado).
