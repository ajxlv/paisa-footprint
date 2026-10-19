"""AMC ingestion, V8 and fund ranking, on the SYNTHETIC workbook only (no real AMC files)."""

import importlib.util
from datetime import date, datetime
from pathlib import Path

import pytest
from openpyxl import Workbook
from typer.testing import CliRunner

from cli.pf import app
from pf_core.funds.adapters import GenericExcelAdapter
from pf_core.funds.ingest import parse_amc_dir, rank_snapshot_funds, read_funds, write_funds
from pf_core.funds.models import FundHolding, FundPortfolio
from pf_core.funds.ranking import FundResult, rank_funds
from pf_core.funds.validators import isin_format, merge_duplicates, v8_nav_sum, validate_fund
from pf_core.pcaf.inputs import load_evic_csv
from pf_core.snapshot import build_snapshot
from tests.conftest import BRSR_DIR, SYNTHETIC_DIR

WORKBOOK = SYNTHETIC_DIR / "amc_portfolio_synthetic.xlsx"
EVIC = SYNTHETIC_DIR / "illustrative_evic.csv"


@pytest.fixture(scope="module")
def schemes() -> dict[str, FundPortfolio]:
    return {p.scheme_name: p for p in GenericExcelAdapter("Illustrative AMC").parse(WORKBOOK)}


@pytest.fixture(scope="module")
def snapshot_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("snap")
    build_snapshot(BRSR_DIR, out)
    return out


def test_generator_script_reproduces_the_committed_workbook(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("make_amc", SYNTHETIC_DIR / "make_amc_fixture.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fresh = module.build(tmp_path / "amc_portfolio_synthetic.xlsx")
    parse = GenericExcelAdapter("Illustrative AMC").parse
    assert [p.holdings for p in parse(fresh)] == [p.holdings for p in parse(WORKBOOK)]


def test_finds_every_scheme_including_stacked_ones(schemes: dict[str, FundPortfolio]) -> None:
    assert list(schemes) == [
        "Illustrative Large Cap Fund",
        "Illustrative Mid Cap Fund",
        "Illustrative Flexi Cap Fund",
    ]
    assert {p.sheet for p in schemes.values()} == {"Illustrative Large Cap", "Two Schemes"}
    assert all(p.as_of_date == date(2026, 3, 31) for p in schemes.values())
    assert all(p.illustrative for p in schemes.values())


def test_merged_two_row_header_and_lakh_scaling(schemes: dict[str, FundPortfolio]) -> None:
    nmdc = schemes["Illustrative Large Cap Fund"].holdings[0]
    assert nmdc == FundHolding(
        isin="INE584A01023",
        name="NMDC Limited",
        quantity=100000,
        market_value_inr=600 * 1e5,
        pct_nav=20.0,
    )


def test_totals_skipped_and_cash_lines_kept(schemes: dict[str, FundPortfolio]) -> None:
    large = schemes["Illustrative Large Cap Fund"]
    names = [h.name for h in large.holdings]
    assert "Sub Total" not in names and "Grand Total" not in names
    assert "Equity & Equity related" not in names
    treps = large.holdings[-1]
    assert (treps.name, treps.isin, treps.is_equity) == ("TREPS", None, False)
    assert len(large.holdings) == 7


def test_v8_flags_weights_outside_95_105(schemes: dict[str, FundPortfolio]) -> None:
    assert v8_nav_sum(schemes["Illustrative Large Cap Fund"]) == []
    issues = v8_nav_sum(schemes["Illustrative Mid Cap Fund"])
    assert [i.rule_id for i in issues] == ["V8"]
    assert "81.00%" in issues[0].message


def test_v8_without_weights_is_reported() -> None:
    p = FundPortfolio(
        amc="a",
        scheme_name="s",
        as_of_date=None,
        source_file="f",
        sheet="x",
        holdings=[FundHolding(isin=None, name="x", market_value_inr=1.0)],
    )
    assert "cannot be checked" in v8_nav_sum(p)[0].message


def test_duplicate_isins_are_summed_with_a_warning(schemes: dict[str, FundPortfolio]) -> None:
    merged, issues = merge_duplicates(schemes["Illustrative Mid Cap Fund"])
    gulshan = [h for h in merged.holdings if h.isin == "INE255D01024"]
    assert len(gulshan) == 1
    assert (gulshan[0].quantity, gulshan[0].market_value_inr, gulshan[0].pct_nav) == (
        30000,
        250 * 1e5,
        25.0,
    )
    assert [i.rule_id for i in issues] == ["V8-dup"]


def test_non_ine_isin_warns(schemes: dict[str, FundPortfolio]) -> None:
    issues = isin_format(schemes["Illustrative Flexi Cap Fund"])
    assert [i.rule_id for i in issues] == ["V8-isin"]
    assert "XX0SYN000001" in issues[0].message


def test_equity_detection_by_isin_security_type() -> None:
    assert FundHolding(isin="INE584A01023", name="x").is_equity
    assert not FundHolding(isin="INE584A07023", name="debenture").is_equity
    assert not FundHolding(isin=None, name="cash").is_equity


def test_other_layouts_rupees_single_header_datetime_and_filename_date(tmp_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["Illustrative Tiny Scheme"])
    ws.append(["Portfolio as of", datetime(2026, 2, 28)])
    ws.append([])
    ws.append(["Security", "ISIN Code", "Qty", "Market Value (Rs.)", "% of Net Assets"])
    ws.append(["NMDC Limited", "INE584A01023", 10, "1,00,000", "98.5%"])
    ws.append(["Cash", None, None, 1500, "1.5"])
    ws2 = wb.create_sheet("Second")
    ws2.append(["Name of the Instrument", "ISIN", "Market Value", "% to NAV"])
    ws2.append(["NMDC Limited", "INE584A01023", 100, "-"])
    path = tmp_path / "2026-02.xlsx"
    wb.save(path)
    first, second = GenericExcelAdapter("x").parse(path)
    assert first.scheme_name == "Illustrative Tiny Scheme"
    assert first.as_of_date == date(2026, 2, 28)
    assert first.holdings[0].market_value_inr == 100000.0
    assert [h.pct_nav for h in first.holdings] == [98.5, 1.5]
    assert second.scheme_name == "Second"  # no name above the header: sheet title
    assert second.as_of_date == date(2026, 2, 28)  # from the file name
    assert second.holdings[0].pct_nav is None  # "-" is missing, never zero
    assert any("assumed rupees" in n for n in second.parse_notes)


def test_parquet_round_trip_and_failures(tmp_path: Path) -> None:
    raw = tmp_path / "amc" / "illustrative-amc"
    raw.mkdir(parents=True)
    (raw / "amc_portfolio_synthetic.xlsx").write_bytes(WORKBOOK.read_bytes())
    (raw / "broken.xlsx").write_bytes(b"not a workbook")
    portfolios, issues, failures = parse_amc_dir(tmp_path / "amc")
    assert len(portfolios) == 3
    assert list(failures) == [str(raw / "broken.xlsx")]
    write_funds(portfolios, issues, tmp_path / "out" / "funds.parquet")
    back, back_issues = read_funds(tmp_path / "out" / "funds.parquet")
    assert [p.holdings for p in back] == [p.holdings for p in portfolios]
    assert back_issues == issues


def test_large_cap_footprint_matches_hand_calculation(
    snapshot_dir: Path, schemes: dict[str, FundPortfolio]
) -> None:
    portfolio, issues = validate_fund(schemes["Illustrative Large Cap Fund"])
    (result,) = rank_snapshot_funds(snapshot_dir, load_evic_csv(EVIC), [portfolio], issues)
    # value / illustrative EVIC x (S1+S2), from the real filings; Rajesh Exports is uncovered (V9).
    financed = (
        6e7 / 6e11 * 198372
        + 9e7 / 1.5e13 * 328344.91
        + 3e7 / 3e12 * 25059
        + 3e7 / 1e11 * 249328
        + 3e7 / 8e10 * 83825
    )
    assert result.financed_emissions_t == pytest.approx(financed, rel=1e-9)
    assert result.carbon_footprint_t_per_crore == pytest.approx(financed / 24, rel=1e-9)
    assert result.coverage_pct == pytest.approx(24 / 25.5 * 100)
    assert result.equity_value_inr == 25.5e7
    assert result.non_equity_value_inr == 4.5e7  # TREPS, reported but not attributed
    assert [u.isin_or_symbol for u in result.uncovered] == ["INE343B01030"]
    assert result.top_contributors[0].company_name == "Uflex Ltd"
    assert result.contains_illustrative_inputs


def test_low_coverage_fund_is_not_ranked(snapshot_dir: Path) -> None:
    portfolios, issues, _ = parse_amc_dir_from_workbook()
    results = {
        r.scheme_name: r
        for r in rank_snapshot_funds(snapshot_dir, load_evic_csv(EVIC), portfolios, issues)
    }
    flexi = results["Illustrative Flexi Cap Fund"]
    assert flexi.status == "insufficient coverage"
    assert flexi.rank is None
    assert flexi.coverage_pct == pytest.approx(100 / 900 * 100)
    assert results["Illustrative Large Cap Fund"].rank == 1
    assert results["Illustrative Mid Cap Fund"].rank == 2


def parse_amc_dir_from_workbook() -> tuple[list[FundPortfolio], list, dict[str, str]]:
    portfolios, issues = [], []
    for p in GenericExcelAdapter("Illustrative AMC").parse(WORKBOOK):
        merged, found = validate_fund(p)
        portfolios.append(merged)
        issues.extend(found)
    return portfolios, issues, {}


def _result(key: str, footprint: float, illustrative: bool) -> FundResult:
    return FundResult(
        fund_key=key,
        amc="a",
        scheme_name=key,
        as_of_date=None,
        source_file="f",
        illustrative=illustrative,
        status="ranked",
        rank=None,
        equity_value_inr=1.0,
        non_equity_value_inr=0.0,
        coverage_pct=100.0,
        carbon_footprint_t_per_crore=footprint,
        waci_t_per_crore_revenue=None,
        financed_emissions_t=0.0,
        pcaf_data_quality=1.0,
        contains_illustrative_inputs=illustrative,
        top_contributors=[],
        uncovered=[],
        issues=[],
    )


def test_real_and_illustrative_funds_are_ranked_separately() -> None:
    ranked = {
        r.fund_key: r.rank
        for r in rank_funds(
            [
                _result("real-b", 5.0, False),
                _result("real-a", 2.0, False),
                _result("demo-a", 1.0, True),
                _result("demo-b", 9.0, True),
            ]
        )
    }
    assert ranked == {"real-a": 1, "real-b": 2, "demo-a": 1, "demo-b": 2}


def test_cli_ingest_and_rank(tmp_path: Path, snapshot_dir: Path) -> None:
    raw = tmp_path / "amc" / "illustrative-amc"
    raw.mkdir(parents=True)
    (raw / "amc_portfolio_synthetic.xlsx").write_bytes(WORKBOOK.read_bytes())
    snap = tmp_path / "snap"
    build_snapshot(BRSR_DIR, snap)
    runner = CliRunner()
    r1 = runner.invoke(
        app,
        ["ingest-funds", "--input", str(tmp_path / "amc"), "--out", str(snap / "funds.parquet")],
    )
    assert r1.exit_code == 0, r1.output
    assert "Schemes parsed: 3" in r1.output
    r2 = runner.invoke(app, ["rank-funds", "--snapshot", str(snap), "--evic", str(EVIC)])
    assert r2.exit_code == 0, r2.output
    assert "insufficient coverage" in r2.output
    assert (snap / "fund_rankings.json").exists()


def test_duplicate_with_a_missing_value_sums_to_unknown_not_partial() -> None:
    p = FundPortfolio(
        amc="a",
        scheme_name="s",
        as_of_date=None,
        source_file="f",
        sheet="x",
        holdings=[
            FundHolding(isin="INE584A01023", name="n", market_value_inr=100.0, pct_nav=10.0),
            FundHolding(isin="INE584A01023", name="n", market_value_inr=None, pct_nav=5.0),
        ],
    )
    merged, _ = merge_duplicates(p)
    (only,) = merged.holdings
    assert only.market_value_inr is None  # 100 + unknown is unknown, never 100
    assert only.pct_nav == 15.0


def test_unvalued_non_equity_lines_are_counted_not_zeroed(snapshot_dir: Path) -> None:
    p = FundPortfolio(
        amc="a",
        scheme_name="s",
        as_of_date=None,
        source_file="f",
        sheet="x",
        holdings=[
            FundHolding(isin="INE584A01023", name="NMDC", market_value_inr=1e7, pct_nav=90.0),
            FundHolding(isin=None, name="TREPS", market_value_inr=5e5, pct_nav=5.0),
            FundHolding(isin=None, name="Net receivables", market_value_inr=None, pct_nav=5.0),
        ],
    )
    (result,) = rank_snapshot_funds(snapshot_dir, load_evic_csv(EVIC), [p], [])
    assert result.non_equity_value_inr == 5e5
    assert result.non_equity_unvalued_lines == 1
