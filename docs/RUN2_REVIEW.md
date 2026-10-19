# Run 2 review: fixes and next milestones

Branch `run2/fixes-and-next`, cut from `main` at `c5a11d6` (PR #1 merged), one commit per phase.
Nothing was pushed to `main` and nothing was force-pushed. No network call was made to NSE, BSE or
any AMC. The 20 fixture filings are byte-for-byte unchanged.

## 0. Baseline (before any run-2 change)

| Check | Result |
|---|---|
| `ruff check .` | clean |
| `mypy pf_core` (strict) | clean, 13 files |
| `pytest` | **88 passed**, 0 failed, 0 xfail |
| `pytest --cov=pf_core` | 97% overall (parser 91%, validators 97%, engine 92%, everything else 100%) |
| `npm ci && npm test -- --run` | **13 passed** |
| `npm run build` | `index` 64.2 kB (20.3 kB gzip), `markdown` 159.1 kB (48.5 kB gzip), `charts` 500.5 kB (146.3 kB gzip); all three loaded on first paint, so **initial JS ≈ 215 kB gzip** |

## 1. Phase checklist

| Phase | Status | Notes |
|---|---|---|
| 0. Read docs, baseline | ✅ done | Section 0 above |
| 1. Honest headline | ✅ done | 14 problems in 6 companies + 26 informational notes; Home tile and Data quality page split |
| 2. Revenue correction (V2-fix) | ✅ done | `pf_core/brsr/revenue.py`; Gujarat Themis now in WACI; `docs/worked-example-b.md`; "Corrected" chip |
| 3. Methodology polish | ✅ done | Assurance (with the FACT conflict, see section 5), Revenue corrections, Limitations; plus EVIC and Funds/V8 sections |
| 4. NSE bulk fetcher | ✅ done (mocked only) | `pf fetch-brsr`, API + RSS, rate limit, retries, resume, manifest, schema dump; revision handling in `build-snapshot`; `docs/RUN_ON_LAPTOP.md` |
| 5. Real-EVIC loader | ✅ done | `pf_core/pcaf/evic.py`, `--evic-real`, E1/E2/E3, `data_templates/evic_template.csv`, `docs/EVIC_DATA_PLAN.md` |
| 6. AMC ingestion + V8 | ✅ done (synthetic only) | Generic Excel adapter, V8 / V8-isin / V8-dup, `pf ingest-funds`, `pf rank-funds`, 50% coverage rule, `docs/AMC_DATA_PLAN.md` |
| 7. Funds page | ✅ done | Honest empty state, "How rankings will work" diagram, illustrative demo in a separate table, fund detail page |
| 8. Frontend + repo polish | ✅ done | Lazy loading (initial JS 58 kB gzip), footer link, 10 screenshots (3 in README), axe 0 violations, ESLint in CI |
| 9. Deployment config | ✅ done (not deployed) | `render.yaml`, `web/vercel.json`, `docs/DEPLOY.md`; both Docker images built and smoke-tested |
| 10. Hardening | ✅ done | Golden snapshot, mutation tests, branch tests, 98% coverage, None→0 fixes, API split into routers |
| 11. Review + PR | ✅ done | This file |

## 2. Numbers before and after

| | Before (run 1) | After (run 2) |
|---|---|---|
| Backend tests | 88 passed | **163 passed**, 0 failed, 0 xfail |
| Frontend tests | 13 passed | **17 passed** |
| Lint / types | ruff, mypy | ruff, `ruff format --check`, mypy strict (24 files), ESLint (`--max-warnings 0`), `tsc` |
| Initial JS (gzip) | ≈ 215 kB | **58 kB**. Recharts (101 kB) and the Markdown renderer (48 kB) now load only on the pages that use them |
| axe (WCAG 2 A/AA) | not run | first scan: 0 critical, 4 serious (`scrollable-region-focusable`); after fixes: **0 critical / 0 serious / 0 moderate / 0 minor** on 7 pages × 2 widths |
| Horizontal scroll at 390 px | — | 0 px on every page (the Methodology page had 634 px before the fix) |

**Coverage per module** (`pytest --cov=pf_core`, 98% overall):

| Module | Coverage | Module | Coverage |
|---|---|---|---|
| brsr/parser.py | 93% | pcaf/engine.py | 100% |
| brsr/validators.py | 98% | pcaf/evic.py | 100% |
| brsr/revenue.py | 98% | pcaf/inputs.py, models.py, quality.py, config.py | 100% |
| brsr/normalise.py | 100% | funds/adapters.py | 94% |
| brsr/fetch.py | 94% | funds/ingest.py | 99% |
| brsr/models.py, config.py | 100% | funds/ranking.py, validators.py, models.py | 100% |
| snapshot.py | 100% | | |

Both targets were met: `pf_core/pcaf` is at 100% and `pf_core/brsr` is at least 93% per module.
The uncovered lines are defensive branches (malformed contexts, transport errors on the last retry,
odd date formats), not calculation paths.

**Existing tests changed on purpose** (none deleted or weakened; each now asserts more):

| Test | Old assertion | New assertion | Why |
|---|---|---|---|
| `test_validators::test_v1_counts` | V1 warnings on {Gujarat Themis, Everest Kanto} | no V1 warnings on fixtures; plus 2 new constructed tests prove V1 still warns on trusted revenue and skips untrusted revenue | D32 |
| `test_validators::test_v2_revenue_scale` | GT FY26 is a V2 error | GT FY26 is V2-fix (warning, message cites the evidence); GT FY25 is still a V2 error; Everest Kanto is V2-fix | Phase 2 |
| `test_validators::test_normalise_v2_is_flagged_not_fixed` | FY26 row unfixed | the unresolvable FY25 row is unfixed; a new test checks the corrected FY26 row and its provenance | Phase 2 |
| `test_pcaf::test_portfolio_b_exclusions` | GT not in WACI; WACI value ₹7.0 cr | GT in WACI, `revenue_corrected`, WACI DQ 2; WACI value ₹7.6 cr; new `test_worked_example_portfolio_b` matches the hand calculation to 1e-9 | Phase 2 |
| `test_api::test_validation_summary` | V2 companies = 2 | V2 = 1, V2-fix = 2, issues sum to 4; plus problem/info counts | Phase 1 + 2 |
| `test_snapshot::test_coverage_stats` | V2 issues = 4 | V2 + V2-fix = 4; plus the 14/26/6 headline and per-rule splits | Phase 1 + 2 |

`docs/worked-example.md` (portfolio A) is unchanged: no bug was found, and none of its companies
needed a correction.

## 3. Corrected headline numbers

| | Count |
|---|---|
| **Data problems** (severity error/warning) | **14**: V2 ×1, V2-fix ×3, V3 ×8, V4 ×1, V5 ×1 |
| **Companies with problems** | **6**: Gujarat Themis, Everest Kanto, Ingersoll-Rand, HMT, Gulshan Polyols, Varroc |
| **Informational notes** (severity info) | **26**: V1 ×20, V6 ×1, V9 ×5 |
| All issues | 40 (unchanged; the old headline counted all 40 as problems) |

The code first produced 18 problems / 22 notes, not 14 / 26. The difference was V1's 4 warnings on
Gujarat Themis and Everest Kanto. They fired only because those companies' revenue is mis-scaled,
which V2 already reports, so they double-counted one problem. V1 now checks its intensity threshold
only against trustworthy revenue (D32). After that change the numbers match the prompt exactly.

## 4. Revenue corrections applied (rule V2-fix)

| Company | FY | Before (ops / total, ₹) | After (ops / total, ₹) | Resolution | Evidence |
|---|---|---|---|---|---|
| Gujarat Themis Biosyn | FY2025-26 | 165.82 / 1,658,227,981 | **1,658,200,000** / 1,658,227,981 | `inferred_crore` | ratio 1.0000e7; the only reading that agrees (within 0.002%) |
| Everest Kanto Cylinder | FY2025-26 | 934.43 / 96,669 | **9,344,300,000 / 9,666,900,000** | `inferred_crore` (two-field) | no single-field fit; ops in crore + total in lakh agree within 3.5% |
| Everest Kanto Cylinder | FY2024-25 | 915.27 / 94,622 | **9,152,700,000 / 9,462,200,000** | `inferred_crore` (two-field) | the same pattern, within 3.4% |
| Ingersoll-Rand (India) | FY2025-26 | 13,923,700,000 / 139,237.03 | 13,923,700,000 / **13,923,703,000** | `inferred_lakh` | ratio 1.0000e5; total revenue in lakh; operating revenue (used for WACI) untouched |
| Ingersoll-Rand (India) | FY2024-25 | 13,362,900,000 / 133,629.36 | 13,362,900,000 / **13,362,936,000** | `inferred_lakh` | ratio 1.0000e5 |
| Gujarat Themis Biosyn | FY2024-25 | 153.23 / 2,483,819,619 | unchanged | `unresolved` | ratio 1.62e7, no clean fit; stays a V2 error |
| HMT | both years | 259,579,246 / 838,698,142 | unchanged | `unresolved` | ratio 3.2, not a power of ten; probably large other income |
| PTC Industries | FY2025-26 | 2,897,961,000 / 2,411,855,613 | unchanged | `unresolved` | 17% apart; the total equals PTC's own FY2024-25 operating revenue to the rupee, which looks like a copy-paste slip in the filing |

The only portfolio-level effect is on portfolio B: WACI goes from 6.9712 over ₹7.0 crore to
**15.3319964493 over ₹7.6 crore**, derived by hand in `docs/worked-example-b.md`.

## 5. What the owner must do, in order (on the laptop)

1. **Pull and install:** `git pull`, `.\.venv\Scripts\Activate.ps1`, `pip install -e ".[dev]"`, `pytest -q`.
2. **Run the NSE fetch** (about an hour; resumable):
   ```powershell
   pf fetch-brsr --out data/raw/brsr --from 2022-01-01
   pf validate data/raw/brsr --out data/raw/brsr_validation_report.csv
   pf build-snapshot --input data/raw/brsr --out data/snapshots/2026-10
   ```
3. **Paste into the project thread:**
   - the fetch counts (found / downloaded / skipped / failed);
   - the `keys` list from `data/raw/brsr/_response_schema.json`;
   - the validate line "Parsed N filings, M failed" and the per-rule table;
   - the build-snapshot summary block.

   Details: `docs/RUN_ON_LAPTOP.md`.
4. **Fill the EVIC template** (`data_templates/evic_template.csv` → `data/evic/evic_2026-03.csv`):
   market cap at 31 March from NSE's market-capitalisation report, and total borrowings from
   financial results. Leave debt blank if unknown, never 0. See `docs/EVIC_DATA_PLAN.md`.
5. **Download 3 AMC monthly portfolio files** (suggested SBI MF, HDFC MF, Parag Parikh MF;
   unverified) into `data/raw/amc/<amc>/<YYYY-MM>.xlsx`. Then run
   `pf ingest-funds --input data/raw/amc --out data/snapshots/2026-10/funds.parquet` and
   `pf rank-funds --snapshot data/snapshots/2026-10 --evic-real data/evic/evic_2026-03.csv`.
   See `docs/AMC_DATA_PLAN.md`.
6. **Check by hand:**
   - `docs/worked-example-b.md` with a calculator.
   - FACT's assurance report. Its GHG `…IsAssuredByAssurer` flag is `false`, but it answers `true`
     to the separate external-assessment question for GHG, naming SR Asia. We score it DQ 2 (D39).
   - PTC Industries' FY2025-26 revenue figures in the PDF (D36).
7. **Optional:** deploy per `docs/DEPLOY.md` (Render + Vercel).

## 6. Decisions made without asking (copied from DECISIONS.md, run 2 only)

| # | Date | Decision | Reasoning |
|---|---|---|---|
| D31 | 2026-10-14 | The headline counts **problems** (severity error/warning) apart from **informational notes** (severity info). `issues_total` is kept in the API, documented as "all issues, problems plus informational notes", because the existing API test and the coverage SQL use it. | 26 of the 40 issues were notes about things handled by design; calling all 40 "problems" overstated the data's problems. |
| D32 | 2026-10-14 | V1's implied-intensity threshold is evaluated only when revenue passes the V2 scale check. On the fixtures this turns V1's 4 warnings (Gujarat Themis, Everest Kanto) into info, giving 14 problems / 26 notes / 6 companies, exactly the run-2 prompt's expected numbers. | With mis-scaled revenue the implied intensity is wrong by about 1e7, so V1 could not judge the unit and was only repeating V2's finding. A constructed test proves V1 still warns when trusted revenue implies megatonnes. |
| D33 | 2026-10-14 | Revenue fields "agree" when they differ by at most 15% of the larger one (symmetric). Total revenue below operating revenue is allowed. | Varroc files total revenue 9.5% below operating revenue; a one-sided rule would call that disagreement. The 15% band comes from the run-2 prompt. |
| D34 | 2026-10-14 | `revenue_resolution` describes the correction applied. When only `TotalRevenueOfTheCompany` is rescaled (Ingersoll-Rand, ×1e5) the label is `inferred_lakh`, but the revenue used for intensity/WACI (`revenue_inr_resolved`) is the untouched operating revenue, and V2-fix and the DQ cap do not apply (`revenue_corrected` is False). | The DQ cap and V2-fix exist to mark an inferred number feeding a calculation; Ingersoll's operating revenue was never inferred. |
| D35 | 2026-10-14 | V3 still fires on corrected companies (counts stay 8). Its suggested fix now explains the scale slip when V2-fix resolved it. | V3 describes the filing as filed, which is still wrong; hiding it would understate the data's problems. |
| D36 | 2026-10-14 | Gujarat Themis FY2024-25 (153.23 vs 2,483,819,619, ratio 1.62e7) and PTC Industries FY2025-26 (operating ₹289.8 cr vs total ₹241.2 cr, 17% apart) are `unresolved`. PTC's total revenue equals its own FY2024-25 operating revenue to the rupee, which looks like a copy-paste slip in the filing. Its operating revenue is still used as filed (no V2/V3 fires). | No lakh/crore reading explains either gap; the rule never guesses. Recorded for the owner to check against the PDFs. |
| D37 | 2026-10-14 | V2-fix caps the **WACI** data quality (new `waci_data_quality`, holding and portfolio level) at 2, not the financed-emissions DQ. | Financed emissions use EVIC, not revenue, so an inferred revenue does not lower their quality; WACI divides by revenue, so it does. |
| D38 | 2026-10-14 | Provenance rows gain `value_used` and `corrected`. The filed `raw_value` is never overwritten. | The panel shows both the number as filed and the number we compute with, so a correction is auditable and reversible. |
| D39 | 2026-10-14 | PCAF data quality uses only `WhetherDetailsOfGreenHouseGasEmissionsAndItsIntensityIsAssuredByAssurer`. FACT stays DQ 2 even though it answers `true` to the separate Principle 6 question on external GHG assessment, naming SR Asia's "Reasonable Assurance for BRSR Core". | The run-2 prompt specifies the GHG-specific flag. The filing itself marks the GHG data point as not assured, so reading a general BRSR Core statement as GHG assurance would be an inference. Flagged for a hand check; the two flags agree in the other 19 filings. |
| D40 | 2026-10-14 | The fetcher identifies filing links by value, not key: any string under `nsearchives.nseindia.com/corporate/xbrl/` ending in `.xml`. Company, symbol and submission date are picked from keys containing hints (`company`/`issuer`/`name`, `symbol`, `submission`/`submitted`/`broadcast`/`date`). | NSE's response schema is undocumented; matching by value cannot miss a renamed field. The first record's keys are saved so the owner can confirm. |
| D41 | 2026-10-14 | Tests use `httpx.MockTransport` (no `respx` dependency). The client takes injectable `sleep`/`clock` so rate-limit and backoff timings are asserted exactly without waiting. | One less dependency, and the timing tests run in milliseconds. |
| D42 | 2026-10-14 | Revisions: the latest submission per (company, reporting-year end) wins, ordered by the `YYYYMMDD_HHMMSSmmm` stamp NSE puts in the file name. When several years are loaded, a year that is both one filing's reporting year and the next filing's comparative keeps the **reporting-year** figure; the other copy is listed as `duplicate`. `is_current` marks only each company's latest year. | The reporting-year figure is the primary disclosure. Multi-year loads would otherwise list a company twice in `/companies`. Every dropped copy appears in `excluded.parquet` with a reason. |
| D43 | 2026-10-14 | Both XML parsers use `lxml.XMLParser(resolve_entities=False, no_network=True)`, and downloaded file names must match `[A-Za-z0-9_.-]+\.xml`. | Files now come from the internet, so they are untrusted input (no XXE, no path traversal). |
| D44 | 2026-10-14 | `httpx` moved from dev to runtime dependencies (the fetcher needs it); `openpyxl` added for phase 6. | Runtime code imports them. |
| D45 | 2026-10-14 | EVIC = market cap + total debt + minority interest, no cash deduction. Missing debt → partial EVIC (market cap only) with financed-emissions DQ capped at 2; missing/non-positive market cap → no EVIC (holding uncovered); `as_of_date` > 15 months from the emissions FY end → warning. Blank cells are `None`, never 0. | PCAF listed-equity definition. A partial EVIC overstates attribution, so it is usable but flagged and down-scored. |
| D46 | 2026-10-14 | `--evic-real` values override `--evic` (illustrative) per company. `contains_illustrative_inputs` stays true if any used EVIC is illustrative; a real-EVIC file named or sourced "illustrative"/"synthetic" counts as illustrative. | A single made-up denominator makes the whole result illustrative. |
| D47 | 2026-10-14 | EVIC tests write CSVs to `tmp_path` with fake keys (`TESTCO1`…). The one CLI test with real ISINs mixes a real-format file into an illustrative run, so its output is (correctly) marked illustrative. | Never pair a real company with a made-up market value in anything that could be read as real. |
| D48 | 2026-10-14 | Engine thresholds moved to `pf_core/pcaf/config.py` with reasons (crore, EVIC age, partial-EVIC floor, fund coverage threshold). | The phase-10 rule: no magic numbers outside config. |
| D49 | 2026-10-14 | The generic AMC adapter skips "Sub Total"/"Total" rows and ends a scheme at "Grand Total" (or at the next header row), rather than stopping at the first "Total". | Real AMC sheets put an equity "Total" before the debt and cash sections; stopping there would drop the lines V8 needs and make every fund fail V8. |
| D50 | 2026-10-14 | Equity = ISIN matching `^INE[A-Z0-9]{4}01[A-Z0-9]{2}[0-9]$` (security type 01). Only equity lines are attributed; fund coverage is over equity value. Non-equity value is reported beside it. | Design doc: coverage = covered value / total *equity* value. PCAF listed equity covers shares, not bonds or cash. |
| D51 | 2026-10-14 | V8 sums % to NAV over every line (equity, debt, cash); missing weights → a V8 warning that it cannot be checked. Duplicate ISINs are summed (quantity, value, weight); if either line lacks a value the summed value is `None` (revised in phase 10, see D65). | The prompt's V8 wording ("across all holdings, including cash/debt lines"); summing duplicates never turns an unknown into a zero. |
| D52 | 2026-10-14 | Market-value units come from the header text (lakh/lac, crore/cr., '000/thousand); when no unit is stated, rupees are assumed **and a parse note says so**. | AMC files differ; the assumption is visible rather than silent. |
| D53 | 2026-10-14 | `fund_key` = slug of AMC + scheme name + as-of date. | Scheme codes are rarely in the files; this is stable and readable. |
| D54 | 2026-10-14 | The synthetic AMC workbook reuses the 20 fixture companies' real ISINs for its equity lines (so the engine has emissions to join), uses obviously fake `…SYN…` ISINs for the uncovered lines, and is named and labelled illustrative throughout. | The made-up part is the holdings, not the companies; the file name and the "Illustrative … Fund" names keep it from being read as a real portfolio. |
| D55 | 2026-10-14 | Workbook read errors are caught narrowly (`InvalidFileException`, `BadZipFile`, `OSError`, `KeyError`, `ValueError`) and reported per file. | One broken download must not stop the rest, and no bare `except` hides bugs. |
| D56 | 2026-10-14 | `GET /funds` serves only non-illustrative rankings from `fund_rankings.json` in the snapshot; illustrative funds are served only by `GET /demo/funds`, computed on request from the synthetic workbook. The UI shows them in a separate table behind the amber banner. | "Never mix illustrative funds with real ones in the same table", enforced at the API so the UI cannot get it wrong. |
| D57 | 2026-10-14 | The "How rankings will work" diagram is HTML (CSS grid boxes and arrows) rather than SVG. | It reflows to a vertical stack on phones; a fixed-viewBox SVG shrinks its text below readable size at 360 px. |
| D58 | 2026-10-14 | Bundle: every page except Home and 404 is `React.lazy`-loaded and the old `manualChunks` grouping was removed, so Recharts and react-markdown download only on pages that use them. Initial JS: ~215 kB → 58 kB gzip. | Target was < 250 kB gzip; the manual chunking had forced the chart bundle onto first paint. |
| D59 | 2026-10-14 | The axe + screenshot script (`web/scripts/visual-check.mjs`, `playwright` + `@axe-core/playwright` dev deps) runs locally against `vite preview`, not in CI. Only the 10 required screenshots are committed (2.4 MB). | CI would need a browser download and the API running; the script is reproducible on demand. |
| D60 | 2026-10-14 | axe found 4 serious `scrollable-region-focusable` violations (company detail tables, methodology code blocks); fixed with `tabIndex=0` + `role="region"` + labels. A long inline XBRL element name made the methodology page scroll sideways by 634 px on phones; inline code now wraps (`overflow-wrap: anywhere`). | Keyboard users must be able to scroll wide content; phones must not scroll horizontally. |
| D61 | 2026-10-14 | `vite preview`'s origin (`http://localhost:4173`) added to the API's dev CORS list. | Found when the screenshot run could not load companies from the preview build. |
| D62 | 2026-10-14 | ESLint 9 flat config with typescript-eslint, react-hooks and react-refresh, `--max-warnings 0`, run in CI. Fixes: `useApi` keeps the latest loader in a ref (its effect depends on `key` only); theme constants and hooks moved to `themeContext.ts` so `theme.tsx` exports only the provider; `_`-prefixed unused arguments allowed. | Clean lint with no rules disabled. |
| D63 | 2026-10-14 | Render blueprint: one free Docker web service, health check `/health`, `autoDeploy: false`, `PF_CORS_ORIGINS` left for the owner (`sync: false`). Vercel: `web/vercel.json` with the Vite build and an SPA rewrite; `VITE_API_URL` is set in the Vercel dashboard (not in `vercel.json`) because Vite inlines it at build time and it differs per deployment. | Nothing deploys without the owner's action; no URLs are guessed into the repo. |
| D64 | 2026-10-14 | Docker images were built and smoke-tested locally using a build-only copy of each Dockerfile that trusts this sandbox's TLS proxy CA; the committed Dockerfiles are unchanged apart from `.dockerignore` excluding `docs/screenshots`. | Same approach as run 1; the CA workaround is specific to this environment. |
| D65 | 2026-10-14 | Phase-10 sweep: (1) duplicate-ISIN sums now return `None` if **either** line lacks a value (was: treat the missing side as 0); (2) a fund's non-equity total sums only valued lines and reports `non_equity_unvalued_lines` instead of counting unvalued lines as ₹0; (3) V4's exact `== 0` and V10's `!= 0` guard are kept on purpose and commented; (4) `api/main.py`'s 171-line `create_app` split into `api/schemas.py`, `api/state.py` (dependency-injected `AppState`) and `api/routes/{companies,portfolio,funds}.py`. No bare `except` existed; no magic thresholds remain outside `config.py` files (only ×100 for percentages). | Silent None→0 conversions break "missing means None"; the rest are readability fixes. |
| D66 | 2026-10-14 | Golden test: `tests/golden/fixtures_summary.json` (40 rows: company, FY, scope1_t, scope2_t, revenue_resolved, revenue_resolution, quality_flag, issues). Regenerate with `UPDATE_GOLDEN=1 pytest tests/test_golden.py` in the same commit as any intended change. | Locks the whole fixture pipeline's output, so any unintended drift fails CI. |

## 7. Interview prep: run-2 changes

1. **"How do you correct a revenue figure typed in the wrong units without guessing?"** Each BRSR
   filing reports revenue twice (operating and total), and total is operating plus other income,
   so they should be close. `revenue.py` rescales exactly one field by 1e5 or 1e7 and accepts the
   result only if exactly one reading makes the two agree within 15% and the corrected revenue is
   at least ₹10 lakh. HMT's 3.2× gap is not a power of ten, so it is left alone.

2. **"Why does a corrected revenue cap data quality at 2, and only for WACI?"** A corrected number
   is an inference, not a disclosure, so anything computed from it cannot claim PCAF score 1.
   Financed emissions divide by EVIC, not revenue, so they keep the company's own score.
   `waci_score()` applies the cap only where revenue is used.

3. **"Why count 14 problems and not 40 issues?"** 26 of the 40 are informational: MtCO2e read as
   tonnes, a June year end, and "not applicable" disclosures that are handled by design. Calling
   them problems overstated the data's problems by almost 3×. `coverage_stats()` splits by
   severity, and V1 no longer double-counts V2's revenue errors.

4. **"What exactly is EVIC, and why no cash deduction?"** EVIC = market cap at fiscal year end +
   total debt + minority interest (`compute_evic`). PCAF keeps cash in because the denominator is
   everyone financing the company, shareholders and lenders, not its takeover price. If debt is
   missing, the EVIC is flagged partial, because it overstates attribution, and the holding's DQ
   is capped at 2.

5. **"Why won't you rank a fund with 40% coverage?"** Its footprint describes only the 40% we can
   measure. If the unmeasured 60% is carbon-heavy, the ranking would reward missing data.
   `FUND_MIN_COVERAGE_PCT = 50` marks such funds "insufficient coverage", and coverage sits next to
   every footprint.

6. **"What does V8 catch, and why sum cash and debt lines too?"** V8 checks a scheme's lines add up
   to 95–105% of NAV. If they don't, the parser probably missed a section or read one twice. It
   must include debt and cash, because equity alone legitimately sums to less than 100%. That is
   also why the adapter ends a scheme at "Grand Total" rather than the first "Total".

## 8. Blocked, xfailed, or not done

- **No xfails.** Every test passes.
- **NSE, real EVIC and real AMC data**: not reachable or not available here, by design. Code,
  tests and runbooks are ready (section 5).
- **Docker** was built and smoke-tested with a build-only copy of each Dockerfile that trusts this
  sandbox's TLS proxy certificate (D64). `docker compose up` was not run end to end.
- **The axe and screenshot script** runs locally against `vite preview`, not in CI (D59).
- **Known warning**: Starlette notes that its test client will move from `httpx` to `httpx2`.
  It is harmless for now.
