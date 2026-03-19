"""Download historical gestora letters from multiple sources.

Combines Ian Araujo's scraper framework with direct URL enumeration
for gestoras with predictable PDF patterns.
"""

import io
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

import requests

# PDF extraction
try:
    import pypdf
except ImportError:
    print('Installing pypdf...')
    os.system(f'{sys.executable} -m pip install pypdf -q')
    import pypdf

try:
    from bs4 import BeautifulSoup
except ImportError:
    print('Installing beautifulsoup4...')
    os.system(f'{sys.executable} -m pip install beautifulsoup4 -q')
    from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

BASE_DIR = Path(__file__).parent.parent / 'data' / 'cartas'
DB_PATH = BASE_DIR / 'cartas.db'

session = requests.Session()
session.headers.update(HEADERS)


def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS letters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gestora TEXT,
            title TEXT,
            date TEXT,
            url TEXT,
            content TEXT,
            pdf_path TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def letter_exists(conn, gestora, title):
    cur = conn.execute('SELECT id FROM letters WHERE gestora=? AND title=?', (gestora, title))
    return cur.fetchone() is not None


def store_letter(conn, letter):
    if letter_exists(conn, letter['gestora'], letter['title']):
        return False
    conn.execute(
        'INSERT INTO letters (gestora, title, date, url, content, pdf_path) VALUES (?,?,?,?,?,?)',
        (
            letter['gestora'],
            letter['title'],
            letter['date'],
            letter['url'],
            letter.get('content', ''),
            letter.get('pdf_path', ''),
        ),
    )
    conn.commit()
    return True


def download_pdf(url, dest_path, timeout=30):
    try:
        r = session.get(url, timeout=timeout, stream=True)
        if r.status_code == 200 and len(r.content) > 1000:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(r.content)
            return True
    except Exception:
        pass
    return False


def extract_text_from_pdf(pdf_path_or_bytes):
    try:
        if isinstance(pdf_path_or_bytes, (str, Path)):
            reader = pypdf.PdfReader(str(pdf_path_or_bytes))
        else:
            reader = pypdf.PdfReader(io.BytesIO(pdf_path_or_bytes))
        return ' '.join(p.extract_text() or '' for p in reader.pages).strip()
    except Exception:
        return ''


# =============================================================================
# VERDE ASSET - Predictable URL pattern
# =============================================================================
def scrape_verde(conn):
    print('\n[Verde Asset] Tentando URLs previsíveis...')
    gestora = 'Verde Asset'
    dest = BASE_DIR / 'verde'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    fund_ids = {
        '158094': 'Verde',
        '118': 'Acoes',
    }

    for fund_id, fund_name in fund_ids.items():
        for year in range(2016, 2027):
            for month in range(1, 13):
                if year == 2026 and month > 3:
                    break
                date_str = f'{year}_{month:02d}'
                fname = f'{fund_name}-REL-{date_str}.pdf'
                url = f'https://www.verdeasset.com.br/public/files/rel_gestao/{fund_id}/{fname}'
                pdf_path = dest / fname
                title = f'{fund_name} - Relatório {year}-{month:02d}'

                if letter_exists(conn, gestora, title):
                    continue
                if pdf_path.exists():
                    text = extract_text_from_pdf(pdf_path)
                    store_letter(
                        conn,
                        {
                            'gestora': gestora,
                            'title': title,
                            'date': f'{year}-{month:02d}',
                            'url': url,
                            'content': text,
                            'pdf_path': str(pdf_path),
                        },
                    )
                    count += 1
                    continue

                if download_pdf(url, pdf_path):
                    text = extract_text_from_pdf(pdf_path)
                    store_letter(
                        conn,
                        {
                            'gestora': gestora,
                            'title': title,
                            'date': f'{year}-{month:02d}',
                            'url': url,
                            'content': text,
                            'pdf_path': str(pdf_path),
                        },
                    )
                    count += 1
                    print(f'  ✓ {fname}')
                time.sleep(0.5)

    print(f'[Verde Asset] {count} cartas baixadas')
    return count


# =============================================================================
# LEGACY CAPITAL - WordPress predictable URLs
# =============================================================================
def scrape_legacy(conn):
    print('\n[Legacy Capital] Tentando URLs previsíveis...')
    gestora = 'Legacy Capital'
    dest = BASE_DIR / 'legacy'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    patterns = [
        'https://www.legacycapital.com.br/wp-content/uploads/{ym}_Legacy_Capital.pdf',
        'https://www.legacycapital.com.br/wp-content/uploads/{ym}_Carta-Mensal.pdf',
        'https://legacywebsite.blob.core.windows.net/site/cartamensal/{y}/{ym}_Carta%20Mensal.pdf',
    ]

    for year in range(2017, 2027):
        for month in range(1, 13):
            if year == 2026 and month > 3:
                break
            ym = f'{year}{month:02d}'
            title = f'Legacy Capital - Carta {year}-{month:02d}'
            if letter_exists(conn, gestora, title):
                continue

            for pat in patterns:
                url = pat.format(ym=ym, y=year)
                fname = f'legacy_{ym}.pdf'
                pdf_path = dest / fname

                if pdf_path.exists():
                    text = extract_text_from_pdf(pdf_path)
                    store_letter(
                        conn,
                        {
                            'gestora': gestora,
                            'title': title,
                            'date': f'{year}-{month:02d}',
                            'url': url,
                            'content': text,
                            'pdf_path': str(pdf_path),
                        },
                    )
                    count += 1
                    break

                if download_pdf(url, pdf_path):
                    text = extract_text_from_pdf(pdf_path)
                    store_letter(
                        conn,
                        {
                            'gestora': gestora,
                            'title': title,
                            'date': f'{year}-{month:02d}',
                            'url': url,
                            'content': text,
                            'pdf_path': str(pdf_path),
                        },
                    )
                    count += 1
                    print(f'  ✓ {fname}')
                    break
            time.sleep(0.5)

    print(f'[Legacy Capital] {count} cartas baixadas')
    return count


# =============================================================================
# KINEA - WordPress blog + PDFs
# =============================================================================
def scrape_kinea(conn):
    print('\n[Kinea] Scraping blog archive...')
    gestora = 'Kinea'
    dest = BASE_DIR / 'kinea'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    fund_names = ['Atlas-II', 'Chronos', 'IPV', 'KNCR', 'KFOF', 'Kan']

    for fund in fund_names:
        for year in range(2018, 2027):
            for month in range(1, 13):
                if year == 2026 and month > 3:
                    break
                patterns = [
                    f'https://www.kinea.com.br/wp-content/uploads/{year}/{month:02d}/Carta-do-Gestor-{fund}-Geral-Sub-I-{year}-{month:02d}.pdf',
                    f'https://www.kinea.com.br/wp-content/uploads/{year}/{month:02d}/Carta-do-Gestor-{fund}-{year}-{month:02d}.pdf',
                    f'https://www.kinea.com.br/wp-content/uploads/{year}/{month:02d}/{fund}_Carta-do-Gestor_{month:02d}-{year}.pdf',
                ]
                title = f'Kinea {fund} - Carta {year}-{month:02d}'
                if letter_exists(conn, gestora, title):
                    continue

                for url in patterns:
                    fname = f'kinea_{fund}_{year}{month:02d}.pdf'
                    pdf_path = dest / fname
                    if pdf_path.exists():
                        text = extract_text_from_pdf(pdf_path)
                        store_letter(
                            conn,
                            {
                                'gestora': gestora,
                                'title': title,
                                'date': f'{year}-{month:02d}',
                                'url': url,
                                'content': text,
                                'pdf_path': str(pdf_path),
                            },
                        )
                        count += 1
                        break
                    if download_pdf(url, pdf_path):
                        text = extract_text_from_pdf(pdf_path)
                        store_letter(
                            conn,
                            {
                                'gestora': gestora,
                                'title': title,
                                'date': f'{year}-{month:02d}',
                                'url': url,
                                'content': text,
                                'pdf_path': str(pdf_path),
                            },
                        )
                        count += 1
                        print(f'  ✓ {fname}')
                        break
                time.sleep(0.3)

    print(f'[Kinea] {count} cartas baixadas')
    return count


# =============================================================================
# DYNAMO - Paginated archive
# =============================================================================
def scrape_dynamo(conn):
    print('\n[Dynamo] Scraping paginated archive...')
    gestora = 'Dynamo'
    dest = BASE_DIR / 'dynamo'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    page = 1
    while True:
        url = 'https://www.dynamo.com.br/pt/cartas-dynamo'
        if page > 1:
            url += f'?page={page}'

        try:
            resp = session.get(url, timeout=15)
            soup = BeautifulSoup(resp.content, 'html.parser')
        except Exception as e:
            print(f'  Error on page {page}: {e}')
            break

        items = soup.find_all('div', class_='block')
        if not items:
            break

        for item in items:
            try:
                span = item.find('span', class_='carta-n')
                if not span:
                    continue
                a = span.find('a')
                if not a:
                    continue
                pdf_url = 'https://www.dynamo.com.br' + a['href']
                h3 = item.find('h3')
                title = h3.get_text(strip=True) if h3 else a.get_text(strip=True)

                if letter_exists(conn, gestora, title):
                    continue

                fname = pdf_url.split('/')[-1]
                if not fname.endswith('.pdf'):
                    fname = f'dynamo_{title.replace(" ", "_")}.pdf'
                pdf_path = dest / fname

                if not pdf_path.exists():
                    download_pdf(pdf_url, pdf_path)

                if pdf_path.exists():
                    text = extract_text_from_pdf(pdf_path)
                    date_match = re.search(r'(\d{4})', title)
                    date_str = date_match.group(1) if date_match else ''
                    store_letter(
                        conn,
                        {
                            'gestora': gestora,
                            'title': title,
                            'date': date_str,
                            'url': pdf_url,
                            'content': text,
                            'pdf_path': str(pdf_path),
                        },
                    )
                    count += 1
                    print(f'  ✓ {title}')
                time.sleep(1)
            except Exception as e:
                print(f'  Skipping item: {e}')
                continue

        page += 1
        time.sleep(2)

    print(f'[Dynamo] {count} cartas baixadas')
    return count


# =============================================================================
# KAPITALO - Archive page
# =============================================================================
def scrape_kapitalo(conn):
    print('\n[Kapitalo] Scraping cartas...')
    gestora = 'Kapitalo'
    dest = BASE_DIR / 'kapitalo'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    pages = [
        'https://www.kapitalo.com.br/carta-do-gestor/kapa-e-zeta/',
        'https://www.kapitalo.com.br/carta-do-gestor/nw3/',
        'https://www.kapitalo.com.br/carta-do-gestor/k10/',
        'https://www.kapitalo.com.br/carta-do-gestor/tarkus/',
    ]

    for page_url in pages:
        try:
            resp = session.get(page_url, timeout=15)
            soup = BeautifulSoup(resp.content, 'html.parser')

            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                if '.pdf' in href.lower():
                    if not href.startswith('http'):
                        href = 'https://www.kapitalo.com.br' + href
                    fname = href.split('/')[-1].split('?')[0]
                    title = fname.replace('.pdf', '').replace('-', ' ').replace('_', ' ')

                    if letter_exists(conn, gestora, title):
                        continue

                    pdf_path = dest / fname
                    if not pdf_path.exists():
                        download_pdf(href, pdf_path)

                    if pdf_path.exists():
                        text = extract_text_from_pdf(pdf_path)
                        date_match = re.search(r'(\d{4})[_-]?(\d{2})', fname)
                        date_str = (
                            f'{date_match.group(1)}-{date_match.group(2)}' if date_match else ''
                        )
                        store_letter(
                            conn,
                            {
                                'gestora': gestora,
                                'title': title,
                                'date': date_str,
                                'url': href,
                                'content': text,
                                'pdf_path': str(pdf_path),
                            },
                        )
                        count += 1
                        print(f'  ✓ {fname}')
                    time.sleep(1)
        except Exception as e:
            print(f'  Error on {page_url}: {e}')

    print(f'[Kapitalo] {count} cartas baixadas')
    return count


# =============================================================================
# ACE CAPITAL
# =============================================================================
def scrape_ace(conn):
    print('\n[Ace Capital] Scraping cartas...')
    gestora = 'Ace Capital'
    dest = BASE_DIR / 'ace'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    try:
        resp = session.get('https://acecapital.com.br/cartas-multimercado/', timeout=15)
        soup = BeautifulSoup(resp.content, 'html.parser')
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            if '.pdf' in href.lower():
                if not href.startswith('http'):
                    href = 'https://acecapital.com.br' + href
                fname = href.split('/')[-1].split('?')[0]
                title = fname.replace('.pdf', '').replace('-', ' ').replace('_', ' ')
                if letter_exists(conn, gestora, title):
                    continue
                pdf_path = dest / fname
                if not pdf_path.exists():
                    download_pdf(href, pdf_path)
                if pdf_path.exists():
                    text = extract_text_from_pdf(pdf_path)
                    store_letter(
                        conn,
                        {
                            'gestora': gestora,
                            'title': title,
                            'date': '',
                            'url': href,
                            'content': text,
                            'pdf_path': str(pdf_path),
                        },
                    )
                    count += 1
                    print(f'  ✓ {fname}')
                time.sleep(1)
    except Exception as e:
        print(f'  Error: {e}')

    print(f'[Ace Capital] {count} cartas baixadas')
    return count


# =============================================================================
# GENOA CAPITAL
# =============================================================================
def scrape_genoa(conn):
    print('\n[Genoa Capital] Scraping relatórios...')
    gestora = 'Genoa Capital'
    dest = BASE_DIR / 'genoa'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    try:
        resp = session.get('https://www.genoacapital.com.br/relatorios.html', timeout=15)
        soup = BeautifulSoup(resp.content, 'html.parser')
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            if '.pdf' in href.lower():
                if not href.startswith('http'):
                    href = 'https://www.genoacapital.com.br/' + href.lstrip('/')
                fname = href.split('/')[-1].split('?')[0]
                title = fname.replace('.pdf', '').replace('-', ' ').replace('_', ' ')
                if letter_exists(conn, gestora, title):
                    continue
                pdf_path = dest / fname
                if not pdf_path.exists():
                    download_pdf(href, pdf_path)
                if pdf_path.exists():
                    text = extract_text_from_pdf(pdf_path)
                    store_letter(
                        conn,
                        {
                            'gestora': gestora,
                            'title': title,
                            'date': '',
                            'url': href,
                            'content': text,
                            'pdf_path': str(pdf_path),
                        },
                    )
                    count += 1
                    print(f'  ✓ {fname}')
                time.sleep(1)
    except Exception as e:
        print(f'  Error: {e}')

    print(f'[Genoa Capital] {count} cartas baixadas')
    return count


# =============================================================================
# DAHLIA CAPITAL
# =============================================================================
def scrape_dahlia(conn):
    print('\n[Dahlia Capital] Scraping cartas...')
    gestora = 'Dahlia Capital'
    dest = BASE_DIR / 'dahlia'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    # Dahlia uses Wix - try known blog URL patterns
    try:
        resp = session.get('https://www.dahliacapital.com.br/nossas-cartas', timeout=15)
        soup = BeautifulSoup(resp.content, 'html.parser')
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            if 'carta' in href.lower() or 'blog' in href.lower():
                if not href.startswith('http'):
                    href = 'https://www.dahliacapital.com.br' + href
                title = link.get_text(strip=True) or href.split('/')[-1]
                if not title or letter_exists(conn, gestora, title):
                    continue
                # Try to get the blog post content
                try:
                    post_resp = session.get(href, timeout=15)
                    post_soup = BeautifulSoup(post_resp.content, 'html.parser')
                    content_div = post_soup.find('div', attrs={'data-id': 'content-viewer'})
                    if content_div:
                        text = content_div.get_text(separator=' ', strip=True)
                        date_match = re.search(r'São Paulo,\s+(.*?\d{4})', text)
                        date_str = date_match.group(1) if date_match else ''
                        store_letter(
                            conn,
                            {
                                'gestora': gestora,
                                'title': title,
                                'date': date_str,
                                'url': href,
                                'content': text,
                            },
                        )
                        count += 1
                        print(f'  ✓ {title[:60]}')
                except Exception:
                    pass
                time.sleep(2)
    except Exception as e:
        print(f'  Error: {e}')

    print(f'[Dahlia Capital] {count} cartas baixadas')
    return count


# =============================================================================
# ADAM CAPITAL - WordPress PDFs
# =============================================================================
def scrape_adam(conn):
    print('\n[Adam Capital] Tentando URLs previsíveis...')
    gestora = 'Adam Capital'
    dest = BASE_DIR / 'adam'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    months_pt = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

    for year in range(2016, 2027):
        for i, month_name in enumerate(months_pt, 1):
            if year == 2026 and i > 3:
                break
            patterns = [
                f'https://adamcapital.com.br/wp-content/uploads/{year}/{i:02d}/Carta-Mensal-{month_name}-{year}.pdf',
                f'https://adamcapital.com.br/wp-content/uploads/{year}/{i:02d}/Adam-Carta-Mensal-{month_name}-{year}.pdf',
            ]
            title = f'Adam Capital - Carta {year}-{i:02d}'
            if letter_exists(conn, gestora, title):
                continue
            for url in patterns:
                fname = f'adam_{year}{i:02d}.pdf'
                pdf_path = dest / fname
                if download_pdf(url, pdf_path):
                    text = extract_text_from_pdf(pdf_path)
                    store_letter(
                        conn,
                        {
                            'gestora': gestora,
                            'title': title,
                            'date': f'{year}-{i:02d}',
                            'url': url,
                            'content': text,
                            'pdf_path': str(pdf_path),
                        },
                    )
                    count += 1
                    print(f'  ✓ {fname}')
                    break
            time.sleep(0.5)

    print(f'[Adam Capital] {count} cartas baixadas')
    return count


# =============================================================================
# MAIN
# =============================================================================
def main():
    print('=' * 60)
    print('OSIRA - Download de Cartas de Gestoras')
    print(f'Destino: {BASE_DIR}')
    print(f'Database: {DB_PATH}')
    print('=' * 60)

    BASE_DIR.mkdir(parents=True, exist_ok=True)
    conn = init_db()

    total = 0
    scrapers = [
        scrape_verde,
        scrape_legacy,
        scrape_kinea,
        scrape_dynamo,
        scrape_kapitalo,
        scrape_ace,
        scrape_genoa,
        scrape_dahlia,
        scrape_adam,
    ]

    for scraper_fn in scrapers:
        try:
            n = scraper_fn(conn)
            total += n
        except Exception as e:
            print(f'  ERROR in {scraper_fn.__name__}: {e}')

    # Summary
    cur = conn.execute(
        'SELECT gestora, COUNT(*) FROM letters GROUP BY gestora ORDER BY COUNT(*) DESC'
    )
    print('\n' + '=' * 60)
    print('RESUMO')
    print('=' * 60)
    for row in cur:
        print(f'  {row[0]}: {row[1]} cartas')

    total_db = conn.execute('SELECT COUNT(*) FROM letters').fetchone()[0]
    print(f'\nTotal no banco: {total_db} cartas')
    print(f'Novas nesta execução: {total}')
    conn.close()


if __name__ == '__main__':
    main()
