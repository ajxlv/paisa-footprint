"""Portfolio calculator endpoints (user-supplied holdings and EVIC; demo portfolios)."""

from pathlib import Path

from fastapi import APIRouter

from api.schemas import DemoPortfolio, EvicIn, HoldingIn, PortfolioRequest
from api.state import State
from pf_core.pcaf.engine import compute_portfolio
from pf_core.pcaf.inputs import (
    company_index,
    emissions_from_snapshot,
    load_evic_csv,
    load_portfolio_csv,
)
from pf_core.pcaf.models import CompanyFinancials, Holding, PortfolioResult

router = APIRouter()


@router.post("/portfolio/compute", response_model=PortfolioResult)
def portfolio_compute(request: PortfolioRequest, state: State) -> PortfolioResult:
    index = company_index(state.snapshot)
    holdings = [
        Holding(
            isin_or_symbol=h.isin_or_symbol,
            company_key=index.get(h.isin_or_symbol.strip().upper()),
            value_inr=h.value_inr,
        )
        for h in request.holdings
    ]
    financials = {e.company_key: CompanyFinancials(**e.model_dump()) for e in request.evic}
    return compute_portfolio(holdings, emissions_from_snapshot(state.snapshot), financials)


@router.get("/demo/portfolios", response_model=list[DemoPortfolio])
def demo_portfolios(state: State) -> list[DemoPortfolio]:
    evic = [
        EvicIn(**f.model_dump())
        for f in load_evic_csv(state.demo_dir / "illustrative_evic.csv").values()
        if f.evic_inr is not None
    ]
    index = company_index(state.snapshot)
    return [
        DemoPortfolio(
            id=path.stem,
            description=_first_comment(path),
            illustrative=True,
            holdings=[
                HoldingIn(isin_or_symbol=h.isin_or_symbol, value_inr=h.value_inr)
                for h in load_portfolio_csv(path, index)
            ],
            evic=evic,
        )
        for path in sorted(state.demo_dir.glob("portfolio_synthetic_*.csv"))
    ]


def _first_comment(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            return line.lstrip("# ").strip()
    return path.stem
