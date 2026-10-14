"""Load engine inputs from CSV files and from a snapshot.

Kept apart from `engine.py` so the engine stays free of I/O. CSV files may start with `#`
comment lines (the synthetic fixtures use them for their "illustrative" warning).
"""

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from pf_core.pcaf.models import CompanyEmissions, CompanyFinancials, Holding
from pf_core.snapshot import Snapshot

_ILLUSTRATIVE_MARKERS = ("illustrative", "synthetic")


def read_commented_csv(path: str | Path) -> pd.DataFrame:
    """CSV with leading `#` comment lines; every column read as text so nothing is coerced."""
    return pd.read_csv(path, comment="#", dtype=str, keep_default_na=False)


def load_evic_csv(path: str | Path) -> dict[str, CompanyFinancials]:
    """EVIC rows keyed by company_key.

    A row is illustrative if its own column says so, or if the file is named or headed as
    illustrative/synthetic. Erring towards "illustrative" keeps made-up numbers labelled.
    """
    path = Path(path)
    header = path.read_text(encoding="utf-8").lower()
    file_flag = any(marker in path.name.lower() for marker in _ILLUSTRATIVE_MARKERS) or any(
        line.startswith("#") and "illustrative" in line for line in header.splitlines()
    )
    frame = read_commented_csv(path)
    result: dict[str, CompanyFinancials] = {}
    for row in frame.to_dict(orient="records"):
        evic = str(row.get("evic_inr", "")).strip()
        result[str(row["company_key"])] = CompanyFinancials(
            company_key=str(row["company_key"]),
            evic_inr=float(evic) if evic else None,
            evic_source=str(row.get("evic_source") or path.name),
            evic_is_illustrative=file_flag
            or str(row.get("evic_is_illustrative", "")).lower() == "true",
        )
    return result


def company_index(snapshot: Snapshot) -> dict[str, str]:
    """Map ISIN, upper-cased NSE symbol and company_key to company_key."""
    index: dict[str, str] = {}
    for row in snapshot.companies:
        key = str(row["company_key"])
        index[key] = key
        if row.get("isin"):
            index[str(row["isin"]).upper()] = key
        if row.get("nse_symbol"):
            index[str(row["nse_symbol"]).upper()] = key
    return index


def load_portfolio_csv(path: str | Path, index: dict[str, str]) -> list[Holding]:
    """Holdings from `isin_or_symbol,value_inr`; unmatched identifiers keep company_key=None."""
    frame = read_commented_csv(path)
    return [
        Holding(
            isin_or_symbol=str(row["isin_or_symbol"]),
            company_key=index.get(str(row["isin_or_symbol"]).strip().upper()),
            value_inr=float(row["value_inr"]),
        )
        for row in frame.to_dict(orient="records")
    ]


def emissions_from_snapshot(snapshot: Snapshot) -> dict[str, CompanyEmissions]:
    """Current-year emissions per company, with the fields that carry error-severity issues."""
    errors: dict[tuple[str, str], list[str]] = {}
    for issue in snapshot.issues:
        if issue["severity"] == "error":
            errors.setdefault((issue["company_key"], issue["fiscal_year"]), []).append(
                str(issue["field"])
            )
    return {
        str(row["company_key"]): _emissions(
            row, errors.get((row["company_key"], row["fiscal_year"]))
        )
        for row in snapshot.companies
        if row["is_current"]
    }


def _emissions(row: dict[str, Any], error_fields: list[str] | None) -> CompanyEmissions:
    return CompanyEmissions(
        company_key=str(row["company_key"]),
        company_name=str(row["company_name"]),
        scope1_t=row["scope1_t"],
        scope2_t=row["scope2_t"],
        revenue_inr=row["revenue_inr_resolved"],
        revenue_corrected=bool(row["revenue_corrected"]),
        revenue_resolution=str(row["revenue_resolution"]),
        assured=row["assured"],
        fiscal_year=str(row["fiscal_year"]),
        period_end=date.fromisoformat(str(row["period_end"])) if row.get("period_end") else None,
        quality_flag=row["quality_flag"],
        error_fields=error_fields or [],
        issues=list(row["issues"]),
        provenance=row["provenance"],
    )
