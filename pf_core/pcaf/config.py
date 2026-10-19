"""PCAF engine thresholds. Every value carries the reason it was chosen."""

from typing import Final

# Rupees in one crore; footprints are quoted per ₹ crore invested, WACI per ₹ crore of revenue.
INR_PER_CRORE: Final[float] = 1e7

# EVIC older or newer than this, relative to the emissions fiscal year end, is flagged. PCAF asks
# for EVIC at the same fiscal year end as the emissions; 15 months allows for companies whose
# results land a quarter late without letting a stale market value through silently.
EVIC_MAX_AGE_MONTHS: Final[int] = 15

# An EVIC computed without total debt (market cap only) understates the denominator and so
# overstates attribution. It is usable, but the holding cannot score better than PCAF 2.
PARTIAL_EVIC_SCORE_FLOOR: Final[int] = 2

# Funds whose covered value is below this share are not ranked: a footprint computed on less than
# half of a fund says more about the half we cannot see than about the fund.
FUND_MIN_COVERAGE_PCT: Final[float] = 50.0
