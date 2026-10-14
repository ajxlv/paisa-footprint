from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from typer.testing import CliRunner

from cli.pf import app
from pf_core.pcaf.engine import AttributionError, attribution, compute_portfolio
from pf_core.pcaf.inputs import (
    company_index,
    emissions_from_snapshot,
    load_evic_csv,
    load_portfolio_csv,
)
from pf_core.pcaf.models import CompanyEmissions, CompanyFinancials, Holding, PortfolioResult
from pf_core.snapshot import Snapshot, build_snapshot, load_snapshot
from tests.conftest import BRSR_DIR, SYNTHETIC_DIR

EVIC_CSV = SYNTHETIC_DIR / "illustrative_evic.csv"

# Hand-derived in docs/worked-example.md (do not change one without the other).
WORKED_A = {
    "total_value_inr": 300_000_000,
    "financed_emissions_t": 83.2346091,
    "carbon_footprint_t_per_crore": 2.77448697,
    "waci_t_per_crore_revenue": 12.973405146532551826,
    "pcaf_data_quality": 7 / 6,
    "per_holding_financed": {
        "INE584A01023": 19.8372,
        "INE040A01034": 3.2834491,
        "INE280A01028": 0.25059,
        "INE188A01015": 34.93057,
        "INE516A01017": 24.9328,
    },
}


@pytest.fixture(scope="module")
def snapshot(tmp_path_factory: pytest.TempPathFactory) -> Snapshot:
    out = tmp_path_factory.mktemp("snap")
    build_snapshot(BRSR_DIR, out)
    return load_snapshot(out)


def run(snapshot: Snapshot, portfolio: str) -> PortfolioResult:
    holdings = load_portfolio_csv(SYNTHETIC_DIR / portfolio, company_index(snapshot))
    return compute_portfolio(holdings, emissions_from_snapshot(snapshot), load_evic_csv(EVIC_CSV))


def test_illustrative_evic_covers_the_15_reporting_companies(snapshot: Snapshot) -> None:
    evic = load_evic_csv(EVIC_CSV)
    reporting = {
        k for k, e in emissions_from_snapshot(snapshot).items() if e.quality_flag != "excluded"
    }
    assert set(evic) == reporting
    assert len(evic) == 15
    assert all(f.evic_is_illustrative for f in evic.values())


def test_worked_example_portfolio_a(snapshot: Snapshot) -> None:
    result = run(snapshot, "portfolio_synthetic_a.csv")
    rel = 1e-9
    assert result.total_value_inr == WORKED_A["total_value_inr"]
    assert result.coverage_pct == 100
    assert result.uncovered == []
    assert result.financed_emissions_t == pytest.approx(WORKED_A["financed_emissions_t"], rel=rel)
    assert result.carbon_footprint_t_per_crore == pytest.approx(
        WORKED_A["carbon_footprint_t_per_crore"], rel=rel
    )
    assert result.waci_t_per_crore_revenue == pytest.approx(
        WORKED_A["waci_t_per_crore_revenue"], rel=rel
    )
    assert result.pcaf_data_quality == pytest.approx(WORKED_A["pcaf_data_quality"], rel=rel)
    per = {h.company_key: h.financed_emissions_t for h in result.holdings}
    assert per == pytest.approx(WORKED_A["per_holding_financed"], rel=rel)
    assert result.contains_illustrative_inputs is True


# Hand-derived in docs/worked-example-b.md (run 2, with the V2-fix revenue correction).
WORKED_B = {
    "financed_emissions_t": 45.228640153333333,
    "carbon_footprint_t_per_crore": 5.9511368622807018,
    "waci_t_per_crore_revenue": 15.331996449270470,
    "pcaf_data_quality": 51 / 38,
    "waci_data_quality": 51 / 38,
    "themis_intensity": 18716.91 / 165.82,
}


def test_worked_example_portfolio_b(snapshot: Snapshot) -> None:
    result = run(snapshot, "portfolio_synthetic_b.csv")
    rel = 1e-9
    for key in (
        "financed_emissions_t",
        "carbon_footprint_t_per_crore",
        "waci_t_per_crore_revenue",
        "pcaf_data_quality",
        "waci_data_quality",
    ):
        assert getattr(result, key) == pytest.approx(WORKED_B[key], rel=rel), key
    themis = next(h for h in result.holdings if h.company_key == "INE942C01045")
    assert themis.intensity_t_per_crore_revenue == pytest.approx(
        WORKED_B["themis_intensity"], rel=rel
    )


def test_portfolio_b_exclusions(snapshot: Snapshot) -> None:
    result = run(snapshot, "portfolio_synthetic_b.csv")
    reasons = {u.isin_or_symbol: u.reason for u in result.uncovered}
    assert set(reasons) == {"RAJESHEXPO", "INE000000000"}
    assert "V9" in reasons["RAJESHEXPO"]
    assert "V7" in reasons["INE000000000"]
    themis = next(h for h in result.holdings if h.company_key == "INE942C01045")
    # Run 2: revenue corrected by V2-fix, so Gujarat Themis is now in WACI, flagged.
    assert themis.in_waci is True
    assert themis.revenue_corrected is True
    assert themis.waci_data_quality == 2
    assert result.total_value_inr == 90_000_000
    assert result.covered_value_inr == 76_000_000
    assert result.coverage_pct == pytest.approx(76 / 90 * 100)
    assert result.waci_value_inr == 76_000_000  # run 2: every covered holding is in WACI


def test_portfolio_c_single_holding(snapshot: Snapshot) -> None:
    result = run(snapshot, "portfolio_synthetic_c.csv")
    # ₹1 crore of NMDC at an illustrative EVIC of ₹60,000 crore: 1/60000 of 198,372 t.
    assert result.financed_emissions_t == pytest.approx(198_372 / 60_000, rel=1e-12)
    assert result.carbon_footprint_t_per_crore == pytest.approx(198_372 / 60_000, rel=1e-12)
    assert result.pcaf_data_quality == 1


def test_attribution_rejects_above_one() -> None:
    with pytest.raises(AttributionError):
        attribution(2e9, 1e9)
    assert attribution(1e9, 1e9) == 1


def test_holding_bigger_than_company_is_uncovered_not_dropped() -> None:
    result = compute_portfolio([_holding("X", 2e9)], {"X": _emissions("X")}, {"X": _fin("X", 1e9)})
    assert result.holdings == []
    assert len(result.uncovered) == 1
    assert "outside (0, 1]" in result.uncovered[0].reason


def test_missing_evic_is_uncovered_but_still_in_waci() -> None:
    result = compute_portfolio([_holding("X", 1e7)], {"X": _emissions("X")}, {})
    assert result.coverage_pct == 0
    assert result.uncovered[0].reason == "No EVIC available for this company"
    assert result.waci_t_per_crore_revenue == pytest.approx(300.0)


values = st.floats(min_value=1e3, max_value=1e9, allow_nan=False)
scopes = st.floats(min_value=0, max_value=1e7, allow_nan=False)


@given(value=values, split=st.floats(0.01, 0.99), s1=scopes, s2=scopes)
def test_splitting_a_holding_changes_nothing(
    value: float, split: float, s1: float, s2: float
) -> None:
    em, fin = {"X": _emissions("X", s1, s2)}, {"X": _fin("X", 1e12)}
    whole = compute_portfolio([_holding("X", value)], em, fin)
    parts = compute_portfolio(
        [_holding("X", value * split), _holding("X", value * (1 - split))], em, fin
    )
    assert parts.financed_emissions_t == pytest.approx(
        whole.financed_emissions_t, rel=1e-9, abs=1e-12
    )


@given(a=values, b=values, k=st.floats(0.1, 100), s1=scopes, s2=scopes)
def test_scaling_scales_financed_not_footprint(
    a: float, b: float, k: float, s1: float, s2: float
) -> None:
    em = {"X": _emissions("X", s1, s2), "Y": _emissions("Y", s2, s1)}
    fin = {"X": _fin("X", 1e12), "Y": _fin("Y", 5e11)}
    base = compute_portfolio([_holding("X", a), _holding("Y", b)], em, fin)
    scaled = compute_portfolio([_holding("X", a * k), _holding("Y", b * k)], em, fin)
    assert scaled.financed_emissions_t == pytest.approx(
        base.financed_emissions_t * k, rel=1e-9, abs=1e-12
    )
    assert scaled.carbon_footprint_t_per_crore == pytest.approx(
        base.carbon_footprint_t_per_crore, rel=1e-9, abs=1e-12
    )


@given(
    holdings=st.lists(
        st.tuples(st.sampled_from(["X", "Y", "Z", None]), values), min_size=1, max_size=8
    )
)
def test_coverage_between_0_and_100(holdings: list[tuple[str | None, float]]) -> None:
    em = {"X": _emissions("X"), "Y": _emissions("Y")}
    fin = {"X": _fin("X", 1e12), "Z": _fin("Z", 1e12)}
    result = compute_portfolio(
        [Holding(isin_or_symbol=str(k), company_key=k, value_inr=v) for k, v in holdings], em, fin
    )
    assert 0 <= result.coverage_pct <= 100
    assert len(result.holdings) + len(result.uncovered) == len(holdings)


def test_cli_compute(tmp_path: Path) -> None:
    snap = tmp_path / "snap"
    build_snapshot(BRSR_DIR, snap)
    out = tmp_path / "result.json"
    result = CliRunner().invoke(
        app,
        [
            "compute",
            "--portfolio",
            str(SYNTHETIC_DIR / "portfolio_synthetic_a.csv"),
            "--evic",
            str(EVIC_CSV),
            "--snapshot",
            str(snap),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "ILLUSTRATIVE" in result.output
    parsed = PortfolioResult.model_validate_json(out.read_text())
    assert parsed.financed_emissions_t == pytest.approx(83.2346091, rel=1e-9)


def _holding(key: str, value: float) -> Holding:
    return Holding(isin_or_symbol=key, company_key=key, value_inr=value)


def _emissions(key: str, s1: float = 100.0, s2: float = 200.0) -> CompanyEmissions:
    return CompanyEmissions(
        company_key=key,
        company_name=f"Synthetic {key}",
        scope1_t=s1,
        scope2_t=s2,
        revenue_inr=1e7,
        assured=True,
        fiscal_year="FY2025-26",
        quality_flag="ok",
    )


def _fin(key: str, evic: float) -> CompanyFinancials:
    return CompanyFinancials(
        company_key=key, evic_inr=evic, evic_source="synthetic", evic_is_illustrative=True
    )
