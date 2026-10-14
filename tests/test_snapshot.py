from pathlib import Path

import duckdb
import pandas as pd
import pytest

from pf_core.snapshot import build_snapshot, coverage_stats, load_snapshot
from tests.conftest import BRSR_DIR

SQL = Path(__file__).parent.parent / "sql" / "coverage.sql"


@pytest.fixture(scope="module")
def snapshot_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("snap")
    build_snapshot(BRSR_DIR, out)
    return out


def test_row_counts_add_up(tmp_path: Path) -> None:
    summary = build_snapshot(BRSR_DIR, tmp_path)
    assert summary.files_parsed == 20
    assert summary.files_failed == 0
    assert summary.parsed_company_years == 40
    assert summary.clean_company_years + summary.excluded_company_years == 40
    companies = pd.read_parquet(tmp_path / "companies.parquet")
    excluded = pd.read_parquet(tmp_path / "excluded.parquet")
    assert len(companies) == summary.parsed_company_years
    clean = companies[companies.quality_flag != "excluded"]
    assert len(clean) + len(excluded) == len(companies)
    assert excluded.reason.notna().all()


def test_round_trip(snapshot_dir: Path) -> None:
    snap = load_snapshot(snapshot_dir)
    titan = next(
        c
        for c in snap.companies
        if c["company_name"] == "Titan Company Limited" and c["is_current"]
    )
    assert titan["scope1_t"] == 3878
    assert titan["issues"] == ["V1"]
    assert titan["provenance"]["scope1_t"]["element"] == "TotalScope1Emissions"
    assert "metric tonnes" in titan["provenance"]["scope1_t"]["transformation"]
    rajesh = next(c for c in snap.companies if c["company_name"] == "RAJESH EXPORTS LIMITED")
    assert rajesh["scope1_t"] is None  # missing stays None after the Parquet round trip


def test_excluded_lists_reasons(snapshot_dir: Path) -> None:
    excluded = pd.read_parquet(snapshot_dir / "excluded.parquet")
    current = excluded[excluded.is_current.astype(bool)]
    assert len(current) == 5
    assert set(current.reason) == {"Company marks GHG disclosure as not applicable (V9)"}


def test_coverage_stats(snapshot_dir: Path) -> None:
    stats = coverage_stats(load_snapshot(snapshot_dir))
    assert stats["companies"] == 20
    assert stats["reporting_scope12"] == 15
    assert stats["pct_reporting_scope12"] == 75.0
    assert stats["assured"] == 6
    assert stats["issues_per_rule"]["V2"] == 4
    # Run 2 headline: problems (error/warning) are counted apart from informational notes.
    assert stats["issues_problems"] == 14  # V2 x4, V3 x8, V4 x1, V5 x1
    assert stats["issues_info"] == 26  # V1 x20, V6 x1, V9 x5
    assert stats["companies_with_problems"] == 6
    assert stats["issues_problems"] + stats["issues_info"] == stats["issues_total"] == 40
    assert {k: v for k, v in stats["problems_per_rule"].items() if v} == {
        "V2": 4,
        "V3": 8,
        "V4": 1,
        "V5": 1,
    }
    assert {k: v for k, v in stats["info_per_rule"].items() if v} == {"V1": 20, "V6": 1, "V9": 5}
    assert stats["companies_per_rule"]["V9"] == 5


def test_coverage_sql_matches_python(snapshot_dir: Path) -> None:
    sql = SQL.read_text().replace("data/snapshots/fixtures", snapshot_dir.as_posix())
    con = duckdb.connect()
    statements = [s for s in sql.split(";") if s.strip() and not _only_comments(s)]
    results = [con.execute(s).fetchall() for s in statements]
    headline = results[2][0]
    assert headline[:2] == (20, 15)
    assert headline[3] == 6
    stats = coverage_stats(load_snapshot(snapshot_dir))
    per_rule = {}
    for rule, _severity, issues, _companies in results[3]:
        per_rule[rule] = per_rule.get(rule, 0) + issues
    assert per_rule == {k: v for k, v in stats["issues_per_rule"].items() if v}


def _only_comments(statement: str) -> bool:
    return all(line.strip().startswith("--") or not line.strip() for line in statement.splitlines())
