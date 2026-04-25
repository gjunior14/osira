"""
Compliance checker — orquestra todas as regras sobre uma lista de produtos.

Recebe produtos candidatos + perfil do cliente + estado da carteira,
roda todas as regras e retorna relatório de aprovados/bloqueados.
"""

from dataclasses import dataclass, field

from osira.compliance.rules import (
    ClientProfile,
    PortfolioState,
    Product,
    RuleResult,
    check_blacklist,
    check_complex_product,
    check_credit_limit,
    check_excessive_cost,
    check_fgc,
    check_fidc_retail,
    check_fund_leverage,
    check_fund_liability,
    check_group_concentration,
    check_investor_tier,
    check_issuer_concentration,
    check_maturity_match,
    check_min_rating,
    check_profile_expiration,
    check_proprietary_product,
    check_sector_concentration,
    check_suitability,
)


@dataclass
class ProductVerdict:
    product: Product
    results: list[RuleResult] = field(default_factory=list)

    @property
    def approved(self) -> bool:
        return all(r.passed or r.severity == 'warn' for r in self.results)

    @property
    def blocks(self) -> list[RuleResult]:
        return [r for r in self.results if not r.passed and r.severity == 'block']

    @property
    def warnings(self) -> list[RuleResult]:
        return [r for r in self.results if not r.passed and r.severity == 'warn']


@dataclass
class ComplianceReport:
    client: ClientProfile
    verdicts: list[ProductVerdict] = field(default_factory=list)

    @property
    def approved(self) -> list[ProductVerdict]:
        return [v for v in self.verdicts if v.approved]

    @property
    def blocked(self) -> list[ProductVerdict]:
        return [v for v in self.verdicts if not v.approved]

    def summary(self) -> str:
        lines = [
            f'Compliance Report — {self.client.name}',
            f'Perfil: {self.client.suitability} | Tier: {self.client.investor_tier}',
            f'Produtos: {len(self.verdicts)} analisados, '
            f'{len(self.approved)} aprovados, '
            f'{len(self.blocked)} bloqueados',
            '',
        ]

        if self.blocked:
            lines.append('BLOQUEADOS:')
            for v in self.blocked:
                reasons = '; '.join(r.reason for r in v.blocks)
                lines.append(f'  ✗ {v.product.code} — {reasons}')

        if self.approved:
            lines.append('\nAPROVADOS:')
            for v in self.approved:
                warns = [r.reason for r in v.warnings]
                suffix = f' ⚠ {"; ".join(warns)}' if warns else ''
                lines.append(f'  ✓ {v.product.code}{suffix}')

        return '\n'.join(lines)


def check_product(
    product: Product,
    client: ClientProfile,
    portfolio: PortfolioState,
) -> ProductVerdict:
    verdict = ProductVerdict(product=product)

    for rule in (
        check_profile_expiration,
        check_suitability,
        check_investor_tier,
        check_complex_product,
        check_fidc_retail,
        check_fund_leverage,
        check_fund_liability,
        check_proprietary_product,
        check_excessive_cost,
        check_maturity_match,
        check_min_rating,
        check_blacklist,
    ):
        verdict.results.append(rule(product, client))

    for rule in (
        check_fgc,
        check_issuer_concentration,
        check_group_concentration,
        check_sector_concentration,
        check_credit_limit,
    ):
        verdict.results.append(rule(product, client, portfolio))

    return verdict


def check_shelf(
    products: list[Product],
    client: ClientProfile,
    portfolio: PortfolioState | None = None,
) -> ComplianceReport:
    """Roda compliance em toda a prateleira."""
    if portfolio is None:
        portfolio = PortfolioState()

    report = ComplianceReport(client=client)
    for product in products:
        verdict = check_product(product, client, portfolio)
        report.verdicts.append(verdict)

    return report
