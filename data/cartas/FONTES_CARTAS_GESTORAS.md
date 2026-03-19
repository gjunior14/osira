# Fontes de Cartas de Gestoras - Guia de Replicacao

> **828 cartas baixadas** de 13 gestoras. Todas publicas, sem necessidade de login.
> Database SQLite: `data/cartas/cartas.db`
> Scripts: `scripts/download_cartas.py` (wave 1) + `scripts/download_cartas_wave2.py` (wave 2)

---

## 1. Verde Asset (Luis Stuhlberger) — 215 cartas, 2016-2026

**URL padrao previsivel — enumerar por mes:**
```
https://www.verdeasset.com.br/public/files/rel_gestao/{FUND_ID}/{FUND_NAME}-REL-{YYYY_MM}.pdf
```

| Fundo | Fund ID | Exemplo |
|-------|---------|---------|
| Verde FIC FIM | 158094 | `Verde-REL-2024_06.pdf` |
| Verde Acoes | 118 | `Acoes-REL-2024_06.pdf` |

**Como replicar:** Iterar `YYYY` de 2016 a 2026, `MM` de 01 a 12. Testar HTTP 200.

---

## 2. Kapitalo (Bruno Magalhaes) — 214 cartas, 2018-2026

**Paginas de cartas por fundo:**
- Kappa e Zeta: https://www.kapitalo.com.br/carta-do-gestor/kapa-e-zeta/
- NW3: https://www.kapitalo.com.br/carta-do-gestor/nw3/
- K10: https://www.kapitalo.com.br/carta-do-gestor/k10/
- Tarkus: https://www.kapitalo.com.br/carta-do-gestor/tarkus/
- Cartas Tematicas: https://www.kapitalo.com.br/carta-do-gestor/cartas-tematicas/

**Base dos PDFs:** `https://www.kapitalo.com.br/wp-content/uploads/...`

**Como replicar:** Acessar cada pagina acima, extrair todos os links `.pdf`. Os nomes variam (ex: `Carta-do-Gestor_Fevereiro2026.pdf`, `kapitalo_cartamensal_KAPPA-ZETA_OUTUBRO.pdf`).

---

## 3. IP Capital Partners — 96 cartas, 1999-2026

**API paginada:**
```
https://ip-capitalpartners.com/wp-content/themes/ip-capital/loop-reports.php?paged={PAGE}
```

**Como replicar:** Paginar de `?paged=1` ate nao ter mais resultados. Cada pagina retorna cards com titulo, data e link de download `.pdf`. Nota: site usa certificado SSL que pode dar warning — usar `verify=False`.

**Exemplos de PDFs:**
- `https://ip-capitalpartners.com/wp-content/uploads/2026/03/IP_RG_202602_AI-hi.pdf`
- `https://ip-capitalpartners.com/wp-content/uploads/2004/03/2004_03_RG_Consolidado.pdf`
- `https://ip-capitalpartners.com/wp-content/uploads/1999/06/ipp_9906.pdf`

---

## 4. Ace Capital — 76 cartas, 2019-2026

**Pagina unica com todos os links:**
```
https://acecapital.com.br/cartas-multimercado/
```

**Base dos PDFs:** `https://acecapital.com.br/wp-content/uploads/`

**Exemplos:**
- `Carta-Fevereiro-2026.pdf`
- `Carta-Outubro-2019.pdf`

**Como replicar:** Scrape da pagina, extrair todos os `<a href="...pdf">`.

---

## 5. Genoa Capital — 72 cartas, 2020-2026

**Pagina unica com todos os relatorios:**
```
https://www.genoacapital.com.br/relatorios.html
```

**Base dos PDFs:** `https://www.genoacapital.com.br/docs/`

**Exemplos:**
- `CartaMensalGenoaCapital_Fev26.pdf`
- `CartaMensalGenoaCapital_Jul20.pdf`

**Como replicar:** Scrape da pagina, extrair links `.pdf`.

---

## 6. Legacy Capital (Felipe Guerra) — 59 cartas, 2021-2025

**URL padrao previsivel — WordPress uploads:**
```
https://www.legacycapital.com.br/wp-content/uploads/{YYYYMM}_Legacy_Capital.pdf
https://www.legacycapital.com.br/wp-content/uploads/{YYYYMM}_Carta-Mensal.pdf
```

**Tambem disponivel via Azure Blob:**
```
https://legacywebsite.blob.core.windows.net/site/cartamensal/{YYYY}/{YYYYMM}_Carta%20Mensal.pdf
```

**Exemplos:**
- `202501_Legacy_Capital.pdf` (padrao mais antigo)
- `202509_Carta-Mensal.pdf` (padrao mais recente)

**Como replicar:** Testar os 3 patterns acima para cada `YYYYMM` de 202101 a 202603.

---

## 7. Kinea (Marco Freire / Itau) — 23 cartas, 2021-2023

**Blog archive:**
```
https://www.kinea.com.br/blog/categoria/carta-do-gestor/
```

**URL padrao dos PDFs:**
```
https://www.kinea.com.br/wp-content/uploads/{YYYY}/{MM}/Carta-do-Gestor-{FUND}-{YYYY}-{MM}.pdf
https://www.kinea.com.br/wp-content/uploads/{YYYY}/{MM}/{FUND}_Carta-do-Gestor_{MM}-{YYYY}.pdf
```

| Fundo | Exemplos encontrados |
|-------|---------------------|
| KNCR | `KNCR_Carta-do-Gestor_08-2023.pdf` |
| KFOF | `KFOF_Carta-do-Gestor_08-2023.pdf` |

**Como replicar:** Testar as URL patterns acima para fundos `Atlas-II, Chronos, IPV, KNCR, KFOF, Kan`.

---

## 8. Mar Asset — 22 cartas

**Pagina com documentos:**
```
https://www.marasset.com.br/conteudo-mar/
```

**Como replicar:** Scrape da pagina, filtrar por secao "Cartas", extrair links dos PDFs dentro de `div.document--term--item`.

**Exemplos:**
- `https://www.marasset.com.br/document/nov-2025-quando-os-ceticos-empurram-os-genios/`
- `https://www.marasset.com.br/document/jan-25-pregando-no-deserto/`

---

## 9. Squadra Investimentos — 19 cartas, 2010-2025

**Pagina de cartas:**
```
https://www.squadrainvest.com.br/cartas/
```

**Base dos PDFs:** `https://www.squadrainvest.com.br/wp-content/uploads/`

**Exemplos:**
- `Squadra_Carta_1S25.pdf`
- `carta-2018.pdf`
- `carta-2011semestre1.pdf`

**Como replicar:** Scrape da pagina, extrair todos os `<h2><a href="...pdf">`.

---

## 10. Alaska Asset (Henrique Bredda) — 18 cartas, 2015-2023

**Pagina de cartas:**
```
https://www.alaska-asset.com.br/cartas/
```

**Base dos PDFs:** `https://www.alaska-asset.com.br/pdf/cartas/`

**Exemplos:**
- `2023.pdf`
- `semestre1_2022.pdf`
- `trimestre1_2015.pdf`

**Como replicar:** Scrape da pagina. Buscar `div.entry` > `div.body` > links `<a>` para PDFs (excluir "Mensais").

---

## 11. Santander Asset — 11 cartas, recente

**Pagina de carta mensal:**
```
https://www.santanderassetmanagement.com.br/conteudos/carta-mensal
```

**Exemplos:**
- `https://www.santanderassetmanagement.com.br/content/view/20280/file/Carta%20Mensal%20Fevereiro.pdf`

**Como replicar:** Scrape da pagina, extrair links `.pdf`.

---

## 12. Ibiuna (Mario Toros) — 2 cartas, latest

**URL direta (somente versao mais recente):**
```
https://www.ibiunainvest.com.br/wp-content/uploads/fundos/RelatorioMensal_IbiunaHedgeSTHFICFIM.pdf
https://www.ibiunainvest.com.br/wp-content/uploads/fundos/RelatorioMensal_IbiunaHedgeFICFIM.pdf
```

**Nota:** Ibiuna sobrescreve o PDF todo mes (URL fixa). Para historico, seria necessario Wayback Machine ou scraping mensal recorrente.

---

## 13. Dynamo — 1 carta

**Pagina de cartas:**
```
https://www.dynamo.com.br/pt/cartas-dynamo
```

**Exemplo:** `https://www.dynamo.com.br/wp-content/uploads/2026/01/Carta-Dynamo-127.pdf`

**Nota:** Site mudou estrutura recentemente. PDFs sao trimestrais e estao linkados na pagina, mas o HTML requer parsing mais sofisticado.

---

## Gestoras que NAO conseguimos baixar (JS-rendered / protegidos)

| Gestora | Site | Problema |
|---------|------|----------|
| **SPX Capital** | spxcapital.com.br | Site JS-rendered, PDFs nao expostos no HTML |
| **Guepardo** | guepardoinvest.com.br/cartas-da-gestora/ | Site mudou estrutura (Elementor) |
| **Artica Capital** | artica.capital/cartas-asset/ | Blog JS-rendered (Jet Engine) |
| **Dahlia Capital** | dahliacapital.com.br/nossas-cartas | Wix JS-rendered |
| **Adam Capital** | adamcapital.com.br | Bot protection ativo |
| **Bahia Asset** | bahiaasset.com.br/carta-do-gestor/ | JS-rendered + disclaimer |

**Para essas, seria necessario Selenium/Playwright para renderizar o JavaScript.**

---

## Fontes suplementares (nao scrapeadas ainda)

| Fonte | URL | Descricao |
|-------|-----|-----------|
| **XP Opiniao Consolidada** | conteudos.xpi.com.br/fundos.../relatorios/ | PDF mensal com centenas de gestoras |
| **Gorila AI Summaries** | gorila.com.br/blog/category/carta-do-gestor | Resumos AI com links para originais |
| **Viagem Lenta** | viagemlenta.com/cartas-dos-gestores-... | Google Drive com PDFs por gestora |
| **Empiricus** | empiricus.com.br/conteudo-extra/cartas-dos-gestores/ | Portal com cartas selecionadas |
| **Acionista** | acionista.com.br | Blog com cartas republicadas |
| **Telegram** | t.me/cartas_dos_fundos | Canal com cartas compartilhadas |

---

## Referencia: Projeto Open Source

**Ian Araujo — bert-finance-sentiment**
- GitHub: `github.com/ianaraujo/bert-finance-sentiment`
- 707 cartas de 12 gestoras (1999-2025)
- Modelo de sentimento: `huggingface.co/ianaraujo/bert-portuguese-asset-management-sentiment`

---

## Como rodar os scripts

```bash
cd /path/to/osira

# Wave 1: Verde, Legacy, Kinea, Dynamo, Kapitalo, Ace, Genoa, Dahlia, Adam
.venv/bin/python scripts/download_cartas.py

# Wave 2: Guepardo, Alaska, IP Capital, Squadra, Artica, Mar Asset, Santander, SPX, Ibiuna, Legacy extended
.venv/bin/python scripts/download_cartas_wave2.py
```

Os PDFs ficam em `data/cartas/{gestora}/` e o indice em `data/cartas/cartas.db` (SQLite).
