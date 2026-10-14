"""Bulk download of BRSR XBRL filings from NSE, meant to run on the owner's laptop.

NSE blocks cloud servers, so this code is never exercised against the real site in CI. Tests drive
it through `httpx.MockTransport`. Design choices:

* **Tolerant extraction.** The JSON API's field names are undocumented, so we do not depend on
  them. Every string anywhere in a record that points at `nsearchives.nseindia.com/corporate/xbrl/`
  and ends in `.xml` is a filing link. The first record's keys are written to
  `_response_schema.json` so the owner can confirm what NSE actually returns.
* **Polite.** At most one request per second, exponential backoff on transient failures (at most
  4 retries), a browser User-Agent, and the cookies NSE sets on its home page.
* **Resumable and auditable.** Files already on disk are skipped. Every link gets a
  `manifest.csv` row with its SHA-256 and status, so a partial run never loses track of anything.
* **Revisions** (a company re-filing the same year) are resolved after parsing, in
  `pf build-snapshot`, where the fiscal year is actually known.
"""

import csv
import hashlib
import json
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import httpx
from lxml import etree

from pf_core.brsr.parser import SAFE_PARSER

NSE_HOME = "https://www.nseindia.com/"
# NSE's own spelling ("bussiness-sustainabilitiy"); do not "fix" it or the endpoint 404s.
API_URL = "https://www.nseindia.com/api/corporate-bussiness-sustainabilitiy"
REFERER = (
    "https://www.nseindia.com/companies-listing/corporate-filings-bussiness-sustainabilitiy-reports"
)
RSS_URL = "https://nsearchives.nseindia.com/content/RSS/brsr.xml"
ARCHIVE_MARKER = "nsearchives.nseindia.com/corporate/xbrl/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)
MIN_INTERVAL_S = 1.0  # one request per second
MAX_RETRIES = 4
BACKOFF_BASE_S = 2.0  # 2, 4, 8, 16 seconds
RETRY_STATUSES = {429, 500, 502, 503, 504}
MANIFEST_COLUMNS = [
    "company",
    "symbol",
    "url",
    "submitted_at",
    "downloaded_at",
    "sha256",
    "status",
    "file",
]

Source = Literal["api", "rss"]


@dataclass(frozen=True)
class FilingRef:
    """One XBRL link found in an NSE response, with whatever metadata could be identified."""

    url: str
    company: str | None = None
    symbol: str | None = None
    submitted_at: str | None = None


@dataclass
class FetchSummary:
    """What a fetch run did. Every link found ends up in exactly one bucket."""

    links_found: int = 0
    downloaded: int = 0
    skipped_existing: int = 0
    failed: int = 0
    failures: dict[str, str] = field(default_factory=dict)


class NseClient:
    """httpx wrapper adding NSE's headers, cookies, a rate limit and retries."""

    def __init__(
        self,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = httpx.Client(
            transport=transport,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-IN,en;q=0.9",
                "Referer": REFERER,
            },
            follow_redirects=True,
            timeout=30.0,
        )
        self._sleep = sleep
        self._clock = clock
        self._last: float | None = None

    def warm_up(self) -> None:
        """Load the home page once so NSE sets the cookies its API requires."""
        self.get(NSE_HOME)

    def get(self, url: str, params: dict[str, str] | None = None) -> httpx.Response:
        """GET with the rate limit and up to `MAX_RETRIES` retries on transient failures."""
        for attempt in range(MAX_RETRIES + 1):
            self._throttle()
            try:
                response = self._client.get(url, params=params)
            except httpx.TransportError:
                if attempt == MAX_RETRIES:
                    raise
            else:
                if response.status_code not in RETRY_STATUSES or attempt == MAX_RETRIES:
                    response.raise_for_status()
                    return response
            self._sleep(BACKOFF_BASE_S * 2**attempt)
        raise AssertionError("unreachable")  # pragma: no cover

    def close(self) -> None:
        self._client.close()

    def _throttle(self) -> None:
        now = self._clock()
        if self._last is not None and now - self._last < MIN_INTERVAL_S:
            self._sleep(MIN_INTERVAL_S - (now - self._last))
        self._last = self._clock()


def year_windows(start: date, end: date) -> list[tuple[date, date]]:
    """Consecutive windows of at most one year covering [start, end]. The API filters on
    submission date, so windows only need to be contiguous, not aligned to fiscal years."""
    windows: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        stop = min(_add_year(cursor) - timedelta(days=1), end)
        windows.append((cursor, stop))
        cursor = stop + timedelta(days=1)
    return windows


def _add_year(d: date) -> date:
    try:
        return d.replace(year=d.year + 1)
    except ValueError:  # 29 February
        return d.replace(year=d.year + 1, day=28)


def is_filing_link(value: object) -> bool:
    """A string pointing at an NSE XBRL archive file."""
    return isinstance(value, str) and ARCHIVE_MARKER in value and value.lower().endswith(".xml")


def extract_records(payload: Any) -> list[dict[str, Any]]:
    """Top-level records of an API response: a list, or the first list found under a dict."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list) and any(isinstance(r, dict) for r in value):
                return [r for r in value if isinstance(r, dict)]
        return [payload]
    return []


def refs_from_record(record: dict[str, Any]) -> list[FilingRef]:
    """Every filing link inside one record, tagged with any company/symbol/date it carries."""
    links = sorted(set(_strings(record, is_filing_link)))
    meta = {
        "company": _first_value(record, ("companyname", "company", "issuer", "name")),
        "symbol": _first_value(record, ("symbol",)),
        "submitted_at": _first_value(record, ("submission", "submitted", "broadcast", "date")),
    }
    return [FilingRef(url=link, **meta) for link in links]


def _strings(obj: Any, keep: Callable[[object], bool]) -> Iterable[str]:
    if isinstance(obj, dict):
        for value in obj.values():
            yield from _strings(value, keep)
    elif isinstance(obj, list):
        for value in obj:
            yield from _strings(value, keep)
    elif keep(obj):
        assert isinstance(obj, str)
        yield obj


def _first_value(record: dict[str, Any], hints: tuple[str, ...]) -> str | None:
    """First scalar whose key contains one of `hints` (case-insensitive), in hint order."""
    for hint in hints:
        for key, value in record.items():
            if hint in key.lower() and isinstance(value, str | int) and str(value).strip():
                if is_filing_link(value):
                    continue
                return str(value).strip()
    return None


def schema_of(record: dict[str, Any]) -> dict[str, str]:
    """Key -> type name of one record, for `_response_schema.json`."""
    return {key: type(value).__name__ for key, value in record.items()}


def refs_from_rss(xml_bytes: bytes) -> list[FilingRef]:
    """Filing links from NSE's BRSR RSS feed (recent filings only)."""
    root = etree.fromstring(xml_bytes, parser=SAFE_PARSER)
    refs: list[FilingRef] = []
    for item in root.iter("item"):
        texts = [(child.text or "").strip() for child in item]
        links = [t for t in texts if is_filing_link(t)]
        title = item.findtext("title")
        date_text = item.findtext("pubDate")
        refs.extend(
            FilingRef(
                url=link,
                company=title.strip() if title else None,
                submitted_at=date_text.strip() if date_text else None,
            )
            for link in links
        )
    return refs


def fetch_brsr(
    out_dir: str | Path,
    start: date,
    end: date | None = None,
    source: Source = "api",
    client: NseClient | None = None,
) -> FetchSummary:
    """Download every BRSR XBRL file NSE lists between `start` and `end` into `out_dir`."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    nse = client or NseClient()
    try:
        nse.warm_up()
        refs = (
            _list_api(nse, out, start, end or date.today()) if source == "api" else _list_rss(nse)
        )
        return _download_all(nse, out, refs)
    finally:
        if client is None:
            nse.close()


def _list_api(nse: NseClient, out: Path, start: date, end: date) -> list[FilingRef]:
    refs: dict[str, FilingRef] = {}
    schema_written = (out / "_response_schema.json").exists()
    for window_start, window_end in year_windows(start, end):
        params = {
            "index": "equities",
            "from_date": window_start.strftime("%d-%m-%Y"),
            "to_date": window_end.strftime("%d-%m-%Y"),
        }
        records = extract_records(nse.get(API_URL, params=params).json())
        if records and not schema_written:
            _write_schema(out, records[0])
            schema_written = True
        for record in records:
            for ref in refs_from_record(record):
                refs.setdefault(ref.url, ref)
    return list(refs.values())


def _list_rss(nse: NseClient) -> list[FilingRef]:
    return refs_from_rss(nse.get(RSS_URL).content)


def _write_schema(out: Path, record: dict[str, Any]) -> None:
    payload = {"keys": sorted(record), "types": schema_of(record), "example": record}
    (out / "_response_schema.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )


def _download_all(nse: NseClient, out: Path, refs: list[FilingRef]) -> FetchSummary:
    summary = FetchSummary(links_found=len(refs))
    manifest = _read_manifest(out)
    for ref in refs:
        name = _file_name(ref.url)
        target = out / name
        row = {
            "company": ref.company or "",
            "symbol": ref.symbol or "",
            "url": ref.url,
            "submitted_at": ref.submitted_at or "",
            "file": name,
        }
        if target.exists():
            summary.skipped_existing += 1
            previous = manifest.get(ref.url, {})
            manifest[ref.url] = {**row, **previous, "status": "skipped_existing"}
            continue
        try:
            content = nse.get(ref.url).content
        except httpx.HTTPError as exc:
            summary.failed += 1
            summary.failures[ref.url] = f"{type(exc).__name__}: {exc}"
            manifest[ref.url] = {**row, "downloaded_at": "", "sha256": "", "status": "failed"}
            continue
        target.write_bytes(content)
        summary.downloaded += 1
        manifest[ref.url] = {
            **row,
            "downloaded_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "sha256": hashlib.sha256(content).hexdigest(),
            "status": "downloaded",
        }
    _write_manifest(out, manifest)
    return summary


def _file_name(url: str) -> str:
    name = url.rsplit("/", 1)[-1]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.xml", name, flags=re.IGNORECASE):
        raise ValueError(f"Refusing unsafe file name from URL: {url}")
    return name


def _read_manifest(out: Path) -> dict[str, dict[str, str]]:
    path = out / "manifest.csv"
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as fh:
        return {row["url"]: row for row in csv.DictReader(fh)}


def _write_manifest(out: Path, rows: dict[str, dict[str, str]]) -> None:
    with (out / "manifest.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows.values():
            writer.writerow({col: row.get(col, "") for col in MANIFEST_COLUMNS})
