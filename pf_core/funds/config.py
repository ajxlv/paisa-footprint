"""Fund ingestion thresholds, each with its reason."""

from typing import Final

# V8: a scheme's holdings (equity, debt and cash lines together) should add up to ~100% of NAV.
# 95–105% allows for rounding, net receivables/payables and derivative margin lines; outside it a
# block of holdings was probably missed or double counted by the parser. Design doc, section 6.
V8_MIN_PCT_NAV: Final[float] = 95.0
V8_MAX_PCT_NAV: Final[float] = 105.0

# How far above a header row to look for the scheme name and the "as on" date.
HEADER_LOOKBACK_ROWS: Final[int] = 8

# Units AMC files use for market value; a label containing the key is scaled to rupees.
MARKET_VALUE_UNITS: Final[dict[str, float]] = {
    "lakh": 1e5,
    "lac": 1e5,
    "crore": 1e7,
    "cr.": 1e7,
    "'000": 1e3,
    "thousand": 1e3,
}
