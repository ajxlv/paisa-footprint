"""NSE fetcher, driven entirely by httpx.MockTransport. These tests never touch the network."""

import csv
import hashlib
import json
from datetime import date
from itertools import pairwise
from pathlib import Path

import httpx
import pytest

from pf_core.brsr import fetch
from pf_core.brsr.fetch import (
    API_URL,
    NSE_HOME,
    REFERER,
    RSS_URL,
    FilingRef,
    NseClient,
    extract_records,
    fetch_brsr,
    refs_from_record,
    refs_from_rss,
    year_windows,
)

FAKE_XML = b"<xbrli:xbrl xmlns:xbrli='http://www.xbrl.org/2003/instance'/>"
LINK_A = "https://nsearchives.nseindia.com/corporate/xbrl/BRSR_1_WebXMLFile_20260101_101010101.xml"
LINK_B = "https://nsearchives.nseindia.com/corporate/xbrl/BRSR_2_WebXMLFile_20260202_101010101.xml"
# Field names are invented on purpose: the extractor must not depend on NSE's real (unknown) keys.
FAKE_RESPONSE = {
    "data": [
        {
            "companyName": "Synthetic Co A",
            "symbol": "SYNA",
            "submissionDate": "01-Jan-2026",
            "attachments": {"xbrl": LINK_A, "pdf": "https://example.invalid/a.pdf"},
        },
        {"companyName": "Synthetic Co B", "symbol": "SYNB", "fileLink": LINK_B},
        {"companyName": "No XBRL Co", "pdf": "https://nsearchives.nseindia.com/x.pdf"},
    ]
}
FAKE_RSS = f"""<?xml version="1.0"?><rss><channel>
<item><title>Synthetic Co A</title><link>{LINK_A}</link><pubDate>Thu, 01 Jan 2026</pubDate></item>
<item><title>Not a filing</title><link>https://example.invalid/news</link></item>
</channel></rss>""".encode()


class FakeNse:
    """Records every request; can fail the first N calls to a URL to exercise retries."""

    def __init__(self, fail_first: dict[str, int] | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self.fail_first = dict(fail_first or {})

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url).split("?")[0]
        if self.fail_first.get(url, 0) > 0:
            self.fail_first[url] -= 1
            return httpx.Response(503)
        if url == NSE_HOME:
            return httpx.Response(200, text="<html/>", headers={"set-cookie": "nsit=abc; Path=/"})
        if url == API_URL:
            return httpx.Response(200, json=FAKE_RESPONSE)
        if url == RSS_URL:
            return httpx.Response(200, content=FAKE_RSS)
        if url in (LINK_A, LINK_B):
            return httpx.Response(200, content=FAKE_XML)
        return httpx.Response(404)


def make_client(fake: FakeNse) -> tuple[NseClient, list[float]]:
    sleeps: list[float] = []
    now = [0.0]

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    return NseClient(transport=httpx.MockTransport(fake), sleep=sleep, clock=lambda: now[0]), sleeps


def test_year_windows_cover_range_without_gaps() -> None:
    windows = year_windows(date(2022, 1, 1), date(2024, 6, 30))
    assert windows[0] == (date(2022, 1, 1), date(2022, 12, 31))
    assert windows[-1] == (date(2024, 1, 1), date(2024, 6, 30))
    for (_, prev_end), (next_start, _) in pairwise(windows):
        assert (next_start - prev_end).days == 1


def test_tolerant_extractor_finds_links_under_any_key() -> None:
    records = extract_records(FAKE_RESPONSE)
    refs = [ref for record in records for ref in refs_from_record(record)]
    assert [r.url for r in refs] == [LINK_A, LINK_B]
    assert refs[0] == FilingRef(LINK_A, "Synthetic Co A", "SYNA", "01-Jan-2026")
    assert refs[1].submitted_at is None


def test_extract_records_accepts_bare_list() -> None:
    assert extract_records([{"a": 1}, "junk"]) == [{"a": 1}]
    assert extract_records("nonsense") == []


def test_rss_fallback_parses_items() -> None:
    refs = refs_from_rss(FAKE_RSS)
    assert [(r.url, r.company) for r in refs] == [(LINK_A, "Synthetic Co A")]


def test_fetch_api_end_to_end(tmp_path: Path) -> None:
    fake = FakeNse()
    client, _ = make_client(fake)
    summary = fetch_brsr(tmp_path, date(2025, 1, 1), date(2026, 3, 31), client=client)
    assert (summary.links_found, summary.downloaded, summary.failed) == (2, 2, 0)
    assert (tmp_path / "BRSR_1_WebXMLFile_20260101_101010101.xml").read_bytes() == FAKE_XML

    # The home page is loaded first (cookies), then one API call per one-year window.
    assert str(fake.requests[0].url) == NSE_HOME
    api_calls = [r for r in fake.requests if str(r.url).startswith(API_URL)]
    assert [r.url.params["from_date"] for r in api_calls] == ["01-01-2025", "01-01-2026"]
    assert api_calls[0].url.params["to_date"] == "31-12-2025"
    assert api_calls[0].headers["referer"] == REFERER
    assert "Mozilla" in api_calls[0].headers["user-agent"]
    assert api_calls[0].headers.get("cookie") == "nsit=abc"

    schema = json.loads((tmp_path / "_response_schema.json").read_text())
    assert schema["keys"] == sorted(FAKE_RESPONSE["data"][0])

    with (tmp_path / "manifest.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    assert {r["status"] for r in rows} == {"downloaded"}
    assert rows[0]["sha256"] == hashlib.sha256(FAKE_XML).hexdigest()
    assert rows[0]["company"] == "Synthetic Co A"


def test_fetch_is_resumable(tmp_path: Path) -> None:
    client, _ = make_client(FakeNse())
    fetch_brsr(tmp_path, date(2026, 1, 1), date(2026, 3, 31), client=client)
    fake = FakeNse()
    client, _ = make_client(fake)
    summary = fetch_brsr(tmp_path, date(2026, 1, 1), date(2026, 3, 31), client=client)
    assert (summary.downloaded, summary.skipped_existing) == (0, 2)
    assert not any(str(r.url) in (LINK_A, LINK_B) for r in fake.requests)
    with (tmp_path / "manifest.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    assert all(len(r["sha256"]) == 64 for r in rows)  # hashes from the first run are kept


def test_rate_limit_one_request_per_second(tmp_path: Path) -> None:
    client, sleeps = make_client(FakeNse())
    fetch_brsr(tmp_path, date(2026, 1, 1), date(2026, 3, 31), client=client)
    # 4 requests (home, API, 2 files): every request after the first waits a full second.
    assert sleeps == [pytest.approx(1.0)] * 3


def test_retries_with_exponential_backoff(tmp_path: Path) -> None:
    client, sleeps = make_client(FakeNse(fail_first={LINK_A: 3}))
    summary = fetch_brsr(tmp_path, date(2026, 1, 1), date(2026, 3, 31), client=client)
    assert summary.downloaded == 2
    assert [s for s in sleeps if s > 1.0] == [2.0, 4.0, 8.0]


def test_gives_up_after_max_retries_and_records_failure(tmp_path: Path) -> None:
    client, _ = make_client(FakeNse(fail_first={LINK_B: 10}))
    summary = fetch_brsr(tmp_path, date(2026, 1, 1), date(2026, 3, 31), client=client)
    assert (summary.downloaded, summary.failed) == (1, 1)
    assert LINK_B in summary.failures
    with (tmp_path / "manifest.csv").open() as fh:
        statuses = {r["url"]: r["status"] for r in csv.DictReader(fh)}
    assert statuses[LINK_B] == "failed"


def test_rss_source(tmp_path: Path) -> None:
    client, _ = make_client(FakeNse())
    summary = fetch_brsr(tmp_path, date(2026, 1, 1), source="rss", client=client)
    assert (summary.links_found, summary.downloaded) == (1, 1)


def test_unsafe_file_names_are_refused() -> None:
    with pytest.raises(ValueError):
        fetch._file_name("https://nsearchives.nseindia.com/corporate/xbrl/../../evil.xml?x=1")
