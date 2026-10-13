"""Typed records produced by the BRSR parser.

The parser keeps values exactly as filed: no unit conversion, no scale fixes, no zero-filling.
Every extracted figure also carries a `FactProvenance` so any number can be traced back to the
XBRL fact it came from.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict


class FactProvenance(BaseModel):
    """Where one extracted value came from inside the XBRL instance."""

    model_config = ConfigDict(frozen=True)

    element: str
    context_ref: str
    period_start: date | None
    period_end: date
    unit_ref: str | None
    unit_raw: str | None
    raw_value: str
    decimals: str | None


class FiscalYearData(BaseModel):
    """Figures for one fiscal year, as filed. `None` always means "not reported"."""

    period_start: date
    period_end: date
    scope1: float | None = None
    scope2: float | None = None
    scope3: float | None = None
    emissions_unit_raw: str | None = None
    intensity_reported_per_inr: float | None = None
    revenue_from_operations_inr: float | None = None
    total_revenue_inr: float | None = None
    ghg_applicable: bool | None = None
    ghg_assured: bool | None = None
    facts: dict[str, FactProvenance] = {}


class BrsrFiling(BaseModel):
    """One parsed BRSR XBRL filing."""

    source_file: str
    company_name: str
    cin: str | None
    nse_symbol: str | None = None
    isin: str | None = None
    paid_up_capital_inr: float | None = None
    taxonomy: str | None
    fy_current: FiscalYearData
    fy_previous: FiscalYearData | None = None
    parse_notes: list[str] = []

    @property
    def company_key(self) -> str:
        """Stable identifier: ISIN when filed (it is what fund holdings join on), else CIN."""
        return self.isin or self.cin or self.source_file
