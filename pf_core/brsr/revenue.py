"""Safe revenue-scale correction (rule V2-fix).

BRSR asks for revenue twice: `RevenueFromOperations` and `TotalRevenueOfTheCompany`. Total
revenue is operating revenue plus other income, so the two should be close. When one of them was
typed in ₹ lakh or ₹ crore instead of rupees, they differ by almost exactly 1e5 or 1e7, and the
other field tells us which reading is right.

The rule is deliberately narrow:

1. If the two fields already agree (within 15%) they are kept as filed. Rescaling both by the same
   factor would always "agree" and proves nothing, so it is never tried.
2. Otherwise exactly one field is rescaled by 1e5 or 1e7. A correction is accepted only if exactly
   one such interpretation makes the fields agree and the corrected operating revenue is at least
   ₹10 lakh.
3. Only if no single-field fix works is one two-field combination tried (one field in crore, the
   other in lakh; Everest Kanto files this way). It, too, must be the only fit.
4. Anything else is `unresolved`: values stay exactly as filed and V2/V3 keep flagging them.

Every result records what was done and why, so a correction is always visible and reversible.
"""

from itertools import product
from typing import Literal

from pydantic import BaseModel

from pf_core.brsr import config

Resolution = Literal["as_filed", "inferred_crore", "inferred_lakh", "unresolved"]

OPS = "revenue_from_operations_inr"
TOTAL = "total_revenue_inr"
_ELEMENT = {OPS: "RevenueFromOperations", TOTAL: "TotalRevenueOfTheCompany"}


class RevenueResolution(BaseModel):
    """Outcome of cross-checking the two revenue fields of one fiscal year."""

    ops_filed: float | None
    total_filed: float | None
    revenue_inr_resolved: float | None
    total_revenue_inr_resolved: float | None
    resolution: Resolution
    factors: dict[str, float] = {}
    note: str

    @property
    def ops_corrected(self) -> bool:
        """True when the operating revenue (the figure used for intensity and WACI) was rescaled."""
        return OPS in self.factors


def agree(a: float, b: float) -> bool:
    """Both positive and within `REVENUE_AGREEMENT_TOLERANCE` of the larger value."""
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) / max(a, b) <= config.REVENUE_AGREEMENT_TOLERANCE


def resolve_revenue(ops: float | None, total: float | None) -> RevenueResolution:
    """Cross-check the two revenue fields and apply a correction only when it is unambiguous."""
    if ops is None or total is None:
        note = (
            "Only one revenue field filed; used as filed, not cross-checked"
            if (ops is None) != (total is None)
            else "No revenue filed"
        )
        return _result(ops, total, {}, "as_filed" if ops is not None else "unresolved", note)
    if agree(ops, total):
        return _result(ops, total, {}, "as_filed", "Both revenue fields agree within 15%")

    scales = list(config.REVENUE_SCALE_FACTORS.values())
    single = [
        {field: k} for field, k in product((OPS, TOTAL), scales) if _fits(ops, total, {field: k})
    ]
    if len(single) == 1:
        return _accept(ops, total, single[0], two_field=False)
    if len(single) > 1:
        return _result(ops, total, {}, "unresolved", "Several rescalings fit; left as filed")

    pairs = [{OPS: a, TOTAL: b} for a, b in product(scales, scales) if a != b]
    two = [p for p in pairs if _fits(ops, total, p)]
    if len(two) == 1:
        return _accept(ops, total, two[0], two_field=True)
    ratio = max(ops, total) / min(ops, total) if min(ops, total) > 0 else float("inf")
    return _result(
        ops,
        total,
        {},
        "unresolved",
        f"Revenue fields disagree (ratio {ratio:.4g}) and no lakh/crore rescaling explains it; "
        "left as filed",
    )


def _fits(ops: float, total: float, factors: dict[str, float]) -> bool:
    return agree(ops * factors.get(OPS, 1.0), total * factors.get(TOTAL, 1.0))


def _accept(
    ops: float, total: float, factors: dict[str, float], two_field: bool
) -> RevenueResolution:
    corrected_ops = ops * factors.get(OPS, 1.0)
    if corrected_ops < config.V2_MIN_PLAUSIBLE_REVENUE_INR:
        return _result(
            ops, total, {}, "unresolved", "Correction would leave revenue under ₹10 lakh"
        )
    filed = {OPS: ops, TOTAL: total}
    other = {OPS: TOTAL, TOTAL: OPS}
    parts = [
        f"{_ELEMENT[field]} {filed[field]:,.2f} interpreted as ₹ {_unit_name(k)}"
        for field, k in factors.items()
    ]
    if two_field:
        evidence = (
            "because the two then agree; this two-field correction is used only because no "
            "single-field correction fits"
        )
    else:
        (field,) = factors
        evidence = f"because {_ELEMENT[other[field]]} = {filed[other[field]]:,.2f}"
    ratio = (total * factors.get(TOTAL, 1.0)) / corrected_ops
    note = (
        f"{' and '.join(parts)} {evidence} "
        f"(ratio before {_raw_ratio(ops, total)}, after {ratio:.4f})"
    )
    # Label by the field that feeds intensity and WACI when it was corrected, else the other one.
    main_factor = factors.get(OPS, factors.get(TOTAL, 1.0))
    label: Resolution = "inferred_crore" if _unit_name(main_factor) == "crore" else "inferred_lakh"
    return _result(ops, total, factors, label, note)


def _raw_ratio(ops: float, total: float) -> str:
    return f"{max(ops, total) / min(ops, total):.4e}"


def _unit_name(factor: float) -> str:
    return next(name for name, k in config.REVENUE_SCALE_FACTORS.items() if k == factor)


def _result(
    ops: float | None,
    total: float | None,
    factors: dict[str, float],
    resolution: Resolution,
    note: str,
) -> RevenueResolution:
    return RevenueResolution(
        ops_filed=ops,
        total_filed=total,
        revenue_inr_resolved=ops * factors.get(OPS, 1.0) if ops is not None else None,
        total_revenue_inr_resolved=total * factors.get(TOTAL, 1.0) if total is not None else None,
        resolution=resolution,
        factors=factors,
        note=note,
    )
