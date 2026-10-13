"""Build and read Parquet snapshots of parsed, validated and normalised BRSR filings.

A snapshot is the only thing the API reads. It is rebuilt from raw XBRL files by `pf
build-snapshot`, so it can always be regenerated and audited.

Files written:

* `companies.parquet`: one row per company per fiscal year (every parsed year, including
  excluded ones, so nothing disappears), with a JSON `provenance` column.
* `validation_report.parquet`: one row per validator issue.
* `excluded.parquet`: every excluded company-year and every file that failed to parse, with why.
* `manifest.json`: input files with SHA-256 hashes and row counts.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel

from pf_core.brsr.normalise import CleanCompanyYear, normalise
from pf_core.brsr.parser import parse_directory
from pf_core.brsr.validators import RULE_DESCRIPTIONS, validate

COMPANIES = "companies.parquet"
VALIDATION = "validation_report.parquet"
EXCLUDED = "excluded.parquet"
MANIFEST = "manifest.json"


class SnapshotSummary(BaseModel):
    """Row counts for one build. `parsed_company_years == clean + excluded` always holds."""

    files_seen: int
    files_parsed: int
    files_failed: int
    parsed_company_years: int
    clean_company_years: int
    excluded_company_years: int
    issues: int


def build_snapshot(input_dir: str | Path, out_dir: str | Path) -> SnapshotSummary:
    """Parse, validate and normalise every filing in `input_dir`; write Parquet to `out_dir`."""
    input_dir, out_dir = Path(input_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filings, failures = parse_directory(input_dir)

    rows: list[CleanCompanyYear] = []
    issue_rows: list[dict[str, Any]] = []
    for filing in filings:
        issues = validate(filing)
        rows.extend(normalise(filing, issues))
        issue_rows.extend(
            {
                "company_key": filing.company_key,
                "company_name": filing.company_name,
                "source_file": filing.source_file,
                **issue.model_dump(),
            }
            for issue in issues
        )

    companies = pd.DataFrame([_company_record(r) for r in rows])
    validation = pd.DataFrame(issue_rows, columns=_ISSUE_COLUMNS)
    excluded = _excluded_frame(rows, failures)

    companies.to_parquet(out_dir / COMPANIES, index=False)
    validation.to_parquet(out_dir / VALIDATION, index=False)
    excluded.to_parquet(out_dir / EXCLUDED, index=False)

    summary = SnapshotSummary(
        files_seen=len(filings) + len(failures),
        files_parsed=len(filings),
        files_failed=len(failures),
        parsed_company_years=len(rows),
        clean_company_years=sum(r.quality_flag != "excluded" for r in rows),
        excluded_company_years=sum(r.quality_flag == "excluded" for r in rows),
        issues=len(issue_rows),
    )
    manifest = {
        "inputs": {p.name: _sha256(p) for p in sorted(input_dir.glob("*.xml"))},
        "summary": summary.model_dump(),
    }
    (out_dir / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return summary


_ISSUE_COLUMNS = [
    "company_key",
    "company_name",
    "source_file",
    "rule_id",
    "severity",
    "field",
    "fiscal_year",
    "message",
    "observed_value",
    "suggested_fix",
]


def _company_record(row: CleanCompanyYear) -> dict[str, Any]:
    record = row.model_dump(mode="json", exclude={"provenance"})
    record["provenance"] = json.dumps(
        {k: v.model_dump(mode="json") for k, v in row.provenance.items()}, sort_keys=True
    )
    return record


def _excluded_frame(rows: list[CleanCompanyYear], failures: dict[str, str]) -> pd.DataFrame:
    records: list[dict[str, Any]] = [
        {
            "company_key": r.company_key,
            "company_name": r.company_name,
            "fiscal_year": r.fiscal_year,
            "is_current": r.is_current,
            "source_file": r.source_file,
            "reason": r.exclusion_reason,
        }
        for r in rows
        if r.quality_flag == "excluded"
    ]
    records.extend(
        {
            "company_key": None,
            "company_name": None,
            "fiscal_year": None,
            "is_current": None,
            "source_file": name,
            "reason": f"Failed to parse: {reason}",
        }
        for name, reason in failures.items()
    )
    return pd.DataFrame(
        records,
        columns=[
            "company_key",
            "company_name",
            "fiscal_year",
            "is_current",
            "source_file",
            "reason",
        ],
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Snapshot(BaseModel):
    """An in-memory snapshot, as served by the API."""

    companies: list[dict[str, Any]]
    issues: list[dict[str, Any]]
    excluded: list[dict[str, Any]]


def load_snapshot(snapshot_dir: str | Path) -> Snapshot:
    """Read a snapshot directory back into plain records (provenance decoded from JSON)."""
    snapshot_dir = Path(snapshot_dir)
    companies = _records(pd.read_parquet(snapshot_dir / COMPANIES))
    for record in companies:
        record["provenance"] = json.loads(record["provenance"])
        record["issues"] = list(record["issues"])
    return Snapshot(
        companies=companies,
        issues=_records(pd.read_parquet(snapshot_dir / VALIDATION)),
        excluded=_records(pd.read_parquet(snapshot_dir / EXCLUDED)),
    )


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame rows as dicts with NaN/NA turned into None (missing stays missing)."""
    cleaned = frame.astype(object).where(frame.notna(), None)
    return [{str(k): v for k, v in row.items()} for row in cleaned.to_dict(orient="records")]


def coverage_stats(snapshot: Snapshot) -> dict[str, Any]:
    """Headline numbers for the current fiscal year of each company, plus issues per rule."""
    current = [c for c in snapshot.companies if c["is_current"]]
    reporting = [c for c in current if c["scope1_t"] is not None and c["scope2_t"] is not None]
    assured = [c for c in reporting if c["assured"] is True]
    per_rule = {rule: 0 for rule in RULE_DESCRIPTIONS}
    companies_per_rule: dict[str, set[str]] = {rule: set() for rule in RULE_DESCRIPTIONS}
    for issue in snapshot.issues:
        per_rule[issue["rule_id"]] = per_rule.get(issue["rule_id"], 0) + 1
        companies_per_rule.setdefault(issue["rule_id"], set()).add(issue["company_key"])
    return {
        "companies": len(current),
        "reporting_scope12": len(reporting),
        "pct_reporting_scope12": _pct(len(reporting), len(current)),
        "assured": len(assured),
        "pct_assured_of_reporting": _pct(len(assured), len(reporting)),
        "excluded_companies": sum(c["quality_flag"] == "excluded" for c in current),
        "issues_total": len(snapshot.issues),
        "issues_per_rule": per_rule,
        "companies_per_rule": {k: len(v) for k, v in companies_per_rule.items()},
        "quality_flags": {
            flag: sum(c["quality_flag"] == flag for c in current)
            for flag in ("ok", "review", "excluded")
        },
    }


def _pct(part: int, whole: int) -> float | None:
    return round(part / whole * 100, 1) if whole else None
