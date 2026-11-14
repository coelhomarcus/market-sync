"""Catálogo de produtos comum a todos os mercados.

O catálogo é gerado combinando:
    tipo de produto (≈100)  ×  marca (10 por categoria)  ×  sabor/variante  ×  tamanho
o que dá alguns milhares de SKUs, como num supermercado de verdade. As marcas são
fictícias. (Os campos `image` e `image_query` vêm da versão com loja web, que mostrava
uma foto por tipo; hoje não são usados.)

Cada supermercado vende parte desse catálogo com preço e estoque próprios (ver seed_databases.py).
"""

from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class ProductType:
    key: str
    name: str
    category: str
    sizes: tuple[tuple[str, float], ...]  # (unidade, preço base)
    brands: str  # chave do grupo de marcas
    variants: tuple[str, ...] = ("",)
    keywords: str = ""
    image_query: str = ""
    image_source: str = "food"  # food | beauty | products | petfood
    image: str = ""  # nome do arquivo da foto (sem .jpg); vazio = key

    @property
    def image_key(self) -> str:
        return self.image or self.key


@dataclass(frozen=True)
class Product:
    slug: str
    name: str
    brand: str
    category: str
    unit: str
    base_price: float
    image: str
    keywords: str = ""
    order: int = 0


BRANDS: dict[str, tuple[str, ...]] = {
    "mercearia": ("Grão Nobre", "Bom Campo", "Sabor da Terra", "Vale Verde", "Dona Clara",
                  "Serra Azul", "Colheita Fina", "Mesa Farta", "Celeiro Real", "Prato Cheio"),
    "doces": ("Doce Lar", "Cacau Fino", "Vovó Lina", "Delícia Mineira", "Bem Doce",
              "Bem Bolado", "Confeitaria Sol", "Doçura", "Mimo", "Festa Boa"),
    "laticinios": ("Leiteria Serrana", "Vaca Mansa", "Campo Branco", "Pasto Alto", "Primavera",
                   "Fazenda Boa Vista", "Leite Puro", "Montanha Verde", "Nata Fina", "Ordenha"),
    "frios": ("Defumados Serra", "Sabor Nobre", "Frigorífico Pampa", "Mesa Posta", "Fatiado Fino",
              "Bom Corte", "Tradição Gaúcha", "Casa do Frio", "Rancho Alegre", "Delícias do Sul"),
    "congelados": ("Gelado Bom", "Forno Rápido", "Prático", "Chef em Casa", "Neve Fina",
                   "Sabor Congelado", "Frio Fino", "Rapidinho", "Mesa Pronta", "Geada"),
    "bebidas": ("Fonte Clara", "Tropical Sul", "Pomar Real", "Gelado Norte", "Vida Leve",
                "Serra Fresca", "Nascente Azul", "Frutos do Vale", "Refresco Bom", "Água Viva"),
    "padaria": ("Forno Dourado", "Trigo Bom", "Pão da Vila", "Granja Feliz", "Massa Leve",
                "Padaria Central", "Fornalha", "Miolo", "Casca Fina", "Sítio Alegre"),
    "limpeza": ("Brilho Max", "Lar Limpo", "Casa Nova", "Espuma Fina", "Limpinho",
                "Cheirinho", "Faxina", "Pura Casa", "Ultra Lar", "Clarear"),
    "higiene": ("Pura Pele", "Sorriso Branco", "Bem Cuidar", "Frescor", "Natural Bio",
                "Macia", "Toque", "Essência", "Leveza", "Brisa"),
    "pet": ("Amigo Fiel", "Patinha", "Bicho Feliz", "Focinho", "Mascote",
            "Pet Vida", "Ronrom", "Au-Au", "Vira-lata Chic", "Petisco"),
}

# perfil de preço das marcas: da mais barata (0,82) à premium (1,25)
BRAND_FACTORS = (0.82, 0.88, 0.93, 0.97, 1.00, 1.03, 1.08, 1.12, 1.18, 1.25)

T = ProductType
TYPES: list[ProductType] = [
    # ---------------------------------------------------------------- Mercearia
    T("arroz-branco", "Arroz Branco Tipo 1", "Mercearia", (("1 kg", 6.29), ("5 kg", 27.90)), "mercearia",
      keywords="arroz agulhinha", image_query="arroz branco tipo 1 5kg", image="arroz-branco-5kg"),
    T("arroz-integral", "Arroz Integral", "Mercearia", (("1 kg", 8.49),), "mercearia",
      keywords="arroz", image_query="arroz integral 1kg", image="arroz-integral-1kg"),
    T("arroz-parboilizado", "Arroz Parboilizado", "Mercearia", (("1 kg", 6.79), ("5 kg", 29.90)), "mercearia",
      keywords="arroz", image_query="arroz parboilizado"),
    T("feijao-carioca", "Feijão Carioca", "Mercearia", (("1 kg", 8.99), ("2 kg", 17.40)), "mercearia",
      keywords="feijao", image_query="feijao carioca 1kg", image="feijao-carioca-1kg"),
    T("feijao-preto", "Feijão Preto", "Mercearia", (("1 kg", 9.49),), "mercearia",
      keywords="feijao", image_query="feijao preto 1kg", image="feijao-preto-1kg"),
    T("lentilha", "Lentilha", "Mercearia", (("500 g", 9.90),), "mercearia", keywords="graos", image_query="lentilha"),
    T("acucar-refinado", "Açúcar Refinado", "Mercearia", (("1 kg", 4.99), ("5 kg", 22.90)), "mercearia",
      keywords="acucar", image_query="acucar refinado 1kg", image="acucar-refinado-1kg"),
    T("acucar-cristal", "Açúcar Cristal", "Mercearia", (("1 kg", 4.59), ("5 kg", 20.90)), "mercearia",
      keywords="acucar", image_query="acucar cristal"),
    T("cafe-torrado", "Café Torrado e Moído", "Mercearia", (("250 g", 10.90), ("500 g", 18.90)), "mercearia",
      variants=("Tradicional", "Extraforte"), keywords="cafe po", image_query="cafe torrado e moido", image="cafe-torrado-500g"),
    T("cafe-soluvel", "Café Solúvel", "Mercearia", (("100 g", 13.90), ("200 g", 24.90)), "mercearia",
      keywords="cafe", image_query="cafe soluvel"),
    T("macarrao-espaguete", "Macarrão Espaguete", "Mercearia", (("500 g", 4.79), ("1 kg", 8.90)), "mercearia",
      keywords="massa macarrao", image_query="macarrao espaguete", image="macarrao-espaguete-500g"),
    T("macarrao-parafuso", "Macarrão Parafuso", "Mercearia", (("500 g", 4.99),), "mercearia",
      keywords="massa macarrao", image_query="macarrao parafuso"),
    T("macarrao-instantaneo", "Macarrão Instantâneo", "Mercearia", (("85 g", 1.79),), "mercearia",
      variants=("Galinha", "Carne", "Legumes"), keywords="massa miojo lamen", image_query="macarrao instantaneo"),
    T("oleo-soja", "Óleo de Soja", "Mercearia", (("900 ml", 7.49),), "mercearia",
      keywords="oleo", image_query="oleo de soja", image="oleo-soja-900ml"),
    T("azeite", "Azeite de Oliva Extravirgem", "Mercearia", (("250 ml", 19.90), ("500 ml", 34.90)), "mercearia",
      keywords="oleo azeite", image_query="azeite de oliva extra virgem"),
    T("farinha-trigo", "Farinha de Trigo", "Mercearia", (("1 kg", 5.49), ("5 kg", 23.90)), "mercearia",
      keywords="farinha", image_query="farinha de trigo 1kg", image="farinha-trigo-1kg"),
    T("farinha-mandioca", "Farinha de Mandioca", "Mercearia", (("500 g", 6.29), ("1 kg", 11.50)), "mercearia",
      keywords="farinha farofa", image_query="farinha de mandioca", image="farinha-mandioca-500g"),
    T("fuba", "Fubá Mimoso", "Mercearia", (("1 kg", 4.29),), "mercearia", keywords="milho farinha", image_query="fuba mimoso"),
    T("sal-refinado", "Sal Refinado", "Mercearia", (("1 kg", 2.79),), "mercearia",
      keywords="sal tempero", image_query="sal refinado", image="sal-refinado-1kg"),
    T("molho-tomate", "Molho de Tomate", "Mercearia", (("340 g", 3.29),), "mercearia",
      variants=("Tradicional", "Manjericão"), keywords="molho tomate", image_query="molho de tomate tradicional", image="molho-tomate-340g"),
    T("extrato-tomate", "Extrato de Tomate", "Mercearia", (("140 g", 3.49), ("340 g", 6.49)), "mercearia",
      keywords="tomate molho", image_query="extrato de tomate"),
    T("milho-verde", "Milho Verde em Conserva", "Mercearia", (("170 g", 4.49),), "mercearia",
      keywords="milho enlatado lata", image_query="milho verde em conserva", image="milho-verde-lata"),
    T("ervilha", "Ervilha em Conserva", "Mercearia", (("170 g", 3.99),), "mercearia",
      keywords="ervilha enlatado lata", image_query="ervilha em conserva"),
    T("atum", "Atum", "Mercearia", (("170 g", 9.99),), "mercearia",
      variants=("Sólido em Óleo", "Ralado"), keywords="atum peixe enlatado lata", image_query="atum solido", image="atum-solido-lata"),
    T("sardinha", "Sardinha em Óleo", "Mercearia", (("125 g", 5.49),), "mercearia",
      keywords="sardinha peixe enlatado lata", image_query="sardinha em oleo"),
    T("maionese", "Maionese", "Mercearia", (("250 g", 5.29), ("500 g", 9.49)), "mercearia",
      keywords="maionese molho", image_query="maionese tradicional", image="maionese-500g"),
    T("ketchup", "Ketchup", "Mercearia", (("400 g", 8.90),), "mercearia", keywords="molho", image_query="ketchup"),
    T("mostarda", "Mostarda", "Mercearia", (("200 g", 4.90),), "mercearia", keywords="molho", image_query="mostarda"),
    T("vinagre", "Vinagre de Álcool", "Mercearia", (("750 ml", 2.99),), "mercearia", keywords="tempero", image_query="vinagre de alcool"),
    T("achocolatado", "Achocolatado em Pó", "Mercearia", (("400 g", 8.99), ("800 g", 16.90)), "mercearia",
      keywords="chocolate po", image_query="achocolatado em po", image="achocolatado-400g"),
    T("leite-po", "Leite em Pó Integral", "Mercearia", (("400 g", 17.90),), "laticinios",
      keywords="leite po", image_query="leite em po integral"),
    T("gelatina", "Gelatina em Pó", "Mercearia", (("20 g", 1.99),), "doces",
      variants=("Morango", "Uva", "Limão"), keywords="sobremesa", image_query="gelatina em po"),
    # ---------------------------------------------------------------- Matinais
    T("aveia", "Aveia em Flocos", "Matinais", (("200 g", 5.29), ("500 g", 11.90)), "mercearia",
      keywords="aveia cereal", image_query="aveia em flocos", image="aveia-flocos-200g"),
    T("granola", "Granola", "Matinais", (("800 g", 19.90),), "mercearia", keywords="cereal", image_query="granola"),
    T("cereal-milho", "Cereal Matinal de Milho", "Matinais", (("300 g", 11.90),), "mercearia",
      keywords="cereal flocos", image_query="corn flakes cereal"),
    # ---------------------------------------------------------------- Biscoitos e Doces
    T("biscoito-cream-cracker", "Biscoito Cream Cracker", "Biscoitos e Doces", (("400 g", 5.99),), "doces",
      keywords="bolacha biscoito", image_query="biscoito cream cracker", image="biscoito-cream-cracker"),
    T("biscoito-recheado", "Biscoito Recheado", "Biscoitos e Doces", (("130 g", 2.99),), "doces",
      variants=("Chocolate", "Morango", "Baunilha"), keywords="bolacha biscoito", image_query="biscoito recheado"),
    T("biscoito-maisena", "Biscoito Maisena", "Biscoitos e Doces", (("400 g", 5.49),), "doces",
      keywords="bolacha biscoito", image_query="biscoito maizena"),
    T("chocolate", "Chocolate", "Biscoitos e Doces", (("90 g", 6.99),), "doces",
      variants=("ao Leite", "Meio Amargo", "Branco"), keywords="chocolate barra doce", image_query="chocolate ao leite"),
    T("wafer", "Wafer", "Biscoitos e Doces", (("115 g", 3.49),), "doces",
      variants=("Chocolate", "Morango"), keywords="biscoito bolacha", image_query="wafer"),
    T("doce-leite", "Doce de Leite", "Biscoitos e Doces", (("400 g", 9.90),), "doces", keywords="doce", image_query="doce de leite"),
    # ---------------------------------------------------------------- Laticínios
    T("leite-integral", "Leite Integral UHT", "Laticínios", (("1 L", 5.49),), "laticinios",
      keywords="leite caixinha", image_query="leite integral uht 1l", image="leite-integral-1l"),
    T("leite-desnatado", "Leite Desnatado UHT", "Laticínios", (("1 L", 5.29),), "laticinios",
      keywords="leite caixinha", image_query="leite desnatado"),
    T("leite-condensado", "Leite Condensado", "Laticínios", (("395 g", 6.99),), "laticinios",
      keywords="leite condensado doce", image_query="leite condensado", image="leite-condensado"),
    T("creme-de-leite", "Creme de Leite", "Laticínios", (("200 g", 3.99),), "laticinios",
      keywords="creme leite", image_query="creme de leite", image="creme-de-leite"),
    T("manteiga", "Manteiga com Sal", "Laticínios", (("200 g", 12.90), ("500 g", 27.90)), "laticinios",
      keywords="manteiga", image_query="manteiga com sal", image="manteiga-200g"),
    T("margarina", "Margarina com Sal", "Laticínios", (("500 g", 8.90),), "laticinios", keywords="margarina", image_query="margarina"),
    T("requeijao", "Requeijão Cremoso", "Laticínios", (("200 g", 8.79),), "laticinios",
      keywords="requeijao", image_query="requeijao cremoso", image="requeijao-200g"),
    T("iogurte", "Iogurte", "Laticínios", (("170 g", 3.49),), "laticinios",
      variants=("Natural", "Morango", "Coco"), keywords="iogurte", image_query="iogurte natural integral", image="iogurte-natural"),
    T("bebida-lactea", "Bebida Láctea", "Laticínios", (("900 g", 8.49),), "laticinios",
      variants=("Morango", "Coco"), keywords="iogurte", image_query="bebida lactea"),
    T("queijo-parmesao", "Queijo Parmesão Ralado", "Laticínios", (("50 g", 6.90),), "laticinios",
      keywords="queijo", image_query="queijo parmesao ralado"),
    # ---------------------------------------------------------------- Frios
    T("queijo-mussarela", "Queijo Mussarela Fatiado", "Frios", (("150 g", 9.90),), "frios",
      keywords="queijo", image_query="queijo mussarela fatiado"),
    T("presunto", "Presunto Cozido Fatiado", "Frios", (("200 g", 8.90),), "frios", keywords="frios", image_query="presunto fatiado"),
    T("salsicha", "Salsicha Hot Dog", "Frios", (("500 g", 9.90),), "frios", keywords="salsicha", image_query="salsicha"),
    T("mortadela", "Mortadela Fatiada", "Frios", (("200 g", 5.90),), "frios", keywords="frios", image_query="mortadela"),
    T("peito-peru", "Peito de Peru Defumado", "Frios", (("200 g", 14.90),), "frios", keywords="frios peru", image_query="peito de peru"),
    # ---------------------------------------------------------------- Congelados
    T("pizza", "Pizza Congelada", "Congelados", (("460 g", 17.90),), "congelados",
      variants=("Mussarela", "Calabresa", "Frango com Requeijão"), keywords="pizza", image_query="pizza congelada"),
    T("lasanha", "Lasanha Congelada", "Congelados", (("600 g", 16.90),), "congelados",
      variants=("Bolonhesa", "Quatro Queijos"), keywords="lasanha massa", image_query="lasanha congelada"),
    T("batata-frita", "Batata Pré-Frita Congelada", "Congelados", (("1 kg", 19.90),), "congelados",
      keywords="batata", image_query="batata pre frita congelada"),
    T("hamburguer", "Hambúrguer Bovino", "Congelados", (("672 g", 21.90),), "congelados",
      keywords="hamburguer carne", image_query="hamburguer bovino"),
    T("empanado-frango", "Empanado de Frango", "Congelados", (("300 g", 12.90),), "congelados",
      keywords="nuggets frango", image_query="empanado de frango nuggets"),
    T("pao-queijo", "Pão de Queijo Congelado", "Congelados", (("1 kg", 19.90),), "congelados",
      keywords="pao queijo", image_query="pao de queijo"),
    # ---------------------------------------------------------------- Bebidas
    T("suco-integral", "Suco Integral", "Bebidas", (("1 L", 10.90),), "bebidas",
      variants=("Laranja", "Uva", "Maçã"), keywords="suco", image_query="suco de laranja integral", image="suco-laranja-1l"),
    T("nectar", "Néctar de Fruta", "Bebidas", (("1 L", 6.49),), "bebidas",
      variants=("Pêssego", "Manga", "Maracujá"), keywords="suco nectar", image_query="nectar de fruta"),
    T("refrigerante", "Refrigerante", "Bebidas", (("350 ml", 3.49), ("2 L", 8.49)), "bebidas",
      variants=("Guaraná", "Cola", "Laranja", "Limão"), keywords="refrigerante refri", image_query="refrigerante guarana 2l",
      image="refrigerante-guarana-2l"),
    T("agua-mineral", "Água Mineral", "Bebidas", (("500 ml", 1.99), ("1,5 L", 2.99)), "bebidas",
      variants=("sem Gás", "com Gás"), keywords="agua", image_query="agua mineral sem gas", image="agua-mineral-1-5l"),
    T("cha-gelado", "Chá Gelado", "Bebidas", (("1,5 L", 6.99),), "bebidas",
      variants=("Limão", "Pêssego"), keywords="cha", image_query="cha gelado"),
    T("isotonico", "Bebida Isotônica", "Bebidas", (("500 ml", 5.49),), "bebidas",
      variants=("Limão", "Laranja"), keywords="isotonico esporte", image_query="bebida isotonica"),
    T("energetico", "Energético", "Bebidas", (("250 ml", 7.90),), "bebidas", keywords="energetico", image_query="energetico lata"),
    # ---------------------------------------------------------------- Padaria
    T("pao-forma", "Pão de Forma", "Padaria", (("500 g", 8.99),), "padaria",
      variants=("Tradicional", "Integral"), keywords="pao", image_query="pao de forma tradicional", image="pao-forma-500g"),
    T("bisnaguinha", "Bisnaguinha", "Padaria", (("300 g", 7.90),), "padaria", keywords="pao", image_query="bisnaguinha"),
    T("torrada", "Torrada", "Padaria", (("160 g", 5.90),), "padaria",
      variants=("Tradicional", "Integral"), keywords="torrada pao", image_query="torrada"),
    T("bolo", "Bolo Pronto", "Padaria", (("250 g", 8.90),), "padaria",
      variants=("Chocolate", "Laranja"), keywords="bolo", image_query="bolo pronto"),
    T("ovos", "Ovos", "Padaria", (("12 un", 11.90), ("30 un", 26.90)), "padaria",
      variants=("Brancos", "Vermelhos"), keywords="ovo ovos duzia", image_query="ovos brancos", image="ovos-brancos-12"),
    # ---------------------------------------------------------------- Limpeza
    T("detergente", "Detergente Líquido", "Limpeza", (("500 ml", 2.69),), "limpeza",
      variants=("Neutro", "Limão", "Coco"), keywords="detergente lava louca", image_query="detergente neutro",
      image_source="products", image="detergente-500ml"),
    T("sabao-po", "Sabão em Pó", "Limpeza", (("800 g", 13.90), ("1,6 kg", 25.90)), "limpeza",
      keywords="sabao lava roupa", image_query="sabao em po", image_source="products", image="sabao-po-1kg"),
    T("sabao-liquido", "Sabão Líquido para Roupas", "Limpeza", (("3 L", 34.90),), "limpeza",
      keywords="sabao lava roupa", image_query="sabao liquido", image_source="products"),
    T("amaciante", "Amaciante", "Limpeza", (("2 L", 14.90),), "limpeza",
      variants=("Tradicional", "Concentrado"), keywords="roupa", image_query="amaciante", image_source="products"),
    T("agua-sanitaria", "Água Sanitária", "Limpeza", (("1 L", 4.49), ("2 L", 7.90)), "limpeza",
      keywords="cloro", image_query="agua sanitaria", image_source="products"),
    T("desinfetante", "Desinfetante", "Limpeza", (("2 L", 9.90),), "limpeza",
      variants=("Lavanda", "Eucalipto", "Pinho"), keywords="limpeza", image_query="desinfetante", image_source="products"),
    T("multiuso", "Limpador Multiuso", "Limpeza", (("500 ml", 4.99),), "limpeza",
      keywords="limpeza", image_query="limpador multiuso", image_source="products"),
    T("esponja", "Esponja Dupla Face", "Limpeza", (("4 un", 5.90),), "limpeza",
      keywords="lava louca", image_query="esponja", image_source="products"),
    T("saco-lixo", "Saco de Lixo 30 L", "Limpeza", (("50 un", 12.90),), "limpeza",
      keywords="lixo", image_query="saco de lixo", image_source="products"),
    T("papel-toalha", "Papel Toalha", "Limpeza", (("2 rolos", 6.90),), "limpeza",
      keywords="papel cozinha", image_query="papel toalha", image_source="products"),
    # ---------------------------------------------------------------- Higiene
    T("creme-dental", "Creme Dental", "Higiene", (("90 g", 4.49),), "higiene",
      variants=("Tradicional", "Branqueador", "Menta"), keywords="pasta de dente", image_query="creme dental",
      image_source="beauty", image="creme-dental-90g"),
    T("sabonete", "Sabonete em Barra", "Higiene", (("90 g", 2.49),), "higiene",
      variants=("Erva-doce", "Aveia", "Glicerina"), keywords="sabonete banho", image_query="sabonete barra",
      image_source="beauty", image="sabonete-barra-90g"),
    T("shampoo", "Shampoo", "Higiene", (("350 ml", 14.90),), "higiene",
      variants=("Cabelos Normais", "Anticaspa", "Hidratação"), keywords="cabelo", image_query="shampoo", image_source="beauty"),
    T("condicionador", "Condicionador", "Higiene", (("350 ml", 15.90),), "higiene",
      variants=("Hidratação", "Cachos"), keywords="cabelo", image_query="condicionador", image_source="beauty"),
    T("desodorante", "Desodorante Aerossol", "Higiene", (("150 ml", 13.90),), "higiene",
      variants=("Masculino", "Feminino"), keywords="desodorante", image_query="desodorante aerosol", image_source="beauty"),
    T("papel-higienico", "Papel Higiênico Folha Dupla", "Higiene", (("4 rolos", 7.90), ("12 rolos", 19.90)), "higiene",
      keywords="papel banheiro", image_query="papel higienico", image_source="products"),
    T("fralda", "Fralda Descartável", "Higiene", (("P, 40 un", 39.90), ("M, 34 un", 39.90), ("G, 30 un", 39.90)), "higiene",
      keywords="fralda bebe", image_query="fralda", image_source="products"),
    T("escova-dente", "Escova de Dente", "Higiene", (("1 un", 6.90),), "higiene",
      keywords="dente", image_query="escova de dente", image_source="beauty"),
    # ---------------------------------------------------------------- Pet
    T("racao-cao", "Ração para Cães Adultos", "Pet", (("1 kg", 19.90), ("10 kg", 139.90)), "pet",
      variants=("Carne", "Frango"), keywords="racao cachorro cao", image_query="racao caes", image_source="petfood"),
    T("racao-gato", "Ração para Gatos Adultos", "Pet", (("1 kg", 24.90),), "pet",
      variants=("Peixe", "Frango"), keywords="racao gato", image_query="racao gatos", image_source="petfood"),
    T("areia-gato", "Areia Higiênica para Gatos", "Pet", (("4 kg", 14.90),), "pet",
      keywords="gato", image_query="areia gato", image_source="products"),
]

TYPES_BY_KEY = {t.key: t for t in TYPES}


def normalize(text: str) -> str:
    """Minúsculas e sem acentos: 'Feijão' -> 'feijao'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize(text)).strip("-")


def search_text(*parts: str) -> str:
    return normalize(" ".join(p for p in parts if p))


def _build_catalog() -> list[Product]:
    by_type: list[list[Product]] = []
    for t in TYPES:
        brands = BRANDS[t.brands]
        # fator de preço de cada marca, embaralhado de forma fixa por tipo
        factors = list(BRAND_FACTORS)
        random.Random(f"marcas-{t.key}").shuffle(factors)
        skus = []
        for variant in t.variants:
            name = f"{t.name} {variant}".strip()
            for unit, price in t.sizes:
                for brand, factor in zip(brands, factors):
                    skus.append(
                        Product(
                            slug=slugify(f"{t.key} {variant} {brand} {unit}"),
                            name=name,
                            brand=brand,
                            category=t.category,
                            unit=unit,
                            base_price=round(price * factor, 2),
                            image=t.image_key,
                            keywords=t.keywords,
                        )
                    )
        random.Random(f"vitrine-{t.key}").shuffle(skus)
        by_type.append(skus)

    # ordem de "destaques": um SKU de cada tipo por vez, para a vitrine variar
    products: list[Product] = []
    for rank in range(max(len(skus) for skus in by_type)):
        for skus in by_type:
            if rank < len(skus):
                products.append(replace(skus[rank], order=len(products)))
    return products


CATALOG: list[Product] = _build_catalog()
CATALOG_BY_SLUG = {p.slug: p for p in CATALOG}
