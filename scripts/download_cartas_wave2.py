"""Wave 2: Download letters from additional gestoras.

Covers: Guepardo, Alaska, IP Capital, Squadra, Artica, Mar Asset,
Dynamo (fixed), Santander, SPX, Ibiuna, Bahia, Legacy (extended).
"""

import io
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

import requests
import urllib3

try:
    import pypdf
except ImportError:
    os.system(f'{sys.executable} -m pip install pypdf -q')
    import pypdf

try:
    from bs4 import BeautifulSoup
except ImportError:
    os.system(f'{sys.executable} -m pip install beautifulsoup4 -q')
    from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)
HEADERS = {'User-Agent': UA, 'Accept': '*/*'}

BASE_DIR = Path(__file__).parent.parent / 'data' / 'cartas'
DB_PATH = BASE_DIR / 'cartas.db'

session = requests.Session()
session.headers.update(HEADERS)


def init_db():
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
    return conn


def exists(conn, gestora, title):
    return (
        conn.execute(
            'SELECT 1 FROM letters WHERE gestora=? AND title=?', (gestora, title)
        ).fetchone()
        is not None
    )


def store(conn, d):
    if exists(conn, d['gestora'], d['title']):
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


def dl_pdf(url, dest, timeout=30, verify=True):
    try:
        r = session.get(url, timeout=timeout, stream=True, verify=verify)
        if r.status_code == 200 and len(r.content) > 1000:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            return True
    except Exception:
        pass
    return False


def pdf_text(path):
    try:
        reader = pypdf.PdfReader(str(path))
        return ' '.join(p.extract_text() or '' for p in reader.pages).strip()
    except Exception:
        return ''


def pdf_text_url(url, verify=True):
    try:
        r = session.get(url, timeout=30, verify=verify)
        r.raise_for_status()
        reader = pypdf.PdfReader(io.BytesIO(r.content))
        return ' '.join(p.extract_text() or '' for p in reader.pages).strip()
    except Exception:
        return ''


def parse(url, verify=True):
    try:
        r = session.get(url, timeout=15, verify=verify)
        return BeautifulSoup(r.content, 'html.parser')
    except Exception:
        return None


# =============================================================================
def scrape_guepardo(conn):
    print('\n[Guepardo] Scraping cartas-da-gestora...')
    g = 'Guepardo'
    dest = BASE_DIR / 'guepardo'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    soup = parse('https://www.guepardoinvest.com.br/cartas-da-gestora/')
    if not soup:
        print('  Failed to load page')
        return 0

    for a in soup.find_all('a', href=True):
        href = a['href']
        if '.pdf' not in href.lower():
            continue
        fname = href.split('/')[-1].split('?')[0]
        title = fname.replace('.pdf', '').replace('-', ' ').replace('_', ' ')
        if exists(conn, g, title):
            continue
        pdf_path = dest / fname
        if not pdf_path.exists():
            dl_pdf(href, pdf_path)
        if pdf_path.exists():
            store(
                conn,
                {
                    'gestora': g,
                    'title': title,
                    'date': '',
                    'url': href,
                    'content': pdf_text(pdf_path),
                    'pdf_path': str(pdf_path),
                },
            )
            count += 1
            print(f'  ✓ {fname}')
        time.sleep(0.5)
    print(f'[Guepardo] {count} cartas')
    return count


# =============================================================================
def scrape_alaska(conn):
    print('\n[Alaska] Scraping cartas...')
    g = 'Alaska'
    dest = BASE_DIR / 'alaska'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    soup = parse('https://www.alaska-asset.com.br/cartas/')
    if not soup:
        print('  Failed to load page')
        return 0

    for entry in soup.find_all('div', class_='entry'):
        title_div = entry.find('div', class_='title')
        body_div = entry.find('div', class_='body')
        if not title_div or not body_div:
            continue
        h3 = title_div.find('h3')
        title_text = h3.get_text(strip=True) if h3 else ''
        for a in body_div.find_all('a', href=True):
            href = a['href']
            if 'Mensais' in href or '.pdf' not in href.lower():
                continue
            body_text = a.get_text(strip=True)
            title = f'{title_text} - {body_text}'
            if exists(conn, g, title):
                continue
            fname = href.split('/')[-1].split('?')[0]
            pdf_path = dest / fname
            if not pdf_path.exists():
                dl_pdf(href, pdf_path)
            if pdf_path.exists():
                store(
                    conn,
                    {
                        'gestora': g,
                        'title': title,
                        'date': '',
                        'url': href,
                        'content': pdf_text(pdf_path),
                        'pdf_path': str(pdf_path),
                    },
                )
                count += 1
                print(f'  ✓ {fname}')
            time.sleep(0.5)
    print(f'[Alaska] {count} cartas')
    return count


# =============================================================================
def scrape_ip_capital(conn):
    print('\n[IP Capital] Scraping reports (paginated)...')
    g = 'IP Capital'
    dest = BASE_DIR / 'ip_capital'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    base = 'https://ip-capitalpartners.com/wp-content/themes/ip-capital/loop-reports.php'
    page = 1
    while True:
        url = f'{base}?paged={page}'
        soup = parse(url, verify=False)
        if not soup:
            break
        cards = soup.find_all('div', class_='card')
        if not cards:
            break
        for card in cards:
            h3 = card.find('h3')
            if not h3:
                continue
            a = h3.find('a')
            title_text = a.get_text(strip=True) if a else ''
            p = card.find('p')
            date_text = p.get_text(strip=True) if p else ''
            title = f'{title_text} ({date_text})'
            pdf_link = card.find('a', class_='btn-feature-download')
            if not pdf_link or not pdf_link['href'].endswith('.pdf'):
                continue
            href = pdf_link['href']
            if exists(conn, g, title):
                continue
            fname = href.split('/')[-1].split('?')[0]
            pdf_path = dest / fname
            if not pdf_path.exists():
                dl_pdf(href, pdf_path, verify=False)
            if pdf_path.exists():
                store(
                    conn,
                    {
                        'gestora': g,
                        'title': title,
                        'date': date_text,
                        'url': href,
                        'content': pdf_text(pdf_path),
                        'pdf_path': str(pdf_path),
                    },
                )
                count += 1
                print(f'  ✓ {fname}')
            time.sleep(0.5)
        load_more = soup.find('a', class_='load-more')
        if not load_more:
            break
        page += 1
    print(f'[IP Capital] {count} cartas')
    return count


# =============================================================================
def scrape_squadra(conn):
    print('\n[Squadra] Scraping cartas...')
    g = 'Squadra'
    dest = BASE_DIR / 'squadra'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    soup = parse('https://www.squadrainvest.com.br/cartas/')
    if not soup:
        print('  Failed to load page')
        return 0

    for a in soup.find_all('a', href=True):
        href = a['href']
        if '.pdf' not in href.lower():
            continue
        fname = href.split('/')[-1].split('?')[0]
        title = fname.replace('.pdf', '').replace('-', ' ').replace('_', ' ')
        if exists(conn, g, title):
            continue
        pdf_path = dest / fname
        if not pdf_path.exists():
            dl_pdf(href, pdf_path)
        if pdf_path.exists():
            store(
                conn,
                {
                    'gestora': g,
                    'title': title,
                    'date': '',
                    'url': href,
                    'content': pdf_text(pdf_path),
                    'pdf_path': str(pdf_path),
                },
            )
            count += 1
            print(f'  ✓ {fname}')
        time.sleep(0.5)
    print(f'[Squadra] {count} cartas')
    return count


# =============================================================================
def scrape_artica(conn):
    print('\n[Artica] Scraping cartas-asset...')
    g = 'Artica Capital'
    count = 0
    soup = parse('https://artica.capital/cartas-asset/')
    if not soup:
        print('  Failed to load page')
        return 0

    for item in soup.find_all('div', class_='jet-listing-grid__item'):
        time_tag = item.find('time')
        date_text = time_tag.get_text(strip=True) if time_tag else ''

        title_span = None
        for span in item.find_all('span', class_='jet-listing-dynamic-link__label'):
            if 'Ler mais' not in span.get_text():
                title_span = span
                break
        title = title_span.get_text(strip=True) if title_span else ''
        if not title or exists(conn, g, title):
            continue

        href = None
        for a in item.find_all('a', class_='jet-listing-dynamic-link__link', href=True):
            sp = a.find('span', class_='jet-listing-dynamic-link__label')
            if sp and 'Ler mais' in sp.get_text():
                href = a['href']
                break
        if not href:
            continue

        try:
            post_soup = parse(href)
            sections = post_soup.find_all('div', class_='elementor-section-wrap')
            text = sections[1].get_text(separator=' ', strip=True) if len(sections) > 1 else ''
        except Exception:
            text = ''

        store(conn, {'gestora': g, 'title': title, 'date': date_text, 'url': href, 'content': text})
        count += 1
        print(f'  ✓ {title[:60]}')
        time.sleep(1)

    print(f'[Artica] {count} cartas')
    return count


# =============================================================================
def scrape_mar_asset(conn):
    print('\n[Mar Asset] Scraping conteudo-mar...')
    g = 'Mar Asset'
    dest = BASE_DIR / 'mar_asset'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    soup = parse('https://www.marasset.com.br/conteudo-mar/')
    if not soup:
        print('  Failed to load page')
        return 0

    for div in soup.find_all('div', class_='document--term--item'):
        h4 = div.find('h4')
        if not h4 or 'Cartas' != h4.get_text(strip=True):
            continue
        for media in div.find_all('div', class_='media'):
            a = media.find('a', href=True)
            if not a:
                continue
            href = a['href']
            title = a.get('title', '').strip() or href.split('/')[-1]
            if exists(conn, g, title):
                continue
            fname = href.split('/')[-1].split('?')[0]
            if not fname.endswith('.pdf'):
                fname += '.pdf'
            pdf_path = dest / fname
            if not pdf_path.exists():
                dl_pdf(href, pdf_path)
            if pdf_path.exists():
                store(
                    conn,
                    {
                        'gestora': g,
                        'title': title,
                        'date': '',
                        'url': href,
                        'content': pdf_text(pdf_path),
                        'pdf_path': str(pdf_path),
                    },
                )
                count += 1
                print(f'  ✓ {fname}')
            time.sleep(0.5)
    print(f'[Mar Asset] {count} cartas')
    return count


# =============================================================================
def scrape_dynamo_v2(conn):
    print('\n[Dynamo v2] Scraping cartas-dynamo...')
    g = 'Dynamo'
    dest = BASE_DIR / 'dynamo'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    page = 1
    while page <= 15:
        url = 'https://www.dynamo.com.br/pt/cartas-dynamo'
        if page > 1:
            url += f'?page={page}'
        soup = parse(url)
        if not soup:
            break

        # Try multiple CSS selectors since site may have changed
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/pdf/' in href or href.endswith('.pdf'):
                if not href.startswith('http'):
                    href = 'https://www.dynamo.com.br' + href
                links.append((a.get_text(strip=True) or href.split('/')[-1], href))

        if not links:
            # Try finding PDF links in any container
            for a in soup.find_all('a', href=re.compile(r'\.pdf|/pdf/')):
                href = a['href']
                if not href.startswith('http'):
                    href = 'https://www.dynamo.com.br' + href
                links.append((a.get_text(strip=True) or href.split('/')[-1], href))

        if not links:
            break

        for title, href in links:
            if exists(conn, g, title):
                continue
            fname = href.split('/')[-1].split('?')[0]
            if not fname.endswith('.pdf'):
                fname = f'dynamo_{title.replace(" ", "_")[:50]}.pdf'
            pdf_path = dest / fname
            if not pdf_path.exists():
                dl_pdf(href, pdf_path)
            if pdf_path.exists():
                store(
                    conn,
                    {
                        'gestora': g,
                        'title': title,
                        'date': '',
                        'url': href,
                        'content': pdf_text(pdf_path),
                        'pdf_path': str(pdf_path),
                    },
                )
                count += 1
                print(f'  ✓ {fname}')
            time.sleep(1)
        page += 1
        time.sleep(2)

    print(f'[Dynamo v2] {count} cartas')
    return count


# =============================================================================
def scrape_santander(conn):
    print('\n[Santander Asset] Scraping carta-mensal...')
    g = 'Santander Asset'
    dest = BASE_DIR / 'santander'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    soup = parse('https://www.santanderassetmanagement.com.br/conteudos/carta-mensal')
    if not soup:
        print('  Failed to load page')
        return 0

    for a in soup.find_all('a', href=True):
        href = a['href']
        if '.pdf' not in href.lower():
            continue
        if not href.startswith('http'):
            href = 'https://www.santanderassetmanagement.com.br' + href
        fname = href.split('/')[-1].split('?')[0]
        title = fname.replace('.pdf', '').replace('-', ' ').replace('_', ' ')
        if exists(conn, g, title):
            continue
        pdf_path = dest / fname
        if not pdf_path.exists():
            dl_pdf(href, pdf_path)
        if pdf_path.exists():
            store(
                conn,
                {
                    'gestora': g,
                    'title': title,
                    'date': '',
                    'url': href,
                    'content': pdf_text(pdf_path),
                    'pdf_path': str(pdf_path),
                },
            )
            count += 1
            print(f'  ✓ {fname}')
        time.sleep(0.5)
    print(f'[Santander Asset] {count} cartas')
    return count


# =============================================================================
def scrape_spx(conn):
    print('\n[SPX Capital] Tentando URLs previsíveis...')
    g = 'SPX Capital'
    dest = BASE_DIR / 'spx'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    # Try scraping the category pages
    categories = [
        'https://www.spxcapital.com.br/category/macro/',
        'https://www.spxcapital.com.br/category/credito/',
        'https://www.spxcapital.com.br/category/previdencia/',
    ]
    for cat_url in categories:
        soup = parse(cat_url)
        if not soup:
            continue
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '.pdf' not in href.lower():
                continue
            if not href.startswith('http'):
                href = 'https://www.spxcapital.com.br' + href
            fname = href.split('/')[-1].split('?')[0]
            title = fname.replace('.pdf', '').replace('-', ' ').replace('_', ' ')
            if exists(conn, g, title):
                continue
            pdf_path = dest / fname
            if not pdf_path.exists():
                dl_pdf(href, pdf_path)
            if pdf_path.exists():
                store(
                    conn,
                    {
                        'gestora': g,
                        'title': title,
                        'date': '',
                        'url': href,
                        'content': pdf_text(pdf_path),
                        'pdf_path': str(pdf_path),
                    },
                )
                count += 1
                print(f'  ✓ {fname}')
            time.sleep(0.5)

    # Also try wap subdomain patterns
    for year in range(2020, 2027):
        for month in range(1, 13):
            if year == 2026 and month > 3:
                break
            patterns = [
                f'https://wap.spxcapital.com.br/wp-content/uploads/{year}/{month:02d}/',
            ]
            for pat in patterns:
                soup = parse(pat)
                if not soup:
                    continue
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if '.pdf' in href.lower():
                        full = pat + href if not href.startswith('http') else href
                        fname = full.split('/')[-1]
                        title = f'SPX {fname.replace(".pdf", "")}'
                        if exists(conn, g, title):
                            continue
                        pdf_path = dest / fname
                        if not pdf_path.exists():
                            dl_pdf(full, pdf_path)
                        if pdf_path.exists():
                            store(
                                conn,
                                {
                                    'gestora': g,
                                    'title': title,
                                    'date': f'{year}-{month:02d}',
                                    'url': full,
                                    'content': pdf_text(pdf_path),
                                    'pdf_path': str(pdf_path),
                                },
                            )
                            count += 1
                            print(f'  ✓ {fname}')
            time.sleep(0.3)

    print(f'[SPX Capital] {count} cartas')
    return count


# =============================================================================
def scrape_ibiuna(conn):
    print('\n[Ibiuna] Tentando URLs de relatórios...')
    g = 'Ibiuna'
    dest = BASE_DIR / 'ibiuna'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    funds = [
        'IbiunaHedgeSTHFICFIM',
        'IbiunaHedgeFICFIM',
        'IbiunaLongShortSTHFICFIM',
        'IbiunaEquityHedgeFICFIM',
    ]
    for fund in funds:
        url = (
            f'https://www.ibiunainvest.com.br/wp-content/uploads/fundos/RelatorioMensal_{fund}.pdf'
        )
        fname = f'ibiuna_{fund}_latest.pdf'
        title = f'Ibiuna {fund} - Latest'
        if exists(conn, g, title):
            continue
        pdf_path = dest / fname
        if dl_pdf(url, pdf_path):
            store(
                conn,
                {
                    'gestora': g,
                    'title': title,
                    'date': '',
                    'url': url,
                    'content': pdf_text(pdf_path),
                    'pdf_path': str(pdf_path),
                },
            )
            count += 1
            print(f'  ✓ {fname}')

    # Try WordPress upload patterns
    for year in range(2020, 2027):
        for month in range(1, 13):
            if year == 2026 and month > 3:
                break
            patterns = [
                f'https://www.ibiunainvest.com.br/wp-content/uploads/{year}/{month:02d}/',
            ]
            for pat in patterns:
                soup = parse(pat)
                if not soup:
                    continue
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if '.pdf' in href.lower() and 'relatorio' in href.lower():
                        full = pat + href if not href.startswith('http') else href
                        fname = full.split('/')[-1]
                        title = f'Ibiuna {fname.replace(".pdf", "")}'
                        if exists(conn, g, title):
                            continue
                        pdf_path = dest / fname
                        if dl_pdf(full, pdf_path):
                            store(
                                conn,
                                {
                                    'gestora': g,
                                    'title': title,
                                    'date': f'{year}-{month:02d}',
                                    'url': full,
                                    'content': pdf_text(pdf_path),
                                    'pdf_path': str(pdf_path),
                                },
                            )
                            count += 1
                            print(f'  ✓ {fname}')
            time.sleep(0.3)

    print(f'[Ibiuna] {count} cartas')
    return count


# =============================================================================
def scrape_legacy_extended(conn):
    print('\n[Legacy Extended] Tentando mais patterns...')
    g = 'Legacy Capital'
    dest = BASE_DIR / 'legacy'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    months_pt = {
        1: 'Janeiro',
        2: 'Fevereiro',
        3: 'Marco',
        4: 'Abril',
        5: 'Maio',
        6: 'Junho',
        7: 'Julho',
        8: 'Agosto',
        9: 'Setembro',
        10: 'Outubro',
        11: 'Novembro',
        12: 'Dezembro',
    }

    for year in range(2018, 2027):
        for month in range(1, 13):
            if year == 2026 and month > 3:
                break
            ym = f'{year}{month:02d}'
            title = f'Legacy Capital - Carta {year}-{month:02d}'
            if exists(conn, g, title):
                continue

            patterns = [
                f'https://www.legacycapital.com.br/wp-content/uploads/{ym}_Legacy_Capital.pdf',
                f'https://www.legacycapital.com.br/wp-content/uploads/{ym}_Carta-Mensal.pdf',
                f'https://www.legacycapital.com.br/wp-content/uploads/carta_mensal_{year}_{month:02d}.pdf',
                f'https://www.legacycapital.com.br/wp-content/uploads/{year}/{month:02d}/Carta-Mensal-{months_pt[month]}-{year}.pdf',
                f'https://www.legacycapital.com.br/wp-content/uploads/{year}/{month:02d}/Legacy-Carta-Mensal.pdf',
                f'https://legacywebsite.blob.core.windows.net/site/cartamensal/{year}/{ym}_Carta%20Mensal.pdf',
                f'https://legacywebsite.blob.core.windows.net/site/cartamensal/{year}/{ym}_Legacy_Capital.pdf',
            ]
            for url in patterns:
                fname = f'legacy_{ym}.pdf'
                pdf_path = dest / fname
                if pdf_path.exists():
                    store(
                        conn,
                        {
                            'gestora': g,
                            'title': title,
                            'date': f'{year}-{month:02d}',
                            'url': url,
                            'content': pdf_text(pdf_path),
                            'pdf_path': str(pdf_path),
                        },
                    )
                    count += 1
                    break
                if dl_pdf(url, pdf_path):
                    store(
                        conn,
                        {
                            'gestora': g,
                            'title': title,
                            'date': f'{year}-{month:02d}',
                            'url': url,
                            'content': pdf_text(pdf_path),
                            'pdf_path': str(pdf_path),
                        },
                    )
                    count += 1
                    print(f'  ✓ legacy_{ym}.pdf')
                    break
            time.sleep(0.3)

    print(f'[Legacy Extended] {count} novas cartas')
    return count


# =============================================================================
def main():
    print('=' * 60)
    print('OSIRA - Download Cartas Wave 2')
    print('=' * 60)

    BASE_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / 'santander').mkdir(exist_ok=True)
    conn = init_db()

    total = 0
    scrapers = [
        scrape_guepardo,
        scrape_alaska,
        scrape_ip_capital,
        scrape_squadra,
        scrape_artica,
        scrape_mar_asset,
        scrape_dynamo_v2,
        scrape_santander,
        scrape_spx,
        scrape_ibiuna,
        scrape_legacy_extended,
    ]

    for fn in scrapers:
        try:
            n = fn(conn)
            total += n
        except Exception as e:
            print(f'  ERROR in {fn.__name__}: {e}')
            import traceback

            traceback.print_exc()

    cur = conn.execute(
        'SELECT gestora, COUNT(*) FROM letters GROUP BY gestora ORDER BY COUNT(*) DESC'
    )
    print('\n' + '=' * 60)
    print('RESUMO TOTAL (wave 1 + wave 2)')
    print('=' * 60)
    for row in cur:
        print(f'  {row[0]}: {row[1]} cartas')
    t = conn.execute('SELECT COUNT(*) FROM letters').fetchone()[0]
    print(f'\nTotal geral: {t} cartas')
    print(f'Novas nesta wave: {total}')
    conn.close()


if __name__ == '__main__':
    main()
