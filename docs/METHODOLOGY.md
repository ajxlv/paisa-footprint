# Methodology

Paisa Footprint measures **financed emissions**: the share of a company's greenhouse-gas emissions that an investor finances by owning part of it. It follows the **PCAF** standard (Partnership for Carbon Accounting Financials) for listed equity, and uses only companies' own **BRSR** (Business Responsibility and Sustainability Report) filings to NSE for emissions.

## The formulas

For each holding *h* in a portfolio:

```
attribution_h        = value_h / EVIC_company                 (must be 0 < a ≤ 1)
financed_emissions_h = attribution_h × (Scope 1 + Scope 2)     [tCO2e]
```

For the portfolio:

```
financed_emissions = Σ financed_emissions_h                    (covered holdings only)  [tCO2e]
coverage           = covered_value / total_value × 100                                  [%]
carbon_footprint   = financed_emissions / covered_value × 1e7  [tCO2e per ₹ crore invested]
WACI               = Σ (value_h / waci_value) × (S1 + S2) / (revenue / 1e7)
                                                               [tCO2e per ₹ crore of revenue]
data_quality       = value-weighted mean of holding scores (1 or 2)
```

₹1 crore = ₹1,00,00,000 = 1e7 rupees.

## EVIC

**EVIC** (enterprise value including cash) is market capitalisation at fiscal year end plus total debt (plus minority interest). PCAF uses EVIC rather than market cap because a company is financed by both its shareholders and its lenders. Dividing by market cap alone would hand shareholders all of the emissions and leave none for debt holders, overstating an equity investor's share for heavily indebted companies.

> **Status:** this repository has **no real EVIC data yet**. The portfolio calculator accepts EVIC you enter, and the demo uses clearly labelled illustrative values. Real EVIC (NSE market cap + borrowings from financial results) is the week-2 milestone.

## WACI

**WACI** (weighted average carbon intensity) is each holding's Scope 1+2 per ₹ crore of revenue, weighted by its share of the portfolio. It needs no EVIC, so it is available even where EVIC is missing. A holding whose revenue fails validation (rule V2) is left out of WACI and the WACI universe's share of the portfolio is shown next to it.

## PCAF data-quality score

| Score | Meaning | How we assign it |
|---|---|---|
| 1 | Reported emissions, verified by a third party | BRSR assurance flag = true |
| 2 | Reported emissions, not verified | assurance flag = false **or not filed** |
| 3–5 | Estimated from physical activity, revenue or sector averages | **Not used.** Holdings without reported emissions are uncovered, not estimated |

Lower is better. The portfolio score is the value-weighted average over covered holdings.

## What is covered

A holding is **covered** only if its company filed Scope 1 and Scope 2 in BRSR, the company is not excluded, there is no error-severity issue on its emissions, an EVIC is available, and its attribution is between 0 and 1. Every other holding is **uncovered** and is listed with its reason. Coverage is always shown next to the footprint, and low coverage is never hidden.

## Validators

Every filing passes through validators built from real errors found in the fixture filings:

| Rule | Check | Severity | Action |
|---|---|---|---|
| V1 | Emissions tagged `MtCO2e` | info (warning if implied intensity > 50,000 t/₹ crore) | Read as metric tonnes |
| V2 | `RevenueFromOperations` below ₹10 lakh | error | Intensity marked untrustworthy; excluded from WACI; not rescaled |
| V3 | Two revenue fields differ by more than 2× | warning | Flag for review |
| V4 | Zero Scope 1 and 2 in a year next to a non-zero year | warning | Treated as missing (None) |
| V5 | Scope 1 or 2 changes more than 2× year on year | warning | Flag only, never corrected |
| V6 | Fiscal year does not end 31 March | info | Dates carried through as filed |
| V7 | Holding ISIN/symbol matches no company | — | Holding listed as uncovered |
| V9 | Company marks GHG disclosure "not applicable" | info | Excluded from emissions |
| V10 | Reported intensity ≠ (S1+S2)/revenue by more than 1% | warning | Flag for review |

V8 (fund weights summing to 95–105% of NAV) needs AMC holdings files and arrives with fund ingestion.

## Principles

- **Missing means unknown.** An absent figure is `None`, never zero.
- **Flag, don't guess.** Only two fixes are automatic (V1 unit reading, V4 zero-as-missing). Everything else is flagged and left as filed.
- **Every number is traceable** to its source file, XBRL element, context, period, unit and the transformation applied.
- **No estimation.** Non-reporting companies are a coverage gap, not a modelled number.

## In scope / out of scope

**In scope:** Scope 1 and Scope 2 from BRSR; PCAF listed-equity attribution; carbon footprint; WACI; data-quality scores 1–2.

**Out of scope (for now):** Scope 3 (reported by too few companies and too inconsistently to attribute), ESG ratings, "green" recommendations, return predictions, and ML estimates for non-reporters.

## Known limitations

1. **No real holdings data.** Mutual-fund portfolios (AMC monthly disclosures) are not ingested yet; demo portfolios are synthetic.
2. **No real EVIC data.** Market cap and debt are not ingested yet; demo EVIC values are illustrative.
3. **20 filings only.** The snapshot covers 20 real FY2025-26 BRSR filings, skewed towards smaller late filers. The NSE bulk download is the next step.
4. **Scope 3 excluded.**
5. **Non-reporters are uncovered, not estimated**, so coverage can be low.
6. **Revenue is taken from BRSR.** V2 catches scale errors, but a second revenue source (financial results) is needed to correct them.
