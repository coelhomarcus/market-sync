# Relatório técnico

| Arquivo | Para que serve |
|---|---|
| `relatorio.md` | **Versão atual (14/11/2026)**, com a estrutura pedida no enunciado: introdução, requisitos, modelagem, implementação, testes, experimentos, resultados e conclusão. Aponta para as figuras em `figuras/`. |
| `relatorio.docx`, `relatorio.pdf` | Gerados do `relatorio.md` por `scripts/build_report.py`, com capa e figuras embutidas. **Não edite à mão**: edite o `.md` (ou a capa) e gere de novo. |
| `capa.json` | Dados da capa: instituição, curso, disciplina, integrantes, professor, cidade e data. |
| `figuras/` | As figuras em PNG. |
| `dados/` | Os dados brutos de cada experimento em CSV e as tabelas geradas a partir deles (`resultados-experimentos.md`). |

## Figuras do relatório

| Figura no texto | Arquivo | Seção | Como é gerada |
|---|---|---|---|
| 1. Casos de uso | `fig-01-casos-de-uso.png` | 3.1 | `scripts/diagrams.py` |
| 2. Arquitetura | `fig-02-arquitetura.png` | 3.2 | `scripts/diagrams.py` |
| 3. Sequência de uma pesquisa concorrente | `fig-12-sequencia.png` | 3.3 | `scripts/diagrams.py` |
| 4. Sequência de uma pesquisa sequencial | `fig-13-sequencia-sequencial.png` | 3.3 | `scripts/diagrams.py` |
| 5. Experimentos 1 e 2 | `fig-08-exp1-exp2.png` | 6.2 | `experiments/exp2_concurrent.py` ← `dados/exp1-sequencial.csv`, `dados/exp2-concorrente.csv` |
| 6. Experimento 3 | `fig-09-exp3-latencia.png` | 6.3 | `experiments/exp3_latency.py` ← `dados/exp3-latencia.csv` |
| 7. Experimento 4 | `fig-10-exp4-clientes.png` | 6.4 | `experiments/exp4_multiple_clients.py` ← `dados/exp4-multiplos-clientes.csv` |
| 8. Experimento 5 | `fig-11-exp5-falha.png` | 6.5 | `experiments/exp5_unavailability.py` ← `dados/exp5-indisponibilidade.csv`, `dados/exp5-gantt.csv` |

## Como refazer

- Experimentos obrigatórios (com o `start.py --quiet` rodando em outro terminal): `python3.12 -m experiments`. Para refazer só tabelas e gráficos a partir dos CSV: `--analyze`.
- Diagramas de casos de uso, arquitetura e sequência: `python3.12 scripts/diagrams.py`.
- DOCX e PDF no padrão ABNT: `python3.12 scripts/build_report.py` (precisa do LibreOffice). O caminho é Markdown → HTML com as figuras embutidas → LibreOffice, onde uma macro aplica A4 com margens 3/2 cm, numeração no topo a partir da Introdução e o sumário com páginas, e exporta DOCX e PDF. Leva poucos segundos. `--html` guarda também o HTML intermediário.

Todos os comandos rodam da raiz do projeto. A discussão de cada experimento está em [`../experimentos.md`](../experimentos.md).

## Pendências para a entrega

- Slides da apresentação (seção 11 do enunciado).
