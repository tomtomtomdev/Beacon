"""Himalayas search API as a company-less JobSource — recorded from the public
`/jobs/api/search` endpoint. Remote-only board, so a posting's place is a work-location
restriction, not an office.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.himalayas import ROLE_QUERIES, HimalayasAdapter


@pytest.fixture
def search_ios(load_fixture: Callable[[str], Any]) -> dict[str, Any]:
    return cast(dict[str, Any], load_fixture("himalayas/search_ios.json"))


def make_adapter(
    handler: Callable[[httpx.Request], httpx.Response] | None = None,
    queries: tuple[str, ...] = ("ios engineer",),
    max_pages: int = 1,
) -> HimalayasAdapter:
    transport = httpx.MockTransport(handler) if handler else None
    client = httpx.AsyncClient(transport=transport)
    return HimalayasAdapter(
        PoliteClient(client, min_interval=0.0), queries=queries, page_size=20, max_pages=max_pages
    )


def job(search_ios: dict[str, Any], company: str) -> dict[str, Any]:
    return next(j for j in search_ios["jobs"] if j["companyName"] == company)


def test_himalayas_normalize_us_restricted_posting(search_ios: dict[str, Any]) -> None:
    normalized = make_adapter().normalize(job(search_ios, "Chariot Solutions"))

    assert normalized.source_id == "himalayas"
    assert normalized.external_id == (
        "https://himalayas.app/companies/chariot-solutions/jobs/"
        "senior-ios-developer-swift-objective-c-rest-120-150k-exciting-it-consul"
    )
    assert normalized.title.startswith("Senior IOS Developer")
    assert normalized.company_name == "Chariot Solutions"  # company-less source names its own
    assert normalized.url == normalized.external_id
    assert normalized.location_raw == "United States"
    assert normalized.country == "US"
    assert normalized.city is None
    assert normalized.posted_at == datetime(2026, 8, 12, 7, 39, 27, tzinfo=UTC)
    assert "<p>" not in normalized.description
    assert normalized.content_hash


def test_himalayas_unrestricted_posting_has_no_country(search_ios: dict[str, Any]) -> None:
    normalized = make_adapter().normalize(job(search_ios, "Curotec"))

    # An empty locationRestrictions means "work anywhere" — not a country we may invent.
    assert normalized.location_raw == ""
    assert normalized.country is None


def test_himalayas_normalize_handles_every_recorded_job(search_ios: dict[str, Any]) -> None:
    adapter = make_adapter()

    jobs = [adapter.normalize(raw) for raw in search_ios["jobs"]]

    assert len(jobs) == len(search_ios["jobs"])
    assert all(j.external_id and j.title and j.company_name and j.content_hash for j in jobs)


async def test_himalayas_fetch_runs_every_role_query_and_dedupes_by_guid(
    search_ios: dict[str, Any],
) -> None:
    queried: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        queried.append(request.url.params["q"])
        return httpx.Response(200, json=search_ios)

    raw_postings = await make_adapter(
        handler=handler, queries=("ios engineer", "java backend engineer")
    ).fetch()

    assert queried == ["ios engineer", "java backend engineer"]
    # Both queries returned the same recorded page; a guid is ingested once.
    assert len(raw_postings) == len(search_ios["jobs"])


async def test_himalayas_fetch_stops_at_a_short_page(search_ios: dict[str, Any]) -> None:
    pages: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        pages.append(request.url.params["page"])
        # A page holding fewer than page_size jobs is the last one.
        return httpx.Response(200, json=search_ios)

    await make_adapter(handler=handler, max_pages=5).fetch()

    assert pages == ["1"]


async def test_himalayas_fetch_pages_up_to_the_configured_maximum() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        jobs = [{"guid": f"g{page}-{i}", "title": "iOS Engineer"} for i in range(20)]
        return httpx.Response(200, json={"totalCount": 100, "jobs": jobs})

    raw_postings = await make_adapter(handler=handler, max_pages=2).fetch()

    assert len(raw_postings) == 40  # two full pages, then the cap stops the walk


# The polite door allows one request per second per host, so queries x pages IS the
# wall-clock cost of one poll of this board. The ceiling below is what Himalayas is
# allowed per cycle; a widening that breaks it should be a deliberate decision, not a
# silent regression. The shipped ROLE_QUERIES had no test at all before slice 15.
_MAX_REQUESTS_PER_POLL = 24


@pytest.mark.parametrize("phrasing", ["ios engineer", "ios developer", "swift developer"])
def test_every_ios_phrasing_employers_title_with_is_searched(phrasing: str) -> None:
    # One phrase was the binding constraint on iOS supply, not the page cap: the board
    # carries 565 live iOS postings and a poll read 60 rows of "ios engineer", of which
    # 17 classified iOS (measured 2026-08-23, diagnosed in slice 14).
    assert phrasing in ROLE_QUERIES


async def test_a_full_poll_issues_every_shipped_query_within_its_request_budget() -> None:
    requested: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append((request.url.params["q"], request.url.params["page"]))
        # Every page full, so only the page cap stops the walk — the worst case.
        jobs = [{"guid": f"{len(requested)}-{i}", "title": "iOS Engineer"} for i in range(20)]
        return httpx.Response(200, json={"totalCount": 999, "jobs": jobs})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await HimalayasAdapter(PoliteClient(client, min_interval=0.0)).fetch()

    assert {query for query, _ in requested} == set(ROLE_QUERIES)
    assert len(requested) <= _MAX_REQUESTS_PER_POLL
