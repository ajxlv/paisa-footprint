"""PCAF data-quality scores for listed equity (design doc, section 2).

Score 1 = reported emissions verified by a third party; score 2 = reported but not verified.
Scores 3–5 (estimates) are out of scope: holdings without reported emissions get no score and
count against coverage instead.
"""


def holding_score(assured: bool | None) -> int:
    """1 if assurance is confirmed, else 2. Unknown assurance is treated as not assured."""
    return 1 if assured is True else 2


def portfolio_score(weighted: list[tuple[float, int]]) -> float | None:
    """Value-weighted average score over covered holdings, given (value, score) pairs."""
    total = sum(value for value, _ in weighted)
    if total <= 0:
        return None
    return sum(value * score for value, score in weighted) / total
