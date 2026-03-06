"""CLI entry point: python -m osira"""

import sys

from dotenv import load_dotenv

from osira.agents.intelligence import IntelligenceAgent

load_dotenv()


def main():
    print('🧠 Osira Intelligence Agent')
    print('=' * 50)

    agent = IntelligenceAgent()
    briefing = agent.run()

    print(f'\n📅 {briefing.date}')
    print(f'📰 {briefing.n_articles_br} BR + {briefing.n_articles_intl} intl articles')
    print(f'📜 {briefing.n_letter_sources} letter sources')
    print(f'🤖 Model: {briefing.model}')
    print('\n' + '=' * 50)
    print(briefing.content)


if __name__ == '__main__':
    sys.exit(main() or 0)
