"""Response and request models for the API, plus the real-fixture rule examples."""

from typing import Any

from pydantic import BaseModel, Field

from pf_core.funds.ranking import FundResult

# Real fixture examples shown on the data-quality page, one per rule that fires.
RULE_EXAMPLES: dict[str, str] = {
    "V1": "Titan Company Limited files Scope 1 = 3,878 'MtCO2e'; 3.9 billion tonnes would be "
    "absurd for a jeweller, so it means metric tonnes.",
    "V2": "Gujarat Themis Biosyn's FY2024-25 RevenueFromOperations is ₹153.23, but its total "
    "revenue (₹2,48,38,19,619) is 1.62e7 times larger, which no lakh/crore reading explains. Left "
    "as filed, flagged, and kept out of WACI.",
    "V2-fix": "Gujarat Themis Biosyn's FY2025-26 RevenueFromOperations of 165.82 is ₹ crore: its "
    "TotalRevenueOfTheCompany is 1,658,227,981, exactly 1e7 times larger. Everest Kanto files "
    "operating revenue in crore and total revenue in lakh.",
    "V3": "Everest Kanto Cylinder files RevenueFromOperations = 934.43 but "
    "TotalRevenueOfTheCompany = 96,669.",
    "V4": "Gulshan Polyols files Scope 1 = 0 and Scope 2 = 0 for FY2024-25, next to about "
    "52,500 t in FY2025-26.",
    "V5": "Varroc Engineering's Scope 1 rises from 2,157 t to 8,020 t (3.7x) in one year.",
    "V6": "Accelya Solutions' fiscal year runs 1 July 2025 to 30 June 2026.",
    "V9": "Rajesh Exports, Sirca Paints, Ashiana Housing, Vishnu Prakash R Punglia and HMT mark "
    "GHG disclosure as not applicable.",
    "V10": "No fixture triggers it: in all 15 reporting filings the intensity equals "
    "(S1+S2)/revenue exactly.",
}

SUMMARY_FIELDS = [
    "company_key",
    "company_name",
    "nse_symbol",
    "isin",
    "fiscal_year",
    "period_end",
    "scope1_t",
    "scope2_t",
    "intensity_t_per_crore",
    "assured",
    "quality_flag",
    "issues",
]


class CompanySummary(BaseModel):
    company_key: str
    company_name: str
    nse_symbol: str | None
    isin: str | None
    fiscal_year: str
    period_end: str
    scope1_t: float | None
    scope2_t: float | None
    total_t: float | None
    intensity_t_per_crore: float | None
    assured: bool | None
    quality_flag: str
    issues: list[str]


class IssueOut(BaseModel):
    rule_id: str
    severity: str
    field: str
    fiscal_year: str
    message: str
    observed_value: str | None
    suggested_fix: str | None
    explanation: str


class CompanyDetail(BaseModel):
    summary: CompanySummary
    source_file: str
    cin: str | None
    exclusion_reason: str | None
    years: list[dict[str, Any]]
    issues: list[IssueOut]


class RuleSummary(BaseModel):
    rule_id: str
    description: str
    issues: int
    problems: int = Field(description="Issues of severity error or warning")
    info: int = Field(description="Informational notes (severity info)")
    companies: int
    example: str


class ValidationSummary(BaseModel):
    companies: int
    reporting_scope12: int
    pct_reporting_scope12: float | None
    assured: int
    pct_assured_of_reporting: float | None
    excluded_companies: int
    issues_problems: int = Field(description="Issues of severity error or warning")
    issues_info: int = Field(description="Informational notes (severity info), not problems")
    companies_with_problems: int
    issues_total: int = Field(description="All issues, problems plus informational notes")
    quality_flags: dict[str, int]
    rules: list[RuleSummary]
    excluded: list[dict[str, Any]]


class HoldingIn(BaseModel):
    isin_or_symbol: str
    value_inr: float = Field(gt=0)


class EvicIn(BaseModel):
    company_key: str
    evic_inr: float = Field(gt=0)
    evic_source: str = "user-supplied"
    evic_is_illustrative: bool = False


class PortfolioRequest(BaseModel):
    holdings: list[HoldingIn] = Field(min_length=1)
    evic: list[EvicIn] = []


class DemoPortfolio(BaseModel):
    id: str
    description: str
    illustrative: bool
    holdings: list[HoldingIn]
    evic: list[EvicIn]


class Methodology(BaseModel):
    markdown: str


class FundsResponse(BaseModel):
    available: bool
    snapshot_dir: str
    funds: list[FundResult]
