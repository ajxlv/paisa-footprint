"""Validator thresholds. Every value carries the reason it was chosen; change none without one."""

from typing import Final

# Rupees in one crore. BRSR reports revenue in rupees; Indian finance reads intensities per crore.
INR_PER_CRORE: Final[float] = 1e7

# V1: implied Scope 1+2 intensity above which a "MtCO2e = metric tonnes" reading is doubtful.
# 50,000 tCO2e per ₹ crore is far above India's most carbon-intensive listed sectors (cement and
# steel sit in the low thousands at most), so crossing it means either the unit really is
# megatonnes or the revenue figure is wrong. Value taken from the design doc, section 6.
V1_MAX_PLAUSIBLE_T_PER_CRORE: Final[float] = 50_000.0

# V2: revenue below ₹10 lakh (₹1,000,000) is treated as a scale error. Every company that must
# file BRSR is a top-1,000 listed company, whose revenue is in the hundreds of crores at least, so
# a figure this small is almost certainly crores or lakhs typed into a rupee field (Gujarat Themis
# files 165.82). The bar is set low on purpose so a genuinely tiny revenue is never "corrected".
V2_MIN_PLAUSIBLE_REVENUE_INR: Final[float] = 1_000_000.0

# V3: maximum ratio between RevenueFromOperations and TotalRevenueOfTheCompany. Total revenue
# adds other income to operating revenue, so it is normally a few percent higher, rarely more than
# tens of percent. A gap above 2x cannot be explained by other income and points to a scale or
# typing error in one of the two fields. Value from the design doc, section 6.
V3_MAX_REVENUE_RATIO: Final[float] = 2.0

# V5: year-on-year change in Scope 1 or Scope 2 above which a human should look. Real emissions
# rarely double or halve in a year without an acquisition, divestment or boundary change; 2x
# catches those (Varroc's Scope 1 rises 3.7x) without flagging ordinary growth. Flag only, never
# auto-correct, because a big change can be real. Value from the design doc, section 6.
V5_MAX_YOY_RATIO: Final[float] = 2.0

# V6: the fiscal year-end most Indian companies use. Anything else is recorded, not corrected.
V6_STANDARD_FY_END_MONTH: Final[int] = 3
V6_STANDARD_FY_END_DAY: Final[int] = 31

# V10: relative tolerance between reported intensity and (S1+S2)/RevenueFromOperations.
# The data check found the reported intensity is derived from those inputs in all 15 filings, so
# anything beyond rounding (1%) means a typo in one of the inputs or in the intensity itself.
V10_REL_TOLERANCE: Final[float] = 0.01

# V10: absolute tolerance. Filers round the intensity to 10 decimal places (e.g. 0.0000003648),
# so a difference below half of the 10th decimal place is rounding, not error. This matters for
# near-zero emitters: Accelya's true intensity is 1.5e-11, which rounds to a reported 0.
V10_ABS_TOLERANCE: Final[float] = 5e-11
