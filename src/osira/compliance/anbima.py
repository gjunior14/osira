"""
Tabelas de score de risco ANBIMA.

Fonte: ANBIMA Regras e Procedimentos do Código de Distribuição (Nov 2023),
Art. 15, 19, 20, 21.

Escala: 0.50 (menor risco) a 5.00 (maior risco), incrementos de 0.25.
"""

from dataclasses import dataclass

# ── Perfis de investidor (Art. 15) ──────────────────────────────

PROFILE_MAX_SCORE: dict[str, float] = {
    'conservador': 1.5,
    'moderado': 3.0,
    'arrojado': 5.0,
}

# ── Scores mínimos por produto (Art. 20) ────────────────────────
# Chave: (instrumento, ig_or_not, indexador_tipo)
# Valor: dict de maturity_bucket → score
# ig = investment grade (≥ BBB- local)

# Maturity buckets usados pela ANBIMA (em anos de prazo/duration)
# ≤2, 2-4, 4-6, 6-8, >8


@dataclass(frozen=True)
class ScoreKey:
    instrument: str  # "gov", "bank", "corp", "equity", "fund", etc.
    is_ig: bool
    rate_type: str  # "pos", "pre"


SCORE_TABLE: dict[ScoreKey, dict[str, float]] = {
    # ── Títulos Públicos ──
    ScoreKey('gov', True, 'pos'): {
        'ultracurto': 0.50,
        'curto': 0.50,
        'medio': 0.50,
        'longo': 0.50,
        'muito_longo': 0.50,
    },
    ScoreKey('gov', True, 'pre'): {
        'ultracurto': 1.00,
        'curto': 1.00,
        'medio': 1.75,
        'longo': 1.75,
        'muito_longo': 2.75,
    },
    # ── Bancários Investment Grade ──
    ScoreKey('bank', True, 'pos'): {
        'ultracurto': 0.75,
        'curto': 0.75,
        'medio': 1.00,
        'longo': 1.25,
        'muito_longo': 2.00,
    },
    ScoreKey('bank', True, 'pre'): {
        'ultracurto': 1.00,
        'curto': 1.00,
        'medio': 1.50,
        'longo': 2.00,
        'muito_longo': 3.00,
    },
    # ── Bancários Non-IG ──
    ScoreKey('bank', False, 'pos'): {
        'ultracurto': 1.75,
        'curto': 1.75,
        'medio': 2.00,
        'longo': 2.25,
        'muito_longo': 3.00,
    },
    ScoreKey('bank', False, 'pre'): {
        'ultracurto': 2.00,
        'curto': 2.00,
        'medio': 2.25,
        'longo': 2.75,
        'muito_longo': 4.00,
    },
    # ── Corporativos (Debênture/CRI/CRA) Investment Grade ──
    ScoreKey('corp', True, 'pos'): {
        'ultracurto': 1.00,
        'curto': 1.00,
        'medio': 1.25,
        'longo': 1.75,
        'muito_longo': 2.75,
    },
    ScoreKey('corp', True, 'pre'): {
        'ultracurto': 1.25,
        'curto': 1.25,
        'medio': 1.75,
        'longo': 2.25,
        'muito_longo': 3.50,
    },
    # ── Corporativos Non-IG / Sem Rating ──
    ScoreKey('corp', False, 'pos'): {
        'ultracurto': 3.50,
        'curto': 3.50,
        'medio': 3.50,
        'longo': 3.50,
        'muito_longo': 3.50,
    },
    ScoreKey('corp', False, 'pre'): {
        'ultracurto': 4.25,
        'curto': 4.25,
        'medio': 4.25,
        'longo': 4.25,
        'muito_longo': 4.25,
    },
}

# ── Scores fixos para produtos sem tabela de prazo ──────────────

FIXED_SCORES: dict[str, float] = {
    'acao': 4.00,
    'bdr': 4.00,
    'derivativo': 4.00,
    'fundo_rf_cdi': 0.50,
    'fundo_rf_simples': 0.50,
    'fundo_rf_dur_baixa_soberano': 1.00,
    'fundo_rf_dur_baixa_ig': 1.00,
    'fundo_rf_dur_baixa_livre': 1.25,
    'fundo_rf_dur_media_soberano': 1.50,
    'fundo_rf_dur_alta_livre': 2.00,
    'fundo_rf_divida_externa': 3.00,
    'fundo_mm_capital_protegido': 1.50,
    'fundo_mm_macro': 2.50,
    'fundo_mm_trading': 2.50,
    'fundo_mm_balanceado': 2.50,
    'fundo_acoes': 3.50,
    'fundo_acoes_mono': 4.00,
    'fii_renda_ativa': 3.00,
    'fii_renda_passiva': 3.50,
    'fii_incorporacao': 4.50,
    'fip': 4.50,
    'cambial': 3.00,
    'fundo_rf_exterior': 3.00,
    'fundo_acoes_exterior': 3.50,
    'etf_rf': 1.00,
    'etf_rv': 3.50,
    'coe': 1.50,
    'cripto': 5.00,
}

# ── Ajustes de liquidez (Art. 21-I) ────────────────────────────

LIQUIDITY_ADJUSTMENTS: list[tuple[int, float]] = [
    (90, 0.50),  # resgate > D+90
    (30, 0.25),  # resgate > D+30
]


def calc_anbima_score(
    instrument: str,
    is_ig: bool,
    rate_type: str,
    maturity_bucket: str,
    redemption_days: int = 0,
) -> float:
    """Calcula o score de risco ANBIMA para um produto.

    Para ações, FIIs, fundos e derivativos, usa FIXED_SCORES.
    Para RF (gov/bank/corp), usa SCORE_TABLE por prazo.
    Aplica ajuste de liquidez se resgate > D+30.
    """
    if instrument in FIXED_SCORES:
        base = FIXED_SCORES[instrument]
    else:
        key = ScoreKey(instrument, is_ig, rate_type)
        bucket_scores = SCORE_TABLE.get(key)
        if bucket_scores is None:
            return 5.0
        base = bucket_scores.get(maturity_bucket, 5.0)

    for threshold, adj in LIQUIDITY_ADJUSTMENTS:
        if redemption_days > threshold:
            base += adj
            break

    return min(base, 5.0)


def is_suitable(score: float, profile: str) -> bool:
    max_score = PROFILE_MAX_SCORE.get(profile.lower(), 0)
    return score <= max_score
