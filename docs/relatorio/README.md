# Relatório técnico

Versão de 13/11/2026 do relatório do trabalho, exportada do documento original no Claude Docs.

| Arquivo | Para que serve |
|---|---|
| `relatorio.docx` | Versão editável para Word ou Google Docs, com as 7 figuras embutidas. É a melhor base para preencher capa, nomes do grupo e formatação da disciplina. |
| `relatorio.pdf` | Versão pronta para entregar ou imprimir (A4). |
| `relatorio.md` | O mesmo texto em Markdown, apontando para as figuras em `figuras/`. Bom para revisar no GitHub ou editar como texto. |
| `figuras/` | As 7 figuras em PNG (casos de uso, arquitetura e os 5 gráficos dos experimentos). |
| `dados/` | Os números de cada gráfico em CSV, para refazer ou ajustar os gráficos em qualquer ferramenta (Excel, Google Sheets, Python). |

## Correspondência entre figuras e dados

| Figura | Seção | Dados |
|---|---|---|
| `fig-01-casos-de-uso.png` | 3. Casos de uso | (diagrama) |
| `fig-02-arquitetura.png` | 4. Arquitetura | (diagrama) |
| `fig-03-gantt-consulta.png` | 8.2 Uma consulta em detalhe | `dados/01-gantt-consulta.csv` |
| `fig-04-cenarios.png` | 8.3 Cenários de latência e falha | `dados/02-cenarios.csv` |
| `fig-05-por-mercados.png` | 8.4 Efeito do número de mercados | `dados/03-por-mercados.csv` |
| `fig-06-por-threads.png` | 8.5 Efeito do número de threads | `dados/04-por-threads.csv` |
| (tabela) | 8.6 Volume de dados | `dados/05-volume-dados.csv` |
| `fig-07-recursos.png` | 8.7 Consumo de recursos | `dados/06-recursos.csv` |

## Como refazer as medições

Os números vêm do benchmark do próprio sistema (`POST /api/benchmark`) e do CSV exportado pelo painel (`/api/metrics/export.csv`, que inclui tempo, bytes, CPU e threads por requisição). O roteiro de cada experimento está em [`../experimentos.md`](../experimentos.md). Ao atualizar os números, atualize também o CSV correspondente em `dados/`, para o texto e os gráficos continuarem batendo.

## Pendências para a entrega

- Capa com nome da disciplina, professor e integrantes do grupo.
- Edições dos livros nas referências (conforme a bibliografia da disciplina).
