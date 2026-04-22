"""
Taxonomia de classificação de produtos financeiros.

Define as constantes e regras de mapeamento para classificar
qualquer produto de renda fixa, variável ou alternativo nas
dimensões da política macro Osira.
"""

# ── Indexador ───────────────────────────────────────────────────

INDEXER_PATTERNS: dict[str, str] = {
    'ipca +': 'ipca_plus',
    'ipca+': 'ipca_plus',
    '% cdi': 'cdi_pct',
    '%cdi': 'cdi_pct',
    'cdi +': 'cdi_plus',
    'cdi+': 'cdi_plus',
    'pré fixada': 'pre',
    'pré-fixada': 'pre',
    'pre fixada': 'pre',
    'prefixado': 'pre',
    'pré': 'pre',
    'igp-m': 'igpm',
    'igpm': 'igpm',
}

INDEXER_TO_SUBCLASS: dict[str, str] = {
    'cdi_pct': 'rf_pos',
    'cdi_plus': 'rf_pos',
    'ipca_plus': 'rf_infl',
    'igpm': 'rf_infl',
    'pre': 'rf_pre',
    'usd': 'rf_global',
}

# ── Grupos econômicos ───────────────────────────────────────────

GRUPO_ECONOMICO: dict[str, str] = {
    'axia': 'Eletrobras',
    'eletrobras': 'Eletrobras',
    'chesf': 'Eletrobras',
    'eletronorte': 'Eletrobras',
    'furnas': 'Eletrobras',
    'cgtee': 'Eletrobras',
    'eletrosul': 'Eletrobras',
    'cpfl': 'CPFL Energia',
    'neoenergia': 'Neoenergia',
    'eneva': 'Eneva',
    'sabesp': 'Sabesp',
    'comgás': 'Comgás',
    'comgas': 'Comgás',
    'alupar': 'Alupar',
    'cesp': 'CESP',
    'direcional': 'Direcional',
    'ecopistas': 'Ecopistas',
    'boa safra': 'Boa Safra',
    'mbrf': 'Marfrig',
    'marfrig': 'Marfrig',
    'delta': 'Delta Energia',
    'vale': 'Vale',
    'petrobras': 'Petrobras',
    'itau': 'Itaú',
    'itaú': 'Itaú',
    'bradesco': 'Bradesco',
    'btg': 'BTG Pactual',
    'santander': 'Santander',
    'bb ': 'Banco do Brasil',
    'caixa': 'Caixa',
}

# ── Setor → Sensibilidade macro ────────────────────────────────
# Ordem importa: checamos prefixos mais específicos primeiro

SECTOR_MACRO: list[tuple[str, str]] = [
    ('distribuição de gás', 'defensivo'),
    ('gás natural', 'defensivo'),
    ('saneamento', 'defensivo'),
    ('energia', 'defensivo'),
    ('elétric', 'defensivo'),
    ('geração', 'defensivo'),
    ('distribuição', 'defensivo'),
    ('transmissão', 'defensivo'),
    ('construção', 'ciclico'),
    ('imobiliário', 'ciclico'),
    ('varejo', 'ciclico'),
    ('consumo', 'ciclico'),
    ('shopping', 'ciclico'),
    ('agronegócio', 'commodity'),
    ('agricultura', 'commodity'),
    ('proteínas', 'commodity'),
    ('alimentos', 'commodity'),
    ('bebidas', 'commodity'),
    ('mineração', 'commodity'),
    ('petróleo', 'commodity'),
    ('petroquímic', 'commodity'),
    ('óleo', 'commodity'),
    ('transporte', 'infra'),
    ('mobilidade', 'infra'),
    ('concess', 'infra'),
    ('telecom', 'infra'),
    ('logística', 'infra'),
    ('rodovia', 'infra'),
    ('ferrovia', 'infra'),
    ('financeiro', 'financeiro'),
    ('banco', 'financeiro'),
    ('seguros', 'financeiro'),
]

# Emissores cujo setor da corretora é enganoso.
# Comgás é distribuidora de gás (utility), não produtora de petróleo.
ISSUER_SECTOR_OVERRIDE: dict[str, str] = {
    'Comgás': 'defensivo',
}

# Emissores cujas debêntures são de infraestrutura mesmo com setor
# não-óbvio na classificação da corretora.
ISSUER_INCENTIVADA_OVERRIDE: set[str] = {
    'Comgás',
}

# ── Setores de infraestrutura (elegíveis a debênture incentivada)

SETORES_INCENTIVADA: set[str] = {
    'energia',
    'saneamento',
    'transporte',
    'mobilidade',
    'telecom',
    'logística',
    'rodovia',
    'ferrovia',
    'porto',
    'geração',
    'transmissão',
    'distribuição',
}

# ── Instrumentos: prefixos de código ───────────────────────────
# Esses prefixos são checados contra o INÍCIO do código do ativo.
# Importante: "ltn" não deve casar com "ELTN" (Eletronorte).

INSTRUMENT_PREFIXES: list[tuple[str, str]] = [
    ('cra0', 'cra'),
    ('cra ', 'cra'),
    ('cri0', 'cri'),
    ('cri ', 'cri'),
    ('lca ', 'lca'),
    ('lca-', 'lca'),
    ('lci ', 'lci'),
    ('lci-', 'lci'),
    ('cdb ', 'cdb'),
    ('cdb-', 'cdb'),
]

# Nomes de instrumentos soberanos (match exato no início)
SOVEREIGN_CODES: list[tuple[str, str]] = [
    ('lft', 'lft'),
    ('ltn', 'ltn'),
    ('ntn-b principal', 'ntn_b_princ'),
    ('ntn-b', 'ntn_b'),
    ('ntn b', 'ntn_b'),
    ('ntn-f', 'ntn_f'),
    ('ntn f', 'ntn_f'),
    ('tesouro selic', 'lft'),
    ('tesouro prefixado', 'ltn'),
    ('tesouro ipca', 'ntn_b'),
]

# ── IR regressivo por prazo (anos → alíquota) ──────────────────

IR_REGRESSIVO: list[tuple[float, float]] = [
    (0.5, 0.225),
    (1.0, 0.200),
    (2.0, 0.175),
    (999, 0.150),
]
