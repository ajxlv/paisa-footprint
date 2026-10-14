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
import re
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel

from pf_core.brsr.models import BrsrFiling
from pf_core.brsr.normalise import CleanCompanyYear, normalise
from pf_core.brsr.parser import parse_directory
from pf_core.brsr.validators import RULE_DESCRIPTIONS, fy_label, validate

COMPANIES = "companies.parquet"
VALIDATION = "validation_report.parquet"
EXCLUDED = "excluded.parquet"
MANIFEST = "manifest.json"


class SnapshotSummary(BaseModel):
    """Row counts for one build. `parsed_company_years == clean + excluded` always holds."""

    files_seen: int
    files_parsed: int
    files_failed: int
    files_superseded: int = 0
    parsed_company_years: int
    clean_company_years: int
    excluded_company_years: int
    duplicate_company_years: int = 0
    issues: int


def build_snapshot(input_dir: str | Path, out_dir: str | Path) -> SnapshotSummary:
    """Parse, validate and normalise every filing in `input_dir`; write Parquet to `out_dir`."""
    input_dir, out_dir = Path(input_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    parsed, failures = parse_directory(input_dir)
    filings, superseded = select_latest(parsed)

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
    rows, duplicates = dedupe_company_years(rows)
    kept = {(r.source_file, r.fiscal_year) for r in rows}
    issue_rows = [i for i in issue_rows if (i["source_file"], i["fiscal_year"]) in kept]

    companies = pd.DataFrame([_company_record(r) for r in rows])
    validation = pd.DataFrame(issue_rows, columns=_ISSUE_COLUMNS)
    excluded = _excluded_frame(rows, failures, superseded, duplicates)

    companies.to_parquet(out_dir / COMPANIES, index=False)
    validation.to_parquet(out_dir / VALIDATION, index=False)
    excluded.to_parquet(out_dir / EXCLUDED, index=False)

    summary = SnapshotSummary(
        files_seen=len(parsed) + len(failures),
        files_parsed=len(parsed),
        files_failed=len(failures),
        files_superseded=len(superseded),
        parsed_company_years=len(rows),
        clean_company_years=sum(r.quality_flag != "excluded" for r in rows),
        excluded_company_years=sum(r.quality_flag == "excluded" for r in rows),
        duplicate_company_years=len(duplicates),
        issues=len(issue_rows),
    )
    manifest = {
        "inputs": {p.name: _sha256(p) for p in sorted(input_dir.glob("*.xml"))},
        "superseded": superseded,
        "summary": summary.model_dump(),
    }
    (out_dir / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return summary


_STAMP = re.compile(r"_(\d{8})_(\d{6,9})\.xml$", re.IGNORECASE)


def submission_stamp(source_file: str) -> str:
    """Sortable submission time from NSE's file name (`..._YYYYMMDD_HHMMSSmmm.xml`), else ''."""
    match = _STAMP.search(source_file)
    return f"{match.group(1)}{match.group(2):0<9}" if match else ""


def select_latest(filings: list[BrsrFiling]) -> tuple[list[BrsrFiling], dict[str, str]]:
    """Keep the latest submission per company per reporting year; the rest are `superseded`.

    A company can re-file (revise) its BRSR. The newest submission, by the timestamp NSE puts in
    the file name, wins. Superseded files are returned with a reason, never silently dropped.
    """
    groups: dict[tuple[str, date], list[BrsrFiling]] = {}
    for filing in filings:
        groups.setdefault((filing.company_key, filing.fy_current.period_end), []).append(filing)
    kept: list[BrsrFiling] = []
    superseded: dict[str, str] = {}
    for group in groups.values():
        ordered = sorted(group, key=lambda f: (submission_stamp(f.source_file), f.source_file))
        winner = ordered[-1]
        kept.append(winner)
        for loser in ordered[:-1]:
            superseded[loser.source_file] = (
                f"Superseded by {winner.source_file} (later submission for "
                f"{fy_label(winner.fy_current)})"
            )
    kept.sort(key=lambda f: f.source_file)
    return kept, superseded


def dedupe_company_years(
    rows: list[CleanCompanyYear],
) -> tuple[list[CleanCompanyYear], list[dict[str, str]]]:
    """One row per company per fiscal year, and `is_current` only on each company's latest year.

    With several years of filings, a year appears twice: as the reporting year of one filing and
    as the comparative ("previous year") of the next. The reporting-year figure is kept (it is
    the primary disclosure); the other is recorded as a duplicate with the reason.
    """
    best: dict[tuple[str, date], CleanCompanyYear] = {}
    duplicates: list[dict[str, str]] = []
    for row in sorted(rows, key=_row_priority, reverse=True):
        key = (row.company_key, row.period_end)
        if key in best:
            duplicates.append(
                {
                    "company_key": row.company_key,
                    "company_name": row.company_name,
                    "fiscal_year": row.fiscal_year,
                    "source_file": row.source_file,
                    "reason": f"Duplicate company-year; kept {best[key].source_file}",
                }
            )
            continue
        best[key] = row
    latest: dict[str, date] = {}
    for company_key, period_end in best:
        latest[company_key] = max(latest.get(company_key, period_end), period_end)
    deduped = [
        row.model_copy(update={"is_current": row.period_end == latest[row.company_key]})
        for row in best.values()
    ]
    deduped.sort(key=lambda r: (r.source_file, not r.is_current, r.period_end))
    return deduped, duplicates


def _row_priority(row: CleanCompanyYear) -> tuple[bool, str]:
    return (row.is_current, submission_stamp(row.source_file) or row.source_file)


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


def _excluded_frame(
    rows: list[CleanCompanyYear],
    failures: dict[str, str],
    superseded: dict[str, str],
    duplicates: list[dict[str, str]],
) -> pd.DataFrame:
    """Everything left out of the snapshot's usable rows, each with its reason."""
    records: list[dict[str, Any]] = [
        {
            "company_key": r.company_key,
            "company_name": r.company_name,
            "fiscal_year": r.fiscal_year,
            "is_current": r.is_current,
            "source_file": r.source_file,
            "kind": "excluded",
            "reason": r.exclusion_reason,
        }
        for r in rows
        if r.quality_flag == "excluded"
    ]
    blank = {"company_key": None, "company_name": None, "fiscal_year": None, "is_current": None}
    records.extend(
        {**blank, "source_file": name, "kind": "parse_failed", "reason": f"Failed to parse: {why}"}
        for name, why in failures.items()
    )
    records.extend(
        {**blank, "source_file": name, "kind": "superseded", "reason": why}
        for name, why in superseded.items()
    )
    records.extend({**d, "is_current": False, "kind": "duplicate"} for d in duplicates)
    return pd.DataFrame(records, columns=_EXCLUDED_COLUMNS)


_EXCLUDED_COLUMNS = [
    "company_key",
    "company_name",
    "fiscal_year",
    "is_current",
    "source_file",
    "kind",
    "reason",
]


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


PROBLEM_SEVERITIES = ("error", "warning")


def coverage_stats(snapshot: Snapshot) -> dict[str, Any]:
    """Headline numbers for the current fiscal year of each company, plus issues per rule.

    Issues are split into *problems* (severity error or warning: something a human should check)
    and *informational notes* (severity info: handled by design, e.g. MtCO2e read as tonnes).
    Counting the two together overstated the data's problems, so the headline uses problems only.
    """
    current = [c for c in snapshot.companies if c["is_current"]]
    reporting = [c for c in current if c["scope1_t"] is not None and c["scope2_t"] is not None]
    assured = [c for c in reporting if c["assured"] is True]
    problems = [i for i in snapshot.issues if i["severity"] in PROBLEM_SEVERITIES]
    return {
        "companies": len(current),
        "reporting_scope12": len(reporting),
        "pct_reporting_scope12": _pct(len(reporting), len(current)),
        "assured": len(assured),
        "pct_assured_of_reporting": _pct(len(assured), len(reporting)),
        "excluded_companies": sum(c["quality_flag"] == "excluded" for c in current),
        "issues_problems": len(problems),
        "issues_info": len(snapshot.issues) - len(problems),
        "companies_with_problems": len({i["company_key"] for i in problems}),
        "issues_total": len(snapshot.issues),
        **_per_rule(snapshot.issues),
        "quality_flags": {
            flag: sum(c["quality_flag"] == flag for c in current)
            for flag in ("ok", "review", "excluded")
        },
    }


def _per_rule(issues: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Issue and company counts per rule, with problems and informational notes kept apart."""
    rules = list(RULE_DESCRIPTIONS)
    totals = dict.fromkeys(rules, 0)
    problem_counts = dict.fromkeys(rules, 0)
    companies: dict[str, set[str]] = {rule: set() for rule in rules}
    for issue in issues:
        rule = issue["rule_id"]
        totals[rule] = totals.get(rule, 0) + 1
        if issue["severity"] in PROBLEM_SEVERITIES:
            problem_counts[rule] = problem_counts.get(rule, 0) + 1
        companies.setdefault(rule, set()).add(issue["company_key"])
    return {
        "issues_per_rule": totals,
        "problems_per_rule": problem_counts,
        "info_per_rule": {rule: totals[rule] - problem_counts.get(rule, 0) for rule in totals},
        "companies_per_rule": {rule: len(keys) for rule, keys in companies.items()},
    }


def _pct(part: int, whole: int) -> float | None:
    return round(part / whole * 100, 1) if whole else None
