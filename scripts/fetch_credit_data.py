"""Fetch credit-related data from CVM/ANBIMA open data (2015+).

Produces two CSVs:
  data/captacao_credito_privado.csv  — monthly net flows for private credit fund types
  data/emissoes_credito_privado.csv  — monthly issuance volume (debentures, NC, CRI, CRA, FIDC)

Data sources:
  - CVM informe diário: yearly ZIPs (2015-2020) + monthly ZIPs (2021+)
  - CVM cadastro: registro_fundo_classe.zip (RCVM175) + cad_fi.csv (legacy)
  - CVM ofertas: oferta_distribuicao.csv (old ICVM400, 2015-2022) + oferta_resolucao_160.csv (2023+)
"""

import csv
import io
import re
import sys
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / 'data'
DATA.mkdir(exist_ok=True)

CVM_BASE = 'https://dados.cvm.gov.br/dados'
UA = 'Mozilla/5.0 osira-bot/1.0'

# --- ANBIMA classes that proxy "private credit" ---
CREDIT_CLASSES = {
    'Renda Fixa Duração Baixa Crédito Livre',
    'Renda Fixa Duração Média Crédito Livre',
    'Renda Fixa Duração Livre Crédito Livre',
}
# Partial matches for legacy cadastro (truncated names)
CREDIT_CLASSES_PARTIAL = (
    'Renda Fixa Duração Baixa Crédito Liv',
    'Renda Fixa Duração Média Crédito Liv',
    'Renda Fixa Duração Livre Crédito Liv',
)
INFRA_KEYWORDS = ('infraestrutura', 'infra ', 'lei 12.431', 'lei 12431')

# --- Emission types ---
# Resolução 160 (2023+)
EMISSION_TYPES_NEW = {
    'Debêntures',
    'Notas Comerciais',
    'Certificados de Recebíveis Imobiliários',
    'Certificados de Recebíveis do Agronegócio',
    'Cotas de FIDC',
}
# ICVM 400 (pre-2023) — map old names → canonical
EMISSION_MAP_OLD: dict[str, str] = {
    'DEBÊNTURES': 'Debêntures',
    'DEBENTURES': 'Debêntures',
    'NOTAS COMERCIAIS': 'Notas Comerciais',
    'NOTAS PROMISSÓRIAS': 'Notas Comerciais',  # predecessor instrument
    'CERTIFICADOS DE RECEBÍVEIS IMOBILIÁRIOS - CRI': 'Certificados de Recebíveis Imobiliários',
    'CERTIFICADO DE RECEBÍVEIS IMOBILIÁRIOS': 'Certificados de Recebíveis Imobiliários',
    'CERTIFICADOS DE RECEBÍVEIS DO AGRONEGÓCIO - CRA': 'Certificados de Recebíveis do Agronegócio',
    'CERTIFICADO DE RECEBÍVEIS DO AGRONEGÓCIO': 'Certificados de Recebíveis do Agronegócio',
    'CERTIFICADOS DE DIREITOS CREDITÓRIOS DO AGRONEGÓCIO - CDCA': (
        'Certificados de Recebíveis do Agronegócio'
    ),
    'QUOTAS DE FUNDO INVEST DIREITOS CREDITÓRIOS SÊNIOR': 'Cotas de FIDC',
    'QUOTAS DE FUNDO INVEST DIREITOS CREDITÓRIOS SUBORD': 'Cotas de FIDC',
    'QUOTAS DE FIC-FIDC': 'Cotas de FIDC',
    'QUOTAS DE FIDC-NP SÊNIOR': 'Cotas de FIDC',
    'QUOTAS DE FIDC-PIPS': 'Cotas de FIDC',
}

CANONICAL_TYPES = sorted(EMISSION_TYPES_NEW)


def _normalize_cnpj(cnpj: str) -> str:
    return re.sub(r'\D', '', cnpj)


def _is_credit_class(anbima: str) -> bool:
    if anbima in CREDIT_CLASSES:
        return True
    return any(anbima.startswith(p) for p in CREDIT_CLASSES_PARTIAL)


def fetch(url: str) -> bytes:
    req = Request(url, headers={'User-Agent': UA})
    with urlopen(req, timeout=120) as resp:
        return resp.read()


def read_all_csvs_from_zip(data: bytes, encoding='latin-1') -> dict[str, list[dict]]:
    """Return {filename: rows} for all CSVs in a ZIP."""
    result = {}
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if name.endswith('.csv'):
                with zf.open(name) as f:
                    text = io.TextIOWrapper(f, encoding=encoding)
                    result[name] = list(csv.DictReader(text, delimiter=';'))
    return result


def build_cnpj_to_class() -> dict[str, str]:
    """Map normalized CNPJ → ANBIMA credit classification, from both cadastro sources."""
    cnpj_map: dict[str, str] = {}

    # Source 1: RCVM175 registro_fundo_classe (new format, has most active funds)
    print('Fetching RCVM175 cadastro (registro_fundo_classe.zip)...')
    data = fetch(f'{CVM_BASE}/FI/CAD/DADOS/registro_fundo_classe.zip')
    for rows in read_all_csvs_from_zip(data).values():
        for row in rows:
            cnpj = _normalize_cnpj(row.get('CNPJ_Classe', ''))
            anbima = row.get('Classificacao_Anbima', '').strip()
            name = row.get('Denominacao_Social', '').lower()
            if not cnpj:
                continue
            if _is_credit_class(anbima):
                cnpj_map[cnpj] = _canonical_credit_class(anbima)
            elif any(kw in name for kw in INFRA_KEYWORDS):
                cnpj_map[cnpj] = 'RF Infraestrutura'

    # Source 2: Legacy cad_fi.csv (pre-RCVM175 funds, many already migrated)
    print('Fetching legacy cadastro (cad_fi.csv)...')
    try:
        legacy = fetch(f'{CVM_BASE}/FI/CAD/DADOS/cad_fi.csv')
        reader = csv.DictReader(io.StringIO(legacy.decode('latin-1')), delimiter=';')
        for row in reader:
            cnpj = _normalize_cnpj(row.get('CNPJ_FUNDO', ''))
            anbima = row.get('CLASSE_ANBIMA', '').strip()
            name = row.get('DENOM_SOCIAL', '').lower()
            if not cnpj or cnpj in cnpj_map:
                continue
            if _is_credit_class(anbima):
                cnpj_map[cnpj] = _canonical_credit_class(anbima)
            elif any(kw in name for kw in INFRA_KEYWORDS):
                cnpj_map[cnpj] = 'RF Infraestrutura'
    except Exception as e:
        print(f'  Warning: could not load cad_fi.csv ({e})')

    print(f'  Mapped {len(cnpj_map)} funds to credit/infra classes')
    return cnpj_map


def _canonical_credit_class(anbima: str) -> str:
    """Normalize truncated ANBIMA class names to full canonical form."""
    for full in CREDIT_CLASSES:
        if anbima.startswith(full[:30]):
            return full
    return anbima


def _build_flow_urls(start_year: int, end_ym: str) -> list[tuple[str, str]]:
    """Build list of (label, url) for informe diário downloads.

    2015-2020: yearly HIST ZIPs containing monthly CSVs
    2021+: individual monthly ZIPs
    """
    urls = []
    end_year = int(end_ym[:4])

    # Yearly historical ZIPs (2015-2020)
    for year in range(start_year, min(2021, end_year + 1)):
        urls.append(
            (str(year), f'{CVM_BASE}/FI/DOC/INF_DIARIO/DADOS/HIST/inf_diario_fi_{year}.zip')
        )

    # Monthly ZIPs (2021+)
    if end_year >= 2021:
        ym = '202101'
        while ym <= end_ym:
            urls.append((ym, f'{CVM_BASE}/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{ym}.zip'))
            ym = _next_month(ym)

    return urls


def _process_informe_rows(
    rows: list[dict],
    cnpj_map: dict[str, str],
    monthly: dict,
) -> int:
    """Process rows from informe diário (handles both old and new column names)."""
    hits = 0
    for row in rows:
        # Old format uses CNPJ_FUNDO, new uses CNPJ_FUNDO_CLASSE
        raw_cnpj = row.get('CNPJ_FUNDO_CLASSE') or row.get('CNPJ_FUNDO', '')
        cnpj = _normalize_cnpj(raw_cnpj)
        cls = cnpj_map.get(cnpj)
        if not cls:
            continue
        month = row.get('DT_COMPTC', '')[:7]
        cap = float(row.get('CAPTC_DIA', '0').replace(',', '.'))
        res = float(row.get('RESG_DIA', '0').replace(',', '.'))
        monthly[month][cls]['captacao'] += cap
        monthly[month][cls]['resgate'] += res
        hits += 1
    return hits


def fetch_flows(start_year: int = 2015, end_ym: str | None = None):
    """Download informe diário (2015+) and aggregate net flows by ANBIMA class."""
    cnpj_map = build_cnpj_to_class()

    if end_ym is None:
        end_ym = datetime.now().strftime('%Y%m')

    monthly: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: {'captacao': 0.0, 'resgate': 0.0})
    )

    for label, url in _build_flow_urls(start_year, end_ym):
        print(f'  Fetching {label}...', end=' ', flush=True)
        try:
            data = fetch(url)
        except Exception as e:
            print(f'skip ({e})')
            continue

        # Yearly ZIPs contain multiple monthly CSVs
        total_hits = 0
        for _fname, rows in read_all_csvs_from_zip(data).items():
            total_hits += _process_informe_rows(rows, cnpj_map, monthly)

        print(f'{total_hits} rows matched')

    # Write CSV
    out = DATA / 'captacao_credito_privado.csv'
    all_classes = sorted({c for m in monthly.values() for c in m})
    with open(out, 'w', newline='') as f:
        w = csv.writer(f)
        header = ['month']
        for cls in all_classes:
            header += [f'{cls}_captacao', f'{cls}_resgate', f'{cls}_liquida']
        header += ['total_captacao', 'total_resgate', 'total_liquida']
        w.writerow(header)

        for month in sorted(monthly):
            row = [month]
            total_cap = total_res = 0.0
            for cls in all_classes:
                d = monthly[month][cls]
                liq = d['captacao'] - d['resgate']
                row += [f'{d["captacao"]:.2f}', f'{d["resgate"]:.2f}', f'{liq:.2f}']
                total_cap += d['captacao']
                total_res += d['resgate']
            row += [f'{total_cap:.2f}', f'{total_res:.2f}', f'{total_cap - total_res:.2f}']
            w.writerow(row)

    print(f'\nFlows CSV: {out} ({len(monthly)} months)')
    return out


def fetch_emissions(start_year: int = 2015):
    """Download CVM offerings and aggregate monthly issuance volume (2015+)."""
    print('Fetching emissions data...')
    data = fetch(f'{CVM_BASE}/OFERTA/DISTRIB/DADOS/oferta_distribuicao.zip')

    monthly: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    skipped = 0

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        # Old format (ICVM 400): oferta_distribuicao.csv
        if 'oferta_distribuicao.csv' in zf.namelist():
            print('  Processing old format (ICVM 400)...')
            with zf.open('oferta_distribuicao.csv') as f:
                text = io.TextIOWrapper(f, encoding='latin-1')
                for row in csv.DictReader(text, delimiter=';'):
                    tipo = row.get('Tipo_Ativo', '').strip()
                    canonical = EMISSION_MAP_OLD.get(tipo)
                    if not canonical:
                        continue
                    date = row.get('Data_Registro_Oferta', '').strip()
                    if not date or len(date) < 7:
                        skipped += 1
                        continue
                    month = date[:7]
                    if int(month[:4]) < start_year:
                        continue
                    vol_str = row.get('Valor_Total', '0').replace(',', '.')
                    try:
                        vol = float(vol_str)
                    except ValueError:
                        skipped += 1
                        continue
                    monthly[month][canonical] += vol

        # New format (Resolução 160): oferta_resolucao_160.csv
        if 'oferta_resolucao_160.csv' in zf.namelist():
            print('  Processing new format (Resolução 160)...')
            with zf.open('oferta_resolucao_160.csv') as f:
                text = io.TextIOWrapper(f, encoding='latin-1')
                for row in csv.DictReader(text, delimiter=';'):
                    vm = row.get('Valor_Mobiliario', '').strip()
                    if vm not in EMISSION_TYPES_NEW:
                        continue
                    date = row.get('Data_Registro', '').strip()
                    if not date or len(date) < 7:
                        skipped += 1
                        continue
                    month = date[:7]
                    vol_str = row.get('Valor_Total_Registrado', '0').replace(',', '.')
                    try:
                        vol = float(vol_str)
                    except ValueError:
                        skipped += 1
                        continue
                    monthly[month][vm] += vol

    out = DATA / 'emissoes_credito_privado.csv'
    with open(out, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['month'] + CANONICAL_TYPES + ['total'])
        for month in sorted(monthly):
            row = [month]
            total = 0.0
            for t in CANONICAL_TYPES:
                v = monthly[month][t]
                row.append(f'{v:.2f}')
                total += v
            row.append(f'{total:.2f}')
            w.writerow(row)

    print(f'Emissions CSV: {out} ({len(monthly)} months, {skipped} skipped)')
    return out


def _next_month(ym: str) -> str:
    y, m = int(ym[:4]), int(ym[4:])
    m += 1
    if m > 12:
        y += 1
        m = 1
    return f'{y}{m:02d}'


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if what in ('flows', 'all'):
        fetch_flows()
    if what in ('emissions', 'all'):
        fetch_emissions()
