# EVIC data plan

The engine needs **EVIC** (enterprise value including cash) for every company a portfolio holds.
No real EVIC is in the repo yet; the demo uses labelled illustrative values. This page says where
to get the real inputs, how to fill the template, and how they are checked.

## Definition (PCAF, listed equity)

```
EVIC = market capitalisation at fiscal year end
     + total debt (book value of borrowings, current + non-current)
     + minority (non-controlling) interest        (optional)
```

There is **no deduction for cash**. The denominator is the whole capital base financing the
company, shareholders and lenders together. See `pf_core/pcaf/evic.py` and `docs/METHODOLOGY.md`.

## The template

`data_templates/evic_template.csv` (headers only):

```
company_key,market_cap_inr,total_debt_inr,minority_interest_inr,as_of_date,source
```

| Column | Meaning | Example format |
|---|---|---|
| `company_key` | ISIN, exactly as in the snapshot (e.g. the 12-character `INE…` code) | `INE584A01023` |
| `market_cap_inr` | Market capitalisation in **rupees** (not crore) at the fiscal year end | `123456789012` |
| `total_debt_inr` | Total borrowings in rupees, current + non-current. **Leave blank if unknown, never 0** | `9876543210` |
| `minority_interest_inr` | Non-controlling interest in rupees; blank if none or unknown | |
| `as_of_date` | Date the market cap refers to | `2026-03-31` |
| `source` | Where each number came from, so it can be audited | `NSE mcap report Mar-2026; FY26 results XBRL` |

Save your filled copy as `data/evic/evic_<YYYY-MM>.csv` (git-ignored). Do **not** put
"illustrative" or "synthetic" in the file name: the loader treats such files as illustrative.

Run it with:

```powershell
pf compute --portfolio <holdings.csv> --evic-real data/evic/evic_2026-03.csv --snapshot data/snapshots/<YYYY-MM>
```

## Where to get each number (to verify; nothing here has been downloaded)

1. **Market capitalisation.** NSE publishes a "market capitalisation of all companies" report,
   listing each company's market cap at a date. It is updated periodically; per the design doc,
   around March and December. Download the one closest to **31 March** (the fiscal year end for
   most companies). It is usually quoted in ₹ lakh or ₹ crore, so **convert to rupees** before
   filling `market_cap_inr` (₹1 crore = 1,00,00,000).
2. **Total debt.** From each company's annual financial results, which NSE also files as XBRL:
   borrowings, non-current plus current. The exact XBRL element names are **not yet verified**
   (design doc, open question 2). Confirm them on 2–3 real results files first, then extract.
   If you cannot find debt for a company, leave it blank. The loader then uses market cap only,
   flags it `evic_partial`, and caps that holding's data quality at 2.
3. **Minority interest.** From the consolidated balance sheet ("non-controlling interest").
   Optional.
4. **Cross-check.** For 5 large companies, compare your EVIC with a reputable market data
   source. Disagreements over 10% usually mean a units slip (lakh vs crore).

## Validation applied by the loader

| Rule | Condition | Severity | Effect |
|---|---|---|---|
| E1 | `market_cap_inr` missing or ≤ 0 | error | No EVIC for that company; its holdings are uncovered |
| E2 | `total_debt_inr` missing | warning | EVIC = market cap (+ minority interest), `evic_partial`, DQ ≤ 2 |
| E3 | `as_of_date` unreadable, or more than 15 months from the emissions fiscal year end | warning | Used, but reported |

`contains_illustrative_inputs` is `false` only when every EVIC used in a computation came from a
non-illustrative file. Mixing in a single illustrative value keeps the whole result marked
illustrative.
