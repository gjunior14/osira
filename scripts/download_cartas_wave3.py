"""Wave 3: Improve coverage for Kinea, Legacy, Santander, Dynamo + new sources."""

import os
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
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
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


def dl(url, dest, timeout=30, verify=True):
    try:
        r = session.get(url, timeout=timeout, stream=True, verify=verify)
        if r.status_code == 200 and len(r.content) > 1000:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            return True
    except Exception:
        pass
    return False


def txt(path):
    try:
        reader = pypdf.PdfReader(str(path))
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
# KINEA - Expanded fund names and URL patterns
# =============================================================================
def scrape_kinea_v3(conn):
    print('\n[Kinea v3] Expanded scraping...')
    g = 'Kinea'
    dest = BASE_DIR / 'kinea'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    funds = [
        'Atlas-II',
        'Atlas',
        'Chronos',
        'IPV',
        'KNCR',
        'KFOF',
        'Kan',
        'Macro',
        'Hedge',
        'RF-Absoluto',
        'Prev-Macro',
        'Atlas-II-Geral-Sub-I',
        'Atlas-Geral-Sub-I',
    ]

    for fund in funds:
        for year in range(2016, 2027):
            for month in range(1, 13):
                if year == 2026 and month > 3:
                    break
                ym = f'{year}-{month:02d}'
                title = f'Kinea {fund} - Carta {ym}'
                if exists(conn, g, title):
                    continue

                base = 'https://www.kinea.com.br/wp-content/uploads'
                ym = f'{year}/{month:02d}'
                dt = f'{year}-{month:02d}'
                patterns = [
                    f'{base}/{ym}/Carta-do-Gestor-{fund}-{dt}.pdf',
                    f'{base}/{ym}/{fund}_Carta-do-Gestor_{month:02d}-{year}.pdf',
                    f'{base}/{ym}/Carta-do-Gestor-{fund}-Geral-Sub-I-{dt}.pdf',
                    f'https://kinea.com.br/wp-content/uploads/{ym}/Carta-do-Gestor-{fund}-{dt}.pdf',
                    f'https://kinea.com.br/wp-content/uploads/{ym}/{fund}-Carta-do-Gestor-{dt}.pdf',
                    f'{base}/{ym}/carta-do-gestor-{fund.lower()}-{dt}.pdf',
                ]
                if month < 12:
                    nm = f'{year}/{month + 1:02d}'
                    patterns.append(f'{base}/{nm}/Carta-do-Gestor-{fund}-{dt}.pdf')
                if month == 12:
                    patterns.append(f'{base}/{year + 1}/01/Carta-do-Gestor-{fund}-{dt}.pdf')
                patterns = [p for p in patterns if p]

                fname = f'kinea_{fund}_{year}{month:02d}.pdf'
                pdf_path = dest / fname

                if pdf_path.exists():
                    store(
                        conn,
                        {
                            'gestora': g,
                            'title': title,
                            'date': ym,
                            'url': '',
                            'content': txt(pdf_path),
                            'pdf_path': str(pdf_path),
                        },
                    )
                    count += 1
                    continue

                for url in patterns:
                    if dl(url, pdf_path):
                        store(
                            conn,
                            {
                                'gestora': g,
                                'title': title,
                                'date': ym,
                                'url': url,
                                'content': txt(pdf_path),
                                'pdf_path': str(pdf_path),
                            },
                        )
                        count += 1
                        print(f'  ✓ {fname}')
                        break
                time.sleep(0.2)

    # Also try scraping the blog pages
    print('  Scraping blog pages...')
    for page_num in range(1, 20):
        url = f'https://www.kinea.com.br/blog/categoria/carta-do-gestor/page/{page_num}/'
        soup = parse(url)
        if not soup:
            break

        articles = soup.find_all('article') or soup.find_all('div', class_='post')
        if not articles:
            # Try finding any links to cartas
            for a in soup.find_all('a', href=True):
                href = a['href']
                if '.pdf' in href.lower() and 'carta' in href.lower():
                    if not href.startswith('http'):
                        href = 'https://www.kinea.com.br' + href
                    fname = href.split('/')[-1].split('?')[0]
                    title = f'Kinea blog - {fname.replace(".pdf", "")}'
                    if exists(conn, g, title):
                        continue
                    pdf_path = dest / fname
                    if not pdf_path.exists():
                        dl(href, pdf_path)
                    if pdf_path.exists():
                        store(
                            conn,
                            {
                                'gestora': g,
                                'title': title,
                                'date': '',
                                'url': href,
                                'content': txt(pdf_path),
                                'pdf_path': str(pdf_path),
                            },
                        )
                        count += 1
                        print(f'  ✓ {fname}')
            break

        for article in articles:
            for a in article.find_all('a', href=True):
                href = a['href']
                if '.pdf' in href.lower():
                    if not href.startswith('http'):
                        href = 'https://www.kinea.com.br' + href
                    fname = href.split('/')[-1].split('?')[0]
                    title = f'Kinea blog - {fname.replace(".pdf", "")}'
                    if exists(conn, g, title):
                        continue
                    pdf_path = dest / fname
                    if not pdf_path.exists():
                        dl(href, pdf_path)
                    if pdf_path.exists():
                        store(
                            conn,
                            {
                                'gestora': g,
                                'title': title,
                                'date': '',
                                'url': href,
                                'content': txt(pdf_path),
                                'pdf_path': str(pdf_path),
                            },
                        )
                        count += 1
                        print(f'  ✓ {fname}')
        time.sleep(1)

    print(f'[Kinea v3] {count} novas cartas')
    return count


# =============================================================================
# LEGACY - Try 2018-2020 patterns + Azure blob exhaustive
# =============================================================================
def scrape_legacy_v3(conn):
    print('\n[Legacy v3] Buscando 2018-2020...')
    g = 'Legacy Capital'
    dest = BASE_DIR / 'legacy'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    months_pt = {
        1: ['Janeiro', 'Jan'],
        2: ['Fevereiro', 'Fev'],
        3: ['Marco', 'Mar', 'Março'],
        4: ['Abril', 'Abr'],
        5: ['Maio', 'Mai'],
        6: ['Junho', 'Jun'],
        7: ['Julho', 'Jul'],
        8: ['Agosto', 'Ago'],
        9: ['Setembro', 'Set'],
        10: ['Outubro', 'Out'],
        11: ['Novembro', 'Nov'],
        12: ['Dezembro', 'Dez'],
    }

    for year in range(2018, 2027):
        for month in range(1, 13):
            if year == 2026 and month > 3:
                break
            ym = f'{year}{month:02d}'
            title = f'Legacy Capital - Carta {year}-{month:02d}'
            if exists(conn, g, title):
                continue

            urls = [
                f'https://www.legacycapital.com.br/wp-content/uploads/{ym}_Legacy_Capital.pdf',
                f'https://www.legacycapital.com.br/wp-content/uploads/{ym}_Carta-Mensal.pdf',
                f'https://www.legacycapital.com.br/wp-content/uploads/carta_mensal_{year}_{month:02d}.pdf',
                f'https://legacywebsite.blob.core.windows.net/site/cartamensal/{year}/{ym}_Carta%20Mensal.pdf',
                f'https://legacywebsite.blob.core.windows.net/site/cartamensal/{year}/{ym}_Legacy_Capital.pdf',
                f'https://legacywebsite.blob.core.windows.net/site/cartamensal/{ym}_Carta%20Mensal.pdf',
                f'https://legacywebsite.blob.core.windows.net/site/cartamensal/{ym}_Legacy_Capital.pdf',
            ]
            # Add month name patterns
            for name in months_pt[month]:
                urls.extend(
                    [
                        f'https://www.legacycapital.com.br/wp-content/uploads/{year}/{month:02d}/Carta-Mensal-{name}-{year}.pdf',
                        f'https://www.legacycapital.com.br/wp-content/uploads/{year}/{month:02d}/Legacy-Carta-{name}-{year}.pdf',
                        f'https://www.legacycapital.com.br/wp-content/uploads/{year}/{month:02d}/carta-mensal-{name.lower()}-{year}.pdf',
                        f'https://www.legacycapital.com.br/wp-content/uploads/{year}/{month:02d}/Legacy_Capital_{name}_{year}.pdf',
                        f'https://legacywebsite.blob.core.windows.net/site/cartamensal/{year}/Legacy_Capital_{name}_{year}.pdf',
                    ]
                )

            fname = f'legacy_{ym}.pdf'
            pdf_path = dest / fname
            if pdf_path.exists():
                store(
                    conn,
                    {
                        'gestora': g,
                        'title': title,
                        'date': f'{year}-{month:02d}',
                        'url': '',
                        'content': txt(pdf_path),
                        'pdf_path': str(pdf_path),
                    },
                )
                count += 1
                continue

            for url in urls:
                if dl(url, pdf_path):
                    store(
                        conn,
                        {
                            'gestora': g,
                            'title': title,
                            'date': f'{year}-{month:02d}',
                            'url': url,
                            'content': txt(pdf_path),
                            'pdf_path': str(pdf_path),
                        },
                    )
                    count += 1
                    print(f'  ✓ {fname} ({url.split("/")[-1]})')
                    break
            time.sleep(0.2)

    print(f'[Legacy v3] {count} novas cartas')
    return count


# =============================================================================
# SANTANDER - Try historical patterns
# =============================================================================
def scrape_santander_v3(conn):
    print('\n[Santander v3] Buscando historico...')
    g = 'Santander Asset'
    dest = BASE_DIR / 'santander'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    months_pt = [
        'Janeiro',
        'Fevereiro',
        'Marco',
        'Abril',
        'Maio',
        'Junho',
        'Julho',
        'Agosto',
        'Setembro',
        'Outubro',
        'Novembro',
        'Dezembro',
    ]
    months_pt2 = [
        'Janeiro',
        'Fevereiro',
        'Março',
        'Abril',
        'Maio',
        'Junho',
        'Julho',
        'Agosto',
        'Setembro',
        'Outubro',
        'Novembro',
        'Dezembro',
    ]

    # Try view IDs (descending from known ~20280)
    print('  Tentando view IDs...')
    for view_id in range(20300, 19000, -1):
        title = f'Santander Asset - View {view_id}'
        if exists(conn, g, title):
            continue
        url = f'https://www.santanderassetmanagement.com.br/content/view/{view_id}/file/Carta%20Mensal.pdf'
        fname = f'santander_view_{view_id}.pdf'
        pdf_path = dest / fname
        if dl(url, pdf_path):
            content = txt(pdf_path)
            # Extract real title from content
            real_title = f'Santander Carta Mensal (view {view_id})'
            store(
                conn,
                {
                    'gestora': g,
                    'title': real_title,
                    'date': '',
                    'url': url,
                    'content': content,
                    'pdf_path': str(pdf_path),
                },
            )
            count += 1
            print(f'  ✓ view {view_id}')
        # Don't sleep on every attempt, only occasionally
        if view_id % 50 == 0:
            time.sleep(0.5)

    # Try month-name URLs
    for name in months_pt + months_pt2:
        for suffix in ['', '-2025', '-2024', '-2023', '-2022', '-2021']:
            title = f'Santander Carta Mensal {name}{suffix}'
            if exists(conn, g, title):
                continue
            encoded = name.replace('ç', '%C3%A7').replace('ã', '%C3%A3')
            urls = [
                f'https://www.santanderassetmanagement.com.br/content/view/20280/file/Carta%20Mensal%20{encoded}{suffix}.pdf',
            ]
            for url in urls:
                fname = f'santander_{name}{suffix}.pdf'
                pdf_path = dest / fname
                if dl(url, pdf_path):
                    store(
                        conn,
                        {
                            'gestora': g,
                            'title': title,
                            'date': '',
                            'url': url,
                            'content': txt(pdf_path),
                            'pdf_path': str(pdf_path),
                        },
                    )
                    count += 1
                    print(f'  ✓ {fname}')
                    break

    print(f'[Santander v3] {count} novas cartas')
    return count


# =============================================================================
# DYNAMO - Try direct PDF URL patterns
# =============================================================================
def scrape_dynamo_v3(conn):
    print('\n[Dynamo v3] Tentando PDFs diretos...')
    g = 'Dynamo'
    dest = BASE_DIR / 'dynamo'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    # Dynamo letters are numbered (e.g., Carta-Dynamo-127)
    for num in range(1, 130):
        title = f'Carta Dynamo {num}'
        if exists(conn, g, title):
            continue
        urls = [
            f'https://www.dynamo.com.br/wp-content/uploads/2026/01/Carta-Dynamo-{num}.pdf',
            f'https://www.dynamo.com.br/wp-content/uploads/2025/01/Carta-Dynamo-{num}.pdf',
        ]
        # Try year-based paths
        for year in range(2025, 2009, -1):
            for month in [1, 4, 7, 10]:  # quarterly
                urls.append(
                    f'https://www.dynamo.com.br/wp-content/uploads/{year}/{month:02d}/Carta-Dynamo-{num}.pdf'
                )

        fname = f'Carta-Dynamo-{num}.pdf'
        pdf_path = dest / fname
        if pdf_path.exists():
            store(
                conn,
                {
                    'gestora': g,
                    'title': title,
                    'date': '',
                    'url': '',
                    'content': txt(pdf_path),
                    'pdf_path': str(pdf_path),
                },
            )
            count += 1
            continue

        for url in urls:
            if dl(url, pdf_path):
                store(
                    conn,
                    {
                        'gestora': g,
                        'title': title,
                        'date': '',
                        'url': url,
                        'content': txt(pdf_path),
                        'pdf_path': str(pdf_path),
                    },
                )
                count += 1
                print(f'  ✓ Carta Dynamo {num}')
                break
        time.sleep(0.1)

    # Also try the old domain pattern
    for num in range(1, 130):
        title = f'Carta Dynamo {num}'
        if exists(conn, g, title):
            continue
        fname = f'Carta-Dynamo-{num}.pdf'
        pdf_path = dest / fname
        if pdf_path.exists():
            continue
        urls = [
            f'https://www.dynamo.com.br/cartas/carta-dynamo-{num}.pdf',
            f'https://www.dynamo.com.br/uploads/carta-dynamo-{num}.pdf',
            f'https://www.dynamo.com.br/pdf/carta-dynamo-{num}.pdf',
        ]
        for url in urls:
            if dl(url, pdf_path):
                store(
                    conn,
                    {
                        'gestora': g,
                        'title': title,
                        'date': '',
                        'url': url,
                        'content': txt(pdf_path),
                        'pdf_path': str(pdf_path),
                    },
                )
                count += 1
                print(f'  ✓ Carta Dynamo {num} (alt)')
                break

    print(f'[Dynamo v3] {count} novas cartas')
    return count


# =============================================================================
# BTG PACTUAL - Asset Strategy PDFs
# =============================================================================
def scrape_btg(conn):
    print('\n[BTG Pactual] Buscando Asset Strategy...')
    g = 'BTG Pactual'
    dest = BASE_DIR / 'btg'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    months_en = [
        '01',
        '02',
        '03',
        '04',
        '05',
        '06',
        '07',
        '08',
        '09',
        '10',
        '11',
        '12',
    ]

    for year in range(2020, 2027):
        for month in months_en:
            if year == 2026 and int(month) > 3:
                break
            title = f'BTG Asset Strategy {year}-{month}'
            if exists(conn, g, title):
                continue
            # Known pattern from Osira template
            # Try specific date patterns
            for day in ['01', '02', '03', '04', '05', '10', '15', '20', '25']:
                url = (
                    f'https://content.btgpactual.com/research/files/file/pt-BR/'
                    f'{year}-{month}-{day}T211356.771_{year}{month}___Asset_Strategy___BTG_Pactual_Macro_Strategy.pdf'
                )
                fname = f'btg_asset_strategy_{year}{month}.pdf'
                pdf_path = dest / fname
                if dl(url, pdf_path):
                    store(
                        conn,
                        {
                            'gestora': g,
                            'title': title,
                            'date': f'{year}-{month}',
                            'url': url,
                            'content': txt(pdf_path),
                            'pdf_path': str(pdf_path),
                        },
                    )
                    count += 1
                    print(f'  ✓ {fname}')
                    break
            time.sleep(0.2)

    print(f'[BTG Pactual] {count} cartas')
    return count


# =============================================================================
# GARDE ASSET
# =============================================================================
def scrape_garde(conn):
    print('\n[Garde Asset] Scraping...')
    g = 'Garde Asset'
    dest = BASE_DIR / 'garde'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    for url_base in [
        'https://www.gardeasset.com.br/cartas/',
        'https://www.gardeasset.com.br/carta-do-gestor/',
        'https://www.gardeasset.com.br/',
    ]:
        soup = parse(url_base)
        if not soup:
            continue
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '.pdf' not in href.lower():
                continue
            if not href.startswith('http'):
                href = 'https://www.gardeasset.com.br' + href
            fname = href.split('/')[-1].split('?')[0]
            title = fname.replace('.pdf', '').replace('-', ' ').replace('_', ' ')
            if exists(conn, g, title):
                continue
            pdf_path = dest / fname
            if not pdf_path.exists():
                dl(href, pdf_path)
            if pdf_path.exists():
                store(
                    conn,
                    {
                        'gestora': g,
                        'title': title,
                        'date': '',
                        'url': href,
                        'content': txt(pdf_path),
                        'pdf_path': str(pdf_path),
                    },
                )
                count += 1
                print(f'  ✓ {fname}')
            time.sleep(0.5)

    print(f'[Garde Asset] {count} cartas')
    return count


# =============================================================================
# JGP
# =============================================================================
def scrape_jgp(conn):
    print('\n[JGP] Scraping...')
    g = 'JGP'
    dest = BASE_DIR / 'jgp'
    dest.mkdir(parents=True, exist_ok=True)
    count = 0

    for url_base in [
        'https://www.jgp.com.br/cartas/',
        'https://www.jgp.com.br/publicacoes/',
        'https://www.jgp.com.br/',
    ]:
        soup = parse(url_base)
        if not soup:
            continue
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '.pdf' not in href.lower():
                continue
            if not href.startswith('http'):
                href = 'https://www.jgp.com.br' + href
            fname = href.split('/')[-1].split('?')[0]
            title = fname.replace('.pdf', '').replace('-', ' ').replace('_', ' ')
            if exists(conn, g, title):
                continue
            pdf_path = dest / fname
            if not pdf_path.exists():
                dl(href, pdf_path)
            if pdf_path.exists():
                store(
                    conn,
                    {
                        'gestora': g,
                        'title': title,
                        'date': '',
                        'url': href,
                        'content': txt(pdf_path),
                        'pdf_path': str(pdf_path),
                    },
                )
                count += 1
                print(f'  ✓ {fname}')
            time.sleep(0.5)

    print(f'[JGP] {count} cartas')
    return count


# =============================================================================
def main():
    print('=' * 60)
    print('OSIRA - Download Cartas Wave 3 (improved coverage)')
    print('=' * 60)

    BASE_DIR.mkdir(parents=True, exist_ok=True)
    for d in ['kinea', 'legacy', 'santander', 'dynamo', 'btg', 'garde', 'jgp']:
        (BASE_DIR / d).mkdir(exist_ok=True)
    conn = init_db()

    total = 0
    for fn in [
        scrape_kinea_v3,
        scrape_legacy_v3,
        scrape_dynamo_v3,
        scrape_santander_v3,
        scrape_garde,
        scrape_jgp,
    ]:
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
    print('RESUMO TOTAL (waves 1+2+3)')
    print('=' * 60)
    for row in cur:
        print(f'  {row[0]}: {row[1]} cartas')
    t = conn.execute('SELECT COUNT(*) FROM letters').fetchone()[0]
    print(f'\nTotal geral: {t} cartas')
    print(f'Novas nesta wave: {total}')
    conn.close()


if __name__ == '__main__':
    main()
