# Briefing: Dataset de Cartas de Gestoras

**Data:** 18/03/2026
**Status:** 1.056 cartas coletadas de 14 gestoras
**Formato:** PDFs + texto extraido em SQLite (`data/cartas/cartas.db`)

---

## Resumo Executivo

Coletamos **1.056 cartas mensais** de 14 gestoras brasileiras, cobrindo de 1999 ate fev/2026. O texto de cada PDF ja foi extraido e indexado em banco SQLite. Os PDFs estao organizados em `data/cartas/{gestora}/`.

---

## Acervo por Gestora

| Gestora | Gestor | Cartas | Periodo | Tipo |
|---------|--------|--------|---------|------|
| **Verde Asset** | Luis Stuhlberger | 215 | jan/16 - fev/26 | Macro mensal |
| **Kapitalo** | Bruno Magalhaes | 214 | jun/18 - fev/26 | Macro mensal (4 fundos) |
| **SPX Capital** | Rogerio Xavier | 157 | jan/11 - jul/18 | Macro + Acoes mensal |
| **IP Capital** | — | 96 | mar/99 - fev/26 | Equity trimestral |
| **Kinea** | Marco Freire | 94 | dez/21 - abr/25 | Multi-fundo mensal |
| **Ace Capital** | Ricardo Denadai | 76 | out/19 - fev/26 | Macro mensal |
| **Genoa Capital** | — | 72 | jul/20 - fev/26 | Macro mensal |
| **Legacy Capital** | Felipe Guerra | 59 | jan/21 - nov/25 | Macro mensal |
| **Mar Asset** | — | 22 | ~2019 - 2025 | Macro mensal |
| **Squadra** | Guilherme Aché | 19 | 2010 - 2025 | Equity semestral |
| **Alaska** | Henrique Bredda | 18 | 2014 - 2023 | Equity semestral |
| **Santander Asset** | — | 11 | recente | Macro mensal |
| **Ibiuna** | Mario Toros | 2 | ultimo mes | Macro mensal |
| **Dynamo** | — | 1 | recente | Equity trimestral |

---

## Cobertura Mensal (2016-2026)

Cada celula mostra quantas gestoras macro temos naquele mes.

```
         J  F  M  A  M  J  J  A  S  O  N  D
2016:    2  2  3  2  2  3  2  2  3  2  2  3   Verde + SPX (+ IP trim)
2017:    2  2  3  2  2  3  2  2  3  2  2  3   Verde + SPX (+ IP trim)
2018:    2  2  2  3  2  3  2  2  1  1  1  2   SPX ate jul, Kapitalo a partir jun
2019:    2  2  2  3  1  2  2  3  2  3  3  4   +Ace a partir out
2020:    3  3  4  4  3  3  3  4  3  3  3  4   Verde+Kapitalo+Ace (+IP trim)
2021:    4  4  4  5  4  4  4  5  4  4  4  6   +Legacy jan, +Kinea dez
2022:    5  4  4  4  4  5  4  4  4  4  5  5   Solido: 4-5 gestoras/mes
2023:    7  5  5  5  5  5  6  5  4  4  4  5   Pico: 7 em jan (Squadra)
2024:    4  4  4  5  4  4  4  5  4  3  4  5   Estavel: 4-5 gestoras/mes
2025:    6  5  6  5  4  4  4  4  4  4  4  3   +Genoa jan
2026:    3  4                                  Ace+Kapitalo+Verde (+IP)
```

**Legenda:** Numeros = gestoras macro com carta naquele mes

---

## Fontes e Como Replicar

### Scraping direto (URLs publicas)

| Gestora | URL Base | Pattern |
|---------|----------|---------|
| Verde | verdeasset.com.br/public/files/rel_gestao/ | `{fund_id}/{Name}-REL-{YYYY_MM}.pdf` |
| Kapitalo | kapitalo.com.br/carta-do-gestor/ | 4 paginas de fundo, links PDF |
| Ace | acecapital.com.br/cartas-multimercado/ | Pagina unica, todos os links |
| Genoa | genoacapital.com.br/relatorios.html | Pagina unica, todos os links |
| Legacy | legacycapital.com.br/wp-content/uploads/ | `{YYYYMM}_Legacy_Capital.pdf` |
| Kinea | kinea.com.br/wp-content/uploads/ | `{YYYY}/{MM}/Carta-do-Gestor-{Fund}-{YYYY}-{MM}.pdf` |
| IP Capital | ip-capitalpartners.com/.../loop-reports.php | Paginado `?paged={N}` |
| Squadra | squadrainvest.com.br/cartas/ | Pagina unica, links PDF |
| Alaska | alaska-asset.com.br/cartas/ | Pagina unica, links PDF |
| Mar Asset | marasset.com.br/conteudo-mar/ | Secao "Cartas", links PDF |
| Santander | santanderassetmanagement.com.br/conteudos/carta-mensal | Links PDF |

### Wayback Machine (dados historicos)

| Gestora | Query CDX | Resultado |
|---------|-----------|-----------|
| **SPX Capital** | `url=spxcapital.com.br/*&filter=mimetype:application/pdf` | **157 PDFs** (2011-2018) |
| Ibiuna | sem resultados PDF | — |
| Legacy | sem resultados PDF | — |
| Dynamo | sem resultados PDF | — |

### Gestoras que precisam Selenium (JS-rendered)

- **SPX** (pos-2018): site novo e JS-rendered
- **Dahlia Capital**: Wix
- **Adam Capital**: bot protection
- **Bahia Asset**: disclaimer + JS
- **Guepardo**: Elementor (estrutura mudou)
- **Artica**: Jet Engine (JS)

---

## Scripts

```bash
# Wave 1: Verde, Legacy, Kinea, Dynamo, Kapitalo, Ace, Genoa
python scripts/download_cartas.py

# Wave 2: Alaska, IP Capital, Squadra, Mar Asset, Santander, SPX, Ibiuna
python scripts/download_cartas_wave2.py

# Wave 3: Kinea expanded, Legacy expanded, Dynamo brute-force, Santander IDs
python scripts/download_cartas_wave3.py

# Wayback Machine: SPX historico (separado)
# Integrado no script wave3 ou rodar manualmente via CDX API
```

---

## Banco de Dados

```
data/cartas/cartas.db (SQLite)

Tabela: letters
  - id (INTEGER PRIMARY KEY)
  - gestora (TEXT)       -- nome da gestora
  - title (TEXT)         -- titulo da carta
  - date (TEXT)          -- YYYY-MM ou YYYY-MM-DD
  - url (TEXT)           -- URL original do PDF
  - content (TEXT)       -- texto extraido do PDF
  - pdf_path (TEXT)      -- caminho local do PDF
  - created_at (TEXT)    -- timestamp de download
```

---

## Proximos Passos

1. **Pipeline LLM**: Processar cada carta com Claude API para extrair visao macro estruturada (hawkish/dovish/neutro para juros, cambio, fiscal, etc.) no formato YAML do Osira
2. **Selenium scrapers**: Para SPX pos-2018, Dahlia, Adam, Bahia (ganho marginal)
3. **XP Opiniao Consolidada**: PDF mensal com centenas de gestoras — maior bang-for-buck pendente
4. **Scraping recorrente**: Automatizar download mensal das novas cartas

---

## Avaliacao para Backtesting

| Periodo | Gestoras/mes | Qualidade |
|---------|-------------|-----------|
| 2011-2015 | 1-2 (SPX+IP) | Fraco — so SPX macro |
| **2016-2018** | **2-3 (Verde+SPX+IP)** | **Minimo viavel** |
| **2019** | 2-4 | Bom a partir de out (Ace) |
| **2020-2021** | 3-5 | Bom |
| **2022-2026** | 4-7 | Solido |

**Conclusao:** Dataset suficiente para backtest de 2016 em diante com Verde+SPX como base. Sinal mais robusto a partir de 2020 com 3+ gestoras macro por mes.
