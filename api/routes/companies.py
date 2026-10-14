"""Company, validation, health and methodology endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException

from api.schemas import (
    RULE_EXAMPLES,
    SUMMARY_FIELDS,
    CompanyDetail,
    CompanySummary,
    IssueOut,
    Methodology,
    RuleSummary,
    ValidationSummary,
)
from api.state import State
from pf_core.brsr.validators import RULE_DESCRIPTIONS
from pf_core.snapshot import coverage_stats

router = APIRouter()

_HEADLINE_FIELDS = (
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


@router.get("/health")
def health(state: State) -> dict[str, Any]:
    return {
        "status": "ok",
        "snapshot_dir": str(state.snapshot_dir),
        "companies": len({c["company_key"] for c in state.snapshot.companies}),
    }


@router.get("/companies", response_model=list[CompanySummary])
def companies(state: State) -> list[CompanySummary]:
    rows = [c for c in state.snapshot.companies if c["is_current"]]
    return sorted((summary(c) for c in rows), key=lambda s: s.company_name.lower())


@router.get("/companies/{key}", response_model=CompanyDetail)
def company(key: str, state: State) -> CompanyDetail:
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
        summary=summary(current),
        source_file=current["source_file"],
        cin=current["cin"],
        exclusion_reason=current["exclusion_reason"],
        years=sorted(rows, key=lambda r: str(r["period_end"]), reverse=True),
        issues=issues,
    )


@router.get("/validation/summary", response_model=ValidationSummary)
def validation_summary(state: State) -> ValidationSummary:
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
        **{k: stats[k] for k in _HEADLINE_FIELDS}, rules=rules, excluded=state.snapshot.excluded
    )


@router.get("/methodology", response_model=Methodology)
def methodology(state: State) -> Methodology:
    path = state.docs_dir / "METHODOLOGY.md"
    if not path.exists():
        raise HTTPException(404, "METHODOLOGY.md not found")
    return Methodology(markdown=path.read_text(encoding="utf-8"))


def summary(row: dict[str, Any]) -> CompanySummary:
    s1, s2 = row["scope1_t"], row["scope2_t"]
    data = {k: row[k] for k in SUMMARY_FIELDS}
    data["period_end"] = str(row["period_end"])
    data["issues"] = list(row["issues"])
    return CompanySummary(**data, total_t=s1 + s2 if s1 is not None and s2 is not None else None)
