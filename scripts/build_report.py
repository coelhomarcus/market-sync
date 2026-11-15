"""Gera relatorio.docx e relatorio.pdf no padrão ABNT a partir do relatorio.md, usando o LibreOffice.

Uso: python3.12 scripts/build_report.py [--html]   (capa em docs/relatorio/capa.json)"""

from __future__ import annotations

import argparse
import base64
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "docs" / "relatorio"
SOURCE = FOLDER / "relatorio.md"
COVER = FOLDER / "capa.json"

MAX_WIDTH_PX = 605  # 16 cm a 96 dpi: largura útil de uma página A4 com margens ABNT (3 cm + 2 cm)

# ABNT (NBR 14724): Times 12, espaçamento 1,5, recuo de 1,25 cm; legendas, tabelas e código menores e simples
CSS = """
body { font-family: 'Times New Roman', serif; font-size: 12pt; }
p { text-align: justify; line-height: 150%; margin: 0cm; }
li { text-align: justify; line-height: 150%; margin: 0cm; }
h1, h2 { font-family: 'Times New Roman', serif; font-size: 12pt; font-weight: bold; line-height: 150%;
         text-indent: 0cm; margin-left: 0cm; }
h1 { margin: 0cm 0cm 18pt 0cm; }
h2 { margin: 18pt 0cm 18pt 0cm; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0cm 12pt 0cm; }
th, td { border: 1px solid #000000; padding: 2pt 4pt; font-size: 10pt; line-height: 100%; vertical-align: top; text-align: left; }
th { font-weight: bold; }
code { font-family: 'Courier New', monospace; font-size: 10pt; }
pre { font-family: 'Courier New', monospace; font-size: 9pt; line-height: 100%; margin: 6pt 0cm 12pt 0cm; }
p.centro { text-align: center; text-indent: 0cm; }
p.legenda { text-align: center; text-indent: 0cm; font-size: 10pt; line-height: 100%; margin-top: 12pt; }
p.figura { text-align: center; text-indent: 0cm; line-height: 100%; }
p.fonte { text-align: center; text-indent: 0cm; font-size: 10pt; line-height: 100%; margin-bottom: 12pt; }
p.ref { text-align: left; text-indent: 0cm; line-height: 100%; margin-bottom: 12pt; }
p.natureza { text-align: justify; text-indent: 0cm; font-size: 10pt; line-height: 100%; margin-left: 8cm; }
"""

# Macro Basic que o LibreOffice roda: página A4 com margens ABNT, número da página no topo à direita
# a partir da Introdução (contando desde a folha de rosto), sumário com páginas e a exportação.
MACRO = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE script:module PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "module.dtd">
<script:module xmlns:script="http://openoffice.org/2000/script" script:name="Module1" script:language="StarBasic">
Sub Main
  On Error Goto Falhou
  Dim args(1) As New com.sun.star.beans.PropertyValue
  args(0).Name = "Hidden" : args(0).Value = True
  args(1).Name = "FilterName" : args(1).Value = "HTML (StarWriter)"
  doc = StarDesktop.loadComponentFromURL(ConvertToURL("{html}"), "_blank", 0, args())

  pages = doc.StyleFamilies.getByName("PageStyles")
  pre = doc.createInstance("com.sun.star.style.PageStyle")
  pages.insertByName("ABNT Pre", pre)
  Margens(pre, 3000)
  txt = doc.createInstance("com.sun.star.style.PageStyle")
  pages.insertByName("ABNT Texto", txt)
  Margens(txt, 2000)
  txt.HeaderIsOn = True
  txt.HeaderBodyDistance = 0
  txt.HeaderHeight = 1000
  hc = txt.HeaderText.createTextCursor()
  hc.ParaAdjust = com.sun.star.style.ParagraphAdjust.RIGHT
  hc.CharFontName = "Times New Roman"
  hc.CharHeight = 10
  pn = doc.createInstance("com.sun.star.text.TextField.PageNumber")
  pn.NumberingType = com.sun.star.style.NumberingType.ARABIC
  pn.SubType = com.sun.star.text.PageNumberType.CURRENT
  txt.HeaderText.insertTextContent(hc, pn, False)

  first = doc.Text.createEnumeration().nextElement()
  first.PageDescName = "ABNT Pre"
  r = Marca(doc, "[[ROSTO]]")
  r.PageDescName = "ABNT Pre"
  r.PageNumberOffset = 1
  r = Marca(doc, "[[TEXTO]]")
  r.PageDescName = "ABNT Texto"

  keep = 0
  en = doc.Text.createEnumeration()
  Do While en.hasMoreElements()
    el = en.nextElement()
    If el.supportsService("com.sun.star.text.Paragraph") Then
      If keep &gt; 0 Then
        el.ParaKeepTogether = True
        keep = keep - 1
      End If
      If Left(el.String, 7) = "Figura " And el.ParaAdjust = com.sun.star.style.ParagraphAdjust.CENTER Then
        el.ParaKeepTogether = True
        keep = 1
      End If
    End If
  Loop

  paras = doc.StyleFamilies.getByName("ParagraphStyles")
  Estilo(paras.getByName("Contents Heading"), True, com.sun.star.style.ParagraphAdjust.CENTER)
  Estilo(paras.getByName("Contents 1"), True, com.sun.star.style.ParagraphAdjust.LEFT)
  Estilo(paras.getByName("Contents 2"), False, com.sun.star.style.ParagraphAdjust.LEFT)
  r = Marca(doc, "[[SUMARIO]]")
  idx = doc.createInstance("com.sun.star.text.ContentIndex")
  idx.CreateFromOutline = True
  idx.Level = 2
  idx.Title = "SUMÁRIO"
  doc.Text.insertTextContent(r, idx, False)
  idx.update()

  Dim docx(0) As New com.sun.star.beans.PropertyValue
  docx(0).Name = "FilterName" : docx(0).Value = "MS Word 2007 XML"
  doc.storeToURL(ConvertToURL("{docx}"), docx())
  Dim pdf(0) As New com.sun.star.beans.PropertyValue
  pdf(0).Name = "FilterName" : pdf(0).Value = "writer_pdf_Export"
  doc.storeToURL(ConvertToURL("{pdf}"), pdf())
  doc.close(True)
  Exit Sub
Falhou:
  f = FreeFile
  Open "{error}" For Output As #f
  Print #f, "Erro " &amp; Err &amp; " na linha " &amp; Erl &amp; ": " &amp; Error$
  Close #f
  On Error Resume Next
  doc.close(True)
End Sub

Sub Margens(style, top)
  style.Width = 21000
  style.Height = 29700
  style.TopMargin = top
  style.LeftMargin = 3000
  style.RightMargin = 2000
  style.BottomMargin = 2000
End Sub

Function Marca(doc, token)
  sd = doc.createSearchDescriptor()
  sd.SearchString = token
  found = doc.findFirst(sd)
  found.String = ""
  Marca = found
End Function

Sub Estilo(s, bold, adjust)
  Dim spacing As New com.sun.star.style.LineSpacing
  spacing.Mode = 0 : spacing.Height = 150
  s.CharFontName = "Times New Roman"
  s.CharHeight = 12
  s.CharWeight = IIf(bold, com.sun.star.awt.FontWeight.BOLD, com.sun.star.awt.FontWeight.NORMAL)
  s.ParaAdjust = adjust
  s.ParaLineSpacing = spacing
  s.ParaLeftMargin = 0
End Sub
</script:module>
"""


def soffice() -> str:
    for candidate in (shutil.which("soffice"), "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        if candidate and Path(candidate).exists():
            return candidate
    sys.exit("LibreOffice não encontrado. Instale (brew install --cask libreoffice) ou ponha o soffice no PATH.")


def cover_data() -> dict:
    data = json.loads(COVER.read_text(encoding="utf-8")) if COVER.exists() else {}
    year = re.search(r"\d{4}", str(data.get("data", "")))
    data["ano"] = year.group(0) if year else str(data.get("data", ""))
    return data


# ---------------------------------------------------------------- elementos pré-textuais

def centered(text: str, top_cm: float = 0, bold: bool = False, extra: str = "") -> str:
    """Parágrafo centralizado; top_cm é a distância até o parágrafo de cima (posiciona os blocos da capa)."""
    text = f"<b>{text}</b>" if bold else text
    return (f'<p align="center" style="text-align: center; text-indent: 0cm; margin-top: {top_cm}cm; {extra}">'
            f"{text}</p>")


def pre_textual(data: dict, abstract: str, keywords: str) -> str:
    """Capa, folha de rosto, resumo e o lugar do sumário (NBR 14724)."""
    e = lambda key: html.escape(str(data.get(key, "")))  # noqa: E731
    names = [html.escape(n.upper()) for n in data.get("integrantes", [])]
    brk = "page-break-before: always;"

    def authors(top_cm: float, marker: str = "", extra: str = "") -> str:
        return "".join(centered((marker if i == 0 else "") + n, top_cm if i == 0 else 0, extra=extra if i == 0 else "")
                       for i, n in enumerate(names))

    def title(top_cm: float) -> str:
        sub = centered(e("subtitulo")) if data.get("subtitulo") else ""
        return centered(e("titulo").upper(), top_cm, bold=True) + sub

    nature = (f"Relatório técnico apresentado à disciplina {e('disciplina')} do curso de {e('curso')} "
              f"da {e('instituicao')}.")
    note = "text-align: justify; text-indent: 0cm; font-size: 10pt; line-height: 100%; margin-left: 8cm;"
    return f"""
{centered(e('instituicao').upper(), bold=True)}{centered(e('curso').upper(), bold=True)}
{authors(3)}{title(5)}
{centered(e('local'), 7)}{centered(e('ano'))}

{authors(0, "[[ROSTO]]", brk)}{title(5)}
<p style="{note} margin-top: 1.5cm">{nature}</p>
<p style="{note} margin-top: 0.5cm">Professor: {e('professor')}</p>
{centered(e('local'), 9)}{centered(e('ano'))}

{centered("RESUMO", bold=True, extra=brk)}
<p style="text-indent: 0cm; margin-top: 0.6cm">{abstract}</p>
<p style="text-indent: 0cm; margin-top: 0.6cm">{keywords}</p>

{centered("[[SUMARIO]]", extra=brk)}
"""


# ---------------------------------------------------------------- elementos textuais e pós-textuais

def embed_image(src: str, alt: str) -> str:
    """A figura embutida no HTML (data URI), na largura útil da página."""
    path = (FOLDER / src).resolve()
    if not path.exists():
        print(f"  aviso: figura não encontrada: {src}", file=sys.stderr)
        return f"<p class='figura'>[{html.escape(alt)}]</p>"
    with Image.open(path) as img:
        width, height = img.size
    scale = min(1.0, MAX_WIDTH_PX / width)
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return (f'<p class="figura" align="center"><img src="data:image/png;base64,{data}" alt="{html.escape(alt)}" '
            f'width="{round(width * scale)}" height="{round(height * scale)}"></p>')


def abnt_figures(body: str, year: str) -> str:
    """ABNT: título acima ("Figura 1 – ..."), a figura e a fonte abaixo."""
    def figure(m: re.Match) -> str:
        number, caption = m.group("num"), m.group("caption").rstrip(".")
        return (f"<p class='legenda' align='center'>Figura {number} – {caption}</p>"
                f"{embed_image(m.group('src'), m.group('alt'))}"
                f"<p class='fonte' align='center'>Fonte: Elaborada pelos autores ({year}).</p>")
    return re.sub(r'<p><img alt="(?P<alt>[^"]*)" src="(?P<src>[^"]+)"\s*/?></p>\s*'
                  r'<p><em>Figura (?P<num>\d+)\. (?P<caption>.*?)</em></p>', figure, body)


def code_blocks(body: str) -> str:
    """Cada linha de código vira um parágrafo em espaço simples (o <pre> importado sai com linhas em branco)."""
    style = ("font-family: 'Courier New', monospace; font-size: 8pt; line-height: 100%; text-align: left; "
             "text-indent: 0cm; margin: 0cm")

    def block(m: re.Match) -> str:
        lines = m.group(1).rstrip("\n").split("\n")
        paras = [f'<p style="{style}">{line.replace("  ", "&nbsp;&nbsp;") or "&nbsp;"}</p>' for line in lines]
        return f'<p style="{style}">&nbsp;</p>{"".join(paras)}<p style="{style}">&nbsp;</p>'
    return re.sub(r"<pre><code[^>]*>(.*?)</code></pre>", block, body, flags=re.S)


def abnt_headings(body: str) -> str:
    """Seções primárias em MAIÚSCULAS e página nova; secundárias em negrito; sem ponto depois do número."""
    def primary(m: re.Match) -> str:
        number, title = m.group(1), m.group(2)
        marker = "[[TEXTO]]" if number == "1" else ""  # a Introdução começa a parte numerada
        brk = "" if marker else ' style="page-break-before: always"'
        return f"<h1{brk}>{marker}{number} {title.upper()}</h1>"

    body = re.sub(r"<h2>(\d+)\. (.*?)</h2>", primary, body)
    body = re.sub(r"<h2>Apêndice ([A-Z])\. (.*?)</h2>",
                  lambda m: f'<h1 align="center" style="page-break-before: always; text-align: center">'
                            f"APÊNDICE {m.group(1)} – {m.group(2).upper()}</h1>", body)
    body = body.replace("<h2>Referências</h2>",
                        '<h1 align="center" style="page-break-before: always; text-align: center">REFERÊNCIAS</h1>')
    return re.sub(r"<h3>(.*?)</h3>", r"<h2>\1</h2>", body)


def abnt_references(body: str) -> str:
    """Referências (NBR 6023): em ordem alfabética, alinhadas à esquerda, espaço simples e uma linha entre elas."""
    m = re.search(r"(REFERÊNCIAS</h1>\s*)<ul>(.*?)</ul>", body, re.S)
    if not m:
        return body
    items = sorted(re.findall(r"<li>(.*?)</li>", m.group(2), re.S), key=lambda s: re.sub(r"<[^>]+>", "", s))
    refs = "".join(f"<p class='ref'>{item}</p>" for item in items)
    return body[:m.start()] + m.group(1) + refs + body[m.end():]


def split_markdown(text: str) -> tuple[str, str, str]:
    """(resumo, palavras-chave, corpo) do relatorio.md; as Referências vão para antes dos Apêndices (NBR 14724)."""
    abstract_md = text[text.index("## Resumo") + len("## Resumo"):text.index("## 1. ")]
    lines = [ln.strip() for ln in abstract_md.strip().splitlines() if ln.strip()]
    keywords = next((ln for ln in lines if ln.startswith("**Palavras-chave")), "")
    abstract = " ".join(ln for ln in lines if ln != keywords)

    body = text[text.index("## 1. "):]
    refs_at = body.find("## Referências")
    appendix_at = body.find("## Apêndice")
    if 0 <= appendix_at < refs_at:
        body = body[:appendix_at] + body[refs_at:].rstrip() + "\n\n" + body[appendix_at:refs_at]
    return abstract, keywords, body


def inline(md: str) -> str:
    return re.sub(r"^<p>(.*)</p>$", r"\1", markdown.markdown(md).strip(), flags=re.S)


def build_html() -> str:
    data = cover_data()
    abstract, keywords, body_md = split_markdown(SOURCE.read_text(encoding="utf-8"))
    body = markdown.markdown(body_md, extensions=["tables", "fenced_code", "sane_lists"], output_format="html")
    body = abnt_figures(body, data["ano"])
    body = body.replace("<p>", '<p style="text-indent: 1.25cm">')  # recuo de parágrafo só no texto corrido
    body = abnt_references(abnt_headings(code_blocks(body)))
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>Relatório técnico</title>
<style>{CSS}</style></head>
<body>{pre_textual(data, inline(abstract), inline(keywords))}{body}</body></html>"""


# ---------------------------------------------------------------- LibreOffice

def run_macro(soffice_bin: str, tmp: Path, html_file: Path) -> tuple[Path, Path]:
    """Cria um perfil próprio do LibreOffice, instala a macro e a executa sem abrir janela."""
    profile = tmp / "perfil-libreoffice"  # perfil próprio: funciona mesmo com o LibreOffice aberto
    base = [soffice_bin, f"-env:UserInstallation={profile.as_uri()}", "--headless", "--norestore"]
    subprocess.run(base + ["--terminate_after_init"], capture_output=True, timeout=180)
    module = profile / "user" / "basic" / "Standard" / "Module1.xba"
    if not module.exists():
        sys.exit("Falha ao criar o perfil do LibreOffice.")

    docx, pdf, error = tmp / "relatorio.docx", tmp / "relatorio.pdf", tmp / "erro-macro.txt"
    module.write_text(MACRO.format(html=html_file, docx=docx, pdf=pdf, error=error), encoding="utf-8")
    r = subprocess.run(base + ["macro:///Standard.Module1.Main"], capture_output=True, text=True, timeout=300)
    if error.exists():
        sys.exit(f"Falha na macro do LibreOffice: {error.read_text()}")
    if r.returncode != 0 or not pdf.exists():
        sys.exit(f"Falha no LibreOffice:\n{r.stdout}\n{r.stderr}")
    return docx, pdf


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera relatorio.docx e relatorio.pdf (ABNT) com o LibreOffice")
    parser.add_argument("--html", action="store_true", help="guarda também o relatorio.html intermediário")
    args = parser.parse_args()

    bin_ = soffice()
    with tempfile.TemporaryDirectory(prefix="relatorio-") as tmp:
        tmp = Path(tmp)
        html_file = tmp / "relatorio.html"
        html_file.write_text(build_html(), encoding="utf-8")
        print("Gerando DOCX e PDF no LibreOffice...")
        docx, pdf = run_macro(bin_, tmp, html_file)
        for out in (docx, pdf) + ((html_file,) if args.html else ()):
            shutil.copy(out, FOLDER / out.name)
            print(f"  → {(FOLDER / out.name).relative_to(ROOT)} ({(FOLDER / out.name).stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
