"""③ SERVIÇOS INDEPENDENTES — os 5 markets.

Cada pasta é um serviço separado: roda num processo próprio, escuta na própria porta
TCP e tem o próprio banco SQLite. O código se repete de propósito entre as pastas,
para deixar claro que nenhum supermercado depende de outro.

    aurora/         porta 5001   python -m markets.aurora
    supervila/      porta 5002   python -m markets.supervila
    emporio_sol/    porta 5003   python -m markets.emporio_sol
    max_atacarejo/  porta 5004   python -m markets.max_atacarejo
    ipe/            porta 5005   python -m markets.ipe
"""
