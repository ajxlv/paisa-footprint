"""Fund portfolio checks: V8 (weights add up), ISIN format, duplicate ISINs."""

from pydantic import BaseModel

from pf_core.funds import config
from pf_core.funds.models import INE_ISIN, FundHolding, FundPortfolio


class FundIssue(BaseModel):
    """One problem in one scheme's portfolio."""

    fund_key: str
    rule_id: str
    severity: str
    field: str
    message: str


def v8_nav_sum(portfolio: FundPortfolio) -> list[FundIssue]:
    """V8: % to NAV over every line (equity, debt, cash) must be within 95–105%."""
    weights = [h.pct_nav for h in portfolio.holdings if h.pct_nav is not None]
    if not weights:
        return [
            _issue(portfolio, "V8", "pct_nav", "No % to NAV values found; V8 cannot be checked")
        ]
    total = sum(weights)
    if config.V8_MIN_PCT_NAV <= total <= config.V8_MAX_PCT_NAV:
        return []
    return [
        _issue(
            portfolio,
            "V8",
            "pct_nav",
            f"Holdings sum to {total:.2f}% of NAV, outside "
            f"{config.V8_MIN_PCT_NAV:g}–{config.V8_MAX_PCT_NAV:g}%: "
            "lines may be missing or doubled",
        )
    ]


def isin_format(portfolio: FundPortfolio) -> list[FundIssue]:
    """An ISIN that is present but not a company ISIN (INE…) is reported, and never joined."""
    return [
        _issue(portfolio, "V8-isin", "isin", f"ISIN {h.isin!r} ({h.name}) is not in INE… format")
        for h in portfolio.holdings
        if h.isin is not None and not INE_ISIN.match(h.isin)
    ]


def merge_duplicates(portfolio: FundPortfolio) -> tuple[FundPortfolio, list[FundIssue]]:
    """Sum lines repeating an ISIN within a scheme (quantity, value, weight), with a warning."""
    merged: dict[str, FundHolding] = {}
    order: list[FundHolding | str] = []
    issues: list[FundIssue] = []
    for holding in portfolio.holdings:
        if holding.isin is None:
            order.append(holding)
            continue
        if holding.isin not in merged:
            merged[holding.isin] = holding
            order.append(holding.isin)
            continue
        first = merged[holding.isin]
        merged[holding.isin] = first.model_copy(
            update={
                "quantity": _add(first.quantity, holding.quantity),
                "market_value_inr": _add(first.market_value_inr, holding.market_value_inr),
                "pct_nav": _add(first.pct_nav, holding.pct_nav),
            }
        )
        issues.append(
            _issue(
                portfolio, "V8-dup", "isin", f"ISIN {holding.isin} listed more than once; summed"
            )
        )
    holdings = [merged[item] if isinstance(item, str) else item for item in order]
    return portfolio.model_copy(update={"holdings": holdings}), issues


def validate_fund(portfolio: FundPortfolio) -> tuple[FundPortfolio, list[FundIssue]]:
    """Merge duplicates, then run V8 and the ISIN check on the merged portfolio."""
    merged, issues = merge_duplicates(portfolio)
    return merged, issues + v8_nav_sum(merged) + isin_format(merged)


def _add(a: float | None, b: float | None) -> float | None:
    """Sum that keeps "unknown" unknown: None only if both sides are missing."""
    if a is None and b is None:
        return None
    return (a or 0.0) + (b or 0.0)


def _issue(portfolio: FundPortfolio, rule: str, field: str, message: str) -> FundIssue:
    return FundIssue(
        fund_key=portfolio.fund_key, rule_id=rule, severity="warning", field=field, message=message
    )
