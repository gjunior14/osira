"""
Motor de regras de compliance e risco.

Cada regra recebe um produto candidato, o perfil do cliente e o estado
atual da carteira, e retorna se o produto passa ou é bloqueado.
"""

from dataclasses import dataclass, field

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
    total_invested: float  # patrimônio financeiro total
    objectives: list[str] = field(default_factory=list)
    horizon_years: float = 5.0
    blacklist: list[str] = field(default_factory=list)
    max_credit_pct: float = 0.40
    max_per_issuer_pct: float = 0.10
    max_per_group_pct: float = 0.15
    max_per_sector_pct: float = 0.25
    min_liquidity_pct: float = 0.20


@dataclass
class Product:
    """Produto candidato a entrar na carteira."""

    code: str
    name: str
    instrument: str  # da taxonomy: debenture, cdb, lca, acao, fii...
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
