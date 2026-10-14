import shutil
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from pf_core.snapshot import build_snapshot, coverage_stats, load_snapshot, submission_stamp
from tests.conftest import BRSR_DIR, BRSR_FILES

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
    assert stats["issues_per_rule"]["V2"] + stats["issues_per_rule"]["V2-fix"] == 4
    # Run 2 headline: problems (error/warning) are counted apart from informational notes.
    assert stats["issues_problems"] == 14  # V2 x4, V3 x8, V4 x1, V5 x1
    assert stats["issues_info"] == 26  # V1 x20, V6 x1, V9 x5
    assert stats["companies_with_problems"] == 6
    assert stats["issues_problems"] + stats["issues_info"] == stats["issues_total"] == 40
    assert {k: v for k, v in stats["problems_per_rule"].items() if v} == {
        "V2": 1,
        "V2-fix": 3,
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


NMDC_FILE = next(p for p in BRSR_FILES if "BRSR_2729_" in p.name)


def test_revised_filing_supersedes_earlier_one(tmp_path: Path) -> None:
    """Two submissions for the same company-year: the later (by NSE's file-name stamp) wins."""
    raw = tmp_path / "raw"
    raw.mkdir()
    shutil.copy(NMDC_FILE, raw / "BRSR_2729_WebXMLFile_20260916_165325349.xml")
    shutil.copy(NMDC_FILE, raw / "BRSR_2729_WebXMLFile_20261001_090000000.xml")
    summary = build_snapshot(raw, tmp_path / "snap")
    assert summary.files_parsed == 2
    assert summary.files_superseded == 1
    assert summary.parsed_company_years == 2
    excluded = pd.read_parquet(tmp_path / "snap" / "excluded.parquet")
    superseded = excluded[excluded.kind == "superseded"]
    assert list(superseded.source_file) == ["BRSR_2729_WebXMLFile_20260916_165325349.xml"]
    assert "BRSR_2729_WebXMLFile_20261001_090000000.xml" in superseded.reason.iloc[0]


def test_overlapping_years_keep_reporting_year_figure(tmp_path: Path) -> None:
    """A later year's filing repeats this year as its comparative; the reporting-year figure wins.

    The FY2026-27 file is built in the test by shifting NMDC's dates forward one year. It is a
    constructed input in a temporary directory, never a fixture, and is deleted with tmp_path.
    """
    raw = tmp_path / "raw"
    raw.mkdir()
    shutil.copy(NMDC_FILE, raw / NMDC_FILE.name)
    text = NMDC_FILE.read_text(encoding="utf-8")
    for old, placeholder in (
        ("2026-03-31", "@A"),
        ("2025-04-01", "@B"),
        ("2025-03-31", "@C"),
        ("2024-04-01", "@D"),
    ):
        text = text.replace(old, placeholder)
    for placeholder, new in (
        ("@A", "2027-03-31"),
        ("@B", "2026-04-01"),
        ("@C", "2026-03-31"),
        ("@D", "2025-04-01"),
    ):
        text = text.replace(placeholder, new)
    (raw / "BRSR_9999_WebXMLFile_20270915_100000000.xml").write_text(text, encoding="utf-8")

    summary = build_snapshot(raw, tmp_path / "snap")
    assert summary.duplicate_company_years == 1
    snap = load_snapshot(tmp_path / "snap")
    nmdc = [c for c in snap.companies if c["company_key"] == "INE584A01023"]
    assert sorted(c["fiscal_year"] for c in nmdc) == ["FY2024-25", "FY2025-26", "FY2026-27"]
    assert [c["fiscal_year"] for c in nmdc if c["is_current"]] == ["FY2026-27"]
    fy26 = next(c for c in nmdc if c["fiscal_year"] == "FY2025-26")
    assert fy26["source_file"] == NMDC_FILE.name  # its own reporting year, not the comparative
    excluded = pd.read_parquet(tmp_path / "snap" / "excluded.parquet")
    assert list(excluded[excluded.kind == "duplicate"].fiscal_year) == ["FY2025-26"]


def test_submission_stamp_parsing() -> None:
    assert submission_stamp("BRSR_1_WebXMLFile_20260916_165325349.xml") == "20260916165325349"
    assert submission_stamp("odd-name.xml") == ""
