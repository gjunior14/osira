"""
Parsers de prateleiras de bancos/corretoras.

Lê dados tabulares (TSV, CSV) e retorna lista de Produto classificado.
"""

import csv

from osira.shelf.classifier import Produto, classify


def _parse_float(raw: str) -> float:
    clean = raw.replace('%', '').replace(',', '.').strip()
    try:
        return float(clean)
    except ValueError:
        return 0.0


def _parse_int(raw: str) -> int:
    clean = raw.replace('.', '').replace(',', '').strip()
    try:
        return int(clean)
    except ValueError:
        return 0


def parse_tsv(filepath: str) -> list[Produto]:
    """Lê prateleira em formato TSV (tab-separated) com header padrão.

    Colunas esperadas (13):
    Emissor | Ativo | Indexador | Taxa | Dur | Vencimento |
    Juros | Meses | Amortização | Rating | Setor | Público | Quantidade
    """
    produtos = []
    with open(filepath, encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        next(reader)
        for row in reader:
            if len(row) < 13:
                continue
            p = Produto(
                ativo=row[1].strip(),
                emissor=row[0].strip(),
                indexador_raw=row[2].strip(),
                taxa=_parse_float(row[3]),
                duration=_parse_float(row[4]),
                vencimento=row[5].strip(),
                amortizacao_raw=row[8].strip(),
                rating_raw=row[9].strip(),
                setor_raw=row[10].strip(),
                publico=row[11].strip().lower(),
                quantidade=_parse_int(row[12]),
            )
            produtos.append(classify(p))
    return produtos
