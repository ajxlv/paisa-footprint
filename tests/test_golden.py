"""Golden snapshot: the fixture build must keep producing exactly these rows.

Any intended change to parsing, validation or normalisation must regenerate the golden file in
the same commit:

    UPDATE_GOLDEN=1 pytest tests/test_golden.py
"""

import json
import os
from pathlib import Path
from typing import Any

import pytest

from pf_core.snapshot import build_snapshot, load_snapshot
from tests.conftest import BRSR_DIR

GOLDEN = Path(__file__).parent / "golden" / "fixtures_summary.json"


def summarise(snapshot_dir: Path) -> list[dict[str, Any]]:
    snap = load_snapshot(snapshot_dir)
    rows = [
        {
            "company": c["company_name"],
            "fy": c["fiscal_year"],
            "scope1_t": c["scope1_t"],
            "scope2_t": c["scope2_t"],
            "revenue_resolved": c["revenue_inr_resolved"],
            "revenue_resolution": c["revenue_resolution"],
            "quality_flag": c["quality_flag"],
            "issues": sorted(c["issues"]),
        }
        for c in snap.companies
    ]
    return sorted(rows, key=lambda r: (r["company"], r["fy"]))


def test_fixture_snapshot_matches_golden(tmp_path: Path) -> None:
    build_snapshot(BRSR_DIR, tmp_path)
    current = summarise(tmp_path)
    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.write_text(
            json.dumps(current, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        pytest.skip("golden file regenerated")
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert len(current) == len(expected) == 40
    for got, want in zip(current, expected, strict=True):
        assert got.keys() == want.keys()
        for key, value in want.items():
            if isinstance(value, float):
                assert got[key] == pytest.approx(value, rel=1e-12), (
                    want["company"],
                    want["fy"],
                    key,
                )
            else:
                assert got[key] == value, (want["company"], want["fy"], key)
