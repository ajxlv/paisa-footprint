# Decisions log

Decisions made during the unattended overnight build (13–14 Oct 2026). Each was taken without asking; the conservative, more transparent option was preferred. Review every entry.

## Starting state

1. Repo `ajxlv/paisa-footprint`, one commit on `main` (`63cf2d6 Add BRSR test fixtures and design docs`).
2. `docs/design-doc.md`: design v0 (PCAF formulas, data sources, validators V1–V8, 6-week plan).
3. `docs/data-check-results.md`: data-quality findings from the 20 fixtures (units, revenue scale, zeros, YoY jumps, June year end).
4. `docs/sources.md`: NSE BRSR JSON API and RSS notes (not callable from this environment).
5. `tests/fixtures/brsr/`: 20 real BRSR XBRL filings, FY2025-26, 500–900 KB each, taxonomy `in-capmkt-ent-2026-02-28.xsd`.
6. `.gitignore` with `data/`, `__pycache__/`, `.venv/`.
7. No code, no `pyproject.toml`, no CI, no README, no CLAUDE.md.
8. Every fixture has exactly three non-dimensional contexts: `DCYMain` (current-year duration), `DPYMain` (previous-year duration) and `ICYMain` (current-year-end instant).
9. 15/20 filings report Scope 1 and Scope 2; 5 set the GHG "applicable" flag to `false`.
10. Python 3.12, Node 22 and Docker CLI are available in the build environment; NSE is not reachable.

## Decisions

| # | Date | Decision | Reasoning |
|---|---|---|---|
| D1 | 2026-10-13 | `cli/` and `api/` are top-level packages next to `pf_core/`, installed together by one `pyproject.toml`; `pf` is the console script `cli.pf:app`. | Matches the target layout in the build prompt; one install command for everything. |
| D2 | 2026-10-13 | Added `pandas-stubs` and `lxml-stubs` to dev dependencies. | `mypy --strict` on `pf_core` needs typed pandas/lxml; without stubs strict mode would need blanket `ignore_missing_imports`. |
| D3 | 2026-10-13 | Dropped the UTF-8 byte-order mark from the start of `.gitignore` while keeping its three entries. | The BOM made the first pattern read as BOM + `data/` for some tools, so `data/` might not be ignored. |
| D4 | 2026-10-13 | A context counts as **dimensional** if it holds any `xbrldi:explicitMember` **or** `xbrldi:typedMember`; only facts in non-dimensional contexts feed company totals. | The fixtures use `typedMember` too (e.g. `StockExchangeAxis`); a typed breakdown is still a breakdown, so treating it as a total would risk double counting. |
| D5 | 2026-10-13 | Element names used by the parser beyond the prompt's known-good list: `ValueOfSharesPaidUp` (paid-up capital, `ICYMain` instant context, unit `INR`, present in 20/20 fixtures). | Found by searching all fixtures for `PaidUp`; it is the only paid-up-capital element present. |
| D6 | 2026-10-13 | `emissions_unit_raw` is the resolved measure of the Scope 1 fact (falling back to Scope 2), e.g. `Non-SI:MtCO2e`; each figure's own unit is also kept in its provenance. | Scope 3 can use a different unit from Scope 1/2 in the same filing (Cyient DLM: `MtCO2e` vs `tCO2e`), so units are tracked per fact. |
| D7 | 2026-10-13 | `ghg_applicable` and `ghg_assured` are only filed in the current-year context, so for the previous year they are `None`, and a missing assurance element is `None` (not `False`). | Missing means unknown. 7/20 filings file the assurance element; the other 13 are "assurance unknown", not "not assured". |
| D8 | 2026-10-13 | `company_key` = ISIN (fallback CIN). | ISIN is unique, URL-safe and is what AMC holdings files join on; NSE symbols in the fixtures are inconsistently cased (`Titan`, `HDFCBank`). |
| D9 | 2026-10-13 | If one element has two different values for the same period, the parser keeps the first and writes a `parse_notes` entry. | Never hide a conflict. None of the 20 fixtures has one (asserted in tests). |
| D10 | 2026-10-13 | Validators run per fiscal year; V1–V5 and V10 can therefore fire once for each of the two filed years. Counts are reported both as issues and as companies. | A unit or revenue problem in the prior year matters for the YoY check and the "both years" UI, and reporting per year keeps each issue tied to one period. |
| D11 | 2026-10-13 | V1 emits one issue per affected year: `info` normally, `warning` when the implied intensity exceeds 50,000 t/₹ crore (only Gujarat Themis and Everest Kanto, whose revenue is mis-scaled). | Matches the prompt's "info (warning if threshold hit)" without double-reporting the same unit. |
| D12 | 2026-10-13 | V3 fires on 4 companies, not just Everest Kanto: also Gujarat Themis (ops ₹165.82 vs total ₹165.8 crore), Ingersoll-Rand (total revenue filed as 139,237.03, i.e. lakhs) and HMT (ops ₹26 crore vs total ₹84 crore: large other income). The rule was **not** loosened to hide them. | They are real >2x disagreements; HMT's may be genuine other income, so V3 stays a warning that asks for review rather than an error. |
| D13 | 2026-10-13 | V5 ignores years where either value is 0 or missing. | A ratio against zero is meaningless and the zero case is V4's job (Gulshan). |
| D14 | 2026-10-13 | V10 uses a 1% relative tolerance **and** a 5e-11 absolute tolerance. | Filers round the intensity to 10 decimals; Accelya's true intensity (1.5e-11) is reported as 0, which is rounding, not error. |
| D15 | 2026-10-13 | `quality_flag`: `excluded` if GHG disclosure is "not applicable" (V9) or no Scope 1/2 survives normalisation; `review` if any warning/error applies to that year or only one of S1/S2 is present; otherwise `ok` (info-only issues such as V1/V6 stay `ok`). | V1 and V6 are handled correctly by design, so they should not push a company into review; anything a human must look at does. |
| D16 | 2026-10-13 | Emissions units other than `tCO2e`/`MtCO2e` are withheld (`None`) with the reason recorded in provenance, not converted. | No such unit occurs in the fixtures; guessing a conversion would be invention. |
| D17 | 2026-10-13 | For a V2 revenue error, the clean row keeps revenue exactly as filed but sets the computed intensity to `None`. | V2 says the intensity is untrustworthy; rescaling by 1e7 is a guess the design doc says to replace with a second revenue source. |
