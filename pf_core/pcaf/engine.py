"""PCAF financed-emissions engine: pure functions, no I/O.

Formulas (design doc, section 2):

    attribution_h        = value_h / EVIC_company                  (0 < a <= 1)
    financed_emissions_h = attribution_h * (scope1_t + scope2_t)
    portfolio_financed   = sum of financed_emissions_h over covered holdings
    coverage_pct         = covered_value / total_value * 100
    carbon_footprint     = portfolio_financed / covered_value * 1e7      tCO2e per ₹ crore invested
    WACI                 = sum (value_h / waci_value) * (S1+S2) / (revenue / 1e7)
                                                                     tCO2e per ₹ crore revenue
    data quality         = value-weighted mean of 1 (assured) / 2 (not assured)

A holding is uncovered (left out, listed with a reason) when its company is unknown, has no
emissions row, is excluded, has an error on Scope 1/2, has no EVIC, or would get attribution > 1.
WACI needs no EVIC (design doc: "the fallback metric when EVIC data is missing"), so its universe
is every holding with usable emissions and a trustworthy revenue, with or without EVIC.
"""

from pf_core.pcaf.models import (
    CompanyEmissions,
    CompanyFinancials,
    Holding,
    HoldingResult,
    PortfolioResult,
    UncoveredHolding,
)
from pf_core.pcaf.quality import holding_score, portfolio_score

INR_PER_CRORE = 1e7
SCOPE_FIELDS = {"scope1", "scope2", "scope1_t", "scope2_t", "scope1+scope2"}
REVENUE_FIELDS = {"revenue_from_operations_inr", "revenue_inr"}


class AttributionError(ValueError):
    """Attribution outside (0, 1]: the holding is worth more than the whole company."""


def attribution(value_inr: float, evic_inr: float) -> float:
    """Share of the company owned. Rejects anything outside (0, 1]."""
    if evic_inr <= 0:
        raise AttributionError(f"EVIC must be positive, got {evic_inr}")
    share = value_inr / evic_inr
    if not 0 < share <= 1:
        raise AttributionError(
            f"attribution {share:.6g} outside (0, 1]: value ₹{value_inr:,.0f} vs EVIC "
            f"₹{evic_inr:,.0f}"
        )
    return share


def compute_portfolio(
    holdings: list[Holding],
    emissions: dict[str, CompanyEmissions],
    financials: dict[str, CompanyFinancials],
) -> PortfolioResult:
    """Financed emissions, footprint, WACI, coverage and data quality for one portfolio."""
    covered: list[HoldingResult] = []
    uncovered: list[UncoveredHolding] = []
    waci_terms: list[tuple[float, float]] = []
    illustrative = False

    for holding in holdings:
        company = emissions.get(holding.company_key) if holding.company_key else None
        fin = financials.get(holding.company_key) if holding.company_key else None
        if fin is not None and fin.evic_is_illustrative:
            illustrative = True
        waci_intensity, waci_reason = _waci_intensity(company)
        if waci_intensity is not None:
            waci_terms.append((holding.value_inr, waci_intensity))
        reason = _uncovered_reason(holding, company, fin)
        if reason is not None:
            uncovered.append(_uncovered(holding, reason))
            continue
        assert company is not None and fin is not None and fin.evic_inr is not None
        try:
            share = attribution(holding.value_inr, fin.evic_inr)
        except AttributionError as exc:
            uncovered.append(_uncovered(holding, f"Rejected: {exc}"))
            continue
        covered.append(_holding_result(holding, company, fin, share, waci_intensity, waci_reason))

    return _totals(holdings, covered, uncovered, waci_terms, illustrative)


def _uncovered_reason(
    holding: Holding, company: CompanyEmissions | None, fin: CompanyFinancials | None
) -> str | None:
    if holding.company_key is None:
        return "ISIN/symbol not matched to any company in the snapshot (V7)"
    if company is None:
        return "No BRSR emissions data for this company"
    if company.quality_flag == "excluded":
        return f"Company excluded from emissions ({', '.join(company.issues) or 'no data'})"
    if set(company.error_fields) & SCOPE_FIELDS:
        return "Error-severity issue on Scope 1/2"
    if company.scope1_t is None or company.scope2_t is None:
        return "Scope 1 or Scope 2 not reported"
    if fin is None or fin.evic_inr is None:
        return "No EVIC available for this company"
    return None


def _waci_intensity(company: CompanyEmissions | None) -> tuple[float | None, str | None]:
    """(S1+S2) per ₹ crore revenue, or None with the reason it cannot be used."""
    if company is None or company.quality_flag == "excluded":
        return None, "no usable emissions"
    if company.scope1_t is None or company.scope2_t is None:
        return None, "Scope 1 or Scope 2 not reported"
    if set(company.error_fields) & SCOPE_FIELDS:
        return None, "error-severity issue on Scope 1/2"
    if set(company.error_fields) & REVENUE_FIELDS:
        return None, "revenue fails validation (V2 scale error)"
    if not company.revenue_inr or company.revenue_inr <= 0:
        return None, "revenue not reported"
    return (company.scope1_t + company.scope2_t) / (company.revenue_inr / INR_PER_CRORE), None


def _holding_result(
    holding: Holding,
    company: CompanyEmissions,
    fin: CompanyFinancials,
    share: float,
    waci_intensity: float | None,
    waci_reason: str | None,
) -> HoldingResult:
    assert company.scope1_t is not None and company.scope2_t is not None
    assert fin.evic_inr is not None
    scope12 = company.scope1_t + company.scope2_t
    financed = share * scope12
    return HoldingResult(
        isin_or_symbol=holding.isin_or_symbol,
        company_key=company.company_key,
        company_name=company.company_name,
        fiscal_year=company.fiscal_year,
        value_inr=holding.value_inr,
        evic_inr=fin.evic_inr,
        evic_source=fin.evic_source,
        evic_is_illustrative=fin.evic_is_illustrative,
        attribution=share,
        scope1_t=company.scope1_t,
        scope2_t=company.scope2_t,
        financed_emissions_t=financed,
        revenue_inr=company.revenue_inr,
        intensity_t_per_crore_revenue=waci_intensity,
        in_waci=waci_intensity is not None,
        waci_exclusion_reason=waci_reason,
        pcaf_data_quality=holding_score(company.assured),
        formula=(
            f"attribution = {holding.value_inr:,.0f} / {fin.evic_inr:,.0f} = {share:.6g}; "
            f"financed = {share:.6g} × ({company.scope1_t:,.2f} + {company.scope2_t:,.2f}) "
            f"= {financed:,.4f} tCO2e"
        ),
        provenance=company.provenance,
    )


def _uncovered(holding: Holding, reason: str) -> UncoveredHolding:
    return UncoveredHolding(
        isin_or_symbol=holding.isin_or_symbol,
        company_key=holding.company_key,
        value_inr=holding.value_inr,
        reason=reason,
    )


def _totals(
    holdings: list[Holding],
    covered: list[HoldingResult],
    uncovered: list[UncoveredHolding],
    waci_terms: list[tuple[float, float]],
    illustrative: bool,
) -> PortfolioResult:
    total_value = sum(h.value_inr for h in holdings)
    covered_value = sum(h.value_inr for h in covered)
    financed = sum(h.financed_emissions_t for h in covered)
    waci_value = sum(value for value, _ in waci_terms)
    waci = (
        sum(value / waci_value * intensity for value, intensity in waci_terms)
        if waci_value > 0
        else None
    )
    return PortfolioResult(
        total_value_inr=total_value,
        covered_value_inr=covered_value,
        coverage_pct=covered_value / total_value * 100 if total_value > 0 else 0.0,
        financed_emissions_t=financed,
        carbon_footprint_t_per_crore=(
            financed / covered_value * INR_PER_CRORE if covered_value > 0 else None
        ),
        waci_t_per_crore_revenue=waci,
        waci_value_inr=waci_value,
        waci_coverage_pct=waci_value / total_value * 100 if total_value > 0 else 0.0,
        pcaf_data_quality=portfolio_score([(h.value_inr, h.pcaf_data_quality) for h in covered]),
        holdings=covered,
        uncovered=uncovered,
        contains_illustrative_inputs=illustrative,
    )
