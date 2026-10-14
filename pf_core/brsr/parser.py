"""Parse a BRSR XBRL instance into a `BrsrFiling`.

Design choices (see docs/DECISIONS.md):

* Only non-dimensional facts are used for company totals. A context is dimensional if its
  scenario or segment holds any `xbrldi:explicitMember` or `xbrldi:typedMember`; those facts are
  breakdowns (per plant, per category) and would double count if summed with the totals.
* Current vs previous year is decided from the context period dates (latest end date wins),
  never from context ids and never by assuming an April–March year.
* Units are resolved through `xbrli:unit` and kept verbatim. No unit conversion happens here;
  that is the job of `normalise.py`, where every transformation is recorded.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from lxml import etree

from pf_core.brsr.models import BrsrFiling, FactProvenance, FiscalYearData

XBRLI = "http://www.xbrl.org/2003/instance"
XBRLDI = "http://xbrl.org/2006/xbrldi"
LINK = "http://www.xbrl.org/2003/linkbase"
XLINK = "http://www.w3.org/1999/xlink"
XSI_NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"
NS = {"xbrli": XBRLI, "xbrldi": XBRLDI}

# Every element name below was confirmed to exist in tests/fixtures/brsr/ (see DECISIONS.md).
NUMERIC_FIELDS: dict[str, str] = {
    "scope1": "TotalScope1Emissions",
    "scope2": "TotalScope2Emissions",
    "scope3": "TotalScope3Emissions",
    "intensity_reported_per_inr": "TotalScope1AndScope2EmissionsIntensityPerRupeeOfTurnover",
    "revenue_from_operations_inr": "RevenueFromOperations",
    "total_revenue_inr": "TotalRevenueOfTheCompany",
}
BOOLEAN_FIELDS: dict[str, str] = {
    "ghg_applicable": (
        "WhetherDetailsOfGreenHouseGasEmissionsAndItsIntensityIsApplicableToTheCompany"
    ),
    "ghg_assured": "WhetherDetailsOfGreenHouseGasEmissionsAndItsIntensityIsAssuredByAssurer",
}
IDENTITY_FIELDS: dict[str, str] = {
    "company_name": "NameOfTheCompany",
    "cin": "CorporateIdentityNumber",
    "nse_symbol": "NSESymbol",
    "isin": "ISIN",
}
PAID_UP_CAPITAL = "ValueOfSharesPaidUp"

_WANTED = (
    set(NUMERIC_FIELDS.values())
    | set(BOOLEAN_FIELDS.values())
    | set(IDENTITY_FIELDS.values())
    | {PAID_UP_CAPITAL}
)


class BrsrParseError(ValueError):
    """The file is not a usable BRSR instance (e.g. no company name or no reporting period)."""


@dataclass(frozen=True)
class _Context:
    id: str
    start: date | None
    end: date
    dimensional: bool


@dataclass(frozen=True)
class _Fact:
    element: str
    context: _Context
    unit_ref: str | None
    unit_raw: str | None
    text: str
    decimals: str | None


def parse_file(path: str | Path) -> BrsrFiling:
    """Parse one BRSR XBRL file from disk."""
    path = Path(path)
    root = etree.parse(str(path)).getroot()
    return parse_tree(root, source_file=path.name)


def parse_tree(root: etree._Element, source_file: str) -> BrsrFiling:
    """Parse an already-loaded XBRL root element."""
    contexts = _read_contexts(root)
    units = _read_units(root)
    facts = list(_read_facts(root, contexts, units))
    notes: list[str] = []

    periods = _duration_periods(contexts.values())
    if not periods:
        raise BrsrParseError(f"{source_file}: no non-dimensional duration context")
    current = periods[0]
    previous = periods[1] if len(periods) > 1 else None

    identity = {
        field: _first_text(facts, element, notes) for field, element in IDENTITY_FIELDS.items()
    }
    company_name = identity["company_name"]
    if not company_name:
        raise BrsrParseError(f"{source_file}: NameOfTheCompany missing")

    paid_up = _first_fact(facts, PAID_UP_CAPITAL, notes)
    return BrsrFiling(
        source_file=source_file,
        company_name=company_name,
        cin=identity["cin"],
        nse_symbol=identity["nse_symbol"],
        isin=identity["isin"],
        paid_up_capital_inr=_to_float(paid_up.text, notes, PAID_UP_CAPITAL) if paid_up else None,
        taxonomy=_taxonomy(root),
        fy_current=_year_data(facts, current, notes),
        fy_previous=_year_data(facts, previous, notes) if previous else None,
        parse_notes=notes,
    )


def _read_contexts(root: etree._Element) -> dict[str, _Context]:
    contexts: dict[str, _Context] = {}
    for ctx in root.iterfind("xbrli:context", NS):
        period = ctx.find("xbrli:period", NS)
        if period is None:
            continue
        start = period.findtext("xbrli:startDate", namespaces=NS)
        end = period.findtext("xbrli:endDate", namespaces=NS) or period.findtext(
            "xbrli:instant", namespaces=NS
        )
        if not end:
            continue
        dimensional = (
            ctx.find(".//xbrldi:explicitMember", NS) is not None
            or ctx.find(".//xbrldi:typedMember", NS) is not None
        )
        ctx_id = ctx.get("id") or ""
        contexts[ctx_id] = _Context(
            id=ctx_id,
            start=date.fromisoformat(start.strip()) if start else None,
            end=date.fromisoformat(end.strip()),
            dimensional=dimensional,
        )
    return contexts


def _read_units(root: etree._Element) -> dict[str, str]:
    """Map unit id to a readable measure, e.g. `Non-SI:MtCO2e` or `Non-SI:tCO2e/iso4217:INR`."""
    units: dict[str, str] = {}
    for unit in root.iterfind("xbrli:unit", NS):
        divide = unit.find("xbrli:divide", NS)
        if divide is not None:
            num = _measures(divide.find("xbrli:unitNumerator", NS))
            den = _measures(divide.find("xbrli:unitDenominator", NS))
            units[unit.get("id") or ""] = f"{num}/{den}"
        else:
            units[unit.get("id") or ""] = _measures(unit)
    return units


def _measures(el: etree._Element | None) -> str:
    if el is None:
        return ""
    return "*".join((m.text or "").strip() for m in el.iterfind("xbrli:measure", NS))


def _read_facts(
    root: etree._Element, contexts: dict[str, _Context], units: dict[str, str]
) -> Iterable[_Fact]:
    for el in root:
        if not isinstance(el.tag, str):
            continue
        name = etree.QName(el).localname
        if name not in _WANTED:
            continue
        ctx = contexts.get(el.get("contextRef") or "")
        if ctx is None or ctx.dimensional or el.get(XSI_NIL) == "true":
            continue
        text = (el.text or "").strip()
        if not text:
            continue
        unit_ref = el.get("unitRef")
        yield _Fact(
            element=name,
            context=ctx,
            unit_ref=unit_ref,
            unit_raw=units.get(unit_ref) if unit_ref else None,
            text=text,
            decimals=el.get("decimals"),
        )


def _duration_periods(contexts: Iterable[_Context]) -> list[tuple[date, date]]:
    """Distinct non-dimensional duration periods, latest end date first."""
    periods = {(c.start, c.end) for c in contexts if not c.dimensional and c.start is not None}
    return sorted(
        ((s, e) for s, e in periods if s is not None), key=lambda p: (p[1], p[0]), reverse=True
    )


def _first_fact(facts: list[_Fact], element: str, notes: list[str]) -> _Fact | None:
    matches = [f for f in facts if f.element == element]
    _note_conflicts(matches, element, notes)
    return matches[0] if matches else None


def _first_text(facts: list[_Fact], element: str, notes: list[str]) -> str | None:
    fact = _first_fact(facts, element, notes)
    return fact.text if fact else None


def _note_conflicts(matches: list[_Fact], element: str, notes: list[str]) -> None:
    """Record (never hide) the case where one element has different values in one period."""
    seen: dict[tuple[date | None, date], str] = {}
    for fact in matches:
        key = (fact.context.start, fact.context.end)
        if key in seen and seen[key] != fact.text:
            notes.append(
                f"{element}: conflicting values {seen[key]!r} and {fact.text!r} for period "
                f"ending {fact.context.end}; kept the first"
            )
        seen.setdefault(key, fact.text)


def _year_data(facts: list[_Fact], period: tuple[date, date], notes: list[str]) -> FiscalYearData:
    start, end = period
    in_year = [f for f in facts if f.context.start == start and f.context.end == end]
    values: dict[str, float | bool | None] = {}
    provenance: dict[str, FactProvenance] = {}

    for field, element in (NUMERIC_FIELDS | BOOLEAN_FIELDS).items():
        fact = _first_fact(in_year, element, notes)
        if fact is None:
            values[field] = None
            continue
        if field in BOOLEAN_FIELDS:
            values[field] = _to_bool(fact.text, notes, element)
        else:
            values[field] = _to_float(fact.text, notes, element)
        provenance[field] = FactProvenance(
            element=fact.element,
            context_ref=fact.context.id,
            period_start=fact.context.start,
            period_end=fact.context.end,
            unit_ref=fact.unit_ref,
            unit_raw=fact.unit_raw,
            raw_value=fact.text,
            decimals=fact.decimals,
        )

    unit_source = provenance.get("scope1") or provenance.get("scope2")
    return FiscalYearData.model_validate(
        {
            "period_start": start,
            "period_end": end,
            "emissions_unit_raw": unit_source.unit_raw if unit_source else None,
            "facts": provenance,
            **values,
        }
    )


def _to_float(text: str, notes: list[str], element: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        notes.append(f"{element}: non-numeric value {text!r} treated as missing")
        return None


def _to_bool(text: str, notes: list[str], element: str) -> bool | None:
    lowered = text.lower()
    if lowered in {"true", "1"}:
        return True
    if lowered in {"false", "0"}:
        return False
    notes.append(f"{element}: unrecognised boolean {text!r} treated as missing")
    return None


def _taxonomy(root: etree._Element) -> str | None:
    ref = root.find(f"{{{LINK}}}schemaRef")
    return ref.get(f"{{{XLINK}}}href") if ref is not None else None


def parse_directory(directory: str | Path) -> tuple[list[BrsrFiling], dict[str, str]]:
    """Parse every `*.xml` in a directory. Failures come back with a reason; none are dropped."""
    filings: list[BrsrFiling] = []
    failures: dict[str, str] = {}
    for path in sorted(Path(directory).glob("*.xml")):
        try:
            filings.append(parse_file(path))
        except (BrsrParseError, etree.XMLSyntaxError, ValueError) as exc:
            failures[path.name] = f"{type(exc).__name__}: {exc}"
    return filings, failures
