"""Letters client — loads fund manager letters from YAML configs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).parent.parent.parent.parent / 'config'


@dataclass
class LetterView:
    """Single fund manager's view on markets."""

    source: str
    region: str  # 'BR' or 'US'
    date: str | None = None
    confidence: float = 0.7

    # Scores [-1, +1]: -1=bearish, 0=neutral, +1=bullish
    equities_us: float | None = None
    equities_intl: float | None = None
    equities_br: float | None = None
    bonds_br: float | None = None
    risk_level: str | None = None  # 'low', 'elevated', 'high'

    quotes: list[str] = field(default_factory=list)


@dataclass
class LettersConsensus:
    """Aggregated consensus across all fund managers."""

    n_sources: int = 0
    equities_us: float | None = None
    equities_intl: float | None = None
    bonds_br: float | None = None
    risk_level: str | None = None
    confidence: float = 0.5


SENTIMENT_SCORE = {
    'very_bullish': 1.0,
    'bullish': 0.5,
    'neutral': 0.0,
    'bearish': -0.5,
    'very_bearish': -1.0,
}

POSITION_SCORE = {
    'muito_comprado': 1.0,
    'comprado': 0.5,
    'neutro': 0.0,
    'vendido': -0.5,
    'muito_vendido': -1.0,
}


class LettersClient:
    """Loads and aggregates fund manager letter views."""

    def __init__(self, config_path: Path = CONFIG_PATH):
        self._path = config_path

    def load_us_letters(self) -> list[LetterView]:
        """Load US letters from most recent YAML."""
        yamls = sorted(self._path.glob('us_letters_*.yaml'), reverse=True)
        if not yamls:
            return []

        with open(yamls[0]) as f:
            data = yaml.safe_load(f)

        views = []
        for letter in data.get('letters', []):
            lv = letter.get('views', {})
            views.append(
                LetterView(
                    source=letter.get('source', '?'),
                    region='US',
                    date=letter.get('date'),
                    confidence=0.8,
                    equities_us=SENTIMENT_SCORE.get(lv.get('equities_us', ''), None),
                    equities_intl=SENTIMENT_SCORE.get(lv.get('equities_intl', ''), None),
                    risk_level=lv.get('risk_assessment'),
                    quotes=letter.get('quotes', [])[:2],
                )
            )
        return views

    def load_br_letters(self) -> list[LetterView]:
        """Load BR gestoras from YAML template."""
        path = self._path / 'cartas_gestoras_template.yaml'
        if not path.exists():
            return []

        with open(path) as f:
            data = yaml.safe_load(f)

        views = []
        for g in data.get('gestoras_brasil', []):
            pos = g.get('posicoes', {})
            # Skip empty entries
            if not g.get('carta_data'):
                continue

            views.append(
                LetterView(
                    source=g.get('nome', '?'),
                    region='BR',
                    date=g.get('carta_data'),
                    confidence=g.get('confianca', 0.7) or 0.7,
                    bonds_br=POSITION_SCORE.get(pos.get('renda_fixa_brasil', ''), None),
                    equities_br=POSITION_SCORE.get(pos.get('acoes_brasil', ''), None),
                    equities_us=POSITION_SCORE.get(pos.get('acoes_us', ''), None),
                    quotes=g.get('quotes', [])[:2],
                )
            )
        return views

    def load_all(self) -> list[LetterView]:
        """Load all letters (BR + US)."""
        return self.load_br_letters() + self.load_us_letters()

    def consensus(self) -> LettersConsensus:
        """Calculate weighted consensus from all sources."""
        views = self.load_all()
        if not views:
            return LettersConsensus()

        def _wavg(attr: str) -> float | None:
            vals = [(getattr(v, attr), v.confidence) for v in views if getattr(v, attr) is not None]
            if not vals:
                return None
            total_w = sum(w for _, w in vals)
            return sum(v * w for v, w in vals) / total_w if total_w else None

        risk_levels = [v.risk_level for v in views if v.risk_level]

        return LettersConsensus(
            n_sources=len(views),
            equities_us=_wavg('equities_us'),
            equities_intl=_wavg('equities_intl'),
            bonds_br=_wavg('bonds_br'),
            risk_level=max(set(risk_levels), key=risk_levels.count) if risk_levels else None,
            confidence=0.8 if len(views) >= 3 else 0.5,
        )
