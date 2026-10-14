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

**EVIC** (enterprise value including cash) is, per PCAF for listed equity:

```
EVIC = market capitalisation at fiscal year end + total debt + minority interest
```

There is **no deduction for cash**, unlike the usual enterprise value. PCAF uses EVIC rather than
market cap because a company is financed by both its shareholders and its lenders. Dividing by
market cap alone would hand shareholders all of the emissions and leave none for debt holders,
overstating an equity investor's share for heavily indebted companies.

Real EVIC is loaded from a CSV (`pf compute --evic-real`, template in
`data_templates/evic_template.csv`) and checked:
- **E1**: market cap missing or ≤ 0 is an error, and the company gets no EVIC.
- **E2**: missing debt gives a *partial* EVIC (market cap only), with data quality capped at 2.
- **E3**: an `as_of_date` more than 15 months from the emissions year end is a warning.

See [EVIC_DATA_PLAN.md](EVIC_DATA_PLAN.md).

> **Status:** this repository has **no real EVIC data yet**. The demo uses clearly labelled
> illustrative values. A result is marked `contains_illustrative_inputs` unless every EVIC it used
> came from a non-illustrative file.

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
| V1 | Emissions tagged `MtCO2e` | info (warning if implied intensity > 50,000 t/₹ crore, checked only against trustworthy revenue) | Read as metric tonnes |
| V2 | `RevenueFromOperations` below ₹10 lakh and no safe correction | error | Intensity marked untrustworthy; excluded from WACI; left as filed |
| V2-fix | Same, but the other revenue field pins down a lakh/crore slip | warning | Corrected, shown with a "Corrected" chip; WACI data quality capped at 2 (see [Revenue corrections](#revenue-corrections)) |
| V3 | Two revenue fields differ by more than 2× | warning | Flag for review |
| V4 | Zero Scope 1 and 2 in a year next to a non-zero year | warning | Treated as missing (None) |
| V5 | Scope 1 or 2 changes more than 2× year on year | warning | Flag only, never corrected |
| V6 | Fiscal year does not end 31 March | info | Dates carried through as filed |
| V7 | Holding ISIN/symbol matches no company | — | Holding listed as uncovered |
| V9 | Company marks GHG disclosure "not applicable" | info | Excluded from emissions |
| V10 | Reported intensity ≠ (S1+S2)/revenue by more than 1% | warning | Flag for review |

V8 (fund weights summing to 95–105% of NAV) applies to fund portfolios; see [Funds](#funds-and-rule-v8).

**Problems vs informational notes.** Severity `error` and `warning` are *problems*: something a human should check. Severity `info` records something handled by design (MtCO2e read as tonnes, a June year end, "not applicable") and is not a problem. On the 20 fixture filings: **14 problems in 6 companies, plus 26 informational notes**.

## Assurance

We use exactly one field for PCAF data quality: the GHG-specific BRSR Core assurance attribute
`WhetherDetailsOfGreenHouseGasEmissionsAndItsIntensityIsAssuredByAssurer`. `true` scores 1;
`false`, or not filed at all, scores 2. No other assurance statement in the filing is used.

BRSR also has a separate Principle 6 question: "has an independent assessment, evaluation or
assurance been carried out by an external agency for greenhouse gas emissions?"
(`WhetherAnyIndicateIfAnyIndependentAssessmentOrEvaluationOrAssuranceHasBeenCarriedOutByAnExternalAgencyForGreenHouseGasEmissions`).
In 19 of the 20 fixture filings the two fields agree.

The exception is **Fertilizers and Chemicals Travancore (FACT)**:
- Its filing names Social Responsibility: Asia (SR Asia) as having carried out "Reasonable
  Assurance for BRSR Core". The same text appears against energy, water, waste and the
  greenhouse-gas external-agency question, and that question is answered `true`.
- But its GHG `…IsAssuredByAssurer` flag is `false`.

We follow the GHG-specific flag, so FACT scores **DQ 2**. Treating a general BRSR Core assurance
statement as GHG assurance would be an inference, and the filing itself says the GHG data point
is not assured. The conflict is listed for a hand check against FACT's assurance report.

## Revenue corrections

Intensity and WACI divide by revenue, and BRSR revenue is sometimes typed in ₹ lakh or ₹ crore
instead of rupees. Every filing reports revenue twice (`RevenueFromOperations` and
`TotalRevenueOfTheCompany`), and total revenue is operating revenue plus other income, so the two
should be close. Rule **V2-fix** (`pf_core/brsr/revenue.py`) uses the second field to check the
first:

1. If the two fields agree within 15%, both are kept as filed. Both are never rescaled by the same
   factor, because that would always "agree".
2. Otherwise exactly one field is rescaled by 1e5 (lakh) or 1e7 (crore). The correction is
   accepted only if **exactly one** interpretation makes the fields agree within 15% **and** the
   corrected operating revenue is at least ₹10 lakh.
3. Only if no single-field fix works is one two-field combination tried (one field in crore, the
   other in lakh). It must also be the only fit.
4. Anything else is `unresolved`: left as filed, still flagged by V2/V3.

A correction turns a V2 error into a `V2-fix` warning. The holding re-enters WACI, and its WACI
data quality is capped at 2, because the revenue is inferred rather than reported. The filed value
is never overwritten: the provenance panel shows the raw value, the value used and the reasoning.

| Company, year | RevenueFromOperations | TotalRevenueOfTheCompany | Outcome |
|---|---|---|---|
| Gujarat Themis FY2025-26 | 165.82 | 1,658,227,981 | Ratio 1.0000e7: operating revenue was in ₹ crore, corrected to ₹1,658,200,000 (`inferred_crore`) |
| Everest Kanto FY2025-26 | 934.43 | 96,669 | No single-field fit; operating revenue in crore (₹9,344,300,000) and total revenue in lakh (₹9,666,900,000), which then agree within 3.5% (`inferred_crore`, two-field) |
| Ingersoll-Rand FY2025-26 | 13,923,700,000 | 139,237.03 | Ratio 1.0000e5: total revenue in ₹ lakh; operating revenue (used for WACI) unchanged (`inferred_lakh`) |
| HMT FY2025-26 | 259,579,246 | 838,698,142 | Ratio 3.23, not a power of ten: **not corrected** (`unresolved`; probably large other income) |

Gujarat Themis FY2024-25 (153.23 vs 2,483,819,619, ratio 1.62e7) and PTC Industries FY2025-26
(17% apart) also stay `unresolved`.

## Principles

- **Missing means unknown.** An absent figure is `None`, never zero.
- **Flag, don't guess.** Only two fixes are automatic (V1 unit reading, V4 zero-as-missing). Everything else is flagged and left as filed.
- **Every number is traceable** to its source file, XBRL element, context, period, unit and the transformation applied.
- **No estimation.** Non-reporting companies are a coverage gap, not a modelled number.

## In scope / out of scope

**In scope:** Scope 1 and Scope 2 from BRSR; PCAF listed-equity attribution; carbon footprint; WACI; data-quality scores 1–2.

**Out of scope (for now):** Scope 3 (reported by too few companies and too inconsistently to attribute), ESG ratings, "green" recommendations, return predictions, and ML estimates for non-reporters.

## Limitations

Kept current with each release.

1. **20 filings only.** The snapshot covers 20 real FY2025-26 BRSR filings, skewed towards smaller late filers. `pf fetch-brsr` (run on a laptop; NSE blocks cloud servers) will widen this to all listed filers.
2. **Illustrative EVIC.** No real market-cap or debt data is in the repo yet. The demo's EVIC values are made up and labelled. A loader for real EVIC exists (`pf compute --evic-real`) and waits for the owner's CSV.
3. **No fund data.** No real AMC portfolio has been ingested. The fund-ranking pipeline is built and tested only on a synthetic workbook.
4. **Scope 3 excluded.** Too few companies report it, and too inconsistently, to attribute.
5. **Non-reporters are not estimated.** They are uncovered, and coverage can be low.
6. **Revenue corrections are inferences.** They are applied only when unambiguous, always shown, and capped at DQ 2. A second revenue source (financial results) would still be better.
