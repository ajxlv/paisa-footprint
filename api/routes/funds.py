"""Fund endpoints. Real rankings and illustrative demo funds are served separately so the two
can never share a table."""

import json

from fastapi import APIRouter, HTTPException

from api.schemas import FundsResponse
from api.state import AppState, State
from pf_core.funds.adapters import GenericExcelAdapter
from pf_core.funds.ingest import RANKINGS_FILE, rank_snapshot_funds
from pf_core.funds.models import FundPortfolio
from pf_core.funds.ranking import FundResult
from pf_core.funds.validators import FundIssue, validate_fund
from pf_core.pcaf.inputs import load_evic_csv

router = APIRouter()


@router.get("/funds", response_model=FundsResponse)
def funds(state: State) -> FundsResponse:
    """Real fund rankings from the snapshot, if `pf rank-funds` has been run."""
    real = [f for f in _rankings(state) if not f.illustrative]
    return FundsResponse(available=bool(real), snapshot_dir=str(state.snapshot_dir), funds=real)


@router.get("/funds/{key}", response_model=FundResult)
def fund(key: str, state: State) -> FundResult:
    for f in _rankings(state):
        if f.fund_key == key and not f.illustrative:
            return f
    raise HTTPException(404, f"No fund with key {key!r}")


@router.get("/demo/funds", response_model=list[FundResult])
def demo_funds(state: State) -> list[FundResult]:
    """ILLUSTRATIVE funds: the synthetic AMC workbook run through the real engine."""
    return _demo_fund_results(state)


@router.get("/demo/funds/{key}", response_model=FundResult)
def demo_fund(key: str, state: State) -> FundResult:
    for f in _demo_fund_results(state):
        if f.fund_key == key:
            return f
    raise HTTPException(404, f"No illustrative fund with key {key!r}")


def _rankings(state: AppState) -> list[FundResult]:
    path = state.snapshot_dir / RANKINGS_FILE
    if not path.exists():
        return []
    return [FundResult.model_validate(r) for r in json.loads(path.read_text(encoding="utf-8"))]


def _demo_fund_results(state: AppState) -> list[FundResult]:
    workbook = state.demo_dir / "amc_portfolio_synthetic.xlsx"
    if not workbook.exists():
        raise HTTPException(404, "Synthetic AMC workbook not found")
    portfolios: list[FundPortfolio] = []
    issues: list[FundIssue] = []
    for portfolio in GenericExcelAdapter("Illustrative AMC").parse(workbook):
        merged, found = validate_fund(portfolio)
        portfolios.append(merged)
        issues.extend(found)
    _ = state.snapshot  # raises a clear 503 if there is no snapshot
    financials = load_evic_csv(state.demo_dir / "illustrative_evic.csv")
    return rank_snapshot_funds(state.snapshot_dir, financials, portfolios, issues)
