# Morning review: overnight build, 13–14 Oct 2026

Branch `overnight/week1-build`, one commit per phase. Nothing was pushed to `main`, nothing was force-pushed, and the 20 fixture files are byte-for-byte unchanged (SHA-256 checked before the PR).

## 1. What was built

| Phase | Status | Notes |
|---|---|---|
| 0. Read docs, starting state | ✅ done | Summary in `docs/DECISIONS.md` → "Starting state" |
| 1. Skeleton + CI | ✅ done | `pyproject.toml`, `CLAUDE.md`, `.github/workflows/ci.yml` (Python + web jobs) |
| 2. BRSR XBRL parser | ✅ done | All 13 exact-value checks from the prompt pass; `pf parse` |
| 3. Validators + normalisation | ✅ done | V1–V6, V9, V10 + hypothesis property; `pf validate` |
| 4. Snapshot | ✅ done | `companies` / `validation_report` / `excluded` Parquet + `manifest.json`; `sql/coverage.sql` |
| 5. PCAF engine | ✅ done | Synthetic portfolios A/B/C, `docs/worked-example.md`, 3 property tests; `pf compute` |
| 6. API | ✅ done | All 7 endpoints, OpenAPI at `/docs`, tests for every endpoint |
| 7. Frontend | ✅ done | All 7 pages, light/dark, phone width (360 px) checked with screenshots |
| 8. Docker + docs | ✅ done, with a caveat | Both images built and smoke-tested here (see "Blocked / needs human") |
| 9. Morning review + PR | ✅ done | This file |

Not built, by design: V7 lives in the PCAF engine (unmatched holdings are listed as uncovered); V8 (fund weights sum to 95–105% of NAV) needs AMC holdings data, which does not exist yet.

## 2. How to run it locally on Windows (PowerShell)

You need Python 3.12 and Node 20+ installed. From the repo folder:

**Backend**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pf build-snapshot --input tests/fixtures/brsr --out data/snapshots/fixtures
uvicorn api.main:app --reload
```

If `Activate.ps1` is blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
API docs: http://localhost:8000/docs

**Frontend** (in a second PowerShell window)

```powershell
cd web
npm install
npm run dev
```

Open http://localhost:5173. To point at another API: `$env:VITE_API_URL = "http://localhost:8000"; npm run dev`.

**Checks**

```powershell
ruff check .; ruff format --check .; mypy pf_core; pytest
cd web; npm run build; npm test
```

**Try the CLI**

```powershell
pf validate tests/fixtures/brsr
pf compute --portfolio tests/fixtures/synthetic/portfolio_synthetic_a.csv --evic tests/fixtures/synthetic/illustrative_evic.csv
```

**Docker** (Docker Desktop): `docker compose up --build`, then open http://localhost:8080.

## 3. Test results

| Suite | Passed | Failed | xfail |
|---|---|---|---|
| Backend (`pytest`) | 88 | 0 | 0 |
| Frontend (`vitest`) | 13 | 0 | 0 |

Plus `ruff check`, `ruff format --check`, `mypy --strict` on `pf_core` and `npm run build` (with `tsc`), all clean. Verified again from a fresh clone just before opening the PR. No test was skipped, weakened or marked xfail.

The one pytest warning is Starlette saying its test client will move from `httpx` to `httpx2`; it is harmless for now.

Hypothesis found one real bug during the build: V5 divided by an underflowed ratio (`5e-324 / 2 → 0`). Fixed by comparing `high <= low × 2` instead of computing `1 / ratio`.

## 4. Validator results on the 20 fixtures

Issues are counted per fiscal year (each filing has two years), so a company can contribute two issues to one rule.

| Rule | Severity | Companies | Issues | Which companies |
|---|---|---|---|---|
| V1 MtCO2e read as tonnes | info | 8 | 16 | Accelya, Cyient DLM, Ingersoll-Rand, Prince Pipes, PTC Industries, Themis Medicare, Titan, Varroc |
| V1 (implied intensity > 50,000 t/₹ cr) | warning | 2 | 4 | Gujarat Themis, Everest Kanto |
| V2 revenue < ₹10 lakh | error | 2 | 4 | Gujarat Themis, Everest Kanto |
| V3 revenue fields differ > 2× | warning | 4 | 8 | Everest Kanto, Gujarat Themis, Ingersoll-Rand, HMT |
| V4 zero year next to non-zero | warning | 1 | 1 | Gulshan Polyols (FY2024-25) |
| V5 YoY change > 2× | warning | 1 | 1 | Varroc (Scope 1, 2,157 → 8,020) |
| V6 FY not ending 31 March | info | 1 | 1 | Accelya (June year end) |
| V9 GHG "not applicable" | info | 5 | 5 | Rajesh Exports, Sirca Paints, Ashiana Housing, Vishnu Prakash R Punglia, HMT |
| V10 intensity mismatch > 1% | warning | 0 | 0 | none (tested with a constructed filing) |
| **Total** | | | **40** | |

V1 in total: **10 companies** (matches the data check's "10 of 15 tag MtCO2e").

Quality flags for the current year: **11 ok, 4 review** (Everest Kanto, Gujarat Themis, Ingersoll-Rand, Varroc), **5 excluded** (the V9 five). Snapshot: 40 company-years = 29 usable + 11 excluded (the 5 V9 companies × 2 years, plus Gulshan's zeroed FY2024-25).

**One difference from the prompt's expectations:** V3 fires on four companies, not only Everest Kanto. I did **not** loosen the rule. All four are real >2× gaps:
- **Gujarat Themis**: operating revenue ₹165.82 vs total ₹1,65,82,27,981 (the same scale error V2 catches)
- **Ingersoll-Rand**: total revenue filed as 1,39,237.03, which looks like ₹ lakh, vs operating revenue ₹13,92,37,00,000
- **HMT**: operating revenue ₹26 crore vs total ₹84 crore. This may be genuine other income, which is why V3 is a warning, not an error.

## 5. Things Atharva must check by hand

1. **The worked example.** Redo `docs/worked-example.md` with a calculator. The headline numbers are 83.2346091 tCO2e financed, 2.77448697 t per ₹ crore, WACI 12.9734051465, DQ 7/6.
2. **Three parsed values against the BRSR PDFs:**
   - **NMDC Limited**: FY2025-26 Scope 1 = **112,805** tCO2e (Section C, Principle 6, GHG table)
   - **Gujarat Themis Biosyn**: revenue from operations = **165.82**. Check what the PDF says: is it really ₹165.82 crore?
   - **Titan Company**: FY2025-26 Scope 1 = **3,878** with unit "MtCO2e". Confirm the PDF means metric tonnes.
3. **Every entry in `docs/DECISIONS.md`** (30 entries, copied in section 6 below). The ones I'd most like a second opinion on: D12 (V3 on HMT), D15 (what counts as `review`), D18 (WACI universe), D19 (unknown assurance scores 2).
4. **The UI copy.** The Home, Data quality and Funds pages make claims about the data. Make sure you're comfortable saying all of it in an interview.
5. **The GitHub link in the footer** is a placeholder (`#`) until the repo is public.

## Blocked / needs human

- **Docker images in CI or on your laptop.** I built and ran both images here (the API answered `/health` with 20 companies; nginx served `/` and deep links). Doing so needed a temporary build-only copy of each Dockerfile that trusted this sandbox's TLS proxy certificate, because pip could not reach PyPI otherwise. The committed Dockerfiles do **not** contain that and should build normally on your machine. I also did not run `docker compose up` end to end, only the two images separately. Please run `docker compose up --build` once.
- **CI on GitHub** has not run yet; it will run on the PR. The workflow is the same set of commands that passes locally.

## 6. Decisions made without asking

Copied from `docs/DECISIONS.md`:

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
| D18 | 2026-10-13 | WACI is computed over every holding with usable Scope 1+2 and a trustworthy revenue, **whether or not EVIC is available**; weights are normalised over that WACI universe and its share of the portfolio is reported as `waci_coverage_pct`. | The design doc (source of truth) says WACI "needs no EVIC, so it's the fallback metric when EVIC data is missing". The prompt's `total_covered_value` denominator would understate WACI when a covered holding is dropped for a V2 revenue error. For portfolio A both readings give the same number. |
| D19 | 2026-10-13 | Assurance unknown (`None`) scores PCAF data quality 2, the same as "not assured". | Conservative: only confirmed assurance earns score 1. |
| D20 | 2026-10-13 | A holding with attribution > 1 is listed as uncovered ("Rejected: …") rather than aborting the whole calculation; `attribution()` itself raises `AttributionError`. | One bad EVIC should not hide the rest of the portfolio, and nothing is silently dropped. |
| D21 | 2026-10-13 | Holdings resolve to companies by ISIN, then by upper-cased NSE symbol. Unknown identifiers stay in the result as uncovered (V7). | Holdings files usually carry ISINs; symbols are a convenience for hand-written portfolios. |
| D22 | 2026-10-13 | Synthetic EVIC values are round crore amounts (e.g. NMDC ₹60,000 cr, HDFC Bank ₹15,00,000 cr) marked `evic_is_illustrative=true`; the loader also treats any EVIC file named or headed "illustrative"/"synthetic" as illustrative. | Round values make the worked example checkable by calculator; double-labelling means a made-up EVIC can never be presented as real. |
| D23 | 2026-10-13 | The engine uses each company's **current** fiscal year (FY2025-26; for Accelya, the year to June 2026). | It is the latest reported year; the portfolio date is not modelled yet. |
| D24 | 2026-10-13 | The "Load illustrative example" button fetches synthetic portfolio A from `GET /demo/portfolios` instead of bundling a copy in the frontend; component-test mocks live in `web/src/demo/synthetic-api-responses.ts`. | One source of truth for demo data; the API marks it `illustrative: true` and the UI banner keys off that. |
| D25 | 2026-10-13 | A row loaded from the demo stays flagged illustrative (and its EVIC is sent with `evic_is_illustrative: true`) even if the user edits it, until the row is removed or cleared. | Conservative: a partly edited demo portfolio is still mostly made-up data, so the banner must not disappear. |
| D26 | 2026-10-13 | On the companies chart, log scale shows Scope 1+2 totals rather than stacked bars, with a note saying so. | Stacked segments have no meaningful length on a log axis; drawing them would mislead. |
| D27 | 2026-10-13 | Chart colours: Scope 1 green `#1f7a4d` / dark `#3fa877`, Scope 2 violet `#6250d6` / dark `#9085e9`. | Picked to stay in the deep-green brand family while passing colour-blind separation and 3:1 contrast in both themes (checked with a palette validator; green+orange failed for protanopia). |
| D28 | 2026-10-13 | Markdown on the methodology page is rendered with `react-markdown` + `remark-gfm` (no raw HTML). | Needs tables and code blocks; disallowing raw HTML keeps it safe. |
| D29 | 2026-10-13 | The API Docker image builds the fixture snapshot at image build time and copies `tests/fixtures/` and `docs/` in, so `/demo/portfolios` and `/methodology` work in the container. | The prompt asks for the snapshot at build time; the demo and methodology endpoints read those files. |
| D30 | 2026-10-13 | The web image bakes `VITE_API_URL` in at build time (build arg, default `http://localhost:8000`) and serves the static build with nginx using an SPA fallback. | Vite inlines env vars at build; the fallback makes deep links like `/companies/INE584A01023` work. |

## 7. Interview prep

1. **"Why treat MtCO2e as tonnes?"** In XBRL, "Mt" would mean megatonnes, but the values make that impossible: Titan's 3,878 would be 3.9 billion tonnes, which is absurd for a jewellery and watch company. So `normalise.py` reads it as metric tonnes, records that transformation in the provenance, and V1 raises a warning if the implied intensity passes 50,000 t per ₹ crore. That threshold only trips where the revenue is broken (Gujarat Themis, Everest Kanto).

2. **"Why is missing `None` and not 0?"** Zero is a claim ("we emitted nothing"); missing is the absence of a claim. If missing became 0, a non-reporting company would look perfectly clean and pull a portfolio's footprint down. So the parser never fills gaps, V4 turns a suspicious zero year (Gulshan) back into `None`, and the hypothesis test checks that `normalise()` never creates a value that wasn't filed.

3. **"What is EVIC and why not just market cap?"** EVIC is market cap plus total debt (plus minority interest): the whole capital base financing the company. PCAF divides by it so equity holders and lenders share the emissions. Using market cap alone would give shareholders 100% of a heavily indebted company's emissions. There's no real EVIC data in this build, so the demo uses labelled illustrative values.

4. **"How do you know your arithmetic is right?"** Three layers. `docs/worked-example.md` derives portfolio A by hand, and a test asserts the engine matches it to 1e-9. Hypothesis checks invariants: splitting a holding changes nothing, scaling all holdings by k scales financed emissions by k and leaves the footprint unchanged, coverage stays within 0–100, and attribution above 1 is rejected. The engine is pure functions with no I/O, so it is easy to test in isolation.

5. **"What happens to a company that doesn't report?"** It is **uncovered**, not estimated: it appears in the uncovered list with a reason, and coverage drops. PCAF allows sector-average estimates (data-quality scores 4–5), but the design doc keeps them out of the MVP so every number is a reported one. Coverage is shown in large type next to the footprint for exactly this reason.

6. **"Why does Gujarat Themis count for financed emissions but not WACI?"** Its emissions are fine; its revenue (₹165.82, ₹ crore typed into a rupee field) is not. Financed emissions use EVIC, not revenue, so the holding stays covered. WACI divides by revenue, so it is left out of WACI with the reason shown, and the share of the portfolio WACI covers is reported next to it.

7. **"Why not just fix the revenue by multiplying by 10⁷?"** Because it's a guess. 165.82 is probably ₹ crore, but it could be lakh or millions. The rule is to flag and wait for a second source: financial-results XBRL, the week-2 plan. Only two fixes are automatic, the MtCO2e reading and zero-as-missing, because both are unambiguous.

8. **"Why Parquet + DuckDB instead of Postgres?"** The data is small (about 1,000 companies × a few hundred fund holdings) and changes monthly. The deployed app only reads. Versioned Parquet snapshots built on a laptop (NSE blocks cloud servers) are immutable, diffable and need no database server. DuckDB runs SQL straight over them (`sql/coverage.sql`).

## 8. What's next (needs the laptop / real data)

1. **NSE bulk BRSR download** (Prompt 4 in the week-1 plan): query the JSON API in one-year windows from your laptop, keep the latest submission per company per fiscal year, then `pf build-snapshot` over ~1,000 filings and hand-check 30 against PDFs.
2. **Real EVIC**: NSE market-cap report at fiscal year end + borrowings from financial-results XBRL (field names still to verify), with the Dataful cross-check.
3. **AMC portfolio ingestion**: adapters for 3 AMCs (proposed: SBI MF, HDFC MF, Parag Parikh), V8 weight check, then the Funds ranking page.
4. **Second revenue source** so V2 errors can be corrected rather than only flagged.
