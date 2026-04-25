"""
Motor de regras de compliance e risco.

Cada regra recebe um produto candidato, o perfil do cliente e o estado
atual da carteira, e retorna se o produto passa ou é bloqueado.
"""

from dataclasses import dataclass, field
from datetime import date

from osira.compliance.anbima import (
    PROFILE_MAX_SCORE,
    calc_anbima_score,
    is_suitable,
)


@dataclass
class ClientProfile:
    """Perfil do cliente para compliance."""

    name: str
    suitability: str  # conservador, moderado, arrojado
    investor_tier: str  # varejo, qualificado, profissional
    total_invested: float
    profile_date: date | None = None  # CVM 30 Art. 9: max 5 anos
    objectives: list[str] = field(default_factory=list)
    horizon_years: float = 5.0
    blacklist: list[str] = field(default_factory=list)
    max_credit_pct: float = 0.40
    max_per_issuer_pct: float = 0.10
    max_per_group_pct: float = 0.15
    max_per_sector_pct: float = 0.25
    min_liquidity_pct: float = 0.20


# Produtos automaticamente complexos (ANBIMA Art. 23)
COMPLEX_PRODUCTS: set[str] = {
    'coe',
    'debenture_conversivel',
    'fidc',
    'fip',
}

# Alavancagem máxima por tipo de fundo para varejo (CVM 175 Art. 73)
FUND_MAX_LEVERAGE: dict[str, float] = {
    'fundo_rf': 0.20,
    'fundo_cambial': 0.40,
    'fundo_acoes': 0.40,
    'fundo_mm': 0.70,
}


@dataclass
class Product:
    """Produto candidato a entrar na carteira."""

    code: str
    name: str
    instrument: str  # debenture, cdb, lca, acao, fii, fidc, fip, coe...
    issuer_type: str  # gov, bank, corp
    grupo: str
    sector: str
    rating: str
    is_ig: bool  # ANBIMA IG = rating ≥ BBB- = credit_quality in (hg, ig, soberano)
    indexer: str  # pos, pre, ipca_plus
    duration: float
    maturity_bucket: str
    credit_quality: str  # soberano, hg, ig, hy, sem_rating
    publico: str  # pg, iq, ip
    amount: float = 0.0
    fgc_covered: bool = False
    redemption_days: int = 0
    is_complex: bool = False  # ANBIMA Art. 23
    is_proprietary: bool = False  # CVM 179: produto do próprio distribuidor
    fund_leverage_pct: float = 0.0  # CVM 175 Art. 73
    fund_limited_liability: bool = True  # CVM 175: responsabilidade limitada
    fidc_is_senior: bool = True  # CVM 175 Anexo II
    fidc_has_rating: bool = False
    fidc_max_lockup_days: int = 0
    total_cost_pct: float = 0.0  # custos totais (taxa adm + perf + dist)


@dataclass
class PortfolioState:
    """Estado atual da carteira para checar concentração."""

    total_value: float = 0.0
    by_issuer: dict[str, float] = field(default_factory=dict)
    by_group: dict[str, float] = field(default_factory=dict)
    by_sector: dict[str, float] = field(default_factory=dict)
    by_institution_fgc: dict[str, float] = field(default_factory=dict)
    credit_total: float = 0.0
    liquid_total: float = 0.0


@dataclass
class RuleResult:
    rule: str
    passed: bool
    reason: str
    severity: str = 'block'  # block, warn


# ── Regras Regulatórias ─────────────────────────────────────────


def check_suitability(product: Product, client: ClientProfile) -> RuleResult:
    """ANBIMA Art. 20: score do produto vs. perfil do cliente."""
    rate_type = 'pos'
    if product.indexer in ('pre',):
        rate_type = 'pre'
    elif product.indexer in ('ipca_plus', 'igpm'):
        rate_type = 'pre'

    score = calc_anbima_score(
        instrument=product.instrument,
        is_ig=product.is_ig,
        rate_type=rate_type,
        maturity_bucket=product.maturity_bucket,
        redemption_days=product.redemption_days,
    )

    max_allowed = PROFILE_MAX_SCORE.get(client.suitability, 0)

    if is_suitable(score, client.suitability):
        return RuleResult(
            rule='ANBIMA Suitability',
            passed=True,
            reason=f'Score {score:.2f} ≤ {max_allowed} ({client.suitability})',
        )
    return RuleResult(
        rule='ANBIMA Suitability',
        passed=False,
        reason=(
            f'Score {score:.2f} > {max_allowed} '
            f'({client.suitability}). Produto inadequado ao perfil.'
        ),
    )


def check_investor_tier(product: Product, client: ClientProfile) -> RuleResult:
    """CVM Res. 30: investidor qualificado/profissional."""
    tier_rank = {'varejo': 0, 'qualificado': 1, 'profissional': 2}
    required_rank = {'pg': 0, 'iq': 1, 'ip': 2}

    client_rank = tier_rank.get(client.investor_tier, 0)
    product_rank = required_rank.get(product.publico, 0)

    if client_rank >= product_rank:
        return RuleResult(
            rule='CVM Qualificação',
            passed=True,
            reason=f'Cliente {client.investor_tier} ≥ {product.publico}',
        )
    tier_label = {'iq': 'qualificado (>R$1M)', 'ip': 'profissional (>R$10M)'}
    return RuleResult(
        rule='CVM Qualificação',
        passed=False,
        reason=(
            f'Produto exige investidor {tier_label.get(product.publico, product.publico)}. '
            f'Cliente é {client.investor_tier}.'
        ),
    )


FGC_LIMIT = 250_000.0


def check_fgc(
    product: Product,
    client: ClientProfile,
    portfolio: PortfolioState,
) -> RuleResult:
    """FGC: R$ 250k por CPF por instituição."""
    if not product.fgc_covered:
        return RuleResult(
            rule='FGC',
            passed=True,
            reason=f'{product.instrument} não é coberto pelo FGC',
            severity='warn',
        )

    current = portfolio.by_institution_fgc.get(product.grupo, 0)
    after = current + product.amount

    if after <= FGC_LIMIT:
        return RuleResult(
            rule='FGC',
            passed=True,
            reason=f'R$ {after:,.0f} / R$ {FGC_LIMIT:,.0f} na {product.grupo}',
        )
    return RuleResult(
        rule='FGC',
        passed=False,
        reason=(
            f'Excede FGC: R$ {after:,.0f} na {product.grupo} '
            f'(limite R$ {FGC_LIMIT:,.0f}/instituição)'
        ),
        severity='warn',
    )


# ── Regras Internas ─────────────────────────────────────────────


def check_issuer_concentration(
    product: Product,
    client: ClientProfile,
    portfolio: PortfolioState,
) -> RuleResult:
    """Max % por emissor individual."""
    if portfolio.total_value <= 0:
        return RuleResult(
            rule='Concentração Emissor',
            passed=True,
            reason='Carteira vazia',
        )

    current = portfolio.by_issuer.get(product.name, 0)
    after_pct = (current + product.amount) / portfolio.total_value

    if after_pct <= client.max_per_issuer_pct:
        return RuleResult(
            rule='Concentração Emissor',
            passed=True,
            reason=f'{after_pct:.1%} ≤ {client.max_per_issuer_pct:.0%}',
        )
    return RuleResult(
        rule='Concentração Emissor',
        passed=False,
        reason=(
            f'Emissor {product.name}: {after_pct:.1%} > '
            f'{client.max_per_issuer_pct:.0%} do portfólio'
        ),
    )


def check_group_concentration(
    product: Product,
    client: ClientProfile,
    portfolio: PortfolioState,
) -> RuleResult:
    """Max % por grupo econômico."""
    if portfolio.total_value <= 0:
        return RuleResult(
            rule='Concentração Grupo',
            passed=True,
            reason='Carteira vazia',
        )

    current = portfolio.by_group.get(product.grupo, 0)
    after_pct = (current + product.amount) / portfolio.total_value

    if after_pct <= client.max_per_group_pct:
        return RuleResult(
            rule='Concentração Grupo',
            passed=True,
            reason=f'{product.grupo}: {after_pct:.1%} ≤ {client.max_per_group_pct:.0%}',
        )
    return RuleResult(
        rule='Concentração Grupo',
        passed=False,
        reason=(f'Grupo {product.grupo}: {after_pct:.1%} > {client.max_per_group_pct:.0%}'),
    )


def check_sector_concentration(
    product: Product,
    client: ClientProfile,
    portfolio: PortfolioState,
) -> RuleResult:
    """Max % por setor macro."""
    if portfolio.total_value <= 0:
        return RuleResult(
            rule='Concentração Setor',
            passed=True,
            reason='Carteira vazia',
        )

    current = portfolio.by_sector.get(product.sector, 0)
    after_pct = (current + product.amount) / portfolio.total_value

    if after_pct <= client.max_per_sector_pct:
        return RuleResult(
            rule='Concentração Setor',
            passed=True,
            reason=f'{product.sector}: {after_pct:.1%} ≤ {client.max_per_sector_pct:.0%}',
        )
    return RuleResult(
        rule='Concentração Setor',
        passed=False,
        reason=(f'Setor {product.sector}: {after_pct:.1%} > {client.max_per_sector_pct:.0%}'),
    )


def check_credit_limit(
    product: Product,
    client: ClientProfile,
    portfolio: PortfolioState,
) -> RuleResult:
    """Max % em crédito privado (não-soberano, não-bancário IG)."""
    is_private_credit = product.issuer_type == 'corp'
    if not is_private_credit:
        return RuleResult(
            rule='Limite Crédito Privado',
            passed=True,
            reason='Não é crédito privado',
        )

    if portfolio.total_value <= 0:
        return RuleResult(
            rule='Limite Crédito Privado',
            passed=True,
            reason='Carteira vazia',
        )

    after_pct = (portfolio.credit_total + product.amount) / portfolio.total_value

    if after_pct <= client.max_credit_pct:
        return RuleResult(
            rule='Limite Crédito Privado',
            passed=True,
            reason=f'Crédito privado: {after_pct:.1%} ≤ {client.max_credit_pct:.0%}',
        )
    return RuleResult(
        rule='Limite Crédito Privado',
        passed=False,
        reason=(f'Crédito privado: {after_pct:.1%} > {client.max_credit_pct:.0%}'),
    )


def check_maturity_match(product: Product, client: ClientProfile) -> RuleResult:
    """Prazo do produto vs. horizonte do cliente."""
    if product.duration <= client.horizon_years:
        return RuleResult(
            rule='Match de Prazo',
            passed=True,
            reason=(f'Duration {product.duration:.1f}a ≤ horizonte {client.horizon_years:.0f}a'),
        )
    overshoot = product.duration - client.horizon_years
    if overshoot <= 2:
        return RuleResult(
            rule='Match de Prazo',
            passed=True,
            reason=(
                f'Duration {product.duration:.1f}a excede horizonte em {overshoot:.1f}a (tolerável)'
            ),
            severity='warn',
        )
    return RuleResult(
        rule='Match de Prazo',
        passed=False,
        reason=(
            f'Duration {product.duration:.1f}a >> horizonte '
            f'{client.horizon_years:.0f}a (excede em {overshoot:.1f}a)'
        ),
        severity='warn',
    )


def check_blacklist(product: Product, client: ClientProfile) -> RuleResult:
    """Ativos vetados pelo cliente."""
    blocked = [
        b
        for b in client.blacklist
        if b.lower() in product.code.lower()
        or b.lower() in product.name.lower()
        or b.lower() in product.grupo.lower()
    ]
    if not blocked:
        return RuleResult(
            rule='Blacklist Cliente',
            passed=True,
            reason='Não está na lista de exclusão',
        )
    return RuleResult(
        rule='Blacklist Cliente',
        passed=False,
        reason=f'Cliente vetou: {", ".join(blocked)}',
    )


def check_min_rating(product: Product, client: ClientProfile) -> RuleResult:
    """Rating mínimo por perfil (regra interna Osira)."""
    min_by_profile: dict[str, set[str]] = {
        'conservador': {'hg', 'soberano'},
        'moderado': {'hg', 'ig', 'soberano'},
        'arrojado': {'hg', 'ig', 'hy', 'soberano', 'sem_rating'},
    }

    allowed = min_by_profile.get(client.suitability, set())

    if product.credit_quality in allowed:
        return RuleResult(
            rule='Rating Mínimo',
            passed=True,
            reason=(f'{product.credit_quality.upper()} permitido para {client.suitability}'),
        )
    return RuleResult(
        rule='Rating Mínimo',
        passed=False,
        reason=(
            f'Rating {product.credit_quality.upper()} não permitido '
            f'para perfil {client.suitability}. '
            f'Permitidos: {", ".join(sorted(allowed))}'
        ),
    )


# ── Regras Regulatórias Adicionais ──────────────────────────────

PROFILE_MAX_AGE_DAYS = 5 * 365  # CVM 30 Art. 9-I: max 5 anos


def check_profile_expiration(product: Product, client: ClientProfile) -> RuleResult:
    """CVM 30 Art. 9: perfil deve estar atualizado (max 5 anos)."""
    if client.profile_date is None:
        return RuleResult(
            rule='CVM 30 Perfil Atualizado',
            passed=False,
            reason='Data do perfil não informada. Proibido recomendar (Art. 6-III).',
        )
    age = (date.today() - client.profile_date).days
    if age <= PROFILE_MAX_AGE_DAYS:
        years = age / 365
        return RuleResult(
            rule='CVM 30 Perfil Atualizado',
            passed=True,
            reason=f'Perfil atualizado há {years:.1f} anos (max 5)',
        )
    return RuleResult(
        rule='CVM 30 Perfil Atualizado',
        passed=False,
        reason=(
            f'Perfil desatualizado: {age} dias (max {PROFILE_MAX_AGE_DAYS}). '
            f'VEDADO recomendar (CVM 30 Art. 6-III).'
        ),
    )


def check_complex_product(product: Product, client: ClientProfile) -> RuleResult:
    """ANBIMA Art. 23 + CVM 30 Art. 8-II: produtos complexos."""
    is_complex = product.is_complex or product.instrument in COMPLEX_PRODUCTS
    if not is_complex:
        return RuleResult(
            rule='ANBIMA Produto Complexo',
            passed=True,
            reason='Não é produto complexo',
        )
    return RuleResult(
        rule='ANBIMA Produto Complexo',
        passed=True,
        reason=(
            f'{product.instrument} é produto complexo (ANBIMA Art. 23). '
            f'Exige: (1) informar riscos estruturais vs. produtos tradicionais, '
            f'(2) declaração escrita de ciência do investidor.'
        ),
        severity='warn',
    )


def check_fidc_retail(product: Product, client: ClientProfile) -> RuleResult:
    """CVM 175 Anexo II: 5 condições cumulativas para FIDC varejo."""
    if product.instrument != 'fidc':
        return RuleResult(
            rule='CVM 175 FIDC Varejo',
            passed=True,
            reason='Não é FIDC',
        )
    if client.investor_tier in ('qualificado', 'profissional'):
        return RuleResult(
            rule='CVM 175 FIDC Varejo',
            passed=True,
            reason=f'Investidor {client.investor_tier} — sem restrição FIDC',
        )

    blocks = []
    if not product.fidc_is_senior:
        blocks.append('somente cotas sênior para varejo')
    if not product.fidc_has_rating:
        blocks.append('rating obrigatório para varejo')
    if product.fidc_max_lockup_days > 180:
        blocks.append(f'lockup {product.fidc_max_lockup_days}d > 180d max')

    if blocks:
        return RuleResult(
            rule='CVM 175 FIDC Varejo',
            passed=False,
            reason=f'FIDC não elegível para varejo: {"; ".join(blocks)}',
        )
    return RuleResult(
        rule='CVM 175 FIDC Varejo',
        passed=True,
        reason='FIDC atende 5 condições CVM 175 para varejo',
    )


def check_fund_leverage(product: Product, client: ClientProfile) -> RuleResult:
    """CVM 175 Art. 73: limites de alavancagem por tipo de fundo."""
    if product.fund_leverage_pct <= 0:
        return RuleResult(
            rule='CVM 175 Alavancagem',
            passed=True,
            reason='Sem alavancagem declarada',
        )
    if client.investor_tier == 'profissional':
        return RuleResult(
            rule='CVM 175 Alavancagem',
            passed=True,
            reason='Profissional: sem limite de alavancagem',
        )

    fund_type = product.instrument
    max_lev = FUND_MAX_LEVERAGE.get(fund_type, 0.70)

    if product.fund_leverage_pct <= max_lev:
        return RuleResult(
            rule='CVM 175 Alavancagem',
            passed=True,
            reason=f'Alavancagem {product.fund_leverage_pct:.0%} ≤ {max_lev:.0%}',
        )
    return RuleResult(
        rule='CVM 175 Alavancagem',
        passed=False,
        reason=(
            f'Alavancagem {product.fund_leverage_pct:.0%} > '
            f'{max_lev:.0%} (max CVM 175 para {fund_type})'
        ),
    )


def check_fund_liability(product: Product, client: ClientProfile) -> RuleResult:
    """CVM 175: responsabilidade limitada vs. ilimitada."""
    if product.fund_limited_liability:
        return RuleResult(
            rule='CVM 175 Responsabilidade',
            passed=True,
            reason='Responsabilidade limitada',
        )
    if client.investor_tier in ('qualificado', 'profissional'):
        return RuleResult(
            rule='CVM 175 Responsabilidade',
            passed=True,
            reason=(
                f'Responsabilidade ilimitada — {client.investor_tier} '
                f'pode, mas requer termo de ciência.'
            ),
            severity='warn',
        )
    return RuleResult(
        rule='CVM 175 Responsabilidade',
        passed=False,
        reason='Fundo com responsabilidade ilimitada: vedado para varejo.',
    )


def check_proprietary_product(product: Product, client: ClientProfile) -> RuleResult:
    """CVM 179/2023: conflito de interesse em produto proprietário."""
    if not product.is_proprietary:
        return RuleResult(
            rule='CVM 179 Conflito',
            passed=True,
            reason='Não é produto proprietário',
        )
    return RuleResult(
        rule='CVM 179 Conflito',
        passed=True,
        reason=(
            'Produto proprietário — CVM 179 exige: '
            '(1) disclosure de remuneração, '
            '(2) extrato trimestral ao investidor, '
            '(3) política de conflito de interesses.'
        ),
        severity='warn',
    )


MAX_COST_BY_PROFILE: dict[str, float] = {
    'conservador': 0.01,
    'moderado': 0.02,
    'arrojado': 0.03,
}


def check_excessive_cost(product: Product, client: ClientProfile) -> RuleResult:
    """CVM 30 Art. 3 §5: custos excessivos para o perfil."""
    if product.total_cost_pct <= 0:
        return RuleResult(
            rule='CVM 30 Custo Excessivo',
            passed=True,
            reason='Custo não informado',
        )

    max_cost = MAX_COST_BY_PROFILE.get(client.suitability, 0.03)

    if product.total_cost_pct <= max_cost:
        return RuleResult(
            rule='CVM 30 Custo Excessivo',
            passed=True,
            reason=f'Custo {product.total_cost_pct:.2%} ≤ {max_cost:.0%}',
        )
    return RuleResult(
        rule='CVM 30 Custo Excessivo',
        passed=False,
        reason=(
            f'Custo total {product.total_cost_pct:.2%} > '
            f'{max_cost:.0%} (max para {client.suitability}). '
            f'CVM 30 Art. 3 §5: vedado custo excessivo.'
        ),
        severity='warn',
    )
