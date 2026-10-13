# Worked example: synthetic portfolio A, by hand

> **Illustrative data, not real market data.** The holdings and EVIC values below are made up
> (`tests/fixtures/synthetic/portfolio_synthetic_a.csv` and `illustrative_evic.csv`). The emissions
> and revenue figures are real: they are copied exactly from the companies' FY2025-26 BRSR filings
> in `tests/fixtures/brsr/`.

`tests/test_pcaf.py::test_worked_example_portfolio_a` asserts that the engine reproduces every
total on this page to a relative tolerance of 1e-9. If you change a number here, the test must
change with it.

## Inputs

| # | Company (ISIN) | Value invested | Illustrative EVIC | Scope 1 (t, as filed) | Scope 2 (t, as filed) | RevenueFromOperations (₹, as filed) | Assured? |
|---|---|---|---|---|---|---|---|
| 1 | NMDC Limited (INE584A01023) | ₹6,00,00,000 (₹6 cr) | ₹60,000 cr | 112805 | 85567 | 315537000000 | Yes |
| 2 | HDFC Bank Limited (INE040A01034) | ₹15,00,00,000 (₹15 cr) | ₹15,00,000 cr | 91849.5 | 236495.41 | 3697059900000 | Yes |
| 3 | Titan Company Limited (INE280A01028) | ₹3,00,00,000 (₹3 cr) | ₹3,00,000 cr | 3878 | 21181 | 775540701954.25 | Yes |
| 4 | Fertilizers and Chemicals Travancore (INE188A01015) | ₹5,00,00,000 (₹5 cr) | ₹50,000 cr | 251188.76 | 98116.94 | 57237612476 | **No** |
| 5 | Uflex Ltd (INE516A01017) | ₹1,00,00,000 (₹1 cr) | ₹10,000 cr | 54378 | 194950 | 77784719000 | Yes |

Total invested: 6 + 15 + 3 + 5 + 1 = **₹30 crore = ₹30,00,00,000**. All five companies report
Scope 1 and Scope 2 with no error-severity issue, and all have an EVIC, so every holding is covered.

Titan files its emissions as `MtCO2e`, which rule V1 reads as metric tonnes (3,878 t, not 3,878
megatonnes). The other four file `tCO2e`. No other transformation is applied.

Revenue in ₹ crore (revenue ÷ 1e7, since ₹1 crore = ₹1,00,00,000), used for WACI:

| # | Revenue ÷ 1e7 |
|---|---|
| 1 | 315537000000 ÷ 1e7 = **31553.7** |
| 2 | 3697059900000 ÷ 1e7 = **369705.99** |
| 3 | 775540701954.25 ÷ 1e7 = **77554.070195425** |
| 4 | 57237612476 ÷ 1e7 = **5723.7612476** |
| 5 | 77784719000 ÷ 1e7 = **7778.4719** |

## Step 1: attribution = value ÷ EVIC

| # | Calculation | Attribution |
|---|---|---|
| 1 | 6 cr ÷ 60,000 cr | **0.0001** |
| 2 | 15 cr ÷ 15,00,000 cr | **0.00001** |
| 3 | 3 cr ÷ 3,00,000 cr | **0.00001** |
| 4 | 5 cr ÷ 50,000 cr | **0.0001** |
| 5 | 1 cr ÷ 10,000 cr | **0.0001** |

All are between 0 and 1, so none is rejected.

## Step 2: financed emissions = attribution × (Scope 1 + Scope 2)

| # | Scope 1 + Scope 2 | × attribution | Financed (tCO2e) |
|---|---|---|---|
| 1 | 112,805 + 85,567 = 198,372 | × 0.0001 | **19.8372** |
| 2 | 91,849.5 + 236,495.41 = 328,344.91 | × 0.00001 | **3.2834491** |
| 3 | 3,878 + 21,181 = 25,059 | × 0.00001 | **0.25059** |
| 4 | 251,188.76 + 98,116.94 = 349,305.70 | × 0.0001 | **34.93057** |
| 5 | 54,378 + 194,950 = 249,328 | × 0.0001 | **24.9328** |

**Portfolio financed emissions** = 19.8372 + 3.2834491 + 0.25059 + 34.93057 + 24.9328
= **83.2346091 tCO2e**

## Step 3: coverage

Covered value = ₹30 crore; total value = ₹30 crore. **Coverage = 100%**.

## Step 4: carbon footprint = financed ÷ covered value × 1e7

83.2346091 ÷ 300,000,000 × 10,000,000 = 83.2346091 ÷ 30 = **2.77448697 tCO2e per ₹ crore invested**

## Step 5: WACI = Σ weight × (S1+S2) ÷ revenue in crore

Weight = value ÷ total WACI value (₹30 crore; every holding has a trustworthy revenue).

| # | Weight | Intensity = (S1+S2) ÷ revenue (₹ cr) | Weight × intensity |
|---|---|---|---|
| 1 | 6/30 = 0.2 | 198372 ÷ 31553.7 = 6.2868063016 | 1.2573612603 |
| 2 | 15/30 = 0.5 | 328344.91 ÷ 369705.99 = 0.8881243985 | 0.4440621993 |
| 3 | 3/30 = 0.1 | 25059 ÷ 77554.070195425 = 0.3231165036 | 0.0323116504 |
| 4 | 5/30 = 0.1666… | 349305.70 ÷ 5723.7612476 = 61.0273009110 | 10.1712168185 |
| 5 | 1/30 = 0.0333… | 249328 ÷ 7778.4719 = 32.0535965425 | 1.0684532181 |

**WACI** = 1.2573612603 + 0.4440621993 + 0.0323116504 + 10.1712168185 + 1.0684532181
= **12.9734051465 tCO2e per ₹ crore of revenue**

## Step 6: PCAF data quality

Score 1 for assured emissions, 2 for reported but not assured. FACT is the only non-assured one.

(6 × 1 + 15 × 1 + 3 × 1 + 5 × 2 + 1 × 1) ÷ 30 = 35 ÷ 30 = **1.1667** (exactly 7/6)

## Summary

| Metric | Value |
|---|---|
| Total invested | ₹30,00,00,000 |
| Coverage | 100% |
| Financed emissions | 83.2346091 tCO2e |
| Carbon footprint | 2.77448697 tCO2e per ₹ crore invested |
| WACI | 12.9734051465 tCO2e per ₹ crore revenue |
| PCAF data quality | 1.1667 |
| Contains illustrative inputs | **Yes** (EVIC) |

Reproduce it:

```bash
pf build-snapshot --input tests/fixtures/brsr --out data/snapshots/fixtures
pf compute --portfolio tests/fixtures/synthetic/portfolio_synthetic_a.csv \
           --evic tests/fixtures/synthetic/illustrative_evic.csv \
           --snapshot data/snapshots/fixtures
```
