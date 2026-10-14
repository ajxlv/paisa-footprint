"""Read AMC files into a funds Parquet table, and rank funds from a snapshot."""

import json
from datetime import date
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

import pandas as pd
from openpyxl.utils.exceptions import InvalidFileException

from pf_core.funds.adapters import GenericExcelAdapter
from pf_core.funds.models import FundHolding, FundPortfolio
from pf_core.funds.ranking import FundResult, fund_result, rank_funds
from pf_core.funds.validators import FundIssue, validate_fund
from pf_core.pcaf.inputs import company_index, emissions_from_snapshot
from pf_core.pcaf.models import CompanyFinancials
from pf_core.snapshot import load_snapshot

FUNDS_FILE = "funds.parquet"
FUND_ISSUES_FILE = "fund_issues.parquet"
RANKINGS_FILE = "fund_rankings.json"
_PORTFOLIO_COLUMNS = [
    "fund_key",
    "amc",
    "scheme_name",
    "as_of_date",
    "source_file",
    "sheet",
    "illustrative",
]
_HOLDING_COLUMNS = ["isin", "name", "quantity", "market_value_inr", "pct_nav", "is_equity"]


def parse_amc_dir(
    input_dir: str | Path,
) -> tuple[list[FundPortfolio], list[FundIssue], dict[str, str]]:
    """Parse every `<amc>/*.xlsx` under `input_dir`. Files that fail are returned with a reason."""
    portfolios: list[FundPortfolio] = []
    issues: list[FundIssue] = []
    failures: dict[str, str] = {}
    for path in sorted(Path(input_dir).rglob("*.xlsx")):
        try:
            parsed = GenericExcelAdapter(amc=path.parent.name).parse(path)
        except (InvalidFileException, BadZipFile, OSError, KeyError, ValueError) as exc:
            failures[str(path)] = f"{type(exc).__name__}: {exc}"
            continue
        if not parsed:
            failures[str(path)] = "No header row with 'ISIN' and market value / % to NAV found"
        for portfolio in parsed:
            merged, found = validate_fund(portfolio)
            portfolios.append(merged)
            issues.extend(found)
    return portfolios, issues, failures


def write_funds(
    portfolios: list[FundPortfolio], issues: list[FundIssue], out_file: str | Path
) -> None:
    """One row per holding in `funds.parquet`; issues in `fund_issues.parquet` beside it."""
    out = Path(out_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {**_portfolio_record(p), **h.model_dump(), "is_equity": h.is_equity}
        for p in portfolios
        for h in p.holdings
    ]
    pd.DataFrame(rows, columns=_PORTFOLIO_COLUMNS + _HOLDING_COLUMNS).to_parquet(out, index=False)
    issue_frame = pd.DataFrame(
        [i.model_dump() for i in issues], columns=list(FundIssue.model_fields)
    )
    issue_frame.to_parquet(out.with_name(FUND_ISSUES_FILE), index=False)


def _portfolio_record(p: FundPortfolio) -> dict[str, Any]:
    return {
        "fund_key": p.fund_key,
        "amc": p.amc,
        "scheme_name": p.scheme_name,
        "as_of_date": p.as_of_date.isoformat() if p.as_of_date else None,
        "source_file": p.source_file,
        "sheet": p.sheet,
        "illustrative": p.illustrative,
    }


def read_funds(funds_file: str | Path) -> tuple[list[FundPortfolio], list[FundIssue]]:
    """Inverse of `write_funds`."""
    path = Path(funds_file)
    frame = pd.read_parquet(path).astype(object)
    frame = frame.where(frame.notna(), None)
    portfolios: list[FundPortfolio] = []
    for _, group in frame.groupby("fund_key", sort=False):
        first = group.iloc[0]
        holdings = [
            FundHolding(
                **{k: row[k] for k in ("isin", "name", "quantity", "market_value_inr", "pct_nav")}
            )
            for row in group.to_dict(orient="records")
        ]
        portfolios.append(
            FundPortfolio(
                amc=str(first["amc"]),
                scheme_name=str(first["scheme_name"]),
                as_of_date=date.fromisoformat(first["as_of_date"]) if first["as_of_date"] else None,
                source_file=str(first["source_file"]),
                sheet=str(first["sheet"]),
                illustrative=bool(first["illustrative"]),
                holdings=holdings,
            )
        )
    issues_path = path.with_name(FUND_ISSUES_FILE)
    issues = (
        [
            FundIssue(**{str(k): v for k, v in r.items()})
            for r in pd.read_parquet(issues_path).to_dict(orient="records")
        ]
        if issues_path.exists()
        else []
    )
    return portfolios, issues


def rank_snapshot_funds(
    snapshot_dir: str | Path,
    financials: dict[str, CompanyFinancials],
    portfolios: list[FundPortfolio] | None = None,
    issues: list[FundIssue] | None = None,
) -> list[FundResult]:
    """Rank funds against a snapshot's emissions. Defaults to the snapshot's own `funds.parquet`."""
    snap_dir = Path(snapshot_dir)
    if portfolios is None:
        portfolios, issues = read_funds(snap_dir / FUNDS_FILE)
    snap = load_snapshot(snap_dir)
    emissions, index = emissions_from_snapshot(snap), company_index(snap)
    by_fund: dict[str, list[FundIssue]] = {}
    for issue in issues or []:
        by_fund.setdefault(issue.fund_key, []).append(issue)
    results = [
        fund_result(p, by_fund.get(p.fund_key, []), emissions, financials, index)
        for p in portfolios
    ]
    return rank_funds(results)


def write_rankings(results: list[FundResult], snapshot_dir: str | Path) -> Path:
    path = Path(snapshot_dir) / RANKINGS_FILE
    path.write_text(
        json.dumps([r.model_dump(mode="json") for r in results], indent=2), encoding="utf-8"
    )
    return path
