"""Baixa fotos reais dos produtos do catálogo a partir das bases abertas
Open Food Facts / Open Beauty Facts / Open Products Facts (licença CC-BY-SA).

Salva em frontend/public/products/<tipo>.jpg (uma foto por tipo de produto) e gera frontend/public/products/CREDITS.md.
Uso (da raiz):  backend/.venv/bin/python scripts/fetch_images.py [--force] [slug ...]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from mercados.catalogo import TYPES, ProductType  # noqa: E402

OUT = ROOT / "frontend" / "public" / "products"
CREDITS = OUT / "CREDITS.md"
USER_AGENT = "ComparadorDePrecos/1.0 (trabalho academico; script de imagens)"
HOSTS = {
    "food": "https://world.openfoodfacts.org",
    "beauty": "https://world.openbeautyfacts.org",
    "products": "https://world.openproductsfacts.org",
    "petfood": "https://world.openpetfoodfacts.org",
}


def get(url: str, timeout: float = 25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def search(product: ProductType, brazil: bool = True) -> list[dict]:
    params = {
        "search_terms": product.image_query or product.name,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": 40,
        "fields": "code,product_name,brands,image_front_url,image_url,countries_tags",
    }
    if brazil:
        params |= {"tagtype_0": "countries", "tag_contains_0": "contains", "tag_0": "brazil"}
    url = f"{HOSTS[product.image_source]}/cgi/search.pl?{urllib.parse.urlencode(params)}"
    for attempt in range(3):
        try:
            return json.loads(get(url)).get("products", [])
        except Exception as exc:  # rede instável / rate limit
            print(f"    tentativa {attempt + 1} falhou: {exc}")
            time.sleep(3 * (attempt + 1))
    return []


def pick(product: ProductType, candidates: list[dict]) -> dict | None:
    words = [w for w in product.image_query.split() if len(w) > 2 and not any(c.isdigit() for c in w)]
    def score(c: dict) -> int:
        name = (c.get("product_name") or "").lower()
        return sum(w in name for w in words)
    with_image = [c for c in candidates if c.get("image_front_url") or c.get("image_url")]
    with_image.sort(key=score, reverse=True)
    return with_image[0] if with_image else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="baixa de novo mesmo se já existir")
    parser.add_argument("slugs", nargs="*", help="slugs a baixar; use slug=termo para trocar o termo de busca")
    args = parser.parse_args()
    overrides = dict(a.split("=", 1) for a in args.slugs if "=" in a)
    args.slugs = [a.split("=", 1)[0] for a in args.slugs]

    OUT.mkdir(parents=True, exist_ok=True)
    credits = json.loads((OUT / "credits.json").read_text()) if (OUT / "credits.json").exists() else {}
    for product in TYPES:  # uma foto por tipo de produto, compartilhada por marcas e tamanhos
        if args.slugs and product.image_key not in args.slugs:
            continue
        target = OUT / f"{product.image_key}.jpg"
        if target.exists() and not args.force:
            continue
        print(f"- {product.name}")
        if product.image_key in overrides:
            product = replace(product, image_query=overrides[product.image_key])
        choice = pick(product, search(product)) or pick(product, search(product, brazil=False))
        if not choice:
            print("    nenhuma imagem encontrada")
            continue
        url = choice.get("image_front_url") or choice["image_url"]
        try:
            target.write_bytes(get(url))
        except Exception as exc:
            print(f"    falha ao baixar: {exc}")
            continue
        credits[product.image_key] = {
            "product": choice.get("product_name"),
            "brands": choice.get("brands"),
            "code": choice.get("code"),
            "image": url,
            "page": f"{HOSTS[product.image_source]}/product/{choice.get('code')}",
        }
        print(f"    ok: {choice.get('product_name')} ({choice.get('brands')})")
        time.sleep(1)  # educação com a API pública

    (OUT / "credits.json").write_text(json.dumps(credits, ensure_ascii=False, indent=2))
    lines = [
        "# Créditos das imagens",
        "",
        "Fotos obtidas das bases abertas Open Food Facts, Open Beauty Facts e Open Products Facts,",
        "licenciadas sob [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/deed.pt_BR).",
        "As marcas aparecem apenas nas fotos ilustrativas; os mercados e preços do sistema são fictícios.",
        "",
        "| Arquivo | Produto na base | Fonte |",
        "|---|---|---|",
    ]
    for slug, c in sorted(credits.items()):
        lines.append(f"| `{slug}.jpg` | {c['product'] or '-'} ({c['brands'] or '-'}) | [{c['code']}]({c['page']}) |")
    CREDITS.write_text("\n".join(lines) + "\n")
    missing = [t.image_key for t in TYPES if not (OUT / f"{t.image_key}.jpg").exists()]
    print(f"\n{len(TYPES) - len(missing)}/{len(TYPES)} imagens. Faltando: {missing or 'nenhuma'}")


if __name__ == "__main__":
    main()
