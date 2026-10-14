"""Real-EVIC loader. Test CSVs are written to tmp_path with fake company keys (TESTCO*), so no
made-up market value is ever paired with a real company outside an illustrative file."""

from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli.pf import app
from pf_core.pcaf.engine import compute_portfolio
from pf_core.pcaf.evic import compute_evic, load_evic_real, months_apart
from pf_core.pcaf.models import CompanyEmissions, Holding
from pf_core.snapshot import build_snapshot
from tests.conftest import BRSR_DIR, SYNTHETIC_DIR

HEADER = "company_key,market_cap_inr,total_debt_inr,minority_interest_inr,as_of_date,source\n"
TEMPLATE = Path(__file__).parent.parent / "data_templates" / "evic_template.csv"


def write(tmp_path: Path, rows: str, name: str = "evic_testcase.csv") -> Path:
    path = tmp_path / name
    path.write_text(HEADER + rows, encoding="utf-8")
    return path


def test_template_has_exactly_the_documented_headers() -> None:
    assert TEMPLATE.read_text(encoding="utf-8") == HEADER


def test_evic_is_market_cap_plus_debt_plus_minority_no_cash_deduction() -> None:
    assert compute_evic(1000.0, 200.0, 50.0) == (1250.0, False)
    assert compute_evic(1000.0, 200.0, None) == (1200.0, False)
    assert compute_evic(1000.0, None, None) == (1000.0, True)  # partial: debt missing


def test_load_valid_and_partial_rows(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "TESTCO1,1000,200,,2026-03-31,test source\nTESTCO2,500,,,2026-03-31,test source\n",
    )
    fins, issues = load_evic_real(path)
    assert fins["TESTCO1"].evic_inr == 1200
    assert not fins["TESTCO1"].evic_partial
    assert fins["TESTCO2"].evic_inr == 500
    assert fins["TESTCO2"].evic_partial
    assert [(i.company_key, i.rule_id, i.severity) for i in issues] == [
        ("TESTCO2", "E2", "warning")
    ]
    assert not any(f.evic_is_illustrative for f in fins.values())


@pytest.mark.parametrize("cap", ["0", "-5", ""])
def test_market_cap_missing_or_non_positive_is_an_error_and_no_evic(
    tmp_path: Path, cap: str
) -> None:
    fins, issues = load_evic_real(write(tmp_path, f"TESTCO1,{cap},100,,2026-03-31,s\n"))
    assert fins == {}
    assert [(i.rule_id, i.severity) for i in issues] == [("E1", "error")]


def test_stale_as_of_date_warns(tmp_path: Path) -> None:
    path = write(tmp_path, "TESTCO1,1000,0,,2024-06-30,s\nTESTCO2,1000,0,,2026-09-30,s\n")
    fy_end = {"TESTCO1": date(2026, 3, 31), "TESTCO2": date(2026, 3, 31)}
    _, issues = load_evic_real(path, fy_end)
    assert [(i.company_key, i.rule_id) for i in issues] == [("TESTCO1", "E3")]  # 21 vs 6 months
    assert months_apart(date(2024, 6, 30), date(2026, 3, 31)) == 21


def test_missing_columns_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("company_key,evic_inr\nX,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        load_evic_real(path)


def test_file_named_illustrative_stays_illustrative(tmp_path: Path) -> None:
    fins, _ = load_evic_real(
        write(tmp_path, "TESTCO1,1000,0,,2026-03-31,s\n", "illustrative_x.csv")
    )
    assert fins["TESTCO1"].evic_is_illustrative


def emissions(key: str) -> CompanyEmissions:
    return CompanyEmissions(
        company_key=key,
        company_name=f"Test {key}",
        scope1_t=100.0,
        scope2_t=100.0,
        revenue_inr=1e9,
        assured=True,
        fiscal_year="FY2025-26",
        quality_flag="ok",
    )


def test_all_real_evic_means_no_illustrative_inputs_and_partial_caps_dq(tmp_path: Path) -> None:
    fins, _ = load_evic_real(
        write(tmp_path, "TESTCO1,1e10,1e9,,2026-03-31,s\nTESTCO2,1e10,,,2026-03-31,s\n")
    )
    holdings = [Holding(isin_or_symbol=k, company_key=k, value_inr=1e7) for k in fins]
    result = compute_portfolio(holdings, {k: emissions(k) for k in fins}, fins)
    assert result.contains_illustrative_inputs is False
    dq = {h.company_key: h.pcaf_data_quality for h in result.holdings}
    assert dq == {"TESTCO1": 1, "TESTCO2": 2}  # assured, but TESTCO2's EVIC lacks debt
    assert next(h for h in result.holdings if h.company_key == "TESTCO2").evic_partial


def test_cli_mixing_real_and_illustrative_evic_is_still_illustrative(tmp_path: Path) -> None:
    snap = tmp_path / "snap"
    build_snapshot(BRSR_DIR, snap)
    real = write(tmp_path, "TESTCO1,1000,0,,2026-03-31,s\n")
    out = tmp_path / "r.json"
    result = CliRunner().invoke(
        app,
        [
            "compute",
            "--portfolio",
            str(SYNTHETIC_DIR / "portfolio_synthetic_c.csv"),
            "--evic",
            str(SYNTHETIC_DIR / "illustrative_evic.csv"),
            "--evic-real",
            str(real),
            "--snapshot",
            str(snap),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert '"contains_illustrative_inputs": true' in out.read_text()


def test_cli_needs_some_evic(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app, ["compute", "--portfolio", str(SYNTHETIC_DIR / "portfolio_synthetic_c.csv")]
    )
    assert result.exit_code != 0
