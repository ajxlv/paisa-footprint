# BRSR data check: results from 20 real filings (13 Oct 2026)

Source: the 20 FY2025-26 XBRL filings Atharva downloaded with `check_brsr.py` (1,953 facts). All numbers below were computed from those files.

## Verdict: GO
The data is usable, and the errors in it are **detectable by simple rules**. Those rules become the project's validation layer.

## Coverage
| | Count |
|---|---|
| Report Scope 1 **and** Scope 2 | **15 / 20** |
| Say emissions are "not applicable" (flag = false) | 5 / 20: Rajesh Exports, Sirca Paints, Ashiana Housing, Vishnu Prakash R Punglia, HMT |
| Report Scope 3 | 7 / 20 |
| Report a prior year (FY2024-25) too | 15 / 15 |

These are the 20 *latest* filers, which skews towards smaller companies. Coverage for large-cap fund holdings should be higher. [Likely, to verify against an actual fund's holdings]

The XBRL element names are stable: `TotalScope1Emissions`, `TotalScope2Emissions`, `TotalScope3Emissions`, `TotalScope1AndScope2EmissionsIntensityPerRupeeOfTurnover`, `RevenueFromOperations`, and `WhetherDetailsOfGreenHouseGasEmissionsAndItsIntensityIsApplicableToTheCompany`.

## Data-quality problems found (each one becomes a validator)
1. **Ambiguous unit label.** 10 of 15 filings tag emissions as `MtCO2e`. Strictly, "Mt" means megatonnes. The values show they mean *metric tonnes*: Titan's Scope 1 is 3,878, and 3.9 billion tonnes would be absurd. The other 5 use `tCO2e`. Rule: treat `MtCO2e` as tonnes, and flag it if the value implies more than about 50,000 t per ₹ crore of revenue.
2. **Revenue entered at the wrong scale, which breaks the intensity figure by a factor of about 10⁷.** Gujarat Themis Biosyn reports `RevenueFromOperations` = 165.82 (₹ crore typed as rupees). That produces an intensity of **112.9 tCO2e per rupee** instead of about 1.1×10⁻⁵. Everest Kanto has the same problem: revenue 934.43, intensity 55.97. Everest Kanto's `TotalRevenueOfTheCompany` = 96,669 also disagrees with its own `RevenueFromOperations`. **2 of 15 (13%)** have this error. Rule: revenue under ₹10 lakh for a listed company means a scale error, so recompute intensity from a trusted revenue source.
3. **The intensity field is derived, not independent.** In all 15 filings, the reported intensity equals (S1+S2) ÷ RevenueFromOperations exactly, so it can't be used to cross-check revenue. Revenue has to come from a second source, such as financial results.
4. **Zeros used for "not reported".** Gulshan Polyols reports FY2024-25 Scope 1 = 0 and Scope 2 = 0 while reporting about 52,500 t in FY2025-26. Rule: a zero next to a large non-zero year means missing data, not zero emissions.
5. **Implausible energy figure.** Accelya, an IT services firm with 0.08 t of Scope 1, reports 754,655 GJ of renewable energy, which is about 210 GWh. That's most likely kWh entered as GJ. [Likely] Rule: an energy ÷ revenue outlier within the sector gets flagged. (Energy isn't needed for PCAF, but it shows the kind of check needed.)
6. **Big year-on-year jumps.** Varroc's Scope 1 goes from 2,157 to 8,020 t (3.7×). That may be real or may be a boundary change, so flag anything above 2× for review rather than auto-correcting it.
7. **Fiscal years differ.** Accelya's year ends 30 June, not 31 March. Rule: carry the period dates through and never assume April to March.

## Bug fixed in the checker
The first version's `has_scope3` matched the "Whether…Scope3…Applicable" flag, so it said True for every company. It now counts only the actual `TotalScopeNEmissions` facts, and the corrected result is 7/20.
