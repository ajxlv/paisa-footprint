"""Read-only FastAPI service over a Parquet snapshot.

The API never calls NSE or any other data source: it serves whatever snapshot `pf
build-snapshot` wrote. Portfolio computation runs the pure PCAF engine on user-supplied holdings
and EVIC values.

Environment:
    PF_SNAPSHOT_DIR   snapshot directory (default data/snapshots/fixtures)
    PF_DEMO_DIR       synthetic demo portfolios (default tests/fixtures/synthetic)
    PF_DOCS_DIR       docs directory holding METHODOLOGY.md (default docs)
    PF_CORS_ORIGINS   extra comma-separated CORS origins
"""

import os
from functools import cached_property
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from pf_core.brsr.validators import RULE_DESCRIPTIONS
from pf_core.pcaf.engine import compute_portfolio
from pf_core.pcaf.inputs import (
    company_index,
    emissions_from_snapshot,
    load_evic_csv,
    load_portfolio_csv,
)
from pf_core.pcaf.models import CompanyFinancials, Holding, PortfolioResult
from pf_core.snapshot import Snapshot, coverage_stats, load_snapshot

DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8080"]

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


class _State:
    """Lazily loaded snapshot so a missing snapshot gives a clear 503, not a crash at import."""

    def __init__(self, snapshot_dir: Path) -> None:
        self.snapshot_dir = snapshot_dir

    @cached_property
    def snapshot(self) -> Snapshot:
        if not (self.snapshot_dir / "companies.parquet").exists():
            raise HTTPException(
                503,
                f"No snapshot in {self.snapshot_dir}. Run: pf build-snapshot "
                f"--input tests/fixtures/brsr --out {self.snapshot_dir}",
            )
        return load_snapshot(self.snapshot_dir)


def create_app(
    snapshot_dir: str | Path | None = None,
    demo_dir: str | Path | None = None,
    docs_dir: str | Path | None = None,
) -> FastAPI:
    """Build the app. Arguments override the PF_* environment variables (used by tests)."""
    state = _State(
        Path(snapshot_dir or os.environ.get("PF_SNAPSHOT_DIR", "data/snapshots/fixtures"))
    )
    demo = Path(demo_dir or os.environ.get("PF_DEMO_DIR", "tests/fixtures/synthetic"))
    docs = Path(docs_dir or os.environ.get("PF_DOCS_DIR", "docs"))

    app = FastAPI(
        title="Paisa Footprint API",
        version="0.1.0",
        description="Read-only PCAF financed emissions from BRSR filings. No live data calls.",
    )
    extra = [o.strip() for o in os.environ.get("PF_CORS_ORIGINS", "").split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS + extra,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "snapshot_dir": str(state.snapshot_dir),
            "companies": len({c["company_key"] for c in state.snapshot.companies}),
        }

    @app.get("/companies", response_model=list[CompanySummary])
    def companies() -> list[CompanySummary]:
        rows = [c for c in state.snapshot.companies if c["is_current"]]
        return sorted((_summary(c) for c in rows), key=lambda s: s.company_name.lower())

    @app.get("/companies/{key}", response_model=CompanyDetail)
    def company(key: str) -> CompanyDetail:
        rows = [c for c in state.snapshot.companies if c["company_key"] == key]
        if not rows:
            raise HTTPException(404, f"No company with key {key!r}")
        current = next(r for r in rows if r["is_current"])
        issues = [
            IssueOut(
                **{k: i[k] for k in IssueOut.model_fields if k != "explanation"},
                explanation=RULE_DESCRIPTIONS.get(i["rule_id"], ""),
            )
            for i in state.snapshot.issues
            if i["company_key"] == key
        ]
        return CompanyDetail(
            summary=_summary(current),
            source_file=current["source_file"],
            cin=current["cin"],
            exclusion_reason=current["exclusion_reason"],
            years=sorted(rows, key=lambda r: str(r["period_end"]), reverse=True),
            issues=issues,
        )

    @app.get("/validation/summary", response_model=ValidationSummary)
    def validation_summary() -> ValidationSummary:
        stats = coverage_stats(state.snapshot)
        rules = [
            RuleSummary(
                rule_id=rule,
                description=text,
                issues=stats["issues_per_rule"].get(rule, 0),
                problems=stats["problems_per_rule"].get(rule, 0),
                info=stats["info_per_rule"].get(rule, 0),
                companies=stats["companies_per_rule"].get(rule, 0),
                example=RULE_EXAMPLES.get(rule, ""),
            )
            for rule, text in RULE_DESCRIPTIONS.items()
        ]
        return ValidationSummary(
            **{
                k: stats[k]
                for k in (
                    "companies",
                    "reporting_scope12",
                    "pct_reporting_scope12",
                    "assured",
                    "pct_assured_of_reporting",
                    "excluded_companies",
                    "issues_problems",
                    "issues_info",
                    "companies_with_problems",
                    "issues_total",
                    "quality_flags",
                )
            },
            rules=rules,
            excluded=state.snapshot.excluded,
        )

    @app.post("/portfolio/compute", response_model=PortfolioResult)
    def portfolio_compute(request: PortfolioRequest) -> PortfolioResult:
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

    @app.get("/demo/portfolios", response_model=list[DemoPortfolio])
    def demo_portfolios() -> list[DemoPortfolio]:
        evic_path = demo / "illustrative_evic.csv"
        evic = [
            EvicIn(**f.model_dump())
            for f in load_evic_csv(evic_path).values()
            if f.evic_inr is not None
        ]
        index = company_index(state.snapshot)
        result = []
        for path in sorted(demo.glob("portfolio_synthetic_*.csv")):
            holdings = load_portfolio_csv(path, index)
            result.append(
                DemoPortfolio(
                    id=path.stem,
                    description=_first_comment(path),
                    illustrative=True,
                    holdings=[
                        HoldingIn(isin_or_symbol=h.isin_or_symbol, value_inr=h.value_inr)
                        for h in holdings
                    ],
                    evic=evic,
                )
            )
        return result

    @app.get("/methodology", response_model=Methodology)
    def methodology() -> Methodology:
        path = docs / "METHODOLOGY.md"
        if not path.exists():
            raise HTTPException(404, "METHODOLOGY.md not found")
        return Methodology(markdown=path.read_text(encoding="utf-8"))

    return app


def _summary(row: dict[str, Any]) -> CompanySummary:
    s1, s2 = row["scope1_t"], row["scope2_t"]
    data = {k: row[k] for k in SUMMARY_FIELDS}
    data["period_end"] = str(row["period_end"])
    data["issues"] = list(row["issues"])
    return CompanySummary(**data, total_t=s1 + s2 if s1 is not None and s2 is not None else None)


def _first_comment(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            return line.lstrip("# ").strip()
    return path.stem


app = create_app()
