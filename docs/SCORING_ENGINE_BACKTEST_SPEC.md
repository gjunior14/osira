# Osira v0.8.6 — Scoring Engine Specification for Backtest

**Para:** Henrique (dev), Enzo (dev)
**De:** Gerson
**Data:** 20/03/2026
**Versao:** Completa — todas as formulas, inputs, fallbacks, e test vectors

---

## 0. Funcao Utilitaria

Todas as formulas usam `clamp`:

```python
def clamp(value, lo=0.0, hi=100.0):
    return max(lo, min(hi, value))
```

Exceto onde indicado com `clamp(x, 10, 100)` — floor diferente de zero.

---

## 1. juro_real — Atratividade do Juro Real

**Formula:** Sigmoid logistica centrada em 6.5%.

```
real_rate = SELIC_meta - IPCA_exp
score = clamp(100 / (1 + exp(-1.2 * (real_rate - 6.5))))
```

**Inputs:**
| Variavel | Fonte | Serie/Ticker | Fallback |
|----------|-------|-------------|----------|
| SELIC_meta | BCB SGS | 432 | 0.0 |
| IPCA_exp | BCB Focus | IPCA EOY | `ipca_12m` (SGS 433) |

**Comportamento:**
| real_rate | score |
|-----------|-------|
| 2.0% | ~0.5 |
| 4.0% | ~4.2 |
| 6.5% | 50.0 |
| 9.0% | ~95.8 |
| 11.25% | ~99.7 |

**Test vector (MockData):**
- SELIC=15.0%, Focus IPCA=3.75% → real_rate=11.25%
- score = 100 / (1 + exp(-1.2 * 4.75)) = 100 / (1 + 0.00335) = **99.7**

---

## 2. easing — Potencial de Afrouxamento

**Formula:** 60% magnitude + 40% velocidade.

```
cuts = SELIC_meta - Focus_SELIC          # positivo = cortes esperados
max_cycle = max(5.0, SELIC_meta * 0.45)  # teto dinamico
magnitude = clamp(cuts / max_cycle * 100)

velocity_bps = cuts * 100 / 8            # bps por reuniao (8 COPOMs/ano)
velocity_signal = clamp(velocity_bps / 75 * 100)   # 75bps = teto

easing = clamp(0.60 * magnitude + 0.40 * velocity_signal)
```

**Inputs:**
| Variavel | Fonte | Serie/Ticker |
|----------|-------|-------------|
| SELIC_meta | BCB SGS | 432 |
| Focus_SELIC | BCB Focus | SELIC EOY (Top5) |

**IMPORTANTE — Comportamento durante TIGHTENING:**
Quando Focus_SELIC > SELIC_meta (mercado espera **alta** de juros):
- `cuts` fica negativo
- `magnitude` clampa a **0**
- `velocity_signal` clampa a **0**
- **easing = 0.0** (score minimo)

NAO existe score de tightening dedicado. O aperto monetario e capturado por:
1. easing = 0 (aqui)
2. ciclo_br.monetary_signal cai para 15-30 (secao 10)
3. pre_tilt = 0 ou baixo (secao 13)

**Test vector (MockData):**
- SELIC=15.0%, Focus=12.25% → cuts=2.75pp
- max_cycle = max(5.0, 6.75) = 6.75
- magnitude = clamp(2.75/6.75*100) = **40.7**
- velocity = 275bps/8 = 34.4bps/reuniao
- velocity_signal = clamp(34.4/75*100) = **45.8**
- easing = 0.60*40.7 + 0.40*45.8 = **42.8**

**Test vector (Tightening — ex: 2022):**
- SELIC=13.75%, Focus=14.25% → cuts=-0.50pp
- magnitude = clamp(-0.50/... * 100) = **0.0**
- velocity_signal = **0.0**
- easing = **0.0**

---

## 3. fiscal — Saude Fiscal Composta

**Formula:** 4 componentes com pesos configuraveis.

```
fiscal = 0.30 * cds_signal
       + 0.25 * letters_fiscal
       + 0.25 * divida_signal
       + 0.20 * ipca_signal
```

### 3.1 CDS Signal (com fallback chain)

**Prioridade 1 — CDS 5Y Brasil:**
| CDS (% a.a.) | Signal |
|--------------|--------|
| < 1.20 | 80 |
| < 1.80 | 60 |
| < 2.50 | 40 |
| < 3.50 | 20 |
| >= 3.50 | 5 |

**Prioridade 2 — EMBI Brasil** (se CDS indisponivel):
| EMBI (bps) | Signal |
|-----------|--------|
| < 150 | 75 |
| < 220 | 55 |
| < 300 | 35 |
| >= 300 | 15 |

**Prioridade 3 — Gap Cambial** (se EMBI indisponivel):
```
fx_gap_pct = (Focus_Cambio / PTAX - 1) * 100
cds_signal = clamp(50 - fx_gap_pct * 10)
```

### 3.2 Letters Fiscal
| Sentimento | Score |
|-----------|-------|
| dovish | 75 |
| otimista | 65 |
| neutro | 50 |
| hawkish | 25 |
| preocupado | 20 |

Default se indisponivel: **50.0**

### 3.3 Divida/PIB Signal
```
divida_signal = clamp((100 - divida_bruta_pib) / 40 * 100)
```
| Divida/PIB | Signal |
|-----------|--------|
| 60% | 100 |
| 78% | 55 |
| 90% | 25 |
| 100% | 0 |

### 3.4 IPCA Deviation
```
ipca_dev = abs(IPCA_12m - 3.0)     # meta = 3.0%
ipca_signal = clamp(100 - ipca_dev * 33)
```

**Inputs:**
| Variavel | Fonte | Serie/Ticker |
|----------|-------|-------------|
| CDS_5Y | BCB SGS | 21619 |
| EMBI_Brasil | BCB SGS | 3545 |
| PTAX | BCB SGS | 1 |
| Focus_Cambio | BCB Focus | Cambio EOY |
| divida_bruta_pib | BCB SGS | 4537 |
| IPCA_12m | BCB SGS | 433 (acumulado 12m) |
| letters_fiscal | Cartas gestoras | YAML config |

**Test vector (MockData):**
- CDS=6.12% → cds_signal = **5.0**
- Letters hawkish → letters_fiscal = **25.0**
- Divida=92.74% → divida_signal = clamp(7.26/40*100) = **18.2**
- IPCA=4.44%, dev=1.44 → ipca_signal = clamp(100-47.5) = **52.5**
- fiscal = 0.30*5 + 0.25*25 + 0.25*18.2 + 0.20*52.5 = **22.8**

---

## 4. ntnb_composite — NTN-B Composto (regime-adaptativo)

**Formula:** Pesos mudam conforme regime.

```
move_signal = clamp(100 - (MOVE - 80) * 2)
ntnb = w[0]*juro_real + w[1]*easing + w[2]*fiscal + w[3]*move_signal
```

| Regime | w_juro_real | w_easing | w_fiscal | w_move |
|--------|-------------|----------|----------|--------|
| risk_off | 0.30 | 0.15 | **0.55** | 0.00 |
| risk_on | 0.35 | **0.45** | 0.20 | 0.00 |
| neutral | 0.40 | 0.25 | 0.20 | 0.15 |
| stagflation | 0.40 | 0.25 | 0.20 | 0.15 |

**NOTA:** Calculado APOS regime detection (depende do regime).

**Input:** MOVE Index (Yahoo ^MOVE)

**Test vector (MockData, regime=risk_off):**
- move=98 → move_signal = clamp(100-36) = 64.0
- ntnb = 0.30*99.7 + 0.15*42.8 + 0.55*22.8 + 0.00*64.0
       = 29.91 + 6.42 + 12.54 + 0 = **48.9**

---

## 5. rv_br — Renda Variavel Brasil

**Formula:**

```
letters_br = clamp(50 + letters_raw * 70)    # [-1,+1] → [0,100] steep
ibov_val = clamp(100 - ibov_pl_percentile)
fiscal_signal = clamp(fiscal_score)

easing_pct = max(0, (SELIC - Focus_SELIC) / SELIC)
easing_signal = clamp(easing_pct * 200)
pib_signal = clamp(Focus_PIB * 22)
focus_macro = 0.50 * pib_signal + 0.50 * easing_signal

ma200_sig = clamp(55 - (Ibov / Ibov_MA200 - 1) * 400)
ma100_sig = clamp(55 - (Ibov / Ibov_MA100 - 1) * 400)
ma_val = 0.60 * ma200_sig + 0.40 * ma100_sig

rv_br = clamp(0.35*letters_br + 0.05*focus_macro + 0.10*ibov_val
              + 0.20*fiscal_signal + 0.30*ma_val)

# Penalidade composta quando fiscal < 40
if fiscal_score < 40:
    f_stress = (40 - fiscal_score) / 40
    if ma_val < 40:
        rv_br -= f_stress * (40 - ma_val) / 40 * 20
    if letters_br < 50:
        rv_br -= f_stress * (50 - letters_br) / 50 * 12
    rv_br = max(0, rv_br)
```

**Inputs:**
| Variavel | Fonte | Serie/Ticker |
|----------|-------|-------------|
| letters_equities_br | Cartas gestoras | YAML [-1, +1] |
| ibov_pl_percentile | Manual | Percentil historico do P/L Ibov |
| Focus_PIB | BCB Focus | PIB Total EOY |
| Ibovespa | Yahoo | ^BVSP |
| Ibov_MA200 | Yahoo | MA200 de ^BVSP |
| Ibov_MA100 | Yahoo | MA100 de ^BVSP |
| fiscal_score | Score 3 | upstream |

**Test vector (MockData):**
- letters=-0.20 → letters_br=36.0, ibov_val=65.0, fiscal=22.8
- easing_pct=0.183 → easing_signal=36.7, pib_signal=42.2 → focus_macro=39.5
- ma200_sig=12.1, ma100_sig=37.9 → ma_val=22.4
- Base: 0.35*36+0.05*39.5+0.10*65+0.20*22.8+0.30*22.4 = 32.4
- Penalidade: f_stress=0.43 → -3.78 (MA) -1.44 (letters) = **27.2**

---

## 6. rv_dm — Renda Variavel Desenvolvidos

```
letters_dm = clamp((letters_raw + 1) / 2 * 100)   # linear [-1,+1] → [0,100]
cape_signal = clamp(100 - cape_percentile)
vix_signal: < 15 → 70, < 25 → 50, else → clamp(30 - (VIX-25)*2)
ma_val = clamp(55 - (SP500 / SP500_MA200 - 1) * 300)
cdi_opp = clamp(100 - CDI * 5, lo=10, hi=100)     # FLOOR = 10!

rv_dm = clamp(0.28*letters + 0.23*cape + 0.23*ma + 0.16*vix + 0.10*cdi_opp)
```

**Test vector:** letters=-0.39→30.5, cape_pct=85→15.0, VIX=29.49→21.0, ma=23.5, cdi=14.90→25.5 → **23.3**

---

## 7. rv_em — Renda Variavel Emergentes

```
dxy_inv = clamp(100 - (DXY - 90) * 4)
letters_intl = clamp((letters_raw + 1) / 2 * 100)
cape_em_signal = clamp(100 - cape_em_percentile)
iron_signal = clamp((iron - 60) / 100 * 100)
copper_signal = clamp((copper - 3.0) / 2.0 * 100)
china_signal = 0.60 * iron_signal + 0.40 * copper_signal
em_momentum = clamp(50 + (EEM/SPY_now / EEM/SPY_6m - 1) * 500)
cdi_opp = clamp(100 - CDI * 5, lo=10, hi=100)

rv_em = clamp(0.22*dxy_inv + 0.22*letters + 0.18*cape_em + 0.14*china
              + 0.14*em_mom + 0.10*cdi_opp)
```

**Test vector:** dxy_inv=62.4, letters=50.0, cape_em=55.0, china=51.8, em_mom=100.0, cdi_opp=25.5 → **58.4**

---

## 8. geo — Tilt Geografico

0 = tudo Brasil, 100 = tudo exterior.

```
fx_val = clamp(50 + (DXY - 100) * 2)

# Momentum relativo Ibov vs SP500 em USD (12m)
ibov_ret = (Ibov/Ibov_12m) * (BRL/BRL_12m) - 1
sp500_ret = SP500/SP500_12m - 1
rel_momentum = ibov_ret - sp500_ret
# > 0.20→70 | > 0.10→60 | > -0.05→45 | > -0.15→35 | else→20

# Spread real BR-US
br_real = SELIC - IPCA_exp
us_real = Treasury_10Y - 2.5        # 2.5% = inflacao US hardcoded
spread = br_real - us_real
spread_signal = clamp(80 - spread * 8)

# Fluxo cambial BCB 30d (USD bi)
# > +5→25 | > 0→40 | > -5→55 | > -15→70 | <= -15→85

geo = clamp(0.30*fx_val + 0.25*opp + 0.30*spread + 0.15*fluxo)
```

**Inputs adicionais:**
| Variavel | Fonte | Serie/Ticker |
|----------|-------|-------------|
| Ibov_12m_ago | Yahoo | ^BVSP 1y ago |
| SP500_12m_ago | Yahoo | ^GSPC 1y ago |
| BRL_12m_ago | Yahoo | BRL=X 1y ago |
| fluxo_cambial_30d | BCB SGS | 23075 (soma 30d) |
| Treasury_10Y | Yahoo | ^TNX |

**Test vector:** fx_val=48.8, opp=35.0, spread=3.0, fluxo=70.0 → **34.8**

---

## 9. cred_hg — Credito High Grade

```
ratio = ida_di_spread / ida_di_hist_avg
spread_signal = clamp((ratio - 1) * 200 + 50)

avg_default = (inadimpl_pf + inadimpl_pj) / 2
inadimp_signal = clamp(130 - avg_default * 20)

# Spread credito vs NTN-B
credito_nominal = SELIC + ida_di_spread/100
ntnb_nominal = IPCA_exp + (SELIC - IPCA_exp)    # = SELIC
spread_vs_ntnb = credito_nominal - ntnb_nominal
# > 3.0→85 | > 2.0→65 | > 1.0→45 | > 0→30 | else→10

cred_hg = clamp(0.45*spread + 0.30*inadimpl + 0.25*ntnb_spread)
```

**Test vector:** spread_signal=72.9, inadimpl=33.0, ntnb_spread=45.0 → **54.0**

---

## 10. ciclo_br — Ciclo Brasileiro

```
ibc_signal = clamp(50 + IBC_Br * 12)

# Monetario: delta SELIC 6 meses
delta_6m = SELIC_meta - SELIC_6m_ago
# < -1.50pp → 75 | < -0.50pp → 60 | < +0.50pp → 45 | < +1.50pp → 30 | >= +1.50pp → 15

# FALLBACK (se selic_6m_ago indisponivel):
# monetary_signal = clamp(80 - (real_rate - 2) * 7)

avg_default = (inadimpl_pf + inadimpl_pj) / 2
inadimp_signal = clamp(130 - avg_default * 20)
pib_signal = clamp(Focus_PIB * 22)

ciclo_br = clamp(0.30*ibc + 0.35*monetary + 0.20*inadimpl + 0.15*pib)
```

**IMPORTANTE para TIGHTENING:**
- SELIC subindo → delta_6m **positivo** → monetary_signal **baixo** (15-30)
- Em ciclo de alta forte (+2pp em 6m), monetary = 15 → ciclo_br despenca
- Isso alimenta regime detection: ciclo_br < 35 + juro_real > 70 → **stagflation**

**Inputs:**
| Variavel | Fonte | Serie/Ticker |
|----------|-------|-------------|
| IBC_Br | BCB SGS | 24363 |
| SELIC_6m_ago | BCB SGS 432 | ~130 dias uteis atras |
| inadimplencia_pf | BCB SGS | 21082 |
| inadimplencia_pj | BCB SGS | 21083 |

**Test vector:** ibc=54.8, monetary=45.0, inadimpl=33.0, pib=42.2 → **45.1**

---

## 11. ciclo_us — Ciclo Americano

```
spread_2s10s = T10Y - T2Y
curve = clamp(40 + spread_2s10s * 30)
move = clamp(80 - (MOVE - 80))
policy = clamp(100 - T13W * 16)
hy = clamp(100 - HY_spread * 13)
ism = clamp((ISM_PMI - 30) / 30 * 100)
sahm: < 0.3→70 | < 0.5→50 | < 0.8→30 | >= 0.8→10

ciclo_us = clamp(0.25*curve + 0.20*move + 0.15*policy + 0.15*hy + 0.15*ism + 0.10*sahm)
```

**Inputs:**
| Variavel | Fonte | Serie/Ticker |
|----------|-------|-------------|
| Treasury_10Y | Yahoo | ^TNX |
| Treasury_2Y | Yahoo | Derivado de ^FVX - 0.10 |
| Treasury_13W | Yahoo | ^IRX |
| MOVE | Yahoo | ^MOVE |
| HY_spread | Manual/Bloomberg | HY OAS |
| ISM_PMI | FRED | NAPM |
| Sahm_Rule | FRED | SAHMREALTIME |

**Test vector:** curve=55.6, move=62.0, policy=42.9, hy=41.5, ism=65.0, sahm=70.0 → **55.7**

---

## 12. ouro — Score de Ouro

```
real_rate = clamp(100 - (TIPS_10Y + 1) * 25)

vix_norm = clamp((VIX - 12) / 40 * 100)
move_norm = clamp((MOVE - 60) / 100 * 100)
cds_norm = clamp((CDS_5Y - 0.8) / 4 * 100)
stress = 0.50*vix_norm + 0.30*move_norm + 0.20*cds_norm

inflation = clamp((CPI_US_YoY - 2.0) * 40)
dxy_inv = clamp(100 - (DXY - 90) * 4)
momentum = clamp(50 + (Gold/Gold_6m - 1) * 200)

ma200_sig = clamp(55 - (Gold/Gold_MA200 - 1) * 350)
ma100_sig = clamp(55 - (Gold/Gold_MA100 - 1) * 350)
ma_val = 0.60*ma200_sig + 0.40*ma100_sig

ouro = clamp(0.15*real_rate + 0.15*stress + 0.10*inflation
             + 0.10*dxy_inv + 0.15*momentum + 0.35*ma_val)
```

**Inputs:**
| Variavel | Fonte | Serie/Ticker |
|----------|-------|-------------|
| TIPS_10Y | FRED | DFII10 |
| CPI_US_YoY | FRED | CPIAUCSL (derivado) |
| Gold | Yahoo | GC=F |
| Gold_MA200, MA100 | Yahoo | MAs de GC=F |
| Gold_6m_ago | Yahoo | GC=F 6m ago |

**Test vector:** real_rate=28.8, stress=53.3, inflation=32.0, dxy=62.4, momentum=72.6, ma_val=13.5 → **37.4**

---

## 13. pre_tilt — Atratividade Pre-Fixado

```
# VETO ABSOLUTO: fiscal <= 25 → pre_tilt = 0
if fiscal_score <= 25:
    return 0.0

cuts_bps = (SELIC - Focus_SELIC) * 100
speed = cuts_bps / 8               # bps por reuniao
speed_signal = clamp(speed / 75 * 100)
curve_signal = clamp(cuts_bps / 5)
fiscal_floor = clamp((fiscal_score - 25) / 50 * 100)
letters_pre = 50.0                  # neutro (nao implementado ainda)

pre_tilt = clamp(0.40*speed + 0.30*curve + 0.20*fiscal_floor + 0.10*letters)
```

**Comportamento durante TIGHTENING:** cuts_bps negativo → speed=0, curve=0 → pre_tilt muito baixo ou zero.

**Test vector (MockData):** fiscal=22.8 ≤ 25 → **VETO** → **0.0**

---

## 14. Regime Detection — 4 Estados

Cascata de prioridade (primeiro match ganha):

```
equity_composite = 0.40*rv_br + 0.35*rv_dm + 0.25*rv_em

# 1. STAGFLATION (mais perigoso)
if juro_real > 70 AND ciclo_br < 35 AND fiscal < 40:
    return 'stagflation'

# 2. HARD RULES (independentes de scores)
if VIX > 40:                                       return 'risk_off'
if VIX > 28 AND (Ibov < 0.92*MA200 OR SP < 0.92*MA200): return 'risk_off'
if CDS_5Y > 4.5 AND fiscal < 30:                   return 'risk_off'

# 3. SCORE RULES
if equity_composite < 20:                           return 'risk_off'
if VIX > 28 AND equity_composite < 30:              return 'risk_off'
if fiscal < 25 AND equity_composite < 30:           return 'risk_off'

# 4. RISK_ON HARD
if VIX < 18 AND Ibov > 1.03*MA200 AND SP > 1.03*MA200: return 'risk_on'

# 5. RISK_ON SCORE
if equity_composite > 60 AND VIX < 22:              return 'risk_on'

# 6. DEFAULT
return 'neutral'
```

**Test vector (MockData):**
- equity_composite = 0.40*27.2 + 0.35*23.3 + 0.25*58.4 = 33.6
- Stagflation: 99.7>70 ✓, 45.1<35 ✗ → NAO
- Hard 1: VIX 29.49>40 ✗
- Hard 2: VIX 29.49>28 ✓, Ibov/MA200=1.107>0.92 ✗ → NAO
- **Hard 3: CDS 6.12>4.5 ✓, fiscal 22.8<30 ✓ → RISK_OFF**

---

## 15. Resumo dos Test Vectors (MockData)

| Score | Valor | Signal |
|-------|-------|--------|
| juro_real | **99.7** | STRONG_BULLISH |
| easing | **42.8** | NEUTRAL |
| fiscal | **22.8** | BEARISH |
| rv_br | **27.2** | BEARISH |
| rv_dm | **23.3** | BEARISH |
| rv_em | **58.4** | NEUTRAL |
| geo | **34.8** | BEARISH |
| cred_hg | **54.0** | NEUTRAL |
| ciclo_br | **45.1** | NEUTRAL |
| ciclo_us | **55.7** | NEUTRAL |
| ouro | **37.4** | BEARISH |
| pre_tilt | **0.0** | STRONG_BEARISH (veto) |
| ntnb | **48.9** | NEUTRAL |
| **Regime** | **risk_off** | CDS hard rule |

**MockData inputs (snapshot 08/03/2026):**
```
SELIC=15.0  Focus_SELIC=12.25  Focus_IPCA=3.75  Focus_PIB=1.92
IPCA_12m=4.44  CDI=14.90  CDS_5Y=6.12  Divida/PIB=92.74
IBC=0.4  Inadimpl_PF=6.2  Inadimpl_PJ=3.5  Fluxo=-5.2
SELIC_6m_ago=15.25  Focus_Cambio=5.45  PTAX=5.29

Ibov=179365  Ibov_MA200=162000  Ibov_MA100=172000  Ibov_12m=155000
SP500=6740  SP500_MA200=6100  SP500_12m=5800
VIX=29.49  DXY=99.41  MOVE=98  T10Y=4.13  T2Y=3.61  T13W=3.57
HY_spread=4.50  Gold=2950  Gold_MA200=2550  Gold_MA100=2780
Gold_6m=2650  EEM=44.5  SPY=570  EEM_6m=41  SPY_6m=590
Iron=108  Copper=4.15  BRL=5.24  BRL_12m=5.50

TIPS_10Y=1.85  CPI_US_YoY=2.8  ISM=49.5  Sahm=0.25
ANBIMA_spread=195  ANBIMA_hist_avg=175
CAPE=33  CAPE_pct=85  US_real_rate=0.5
Ibov_PL_pct=35  CAPE_EM_pct=45
Letters_BR=-0.20  Letters_US=-0.39  Letters_fiscal=hawkish
```

---

## 16. Fontes de Dados Historicos para Backtest (2016-2026)

### BCB (api.bcb.gov.br/dados/serie/bcdata.sgs.{SERIE}/dados)
| Serie | Variavel | Periodicidade |
|-------|----------|--------------|
| 432 | SELIC Meta | diaria |
| 433 | IPCA acumulado 12m | mensal |
| 4389 | CDI | diaria |
| 1 | PTAX | diaria |
| 21619 | CDS 5Y Brasil | diaria |
| 3545 | EMBI Brasil | diaria |
| 4537 | Divida Bruta/PIB | mensal |
| 24363 | IBC-Br | mensal |
| 21082 | Inadimplencia PF | mensal |
| 21083 | Inadimplencia PJ | mensal |
| 23075 | Fluxo Cambial (acumular 30d) | diaria |

### BCB Focus (olinda.bcb.gov.br/expectativas)
| Variavel | Endpoint |
|----------|----------|
| Focus SELIC | /ExpectativasMercadoSelic |
| Focus IPCA | /ExpectativasMercadoAnuais (IPCA) |
| Focus PIB | /ExpectativasMercadoAnuais (PIB Total) |
| Focus Cambio | /ExpectativasMercadoAnuais (Taxa de cambio) |

### Yahoo Finance (yfinance Python)
| Ticker | Variavel |
|--------|----------|
| ^BVSP | Ibovespa (+ MA200, MA100, 12m ago) |
| ^GSPC | S&P 500 (+ MA200, 12m ago) |
| ^VIX | VIX |
| DX-Y.NYB | DXY |
| ^TNX | Treasury 10Y |
| ^IRX | Treasury 13W |
| ^MOVE | MOVE Index |
| GC=F | Gold (+ MA200, MA100, 6m ago) |
| BRL=X | USD/BRL |
| EEM | iShares EM ETF |
| SPY | SPDR S&P 500 ETF |
| TIO=F | Iron Ore |
| HG=F | Copper |

### FRED (fredapi Python)
| Serie | Variavel |
|-------|----------|
| DFII10 | TIPS 10Y |
| CPIAUCSL | CPI US (derivar YoY) |
| NAPM | ISM PMI |
| SAHMREALTIME | Sahm Rule |

### Manuais (precisam de source alternativa para backtest)
| Variavel | Sugestao |
|----------|---------|
| CAPE / CAPE_percentile | Shiller site ou multpl.com |
| CAPE_EM_percentile | StarCapital ou MSCI |
| Ibov_PL_percentile | Economatica ou calcular manual |
| HY_spread | FRED BAMLH0A0HYM2 (ICE BofA HY OAS) |
| ANBIMA spreads | config/anbima_spreads.json |
| Letters consensus | Cartas gestoras (nosso dataset de 1252 cartas) |

---

## 17. Signal e Bucket Labels

| Score Range | Signal Label |
|-------------|-------------|
| 0 - 20 | STRONG_BEARISH |
| 20 - 40 | BEARISH |
| 40 - 60 | NEUTRAL |
| 60 - 80 | BULLISH |
| 80 - 100 | STRONG_BULLISH |

| Score Range | Juro Bucket |
|-------------|------------|
| 0 - 35 | bearish |
| 35 - 65 | neutral |
| 65 - 100 | bullish |

| Score Range | Geo Bucket |
|-------------|-----------|
| 0 - 35 | br_heavy |
| 35 - 65 | balanced |
| 65 - 100 | us_heavy |
