"""Intelligence agent — synthesizes news + letters into actionable briefings."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime

import anthropic

from osira.data.letters_client import LettersClient, LettersConsensus
from osira.data.news_client import Article, NewsClient

SYSTEM_PROMPT = """\
You are a senior macro strategist at a Brazilian wealth management firm.
Your job is to produce a concise daily market briefing for the advisory team.

Output language: Portuguese (BR).

Structure your briefing as:
1. **Macro Pulse** — 2-3 bullet points on the macro environment today (BR + global)
2. **Key Headlines** — Top 5 most relevant headlines with one-line commentary each
3. **Letters Consensus** — What the top fund managers think (bullish/bearish by asset class)
4. **Risk Monitor** — Key risks to watch (geopolitical, rates, FX, etc.)
5. **Score** — Overall market sentiment score from -10 (extreme fear) to +10 (extreme greed)

Be direct. No filler. Numbers and facts over opinions.\
"""


@dataclass
class DailyBriefing:
    """Output of the intelligence agent."""

    date: str
    content: str
    n_articles_br: int = 0
    n_articles_intl: int = 0
    n_letter_sources: int = 0
    model: str = ''


@dataclass
class IntelligenceAgent:
    """Consumes news + letters, produces daily briefing via Claude."""

    redis_url: str | None = None
    config_path: str | None = None
    model: str = 'claude-sonnet-4-5-20250929'
    _news: NewsClient = field(init=False, repr=False)
    _letters: LettersClient = field(init=False, repr=False)
    _llm: anthropic.Anthropic = field(init=False, repr=False)

    def __post_init__(self):
        self._news = NewsClient(self.redis_url)
        if self.config_path:
            from pathlib import Path

            self._letters = LettersClient(Path(self.config_path))
        else:
            self._letters = LettersClient()
        self._llm = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

    def run(self) -> DailyBriefing:
        """Run the full intelligence pipeline: gather → synthesize → output."""
        # 1. Gather
        br_articles = self._news.get_today_br()
        intl_articles = self._news.get_today_intl()
        consensus = self._letters.consensus()

        # 2. Build context
        context = self._build_context(br_articles, intl_articles, consensus)

        # 3. Synthesize via LLM
        response = self._llm.messages.create(
            model=self.model,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': context}],
        )

        content = response.content[0].text

        return DailyBriefing(
            date=datetime.now().strftime('%Y-%m-%d'),
            content=content,
            n_articles_br=len(br_articles),
            n_articles_intl=len(intl_articles),
            n_letter_sources=consensus.n_sources,
            model=self.model,
        )

    def _build_context(
        self,
        br: list[Article],
        intl: list[Article],
        consensus: LettersConsensus,
    ) -> str:
        """Build the user message with all gathered data."""
        parts = [f'Data: {datetime.now().strftime("%d/%m/%Y %H:%M")}']

        # News BR
        parts.append(f'\n## Notícias Brasil ({len(br)} artigos hoje)')
        for a in br[:20]:
            ts = a.date_published.strftime('%H:%M') if a.date_published else ''
            parts.append(f'- [{a.source}] {ts} | {a.title}')
            if a.summary:
                parts.append(f'  {a.summary[:200]}')

        # News Intl
        parts.append(f'\n## Notícias Internacional ({len(intl)} artigos hoje)')
        for a in intl[:20]:
            ts = a.date_published.strftime('%H:%M') if a.date_published else ''
            parts.append(f'- [{a.source}] {ts} | {a.title}')
            if a.summary:
                parts.append(f'  {a.summary[:200]}')

        # Letters consensus
        parts.append('\n## Consenso Cartas de Gestoras')
        parts.append(f'Fontes: {consensus.n_sources}')
        if consensus.equities_us is not None:
            parts.append(f'US Equities: {consensus.equities_us:+.2f} (-1=bear, +1=bull)')
        if consensus.equities_intl is not None:
            parts.append(f'Intl Equities: {consensus.equities_intl:+.2f}')
        if consensus.bonds_br is not None:
            parts.append(f'RF Brasil: {consensus.bonds_br:+.2f}')
        if consensus.risk_level:
            parts.append(f'Risk Level: {consensus.risk_level}')

        parts.append('\n---\nGere o briefing diário com base nas informações acima.')
        return '\n'.join(parts)
