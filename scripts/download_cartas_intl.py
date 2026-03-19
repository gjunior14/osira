"""Download international fund manager letters for backtesting.

Covers: Hussman (weekly since 2016), GMO (quarterly), PIMCO (Wayback), more Oaktree.
"""

import os
import sqlite3
import sys
import time
from pathlib import Path

import requests
import urllib3

try:
    from bs4 import BeautifulSoup
except ImportError:
    os.system(f'{sys.executable} -m pip install beautifulsoup4 -q')
    from bs4 import BeautifulSoup

urllib3.disable_warnings()

session = requests.Session()
session.headers.update(
    {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        ),
    }
)

DB_PATH = Path('data/cartas/cartas.db')
conn = sqlite3.connect(str(DB_PATH))
conn.execute("""
    CREATE TABLE IF NOT EXISTS letters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gestora TEXT, title TEXT, date TEXT,
        url TEXT, content TEXT, pdf_path TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()


def exists(g, t):
    return (
        conn.execute('SELECT 1 FROM letters WHERE gestora=? AND title=?', (g, t)).fetchone()
        is not None
    )


def store(d):
    if exists(d['gestora'], d['title']):
        return False
    conn.execute(
        'INSERT INTO letters (gestora,title,date,url,content,pdf_path) VALUES(?,?,?,?,?,?)',
        (
            d['gestora'],
            d['title'],
            d['date'],
            d['url'],
            d.get('content', ''),
            d.get('pdf_path', ''),
        ),
    )
    conn.commit()
    return True


def fetch(url, timeout=15):
    try:
        r = session.get(url, timeout=timeout)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, 'html.parser')
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            return soup.get_text(separator=' ', strip=True)[:15000]
    except Exception:
        pass
    return ''


# =============================================
# HUSSMAN - Monthly sample 2016-2026
# =============================================
print('[Hussman] Weekly market comments (1/month, 2016-2026)...')
g = 'Hussman Funds'
count = 0

for year in range(2016, 2027):
    yy = str(year)[2:]
    for month in range(1, 13):
        if year == 2026 and month > 3:
            break
        for day in [15, 10, 20, 5, 25, 1, 8, 22]:
            slug = f'mc{yy}{month:02d}{day:02d}'
            title = f'Hussman Weekly {year}-{month:02d}-{day:02d}'
            if exists(g, title):
                break
            url = f'https://www.hussmanfunds.com/comment/{slug}/'
            text = fetch(url)
            if text and len(text) > 2000:
                store(
                    {
                        'gestora': g,
                        'title': title,
                        'date': f'{year}-{month:02d}',
                        'url': url,
                        'content': text,
                    }
                )
                count += 1
                print(f'  ✓ {year}-{month:02d} | {slug}')
                break
        time.sleep(0.3)

print(f'[Hussman] {count} comments\n')


# =============================================
# GMO - Quarterly letters & forecasts
# =============================================
print('[GMO expanded] Quarterly letters & forecasts...')
g = 'GMO'
count = 0

gmo_slugs = []
for year in range(2016, 2026):
    for q in range(1, 5):
        gmo_slugs.append(
            (f'{q}q-{year}-gmo-quarterly-letter_gmoquarterlyletter', f'{year}-{q * 3:02d}')
        )
        gmo_slugs.append((f'gmo-7-year-asset-class-forecast-{q}q-{year}', f'{year}-{q * 3:02d}'))

for slug, date_str in gmo_slugs:
    title = slug.replace('-', ' ').replace('_', ' ').title()[:80]
    if exists(g, title):
        continue
    url = f'https://www.gmo.com/americas/research-library/{slug}/'
    text = fetch(url)
    if text and len(text) > 1000:
        store({'gestora': g, 'title': title, 'date': date_str, 'url': url, 'content': text})
        count += 1
        print(f'  ✓ {date_str} | {title[:60]}')
    time.sleep(0.8)

print(f'[GMO expanded] {count} more\n')


# =============================================
# PIMCO via Wayback Machine
# =============================================
print('[PIMCO] Cyclical outlooks via Wayback...')
g = 'PIMCO'
count = 0

pimco = [
    ('navigating-uncertainty', '2026-01'),
    ('easing-into-an-uncertain-landing', '2024-10'),
    ('post-peak-macro-policy', '2024-06'),
    ('navigating-the-descent', '2024-01'),
    ('shifting-rate-expectations-create-opportunities-for-bonds', '2023-10'),
    ('fractured-markets-strong-bonds', '2023-06'),
    ('strained-markets-strong-bonds', '2023-01'),
    ('prevailing-under-pressure', '2022-10'),
    ('recession-risk-rises', '2022-06'),
    ('starting-to-wobble', '2022-01'),
    ('inflation-inflection', '2021-06'),
    ('setting-the-stage', '2021-01'),
    ('from-hurting-to-healing', '2020-06'),
    ('window-of-weakness', '2020-01'),
    ('growing-risks', '2019-06'),
    ('synching-lower', '2019-01'),
    ('the-road-ahead', '2018-06'),
    ('growing-but-slowing', '2018-01'),
    ('eyes-on-the-horizon', '2017-06'),
    ('global-growth-edge', '2017-01'),
]

for slug, date_str in pimco:
    title = f'PIMCO Cyclical - {slug.replace("-", " ").title()}'
    if exists(g, title):
        continue
    base = 'https://www.pimco.com/en-us/insights/economic-and-market-commentary/cyclical-outlook'
    wb = f'https://web.archive.org/web/2024/{base}/{slug}'
    text = fetch(wb, timeout=20)
    if not text or len(text) < 1000:
        text = fetch(f'{base}/{slug}', timeout=20)
    if text and len(text) > 1000:
        store({'gestora': g, 'title': title, 'date': date_str, 'url': wb, 'content': text})
        count += 1
        print(f'  ✓ {date_str} | {slug}')
    time.sleep(1)

print(f'[PIMCO] {count} outlooks\n')


# =============================================
# SUMMARY
# =============================================
cur = conn.execute('SELECT gestora, COUNT(*) FROM letters GROUP BY gestora ORDER BY COUNT(*) DESC')
print('=' * 60)
print('RESUMO TOTAL')
print('=' * 60)
for row in cur:
    print(f'  {row[0]}: {row[1]}')
t = conn.execute('SELECT COUNT(*) FROM letters').fetchone()[0]
print(f'\nTotal geral: {t}')

intl = conn.execute("""
    SELECT gestora, COUNT(*) FROM letters
    WHERE gestora IN ('Oaktree Capital','GMO','AQR','BlackRock',
                      'Bridgewater','PIMCO','Hussman Funds')
    GROUP BY gestora ORDER BY COUNT(*) DESC
""").fetchall()
print('\n--- INTERNACIONAIS ---')
for row in intl:
    print(f'  {row[0]}: {row[1]}')
print(f'Total intl: {sum(r[1] for r in intl)}')
conn.close()
