"""Inputs and outputs of the PCAF engine."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class Holding(BaseModel):
    """One position. `company_key` is None when the ISIN/symbol matched no known company."""

    isin_or_symbol: str
    company_key: str | None
    value_inr: float = Field(gt=0)


class CompanyFinancials(BaseModel):
    """EVIC for one company. `evic_is_illustrative` marks made-up demo values."""

    company_key: str
    evic_inr: float | None = Field(default=None, gt=0)
    evic_source: str
    evic_is_illustrative: bool


class CompanyEmissions(BaseModel):
    """Clean Scope 1+2 for one company-year, from the snapshot."""

    company_key: str
    company_name: str
    scope1_t: float | None
    scope2_t: float | None
    revenue_inr: float | None
    assured: bool | None
    fiscal_year: str
    quality_flag: Literal["ok", "review", "excluded"]
    revenue_corrected: bool = False
    revenue_resolution: str = "as_filed"
    error_fields: list[str] = []
    issues: list[str] = []
    provenance: dict[str, Any] = {}


class HoldingResult(BaseModel):
    """A covered holding with every formula input, so the arithmetic can be redone by hand."""

    isin_or_symbol: str
    company_key: str
    company_name: str
    fiscal_year: str
    value_inr: float
    evic_inr: float
    evic_source: str
    evic_is_illustrative: bool
    attribution: float
    scope1_t: float
    scope2_t: float
    financed_emissions_t: float
    revenue_inr: float | None
    intensity_t_per_crore_revenue: float | None
    in_waci: bool
    waci_exclusion_reason: str | None
    revenue_corrected: bool = False
    pcaf_data_quality: int
    waci_data_quality: int | None = None
    formula: str
    provenance: dict[str, Any] = {}


class UncoveredHolding(BaseModel):
    """A holding left out of financed emissions, and why."""

    isin_or_symbol: str
    company_key: str | None
    value_inr: float
    reason: str


class PortfolioResult(BaseModel):
    """Portfolio totals. Low coverage is reported, never hidden."""

    total_value_inr: float
    covered_value_inr: float
    coverage_pct: float
    financed_emissions_t: float
    carbon_footprint_t_per_crore: float | None
    waci_t_per_crore_revenue: float | None
    waci_value_inr: float
    waci_coverage_pct: float
    pcaf_data_quality: float | None
    waci_data_quality: float | None = None
    holdings: list[HoldingResult]
    uncovered: list[UncoveredHolding]
    contains_illustrative_inputs: bool
