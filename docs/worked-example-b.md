# Worked example: synthetic portfolio B, by hand (with a revenue correction)

> **Illustrative data, not real market data.** Holdings and EVIC are made up
> (`tests/fixtures/synthetic/portfolio_synthetic_b.csv`, `illustrative_evic.csv`). Emissions and
> revenue are the real FY2025-26 figures from the BRSR fixtures.

Portfolio B exercises every exclusion path, and since run 2 it also exercises the **V2-fix revenue
correction**. `tests/test_pcaf.py::test_worked_example_portfolio_b` asserts the engine reproduces
every total on this page to a relative tolerance of 1e-9.

## Inputs

| # | Holding | Value | Illustrative EVIC | S1 + S2 (t) | Revenue used (₹) | Assured? |
|---|---|---|---|---|---|---|
| 1 | NMDC (INE584A01023) | ₹2 cr | ₹60,000 cr | 112805 + 85567 = 198372 | 315537000000 | Yes |
| 2 | HDFC Bank (INE040A01034) | ₹3 cr | ₹15,00,000 cr | 91849.5 + 236495.41 = 328344.91 | 3697059900000 | Yes |
| 3 | Varroc (`VARROC`) | ₹1 cr | ₹8,000 cr | 8020 + 75805 = 83825 | 81455320000 | not filed |
| 4 | Prince Pipes (INE689W01016) | ₹50 lakh | ₹5,000 cr | 1105 + 61257 = 62362 | 25983321435.75 | not filed |
| 5 | Gulshan Polyols (INE255D01024) | ₹50 lakh | ₹1,500 cr | 26579.29 + 25926.24 = 52505.53 | 23296527655.3 | not filed |
| 6 | Gujarat Themis (INE942C01045) | ₹60 lakh | ₹3,000 cr | 12487.99 + 6228.92 = 18716.91 | **1658200000 (corrected)** | not filed |
| 7 | Rajesh Exports (`RAJESHEXPO`) | ₹1 cr | — | — | — | — |
| 8 | `INE000000000` | ₹40 lakh | — | — | — | — |

Total value: 2 + 3 + 1 + 0.5 + 0.5 + 1 + 0.6 + 0.4 = **₹9 crore**.

**Uncovered:**
- Rajesh Exports marks GHG disclosure "not applicable" (rule V9).
- `INE000000000` matches no company (rule V7).

Both are listed with their reasons and left out of every total. Covered value = 9 − 1 − 0.4 = **₹7.6 crore**.

### The revenue correction (rule V2-fix)

Gujarat Themis files `RevenueFromOperations` = **165.82**, which is below ₹10 lakh and impossible
for a listed company. Its `TotalRevenueOfTheCompany` = **1,658,227,981**. The ratio is
1,658,227,981 ÷ 165.82 = 1.0000e7, so exactly one reading makes the two fields agree: 165.82 was
typed in ₹ crore.

- Corrected operating revenue: 165.82 × 1e7 = **₹1,658,200,000**. It agrees with total revenue
  within 0.002%, well inside the 15% tolerance.
- Rescaling by 1e5 instead (₹1,65,82,000) would not agree, and nor would rescaling the other field.
  The correction is therefore unambiguous.
- V2 is downgraded to a `V2-fix` warning. The holding enters WACI, flagged, with its WACI data
  quality capped at 2 (it is already 2, since assurance is not filed).

Before run 2, Gujarat Themis was left out of WACI, and WACI was 6.9712 over ₹7 crore.

## Step 1: attribution and financed emissions

| # | Attribution = value ÷ EVIC | × (S1+S2) | Financed (t) |
|---|---|---|---|
| 1 | 2 ÷ 60,000 = 0.0000333… | × 198372 | **6.6124** |
| 2 | 3 ÷ 15,00,000 = 0.000002 | × 328344.91 | **0.65668982** |
| 3 | 1 ÷ 8,000 = 0.000125 | × 83825 | **10.478125** |
| 4 | 0.5 ÷ 5,000 = 0.0001 | × 62362 | **6.2362** |
| 5 | 0.5 ÷ 1,500 = 0.000333… | × 52505.53 | **17.5018433333** |
| 6 | 0.6 ÷ 3,000 = 0.0002 | × 18716.91 | **3.743382** |

**Financed emissions** = 6.6124 + 0.65668982 + 10.478125 + 6.2362 + 17.5018433333 + 3.743382
= **45.2286401533 tCO2e**. Revenue plays no part in this step, so it is the same as before run 2.

## Step 2: coverage and carbon footprint

- Coverage = 7.6 ÷ 9 = **84.444…%**
- Footprint = 45.2286401533 ÷ 7.6 = **5.9511368623 tCO2e per ₹ crore invested**

## Step 3: WACI (all six covered holdings now have trustworthy revenue)

| # | Weight = value ÷ ₹7.6 cr | Intensity = (S1+S2) ÷ revenue in ₹ cr | Weight × intensity |
|---|---|---|---|
| 1 | 2/7.6 = 0.2631578947 | 198372 ÷ 31553.7 = 6.2868063016 | 1.6544227110 |
| 2 | 3/7.6 = 0.3947368421 | 328344.91 ÷ 369705.99 = 0.8881243985 | 0.3505754205 |
| 3 | 1/7.6 = 0.1315789474 | 83825 ÷ 8145.532 = 10.2909177694 | 1.3540681276 |
| 4 | 0.5/7.6 = 0.0657894737 | 62362 ÷ 2598.332143575 = 24.0007807140 | 1.5789987312 |
| 5 | 0.5/7.6 = 0.0657894737 | 52505.53 ÷ 2329.65276553 = 22.5379210056 | 1.4827579609 |
| 6 | 0.6/7.6 = 0.0789473684 | 18716.91 ÷ 165.82 = **112.8748643107** | 8.9111734982 |

**WACI** = 1.6544227110 + 0.3505754205 + 1.3540681276 + 1.5789987312 + 1.4827579609 + 8.9111734982
= **15.3319964493 tCO2e per ₹ crore of revenue**. WACI covers ₹7.6 crore of ₹9 crore, or 84.4% of value.

## Step 4: PCAF data quality

| Measure | Calculation | Result |
|---|---|---|
| Financed emissions | (2×1 + 3×1 + 1×2 + 0.5×2 + 0.5×2 + 0.6×2) ÷ 7.6 = 10.2 ÷ 7.6 | **1.3421** (= 51/38) |
| WACI | The same, because Gujarat Themis's cap at 2 changes nothing: it already scores 2 | **1.3421** |

## Summary

| Metric | Before run 2 | Run 2 |
|---|---|---|
| Financed emissions | 45.2286401533 t | 45.2286401533 t (unchanged) |
| Coverage | 84.4% | 84.4% (unchanged) |
| Carbon footprint | 5.9511368623 t / ₹ cr | 5.9511368623 t / ₹ cr (unchanged) |
| WACI | 6.9712 over ₹7.0 cr | **15.3319964493 over ₹7.6 cr** |
| WACI value covered | 77.8% | 84.4% |
| PCAF DQ (financed / WACI) | 1.3421 | 1.3421 / 1.3421 |
