"""Fund portfolio records produced by AMC adapters."""

import re
from datetime import date

from pydantic import BaseModel

# Indian ISINs: "IN" + issuer type + 9 characters. Company securities use "INE"; characters 8–9
# give the security type, and "01" is equity shares (e.g. INE584A01023 is NMDC's equity).
INE_ISIN = re.compile(r"^INE[A-Z0-9]{8}[0-9]$")
EQUITY_ISIN = re.compile(r"^INE[A-Z0-9]{4}01[A-Z0-9]{2}[0-9]$")


class FundHolding(BaseModel):
    """One line of a fund portfolio. Lines without an ISIN (cash, TREPS, receivables) are kept."""

    isin: str | None
    name: str
    quantity: float | None = None
    market_value_inr: float | None = None
    pct_nav: float | None = None

    @property
    def is_equity(self) -> bool:
        """Listed Indian equity share, by ISIN security type ("01")."""
        return self.isin is not None and bool(EQUITY_ISIN.match(self.isin))


class FundPortfolio(BaseModel):
    """One scheme's portfolio as of one date."""

    amc: str
    scheme_name: str
    scheme_code: str | None = None
    as_of_date: date | None
    source_file: str
    sheet: str
    holdings: list[FundHolding]
    illustrative: bool = False
    parse_notes: list[str] = []

    @property
    def fund_key(self) -> str:
        """Stable id: AMC + scheme name + date (scheme codes are rarely in the files)."""
        slug = re.sub(r"[^a-z0-9]+", "-", f"{self.amc} {self.scheme_name}".lower()).strip("-")
        return f"{slug}-{self.as_of_date.isoformat() if self.as_of_date else 'undated'}"
