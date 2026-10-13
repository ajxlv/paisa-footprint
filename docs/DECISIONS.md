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
| D3 | 2026-10-13 | Dropped the UTF-8 byte-order mark from the start of `.gitignore` while keeping its three entries. | The BOM made the first pattern read as `﻿data/` for some tools, so `data/` might not be ignored. |
