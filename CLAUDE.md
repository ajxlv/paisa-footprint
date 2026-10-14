# Rules for working in this repo

Paisa Footprint computes PCAF financed emissions for Indian equity portfolios from companies' BRSR filings. Its credibility comes from transparent, checkable arithmetic, so these rules are not optional.

1. **The design doc is the source of truth.** `docs/design-doc.md` defines what we build, the PCAF formulas and the validators. If code or a prompt disagrees with it, the design doc wins; record any deliberate deviation in `docs/DECISIONS.md`.
2. **Never invent XBRL element names.** Only use names you have confirmed exist by searching `tests/fixtures/brsr/`. Element names in use are listed in `pf_core/brsr/parser.py` and `docs/DECISIONS.md`.
3. **Fixtures are read-only.** `tests/fixtures/brsr/*.xml` are 20 real BRSR filings. Never edit, reformat or regenerate them.
4. **Missing means `None`, never `0`.** A fact that is absent is unknown, not zero. Never fill gaps with zeros.
5. **Synthetic data is labelled.** Anything made up lives in `tests/fixtures/synthetic/` or `web/src/demo/`, has `synthetic` or `illustrative` in its filename, and is shown in the UI with an "Illustrative data, not real market data" badge. There is no real fund-holdings, market-cap or debt data in this repo yet.
6. **Tests never hit the network.** Tests use fixtures only. Never call NSE, BSE, AMC sites or any data source from tests or from the API.
7. **Every validator needs a test built from a real fixture** (or, where no fixture triggers it, a clearly constructed filing plus a negative test on real fixtures).
8. **Never silently drop data.** Excluded filings, companies and holdings appear in a report with a reason.
9. **Every number shown must be traceable** to its source file, XBRL element, context/period, unit and transformation.
10. **Never delete or weaken a test to make it pass.** Use `xfail` with a reason and record it in `docs/MORNING_REVIEW.md`.

## Checks to run before committing

```bash
ruff check .
mypy pf_core
pytest
cd web && npm run build && npm test
```
