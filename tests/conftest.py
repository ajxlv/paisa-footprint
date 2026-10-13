from pathlib import Path

import pytest

from pf_core.brsr.models import BrsrFiling
from pf_core.brsr.parser import parse_file

FIXTURES = Path(__file__).parent / "fixtures"
BRSR_DIR = FIXTURES / "brsr"
SYNTHETIC_DIR = FIXTURES / "synthetic"
BRSR_FILES = sorted(BRSR_DIR.glob("*.xml"))


@pytest.fixture(scope="session")
def filings() -> list[BrsrFiling]:
    return [parse_file(p) for p in BRSR_FILES]


@pytest.fixture(scope="session")
def by_name(filings: list[BrsrFiling]) -> dict[str, BrsrFiling]:
    """Filings keyed by the company name read from the file (not the filename)."""
    return {f.company_name: f for f in filings}
