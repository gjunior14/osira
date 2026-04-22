"""
Classificador universal de produtos financeiros.

Recebe dados brutos de uma prateleira (banco/corretora) e retorna
cada produto classificado em 12 dimensões para mapeamento à
política macro Osira.
"""

from dataclasses import dataclass

from osira.shelf.taxonomy import (
    GRUPO_ECONOMICO,
    INDEXER_PATTERNS,
    INDEXER_TO_SUBCLASS,
    INSTRUMENT_PREFIXES,
    IR_REGRESSIVO,
    ISSUER_INCENTIVADA_OVERRIDE,
    ISSUER_SECTOR_OVERRIDE,
    SECTOR_MACRO,
    SETORES_INCENTIVADA,
    SOVEREIGN_CODES,
)


@dataclass
class Produto:
    ativo: str
    emissor: str
    indexador_raw: str
    taxa: float
    duration: float
    vencimento: str
    amortizacao_raw: str
    rating_raw: str
    setor_raw: str
    publico: str
    quantidade: int

    # 12 dimensões classificadas
    classe_macro: str = ''
    sub_classe: str = ''
    indexador: str = ''
    instrumento: str = ''
    credit_quality: str = ''
    issuer_type: str = ''
    grupo_economico: str = ''
    maturity_bucket: str = ''
    macro_sector: str = ''
    cash_flow: str = ''
    tributacao: str = ''
    incentivada: bool = False

    # Métricas derivadas
    yield_bruto: float = 0.0
    yield_liquido: float = 0.0
    yield_equivalente_tributado: float = 0.0
    ir_aliquota: float = 0.0


# ── Inferência de cada dimensão ─────────────────────────────────


def infer_indexador(raw: str) -> str:
    low = raw.strip().lower()
    for pattern, value in INDEXER_PATTERNS.items():
        if pattern in low:
            return value
    return low or 'indefinido'


def infer_instrumento(ativo: str, emissor: str) -> str:
    """Infere o tipo de instrumento pelo código do ativo e nome do emissor."""
    code_low = ativo.strip().lower()
    name_low = (ativo + ' ' + emissor).strip().lower()

    for prefix, instr in SOVEREIGN_CODES:
        if code_low == prefix or name_low.startswith(prefix):
            return instr

    for prefix, instr in INSTRUMENT_PREFIXES:
        if code_low.startswith(prefix):
            return instr

    if code_low.startswith('cra'):
        return 'cra'
    if code_low.startswith('cri'):
        return 'cri'

    return 'debenture'


def infer_sub_classe(indexador: str, instrumento: str) -> str:
    if instrumento in ('acao', 'etf_br'):
        return 'rv_br'
    if instrumento in ('bdr', 'fundo_intl', 'etf_intl'):
        return 'rv_dm'
    if instrumento == 'fii':
        return 'imobiliario'
    if instrumento == 'fundo_cripto':
        return 'cripto'
    if instrumento == 'fundo_ouro':
        return 'ouro'
    return INDEXER_TO_SUBCLASS.get(indexador, 'rf_pos')


def infer_classe_macro(sub_classe: str) -> str:
    if sub_classe.startswith('rf'):
        return 'rf'
    if sub_classe.startswith('rv'):
        return 'rv'
    if sub_classe in ('imobiliario', 'ouro', 'cripto'):
        return 'alt'
    return 'mm'


def infer_issuer_type(instrumento: str) -> str:
    sovereign = {'lft', 'ltn', 'ntn_b', 'ntn_f', 'ntn_b_princ'}
    banking = {'cdb', 'lca', 'lci'}
    if instrumento in sovereign:
        return 'governo'
    if instrumento in banking:
        return 'bancario'
    return 'corporativo'


def infer_grupo(emissor: str) -> str:
    low = emissor.lower()
    for key, grupo in GRUPO_ECONOMICO.items():
        if key in low:
            return grupo
    return emissor.split('(')[0].strip().title()


def infer_macro_sector(setor: str, grupo: str) -> str:
    if grupo in ISSUER_SECTOR_OVERRIDE:
        return ISSUER_SECTOR_OVERRIDE[grupo]
    low = setor.lower()
    for keyword, macro in SECTOR_MACRO:
        if keyword in low:
            return macro
    return 'outros'


def classify_credit(rating: str) -> str:
    r = rating.strip().upper()
    if r in ('GOVERNO', 'SOBERANO'):
        return 'soberano'
    if r in ('AAA', 'AA+', 'AA', 'AA-'):
        return 'hg'
    if r in ('A+', 'A', 'A-', 'BBB+', 'BBB', 'BBB-'):
        return 'ig'
    if r in ('BB+', 'BB', 'BB-', 'B+', 'B', 'B-'):
        return 'hy'
    if 'sem' in r.lower() or r in ('', '-'):
        return 'sem_rating'
    return 'ig'


def classify_maturity(dur: float) -> str:
    if dur < 0.5:
        return 'ultracurto'
    if dur < 2:
        return 'curto'
    if dur < 5:
        return 'medio'
    if dur < 10:
        return 'longo'
    return 'muito_longo'


def classify_cash_flow(amort: str) -> str:
    low = amort.lower()
    if 'bullet' in low:
        return 'bullet'
    if 'custom' in low or 'fluxo' in low:
        return 'custom'
    if 'carência' in low or 'carencia' in low:
        return 'amort_carencia'
    if any(x in low for x in ('semestral', 'anual', 'mensal')):
        return 'amort'
    if '/' in low and 'ano' in low:
        return 'amort'
    return 'bullet'


def is_incentivada(instrumento: str, setor: str, grupo: str) -> bool:
    """Debêntures de infraestrutura são isentas de IR (Lei 12.431)."""
    if instrumento != 'debenture':
        return False
    if grupo in ISSUER_INCENTIVADA_OVERRIDE:
        return True
    low = setor.lower()
    return any(kw in low for kw in SETORES_INCENTIVADA)


def infer_tributacao(instrumento: str, incentivada: bool) -> str:
    isentos = {'lca', 'lci', 'cra', 'cri'}
    if instrumento in isentos or incentivada:
        return 'isento_pf'
    if instrumento in ('acao', 'bdr', 'etf_br', 'fii'):
        return 'rv'
    return 'regressiva'


def calc_ir_aliquota(duration: float, tributacao: str) -> float:
    if tributacao != 'regressiva':
        return 0.0
    for threshold, rate in IR_REGRESSIVO:
        if duration <= threshold:
            return rate
    return 0.15


def calc_yields(
    taxa: float,
    indexador: str,
    ir_aliquota: float,
    tributacao: str,
) -> tuple[float, float, float]:
    """Calcula yield bruto, líquido e equivalente tributado.

    Para IPCA+: o IR incide sobre o ganho total (spread + correção).
    Aproximamos assumindo IPCA = 5% a.a. para estimar o impacto.
    Para CDI%: taxa já é o % do CDI, retornamos como está.
    Para Pré: taxa já é o yield nominal.
    """
    ipca_estimado = 5.0
    yield_bruto = taxa

    if tributacao == 'isento_pf':
        yield_liquido = yield_bruto
        if indexador == 'ipca_plus':
            yield_equiv = yield_bruto / 0.85
        elif indexador == 'pre':
            nominal = yield_bruto
            nominal_liq = nominal
            yield_equiv = nominal_liq / 0.85
        else:
            yield_equiv = yield_bruto / 0.85
    elif tributacao == 'regressiva':
        if indexador == 'ipca_plus':
            nominal_total = taxa + ipca_estimado
            nominal_liq = nominal_total * (1 - ir_aliquota)
            yield_liquido = nominal_liq - ipca_estimado
            yield_equiv = yield_bruto
        elif indexador == 'pre':
            yield_liquido = taxa * (1 - ir_aliquota)
            yield_equiv = yield_bruto
        else:
            yield_liquido = taxa * (1 - ir_aliquota)
            yield_equiv = yield_bruto
    else:
        yield_liquido = yield_bruto
        yield_equiv = yield_bruto

    return (
        round(yield_bruto, 2),
        round(yield_liquido, 2),
        round(yield_equiv, 2),
    )


# ── Classificador principal ─────────────────────────────────────


def classify(p: Produto) -> Produto:
    """Preenche todas as 12 dimensões + métricas derivadas."""
    p.indexador = infer_indexador(p.indexador_raw)
    p.instrumento = infer_instrumento(p.ativo, p.emissor)
    p.sub_classe = infer_sub_classe(p.indexador, p.instrumento)
    p.classe_macro = infer_classe_macro(p.sub_classe)
    p.credit_quality = classify_credit(p.rating_raw)
    p.issuer_type = infer_issuer_type(p.instrumento)
    p.grupo_economico = infer_grupo(p.emissor)
    p.maturity_bucket = classify_maturity(p.duration)
    p.macro_sector = infer_macro_sector(p.setor_raw, p.grupo_economico)
    p.cash_flow = classify_cash_flow(p.amortizacao_raw)
    p.incentivada = is_incentivada(p.instrumento, p.setor_raw, p.grupo_economico)
    p.tributacao = infer_tributacao(p.instrumento, p.incentivada)
    p.ir_aliquota = calc_ir_aliquota(p.duration, p.tributacao)

    p.yield_bruto, p.yield_liquido, p.yield_equivalente_tributado = calc_yields(
        p.taxa, p.indexador, p.ir_aliquota, p.tributacao
    )

    return p
