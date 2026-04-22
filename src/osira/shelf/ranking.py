"""
Motor de ranking de produtos de renda fixa.

Gera scores compostos e exporta CSV ordenado para análise.
"""

import csv
from dataclasses import dataclass

from osira.shelf.classifier import Produto


@dataclass
class ProdutoRankeado:
    produto: Produto
    score_yield: float = 0.0
    score_credit: float = 0.0
    score_tax: float = 0.0
    score_structure: float = 0.0
    score_diversification: float = 0.0
    score_total: float = 0.0


CREDIT_SCORES: dict[str, float] = {
    'soberano': 10.0,
    'hg': 8.5,
    'ig': 6.0,
    'hy': 3.5,
    'sem_rating': 2.0,
}

STRUCTURE_SCORES: dict[str, float] = {
    'bullet': 10.0,
    'amort': 7.0,
    'amort_carencia': 5.5,
    'custom': 4.0,
}


def _yield_score(produtos: list[Produto], p: Produto) -> float:
    """Percentil do yield líquido entre peers (mesmo indexador)."""
    peers = [x.yield_liquido for x in produtos if x.indexador == p.indexador]
    if len(peers) <= 1:
        return 5.0
    peers_sorted = sorted(peers)
    rank = peers_sorted.index(p.yield_liquido)
    return round(rank / (len(peers_sorted) - 1) * 10, 1)


def _diversification_score(produtos: list[Produto], p: Produto) -> float:
    """Penaliza grupos/setores super-representados."""
    n = len(produtos)
    grupo_count = sum(1 for x in produtos if x.grupo_economico == p.grupo_economico)
    sector_count = sum(1 for x in produtos if x.macro_sector == p.macro_sector)
    grupo_pct = grupo_count / n
    sector_pct = sector_count / n

    score = 10.0
    if grupo_pct > 0.20:
        score -= (grupo_pct - 0.20) * 20
    if sector_pct > 0.30:
        score -= (sector_pct - 0.30) * 15
    return max(round(score, 1), 0.0)


def rank_produtos(
    produtos: list[Produto],
    w_yield: float = 0.30,
    w_credit: float = 0.20,
    w_tax: float = 0.20,
    w_structure: float = 0.15,
    w_diversification: float = 0.15,
) -> list[ProdutoRankeado]:
    ranked = []
    for p in produtos:
        r = ProdutoRankeado(produto=p)
        r.score_yield = _yield_score(produtos, p)
        r.score_credit = CREDIT_SCORES.get(p.credit_quality, 5.0)
        r.score_tax = 10.0 if p.tributacao == 'isento_pf' else 4.0
        r.score_structure = STRUCTURE_SCORES.get(p.cash_flow, 5.0)
        r.score_diversification = _diversification_score(produtos, p)
        r.score_total = round(
            r.score_yield * w_yield
            + r.score_credit * w_credit
            + r.score_tax * w_tax
            + r.score_structure * w_structure
            + r.score_diversification * w_diversification,
            2,
        )
        ranked.append(r)

    ranked.sort(key=lambda x: -x.score_total)
    return ranked


CSV_COLUMNS = [
    'Rank',
    'Ativo',
    'Emissor',
    'Grupo',
    'Sub Classe Osira',
    'Indexador',
    'Taxa Bruta',
    'Yield Liquido',
    'Yield Equiv Tributado',
    'IR Aliquota',
    'Incentivada',
    'Duration',
    'Maturity Bucket',
    'Rating',
    'Credit Quality',
    'Issuer Type',
    'Setor Macro',
    'Setor Original',
    'Cash Flow',
    'Publico',
    'Qtd Disponivel',
    'Vencimento',
    'Score Yield',
    'Score Credit',
    'Score Tax',
    'Score Structure',
    'Score Diversification',
    'SCORE TOTAL',
]


def export_csv(ranked: list[ProdutoRankeado], filepath: str) -> None:
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(CSV_COLUMNS)
        for i, r in enumerate(ranked, 1):
            p = r.produto
            w.writerow(
                [
                    i,
                    p.ativo,
                    p.emissor,
                    p.grupo_economico,
                    p.sub_classe,
                    p.indexador,
                    f'{p.yield_bruto:.2f}%',
                    f'{p.yield_liquido:.2f}%',
                    f'{p.yield_equivalente_tributado:.2f}%',
                    f'{p.ir_aliquota:.1%}' if p.ir_aliquota > 0 else 'isento',
                    'Sim' if p.incentivada else 'Não',
                    f'{p.duration:.1f}',
                    p.maturity_bucket,
                    p.rating_raw,
                    p.credit_quality,
                    p.issuer_type,
                    p.macro_sector,
                    p.setor_raw,
                    p.cash_flow,
                    p.publico.upper(),
                    p.quantidade,
                    p.vencimento,
                    f'{r.score_yield:.1f}',
                    f'{r.score_credit:.1f}',
                    f'{r.score_tax:.1f}',
                    f'{r.score_structure:.1f}',
                    f'{r.score_diversification:.1f}',
                    f'{r.score_total:.2f}',
                ]
            )
