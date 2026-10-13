# Paisa Footprint

Paisa Footprint computes the **financed emissions** of Indian equity portfolios with the PCAF method, using companies' own BRSR filings to NSE. Every number traces back to a filing, an XBRL element and a formula.

## Run the tests

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check . && mypy pf_core && pytest
```
