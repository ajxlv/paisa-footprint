# Paisa Footprint

Paisa Footprint computes the **financed emissions** of Indian equity portfolios with the PCAF method, using companies' own BRSR filings to NSE. Every number traces back to a filing, an XBRL element and a formula, and every filing passes validators that catch real reporting errors.

<!-- Screenshot placeholder: add docs/screenshot.png of the Companies page once deployed. -->
_Screenshot coming soon._

> **Status:** week 1–2 build. Emissions come from **20 real BRSR filings (FY2025-26)**. There is **no real fund-holdings, market-cap or debt data yet**: the demo portfolios and EVIC values are synthetic and labelled "illustrative" everywhere they appear.

## Quickstart

Backend (Python 3.12):

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pf build-snapshot --input tests/fixtures/brsr --out data/snapshots/fixtures
uvicorn api.main:app --reload            # API docs at http://localhost:8000/docs
```

Frontend (Node 20+):

```bash
cd web
npm install
npm run dev                              # http://localhost:5173
```

Set `VITE_API_URL` if the API is not on `http://localhost:8000`.

Or run both with Docker: `docker compose up --build`, then open http://localhost:8080.

Windows (PowerShell) commands are in [docs/MORNING_REVIEW.md](docs/MORNING_REVIEW.md).

## Command line

```bash
pf parse tests/fixtures/brsr/BRSR_2729_WebXMLFile_20260916_165325349.xml   # one filing as JSON
pf validate tests/fixtures/brsr                                            # validation_report.csv + counts per rule
pf build-snapshot --input tests/fixtures/brsr --out data/snapshots/fixtures
pf compute --portfolio tests/fixtures/synthetic/portfolio_synthetic_a.csv \
           --evic tests/fixtures/synthetic/illustrative_evic.csv
duckdb < sql/coverage.sql        # coverage report (needs the DuckDB CLI; tests run it via Python)
```

## Tests

```bash
ruff check . && ruff format --check . && mypy pf_core && pytest
cd web && npm run build && npm test
```

Tests use fixtures only and never call NSE or any other network source.

## Project structure

```
pf_core/            pure Python core, no web code
  brsr/             parser.py (XBRL → BrsrFiling), validators.py (V1–V6, V9, V10),
                    normalise.py (safe fixes only), config.py (thresholds + reasons)
  pcaf/             engine.py (pure PCAF arithmetic), quality.py, models.py, inputs.py (loaders)
  snapshot.py       builds and reads Parquet snapshots
cli/pf.py           Typer CLI: parse, validate, build-snapshot, compute
api/main.py         read-only FastAPI over a snapshot
web/                React + TypeScript + Vite + Tailwind + Recharts
sql/coverage.sql    DuckDB coverage report
tests/              pytest + hypothesis; fixtures/brsr (20 real filings, read-only), fixtures/synthetic
docs/               design doc, methodology, worked example, decisions, morning review
```

## Status & limitations

- **20 filings only**, skewed towards smaller late filers. The NSE bulk download runs on a laptop (NSE blocks cloud servers) and is the next step.
- **No real EVIC.** The calculator takes EVIC you enter; the demo's EVIC values are made up.
- **No mutual-fund data.** AMC monthly portfolio ingestion is the next milestone; the Funds page says so and shows no fund numbers.
- **Scope 3 is excluded**, and companies that do not report emissions are **uncovered, not estimated**.
- **Revenue comes from BRSR.** Rule V2 flags scale errors (2 of 15 reporting filings) but cannot correct them until a second revenue source is added.

How the numbers are computed, and why: [docs/METHODOLOGY.md](docs/METHODOLOGY.md). A full hand calculation: [docs/worked-example.md](docs/worked-example.md).
