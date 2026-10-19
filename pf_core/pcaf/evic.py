"""Load real EVIC data and validate it.

**EVIC** (enterprise value including cash), as PCAF defines it for listed equity, is

    EVIC = market capitalisation at fiscal year end + total debt + minority interest

with **no deduction for cash**, unlike the usual enterprise value. PCAF keeps cash in because
the denominator is meant to be the whole capital base financing the company (shareholders and
lenders together), not what it would cost to buy it. Dividing by market cap alone would hand
equity holders all of a heavily indebted company's emissions. (PCAF also includes preferred-share
market value, which is rare among Indian listed companies; put it in `market_cap_inr` if present.)

CSV columns: `company_key` (ISIN), `market_cap_inr`, `total_debt_inr`,
`minority_interest_inr` (optional), `as_of_date` (YYYY-MM-DD), `source`.

Validation (each finding is returned, never swallowed):
* market cap missing or <= 0: **error**, and the company gets no EVIC (its holdings go uncovered);
* total debt missing: EVIC = market cap (+ minority interest), flagged `evic_partial`, DQ capped
  at 2;
* `as_of_date` more than 15 months from the emissions fiscal year end: **warning**.
"""

from datetime import date
from pathlib import Path

from pydantic import BaseModel

from pf_core.pcaf import config
from pf_core.pcaf.inputs import read_commented_csv
from pf_core.pcaf.models import CompanyFinancials

REQUIRED_COLUMNS = ("company_key", "market_cap_inr", "total_debt_inr", "as_of_date", "source")
_ILLUSTRATIVE_MARKERS = ("illustrative", "synthetic")


class EvicIssue(BaseModel):
    """One problem found in an EVIC row."""

    company_key: str
    rule_id: str
    severity: str
    message: str


def compute_evic(
    market_cap_inr: float, total_debt_inr: float | None, minority_interest_inr: float | None
) -> tuple[float, bool]:
    """(EVIC, is_partial). Missing debt makes the EVIC partial; minority interest is optional."""
    evic = market_cap_inr + (total_debt_inr or 0.0) + (minority_interest_inr or 0.0)
    return evic, total_debt_inr is None


def months_apart(a: date, b: date) -> int:
    """Whole calendar months between two dates, ignoring the day of month."""
    return abs((a.year - b.year) * 12 + (a.month - b.month))


def load_evic_real(
    path: str | Path, emissions_fy_end: dict[str, date] | None = None
) -> tuple[dict[str, CompanyFinancials], list[EvicIssue]]:
    """Read a real-EVIC CSV. Returns financials for valid rows and every issue found."""
    path = Path(path)
    frame = read_commented_csv(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(
            f"{path.name}: missing columns {missing}; see data_templates/evic_template.csv"
        )
    illustrative_file = any(m in path.name.lower() for m in _ILLUSTRATIVE_MARKERS)
    financials: dict[str, CompanyFinancials] = {}
    issues: list[EvicIssue] = []
    for row in frame.to_dict(orient="records"):
        key = str(row["company_key"]).strip()
        record = {str(k): v for k, v in row.items()}
        fin, row_issues = _row(key, record, illustrative_file, (emissions_fy_end or {}).get(key))
        issues.extend(row_issues)
        if fin is not None:
            financials[key] = fin
    return financials, issues


def _row(
    key: str, row: dict[str, object], illustrative_file: bool, fy_end: date | None
) -> tuple[CompanyFinancials | None, list[EvicIssue]]:
    issues: list[EvicIssue] = []
    market_cap = _number(row.get("market_cap_inr"))
    if market_cap is None or market_cap <= 0:
        issues.append(
            _issue(key, "E1", "error", f"market_cap_inr is {row.get('market_cap_inr')!r}; no EVIC")
        )
        return None, issues
    debt = _number(row.get("total_debt_inr"))
    evic, partial = compute_evic(market_cap, debt, _number(row.get("minority_interest_inr")))
    if partial:
        issues.append(
            _issue(
                key,
                "E2",
                "warning",
                "total_debt_inr missing: EVIC is market cap only (evic_partial, DQ ≤ 2)",
            )
        )
    as_of = _date(row.get("as_of_date"))
    if as_of is None:
        issues.append(
            _issue(key, "E3", "warning", f"as_of_date {row.get('as_of_date')!r} is not YYYY-MM-DD")
        )
    elif fy_end is not None and months_apart(as_of, fy_end) > config.EVIC_MAX_AGE_MONTHS:
        issues.append(
            _issue(
                key,
                "E3",
                "warning",
                f"EVIC as of {as_of} is more than {config.EVIC_MAX_AGE_MONTHS} months from the "
                f"emissions fiscal year end {fy_end}",
            )
        )
    source = str(row.get("source") or "").strip()
    return (
        CompanyFinancials(
            company_key=key,
            evic_inr=evic,
            evic_source=source or "unspecified",
            evic_is_illustrative=illustrative_file
            or any(m in source.lower() for m in _ILLUSTRATIVE_MARKERS),
            evic_partial=partial,
            evic_as_of=as_of,
        ),
        issues,
    )


def _issue(key: str, rule: str, severity: str, message: str) -> EvicIssue:
    return EvicIssue(company_key=key, rule_id=rule, severity=severity, message=message)


def _number(value: object) -> float | None:
    """Blank means missing (None), never zero."""
    text = str(value).strip().replace(",", "") if value is not None else ""
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None
