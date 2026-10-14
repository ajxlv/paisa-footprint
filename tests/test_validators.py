from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st
from typer.testing import CliRunner

from cli.pf import app
from pf_core.brsr.models import BrsrFiling, FactProvenance, FiscalYearData
from pf_core.brsr.normalise import normalise
from pf_core.brsr.validators import VALIDATORS, v10_intensity_check, validate
from tests.conftest import BRSR_DIR

GHG_NOT_APPLICABLE = {
    "RAJESH EXPORTS LIMITED",
    "Sirca Paints India Limited",
    "ASHIANA HOUSING LIMITED",
    "Vishnu Prakash R Punglia Limited",
    "HMT LIMITED",
}


def companies_hit(filings: list[BrsrFiling], rule: str, severity: str | None = None) -> set[str]:
    return {
        f.company_name
        for f in filings
        for i in VALIDATORS[rule](f)
        if severity is None or i.severity == severity
    }


def test_v1_mtco2e_titan_is_info(by_name: dict[str, BrsrFiling]) -> None:
    issues = VALIDATORS["V1"](by_name["Titan Company Limited"])
    assert [i.severity for i in issues] == ["info", "info"]
    assert "metric tonnes" in issues[0].message


def test_v1_counts(filings: list[BrsrFiling]) -> None:
    # 10 of 15 reporting filings tag emissions MtCO2e (data-check-results.md, finding 1).
    assert len(companies_hit(filings, "V1")) == 10
    # Run 2: the implausible-intensity check is skipped when revenue fails V2, because the
    # implied intensity is then wrong by ~1e7 and only repeats V2. No fixture with trusted revenue
    # crosses the threshold, so every V1 issue on the fixtures is informational.
    assert companies_hit(filings, "V1", "warning") == set()
    assert companies_hit(filings, "V1", "info") == companies_hit(filings, "V1")


def test_v1_warns_when_trusted_revenue_implies_megatonnes() -> None:
    # 1,000,000 t on ₹100 crore of revenue = 10,000 t/₹ cr: plausible, stays info.
    plausible = _constructed(scope1=500_000, scope2=500_000, revenue=1e9, unit="Non-SI:MtCO2e")
    assert {i.severity for i in VALIDATORS["V1"](plausible)} == {"info"}
    # 10,000,000 t on ₹100 crore = 100,000 t/₹ cr: above 50,000, so the unit is doubtful.
    implausible = _constructed(
        scope1=5_000_000, scope2=5_000_000, revenue=1e9, unit="Non-SI:MtCO2e"
    )
    assert "warning" in {i.severity for i in VALIDATORS["V1"](implausible)}


def test_v1_skips_intensity_check_on_untrusted_revenue() -> None:
    filing = _constructed(scope1=5_000_000, scope2=5_000_000, revenue=165.82, unit="Non-SI:MtCO2e")
    assert {i.severity for i in VALIDATORS["V1"](filing)} == {"info"}
    assert VALIDATORS["V2"](filing)  # the revenue problem is still reported, once, by V2


def test_v2_revenue_scale(filings: list[BrsrFiling]) -> None:
    assert companies_hit(filings, "V2") == {
        "GUJARAT THEMIS BIOSYN LIMITED",
        "Everest Kanto Cylinder Limited",
    }
    issue = VALIDATORS["V2"](next(f for f in filings if f.company_name.startswith("GUJARAT")))[0]
    assert issue.severity == "error"
    assert issue.observed_value == "165.82"


def test_v3_revenue_mismatch(filings: list[BrsrFiling], by_name: dict[str, BrsrFiling]) -> None:
    assert VALIDATORS["V3"](by_name["Everest Kanto Cylinder Limited"])
    # Also fires, correctly, on three filings beyond the design doc's example (see MORNING_REVIEW).
    assert companies_hit(filings, "V3") == {
        "Everest Kanto Cylinder Limited",
        "GUJARAT THEMIS BIOSYN LIMITED",
        "Ingersoll-Rand (India) Limited",
        "HMT LIMITED",
    }


def test_v4_zero_year(filings: list[BrsrFiling], by_name: dict[str, BrsrFiling]) -> None:
    assert companies_hit(filings, "V4") == {"GULSHAN POLYOLS LIMITED"}
    issue = VALIDATORS["V4"](by_name["GULSHAN POLYOLS LIMITED"])[0]
    assert issue.fiscal_year == "FY2024-25"


def test_v5_yoy_jump(filings: list[BrsrFiling], by_name: dict[str, BrsrFiling]) -> None:
    assert companies_hit(filings, "V5") == {"Varroc Engineering Limited"}
    issue = VALIDATORS["V5"](by_name["Varroc Engineering Limited"])[0]
    assert issue.field == "scope1"


def test_v6_fiscal_year_end(filings: list[BrsrFiling]) -> None:
    assert companies_hit(filings, "V6") == {"Accelya Solutions India Limited"}


def test_v9_not_applicable(filings: list[BrsrFiling]) -> None:
    assert companies_hit(filings, "V9") == GHG_NOT_APPLICABLE


def test_v10_no_real_fixture_triggers_it(filings: list[BrsrFiling]) -> None:
    # data-check-results.md finding 3: the intensity is derived from S1, S2 and revenue in all 15.
    assert companies_hit(filings, "V10") == set()


def test_v10_constructed_mismatch() -> None:
    filing = _constructed(scope1=100, scope2=100, revenue=1e9, intensity=4e-7)  # true: 2e-7
    issues = v10_intensity_check(filing)
    assert len(issues) == 1
    assert issues[0].rule_id == "V10"


def test_v10_constructed_match_within_rounding() -> None:
    filing = _constructed(scope1=100, scope2=100, revenue=1e9, intensity=2.001e-7)
    assert v10_intensity_check(filing) == []


@pytest.mark.parametrize("name", ["NMDC Limited", "HDFC Bank Limited"])
def test_clean_companies_trigger_nothing(by_name: dict[str, BrsrFiling], name: str) -> None:
    assert validate(by_name[name]) == []
    assert {r.quality_flag for r in normalise(by_name[name])} == {"ok"}


def test_normalise_v1_mtco2e_kept_as_tonnes(by_name: dict[str, BrsrFiling]) -> None:
    row = normalise(by_name["Titan Company Limited"])[0]
    assert row.scope1_t == 3878
    assert "metric tonnes" in row.provenance["scope1_t"].transformation


def test_normalise_v4_zero_becomes_none(by_name: dict[str, BrsrFiling]) -> None:
    current, previous = normalise(by_name["GULSHAN POLYOLS LIMITED"])
    assert current.scope1_t == 26579.29
    assert previous.scope1_t is None
    assert previous.scope2_t is None
    assert previous.quality_flag == "excluded"
    assert previous.provenance["scope1_t"].raw_value == "0"


def test_normalise_v2_is_flagged_not_fixed(by_name: dict[str, BrsrFiling]) -> None:
    row = normalise(by_name["GUJARAT THEMIS BIOSYN LIMITED"])[0]
    assert row.revenue_inr == 165.82
    assert row.intensity_t_per_crore is None
    assert row.quality_flag == "review"


def test_normalise_v9_excluded(by_name: dict[str, BrsrFiling]) -> None:
    for name in GHG_NOT_APPLICABLE:
        assert {r.quality_flag for r in normalise(by_name[name])} == {"excluded"}


def test_quality_flag_counts(filings: list[BrsrFiling]) -> None:
    current = [normalise(f)[0] for f in filings]
    counts = {flag: sum(r.quality_flag == flag for r in current) for flag in ("ok", "review")}
    assert counts == {"ok": 11, "review": 4}
    assert sum(r.quality_flag == "excluded" for r in current) == 5


emission = st.one_of(st.none(), st.just(0.0), st.floats(0, 1e8, allow_nan=False))


@given(
    s1=emission,
    s2=emission,
    p1=emission,
    p2=emission,
    unit=st.sampled_from(["Non-SI:tCO2e", "Non-SI:MtCO2e", "Non-SI:kgCO2e"]),
    applicable=st.sampled_from([True, False, None]),
)
def test_normalise_never_creates_values(
    s1: float | None,
    s2: float | None,
    p1: float | None,
    p2: float | None,
    unit: str,
    applicable: bool | None,
) -> None:
    filing = _constructed(scope1=s1, scope2=s2, prev_scope1=p1, prev_scope2=p2, unit=unit)
    filing.fy_current.ghg_applicable = applicable
    before = sum(v is not None for v in (s1, s2, p1, p2))
    after = sum(v is not None for row in normalise(filing) for v in (row.scope1_t, row.scope2_t))
    assert after <= before


def test_cli_validate_writes_report(tmp_path: object) -> None:
    from pathlib import Path

    out = Path(str(tmp_path)) / "validation_report.csv"
    result = CliRunner().invoke(app, ["validate", str(BRSR_DIR), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert "V2" in result.output
    lines = out.read_text().splitlines()
    assert lines[0].startswith("source_file,")
    assert len(lines) == 1 + 40  # 40 issues across the 20 fixtures


def _constructed(
    scope1: float | None,
    scope2: float | None,
    revenue: float | None = 1e9,
    intensity: float | None = None,
    prev_scope1: float | None = None,
    prev_scope2: float | None = None,
    unit: str = "Non-SI:tCO2e",
) -> BrsrFiling:
    """A synthetic filing built in code; it never touches the real fixtures."""

    def year(start: int, s1: float | None, s2: float | None) -> FiscalYearData:
        facts = {
            field: FactProvenance(
                element=element,
                context_ref="C",
                period_start=date(start, 4, 1),
                period_end=date(start + 1, 3, 31),
                unit_ref="u",
                unit_raw=unit,
                raw_value=str(value),
                decimals="INF",
            )
            for field, element, value in (
                ("scope1", "TotalScope1Emissions", s1),
                ("scope2", "TotalScope2Emissions", s2),
            )
            if value is not None
        }
        return FiscalYearData(
            period_start=date(start, 4, 1),
            period_end=date(start + 1, 3, 31),
            scope1=s1,
            scope2=s2,
            emissions_unit_raw=unit,
            revenue_from_operations_inr=revenue,
            intensity_reported_per_inr=intensity,
            facts=facts,
        )

    return BrsrFiling(
        source_file="constructed.xml",
        company_name="Constructed Test Co (synthetic)",
        cin=None,
        taxonomy=None,
        fy_current=year(2025, scope1, scope2),
        fy_previous=year(2024, prev_scope1, prev_scope2),
    )
