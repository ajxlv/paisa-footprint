"""Rank funds by financed-emissions footprint, using the same PCAF engine as portfolios.

Only listed Indian equity lines (ISIN security type "01") form the equity universe; debt, cash and
unrecognised instruments are reported, not attributed. Coverage is the share of equity value with
reported emissions and an EVIC. A fund under 50% coverage is shown as "insufficient coverage" and
is not ranked, because its footprint would mostly describe the holdings we cannot see.
"""

from typing import Literal

from pydantic import BaseModel

from pf_core.funds.models import FundPortfolio
from pf_core.funds.validators import FundIssue
from pf_core.pcaf import config
from pf_core.pcaf.engine import compute_portfolio
from pf_core.pcaf.models import (
    CompanyEmissions,
    CompanyFinancials,
    Holding,
    HoldingResult,
    PortfolioResult,
    UncoveredHolding,
)

FundStatus = Literal["ranked", "insufficient coverage", "no equity holdings"]
TOP_CONTRIBUTORS = 10


class FundResult(BaseModel):
    """One fund's footprint, with everything needed to audit it."""

    fund_key: str
    amc: str
    scheme_name: str
    as_of_date: str | None
    source_file: str
    illustrative: bool
    status: FundStatus
    rank: int | None
    equity_value_inr: float
    non_equity_value_inr: float
    coverage_pct: float
    carbon_footprint_t_per_crore: float | None
    waci_t_per_crore_revenue: float | None
    financed_emissions_t: float
    pcaf_data_quality: float | None
    contains_illustrative_inputs: bool
    top_contributors: list[HoldingResult]
    uncovered: list[UncoveredHolding]
    issues: list[FundIssue]


def fund_result(
    portfolio: FundPortfolio,
    issues: list[FundIssue],
    emissions: dict[str, CompanyEmissions],
    financials: dict[str, CompanyFinancials],
    index: dict[str, str],
) -> FundResult:
    """Run the PCAF engine over a fund's equity lines."""
    equity = [h for h in portfolio.holdings if h.is_equity]
    valued = [h for h in equity if h.market_value_inr is not None and h.market_value_inr > 0]
    holdings = [
        Holding(isin_or_symbol=h.isin or h.name, company_key=index.get(h.isin or ""), value_inr=v)
        for h in valued
        if (v := h.market_value_inr) is not None
    ]
    unvalued = [
        UncoveredHolding(
            isin_or_symbol=h.isin or h.name,
            company_key=None,
            value_inr=0.0,
            reason="No market value in the file; cannot be weighted",
        )
        for h in equity
        if h not in valued
    ]
    result: PortfolioResult | None = (
        compute_portfolio(holdings, emissions, financials) if holdings else None
    )
    non_equity = sum(h.market_value_inr or 0.0 for h in portfolio.holdings if not h.is_equity)
    return _assemble(portfolio, issues, result, unvalued, non_equity)


def _assemble(
    portfolio: FundPortfolio,
    issues: list[FundIssue],
    result: PortfolioResult | None,
    unvalued: list[UncoveredHolding],
    non_equity: float,
) -> FundResult:
    coverage = result.coverage_pct if result else 0.0
    status: FundStatus = (
        "no equity holdings"
        if result is None
        else "ranked"
        if coverage >= config.FUND_MIN_COVERAGE_PCT
        else "insufficient coverage"
    )
    top = (
        sorted(result.holdings, key=lambda h: h.financed_emissions_t, reverse=True)
        if result
        else []
    )
    return FundResult(
        fund_key=portfolio.fund_key,
        amc=portfolio.amc,
        scheme_name=portfolio.scheme_name,
        as_of_date=portfolio.as_of_date.isoformat() if portfolio.as_of_date else None,
        source_file=portfolio.source_file,
        illustrative=portfolio.illustrative,
        status=status,
        rank=None,
        equity_value_inr=result.total_value_inr if result else 0.0,
        non_equity_value_inr=non_equity,
        coverage_pct=coverage,
        carbon_footprint_t_per_crore=result.carbon_footprint_t_per_crore if result else None,
        waci_t_per_crore_revenue=result.waci_t_per_crore_revenue if result else None,
        financed_emissions_t=result.financed_emissions_t if result else 0.0,
        pcaf_data_quality=result.pcaf_data_quality if result else None,
        contains_illustrative_inputs=portfolio.illustrative
        or (result.contains_illustrative_inputs if result else False),
        top_contributors=top[:TOP_CONTRIBUTORS],
        uncovered=(result.uncovered if result else []) + unvalued,
        issues=issues,
    )


def rank_funds(results: list[FundResult]) -> list[FundResult]:
    """Rank funds with enough coverage by footprint (lowest first); others keep rank None.

    Illustrative and real funds are ranked separately and must never share a table.
    """
    ranked: list[FundResult] = []
    for illustrative in (False, True):
        group = [r for r in results if r.illustrative == illustrative]
        eligible = sorted(
            (
                r
                for r in group
                if r.status == "ranked" and r.carbon_footprint_t_per_crore is not None
            ),
            key=lambda r: r.carbon_footprint_t_per_crore or 0.0,
        )
        positions = {r.fund_key: i + 1 for i, r in enumerate(eligible)}
        ranked.extend(r.model_copy(update={"rank": positions.get(r.fund_key)}) for r in group)
    return ranked
