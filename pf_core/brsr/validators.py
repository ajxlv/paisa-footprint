"""Validators V1–V6, V9 and V10 for parsed BRSR filings.

Each validator is a pure function `(BrsrFiling) -> list[Issue]`. Validators only *describe*
problems; the few safe fixes live in `normalise.py`. V7 (unmatched holding ISIN) belongs to the
PCAF engine, which reports unmatched holdings as uncovered. V8 (fund weights sum to 95–105%) needs
AMC holdings data, which does not exist in this repo yet.
"""

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel

from pf_core.brsr import config
from pf_core.brsr.models import BrsrFiling, FiscalYearData
from pf_core.brsr.revenue import RevenueResolution, resolve_revenue

Severity = Literal["error", "warning", "info"]


class Issue(BaseModel):
    """One problem found in one filing."""

    rule_id: str
    severity: Severity
    field: str
    fiscal_year: str
    message: str
    observed_value: str | None
    suggested_fix: str | None = None


RULE_DESCRIPTIONS: dict[str, str] = {
    "V1": "Emissions tagged 'MtCO2e' are read as metric tonnes; flagged if that implies an "
    "implausible intensity.",
    "V2": "Revenue under ₹10 lakh for a listed company is a scale error; reported intensity is "
    "untrustworthy.",
    "V2-fix": "Revenue typed in ₹ crore or lakh, corrected because the other revenue field "
    "confirms the scale unambiguously; flagged, and WACI data quality capped at 2.",
    "V3": "RevenueFromOperations and TotalRevenueOfTheCompany differ by more than 2x.",
    "V4": "A year reporting zero Scope 1 and zero Scope 2 next to a non-zero year is treated as "
    "missing.",
    "V5": "Scope 1 or Scope 2 changes more than 2x year on year; needs human review.",
    "V6": "Fiscal year does not end on 31 March; dates carried through as filed.",
    "V9": "Company states GHG disclosure is not applicable; excluded from emissions.",
    "V10": "Reported intensity disagrees with (Scope 1 + Scope 2) / revenue by more than 1%.",
}


def fy_label(year: FiscalYearData) -> str:
    """Human label such as `FY2025-26`, built from the filed period (works for June year-ends)."""
    return f"FY{year.period_start.year}-{year.period_end.year % 100:02d}"


def years(filing: BrsrFiling) -> list[FiscalYearData]:
    """Current year first, then the previous year if filed."""
    return [filing.fy_current] + ([filing.fy_previous] if filing.fy_previous else [])


def year_revenue(year: FiscalYearData) -> RevenueResolution:
    """Cross-checked revenue for one year (rule V2-fix); see `revenue.py`."""
    return resolve_revenue(year.revenue_from_operations_inr, year.total_revenue_inr)


def scope12_t_per_crore(year: FiscalYearData, revenue: float | None = None) -> float | None:
    """(S1+S2) per ₹ crore of revenue (filed RevenueFromOperations unless `revenue` is given)."""
    revenue = year.revenue_from_operations_inr if revenue is None else revenue
    if year.scope1 is None or year.scope2 is None or not revenue:
        return None
    return (year.scope1 + year.scope2) / (revenue / config.INR_PER_CRORE)


def _trusted_revenue(year: FiscalYearData) -> float | None:
    """Resolved revenue if it passes the V2 check (as filed or safely corrected), else None."""
    revenue = year_revenue(year).revenue_inr_resolved
    if revenue is None or revenue < config.V2_MIN_PLAUSIBLE_REVENUE_INR:
        return None
    return revenue


def _is_megatonne_label(unit_raw: str | None) -> bool:
    return unit_raw is not None and unit_raw.rsplit(":", 1)[-1] == "MtCO2e"


def v1_mtco2e_label(filing: BrsrFiling) -> list[Issue]:
    """V1: 'MtCO2e' read as metric tonnes; warn if the implied intensity is implausible."""
    issues: list[Issue] = []
    for year in years(filing):
        if not _is_megatonne_label(year.emissions_unit_raw):
            continue
        # The intensity check is only meaningful against a revenue we trust. When revenue fails
        # V2 the implied intensity is wrong by ~1e7 and would just repeat V2's finding.
        revenue = _trusted_revenue(year)
        implied = scope12_t_per_crore(year, revenue) if revenue is not None else None
        too_high = implied is not None and implied > config.V1_MAX_PLAUSIBLE_T_PER_CRORE
        message = "Unit 'MtCO2e' interpreted as metric tonnes CO2e (not megatonnes)."
        if too_high:
            message += (
                f" Implied intensity {implied:,.0f} tCO2e per ₹ crore exceeds "
                f"{config.V1_MAX_PLAUSIBLE_T_PER_CRORE:,.0f}; check the unit and the revenue."
            )
        issues.append(
            Issue(
                rule_id="V1",
                severity="warning" if too_high else "info",
                field="emissions_unit_raw",
                fiscal_year=fy_label(year),
                message=message,
                observed_value=year.emissions_unit_raw,
            )
        )
    return issues


def v2_revenue_scale(filing: BrsrFiling) -> list[Issue]:
    """V2: RevenueFromOperations below ₹10 lakh is a scale error (V2-fix if safely corrected)."""
    issues: list[Issue] = []
    for year in years(filing):
        revenue = year.revenue_from_operations_inr
        if revenue is None or revenue >= config.V2_MIN_PLAUSIBLE_REVENUE_INR:
            continue
        resolved = year_revenue(year)
        if resolved.ops_corrected:
            issues.append(_v2_fix_issue(year, revenue, resolved))
            continue
        issues.append(
            Issue(
                rule_id="V2",
                severity="error",
                field="revenue_from_operations_inr",
                fiscal_year=fy_label(year),
                message=(
                    f"RevenueFromOperations of ₹{revenue:,.2f} is below ₹10 lakh, implausible for "
                    "a listed company; the reported intensity is untrustworthy. "
                    f"No safe correction: {resolved.note}."
                ),
                observed_value=_fmt(revenue),
                suggested_fix=(
                    "Likely ₹ crore typed as rupees. Take revenue from the company's financial "
                    "results; do not rescale automatically."
                ),
            )
        )
    return issues


def _v2_fix_issue(year: FiscalYearData, revenue: float, resolved: RevenueResolution) -> Issue:
    """V2 downgraded to a warning because the other revenue field pins down the scale."""
    assert resolved.revenue_inr_resolved is not None
    return Issue(
        rule_id="V2-fix",
        severity="warning",
        field="revenue_from_operations_inr",
        fiscal_year=fy_label(year),
        message=(
            f"RevenueFromOperations of ₹{revenue:,.2f} is below ₹10 lakh. Corrected to "
            f"₹{resolved.revenue_inr_resolved:,.0f}: {resolved.note}."
        ),
        observed_value=_fmt(revenue),
        suggested_fix=(
            "Correction applied and shown in provenance; confirm against the financial results. "
            "WACI data quality for this company is capped at 2."
        ),
    )


def v3_revenue_mismatch(filing: BrsrFiling) -> list[Issue]:
    """V3: the two revenue fields disagree by more than 2x."""
    issues: list[Issue] = []
    for year in years(filing):
        ops, total = year.revenue_from_operations_inr, year.total_revenue_inr
        if ops is None or total is None:
            continue
        low, high = sorted((ops, total))
        if high <= 0:
            continue
        if low > 0 and high / low <= config.V3_MAX_REVENUE_RATIO:
            continue
        issues.append(
            Issue(
                rule_id="V3",
                severity="warning",
                field="total_revenue_inr",
                fiscal_year=fy_label(year),
                message=(
                    f"RevenueFromOperations (₹{ops:,.2f}) and TotalRevenueOfTheCompany "
                    f"(₹{total:,.2f}) differ by more than {config.V3_MAX_REVENUE_RATIO:g}x."
                ),
                observed_value=f"{_fmt(ops)} vs {_fmt(total)}",
                suggested_fix=_v3_fix_hint(year_revenue(year)),
            )
        )
    return issues


def _v3_fix_hint(resolved: RevenueResolution) -> str:
    if resolved.resolution in ("inferred_crore", "inferred_lakh"):
        return f"Explained by a lakh/crore scale slip (rule V2-fix): {resolved.note}."
    return "Check both figures against the financial results."


def v4_zero_year(filing: BrsrFiling) -> list[Issue]:
    """V4: S1 = 0 and S2 = 0 in one year while the other year is non-zero means 'not reported'."""
    if filing.fy_previous is None:
        return []
    issues: list[Issue] = []
    pairs = ((filing.fy_current, filing.fy_previous), (filing.fy_previous, filing.fy_current))
    for year, other in pairs:
        # Only "is the other year non-zero?" is asked, so a missing scope adds nothing here.
        other_total = (other.scope1 or 0.0) + (other.scope2 or 0.0)
        # Exact comparison on purpose: V4 is about a literal "0" in the filing, not a small number.
        if year.scope1 == 0 and year.scope2 == 0 and other_total > 0:
            issues.append(
                Issue(
                    rule_id="V4",
                    severity="warning",
                    field="scope1+scope2",
                    fiscal_year=fy_label(year),
                    message=(
                        f"Scope 1 and Scope 2 are both 0 in {fy_label(year)} while "
                        f"{fy_label(other)} reports {other_total:,.2f}; treated as missing."
                    ),
                    observed_value="0 / 0",
                    suggested_fix="Treat as not reported (None), never as zero emissions.",
                )
            )
    return issues


def v5_yoy_jump(filing: BrsrFiling) -> list[Issue]:
    """V5: Scope 1 or Scope 2 changes more than 2x between the two filed years."""
    prev = filing.fy_previous
    if prev is None:
        return []
    issues: list[Issue] = []
    cur = filing.fy_current
    for field, before, after in (
        ("scope1", prev.scope1, cur.scope1),
        ("scope2", prev.scope2, cur.scope2),
    ):
        # Zeros and gaps are V4's business; a ratio against zero says nothing.
        if not before or not after or before < 0 or after < 0:
            continue
        low, high = sorted((before, after))
        if high <= low * config.V5_MAX_YOY_RATIO:
            continue
        ratio = after / before
        issues.append(
            Issue(
                rule_id="V5",
                severity="warning",
                field=field,
                fiscal_year=fy_label(cur),
                message=(
                    f"{field.title()} changed {ratio:.2f}x year on year "
                    f"({before:,.2f} → {after:,.2f}). Could be real or a boundary change."
                ),
                observed_value=f"{_fmt(before)} → {_fmt(after)}",
                suggested_fix="Review against the filing's notes; never auto-correct.",
            )
        )
    return issues


def v6_fiscal_year_end(filing: BrsrFiling) -> list[Issue]:
    """V6: record a fiscal year that does not end on 31 March."""
    end = filing.fy_current.period_end
    if (end.month, end.day) == (config.V6_STANDARD_FY_END_MONTH, config.V6_STANDARD_FY_END_DAY):
        return []
    return [
        Issue(
            rule_id="V6",
            severity="info",
            field="period_end",
            fiscal_year=fy_label(filing.fy_current),
            message=(
                f"Fiscal year runs {filing.fy_current.period_start} to {end}, not April–March. "
                "Dates are carried through as filed."
            ),
            observed_value=end.isoformat(),
        )
    ]


def v9_not_applicable(filing: BrsrFiling) -> list[Issue]:
    """V9: the company says GHG disclosure does not apply to it."""
    if filing.fy_current.ghg_applicable is not False:
        return []
    return [
        Issue(
            rule_id="V9",
            severity="info",
            field="ghg_applicable",
            fiscal_year=fy_label(filing.fy_current),
            message=(
                "Company marks GHG emissions disclosure as not applicable; excluded from "
                "emissions and reported as a coverage gap, not estimated."
            ),
            observed_value="false",
        )
    ]


def v10_intensity_check(filing: BrsrFiling) -> list[Issue]:
    """V10: reported intensity must equal (S1+S2)/RevenueFromOperations within tolerance."""
    issues: list[Issue] = []
    for year in years(filing):
        s1, s2 = year.scope1, year.scope2
        revenue, reported = year.revenue_from_operations_inr, year.intensity_reported_per_inr
        if s1 is None or s2 is None or reported is None or not revenue:
            continue
        computed = (s1 + s2) / revenue
        diff = abs(computed - reported)
        if diff <= config.V10_ABS_TOLERANCE:
            continue
        # `reported != 0` only guards the division; near-zero cases were settled by the
        # absolute tolerance above.
        if reported != 0 and diff / abs(reported) <= config.V10_REL_TOLERANCE:
            continue
        issues.append(
            Issue(
                rule_id="V10",
                severity="warning",
                field="intensity_reported_per_inr",
                fiscal_year=fy_label(year),
                message=(
                    f"Reported intensity {reported:.4g} per ₹ differs from (S1+S2)/revenue = "
                    f"{computed:.4g} by more than {config.V10_REL_TOLERANCE:.0%}."
                ),
                observed_value=f"{reported:.6g} vs {computed:.6g}",
                suggested_fix="One of Scope 1, Scope 2, revenue or the intensity is mistyped.",
            )
        )
    return issues


VALIDATORS: dict[str, Callable[[BrsrFiling], list[Issue]]] = {
    "V1": v1_mtco2e_label,
    "V2": v2_revenue_scale,
    "V3": v3_revenue_mismatch,
    "V4": v4_zero_year,
    "V5": v5_yoy_jump,
    "V6": v6_fiscal_year_end,
    "V9": v9_not_applicable,
    "V10": v10_intensity_check,
}


def validate(filing: BrsrFiling) -> list[Issue]:
    """Run every validator, in rule order."""
    return [issue for check in VALIDATORS.values() for issue in check(filing)]


def _fmt(value: float) -> str:
    """Exact, readable string for an observed value: `96669`, `165.82`."""
    return str(int(value)) if value.is_integer() else repr(value)
