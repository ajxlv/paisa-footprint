from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from pf_core.snapshot import build_snapshot
from tests.conftest import BRSR_DIR, SYNTHETIC_DIR

DOCS = Path(__file__).parent.parent / "docs"


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> TestClient:
    snap = tmp_path_factory.mktemp("snap")
    build_snapshot(BRSR_DIR, snap)
    return TestClient(create_app(snapshot_dir=snap, demo_dir=SYNTHETIC_DIR, docs_dir=DOCS))


def test_health(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["companies"] == 20


def test_companies(client: TestClient) -> None:
    rows = client.get("/companies").json()
    assert len(rows) == 20
    titan = next(r for r in rows if r["company_name"] == "Titan Company Limited")
    assert titan["scope1_t"] == 3878
    assert titan["total_t"] == 3878 + 21181
    assert titan["assured"] is True
    assert titan["quality_flag"] == "ok"
    rajesh = next(r for r in rows if r["company_name"] == "RAJESH EXPORTS LIMITED")
    assert rajesh["scope1_t"] is None
    assert rajesh["total_t"] is None
    assert rajesh["quality_flag"] == "excluded"


def test_company_detail_has_provenance_and_issues(client: TestClient) -> None:
    body = client.get("/companies/INE942C01045").json()  # Gujarat Themis Biosyn
    assert body["summary"]["company_name"] == "GUJARAT THEMIS BIOSYN LIMITED"
    assert len(body["years"]) == 2
    prov = body["years"][0]["provenance"]["revenue_from_operations_inr"]
    assert prov["element"] == "RevenueFromOperations"
    assert prov["raw_value"] == "165.82"
    assert "V2" in prov["transformation"]
    rules = {i["rule_id"] for i in body["issues"]}
    assert {"V1", "V2", "V3"} <= rules
    assert all(i["explanation"] for i in body["issues"])


def test_company_404(client: TestClient) -> None:
    assert client.get("/companies/NOPE").status_code == 404


def test_validation_summary(client: TestClient) -> None:
    body = client.get("/validation/summary").json()
    assert body["companies"] == 20
    assert body["reporting_scope12"] == 15
    assert body["issues_total"] == 40
    assert body["issues_problems"] == 14
    assert body["issues_info"] == 26
    assert body["companies_with_problems"] == 6
    rules = {r["rule_id"]: r for r in body["rules"]}
    assert rules["V2"]["companies"] == 2
    assert rules["V10"]["issues"] == 0
    assert (rules["V1"]["problems"], rules["V1"]["info"]) == (0, 20)
    assert (rules["V3"]["problems"], rules["V3"]["info"]) == (8, 0)
    assert all(r["example"] for r in body["rules"])
    assert len([e for e in body["excluded"] if e["is_current"]]) == 5


def test_demo_portfolios_are_marked_illustrative(client: TestClient) -> None:
    demos = client.get("/demo/portfolios").json()
    assert [d["id"] for d in demos] == [
        "portfolio_synthetic_a",
        "portfolio_synthetic_b",
        "portfolio_synthetic_c",
    ]
    assert all(d["illustrative"] for d in demos)
    assert all(e["evic_is_illustrative"] for d in demos for e in d["evic"])
    assert "ILLUSTRATIVE" in demos[0]["description"]


def test_compute_matches_worked_example(client: TestClient) -> None:
    demo = client.get("/demo/portfolios").json()[0]
    body = client.post(
        "/portfolio/compute", json={"holdings": demo["holdings"], "evic": demo["evic"]}
    ).json()
    assert body["financed_emissions_t"] == pytest.approx(83.2346091, rel=1e-9)
    assert body["carbon_footprint_t_per_crore"] == pytest.approx(2.77448697, rel=1e-9)
    assert body["waci_t_per_crore_revenue"] == pytest.approx(12.973405146532551826, rel=1e-9)
    assert body["coverage_pct"] == 100
    assert body["contains_illustrative_inputs"] is True


def test_compute_user_evic_is_not_illustrative(client: TestClient) -> None:
    body = client.post(
        "/portfolio/compute",
        json={
            "holdings": [{"isin_or_symbol": "NMDC", "value_inr": 1e7}],
            "evic": [{"company_key": "INE584A01023", "evic_inr": 6e11}],
        },
    ).json()
    assert body["contains_illustrative_inputs"] is False
    assert body["financed_emissions_t"] == pytest.approx(198372 / 60000)


def test_compute_rejects_bad_input(client: TestClient) -> None:
    assert client.post("/portfolio/compute", json={"holdings": []}).status_code == 422
    bad = {"holdings": [{"isin_or_symbol": "NMDC", "value_inr": -5}]}
    assert client.post("/portfolio/compute", json=bad).status_code == 422


def test_methodology(client: TestClient) -> None:
    body = client.get("/methodology").json()
    assert body["markdown"].startswith("# Methodology")
    assert "EVIC" in body["markdown"]


def test_openapi(client: TestClient) -> None:
    assert "/portfolio/compute" in client.get("/openapi.json").json()["paths"]


def test_missing_snapshot_gives_503(tmp_path: Path) -> None:
    empty = TestClient(create_app(snapshot_dir=tmp_path, demo_dir=SYNTHETIC_DIR, docs_dir=DOCS))
    response = empty.get("/companies")
    assert response.status_code == 503
    assert "pf build-snapshot" in response.json()["detail"]
