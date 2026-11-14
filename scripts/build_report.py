"""Gera relatorio.docx e relatorio.pdf a partir do relatorio.md, usando o LibreOffice.

Caminho: Markdown → HTML (figuras embutidas, capa) → LibreOffice → DOCX → PDF.
O LibreOffice não lê Markdown, mas importa HTML no Writer; o PDF é exportado do
próprio DOCX, então os dois ficam iguais.

Uso (da raiz do projeto):
    .venv/bin/python scripts/build_report.py
    .venv/bin/python scripts/build_report.py --html   # também guarda o HTML intermediário

Capa: edite docs/relatorio/capa.json (disciplina, professor, integrantes...).
Precisa do LibreOffice instalado (soffice no PATH ou em /Applications/LibreOffice.app)
e do pacote `markdown` (está no requirements.txt).
"""

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

MAX_WIDTH_PX = 605  # ~16 cm a 96 dpi: largura útil de uma página A4 com margens de 2,5 cm

CSS = """
body { font-family: 'Liberation Sans', Arial, sans-serif; font-size: 11pt; line-height: 1.35; }
h1 { font-size: 20pt; }
h2 { font-size: 15pt; margin-top: 18pt; }
h3 { font-size: 12.5pt; margin-top: 12pt; }
p { text-align: justify; margin: 0 0 6pt 0; }
li { margin-bottom: 3pt; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt 0; }
th, td { border: 1px solid #999999; padding: 3pt 5pt; font-size: 9pt; vertical-align: top; text-align: left; }
th { background: #e8e8e8; font-weight: bold; }
code { font-family: 'Liberation Mono', Menlo, monospace; font-size: 9pt; }
pre { font-family: 'Liberation Mono', Menlo, monospace; font-size: 8pt; background: #f4f4f4;
      border: 1px solid #dddddd; padding: 6pt; }
p.figura { text-align: center; margin-top: 10pt; margin-bottom: 2pt; }
p.legenda { text-align: center; font-size: 9.5pt; color: #444444; margin-bottom: 12pt; }
.capa { text-align: center; }
"""


def soffice() -> str:
    for candidate in (shutil.which("soffice"), "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        if candidate and Path(candidate).exists():
            return candidate
    sys.exit("LibreOffice não encontrado. Instale (brew install --cask libreoffice) ou ponha o soffice no PATH.")


def embed_image(match: re.Match) -> str:
    """Troca <img src="figuras/x.png"> por uma imagem embutida (data URI), com largura de página."""
    alt, src = match.group("alt"), match.group("src")
    path = (FOLDER / src).resolve()
    if not path.exists():
        print(f"  aviso: figura não encontrada: {src}", file=sys.stderr)
        return match.group(0)
    with Image.open(path) as img:
        width, height = img.size
    scale = min(1.0, MAX_WIDTH_PX / width)
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return (f'<p class="figura" align="center"><img src="data:image/png;base64,{data}" alt="{alt}" '
            f'width="{round(width * scale)}" height="{round(height * scale)}"></p>')


def cover() -> str:
    data = json.loads(COVER.read_text(encoding="utf-8")) if COVER.exists() else {}
    e = lambda key, default="": html.escape(str(data.get(key, default)))  # noqa: E731
    members = "".join(f"<p class='capa'>{html.escape(n)}</p>" for n in data.get("integrantes", []))
    return f"""
<p class="capa"><b>{e('instituicao')}</b></p>
<p class="capa">{e('curso')}</p>
<p class="capa">{e('disciplina')}</p>
<p class="capa">&nbsp;</p><p class="capa">&nbsp;</p><p class="capa">&nbsp;</p>
<h1 class="capa" align="center">{e('titulo', 'Comparador de Preços de Supermercados')}</h1>
<p class="capa">{e('subtitulo')}</p>
<p class="capa">&nbsp;</p><p class="capa">&nbsp;</p>
<p class="capa"><b>Integrantes</b></p>
{members}
<p class="capa">&nbsp;</p>
<p class="capa">Professor(a): {e('professor')}</p>
<p class="capa">&nbsp;</p><p class="capa">&nbsp;</p><p class="capa">&nbsp;</p>
<p class="capa">{e('local')}</p>
<p class="capa">{e('data')}</p>
<p style="page-break-before: always"></p>
"""


def build_html() -> str:
    text = SOURCE.read_text(encoding="utf-8")
    # a capa substitui o título e a data do topo do Markdown: o corpo começa no Resumo
    start = text.find("## Resumo")
    body_md = text[start:] if start >= 0 else text
    body = markdown.markdown(body_md, extensions=["tables", "fenced_code", "sane_lists"], output_format="html")

    body = re.sub(r'<p><img alt="(?P<alt>[^"]*)" src="(?P<src>[^"]+)"\s*/?></p>', embed_image, body)
    body = re.sub(r"<p><em>(Figura \d+\..*?)</em></p>", r'<p class="legenda"><i>\1</i></p>', body)
    # cada seção numerada (## 1. ... ## 8.) e os apêndices começam em página nova
    body = re.sub(r"<h2>(\d+\. |Apêndice|Referências)", r'<h2 style="page-break-before: always">\1', body)
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>Relatório técnico</title>
<style>{CSS}</style></head>
<body>{cover()}{body}</body></html>"""


def convert(soffice_bin: str, src_path: Path, out_filter: str, log_out: Path, profile_dir: Path, infilter: str | None = None) -> Path:
    cmd = [soffice_bin, f"-env:UserInstallation={profile_dir.as_uri()}", "--headless", "--norestore"]
    if infilter:
        cmd.append(f"--infilter={infilter}")
    cmd += ["--convert-to", out_filter, "--outdir", str(log_out), str(src_path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    dest_path = log_out / (src_path.stem + "." + out_filter.split(":")[0])
    if r.returncode != 0 or not dest_path.exists():
        sys.exit(f"Falha no LibreOffice ({' '.join(cmd)}):\n{r.stdout}\n{r.stderr}")
    return dest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera relatorio.docx e relatorio.pdf com o LibreOffice")
    parser.add_argument("--html", action="store_true", help="guarda também o relatorio.html intermediário")
    args = parser.parse_args()

    bin_ = soffice()
    with tempfile.TemporaryDirectory(prefix="relatorio-") as tmp:
        tmp = Path(tmp)
        profile_dir = tmp / "perfil-libreoffice"  # perfil próprio: funciona mesmo com o LibreOffice aberto
        html_file = tmp / "relatorio.html"
        html_file.write_text(build_html(), encoding="utf-8")
        print("Convertendo HTML → DOCX...")
        docx = convert(bin_, html_file, "docx:MS Word 2007 XML", tmp, profile_dir, infilter="HTML (StarWriter)")
        print("Convertendo DOCX → PDF...")
        pdf = convert(bin_, docx, "pdf:writer_pdf_Export", tmp, profile_dir)
        for log_file in (docx, pdf) + ((html_file,) if args.html else ()):
            shutil.copy(log_file, FOLDER / log_file.name)
            print(f"  → {(FOLDER / log_file.name).relative_to(ROOT)} ({(FOLDER / log_file.name).stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
