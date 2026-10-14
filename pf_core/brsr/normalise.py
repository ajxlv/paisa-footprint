"""Turn a validated filing into `CleanCompanyYear` rows.

Only two fixes are applied, because only these two are safe to apply mechanically:

* V1: emissions tagged `MtCO2e` or `tCO2e` are expressed as tonnes (`scope1_t`, `scope2_t`).
* V4: a zero year next to a non-zero year becomes `None` (unknown), never zero.

Everything else (revenue scale, revenue mismatch, YoY jumps, intensity mismatch) is flagged and
left exactly as filed. Each transformed number records what was done to it in `provenance`.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel

from pf_core.brsr import config
from pf_core.brsr.models import BrsrFiling, FactProvenance, FiscalYearData
from pf_core.brsr.revenue import OPS, TOTAL, Resolution, RevenueResolution
from pf_core.brsr.validators import Issue, fy_label, validate, year_revenue, years

QualityFlag = Literal["ok", "review", "excluded"]

# Unit local-names (after the XBRL prefix) that mean tonnes of CO2e, and how we read each one.
_TONNE_UNITS: dict[str, str] = {
    "tCO2e": "none (filed in tCO2e)",
    "MtCO2e": "MtCO2e interpreted as metric tonnes (rule V1)",
}


class ValueProvenance(BaseModel):
    """Trace for one clean number: the filed fact plus what was done to it."""

    element: str
    context_ref: str
    period_start: date | None
    period_end: date
    unit_raw: str | None
    raw_value: str
    transformation: str
    value_used: float | None = None
    corrected: bool = False


class CleanCompanyYear(BaseModel):
    """One company in one fiscal year, after the safe fixes."""

    company_key: str
    company_name: str
    nse_symbol: str | None
    isin: str | None
    cin: str | None
    source_file: str
    fiscal_year: str
    is_current: bool
    period_start: date
    period_end: date
    scope1_t: float | None
    scope2_t: float | None
    revenue_inr: float | None
    total_revenue_inr: float | None
    revenue_inr_resolved: float | None
    total_revenue_inr_resolved: float | None
    revenue_resolution: Resolution
    revenue_note: str
    revenue_corrected: bool
    intensity_reported_per_inr: float | None
    intensity_t_per_crore: float | None
    ghg_applicable: bool | None
    assured: bool | None
    issues: list[str]
    quality_flag: QualityFlag
    exclusion_reason: str | None
    provenance: dict[str, ValueProvenance]


def normalise(filing: BrsrFiling, issues: list[Issue] | None = None) -> list[CleanCompanyYear]:
    """Clean rows for every filed year of one filing (current year first)."""
    found = validate(filing) if issues is None else issues
    return [
        _clean_year(filing, year, is_current=(year is filing.fy_current), issues=found)
        for year in years(filing)
    ]


def _clean_year(
    filing: BrsrFiling, year: FiscalYearData, is_current: bool, issues: list[Issue]
) -> CleanCompanyYear:
    label = fy_label(year)
    year_issues = [i for i in issues if i.fiscal_year == label]
    zero_year = any(i.rule_id == "V4" for i in year_issues)
    revenue_error = any(i.rule_id == "V2" and i.severity == "error" for i in year_issues)

    provenance: dict[str, ValueProvenance] = {}
    scope1_t = _tonnes(year, "scope1", zero_year, provenance)
    scope2_t = _tonnes(year, "scope2", zero_year, provenance)
    resolved = year_revenue(year)
    provenance.update(_revenue_provenance(year, resolved, revenue_error))

    intensity = None
    revenue = resolved.revenue_inr_resolved
    if scope1_t is not None and scope2_t is not None and revenue and not revenue_error:
        intensity = (scope1_t + scope2_t) / (revenue / config.INR_PER_CRORE)

    flag, reason = _quality(filing, scope1_t, scope2_t, year_issues)
    return CleanCompanyYear(
        company_key=filing.company_key,
        company_name=filing.company_name,
        nse_symbol=filing.nse_symbol,
        isin=filing.isin,
        cin=filing.cin,
        source_file=filing.source_file,
        fiscal_year=label,
        is_current=is_current,
        period_start=year.period_start,
        period_end=year.period_end,
        scope1_t=scope1_t,
        scope2_t=scope2_t,
        revenue_inr=year.revenue_from_operations_inr,
        total_revenue_inr=year.total_revenue_inr,
        revenue_inr_resolved=resolved.revenue_inr_resolved,
        total_revenue_inr_resolved=resolved.total_revenue_inr_resolved,
        revenue_resolution=resolved.resolution,
        revenue_note=resolved.note,
        revenue_corrected=resolved.ops_corrected,
        intensity_reported_per_inr=year.intensity_reported_per_inr,
        intensity_t_per_crore=intensity,
        ghg_applicable=year.ghg_applicable if is_current else filing.fy_current.ghg_applicable,
        assured=year.ghg_assured,
        issues=[i.rule_id for i in year_issues],
        quality_flag=flag,
        exclusion_reason=reason,
        provenance=provenance,
    )


def _revenue_provenance(
    year: FiscalYearData, resolved: RevenueResolution, revenue_error: bool
) -> dict[str, ValueProvenance]:
    """Trace both revenue fields and the reported intensity, marking any V2-fix correction."""
    used = {OPS: resolved.revenue_inr_resolved, TOTAL: resolved.total_revenue_inr_resolved}
    out: dict[str, ValueProvenance] = {}
    for field in (OPS, TOTAL, "intensity_reported_per_inr"):
        fact = year.facts.get(field)
        if fact is None:
            continue
        note, corrected = "none (as filed)", False
        if field in resolved.factors:
            note, corrected = (
                f"corrected ×{resolved.factors[field]:.0e} (rule V2-fix): {resolved.note}",
                True,
            )
        elif field == OPS and revenue_error:
            note = "none; flagged as a scale error (rule V2), not corrected"
        trace = _trace(fact, note)
        out[field] = trace.model_copy(
            update={"value_used": used.get(field), "corrected": corrected}
        )
    return out


def _tonnes(
    year: FiscalYearData, field: str, zero_year: bool, provenance: dict[str, ValueProvenance]
) -> float | None:
    """Express one scope in tonnes, or None. Records the transformation applied."""
    raw: float | None = getattr(year, field)
    fact = year.facts.get(field)
    if raw is None or fact is None:
        return None
    unit_name = (fact.unit_raw or "").rsplit(":", 1)[-1]
    if zero_year:
        provenance[f"{field}_t"] = _trace(
            fact, "reported 0 next to a non-zero year; treated as missing (rule V4)"
        )
        return None
    if unit_name not in _TONNE_UNITS:
        provenance[f"{field}_t"] = _trace(fact, f"unrecognised unit {fact.unit_raw!r}; withheld")
        return None
    provenance[f"{field}_t"] = _trace(fact, _TONNE_UNITS[unit_name]).model_copy(
        update={"value_used": raw}
    )
    return raw


def _quality(
    filing: BrsrFiling,
    scope1_t: float | None,
    scope2_t: float | None,
    year_issues: list[Issue],
) -> tuple[QualityFlag, str | None]:
    """`excluded` = no usable emissions; `review` = usable but a warning/error applies."""
    if filing.fy_current.ghg_applicable is False:
        return "excluded", "Company marks GHG disclosure as not applicable (V9)"
    if scope1_t is None and scope2_t is None:
        if any(i.rule_id == "V4" for i in year_issues):
            return "excluded", "Zero Scope 1 and Scope 2 next to a non-zero year (V4)"
        return "excluded", "No Scope 1 or Scope 2 reported"
    if scope1_t is None or scope2_t is None:
        return "review", None
    if any(i.severity in ("error", "warning") for i in year_issues):
        return "review", None
    return "ok", None


def _trace(fact: FactProvenance, transformation: str) -> ValueProvenance:
    return ValueProvenance(
        element=fact.element,
        context_ref=fact.context_ref,
        period_start=fact.period_start,
        period_end=fact.period_end,
        unit_raw=fact.unit_raw,
        raw_value=fact.raw_value,
        transformation=transformation,
    )
