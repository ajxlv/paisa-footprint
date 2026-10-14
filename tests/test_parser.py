from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli.pf import app
from pf_core.brsr.models import BrsrFiling
from pf_core.brsr.parser import BrsrParseError, parse_file
from tests.conftest import BRSR_FILES


def test_there_are_twenty_fixtures() -> None:
    assert len(BRSR_FILES) == 20


@pytest.mark.parametrize("path", BRSR_FILES, ids=lambda p: p.name.split("_")[1])
def test_every_fixture_parses(path: Path) -> None:
    filing = parse_file(path)
    assert filing.company_name.strip()
    assert filing.fy_current.period_end is not None
    assert filing.taxonomy == "in-capmkt-ent-2026-02-28.xsd"
    assert filing.parse_notes == []


def test_company_names_are_unique(filings: list[BrsrFiling]) -> None:
    assert len({f.company_name for f in filings}) == 20


def test_previous_year_present_for_every_fixture(filings: list[BrsrFiling]) -> None:
    for f in filings:
        assert f.fy_previous is not None
        assert f.fy_previous.period_end < f.fy_current.period_end


def test_nmdc(by_name: dict[str, BrsrFiling]) -> None:
    f = by_name["NMDC Limited"]
    assert f.fy_current.period_end == date(2026, 3, 31)
    assert f.fy_current.scope1 == 112805
    assert f.fy_current.scope2 == 85567
    assert f.fy_previous is not None
    assert f.fy_previous.scope1 == 103482
    assert f.fy_current.ghg_assured is True
    assert f.nse_symbol == "NMDC"
    assert f.isin == "INE584A01023"


def test_hdfc_bank(by_name: dict[str, BrsrFiling]) -> None:
    f = by_name["HDFC Bank Limited"]
    assert f.fy_current.scope1 == 91849.5
    assert f.fy_current.scope2 == 236495.41


def test_titan_unit_is_kept_raw(by_name: dict[str, BrsrFiling]) -> None:
    f = by_name["Titan Company Limited"]
    assert f.fy_current.scope1 == 3878
    assert f.fy_current.emissions_unit_raw is not None
    assert "MtCO2e" in f.fy_current.emissions_unit_raw


def test_fact_tco2e(by_name: dict[str, BrsrFiling]) -> None:
    f = by_name["FERTILIZERS AND CHEMICALS TRAVANCORE LIMITED"]
    assert f.fy_current.scope1 == 251188.76
    assert f.fy_current.emissions_unit_raw == "Non-SI:tCO2e"


def test_gujarat_themis_revenue_kept_as_filed(by_name: dict[str, BrsrFiling]) -> None:
    f = by_name["GUJARAT THEMIS BIOSYN LIMITED"]
    assert f.fy_current.revenue_from_operations_inr == 165.82


def test_everest_kanto_revenues(by_name: dict[str, BrsrFiling]) -> None:
    f = by_name["Everest Kanto Cylinder Limited"]
    assert f.fy_current.revenue_from_operations_inr == 934.43
    assert f.fy_current.total_revenue_inr == 96669


def test_gulshan_previous_zero_kept_raw(by_name: dict[str, BrsrFiling]) -> None:
    f = by_name["GULSHAN POLYOLS LIMITED"]
    assert f.fy_previous is not None
    assert f.fy_previous.scope1 == 0


def test_varroc_both_years(by_name: dict[str, BrsrFiling]) -> None:
    f = by_name["Varroc Engineering Limited"]
    assert f.fy_current.scope1 == 8020
    assert f.fy_previous is not None
    assert f.fy_previous.scope1 == 2157


def test_rajesh_exports_not_applicable_means_none(by_name: dict[str, BrsrFiling]) -> None:
    f = by_name["RAJESH EXPORTS LIMITED"]
    assert f.fy_current.ghg_applicable is False
    assert f.fy_current.scope1 is None
    assert f.fy_current.scope2 is None


def test_accelya_june_year_end(by_name: dict[str, BrsrFiling]) -> None:
    f = by_name["Accelya Solutions India Limited"]
    assert f.fy_current.period_start == date(2025, 7, 1)
    assert f.fy_current.period_end == date(2026, 6, 30)


def test_missing_assurance_flag_is_none_not_false(by_name: dict[str, BrsrFiling]) -> None:
    # Varroc does not file the assurance element at all.
    assert by_name["Varroc Engineering Limited"].fy_current.ghg_assured is None
    assert by_name["FERTILIZERS AND CHEMICALS TRAVANCORE LIMITED"].fy_current.ghg_assured is False


def test_paid_up_capital(by_name: dict[str, BrsrFiling]) -> None:
    # ValueOfSharesPaidUp, ICYMain instant context, INR.
    assert by_name["Titan Company Limited"].paid_up_capital_inr == 887786160


def test_provenance_points_at_the_fact(by_name: dict[str, BrsrFiling]) -> None:
    prov = by_name["NMDC Limited"].fy_current.facts["scope1"]
    assert prov.element == "TotalScope1Emissions"
    assert prov.context_ref == "DCYMain"
    assert prov.raw_value == "112805"
    assert prov.unit_ref == "tCO2e"
    assert prov.unit_raw == "Non-SI:tCO2e"
    assert prov.period_end == date(2026, 3, 31)


def test_dimensional_facts_are_ignored(tmp_path: Path) -> None:
    xml = _minimal_instance(
        extra_context=(
            '<xbrli:context id="D_Plant"><xbrli:entity><xbrli:identifier scheme="x">I'
            "</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2025-04-01"
            "</xbrli:startDate><xbrli:endDate>2026-03-31</xbrli:endDate></xbrli:period>"
            '<xbrli:scenario><xbrldi:explicitMember dimension="in-capmkt:PlantAxis">'
            "in-capmkt:Plant1</xbrldi:explicitMember></xbrli:scenario></xbrli:context>"
        ),
        extra_facts=(
            '<in-capmkt:TotalScope1Emissions contextRef="D_Plant" unitRef="t" decimals="INF">'
            "999</in-capmkt:TotalScope1Emissions>"
        ),
    )
    path = tmp_path / "x.xml"
    path.write_text(xml)
    filing = parse_file(path)
    assert filing.fy_current.scope1 == 10


def test_missing_name_raises(tmp_path: Path) -> None:
    path = tmp_path / "x.xml"
    path.write_text(_minimal_instance(name=""))
    with pytest.raises(BrsrParseError):
        parse_file(path)


def test_cli_parse_prints_json() -> None:
    nmdc = next(p for p in BRSR_FILES if "BRSR_2729_" in p.name)
    result = CliRunner().invoke(app, ["parse", str(nmdc)])
    assert result.exit_code == 0, result.output
    assert '"company_name": "NMDC Limited"' in result.output


def _minimal_instance(name: str = "Test Co", extra_context: str = "", extra_facts: str = "") -> str:
    name_fact = (
        f'<in-capmkt:NameOfTheCompany contextRef="C">{name}</in-capmkt:NameOfTheCompany>'
        if name
        else ""
    )
    return (
        '<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" '
        'xmlns:xbrldi="http://xbrl.org/2006/xbrldi" '
        'xmlns:in-capmkt="https://www.sebi.gov.in/xbrl/2026-02-28/in-capmkt">'
        '<xbrli:context id="C"><xbrli:entity><xbrli:identifier scheme="x">I'
        "</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2025-04-01"
        "</xbrli:startDate><xbrli:endDate>2026-03-31</xbrli:endDate></xbrli:period>"
        "</xbrli:context>"
        f"{extra_context}"
        '<xbrli:unit id="t"><xbrli:measure>Non-SI:tCO2e</xbrli:measure></xbrli:unit>'
        f"{name_fact}"
        '<in-capmkt:TotalScope1Emissions contextRef="C" unitRef="t" decimals="INF">10'
        "</in-capmkt:TotalScope1Emissions>"
        f"{extra_facts}"
        "</xbrli:xbrl>"
    )
