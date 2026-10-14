# Run 2 review: fixes and next milestones

Branch `run2/fixes-and-next`, cut from `main` at `c5a11d6` (PR #1 merged).

## 0. Baseline (before any run-2 change)

| Check | Result |
|---|---|
| `ruff check .` | clean |
| `mypy pf_core` (strict) | clean, 13 files |
| `pytest` | **88 passed**, 0 failed, 0 xfail |
| `pytest --cov=pf_core` | 97% overall (parser 91%, validators 97%, engine 92%, everything else 100%) |
| `npm ci && npm test -- --run` | **13 passed** |
| `npm run build` | `index` 64.2 kB (20.3 kB gzip), `markdown` 159.1 kB (48.5 kB gzip), `charts` 500.5 kB (146.3 kB gzip); all three load on first paint, so **initial JS ≈ 215 kB gzip** |
