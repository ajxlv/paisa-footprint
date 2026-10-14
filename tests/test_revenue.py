"""Rule V2-fix: safe revenue-scale correction. Real cases come straight from the fixtures."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pf_core.brsr import config
from pf_core.brsr.models import BrsrFiling
from pf_core.brsr.revenue import OPS, TOTAL, agree, resolve_revenue
from pf_core.brsr.validators import year_revenue
from pf_core.pcaf.quality import waci_score


def test_gujarat_themis_fy26_ops_in_crore(by_name: dict[str, BrsrFiling]) -> None:
    res = year_revenue(by_name["GUJARAT THEMIS BIOSYN LIMITED"].fy_current)
    assert (res.ops_filed, res.total_filed) == (165.82, 1658227981)
    assert res.resolution == "inferred_crore"
    assert res.factors == {OPS: 1e7}
    assert res.revenue_inr_resolved == pytest.approx(1_658_200_000)
    assert res.total_revenue_inr_resolved == 1658227981
    assert res.ops_corrected
    assert "RevenueFromOperations 165.82 interpreted as ₹ crore" in res.note
    assert "TotalRevenueOfTheCompany = 1,658,227,981" in res.note


def test_everest_kanto_two_field_crore_and_lakh(by_name: dict[str, BrsrFiling]) -> None:
    res = year_revenue(by_name["Everest Kanto Cylinder Limited"].fy_current)
    assert res.resolution == "inferred_crore"
    assert res.factors == {OPS: 1e7, TOTAL: 1e5}
    assert res.revenue_inr_resolved == pytest.approx(9_344_300_000)
    assert res.total_revenue_inr_resolved == pytest.approx(9_666_900_000)
    assert "two-field correction" in res.note


def test_ingersoll_rand_total_in_lakh(by_name: dict[str, BrsrFiling]) -> None:
    res = year_revenue(by_name["Ingersoll-Rand (India) Limited"].fy_current)
    assert res.resolution == "inferred_lakh"
    assert res.factors == {TOTAL: 1e5}
    assert res.revenue_inr_resolved == 13_923_700_000  # operating revenue untouched
    assert res.total_revenue_inr_resolved == pytest.approx(13_923_703_000)
    assert not res.ops_corrected


def test_hmt_ratio_not_a_power_of_ten_stays_unresolved(by_name: dict[str, BrsrFiling]) -> None:
    res = year_revenue(by_name["HMT LIMITED"].fy_current)
    assert res.resolution == "unresolved"
    assert res.factors == {}
    assert res.revenue_inr_resolved == 259579246
    assert res.total_revenue_inr_resolved == 838698142


def test_gujarat_themis_fy25_has_no_clean_fit(by_name: dict[str, BrsrFiling]) -> None:
    filing = by_name["GUJARAT THEMIS BIOSYN LIMITED"]
    assert filing.fy_previous is not None
    res = year_revenue(filing.fy_previous)
    assert res.resolution == "unresolved"
    assert res.revenue_inr_resolved == 153.23


def test_agreeing_fields_kept_as_filed(by_name: dict[str, BrsrFiling]) -> None:
    res = year_revenue(by_name["NMDC Limited"].fy_current)
    assert res.resolution == "as_filed"
    assert res.factors == {}


def test_single_field_filed_is_used_as_filed(by_name: dict[str, BrsrFiling]) -> None:
    res = year_revenue(by_name["Sirca Paints India Limited"].fy_current)
    assert res.resolution == "as_filed"
    assert "not cross-checked" in res.note


def test_no_revenue_is_unresolved_none() -> None:
    res = resolve_revenue(None, None)
    assert (res.resolution, res.revenue_inr_resolved) == ("unresolved", None)


def test_correction_rejected_if_result_still_below_ten_lakh() -> None:
    # 5 x 1e5 = 5 lakh agrees with total 5,00,000 but is still implausible for a listed company.
    res = resolve_revenue(5.0, 500_000.0)
    assert res.resolution == "unresolved"
    assert res.revenue_inr_resolved == 5.0


def test_ops_in_lakh_inferred() -> None:
    res = resolve_revenue(1000.0, 1000.0 * 1e5 * 1.1)
    assert res.resolution == "inferred_lakh"
    assert res.factors == {OPS: 1e5}


def test_ambiguous_candidates_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    # With the real factors (100x apart) two single-field fits cannot coexist, so the guard is
    # exercised with near-identical factors: both would "fit", so neither may be applied.
    monkeypatch.setattr(config, "REVENUE_SCALE_FACTORS", {"lakh": 1e5, "near_lakh": 1.05e5})
    res = resolve_revenue(1000.0, 1.02e8)
    assert res.resolution == "unresolved"
    assert "Several rescalings fit" in res.note
    assert res.revenue_inr_resolved == 1000.0


def test_waci_quality_capped_at_two_when_revenue_corrected() -> None:
    assert waci_score(assured=True, revenue_corrected=False) == 1
    assert waci_score(assured=True, revenue_corrected=True) == 2
    assert waci_score(assured=None, revenue_corrected=True) == 2


positive = st.floats(min_value=1.0, max_value=1e14, allow_nan=False, allow_infinity=False)


@given(ops=positive, ratio=st.floats(min_value=0.87, max_value=1.15))
def test_never_changes_values_that_already_agree(ops: float, ratio: float) -> None:
    total = ops * ratio
    if not agree(ops, total):
        return  # float rounding at the band edge; the property is about agreeing pairs
    res = resolve_revenue(ops, total)
    assert res.resolution == "as_filed"
    assert (res.revenue_inr_resolved, res.total_revenue_inr_resolved) == (ops, total)


@given(ops=st.one_of(st.none(), positive), total=st.one_of(st.none(), positive))
def test_output_is_filed_or_a_lakh_crore_rescale(ops: float | None, total: float | None) -> None:
    res = resolve_revenue(ops, total)
    allowed = {1.0, 1e5, 1e7}
    for filed, out in ((ops, res.revenue_inr_resolved), (total, res.total_revenue_inr_resolved)):
        if filed is None:
            assert out is None
        else:
            assert out is not None
            assert any(out == pytest.approx(filed * k, rel=1e-12) for k in allowed)
    if res.resolution in ("as_filed", "unresolved"):
        assert res.factors == {}
